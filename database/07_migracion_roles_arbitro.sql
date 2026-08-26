-- ============================================================
-- 07_migracion_roles_arbitro.sql
-- Migración puntual para una base YA provisionada (torneos_mvp): pasa de
-- los 3 roles planos a los 4 roles reales, y agrega la asignación
-- árbitro↔partido. No es parte de la secuencia 01-06 (esa sigue siendo la
-- definición "desde cero" — ver 01_schema.sql y 02_constraints.sql, ya
-- actualizados con el estado final).
--
-- No hay Alembic en este proyecto (son archivos SQL numerados corridos a
-- mano). Este script SÍ se puede correr más de una vez sin romper nada:
-- cada paso chequea si ya se aplicó antes de tocar el esquema.
--
-- Uso: correr una sola vez contra torneos_mvp (o cualquier base que ya
-- tenga datos con el esquema viejo). Un entorno nuevo NO necesita esto —
-- nace correcto directamente desde 01-02.
-- ============================================================

-- ------------------------------------------------------------
-- USUARIOS: 3 roles -> 4 roles
--
-- Orden importa: se saca el CHECK viejo, se migran los datos, y recién
-- ahí entra el CHECK nuevo — así ninguna fila existente viola una
-- restricción a mitad de camino.
-- ------------------------------------------------------------
ALTER TABLE USUARIOS DROP CONSTRAINT IF EXISTS chk_usuarios_rol;

-- Dato verificado en esta base (2026-08-26): un solo usuario con Rol='Admin'
-- (el bootstrap del sistema) — sin ambigüedad, migra a AdminGeneral. Si esta
-- base tiene más de una fila 'Admin' al correr esto, revisar caso por caso
-- antes de asumir que todas migran igual (ver plan, sección "NOT in scope").
UPDATE USUARIOS SET Rol = 'AdminGeneral' WHERE Rol = 'Admin';

ALTER TABLE USUARIOS
    ADD CONSTRAINT chk_usuarios_rol
    CHECK (Rol IN ('AdminGeneral', 'TorneoAdmin', 'Arbitro', 'Publico'));

-- ------------------------------------------------------------
-- PARTIDOS: columna de asignación árbitro↔partido
--
-- Mismo patrón que EQUIPOS_ID_LOCAL/EQUIPOS_ID_VISITANTE en la misma
-- tabla: FK directa, nullable (un partido puede no tener árbitro asignado
-- todavía). ON DELETE SET NULL en vez de CASCADE/RESTRICT: los usuarios
-- se dan de baja lógica (Estado='Inactivo'), nunca se borran físicamente
-- en operación normal, pero si alguna vez se purga una fila no tiene
-- sentido que eso arrastre o bloquee el partido.
-- ------------------------------------------------------------
ALTER TABLE PARTIDOS ADD COLUMN IF NOT EXISTS ARBITRO_ID INT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_partidos_arbitro'
    ) THEN
        ALTER TABLE PARTIDOS
            ADD CONSTRAINT fk_partidos_arbitro
            FOREIGN KEY (ARBITRO_ID) REFERENCES USUARIOS(ID) ON DELETE SET NULL;
    END IF;
END $$;

-- Postgres no indexa automáticamente las FK (mismo comentario que
-- 03_indexes.sql) — sin esto, tanto el ownership-check (Fase 1) como
-- "Mis partidos" (Fase 3) hacen table scan en cada request.
CREATE INDEX IF NOT EXISTS idx_partidos_arbitro ON PARTIDOS(ARBITRO_ID);

-- ------------------------------------------------------------
-- Verificación manual post-migración (no falla el script, solo informa)
-- ------------------------------------------------------------
DO $$
DECLARE
    v_admin_restante INT;
BEGIN
    SELECT COUNT(*) INTO v_admin_restante FROM USUARIOS WHERE Rol = 'Admin';
    IF v_admin_restante > 0 THEN
        RAISE WARNING 'Quedan % fila(s) con Rol=''Admin'' sin migrar — no deberían existir tras este script.', v_admin_restante;
    END IF;
END $$;
