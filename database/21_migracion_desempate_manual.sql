-- ============================================================
-- 21_migracion_desempate_manual.sql
-- Desempate manual en la tabla de posiciones de una Fase de Grupos
-- (3A-12, docs/plans/cierre-backlog-todos-plan.md — EC-51 de
-- motor-formatos-plantillas-navegacion-plan.md), para una base YA
-- provisionada (torneos_mvp). La secuencia 01-06 ya quedó actualizada al
-- estado final — mismo criterio que 07/08/09/12/13/14/18/19/20.
--
-- Numerada 21 (sigue a 20_migracion_control_mesa_tiempos.sql).
--
-- Aditiva pura: una columna nueva en GRUPO_EQUIPO (Orden_Manual, NULL por
-- default = sin cambios de comportamiento para ningún torneo existente) y
-- vw_tabla_posiciones reemplazada para exponerla y usarla como desempate
-- de ÚLTIMA instancia (después de PTS/DG/GF — nunca puede promover a un
-- equipo con menos puntos por encima de otro con más). Sin backfill: no
-- hay ningún valor "correcto" que inferir para una columna que hasta
-- ahora no existía, todo torneo con empates sigue mostrando el orden
-- automático hasta que un admin decida lo contrario.
--
-- Re-ejecutable: ADD COLUMN / CREATE CONSTRAINT guardados con IF NOT
-- EXISTS o un chequeo contra pg_constraint, CREATE OR REPLACE VIEW.
-- ============================================================

ALTER TABLE GRUPO_EQUIPO ADD COLUMN IF NOT EXISTS Orden_Manual INT;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_grupo_equipo_orden_manual') THEN
        ALTER TABLE GRUPO_EQUIPO
            ADD CONSTRAINT chk_grupo_equipo_orden_manual CHECK (Orden_Manual IS NULL OR Orden_Manual > 0);
    END IF;
END $$;

-- Mismo texto que la versión final en 04_views.sql — ver ese archivo para
-- el comentario completo de por qué Orden_Manual entra DESPUÉS de
-- PTS/DG/GF en el ORDER BY.
CREATE OR REPLACE VIEW vw_tabla_posiciones AS
WITH lados AS (
    SELECT Fase_ID, Grupo_ID, Torneo_ID, Equipo_Local_ID AS Equipo_ID,
           Goles_Local AS GF, Goles_Visitante AS GC
      FROM vw_resultados_partidos
     WHERE Estado = 'Finalizado'
    UNION ALL
    SELECT Fase_ID, Grupo_ID, Torneo_ID, Equipo_Visitante_ID,
           Goles_Visitante, Goles_Local
      FROM vw_resultados_partidos
     WHERE Estado = 'Finalizado'
)
SELECT
    l.Fase_ID,
    l.Grupo_ID,
    l.Torneo_ID,
    l.Equipo_ID,
    e.Nombre AS Equipo,
    COUNT(*)                                  AS PJ,
    COUNT(*) FILTER (WHERE l.GF >  l.GC)      AS PG,
    COUNT(*) FILTER (WHERE l.GF =  l.GC)      AS PE,
    COUNT(*) FILTER (WHERE l.GF <  l.GC)      AS PP,
    SUM(l.GF)::INT                            AS GF,
    SUM(l.GC)::INT                            AS GC,
    (SUM(l.GF) - SUM(l.GC))::INT              AS DG,
    (COUNT(*) FILTER (WHERE l.GF > l.GC) * 3
     + COUNT(*) FILTER (WHERE l.GF = l.GC))::INT AS PTS,
    ge.ID          AS Grupo_Equipo_ID,
    ge.Orden_Manual
FROM lados l
JOIN EQUIPOS e ON e.ID = l.Equipo_ID
LEFT JOIN INSCRIPCIONES_TORNEO it ON it.Torneo_ID = l.Torneo_ID AND it.Equipo_ID = l.Equipo_ID
LEFT JOIN GRUPO_EQUIPO ge ON ge.Grupo_ID = l.Grupo_ID AND ge.Inscripcion_Torneo_ID = it.ID
GROUP BY l.Fase_ID, l.Grupo_ID, l.Torneo_ID, l.Equipo_ID, e.Nombre, ge.ID, ge.Orden_Manual
ORDER BY l.Torneo_ID, l.Fase_ID, l.Grupo_ID NULLS FIRST, PTS DESC, DG DESC, GF DESC, ge.Orden_Manual NULLS LAST, Equipo;
