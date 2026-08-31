-- ============================================================
-- 17_migracion_motor_formatos.sql
-- Motor de Formatos de Competición (Liga, Eliminación, Grupos + Playoffs)
-- para una base YA provisionada (torneos_mvp) —
-- motor-formatos-plantillas-navegacion-plan.md, requerimiento #4. La
-- secuencia 01-06 ya quedó actualizada al estado final — mismo criterio
-- que 07/08/09/12/13/14/15/16.
--
-- Alcance: columnas nuevas en TORNEO, 4 tablas nuevas (FASE/GRUPO/
-- GRUPO_EQUIPO/SORTEOS), extensión de PARTIDOS (incluye
-- EQUIPOS_ID_LOCAL/VISITANTE pasando a nullable — Decisión Eng #13),
-- 3 triggers nuevos, 1 trigger existente relajado (fn_validar_equipos_
-- inscritos, para tolerar los shells de bracket), 2 vistas rescopadas, y
-- el backfill: toda TORNEO existente recibe su FASE #1 (Tipo='Liga',
-- Decisión G1) y cada uno de sus PARTIDOS existentes queda apuntando a
-- ella — igual que hace TorneoService.create() para un torneo nuevo.
--
-- Re-ejecutable de punta a punta: todo va con guardas (IF NOT EXISTS /
-- pg_constraint / information_schema). El backup previo sigue siendo
-- buena idea por costumbre — es la migración más grande de las 17 hasta
-- acá — pero no hay DROP destructivo en ningún paso.
-- ============================================================

-- ------------------------------------------------------------
-- 1. TORNEO — columnas nuevas
-- ------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE lower(table_name)='torneo' AND lower(column_name)='formato') THEN
        ALTER TABLE TORNEO ADD COLUMN Formato VARCHAR(20) NOT NULL DEFAULT 'Liga';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE lower(table_name)='torneo' AND lower(column_name)='ida_vuelta') THEN
        ALTER TABLE TORNEO ADD COLUMN Ida_Vuelta BOOLEAN NOT NULL DEFAULT FALSE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE lower(table_name)='torneo' AND lower(column_name)='equipos_por_grupo') THEN
        ALTER TABLE TORNEO ADD COLUMN Equipos_Por_Grupo INT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE lower(table_name)='torneo' AND lower(column_name)='clasificados_por_grupo') THEN
        ALTER TABLE TORNEO ADD COLUMN Clasificados_Por_Grupo INT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE lower(table_name)='torneo' AND lower(column_name)='incluye_tercer_lugar') THEN
        ALTER TABLE TORNEO ADD COLUMN Incluye_Tercer_Lugar BOOLEAN NOT NULL DEFAULT TRUE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_torneo_formato') THEN
        ALTER TABLE TORNEO ADD CONSTRAINT chk_torneo_formato CHECK (Formato IN ('Liga', 'Eliminacion', 'Grupos_Playoffs'));
    END IF;
END $$;

