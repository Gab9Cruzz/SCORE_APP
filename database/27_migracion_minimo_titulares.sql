-- ============================================================
-- 27_migracion_minimo_titulares.sql
-- "Gestionar Partido": mínimo reglamentario para iniciar + soporte de
-- concurrencia y llegadas tardías en la convocatoria
-- (docs/plans/gestionar-partido-alineaciones-plan.md, D1 / H4-eng / H5-eng),
-- para una base YA provisionada (torneos_mvp). La secuencia 01-06 ya quedó
-- actualizada al estado final — mismo criterio que 07/08/09/12/13/14/18/19/
-- 20/21/22/23/24/25.
--
-- Numerada 27 (sigue a 26_migracion_rbac_licencias_torneos.sql).
--
-- Aditiva pura: 4 columnas nuevas, 3 constraints y 1 trigger. NO hay backfill
-- a propósito: TORNEO.Minimo_Jugadores_Para_Iniciar queda en NULL, que el
-- service lee como "usar Modalidad.Tamano_Equipo" — exactamente el
-- comportamiento anterior a esta migración. Una base que corre este script y
-- no configura nada se comporta igual que antes, así que no existe la clase
-- de riesgo "backfill omitido o a medias".
--
-- Re-ejecutable: ADD COLUMN IF NOT EXISTS, constraints guardadas con un
-- chequeo contra pg_constraint, trigger con DROP TRIGGER IF EXISTS previo
-- (test_scripts_sql.py corre cada script dos veces).
-- ============================================================

-- ------------------------------------------------------------
-- 1) TORNEO.Minimo_Jugadores_Para_Iniciar
--    Flag de reglamento por torneo, hermano de Permite_Walkover_Grupos.
--    NULL = exigir el equipo completo (Modalidad.Tamano_Equipo).
-- ------------------------------------------------------------
ALTER TABLE TORNEO
    ADD COLUMN IF NOT EXISTS Minimo_Jugadores_Para_Iniciar INT;

-- ------------------------------------------------------------
-- 2) CONVOCADO_A_PARTIDO: ETag de concurrencia + valor probatorio de las
--    llegadas tardías.
-- ------------------------------------------------------------
ALTER TABLE CONVOCADO_A_PARTIDO
    ADD COLUMN IF NOT EXISTS Fecha_Modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE CONVOCADO_A_PARTIDO
    ADD COLUMN IF NOT EXISTS Minuto_Ingreso INT;

ALTER TABLE CONVOCADO_A_PARTIDO
    ADD COLUMN IF NOT EXISTS Registrado_Por INT;

-- Las filas que ya existían nacen con Fecha_Modificacion NULL (el DEFAULT
-- solo aplica a inserciones nuevas). Se igualan a su Fecha_Registro para que
-- MAX(Fecha_Modificacion) sea un ETag válido desde el primer request, sin
-- tener que tratar NULL como caso especial en el service.
UPDATE CONVOCADO_A_PARTIDO
SET Fecha_Modificacion = COALESCE(Fecha_Registro, CURRENT_TIMESTAMP)
WHERE Fecha_Modificacion IS NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_torneo_minimo_iniciar') THEN
        ALTER TABLE TORNEO
            ADD CONSTRAINT chk_torneo_minimo_iniciar
            CHECK (Minimo_Jugadores_Para_Iniciar IS NULL OR Minimo_Jugadores_Para_Iniciar >= 1);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_convocado_registrado_por') THEN
        ALTER TABLE CONVOCADO_A_PARTIDO
            ADD CONSTRAINT fk_convocado_registrado_por
            FOREIGN KEY (Registrado_Por) REFERENCES USUARIOS(ID);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_convocado_minuto_ingreso') THEN
        ALTER TABLE CONVOCADO_A_PARTIDO
            ADD CONSTRAINT chk_convocado_minuto_ingreso
            CHECK (Minuto_Ingreso IS NULL OR Minuto_Ingreso >= 0);
    END IF;
END $$;

-- ------------------------------------------------------------
-- 3) Trigger de Fecha_Modificacion. DROP previo en vez de un guard contra
--    pg_trigger: CREATE TRIGGER no acepta IF NOT EXISTS en las versiones de
--    Postgres que soporta el proyecto, y el DROP IF EXISTS es idempotente.
-- ------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_convocado_upd_fecha ON CONVOCADO_A_PARTIDO;
CREATE TRIGGER trg_convocado_upd_fecha
BEFORE UPDATE ON CONVOCADO_A_PARTIDO
FOR EACH ROW EXECUTE FUNCTION fn_actualizar_fecha_modificacion();
