-- ============================================================
-- 15_migracion_popularidad_disciplinas.sql
-- Agrega DISCIPLINA.Orden_Popularidad para una base YA provisionada
-- (torneos_mvp) — motor-formatos-plantillas-navegacion-plan.md,
-- requerimiento #3 ("barra tipo SofaScore ordenada por popularidad, no
-- alfabético"). La secuencia 01-06 ya quedó actualizada al estado final
-- — mismo criterio que 07/08/09/12/13/14.
--
-- Puramente ADITIVA: agrega una columna nullable a una tabla existente y
-- la puebla con el ranking recomendado (Fase 2 del plan). No toca ninguna
-- otra tabla ni fila fuera de DISCIPLINA. Si algo sale mal, alcanza con
-- `ALTER TABLE DISCIPLINA DROP COLUMN Orden_Popularidad`.
--
-- Re-ejecutable: ADD COLUMN con guarda sobre information_schema, y el
-- UPDATE del ranking es idempotente (mismos valores cada corrida).
-- ============================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE lower(table_name) = 'disciplina' AND lower(column_name) = 'orden_popularidad'
    ) THEN
        ALTER TABLE DISCIPLINA ADD COLUMN Orden_Popularidad INT;
    END IF;
END $$;

-- Ranking recomendado (Fase 2 — Design Review). Match por Nombre porque el
-- ID varía según el orden en que 11_catalogo_disciplinas.sql insertó cada
-- fila; una disciplina que no está en esta lista queda en NULL (ordena al
-- final, NULLS LAST) — el admin puede reordenar después con un UPDATE
-- directo, no bloquea nada de este plan.
UPDATE DISCIPLINA SET Orden_Popularidad = v.orden
FROM (VALUES
    ('Fútbol', 1), ('Baloncesto', 2), ('Tenis', 3), ('Voleibol', 4),
    ('Ping Pong', 5), ('Boxeo', 6), ('Natación', 7), ('Atletismo', 8),
    ('MMA', 9), ('Ajedrez', 10), ('Bádminton', 11), ('Judo', 12),
    ('Ciclismo', 13), ('Rugby', 14), ('League of Legends', 15),
    ('Valorant', 16), ('CS:GO', 17), ('FIFA / EA FC', 18),
    ('Rocket League', 19), ('Taekwondo', 20), ('Karate', 21),
    ('Gimnasia', 22), ('Hándbol', 23), ('CrossFit', 24),
    ('Squash / Racquetball', 25), ('Fútbol Americano / Flag Football', 26),
    ('Pickleball', 27), ('Frontón / Pelota Vasca', 28)
) AS v(nombre, orden)
WHERE DISCIPLINA.Nombre = v.nombre;

-- ------------------------------------------------------------
-- Verificación
-- ------------------------------------------------------------
DO $$
DECLARE
    v_sin_orden INT;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE lower(table_name) = 'disciplina' AND lower(column_name) = 'orden_popularidad'
    ) THEN
        RAISE EXCEPTION 'Migracion incompleta: DISCIPLINA.Orden_Popularidad no existe.';
    END IF;

    SELECT COUNT(*) INTO v_sin_orden FROM DISCIPLINA WHERE Orden_Popularidad IS NULL;
    RAISE NOTICE 'Orden_Popularidad listo. % disciplina(s) sin ranking asignado (quedan al final, NULLS LAST).', v_sin_orden;
END $$;
