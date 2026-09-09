-- ============================================================
-- 30_migracion_fin_forzado.sql
-- "Modo en Vivo": cierre forzado de partido (docs/plans/modo-vivo-
-- sustituciones-cierre-plan.md, Área 4, T6/T15/T17) — para una base YA
-- provisionada (torneos_mvp). La secuencia 01-06 ya quedó actualizada al
-- estado final.
--
-- Numerada 30 (sigue a 29_migracion_maximo_titulares.sql).
--
-- Aditiva pura: 3 columnas nuevas en HITOS_PARTIDO (todas con default
-- seguro/nullable, sin backfill: todo Hito ya existente es Forzado=FALSE,
-- que es lo que en efecto fue), 5 constraints, 1 índice único parcial que
-- cierra la carrera de doble Fin_Partido (T15) — este último aplica
-- igual a los Hitos ya existentes: si alguna base tuviera dos
-- Fin_Partido para el mismo partido (no debería, el trigger de secuencia
-- ya lo impedía en el caso no-concurrente), el CREATE INDEX fallaría y
-- habría que limpiar ese dato antes de reintentar — señal correcta, no un
-- bug de esta migración.
--
-- Re-ejecutable: ADD COLUMN IF NOT EXISTS, constraints/índice guardados
-- con un chequeo previo (test_scripts_sql.py corre cada script dos veces).
-- ============================================================

ALTER TABLE HITOS_PARTIDO
    ADD COLUMN IF NOT EXISTS Forzado BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE HITOS_PARTIDO
    ADD COLUMN IF NOT EXISTS Motivo_Cierre VARCHAR(30);

ALTER TABLE HITOS_PARTIDO
    ADD COLUMN IF NOT EXISTS Motivo_Cierre_Detalle VARCHAR(200);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_hitos_partido_forzado_solo_fin') THEN
        ALTER TABLE HITOS_PARTIDO
            ADD CONSTRAINT chk_hitos_partido_forzado_solo_fin
            CHECK (NOT Forzado OR Tipo_Hito = 'Fin_Partido');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_hitos_partido_motivo_solo_forzado') THEN
        ALTER TABLE HITOS_PARTIDO
            ADD CONSTRAINT chk_hitos_partido_motivo_solo_forzado
            CHECK (Motivo_Cierre IS NULL OR Forzado);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_hitos_partido_forzado_requiere_motivo') THEN
        ALTER TABLE HITOS_PARTIDO
            ADD CONSTRAINT chk_hitos_partido_forzado_requiere_motivo
            CHECK (NOT Forzado OR Motivo_Cierre IS NOT NULL);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_hitos_partido_motivo_cierre') THEN
        ALTER TABLE HITOS_PARTIDO
            ADD CONSTRAINT chk_hitos_partido_motivo_cierre
            CHECK (Motivo_Cierre IS NULL OR Motivo_Cierre IN ('Clima', 'Incidente', 'Lesion_Grave', 'Orden_Seguridad', 'Otro'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_hitos_partido_detalle_solo_otro') THEN
        ALTER TABLE HITOS_PARTIDO
            ADD CONSTRAINT chk_hitos_partido_detalle_solo_otro
            CHECK (Motivo_Cierre_Detalle IS NULL OR Motivo_Cierre = 'Otro');
    END IF;
END $$;

-- T15: índice único parcial — ver el comentario largo en 03_indexes.sql.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = 'uq_hitos_partido_fin_unico') THEN
        CREATE UNIQUE INDEX uq_hitos_partido_fin_unico
            ON HITOS_PARTIDO (Partido_ID)
            WHERE Tipo_Hito = 'Fin_Partido';
    END IF;
END $$;
