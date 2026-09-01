-- ============================================================
-- 23_migracion_archivar_torneo_grupo.sql
-- Archivar/eliminar TORNEO_GRUPO (3B-7, docs/plans/cierre-backlog-todos-plan.md),
-- para una base YA provisionada (torneos_mvp). La secuencia 01-06 ya
-- quedó actualizada al estado final — mismo criterio que
-- 07/08/09/12/13/14/18/19/20/21/22.
--
-- Numerada 23 (sigue a 22_migracion_rate_limiting_login.sql).
--
-- Aditiva pura: una columna nueva en TORNEO_GRUPO (Estado, default
-- 'Activo' = ningún grupo existente cambia de comportamiento). Sin
-- backfill: todo grupo pre-existente nace 'Activo' por el DEFAULT del
-- ADD COLUMN, no hay ambigüedad que resolver.
--
-- Re-ejecutable: ADD COLUMN / CREATE CONSTRAINT guardados con IF NOT
-- EXISTS o un chequeo contra pg_constraint.
-- ============================================================

ALTER TABLE TORNEO_GRUPO ADD COLUMN IF NOT EXISTS Estado VARCHAR(20) NOT NULL DEFAULT 'Activo';

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_torneo_grupo_estado') THEN
        ALTER TABLE TORNEO_GRUPO
            ADD CONSTRAINT chk_torneo_grupo_estado CHECK (Estado IN ('Activo', 'Archivado'));
    END IF;
END $$;
