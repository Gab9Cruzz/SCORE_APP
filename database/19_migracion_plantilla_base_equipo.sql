-- ============================================================
-- 19_migracion_plantilla_base_equipo.sql
-- Agrega EQUIPO_JUGADOR_BASE (Plantilla Base de equipo, D1-C de
-- gestion-avanzada-equipos-control-mesa-plan.md) para una base YA
-- provisionada (torneos_mvp). La secuencia 01-06 ya quedó actualizada al
-- estado final — mismo criterio que 07/08/09/12/13/14/18.
--
-- Puramente ADITIVA: crea una tabla nueva y no toca ninguna fila
-- existente. No puede frenar a mitad, no necesita backfill (no hay
-- "plantilla base" que reconstruir retroactivamente desde JUGADOR_EQUIPO
-- — D1 es explícito en que son fuentes independientes) y no hay decisión
-- humana pendiente. Si algo sale mal, alcanza con `DROP TABLE EQUIPO_JUGADOR_BASE`.
--
-- Re-ejecutable: todo va con IF NOT EXISTS / guardas sobre pg_constraint.
-- ============================================================

CREATE TABLE IF NOT EXISTS EQUIPO_JUGADOR_BASE (
    ID SERIAL PRIMARY KEY,
    Equipo_ID INT NOT NULL,
    Jugador_Perfil_ID INT NOT NULL,
    Dorsal_Sugerido INT,
    Fecha_Registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Fecha_Modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Estado VARCHAR(20) DEFAULT 'Activo'
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_equipo_jugador_base_equipo') THEN
        ALTER TABLE EQUIPO_JUGADOR_BASE
            ADD CONSTRAINT fk_equipo_jugador_base_equipo FOREIGN KEY (Equipo_ID) REFERENCES EQUIPOS(ID) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_equipo_jugador_base_perfil') THEN
        ALTER TABLE EQUIPO_JUGADOR_BASE
            ADD CONSTRAINT fk_equipo_jugador_base_perfil FOREIGN KEY (Jugador_Perfil_ID) REFERENCES JUGADOR_PERFIL_DISCIPLINA(ID) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_equipo_jugador_base_estado') THEN
        ALTER TABLE EQUIPO_JUGADOR_BASE
            ADD CONSTRAINT chk_equipo_jugador_base_estado CHECK (Estado IN ('Activo', 'Inactivo'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'unique_equipo_jugador_base') THEN
        ALTER TABLE EQUIPO_JUGADOR_BASE
            ADD CONSTRAINT unique_equipo_jugador_base UNIQUE (Equipo_ID, Jugador_Perfil_ID);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_equipo_jugador_base_equipo ON EQUIPO_JUGADOR_BASE(Equipo_ID);
CREATE INDEX IF NOT EXISTS idx_equipo_jugador_base_perfil ON EQUIPO_JUGADOR_BASE(Jugador_Perfil_ID);

DROP TRIGGER IF EXISTS trg_equipo_jugador_base_upd_fecha ON EQUIPO_JUGADOR_BASE;
CREATE TRIGGER trg_equipo_jugador_base_upd_fecha
BEFORE UPDATE ON EQUIPO_JUGADOR_BASE
FOR EACH ROW EXECUTE FUNCTION fn_actualizar_fecha_modificacion();

-- ------------------------------------------------------------
-- Verificación
-- ------------------------------------------------------------
DO $$
DECLARE
    v_faltan TEXT := '';
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE lower(table_name) = 'equipo_jugador_base') THEN
        RAISE EXCEPTION 'Migracion incompleta: la tabla EQUIPO_JUGADOR_BASE no existe.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'unique_equipo_jugador_base') THEN
        v_faltan := v_faltan || ' unique_equipo_jugador_base';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_equipo_jugador_base_estado') THEN
        v_faltan := v_faltan || ' chk_equipo_jugador_base_estado';
    END IF;
    IF v_faltan <> '' THEN
        RAISE EXCEPTION 'Migracion incompleta: faltan constraints:%', v_faltan;
    END IF;

    RAISE NOTICE 'Plantilla Base lista: tabla EQUIPO_JUGADOR_BASE creada. NO participa de ninguna regla de elegibilidad (D1-C) — se copia a JUGADOR_EQUIPO al inscribir el equipo a un torneo (InscripcionTorneoService.copiar_plantilla_base).';
END $$;
