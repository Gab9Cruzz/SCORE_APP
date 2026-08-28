-- ============================================================
-- 12_migracion_catalogo_disciplinas.sql
-- Migración puntual para una base YA provisionada (torneos_mvp): aplica
-- docs/plans/ediciones-catalogo-disciplinas-plan.md, Decisiones A1 y B1 —
-- elimina DISCIPLINA.Tipo (todo pasa a depender de Modalidad.Tamano_Equipo)
-- y permite que INSCRIPCIONES_TORNEO ancle una inscripción individual
-- directo a un Jugador_Perfil_ID, sin fila en EQUIPOS. No es parte de la
-- secuencia 01-06 (esa ya quedó actualizada al estado final — ver
-- 01_schema.sql/02_constraints.sql/06_triggers.sql) — mismo criterio que
-- 07_migracion_roles_arbitro.sql, 08_migracion_equipos_jugadores.sql y
-- 09_migracion_torneo_ediciones.sql: sin Alembic en este proyecto, y este
-- script SÍ se puede correr más de una vez sin romper nada.
--
-- Autocontenido — NO depende de haber corrido 11_catalogo_disciplinas.sql
-- antes. El orden interno de las partes (A → B → C → D → E → F) importa
-- y se verificó ejecutándolo de punta a punta contra una copia de una
-- base con el esquema viejo (ver docs/plans/ediciones-catalogo-disciplinas-plan.md,
-- Fase 1):
--   A (drop Tipo) tiene que ir ANTES que B: el catálogo inserta en
--     DISCIPLINA (Nombre) sin Tipo, que en el esquema viejo es NOT NULL
--     sin default.
--   C (reemplazar fn_validar_torneo_modalidad) tiene que ir ANTES que D:
--     el backfill de D hace un UPDATE sobre TORNEO.Modalidad_ID, que
--     dispara el trigger — con la función VIEJA (que todavía consulta
--     DISCIPLINA.Tipo) ese UPDATE falla porque A ya borró la columna.
--   D (backfill) tiene que ir ANTES que E: da igual en la práctica (E no
--     toca TORNEO), pero mantiene el archivo en el mismo orden narrativo
--     que el resto del plan.
-- Correr 11_catalogo_disciplinas.sql también (antes o después, da igual)
-- es inofensivo — mismos INSERT ... ON CONFLICT DO NOTHING, no duplica
-- nada — pero ya no hace falta para que esta migración funcione sola.
--
-- Antes de correr esto contra torneos_mvp real: backup primero y
-- verificar contra una réplica (mismo criterio que
-- 09_migracion_torneo_ediciones.sql) — la Parte A (DROP COLUMN) y la
-- Parte E (Equipo_ID pasa a nullable) no son triviales de deshacer a mano
-- si algo sale mal.
-- ============================================================

-- ------------------------------------------------------------
-- PARTE A — DISCIPLINA: eliminar Tipo (Decisión A1)
-- ------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_disciplina_tipo') THEN
        ALTER TABLE DISCIPLINA DROP CONSTRAINT chk_disciplina_tipo;
    END IF;
END $$;

ALTER TABLE DISCIPLINA DROP COLUMN IF EXISTS Tipo;

-- unique_disciplina_nombre ya existe desde 02_constraints.sql en toda
-- base provisionada con este proyecto — se agrega igual por si acaso,
-- protegido para no fallar si ya está.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'unique_disciplina_nombre') THEN
        ALTER TABLE DISCIPLINA ADD CONSTRAINT unique_disciplina_nombre UNIQUE (Nombre);
    END IF;
END $$;

