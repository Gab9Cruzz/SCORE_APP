-- 42 — TASK-031 (docs/audit/11_BACKLOG_IMPLEMENTACION.md, ARQ-01/DB-10/OPS-10):
-- tabla SCHEMA_MIGRATIONS, el registro de qué migraciones tiene aplicadas
-- cada base. En una base existente: correr
--   python -m scripts.migrar --marcar-hasta 41
-- (marca las anteriores sin ejecutarlas) y después
--   python -m scripts.migrar --aplicar
-- (aplica esta y lo que falte). Re-ejecutable.

CREATE TABLE IF NOT EXISTS SCHEMA_MIGRATIONS (
    Nombre VARCHAR(200) PRIMARY KEY,
    Aplicada_En TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Checksum VARCHAR(64)
);
