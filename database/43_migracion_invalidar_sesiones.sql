-- 43 — TASK-033 (docs/audit/11_BACKLOG_IMPLEMENTACION.md, SEC-03/SEC-14):
-- cambio de contraseña propio e invalidación de sesiones.
--
-- * USUARIOS.Tokens_Validos_Desde: un token emitido ANTES de esta marca
--   (claim `iat`) se rechaza. Se actualiza al cambiar la contraseña (propia
--   o por un AdminGeneral) y al desactivar la cuenta. NULL = nunca se
--   invalidó nada, todo token vigente sirve.
-- * chk_accesos_motivo admite 'cambio_password': un intento de cambio con la
--   contraseña actual incorrecta queda en la bitácora de accesos.
--
-- Re-ejecutable. Aplicar con:
--   psql -h 127.0.0.1 -U postgres -d torneos_mvp -1 -f database/43_migracion_invalidar_sesiones.sql

ALTER TABLE USUARIOS ADD COLUMN IF NOT EXISTS Tokens_Validos_Desde TIMESTAMP;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_accesos_motivo') THEN
        ALTER TABLE ACCESOS DROP CONSTRAINT chk_accesos_motivo;
    END IF;
    ALTER TABLE ACCESOS
        ADD CONSTRAINT chk_accesos_motivo CHECK (
            (Exitoso = TRUE AND Motivo IS NULL)
         OR (Exitoso = FALSE AND Motivo IN ('credenciales', 'inactivo', 'bloqueado', 'licencia_revocada', 'cambio_password'))
        );
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'usuarios' AND column_name = 'tokens_validos_desde'
    ) THEN
        RAISE EXCEPTION 'Falta USUARIOS.Tokens_Validos_Desde';
    END IF;
    RAISE NOTICE 'TASK-033 listo: USUARIOS.Tokens_Validos_Desde y motivo cambio_password.';
END $$;
