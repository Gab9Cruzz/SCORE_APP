-- ============================================================
-- 16_migracion_foto_jugadores.sql
-- Agrega JUGADORES.Foto_URL para una base YA provisionada (torneos_mvp) —
-- motor-formatos-plantillas-navegacion-plan.md, requerimiento #3 (grid de
-- Plantillas: tarjetas por equipo, foto + dorsal). La secuencia 01-06 ya
-- quedó actualizada al estado final — mismo criterio que 07/08/09/12/13/
-- 14/15.
--
-- Puramente ADITIVA: agrega una columna nullable a una tabla existente.
-- Todo jugador existente queda sin foto (el frontend cae a iniciales) —
-- no hay backfill posible ni necesario. Si algo sale mal, alcanza con
-- `ALTER TABLE JUGADORES DROP COLUMN Foto_URL`.
--
-- Re-ejecutable: ADD COLUMN con guarda sobre information_schema.
-- ============================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE lower(table_name) = 'jugadores' AND lower(column_name) = 'foto_url'
    ) THEN
        ALTER TABLE JUGADORES ADD COLUMN Foto_URL VARCHAR(500);
    END IF;
END $$;

-- ------------------------------------------------------------
-- Verificación
-- ------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE lower(table_name) = 'jugadores' AND lower(column_name) = 'foto_url'
    ) THEN
        RAISE EXCEPTION 'Migracion incompleta: JUGADORES.Foto_URL no existe.';
    END IF;

    RAISE NOTICE 'Foto_URL lista en JUGADORES. Todo jugador existente queda sin foto (NULL) — el frontend cae a iniciales.';
END $$;
