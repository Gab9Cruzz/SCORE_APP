-- 38 — TASK-024 (docs/audit/11_BACKLOG_IMPLEMENTACION.md, BE-03): un solo
-- Inicio_Partido por partido, como ya pasaba con Fin_Partido
-- (uq_hitos_partido_fin_unico). fn_validar_hito_partido lo detectaba con un
-- SELECT previo, que bajo dos transacciones simultáneas no alcanza.
--
-- Se detiene si ya hay partidos con dos Inicio_Partido: hay que decidir a
-- mano cuál queda. Re-ejecutable. Aplicar con:
--   psql -h 127.0.0.1 -U postgres -d torneos_mvp -1 -f database/38_migracion_inicio_partido_unico.sql

DO $$
DECLARE
    v_repetidos TEXT;
BEGIN
    SELECT string_agg(Partido_ID::TEXT, ', ') INTO v_repetidos
      FROM (SELECT Partido_ID FROM HITOS_PARTIDO WHERE Tipo_Hito = 'Inicio_Partido'
             GROUP BY Partido_ID HAVING COUNT(*) > 1) r;
    IF v_repetidos IS NOT NULL THEN
        RAISE EXCEPTION 'Partidos con más de un Inicio_Partido (%): dejá uno solo antes de migrar.', v_repetidos;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_hitos_partido_inicio_unico
    ON HITOS_PARTIDO (Partido_ID)
    WHERE Tipo_Hito = 'Inicio_Partido';
