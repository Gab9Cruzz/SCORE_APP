-- ============================================================
-- 09_migracion_torneo_ediciones.sql
-- Migración puntual para una base YA provisionada (torneos_mvp): aplica
-- docs/plans/torneos-admin-plan.md — TORNEO_GRUPO + TORNEO.Numero_Edicion,
-- para poder agrupar "Raúl Torneo - Edición 1" y "Raúl Torneo - Edición 2"
-- bajo un mismo grupo. No es parte de la secuencia 01-06 (esa sigue siendo
-- la definición "desde cero" — ver 01_schema.sql, ya actualizado con el
-- estado final).
--
-- Mismo criterio que 07_migracion_roles_arbitro.sql y
-- 08_migracion_equipos_jugadores.sql: sin Alembic en este proyecto, y este
-- script SÍ se puede correr más de una vez sin romper nada — cada paso
-- chequea si ya se aplicó antes de tocar el esquema o de re-backfillear
-- filas ya migradas.
--
-- Backfill: a diferencia de 08 (donde una fila vieja podía tener varias
-- INSCRIPCIONES_TORNEO candidatas y había que desambiguar), acá NO hay
-- ambigüedad posible — cada TORNEO existente se vuelve, 1:1, su propio
-- TORNEO_GRUPO de una sola edición (Numero_Edicion=1), nombrado igual al
-- Nombre actual del torneo. No hay pérdida de datos ni decisión manual
-- pendiente.
--
-- Uso: correr una sola vez contra torneos_mvp (o cualquier base que ya
-- tenga TORNEO sin Torneo_Grupo_ID). Un entorno nuevo NO necesita esto —
-- nace correcto directamente desde 01-06.
-- ============================================================

