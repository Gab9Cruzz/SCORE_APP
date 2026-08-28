-- ============================================================
-- 14_migracion_auditoria_accesos.sql
-- Agrega ACCESOS: bitácora de intentos de inicio de sesión (exitosos y
-- fallidos) para una base YA provisionada (torneos_mvp). La secuencia
-- 01-06 ya quedó actualizada al estado final — mismo criterio que
-- 07/08/09/12/13.
--
-- A diferencia de 13, esta migración es puramente ADITIVA: crea una tabla
-- nueva y no toca ninguna fila existente. No puede frenar a mitad, no
-- necesita backfill y no hay decisión humana pendiente. El backup previo
-- sigue siendo buena idea por costumbre, pero acá no hay nada que
-- deshacer si algo sale mal: alcanza con `DROP TABLE ACCESOS`.
--
-- Re-ejecutable: todo va con IF NOT EXISTS / guardas sobre pg_constraint.
-- ============================================================

CREATE TABLE IF NOT EXISTS ACCESOS (
    ID SERIAL PRIMARY KEY,
    Usuario_ID INT,
    Username VARCHAR(50) NOT NULL,
    Exitoso BOOLEAN NOT NULL,
    Motivo VARCHAR(30),
    IP VARCHAR(45),
    User_Agent VARCHAR(255),
    Fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_accesos_usuario') THEN
        ALTER TABLE ACCESOS
            ADD CONSTRAINT fk_accesos_usuario FOREIGN KEY (Usuario_ID) REFERENCES USUARIOS(ID);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_accesos_motivo') THEN
        ALTER TABLE ACCESOS
            ADD CONSTRAINT chk_accesos_motivo CHECK (
                (Exitoso = TRUE AND Motivo IS NULL)
             OR (Exitoso = FALSE AND Motivo IN ('credenciales', 'inactivo'))
            );
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_accesos_fecha ON ACCESOS(Fecha DESC);
CREATE INDEX IF NOT EXISTS idx_accesos_usuario ON ACCESOS(Usuario_ID);
CREATE INDEX IF NOT EXISTS idx_accesos_username ON ACCESOS(Username);

-- ------------------------------------------------------------
-- Verificación
-- ------------------------------------------------------------
DO $$
DECLARE
    v_faltan TEXT := '';
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE lower(table_name) = 'accesos') THEN
        RAISE EXCEPTION 'Migracion incompleta: la tabla ACCESOS no existe.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_accesos_motivo') THEN
        v_faltan := v_faltan || ' chk_accesos_motivo';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_accesos_usuario') THEN
        v_faltan := v_faltan || ' fk_accesos_usuario';
    END IF;
    IF v_faltan <> '' THEN
        RAISE EXCEPTION 'Migracion incompleta: faltan constraints:%', v_faltan;
    END IF;

    RAISE NOTICE 'Auditoria de accesos lista: tabla ACCESOS creada. Se llena sola desde POST /auth/login (exitos y fallos); se consulta en GET /accesos como AdminGeneral.';
END $$;