-- ------------------------------------------------------------
-- PARTE B — Catálogo maestro (28 disciplinas / 66 modalidades).
-- Mismo contenido que 11_catalogo_disciplinas.sql (D-Eng-8) — inline acá
-- porque la Parte C (backfill) necesita 'Fútbol 11' ya insertada, y este
-- archivo tiene que poder correr solo. Idempotente: ON CONFLICT DO
-- NOTHING sobre unique_disciplina_nombre / unique_modalidad_por_disciplina.
-- ------------------------------------------------------------
INSERT INTO DISCIPLINA (Nombre) VALUES
    ('Fútbol'), ('Fútbol Americano / Flag Football'),
    ('Baloncesto'), ('Voleibol'), ('Hándbol'), ('Rugby'),
    ('Tenis'), ('Ping Pong'), ('Bádminton'), ('Squash / Racquetball'),
    ('Pickleball'), ('Frontón / Pelota Vasca'),
    ('Atletismo'), ('Natación'), ('Ciclismo'), ('Gimnasia'), ('CrossFit'),
    ('MMA'), ('Boxeo'), ('Judo'), ('Taekwondo'), ('Karate'),
    ('League of Legends'), ('CS:GO'), ('Valorant'), ('Rocket League'),
    ('FIFA / EA FC'), ('Ajedrez')
ON CONFLICT (Nombre) DO NOTHING;

INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, m.nombre, m.tamano FROM DISCIPLINA d
JOIN (VALUES
    ('Fútbol 11', 11), ('Fútbol 7', 7), ('Fútbol 5', 5), ('Fútsal', 5)
) AS m(nombre, tamano) ON true
WHERE d.Nombre = 'Fútbol'
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, m.nombre, m.tamano FROM DISCIPLINA d
JOIN (VALUES ('5v5', 5), ('7v7 sin contacto', 7)) AS m(nombre, tamano) ON true
WHERE d.Nombre = 'Fútbol Americano / Flag Football'
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, m.nombre, m.tamano FROM DISCIPLINA d
JOIN (VALUES ('Tradicional', 5), ('3x3', 3)) AS m(nombre, tamano) ON true
WHERE d.Nombre = 'Baloncesto'
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, m.nombre, m.tamano FROM DISCIPLINA d
JOIN (VALUES ('Pista 6x6', 6), ('Playa 2x2', 2)) AS m(nombre, tamano) ON true
WHERE d.Nombre = 'Voleibol'
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, m.nombre, m.tamano FROM DISCIPLINA d
JOIN (VALUES ('Pista', 7), ('Playa', 4)) AS m(nombre, tamano) ON true
WHERE d.Nombre = 'Hándbol'
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, m.nombre, m.tamano FROM DISCIPLINA d
JOIN (VALUES ('Rugby 7', 7), ('Rugby 15', 15)) AS m(nombre, tamano) ON true
WHERE d.Nombre = 'Rugby'
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

-- Raqueta y pala: mismo patrón Singles(1)/Dobles(2) para las 5 disciplinas.
INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, m.nombre, m.tamano FROM DISCIPLINA d
JOIN (VALUES ('Singles', 1), ('Dobles', 2)) AS m(nombre, tamano) ON true
WHERE d.Nombre IN ('Tenis', 'Ping Pong', 'Bádminton', 'Squash / Racquetball', 'Pickleball')
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, m.nombre, m.tamano FROM DISCIPLINA d
JOIN (VALUES ('Individual', 1), ('Parejas', 2)) AS m(nombre, tamano) ON true
WHERE d.Nombre = 'Frontón / Pelota Vasca'
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

-- Marcas y tiempos: todas Tamano_Equipo=1 (individual, sin excepción).
INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, m.nombre, 1 FROM DISCIPLINA d
JOIN (VALUES ('100m'), ('5K'), ('10K'), ('Maratón')) AS m(nombre) ON true
WHERE d.Nombre = 'Atletismo'
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, m.nombre, 1 FROM DISCIPLINA d
JOIN (VALUES ('Libre'), ('Espalda'), ('Pecho'), ('Mariposa')) AS m(nombre) ON true
WHERE d.Nombre = 'Natación'
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, m.nombre, 1 FROM DISCIPLINA d
JOIN (VALUES ('Ruta'), ('MTB'), ('BMX'), ('Velódromo')) AS m(nombre) ON true
WHERE d.Nombre = 'Ciclismo'
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, m.nombre, 1 FROM DISCIPLINA d
JOIN (VALUES ('Artística'), ('Rítmica'), ('Trampolín')) AS m(nombre) ON true
WHERE d.Nombre = 'Gimnasia'
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, 'WODs', 1 FROM DISCIPLINA d WHERE d.Nombre = 'CrossFit'
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

