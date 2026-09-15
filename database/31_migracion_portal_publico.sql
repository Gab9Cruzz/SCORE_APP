-- ============================================================
-- 31_migracion_portal_publico.sql
-- Portal Público: Navbar de Disciplinas + Feed de Partidos del Día
-- (docs/plans/portal-publico-feed-partidos-plan.md, T3.1)
--
-- Aditiva. Sin rollback necesario (F11): agrega columnas nuevas a
-- EQUIPOS, TORNEO_GRUPO, TORNEO y DISCIPLINA; el código viejo las
-- ignora. Si algo sale mal, alcanza con un DROP COLUMN de cada una — no
-- hay tablas nuevas ni FKs que dependan de esto.
--
-- Re-ejecutable: todo ADD COLUMN va guardado con information_schema,
-- mismo patrón que 15_/19_/23_.
-- ============================================================

-- ------------------------------------------------------------
-- EQUIPOS.Logo_URL / TORNEO_GRUPO.Pais / TORNEO_GRUPO.Logo_URL (C3)
-- Nacen NULL — T3.4 agrega el formulario para cargarlas, este script
-- solo abre la columna. Ver E-S2 (backend/app/schemas) para el filtro de
-- esquema https:// en LECTURA, que neutraliza lo que entre sucio por acá.
-- ------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE lower(table_name) = 'equipos' AND lower(column_name) = 'logo_url'
    ) THEN
        ALTER TABLE EQUIPOS ADD COLUMN Logo_URL VARCHAR(500);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE lower(table_name) = 'torneo_grupo' AND lower(column_name) = 'pais'
    ) THEN
        ALTER TABLE TORNEO_GRUPO ADD COLUMN Pais VARCHAR(60);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE lower(table_name) = 'torneo_grupo' AND lower(column_name) = 'logo_url'
    ) THEN
        ALTER TABLE TORNEO_GRUPO ADD COLUMN Logo_URL VARCHAR(500);
    END IF;
END $$;

-- ------------------------------------------------------------
-- TORNEO.Publicado (C2/E-M2): gatea si un torneo es visible para un
-- caller anónimo. DEFAULT TRUE al agregar la columna para que el
-- backfill implícito deje a TODOS los torneos existentes exactamente
-- como estaban (públicos — el comportamiento de la API hoy), sin un
-- UPDATE aparte. Después se baja el DEFAULT a FALSE: un torneo creado a
-- partir de esta migración nace SIN publicar — evita que la primera
-- impresión pública de un torneo recién creado (D8c) sean tres tablas de
-- ceros. Las filas viejas quedan públicas; las nuevas se publican a
-- propósito.
-- ------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE lower(table_name) = 'torneo' AND lower(column_name) = 'publicado'
    ) THEN
        ALTER TABLE TORNEO ADD COLUMN Publicado BOOLEAN NOT NULL DEFAULT TRUE;
        ALTER TABLE TORNEO ALTER COLUMN Publicado SET DEFAULT FALSE;
    END IF;
END $$;

-- ------------------------------------------------------------
-- DISCIPLINA.Slug (F3): id legible y estable para un deep link
-- compartible (`/?deporte=futbol`), generado en un solo lugar (la base)
-- para que no haga falta un slugify duplicado en el cliente que tenga
-- que coincidir por casualidad con el que generó el link.
--
-- Sin la extensión `unaccent` (E-B1: `grep -rn "CREATE EXTENSION"
-- database/` no tiene resultados — no está instalada en este repo, y
-- exigirla sumaría un requisito de privilegios de superusuario al
-- entorno de deploy a cambio de nada). Se remueven tildes con
-- `translate()` sobre el catálogo fijo de 28 filas: SQL puro, IMMUTABLE.
-- ------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE lower(table_name) = 'disciplina' AND lower(column_name) = 'slug'
    ) THEN
        ALTER TABLE DISCIPLINA ADD COLUMN Slug VARCHAR(60);
    END IF;
END $$;

-- El trigger es el mecanismo real de alta para filas NUEVAS o renombradas
-- (E-B2: 11_catalogo_disciplinas.sql es re-ejecutable y es el único alta
-- real — routes/disciplinas.py no tiene POST — así que una disciplina
-- agregada después de esta migración nacería con Slug NULL sin esto).
-- CREATE OR REPLACE + DROP TRIGGER IF EXISTS lo dejan idempotente sobre
-- una base ya provisionada.
CREATE OR REPLACE FUNCTION fn_generar_disciplina_slug()
RETURNS TRIGGER AS $$
BEGIN
    -- Ojo con M7 (E-B2): en UPDATE solo si Slug todavía es NULL — un
    -- rename vía PATCH /disciplinas/{id} no debe cambiar (y romper) un
    -- deep link ya compartido.
    IF TG_OP = 'INSERT' OR NEW.Slug IS NULL THEN
        NEW.Slug := regexp_replace(
            regexp_replace(
                translate(lower(NEW.Nombre), 'áéíóúüñ', 'aeiouun'),
                '[^a-z0-9]+', '-', 'g'
            ),
            '(^-+)|(-+$)', '', 'g'
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_disciplina_generar_slug ON DISCIPLINA;
CREATE TRIGGER trg_disciplina_generar_slug
BEFORE INSERT OR UPDATE OF Nombre ON DISCIPLINA
FOR EACH ROW EXECUTE FUNCTION fn_generar_disciplina_slug();

-- Backfill de las filas preexistentes: un UPDATE de Nombre a sí mismo
-- dispara el trigger de arriba (BEFORE UPDATE OF Nombre no exige que el
-- valor cambie). Filas que ya tienen Slug no se tocan de nuevo en la
-- segunda corrida (WHERE Slug IS NULL), así que es idempotente.
UPDATE DISCIPLINA SET Nombre = Nombre WHERE Slug IS NULL;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE lower(table_name) = 'disciplina' AND lower(column_name) = 'slug' AND is_nullable = 'YES'
    ) THEN
        ALTER TABLE DISCIPLINA ALTER COLUMN Slug SET NOT NULL;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE lower(table_name) = 'disciplina' AND constraint_name = 'unique_disciplina_slug'
    ) THEN
        ALTER TABLE DISCIPLINA ADD CONSTRAINT unique_disciplina_slug UNIQUE (Slug);
    END IF;