-- ------------------------------------------------------------
-- 2. FASE / GRUPO / GRUPO_EQUIPO / SORTEOS — tablas nuevas
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS FASE (
    ID SERIAL PRIMARY KEY,
    Torneo_ID INT NOT NULL,
    Nombre VARCHAR(50) NOT NULL,
    Tipo VARCHAR(20) NOT NULL,
    Orden INT NOT NULL,
    Estado VARCHAR(20) NOT NULL DEFAULT 'Pendiente',
    Fecha_Registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Fecha_Modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS GRUPO (
    ID SERIAL PRIMARY KEY,
    Fase_ID INT NOT NULL,
    Nombre VARCHAR(10) NOT NULL,
    Fecha_Registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS GRUPO_EQUIPO (
    ID SERIAL PRIMARY KEY,
    Grupo_ID INT NOT NULL,
    Inscripcion_Torneo_ID INT NOT NULL,
    Fecha_Registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS SORTEOS (
    ID SERIAL PRIMARY KEY,
    Fase_ID INT NOT NULL,
    Realizado_Por INT NOT NULL,
    Semilla VARCHAR(50),
    Fecha_Sorteo TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Estado VARCHAR(20) NOT NULL DEFAULT 'Completado'
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_fase_torneo') THEN
        ALTER TABLE FASE ADD CONSTRAINT fk_fase_torneo FOREIGN KEY (Torneo_ID) REFERENCES TORNEO(ID) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_fase_tipo') THEN
        ALTER TABLE FASE ADD CONSTRAINT chk_fase_tipo CHECK (Tipo IN ('Liga', 'Grupos', 'Eliminacion'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_fase_estado') THEN
        ALTER TABLE FASE ADD CONSTRAINT chk_fase_estado CHECK (Estado IN ('Pendiente', 'En_Curso', 'Finalizada'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'unique_fase_orden_por_torneo') THEN
        ALTER TABLE FASE ADD CONSTRAINT unique_fase_orden_por_torneo UNIQUE (Torneo_ID, Orden);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_grupo_fase') THEN
        ALTER TABLE GRUPO ADD CONSTRAINT fk_grupo_fase FOREIGN KEY (Fase_ID) REFERENCES FASE(ID) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'unique_grupo_nombre_por_fase') THEN
        ALTER TABLE GRUPO ADD CONSTRAINT unique_grupo_nombre_por_fase UNIQUE (Fase_ID, Nombre);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_grupo_equipo_grupo') THEN
        ALTER TABLE GRUPO_EQUIPO ADD CONSTRAINT fk_grupo_equipo_grupo FOREIGN KEY (Grupo_ID) REFERENCES GRUPO(ID) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_grupo_equipo_inscripcion') THEN
        ALTER TABLE GRUPO_EQUIPO ADD CONSTRAINT fk_grupo_equipo_inscripcion FOREIGN KEY (Inscripcion_Torneo_ID) REFERENCES INSCRIPCIONES_TORNEO(ID);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'unique_grupo_equipo') THEN
        ALTER TABLE GRUPO_EQUIPO ADD CONSTRAINT unique_grupo_equipo UNIQUE (Grupo_ID, Inscripcion_Torneo_ID);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_sorteos_fase') THEN
        ALTER TABLE SORTEOS ADD CONSTRAINT fk_sorteos_fase FOREIGN KEY (Fase_ID) REFERENCES FASE(ID) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_sorteos_usuario') THEN
        ALTER TABLE SORTEOS ADD CONSTRAINT fk_sorteos_usuario FOREIGN KEY (Realizado_Por) REFERENCES USUARIOS(ID);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_sorteos_estado') THEN
        ALTER TABLE SORTEOS ADD CONSTRAINT chk_sorteos_estado CHECK (Estado IN ('Completado', 'Rehecho'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_fase_torneo ON FASE(Torneo_ID);
CREATE INDEX IF NOT EXISTS idx_grupo_fase ON GRUPO(Fase_ID);
CREATE INDEX IF NOT EXISTS idx_grupo_equipo_grupo ON GRUPO_EQUIPO(Grupo_ID);
CREATE INDEX IF NOT EXISTS idx_grupo_equipo_inscripcion ON GRUPO_EQUIPO(Inscripcion_Torneo_ID);
CREATE INDEX IF NOT EXISTS idx_sorteos_fase ON SORTEOS(Fase_ID);

-- ------------------------------------------------------------
-- 3. PARTIDOS — extensión (bracket chaining, Fase_ID/Grupo_ID, nullable
--    EQUIPOS_ID_LOCAL/VISITANTE)
-- ------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE lower(table_name)='partidos' AND lower(column_name)='fase_id') THEN
        ALTER TABLE PARTIDOS ADD COLUMN Fase_ID INT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE lower(table_name)='partidos' AND lower(column_name)='grupo_id') THEN
        ALTER TABLE PARTIDOS ADD COLUMN Grupo_ID INT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE lower(table_name)='partidos' AND lower(column_name)='ronda_nombre') THEN
        ALTER TABLE PARTIDOS ADD COLUMN Ronda_Nombre VARCHAR(30);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE lower(table_name)='partidos' AND lower(column_name)='partido_siguiente_id') THEN
        ALTER TABLE PARTIDOS ADD COLUMN Partido_Siguiente_ID INT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE lower(table_name)='partidos' AND lower(column_name)='slot_siguiente') THEN
        ALTER TABLE PARTIDOS ADD COLUMN Slot_Siguiente VARCHAR(10);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE lower(table_name)='partidos' AND lower(column_name)='partido_perdedor_siguiente_id') THEN
        ALTER TABLE PARTIDOS ADD COLUMN Partido_Perdedor_Siguiente_ID INT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE lower(table_name)='partidos' AND lower(column_name)='slot_perdedor_siguiente') THEN
        ALTER TABLE PARTIDOS ADD COLUMN Slot_Perdedor_Siguiente VARCHAR(10);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE lower(table_name)='partidos' AND lower(column_name)='ganador_desempate_id') THEN
        ALTER TABLE PARTIDOS ADD COLUMN Ganador_Desempate_ID INT;
    END IF;
