-- ============================================================
-- 13_migracion_equipos_disciplina.sql
-- Migración puntual para una base YA provisionada (torneos_mvp): aplica
-- docs/plans/equipos-disciplina-navegacion-plan.md — EQUIPOS gana
-- Disciplina_ID y Modalidad_ID (NOT NULL tras el backfill), y la
-- Modalidad tiene que pertenecer a la Disciplina (trigger espejo del que
-- ya valida TORNEO). No es parte de la secuencia 01-06 (esa ya quedó
-- actualizada al estado final — ver 01_schema.sql / 02_constraints.sql /
-- 03_indexes.sql / 05_seed.sql / 06_triggers.sql) — mismo criterio que
-- 07/08/09/12: sin Alembic en este proyecto, y este script SÍ se puede
-- correr más de una vez sin romper nada.
--
-- El orden interno de las partes (A → B → C → D → E → F) importa:
--   A (columnas nullable) antes que todo: sin columnas no hay backfill.
--   B (backfill desde INSCRIPCIONES_TORNEO) antes que C: C solo toca lo
--     que B no pudo resolver.
--   C (huérfanos a Inactivo) antes que E: el SET NOT NULL de E falla si
--     queda un solo NULL.
--   D (reporte) entre C y E a propósito: es el punto de parada humano.
--     Si lista equipos ambiguos, conviene enterarse ACÁ y no cuando E
--     reviente sin decir cuáles son.
--   E (NOT NULL + trigger) antes que F (verificación final).
--
-- Antes de correr esto contra torneos_mvp real: backup primero y
-- verificar contra una réplica (mismo criterio que
-- 09_migracion_torneo_ediciones.sql y 12_migracion_catalogo_disciplinas.sql)
-- — el SET NOT NULL de la PARTE E y el UPDATE de Estado de la PARTE C no
-- son triviales de deshacer a mano.
-- ============================================================

