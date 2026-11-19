-- 37 — TASK-023 (docs/audit/11_BACKLOG_IMPLEMENTACION.md, DB-08): índice
-- sobre PARTIDOS(Partido_Ida_ID). El listado de partidos pregunta, para
-- toda la página, qué partidos son la ida de otro.
--
-- Re-ejecutable. Aplicar con:
--   psql -h 127.0.0.1 -U postgres -d torneos_mvp -1 -f database/37_migracion_indice_partido_ida.sql

CREATE INDEX IF NOT EXISTS idx_partidos_ida ON PARTIDOS(Partido_Ida_ID);
