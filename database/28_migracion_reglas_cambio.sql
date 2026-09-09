-- ============================================================
-- 28_migracion_reglas_cambio.sql
-- "Modo en Vivo": reglas de sustitución por torneo — tope de cambios y
-- no-retorno (docs/plans/modo-vivo-sustituciones-cierre-plan.md, Área 3,
-- T5), para una base YA provisionada (torneos_mvp). La secuencia 01-06 ya
-- quedó actualizada al estado final — mismo criterio que
-- 27_migracion_minimo_titulares.sql y las anteriores.
--
-- Numerada 28 (sigue a 27_migracion_minimo_titulares.sql).
--
-- Aditiva pura: 2 columnas nuevas + 2 constraints. Sin backfill: ambas
-- nacen en su default (Permite_Cambios_Ilimitados=FALSE,
-- Maximo_Cambios_Por_Equipo=NULL), que es el comportamiento anterior a
-- esta migración (sin tope numérico, con no-retorno exigido) — una base
-- que corre este script y no configura nada por torneo no cambia de
-- comportamiento.
--
-- Re-ejecutable: ADD COLUMN IF NOT EXISTS, constraints guardadas con un
-- chequeo contra pg_constraint (test_scripts_sql.py corre cada script dos
-- veces).
-- ============================================================

ALTER TABLE TORNEO
    ADD COLUMN IF NOT EXISTS Permite_Cambios_Ilimitados BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE TORNEO
    ADD COLUMN IF NOT EXISTS Maximo_Cambios_Por_Equipo INT;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_torneo_maximo_cambios') THEN
        ALTER TABLE TORNEO
            ADD CONSTRAINT chk_torneo_maximo_cambios
            CHECK (Maximo_Cambios_Por_Equipo IS NULL OR Maximo_Cambios_Por_Equipo >= 1);
    END IF;
END $$;