END $$;

-- ------------------------------------------------------------
-- vw_proximos_partidos (C2/E-B3a/C18): sobre una base ya provisionada,
-- redefine la vista para excluir torneos despublicados — incondicional,
-- esta vista no distingue quién pregunta (ver el comentario largo en
-- 04_views.sql). CREATE OR REPLACE VIEW es idempotente por naturaleza.
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW vw_proximos_partidos AS
SELECT
    p.ID          AS Partido_ID,
    p.TORNEO_ID,
    t.Nombre      AS Torneo,
    el.ID         AS Equipo_Local_ID,
    el.Nombre     AS Equipo_Local,
    ev.ID         AS Equipo_Visitante_ID,
    ev.Nombre     AS Equipo_Visitante,
    p.Fecha_Partido,
    p.Jornada,
    p.Fase,
    p.Grupo,
    p.Estado
FROM PARTIDOS p
JOIN TORNEO  t  ON t.ID  = p.TORNEO_ID
JOIN EQUIPOS el ON el.ID = p.EQUIPOS_ID_LOCAL
JOIN EQUIPOS ev ON ev.ID = p.EQUIPOS_ID_VISITANTE
WHERE p.Estado = 'Programado'
  AND p.Fecha_Partido >= CURRENT_TIMESTAMP
  AND t.Estado  = 'Activo'
  AND el.Estado = 'Activo'
  AND ev.Estado = 'Activo'
  AND t.Publicado = TRUE
ORDER BY p.Fecha_Partido;

-- ------------------------------------------------------------
-- E-G1 (Final Gate D2) — supersede D-A: orden de deportes, gana el
-- pedido del usuario. Fútbol=1, Tenis=2, Baloncesto=3 (antes: Fútbol=1,
-- Baloncesto=2, Tenis=3, ver 15_migracion_popularidad_disciplinas.sql).
-- El resto del ranking no cambia. Mismo patrón de match por Nombre,
-- idempotente (mismos valores cada corrida) — DisciplinaRepository.list
-- ya ordena por Orden_Popularidad NULLS LAST, no hay código que tocar.
-- ------------------------------------------------------------
UPDATE DISCIPLINA SET Orden_Popularidad = v.orden
FROM (VALUES ('Baloncesto', 3), ('Tenis', 2)) AS v(nombre, orden)
WHERE DISCIPLINA.Nombre = v.nombre;

-- ------------------------------------------------------------
-- vw_feed_partidos (T3.2/C5/E-L1/E-L3): sobre una base ya provisionada,
-- crea la vista del feed — ver el comentario largo en 04_views.sql para
-- el porqué de cada JOIN/filtro. CREATE OR REPLACE VIEW es idempotente.
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW vw_feed_partidos AS
SELECT
    r.Partido_ID,
    r.Torneo_ID,
    t.Nombre                                                          AS Torneo,
    tg.ID                                                             AS Torneo_Grupo_ID,
    tg.Nombre                                                         AS Torneo_Grupo,
    tg.Pais,
    CASE WHEN tg.Logo_URL LIKE 'https://%' THEN tg.Logo_URL END       AS Logo_Torneo,
    t.Disciplina_ID,
    d.Nombre                                                          AS Disciplina,
    r.Equipo_Local_ID,
    r.Equipo_Local,
    CASE WHEN el.Logo_URL LIKE 'https://%' THEN el.Logo_URL END       AS Logo_Local,
    r.Equipo_Visitante_ID,
    r.Equipo_Visitante,
    CASE WHEN ev.Logo_URL LIKE 'https://%' THEN ev.Logo_URL END       AS Logo_Visitante,
    r.Fecha_Partido,
    r.Estado,
    r.Goles_Local,
    r.Goles_Visitante
FROM vw_resultados_partidos r
JOIN TORNEO       t  ON t.ID  = r.Torneo_ID
JOIN TORNEO_GRUPO tg ON tg.ID = t.Torneo_Grupo_ID
JOIN DISCIPLINA   d  ON d.ID  = t.Disciplina_ID
JOIN EQUIPOS      el ON el.ID = r.Equipo_Local_ID
JOIN EQUIPOS      ev ON ev.ID = r.Equipo_Visitante_ID
WHERE t.Publicado = TRUE
  AND t.Estado IS DISTINCT FROM 'Inactivo'
  AND tg.Estado <> 'Archivado'
  AND r.Estado <> 'Cancelado'
  AND el.Estado IS DISTINCT FROM 'Inactivo'
  AND ev.Estado IS DISTINCT FROM 'Inactivo';

-- ------------------------------------------------------------
-- Verificación
-- ------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE lower(table_name) = 'torneo' AND lower(column_name) = 'publicado'
    ) THEN
        RAISE EXCEPTION 'Migracion incompleta: TORNEO.Publicado no existe.';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE lower(table_name) = 'disciplina' AND lower(column_name) = 'slug' AND is_nullable = 'NO'
    ) THEN
        RAISE EXCEPTION 'Migracion incompleta: DISCIPLINA.Slug no quedo NOT NULL.';
    END IF;
    RAISE NOTICE 'Migracion 31_ (portal publico) completa.';
END $$;
