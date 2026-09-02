-- ============================================================
-- 25_migracion_convocados.sql
-- Titular/suplente/convocados a un partido (3B-2,
-- docs/plans/cierre-backlog-todos-plan.md), para una base YA provisionada
-- (torneos_mvp). La secuencia 01-06 ya quedó actualizada al estado final
-- — mismo criterio que 07/08/09/12/13/14/18/19/20/21/22/23/24.
--
-- Numerada 25 (sigue a 24_migracion_limites_y_walkover.sql).
--
-- Aditiva pura: una tabla nueva (CONVOCADO_A_PARTIDO, mismo espíritu no-
-- autoritativo que EQUIPO_JUGADOR_BASE — ver el comentario completo en
-- 01_schema.sql) + una columna nueva en vw_jugadores_activos_por_equipo.
-- Sin fila en CONVOCADO_A_PARTIDO para un partido dado = comportamiento
-- de siempre (toda la plantilla vigente es candidata en Control de Mesa).
--
-- Re-ejecutable: CREATE TABLE IF NOT EXISTS, CREATE CONSTRAINT guardado
-- con un chequeo contra pg_constraint, CREATE OR REPLACE VIEW.
-- ============================================================

CREATE TABLE IF NOT EXISTS CONVOCADO_A_PARTIDO (
    ID SERIAL PRIMARY KEY,
    Partido_ID INT NOT NULL,
    Jugador_Perfil_ID INT NOT NULL,
    Titular BOOLEAN NOT NULL DEFAULT FALSE,
    Fecha_Registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_convocado_partido') THEN
        ALTER TABLE CONVOCADO_A_PARTIDO
            ADD CONSTRAINT fk_convocado_partido FOREIGN KEY (Partido_ID) REFERENCES PARTIDOS(ID) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_convocado_perfil') THEN
        ALTER TABLE CONVOCADO_A_PARTIDO
            ADD CONSTRAINT fk_convocado_perfil FOREIGN KEY (Jugador_Perfil_ID) REFERENCES JUGADOR_PERFIL_DISCIPLINA(ID) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'unique_convocado_partido') THEN
        ALTER TABLE CONVOCADO_A_PARTIDO
            ADD CONSTRAINT unique_convocado_partido UNIQUE (Partido_ID, Jugador_Perfil_ID);
    END IF;
END $$;

-- Mismo texto que la versión final en 04_views.sql.
CREATE OR REPLACE VIEW vw_jugadores_activos_por_equipo AS
SELECT
    e.ID       AS Equipo_ID,
    e.Nombre   AS Equipo,
    it.Torneo_ID,
    j.ID       AS Jugador_ID,
    j.Nombre   AS Jugador,
    jpd.ID     AS Jugador_Perfil_ID,
    je.Dorsal,
    je.Fecha_Inicio
FROM JUGADOR_EQUIPO je
JOIN JUGADOR_PERFIL_DISCIPLINA jpd ON jpd.ID = je.Jugador_Perfil_ID
JOIN JUGADORES j             ON j.ID  = jpd.Jugador_ID
JOIN INSCRIPCIONES_TORNEO it ON it.ID = je.Inscripcion_Torneo_ID
JOIN EQUIPOS   e             ON e.ID  = it.Equipo_ID
WHERE je.Estado = 'Activo'
  AND je.Fecha_Fin IS NULL
  AND j.Estado = 'Activo'
  AND e.Estado = 'Activo';
