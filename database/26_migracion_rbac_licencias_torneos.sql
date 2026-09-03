-- ============================================================
-- 26_migracion_rbac_licencias_torneos.sql
-- RBAC — Asignación de Torneos (N:M) + Sistema de Licenciamiento
-- (docs/plans/rbac-licencias-torneos-plan.md), para una base YA
-- provisionada (torneos_mvp). La secuencia 01-06 ya quedó actualizada al
-- estado final — mismo criterio que 07/08/09/12/13/14/18/19/20/21/22/23/24/25.
--
-- Puramente ADITIVA: columna nueva con DEFAULT TRUE (nadie pierde acceso
-- el día del deploy), tabla nueva sin FK entrante desde tablas existentes,
-- y un tercer valor agregado a un CHECK ya existente (mismo patrón que
-- 22_migracion_rate_limiting_login.sql con chk_accesos_motivo). No hay
-- backfill ni decisión humana pendiente.
--
-- Re-ejecutable: todo va con IF NOT EXISTS / guardas sobre pg_constraint.
-- ============================================================

-- ------------------------------------------------------------
-- USUARIOS: columna de licencia (D1/D2a — rbac-licencias-torneos-plan.md §3.1)
-- ------------------------------------------------------------
ALTER TABLE USUARIOS
    ADD COLUMN IF NOT EXISTS Licencia_Activa BOOLEAN NOT NULL DEFAULT TRUE;

-- ------------------------------------------------------------
-- ASIGNACION_TORNEO_ADMIN: N:M Usuario (TorneoAdmin) <-> Torneo (§3.2)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ASIGNACION_TORNEO_ADMIN (
    ID SERIAL PRIMARY KEY,
    Usuario_ID INT NOT NULL,
    Torneo_ID INT NOT NULL,
    -- 'Activo'/'Inactivo': revocar acceso = flip de Estado, no DELETE.
    -- Mismo criterio soft-delete que el resto del esquema.
    Estado VARCHAR(20) NOT NULL DEFAULT 'Activo',
    Fecha_Registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Fecha_Modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'unique_asignacion_usuario_torneo') THEN
        ALTER TABLE ASIGNACION_TORNEO_ADMIN
            ADD CONSTRAINT unique_asignacion_usuario_torneo UNIQUE (Usuario_ID, Torneo_ID);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_asignacion_usuario') THEN
        ALTER TABLE ASIGNACION_TORNEO_ADMIN
            ADD CONSTRAINT fk_asignacion_usuario FOREIGN KEY (Usuario_ID) REFERENCES USUARIOS(ID);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_asignacion_torneo') THEN
        ALTER TABLE ASIGNACION_TORNEO_ADMIN
            ADD CONSTRAINT fk_asignacion_torneo FOREIGN KEY (Torneo_ID) REFERENCES TORNEO(ID);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_asignacion_estado') THEN
        ALTER TABLE ASIGNACION_TORNEO_ADMIN
            ADD CONSTRAINT chk_asignacion_estado CHECK (Estado IN ('Activo', 'Inactivo'));
    END IF;
END $$;

-- Postgres no indexa FK automáticamente (mismo comentario que 03_indexes.sql).
-- El UNIQUE de arriba ya cubre (Usuario_ID, Torneo_ID) como índice btree;
-- idx_asignacion_usuario cubre además el lookup solo-por-Usuario_ID que usa
-- GET /usuarios/{id}/torneos y el chequeo de "¿tiene algún torneo asignado?".
CREATE INDEX IF NOT EXISTS idx_asignacion_usuario ON ASIGNACION_TORNEO_ADMIN(Usuario_ID);
CREATE INDEX IF NOT EXISTS idx_asignacion_torneo ON ASIGNACION_TORNEO_ADMIN(Torneo_ID);