-- ------------------------------------------------------------
-- PARTE A — Tabla TORNEO_GRUPO
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS TORNEO_GRUPO (
    ID SERIAL PRIMARY KEY,
    Nombre VARCHAR(100) NOT NULL,
    Fecha_Registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Fecha_Modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DROP TRIGGER IF EXISTS trg_torneo_grupo_upd_fecha ON TORNEO_GRUPO;
CREATE TRIGGER trg_torneo_grupo_upd_fecha
BEFORE UPDATE ON TORNEO_GRUPO
FOR EACH ROW EXECUTE FUNCTION fn_actualizar_fecha_modificacion();

-- ------------------------------------------------------------
-- PARTE B — TORNEO: Torneo_Grupo_ID / Numero_Edicion + backfill 1:1
-- ------------------------------------------------------------
ALTER TABLE TORNEO ADD COLUMN IF NOT EXISTS Torneo_Grupo_ID INT;
ALTER TABLE TORNEO ADD COLUMN IF NOT EXISTS Numero_Edicion INT NOT NULL DEFAULT 1;

-- Un TORNEO_GRUPO nuevo por cada TORNEO que todavía no tenga
-- Torneo_Grupo_ID resuelto, nombrado igual a TORNEO.Nombre — el admin
-- puede renombrar el grupo después si quiere separar el nombre del grupo
-- del nombre histórico de la primera edición (torneos-admin-plan.md, EC-25).
DO $$
DECLARE
    v_creados INT;
BEGIN
    INSERT INTO TORNEO_GRUPO (Nombre)
    SELECT t.Nombre
      FROM TORNEO t
     WHERE t.Torneo_Grupo_ID IS NULL;

    GET DIAGNOSTICS v_creados = ROW_COUNT;

    -- El backfill de abajo empareja por Nombre, así que si dos TORNEO
    -- existentes comparten el mismo Nombre exacto (caso raro pero
    -- posible: nada en el esquema viejo lo impedía) terminarían
    -- compartiendo un solo TORNEO_GRUPO con dos "Edición 1" — el UNIQUE
    -- (Torneo_Grupo_ID, Numero_Edicion) de la Parte C lo bloquearía y
    -- abortaría el script, en vez de dejarlo pasar en silencio.
    RAISE NOTICE '% TORNEO_GRUPO creado(s) por backfill (1 por cada torneo existente).', v_creados;
END $$;

UPDATE TORNEO t
   SET Torneo_Grupo_ID = tg.ID
  FROM TORNEO_GRUPO tg
 WHERE tg.Nombre = t.Nombre
   AND t.Torneo_Grupo_ID IS NULL;

DO $$
DECLARE
    v_sin_grupo INT;
    v_duplicados INT;
BEGIN
    SELECT COUNT(*) INTO v_sin_grupo FROM TORNEO WHERE Torneo_Grupo_ID IS NULL;
    IF v_sin_grupo > 0 THEN
        RAISE EXCEPTION '% torneo(s) sin Torneo_Grupo_ID resuelto tras el backfill — no debería pasar (cada torneo crea su propio grupo arriba); revisar manualmente.', v_sin_grupo;
    END IF;

    -- Nombres de torneo duplicados exactos habrían quedado agrupados
    -- juntos por el JOIN de arriba — se detecta ANTES de que el UNIQUE
    -- constraint aborte con un mensaje menos claro.
    SELECT COUNT(*) INTO v_duplicados
      FROM (SELECT Torneo_Grupo_ID FROM TORNEO GROUP BY Torneo_Grupo_ID HAVING COUNT(*) > 1) dup;
    IF v_duplicados > 0 THEN
        RAISE WARNING '% TORNEO_GRUPO quedaron con más de un torneo asociado tras el backfill (nombres de torneo duplicados en el dato original) — antes de que el paso siguiente numere las ediciones, confirmar si de verdad son ediciones del mismo torneo o si conviene separarlas a mano en grupos distintos.', v_duplicados;
    END IF;
END $$;

ALTER TABLE TORNEO ALTER COLUMN Torneo_Grupo_ID SET NOT NULL;

-- Numero_Edicion: si el backfill de arriba dejó más de un TORNEO en el
-- mismo grupo (caso de nombres duplicados, advertido arriba), se numeran
-- por Fecha_Inicio ascendente en vez de dejarlos todos en 1 (que el
-- UNIQUE de la Parte C rechazaría de entrada).
UPDATE TORNEO t
   SET Numero_Edicion = sub.rn
  FROM (
      SELECT ID, ROW_NUMBER() OVER (PARTITION BY Torneo_Grupo_ID ORDER BY Fecha_Inicio, ID) AS rn
        FROM TORNEO
  ) sub
 WHERE sub.ID = t.ID
   AND sub.rn <> t.Numero_Edicion;

-- ------------------------------------------------------------
-- PARTE C — Constraints e índice
-- ------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_torneo_grupo') THEN
        ALTER TABLE TORNEO ADD CONSTRAINT fk_torneo_grupo FOREIGN KEY (Torneo_Grupo_ID) REFERENCES TORNEO_GRUPO(ID) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_torneo_numero_edicion') THEN
        ALTER TABLE TORNEO ADD CONSTRAINT chk_torneo_numero_edicion CHECK (Numero_Edicion > 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'unique_edicion_por_grupo') THEN
        ALTER TABLE TORNEO ADD CONSTRAINT unique_edicion_por_grupo UNIQUE (Torneo_Grupo_ID, Numero_Edicion);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_torneo_grupo ON TORNEO(Torneo_Grupo_ID);

-- ------------------------------------------------------------
-- PARTE D — Verificación final
-- ------------------------------------------------------------
DO $$
DECLARE
    v_total_grupos INT;
    v_total_torneos INT;
BEGIN
    SELECT COUNT(*) INTO v_total_grupos FROM TORNEO_GRUPO;
    SELECT COUNT(*) INTO v_total_torneos FROM TORNEO;
    RAISE NOTICE 'Migracion torneo-ediciones aplicada: % TORNEO_GRUPO para % TORNEO. Revisar los WARNING de arriba si los hubo (nombres de torneo duplicados).', v_total_grupos, v_total_torneos;
END $$;