-- Combate: 3 categorías genéricas de peso por disciplina (ver EC-32).
INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, m.nombre, 1 FROM DISCIPLINA d
JOIN (VALUES ('Peso Ligero'), ('Peso Medio'), ('Peso Pesado')) AS m(nombre) ON true
WHERE d.Nombre IN ('MMA', 'Boxeo', 'Judo', 'Taekwondo', 'Karate')
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

-- eSports y estrategia.
INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, '5v5', 5 FROM DISCIPLINA d
WHERE d.Nombre IN ('League of Legends', 'CS:GO', 'Valorant')
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, '3v3', 3 FROM DISCIPLINA d WHERE d.Nombre = 'Rocket League'
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, m.nombre, m.tamano FROM DISCIPLINA d
JOIN (VALUES ('1v1', 1), ('2v2', 2)) AS m(nombre, tamano) ON true
WHERE d.Nombre = 'FIFA / EA FC'
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, m.nombre, 1 FROM DISCIPLINA d
JOIN (VALUES ('Clásico'), ('Rápido'), ('Blitz')) AS m(nombre) ON true
WHERE d.Nombre = 'Ajedrez'
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

-- ------------------------------------------------------------
-- PARTE C — fn_validar_torneo_modalidad: simplificar (ya no hay Tipo que
-- consultar). CREATE OR REPLACE es seguro de re-correr.
--
-- Va ANTES del backfill (Parte D): ese backfill hace un UPDATE sobre
-- TORNEO.Modalidad_ID, que dispara trg_torneo_validar_modalidad — con la
-- versión VIEJA de la función (la que todavía consulta DISCIPLINA.Tipo)
-- ese UPDATE falla, porque la Parte A de acá ya borró esa columna. Se
-- verificó corriendo esta migración end-to-end contra una copia de una
-- base vieja: en el orden original (backfill antes que el reemplazo de la
-- función) revienta con "no existe la columna «tipo»".
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_validar_torneo_modalidad()
RETURNS TRIGGER AS $$
DECLARE
    v_modalidad_disciplina INT;
BEGIN
    SELECT Disciplina_ID INTO v_modalidad_disciplina FROM MODALIDAD WHERE ID = NEW.Modalidad_ID;
    IF v_modalidad_disciplina IS NULL THEN
        RAISE EXCEPTION 'La modalidad indicada no existe.';
    END IF;
    IF v_modalidad_disciplina <> NEW.Disciplina_ID THEN
        RAISE EXCEPTION 'La modalidad indicada no pertenece a esta disciplina.';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ------------------------------------------------------------
-- PARTE D — TORNEO.Modalidad_ID: backfill + NOT NULL (EC-30)
--
-- Usa la modalidad 'Fútbol 11' insertada en la Parte B (por eso el orden
-- dentro de este mismo archivo importa: A → B → C → D, no al revés).
--
-- El torneo real ya jugó con 11 por lado — es completar el dato, no una
-- decisión de producto nueva.
--
-- Solo se backfillea Fútbol a propósito (a diferencia del borrador del
-- plan, que hacía un UPDATE ciego sobre TODO Modalidad_ID NULL): si en
-- esta base hay un torneo de OTRA disciplina sin modalidad, "Fútbol 11"
-- no es un backfill correcto para él y el script debe frenar y avisar,
-- no adivinar.
-- ------------------------------------------------------------
DO $$
DECLARE
    v_modalidad_futbol_11 INT;
    v_pendientes_otra_disciplina INT;
BEGIN
    SELECT m.ID INTO v_modalidad_futbol_11
      FROM MODALIDAD m
      JOIN DISCIPLINA d ON d.ID = m.Disciplina_ID
     WHERE d.Nombre = 'Fútbol' AND m.Nombre = 'Fútbol 11';

    IF v_modalidad_futbol_11 IS NULL THEN
        RAISE EXCEPTION 'No existe la modalidad ''Fútbol 11'' — no debería pasar, la Parte B de este mismo archivo la crea; revisar si esa parte corrió sin errores.';
    END IF;

    UPDATE TORNEO t
       SET Modalidad_ID = v_modalidad_futbol_11
     WHERE t.Modalidad_ID IS NULL
       AND t.Disciplina_ID = (SELECT ID FROM DISCIPLINA WHERE Nombre = 'Fútbol');

    SELECT COUNT(*) INTO v_pendientes_otra_disciplina
      FROM TORNEO
     WHERE Modalidad_ID IS NULL;

    IF v_pendientes_otra_disciplina > 0 THEN
        RAISE EXCEPTION '% torneo(s) sin Modalidad_ID que no son de Fútbol — no hay un backfill automático seguro para ellos; asignales una Modalidad a mano (UPDATE TORNEO SET Modalidad_ID = ... WHERE ID = ...) antes de volver a correr esta migración.', v_pendientes_otra_disciplina;
    END IF;