-- ------------------------------------------------------------
-- PARTE A — columnas nullable primero (Decisión #3 = C2)
-- ------------------------------------------------------------
ALTER TABLE EQUIPOS ADD COLUMN IF NOT EXISTS Disciplina_ID INT;
ALTER TABLE EQUIPOS ADD COLUMN IF NOT EXISTS Modalidad_ID INT;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_equipos_disciplina') THEN
        ALTER TABLE EQUIPOS
            ADD CONSTRAINT fk_equipos_disciplina FOREIGN KEY (Disciplina_ID) REFERENCES DISCIPLINA(ID);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_equipos_modalidad') THEN
        ALTER TABLE EQUIPOS
            ADD CONSTRAINT fk_equipos_modalidad FOREIGN KEY (Modalidad_ID) REFERENCES MODALIDAD(ID);
    END IF;
END $$;

-- ------------------------------------------------------------
-- PARTE B — backfill desde las inscripciones existentes (D-Eng-11).
--
-- Un equipo con inscripciones en 2+ disciplinas distintas es exactamente
-- el caso que este plan viene a impedir; si ya existe, se le asigna la
-- primera por orden y la PARTE D lo reporta para revisión manual. NO se
-- falla la migración: abortar dejaría la base a medias sin decir cuáles
-- son los conflictivos (D-Eng-11).
--
-- DISTINCT ON, y no dos MIN() sueltos como decía el borrador del plan: la
-- disciplina y la modalidad tienen que salir de la MISMA fila. Dos MIN()
-- independientes pueden combinar la disciplina de un torneo con la
-- modalidad de otro y producir un par incoherente — que es exactamente lo
-- que el trigger de la PARTE E rechaza, dejando la migración trabada por
-- un dato que ella misma se inventó.
-- ------------------------------------------------------------
UPDATE EQUIPOS e SET
    Disciplina_ID = sub.disciplina_id,
    Modalidad_ID  = sub.modalidad_id
FROM (
    SELECT DISTINCT ON (i.Equipo_ID)
           i.Equipo_ID,
           t.Disciplina_ID AS disciplina_id,
           t.Modalidad_ID  AS modalidad_id
    FROM INSCRIPCIONES_TORNEO i
    JOIN TORNEO t ON t.ID = i.Torneo_ID
    WHERE i.Equipo_ID IS NOT NULL
    ORDER BY i.Equipo_ID, t.Disciplina_ID, t.Modalidad_ID
) sub
WHERE e.ID = sub.Equipo_ID AND e.Disciplina_ID IS NULL;

-- ------------------------------------------------------------
-- PARTE C — huérfanos: equipos sin ninguna inscripción (EC-36, D-Eng-12).
--
-- Regla explícita: NO se les inventa una disciplina. Se los desactiva y
-- se los reporta — son equipos que nunca jugaron nada. El admin los
-- reactiva eligiendo disciplina desde la UI nueva (/torneo-admin/equipos).
-- Borrarlos sería irreversible; inventarles una disciplina rompería el
-- filtro estricto en silencio, que es justo lo que este plan cierra.
--
-- Quedan con Disciplina_ID NULL a propósito hasta acá — la PARTE E no
-- puede aplicar el NOT NULL con ellos así, por eso la PARTE D obliga a
-- resolverlos primero.
--
-- Ojo con cómo se corre el script: con `psql -f` (autocommit por
-- sentencia) esta desactivación QUEDA aplicada aunque la PARTE D después
-- aborte; envuelto en una sola transacción (`psql -1 -f`, o un cliente que
-- mande el archivo entero como un statement), el abort de la PARTE D
-- revierte también esto y los huérfanos siguen Activos. Las dos son
-- correctas —en el segundo caso el efecto se aplica en la corrida buena—
-- y por eso el mensaje de la PARTE D no afirma en qué estado quedaron.
-- Verificado end-to-end contra una base descartable con el esquema viejo
-- (T9/T10 del plan): ambigüos y huérfanos, frenazo, resolución manual,
-- segunda corrida limpia e idempotencia.
-- ------------------------------------------------------------
UPDATE EQUIPOS SET Estado = 'Inactivo'
WHERE Disciplina_ID IS NULL AND Estado = 'Activo';

-- ------------------------------------------------------------
-- PARTE D — reporte ANTES del NOT NULL. Punto de parada humano.
--
-- Dos poblaciones distintas:
--   1. Ambiguos (EC-35): tienen inscripciones en 2+ disciplinas. Ya
--      quedaron backfilleados con la primera por orden — se listan como
--      NOTICE para revisión, no frenan nada.
--   2. Huérfanos (EC-36): siguen con Disciplina_ID NULL. Estos SÍ frenan
--      la migración, con las instrucciones exactas para resolverlos.
-- ------------------------------------------------------------
DO $$
DECLARE
    r RECORD;
    v_ambiguos INT := 0;
    v_huerfanos INT;
BEGIN
    FOR r IN
        SELECT i.Equipo_ID AS equipo_id,
               (SELECT Nombre FROM EQUIPOS WHERE ID = i.Equipo_ID) AS nombre,
               COUNT(DISTINCT t.Disciplina_ID) AS disciplinas
          FROM INSCRIPCIONES_TORNEO i
          JOIN TORNEO t ON t.ID = i.Torneo_ID
         WHERE i.Equipo_ID IS NOT NULL
         GROUP BY i.Equipo_ID
        HAVING COUNT(DISTINCT t.Disciplina_ID) > 1
    LOOP
        v_ambiguos := v_ambiguos + 1;
        RAISE NOTICE 'AMBIGUO (EC-35): equipo % (%) tiene inscripciones en % disciplinas distintas; se le asigno la primera por orden. Revisar a mano.',
            r.equipo_id, r.nombre, r.disciplinas;
    END LOOP;

    IF v_ambiguos > 0 THEN
        RAISE NOTICE '% equipo(s) ambiguo(s) reportados arriba. La migracion continua (D-Eng-11).', v_ambiguos;
    END IF;

    SELECT COUNT(*) INTO v_huerfanos FROM EQUIPOS WHERE Disciplina_ID IS NULL;
    IF v_huerfanos > 0 THEN
        FOR r IN SELECT ID, Nombre FROM EQUIPOS WHERE Disciplina_ID IS NULL ORDER BY ID LOOP
            RAISE NOTICE 'HUERFANO (EC-36): equipo % (%) — sin disciplina inferible, se desactiva (ver la nota de la PARTE C sobre transacciones).', r.ID, r.Nombre;
        END LOOP;
        RAISE EXCEPTION '% equipo(s) sin Disciplina_ID inferible (nunca se inscribieron a nada) — listados arriba. Asignales disciplina y modalidad a mano y volve a correr esta migracion: UPDATE EQUIPOS SET Disciplina_ID = ..., Modalidad_ID = ... WHERE ID = ...;', v_huerfanos;
    END IF;
END $$;

-- ------------------------------------------------------------
-- PARTE E — recién ahora el NOT NULL, y la coherencia disciplina/modalidad
-- (D-Eng-15). fn_validar_equipo_modalidad espeja exactamente a
-- fn_validar_torneo_modalidad (06_triggers.sql) — la modalidad tiene que
-- pertenecer a la disciplina. Se reusa el patrón, no se inventa otro.
-- ------------------------------------------------------------
ALTER TABLE EQUIPOS ALTER COLUMN Disciplina_ID SET NOT NULL;
ALTER TABLE EQUIPOS ALTER COLUMN Modalidad_ID SET NOT NULL;

CREATE OR REPLACE FUNCTION fn_validar_equipo_modalidad()
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

DROP TRIGGER IF EXISTS trg_equipos_validar_modalidad ON EQUIPOS;
CREATE TRIGGER trg_equipos_validar_modalidad
BEFORE INSERT OR UPDATE OF Disciplina_ID, Modalidad_ID ON EQUIPOS
FOR EACH ROW EXECUTE FUNCTION fn_validar_equipo_modalidad();

-- ------------------------------------------------------------
-- PARTE F — índices para los filtros nuevos de GET /equipos
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_equipos_disciplina ON EQUIPOS(Disciplina_ID);
CREATE INDEX IF NOT EXISTS idx_equipos_modalidad ON EQUIPOS(Modalidad_ID);

-- ------------------------------------------------------------
-- PARTE G — Verificación final
-- ------------------------------------------------------------
DO $$
DECLARE
    v_sin_disciplina INT;
    v_incoherentes INT;
    v_inscripciones_cruzadas INT;
BEGIN
    SELECT COUNT(*) INTO v_sin_disciplina
      FROM EQUIPOS WHERE Disciplina_ID IS NULL OR Modalidad_ID IS NULL;
    IF v_sin_disciplina > 0 THEN
        RAISE EXCEPTION 'Migracion incompleta: % EQUIPOS sin Disciplina_ID/Modalidad_ID.', v_sin_disciplina;
    END IF;

    SELECT COUNT(*) INTO v_incoherentes
      FROM EQUIPOS e JOIN MODALIDAD m ON m.ID = e.Modalidad_ID
     WHERE m.Disciplina_ID <> e.Disciplina_ID;
    IF v_incoherentes > 0 THEN
        RAISE EXCEPTION 'Migracion incompleta: % EQUIPOS con una Modalidad que no pertenece a su Disciplina.', v_incoherentes;
    END IF;

    -- No aborta: son inscripciones PREEXISTENTES que la validacion nueva
    -- (InscripcionTorneoService.create) impide crear de ahora en mas. Se
    -- reportan para que el admin decida cancelarlas; borrarlas desde una
    -- migracion seria destructivo y nadie lo pidio.
    SELECT COUNT(*) INTO v_inscripciones_cruzadas
      FROM INSCRIPCIONES_TORNEO i
      JOIN EQUIPOS e ON e.ID = i.Equipo_ID
      JOIN TORNEO t ON t.ID = i.Torneo_ID
     WHERE i.Equipo_ID IS NOT NULL AND e.Disciplina_ID <> t.Disciplina_ID;
    IF v_inscripciones_cruzadas > 0 THEN
        RAISE NOTICE 'ATENCION: % inscripcion(es) preexistente(s) de un equipo en un torneo de OTRA disciplina (equipos ambiguos de la PARTE D). La API ya no permite crear nuevas asi; revisar y cancelar a mano si corresponde.', v_inscripciones_cruzadas;
    END IF;

    RAISE NOTICE 'Migracion equipos-disciplina aplicada: EQUIPOS.Disciplina_ID/Modalidad_ID NOT NULL, trigger trg_equipos_validar_modalidad activo.';
END $$;
