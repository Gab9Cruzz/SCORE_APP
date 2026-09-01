-- ============================================================
-- 22_migracion_rate_limiting_login.sql
-- Rate limiting de login (3B-14, docs/plans/cierre-backlog-todos-plan.md),
-- para una base YA provisionada (torneos_mvp). La secuencia 01-06 ya
-- quedó actualizada al estado final — mismo criterio que
-- 07/08/09/12/13/14/18/19/20/21.
--
-- Numerada 22 (sigue a 21_migracion_desempate_manual.sql).
--
-- Único cambio de esquema: chk_accesos_motivo admite un tercer valor
-- ('bloqueado') además de 'credenciales'/'inactivo' — ver el comentario
-- de la columna en 02_constraints.sql para por qué es un motivo aparte y
-- no se cuenta contra el umbral de fallos. El resto de la funcionalidad
-- (contar fallos recientes, decidir el bloqueo) vive en Python
-- (AccesoRepository/UsuarioService), no en la base — no hay tabla ni
-- columna nueva.
--
-- Re-ejecutable: DROP + ADD del CHECK sobre un chequeo previo, no hay
-- forma de "agregar un valor" a un CHECK existente sin recrearlo.
-- ============================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_accesos_motivo') THEN
        ALTER TABLE ACCESOS DROP CONSTRAINT chk_accesos_motivo;
    END IF;
    ALTER TABLE ACCESOS
        ADD CONSTRAINT chk_accesos_motivo CHECK (
            (Exitoso = TRUE AND Motivo IS NULL)
         OR (Exitoso = FALSE AND Motivo IN ('credenciales', 'inactivo', 'bloqueado'))
        );
END $$;