END $$;

ALTER TABLE TORNEO ALTER COLUMN Modalidad_ID SET NOT NULL;

-- ------------------------------------------------------------
-- PARTE E — INSCRIPCIONES_TORNEO: Equipo_ID nullable + Jugador_Perfil_ID
-- + CHECK exactamente-uno (Decisión B1)
-- ------------------------------------------------------------
ALTER TABLE INSCRIPCIONES_TORNEO ALTER COLUMN Equipo_ID DROP NOT NULL;
ALTER TABLE INSCRIPCIONES_TORNEO ADD COLUMN IF NOT EXISTS Jugador_Perfil_ID INT;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_inscripciones_jugador_perfil') THEN
        ALTER TABLE INSCRIPCIONES_TORNEO
            ADD CONSTRAINT fk_inscripciones_jugador_perfil FOREIGN KEY (Jugador_Perfil_ID)
                REFERENCES JUGADOR_PERFIL_DISCIPLINA(ID) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_inscripcion_exactamente_uno') THEN
        ALTER TABLE INSCRIPCIONES_TORNEO
            ADD CONSTRAINT chk_inscripcion_exactamente_uno CHECK (
                (Equipo_ID IS NOT NULL AND Jugador_Perfil_ID IS NULL) OR
                (Equipo_ID IS NULL AND Jugador_Perfil_ID IS NOT NULL)
            );
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'unique_inscripcion_individual') THEN
        ALTER TABLE INSCRIPCIONES_TORNEO
            ADD CONSTRAINT unique_inscripcion_individual UNIQUE (Torneo_ID, Jugador_Perfil_ID);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_inscripciones_jugador_perfil ON INSCRIPCIONES_TORNEO(Jugador_Perfil_ID);

-- ------------------------------------------------------------
-- PARTE F — Verificación final
-- ------------------------------------------------------------
DO $$
DECLARE
    v_torneos_sin_modalidad INT;
    v_inscripciones_invalidas INT;
    v_tiene_tipo INT;
BEGIN
    SELECT COUNT(*) INTO v_torneos_sin_modalidad FROM TORNEO WHERE Modalidad_ID IS NULL;
    IF v_torneos_sin_modalidad > 0 THEN
        RAISE EXCEPTION 'Migracion incompleta: % TORNEO con Modalidad_ID NULL tras el backfill.', v_torneos_sin_modalidad;
    END IF;

    SELECT COUNT(*) INTO v_inscripciones_invalidas
      FROM INSCRIPCIONES_TORNEO
     WHERE (Equipo_ID IS NULL AND Jugador_Perfil_ID IS NULL)
        OR (Equipo_ID IS NOT NULL AND Jugador_Perfil_ID IS NOT NULL);
    IF v_inscripciones_invalidas > 0 THEN
        RAISE EXCEPTION 'Migracion incompleta: % INSCRIPCIONES_TORNEO no cumplen exactamente-uno-de-Equipo_ID/Jugador_Perfil_ID.', v_inscripciones_invalidas;
    END IF;

    SELECT COUNT(*) INTO v_tiene_tipo
      FROM information_schema.columns
     WHERE lower(table_name) = 'disciplina' AND lower(column_name) = 'tipo';
    IF v_tiene_tipo > 0 THEN
        RAISE EXCEPTION 'Migracion incompleta: DISCIPLINA.Tipo todavia existe.';
    END IF;

    RAISE NOTICE 'Migracion catalogo-disciplinas aplicada: DISCIPLINA.Tipo eliminado, TORNEO.Modalidad_ID NOT NULL, INSCRIPCIONES_TORNEO admite inscripcion individual directa.';
END $$;
