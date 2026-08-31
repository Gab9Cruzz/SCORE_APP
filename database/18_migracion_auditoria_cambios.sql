-- ============================================================
-- 18_migracion_auditoria_cambios.sql
-- Agrega AUDITORIA: bitacora de alta/modificacion/baja de CUALQUIER
-- entidad del sistema, para una base YA provisionada (torneos_mvp). La
-- secuencia 01-06 ya quedo actualizada al estado final — mismo criterio
-- que 07/08/09/12/13/14.
--
-- Numerada 18 (no 15) porque 15/16/17 ya estaban tomados por otro plan en
-- curso (motor-formatos-plantillas-navegacion-plan.md) en el momento de
-- escribir esta migracion. No depende de esos tres: solo agrega una tabla
-- nueva, independiente de DISCIPLINA/JUGADORES/el motor de formatos.
--
-- Igual que 14 (ACCESOS), esta migracion es puramente ADITIVA: crea una
-- tabla nueva y no toca ninguna fila existente. No puede frenar a mitad,
-- no necesita backfill y no hay decision humana pendiente. El backup
-- previo sigue siendo buena idea por costumbre, pero aca no hay nada que
-- deshacer si algo sale mal: alcanza con `DROP TABLE AUDITORIA`.
--
-- Re-ejecutable: todo va con IF NOT EXISTS / guardas sobre pg_constraint.
-- ============================================================

CREATE TABLE IF NOT EXISTS AUDITORIA (
    ID SERIAL PRIMARY KEY,
    Usuario_ID INT,
    Tabla VARCHAR(50) NOT NULL,
    Registro_ID INT NOT NULL,
    Accion VARCHAR(20) NOT NULL,
    Datos_Anteriores JSONB,
    Datos_Nuevos JSONB,
    IP VARCHAR(45),
    User_Agent VARCHAR(255),
    Fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_auditoria_usuario') THEN
        ALTER TABLE AUDITORIA
            ADD CONSTRAINT fk_auditoria_usuario FOREIGN KEY (Usuario_ID) REFERENCES USUARIOS(ID);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_auditoria_accion') THEN
        ALTER TABLE AUDITORIA
            ADD CONSTRAINT chk_auditoria_accion CHECK (Accion IN ('crear', 'modificar', 'eliminar'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_auditoria_fecha ON AUDITORIA(Fecha DESC);
CREATE INDEX IF NOT EXISTS idx_auditoria_tabla_registro ON AUDITORIA(Tabla, Registro_ID);
CREATE INDEX IF NOT EXISTS idx_auditoria_usuario ON AUDITORIA(Usuario_ID);

-- ------------------------------------------------------------
-- Verificacion
-- ------------------------------------------------------------
DO $$
DECLARE
    v_faltan TEXT := '';
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE lower(table_name) = 'auditoria') THEN
        RAISE EXCEPTION 'Migracion incompleta: la tabla AUDITORIA no existe.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_auditoria_accion') THEN
        v_faltan := v_faltan || ' chk_auditoria_accion';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_auditoria_usuario') THEN
        v_faltan := v_faltan || ' fk_auditoria_usuario';
    END IF;
    IF v_faltan <> '' THEN
        RAISE EXCEPTION 'Migracion incompleta: faltan constraints:%', v_faltan;
    END IF;

    RAISE NOTICE 'Auditoria de cambios lista: tabla AUDITORIA creada. La llena sola un event listener de SQLAlchemy (backend/app/core/auditoria.py) en cada alta/modificacion/baja de cualquier entidad; se consulta en GET /auditoria como AdminGeneral.';
END $$;