END $$;

-- Nullable: un partido de ronda 2+ de un bracket se crea antes de saber
-- quién lo juega (Decisión Eng #13).
ALTER TABLE PARTIDOS ALTER COLUMN EQUIPOS_ID_LOCAL DROP NOT NULL;
ALTER TABLE PARTIDOS ALTER COLUMN EQUIPOS_ID_VISITANTE DROP NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_partidos_fase') THEN
        ALTER TABLE PARTIDOS ADD CONSTRAINT fk_partidos_fase FOREIGN KEY (Fase_ID) REFERENCES FASE(ID);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_partidos_grupo') THEN
        ALTER TABLE PARTIDOS ADD CONSTRAINT fk_partidos_grupo FOREIGN KEY (Grupo_ID) REFERENCES GRUPO(ID);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_partidos_siguiente') THEN
        ALTER TABLE PARTIDOS ADD CONSTRAINT fk_partidos_siguiente FOREIGN KEY (Partido_Siguiente_ID) REFERENCES PARTIDOS(ID) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_partidos_perdedor_siguiente') THEN
        ALTER TABLE PARTIDOS ADD CONSTRAINT fk_partidos_perdedor_siguiente FOREIGN KEY (Partido_Perdedor_Siguiente_ID) REFERENCES PARTIDOS(ID) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_partidos_ganador_desempate') THEN
        ALTER TABLE PARTIDOS ADD CONSTRAINT fk_partidos_ganador_desempate FOREIGN KEY (Ganador_Desempate_ID) REFERENCES EQUIPOS(ID);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_partidos_slot_siguiente') THEN
        ALTER TABLE PARTIDOS ADD CONSTRAINT chk_partidos_slot_siguiente CHECK (Slot_Siguiente IS NULL OR Slot_Siguiente IN ('Local', 'Visitante'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_partidos_slot_perdedor_siguiente') THEN
        ALTER TABLE PARTIDOS ADD CONSTRAINT chk_partidos_slot_perdedor_siguiente CHECK (Slot_Perdedor_Siguiente IS NULL OR Slot_Perdedor_Siguiente IN ('Local', 'Visitante'));
    END IF;

    -- chk_partidos_equipos_distintos: la versión vieja (sin tolerar NULL)
    -- bloquearía cualquier shell de bracket. Se reemplaza por la versión
    -- que sí los tolera (misma lógica que 02_constraints.sql).
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_partidos_equipos_distintos') THEN
        ALTER TABLE PARTIDOS DROP CONSTRAINT chk_partidos_equipos_distintos;
    END IF;
    ALTER TABLE PARTIDOS ADD CONSTRAINT chk_partidos_equipos_distintos
        CHECK (EQUIPOS_ID_LOCAL IS NULL OR EQUIPOS_ID_VISITANTE IS NULL OR EQUIPOS_ID_LOCAL <> EQUIPOS_ID_VISITANTE);
END $$;

CREATE INDEX IF NOT EXISTS idx_partidos_fase ON PARTIDOS(Fase_ID);
CREATE INDEX IF NOT EXISTS idx_partidos_grupo ON PARTIDOS(Grupo_ID);
CREATE INDEX IF NOT EXISTS idx_partidos_siguiente ON PARTIDOS(Partido_Siguiente_ID);
CREATE INDEX IF NOT EXISTS idx_partidos_perdedor_siguiente ON PARTIDOS(Partido_Perdedor_Siguiente_ID);

-- ------------------------------------------------------------
-- 4. Trigger existente relajado: un shell de bracket con uno o los dos
--    equipos en NULL todavía no tiene nada que validar.
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_validar_equipos_inscritos()
RETURNS TRIGGER AS $$
DECLARE
    v_inscritos INT;
BEGIN
    IF NEW.EQUIPOS_ID_LOCAL IS NULL OR NEW.EQUIPOS_ID_VISITANTE IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT COUNT(*)
      INTO v_inscritos
      FROM INSCRIPCIONES_TORNEO
     WHERE TORNEO_ID = NEW.TORNEO_ID
       AND EQUIPO_ID IN (NEW.EQUIPOS_ID_LOCAL, NEW.EQUIPOS_ID_VISITANTE)
       AND Estado IN ('Inscrito', 'Confirmado');

    IF v_inscritos < 2 THEN
        RAISE EXCEPTION
            'Ambos equipos deben estar inscritos y no cancelados en el torneo % para disputar un partido.',
            NEW.TORNEO_ID;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ------------------------------------------------------------
-- 5. Triggers nuevos: exclusividad de grupo, validación de desempate,
--    propagación de bracket.
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_validar_equipo_un_grupo_por_fase()
RETURNS TRIGGER AS $$
DECLARE
    v_conflicto INT;
BEGIN
    SELECT COUNT(*) INTO v_conflicto
    FROM GRUPO_EQUIPO ge
    JOIN GRUPO g_new ON g_new.ID = NEW.Grupo_ID
    JOIN GRUPO g_ge  ON g_ge.ID  = ge.Grupo_ID
    WHERE ge.Inscripcion_Torneo_ID = NEW.Inscripcion_Torneo_ID
      AND ge.ID <> COALESCE(NEW.ID, -1)
      AND g_ge.Fase_ID = g_new.Fase_ID;
    IF v_conflicto > 0 THEN
        RAISE EXCEPTION 'equipo_ya_asignado_a_otro_grupo_en_esta_fase';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_grupo_equipo_un_grupo_por_fase ON GRUPO_EQUIPO;
CREATE TRIGGER trg_grupo_equipo_un_grupo_por_fase
BEFORE INSERT OR UPDATE ON GRUPO_EQUIPO
FOR EACH ROW EXECUTE FUNCTION fn_validar_equipo_un_grupo_por_fase();

CREATE OR REPLACE FUNCTION fn_validar_partido_eliminacion_desempate()
RETURNS TRIGGER AS $$
DECLARE
    v_tipo_fase VARCHAR(20);
    v_goles_local INT;
    v_goles_visitante INT;
BEGIN
    IF NEW.Estado = 'Finalizado' AND OLD.Estado <> 'Finalizado' AND NEW.Fase_ID IS NOT NULL THEN
        SELECT Tipo INTO v_tipo_fase FROM FASE WHERE ID = NEW.Fase_ID;
        IF v_tipo_fase = 'Eliminacion' THEN
            SELECT
                COUNT(*) FILTER (WHERE ga.Equipo_Acreditado = NEW.EQUIPOS_ID_LOCAL),
                COUNT(*) FILTER (WHERE ga.Equipo_Acreditado = NEW.EQUIPOS_ID_VISITANTE)
              INTO v_goles_local, v_goles_visitante
              FROM vw_goles_acreditados ga
             WHERE ga.PARTIDOS_ID = NEW.ID;
            IF v_goles_local = v_goles_visitante AND NEW.Ganador_Desempate_ID IS NULL THEN
                RAISE EXCEPTION 'partido_eliminacion_empatado_sin_desempate';
            END IF;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_partido_validar_desempate ON PARTIDOS;
CREATE TRIGGER trg_partido_validar_desempate
BEFORE UPDATE ON PARTIDOS
FOR EACH ROW EXECUTE FUNCTION fn_validar_partido_eliminacion_desempate();

CREATE OR REPLACE FUNCTION fn_propagar_ganador_bracket()
RETURNS TRIGGER AS $$
DECLARE
    v_ganador_id INT;
    v_perdedor_id INT;
    v_goles_local INT;
    v_goles_visitante INT;
BEGIN
    IF NEW.Estado = 'Finalizado' AND OLD.Estado <> 'Finalizado'
       AND (NEW.Partido_Siguiente_ID IS NOT NULL OR NEW.Partido_Perdedor_Siguiente_ID IS NOT NULL) THEN

        SELECT
            COUNT(*) FILTER (WHERE ga.Equipo_Acreditado = NEW.EQUIPOS_ID_LOCAL),
            COUNT(*) FILTER (WHERE ga.Equipo_Acreditado = NEW.EQUIPOS_ID_VISITANTE)
          INTO v_goles_local, v_goles_visitante
          FROM vw_goles_acreditados ga
         WHERE ga.PARTIDOS_ID = NEW.ID;

        v_ganador_id := CASE
            WHEN v_goles_local > v_goles_visitante THEN NEW.EQUIPOS_ID_LOCAL
            WHEN v_goles_visitante > v_goles_local THEN NEW.EQUIPOS_ID_VISITANTE
            ELSE NEW.Ganador_Desempate_ID
        END;
        v_perdedor_id := CASE WHEN v_ganador_id = NEW.EQUIPOS_ID_LOCAL
                               THEN NEW.EQUIPOS_ID_VISITANTE ELSE NEW.EQUIPOS_ID_LOCAL END;

        IF NEW.Partido_Siguiente_ID IS NOT NULL THEN
            UPDATE PARTIDOS
               SET EQUIPOS_ID_LOCAL     = CASE WHEN NEW.Slot_Siguiente = 'Local'
                                                THEN v_ganador_id ELSE EQUIPOS_ID_LOCAL END,
                   EQUIPOS_ID_VISITANTE = CASE WHEN NEW.Slot_Siguiente = 'Visitante'
                                                THEN v_ganador_id ELSE EQUIPOS_ID_VISITANTE END
             WHERE ID = NEW.Partido_Siguiente_ID;
        END IF;

        IF NEW.Partido_Perdedor_Siguiente_ID IS NOT NULL THEN
            UPDATE PARTIDOS
               SET EQUIPOS_ID_LOCAL     = CASE WHEN NEW.Slot_Perdedor_Siguiente = 'Local'
                                                THEN v_perdedor_id ELSE EQUIPOS_ID_LOCAL END,
                   EQUIPOS_ID_VISITANTE = CASE WHEN NEW.Slot_Perdedor_Siguiente = 'Visitante'
                                                THEN v_perdedor_id ELSE EQUIPOS_ID_VISITANTE END
             WHERE ID = NEW.Partido_Perdedor_Siguiente_ID;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_partido_propagar_bracket ON PARTIDOS;
CREATE TRIGGER trg_partido_propagar_bracket
AFTER UPDATE ON PARTIDOS
FOR EACH ROW EXECUTE FUNCTION fn_propagar_ganador_bracket();

-- ------------------------------------------------------------
-- 6. Vistas rescopadas — DROP + CREATE, no CREATE OR REPLACE: Postgres
--    solo permite agregar columnas al FINAL con REPLACE, y Fase_ID/
--    Grupo_ID van antes de Estado en las dos. vw_tabla_posiciones
--    depende de vw_resultados_partidos, así que se dropea primero.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS vw_tabla_posiciones;
DROP VIEW IF EXISTS vw_resultados_partidos;

CREATE VIEW vw_resultados_partidos AS
SELECT
    p.ID       AS Partido_ID,
    p.TORNEO_ID,
    el.ID      AS Equipo_Local_ID,
    el.Nombre  AS Equipo_Local,
    ev_eq.ID   AS Equipo_Visitante_ID,
    ev_eq.Nombre AS Equipo_Visitante,
    COUNT(ga.Evento_Partido_ID)
        FILTER (WHERE ga.Equipo_Acreditado = p.EQUIPOS_ID_LOCAL)     AS Goles_Local,
    COUNT(ga.Evento_Partido_ID)
        FILTER (WHERE ga.Equipo_Acreditado = p.EQUIPOS_ID_VISITANTE) AS Goles_Visitante,
    p.Fecha_Partido,
    p.Jornada,
    p.Fase,
    p.Grupo,
    p.Fase_ID,
    p.Grupo_ID,
    p.Estado
FROM PARTIDOS p
JOIN EQUIPOS el    ON el.ID    = p.EQUIPOS_ID_LOCAL
JOIN EQUIPOS ev_eq ON ev_eq.ID = p.EQUIPOS_ID_VISITANTE
LEFT JOIN vw_goles_acreditados ga ON ga.PARTIDOS_ID = p.ID
GROUP BY p.ID, p.TORNEO_ID, el.ID, el.Nombre, ev_eq.ID, ev_eq.Nombre,
         p.Fecha_Partido, p.Jornada, p.Fase, p.Grupo, p.Fase_ID, p.Grupo_ID, p.Estado;

CREATE VIEW vw_tabla_posiciones AS
WITH lados AS (
    SELECT Fase_ID, Grupo_ID, Torneo_ID, Equipo_Local_ID AS Equipo_ID,
           Goles_Local AS GF, Goles_Visitante AS GC
      FROM vw_resultados_partidos
     WHERE Estado = 'Finalizado'
    UNION ALL
    SELECT Fase_ID, Grupo_ID, Torneo_ID, Equipo_Visitante_ID,
           Goles_Visitante, Goles_Local
      FROM vw_resultados_partidos
     WHERE Estado = 'Finalizado'
)
SELECT
    l.Fase_ID,
    l.Grupo_ID,
    l.Torneo_ID,
    l.Equipo_ID,
    e.Nombre AS Equipo,
    COUNT(*)                                  AS PJ,
    COUNT(*) FILTER (WHERE l.GF >  l.GC)      AS PG,
    COUNT(*) FILTER (WHERE l.GF =  l.GC)      AS PE,
    COUNT(*) FILTER (WHERE l.GF <  l.GC)      AS PP,
    SUM(l.GF)::INT                            AS GF,
    SUM(l.GC)::INT                            AS GC,
    (SUM(l.GF) - SUM(l.GC))::INT              AS DG,
    (COUNT(*) FILTER (WHERE l.GF > l.GC) * 3
     + COUNT(*) FILTER (WHERE l.GF = l.GC))::INT AS PTS
FROM lados l
JOIN EQUIPOS e ON e.ID = l.Equipo_ID
GROUP BY l.Fase_ID, l.Grupo_ID, l.Torneo_ID, l.Equipo_ID, e.Nombre
ORDER BY l.Torneo_ID, l.Fase_ID, l.Grupo_ID NULLS FIRST, PTS DESC, DG DESC, GF DESC, Equipo;

-- ------------------------------------------------------------
-- 7. Backfill: toda TORNEO existente recibe su FASE #1, y cada uno de sus
--    PARTIDOS existentes queda apuntando a ella (Tipo derivado del
--    Formato, que en una base pre-existente es 'Liga' para todos —
--    default de la columna recién agregada).
-- ------------------------------------------------------------
DO $$
DECLARE
    v_torneo RECORD;
    v_fase_id INT;
    v_tipo VARCHAR(20);
    v_nombre VARCHAR(50);
BEGIN
    FOR v_torneo IN SELECT ID, Formato FROM TORNEO LOOP
        IF NOT EXISTS (SELECT 1 FROM FASE WHERE Torneo_ID = v_torneo.ID AND Orden = 1) THEN
            v_tipo := CASE v_torneo.Formato
                WHEN 'Eliminacion' THEN 'Eliminacion'
                WHEN 'Grupos_Playoffs' THEN 'Grupos'
                ELSE 'Liga'
            END;
            v_nombre := CASE v_torneo.Formato
                WHEN 'Eliminacion' THEN 'Eliminatoria'
                WHEN 'Grupos_Playoffs' THEN 'Fase de Grupos'
                ELSE 'Liga Regular'
            END;
            INSERT INTO FASE (Torneo_ID, Nombre, Tipo, Orden, Estado)
            VALUES (
                v_torneo.ID, v_nombre, v_tipo, 1,
                CASE WHEN EXISTS (SELECT 1 FROM PARTIDOS WHERE Torneo_ID = v_torneo.ID) THEN 'En_Curso' ELSE 'Pendiente' END
            )
            RETURNING ID INTO v_fase_id;

            UPDATE PARTIDOS SET Fase_ID = v_fase_id WHERE Torneo_ID = v_torneo.ID AND Fase_ID IS NULL;
        END IF;
    END LOOP;
END $$;

-- ------------------------------------------------------------
-- Verificación
-- ------------------------------------------------------------
DO $$
DECLARE
    v_torneos_sin_fase INT;
    v_faltan TEXT := '';
BEGIN
    SELECT COUNT(*) INTO v_torneos_sin_fase
      FROM TORNEO t WHERE NOT EXISTS (SELECT 1 FROM FASE f WHERE f.Torneo_ID = t.ID);
    IF v_torneos_sin_fase > 0 THEN
        RAISE EXCEPTION 'Migracion incompleta: % torneo(s) sin FASE.', v_torneos_sin_fase;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE lower(table_name)='partidos' AND lower(column_name)='fase_id') THEN
        v_faltan := v_faltan || ' partidos.fase_id';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_partido_propagar_bracket') THEN
        v_faltan := v_faltan || ' trg_partido_propagar_bracket';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_partido_validar_desempate') THEN
        v_faltan := v_faltan || ' trg_partido_validar_desempate';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_grupo_equipo_un_grupo_por_fase') THEN
        v_faltan := v_faltan || ' trg_grupo_equipo_un_grupo_por_fase';
    END IF;
    IF v_faltan <> '' THEN
        RAISE EXCEPTION 'Migracion incompleta: falta%', v_faltan;
    END IF;

    RAISE NOTICE 'Motor de Formatos listo: TORNEO.Formato, FASE/GRUPO/GRUPO_EQUIPO/SORTEOS, PARTIDOS extendido, 3 triggers nuevos, vistas rescopadas. Todo torneo existente quedo con su FASE #1 y sus PARTIDOS apuntando a ella.';
END $$;