-- ------------------------------------------------------------
-- Trigger: Usuario_ID de una asignación debe ser Rol='TorneoAdmin'.
-- Espejo del patrón de fn_validar_torneo_modalidad (06_triggers.sql):
-- red de seguridad para un INSERT crudo, el mensaje legible para el admin
-- ya lo da AsignacionTorneoAdminService antes de llegar acá.
--
-- Esto valida en el momento de INSERT/UPDATE de la fila de asignación
-- únicamente — NO revalida si el USUARIO cambia de rol después (ver el
-- comentario en rbac-licencias-torneos-plan.md §3.2, hallazgo #3 de la
-- voz externa): ese caso lo cubre UsuarioService.update() en Python,
-- desactivando las filas Activo del usuario cuando su Rol deja de ser
-- 'TorneoAdmin' — no un segundo trigger cruzando en la dirección opuesta.
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_validar_asignacion_torneo_admin_rol()
RETURNS TRIGGER AS $$
DECLARE
    v_rol VARCHAR(20);
BEGIN
    SELECT Rol INTO v_rol FROM USUARIOS WHERE ID = NEW.Usuario_ID;
    IF v_rol IS NULL THEN
        RAISE EXCEPTION 'El usuario indicado no existe.';
    END IF;
    IF v_rol <> 'TorneoAdmin' THEN
        RAISE EXCEPTION 'Solo se puede asignar torneos a cuentas con rol TorneoAdmin (esta cuenta es %).', v_rol;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_asignacion_validar_rol ON ASIGNACION_TORNEO_ADMIN;
CREATE TRIGGER trg_asignacion_validar_rol
BEFORE INSERT OR UPDATE OF Usuario_ID ON ASIGNACION_TORNEO_ADMIN
FOR EACH ROW EXECUTE FUNCTION fn_validar_asignacion_torneo_admin_rol();

-- ------------------------------------------------------------
-- ACCESOS: chk_accesos_motivo admite un cuarto valor ('licencia_revocada')
-- además de 'credenciales'/'inactivo'/'bloqueado' — mismo patrón que
-- 22_migracion_rate_limiting_login.sql agregó 'bloqueado'. Sin esto,
-- UsuarioService.login() no podría registrar el rechazo por licencia
-- revocada en la bitácora de accesos (rbac-licencias-torneos-plan.md §4.2).
-- ------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_accesos_motivo') THEN
        ALTER TABLE ACCESOS DROP CONSTRAINT chk_accesos_motivo;
    END IF;
    ALTER TABLE ACCESOS
        ADD CONSTRAINT chk_accesos_motivo CHECK (
            (Exitoso = TRUE AND Motivo IS NULL)
         OR (Exitoso = FALSE AND Motivo IN ('credenciales', 'inactivo', 'bloqueado', 'licencia_revocada'))
        );
END $$;

-- ------------------------------------------------------------
-- Verificación
-- ------------------------------------------------------------
DO $$
DECLARE
    v_faltan TEXT := '';
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE lower(table_name) = 'usuarios' AND lower(column_name) = 'licencia_activa'
    ) THEN
        v_faltan := v_faltan || ' USUARIOS.Licencia_Activa';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE lower(table_name) = 'asignacion_torneo_admin') THEN
        v_faltan := v_faltan || ' tabla ASIGNACION_TORNEO_ADMIN';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'unique_asignacion_usuario_torneo') THEN
        v_faltan := v_faltan || ' unique_asignacion_usuario_torneo';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_asignacion_validar_rol') THEN
        v_faltan := v_faltan || ' trg_asignacion_validar_rol';
    END IF;
    IF v_faltan <> '' THEN
        RAISE EXCEPTION 'Migracion incompleta: faltan:%', v_faltan;
    END IF;

    RAISE NOTICE 'RBAC licencias+asignacion listo: USUARIOS.Licencia_Activa y ASIGNACION_TORNEO_ADMIN creadas. Kill switch en get_current_user/login; scoping por torneo en require_torneo_access (torneos.py).';
END $$;
