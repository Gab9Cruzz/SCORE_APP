-- 39 — TASK-025 (docs/audit/11_BACKLOG_IMPLEMENTACION.md, FUN-09): tabla de
-- posiciones completa.
--
-- vw_tabla_posiciones partía de los partidos finalizados: un equipo sin
-- partidos jugados no aparecía, y en cronómetro corrido (sin goles) todo
-- contaba como empate. Ahora parte de los participantes y usa el ganador
-- declarado (Ganador_Corrido_ID de PARTIDOS).
--
-- Re-ejecutable (CREATE OR REPLACE VIEW, mismas columnas). Aplicar con:
--   psql -h 127.0.0.1 -U postgres -d torneos_mvp -1 -f database/39_migracion_tabla_posiciones.sql

CREATE OR REPLACE VIEW vw_tabla_posiciones AS
-- TASK-025 (FUN-09): parte de los PARTICIPANTES, no de los partidos
-- jugados — un torneo recién generado muestra a todos con ceros. En una
-- Liga participan los inscriptos no cancelados; en una fase de Grupos, los
-- miembros de cada grupo; en cualquier otra fase (Eliminación), quien jugó.
-- El resultado de cada partido sale del ganador declarado en cronómetro
-- corrido (sin goles: 3 puntos al ganador, nunca empate) y de los goles en
-- el resto. Ganador_Corrido_ID se toma de PARTIDOS y no de
-- vw_resultados_partidos: agregarle una columna a esa vista rompería las
-- migraciones vigentes que la recrean (24, 33), porque Postgres no deja
-- quitar columnas de una vista.
WITH lados AS (
    SELECT r.Fase_ID, r.Grupo_ID, r.Torneo_ID, r.Equipo_Local_ID AS Equipo_ID,
           r.Goles_Local AS GF, r.Goles_Visitante AS GC,
           CASE WHEN pa.Ganador_Corrido_ID IS NOT NULL
                THEN CASE WHEN pa.Ganador_Corrido_ID = r.Equipo_Local_ID THEN 1 ELSE -1 END
                ELSE SIGN(r.Goles_Local - r.Goles_Visitante)
           END AS Resultado
      FROM vw_resultados_partidos r
      JOIN PARTIDOS pa ON pa.ID = r.Partido_ID
     WHERE r.Estado = 'Finalizado'
    UNION ALL
    SELECT r.Fase_ID, r.Grupo_ID, r.Torneo_ID, r.Equipo_Visitante_ID,
           r.Goles_Visitante, r.Goles_Local,
           CASE WHEN pa.Ganador_Corrido_ID IS NOT NULL
                THEN CASE WHEN pa.Ganador_Corrido_ID = r.Equipo_Visitante_ID THEN 1 ELSE -1 END
                ELSE SIGN(r.Goles_Visitante - r.Goles_Local)
           END
      FROM vw_resultados_partidos r
      JOIN PARTIDOS pa ON pa.ID = r.Partido_ID
     WHERE r.Estado = 'Finalizado'
),
participantes AS (
    SELECT f.ID AS Fase_ID, NULL::INT AS Grupo_ID, f.Torneo_ID, it.Equipo_ID
      FROM FASE f
      JOIN INSCRIPCIONES_TORNEO it ON it.Torneo_ID = f.Torneo_ID
     WHERE f.Tipo = 'Liga'
       AND it.Equipo_ID IS NOT NULL
       AND it.Estado IN ('Inscrito', 'Confirmado')
    UNION
    SELECT g.Fase_ID, g.ID, f.Torneo_ID, it.Equipo_ID
      FROM GRUPO g
      JOIN FASE f ON f.ID = g.Fase_ID
      JOIN GRUPO_EQUIPO ge ON ge.Grupo_ID = g.ID
      JOIN INSCRIPCIONES_TORNEO it ON it.ID = ge.Inscripcion_Torneo_ID
     WHERE it.Equipo_ID IS NOT NULL
    UNION
    SELECT Fase_ID, Grupo_ID, Torneo_ID, Equipo_ID FROM lados
)
SELECT
    p.Fase_ID,
    p.Grupo_ID,
    p.Torneo_ID,
    p.Equipo_ID,
    e.Nombre AS Equipo,
    COUNT(l.Equipo_ID)                                AS PJ,
    COUNT(*) FILTER (WHERE l.Resultado = 1)           AS PG,
    COUNT(*) FILTER (WHERE l.Resultado = 0)           AS PE,
    COUNT(*) FILTER (WHERE l.Resultado = -1)          AS PP,
    COALESCE(SUM(l.GF), 0)::INT                       AS GF,
    COALESCE(SUM(l.GC), 0)::INT                       AS GC,
    (COALESCE(SUM(l.GF), 0) - COALESCE(SUM(l.GC), 0))::INT AS DG,
    (COUNT(*) FILTER (WHERE l.Resultado = 1) * 3
     + COUNT(*) FILTER (WHERE l.Resultado = 0))::INT  AS PTS,
    -- 3A-12 (EC-51): desempate manual del admin, solo aplica a partidos
    -- de una Fase de Grupos (Grupo_ID no-NULL) — Liga no tiene
    -- GRUPO_EQUIPO, así que ge.* sale NULL ahí por construcción, no hace
    -- falta filtrar aparte. Grupo_Equipo_ID va expuesto para que el
    -- frontend pueda dirigir el PATCH sin resolverlo aparte.
    ge.ID          AS Grupo_Equipo_ID,
    ge.Orden_Manual
FROM participantes p
JOIN EQUIPOS e ON e.ID = p.Equipo_ID
LEFT JOIN lados l
       ON l.Torneo_ID = p.Torneo_ID
      AND l.Equipo_ID = p.Equipo_ID
      AND l.Fase_ID IS NOT DISTINCT FROM p.Fase_ID
      AND l.Grupo_ID IS NOT DISTINCT FROM p.Grupo_ID
LEFT JOIN INSCRIPCIONES_TORNEO it ON it.Torneo_ID = p.Torneo_ID AND it.Equipo_ID = p.Equipo_ID
LEFT JOIN GRUPO_EQUIPO ge ON ge.Grupo_ID = p.Grupo_ID AND ge.Inscripcion_Torneo_ID = it.ID
GROUP BY p.Fase_ID, p.Grupo_ID, p.Torneo_ID, p.Equipo_ID, e.Nombre, ge.ID, ge.Orden_Manual
-- Orden_Manual entra DESPUÉS de PTS/DG/GF a propósito (ver el comentario
-- de la columna en 01_schema.sql): es el desempate de última instancia,
-- nunca puede promover a un equipo con menos puntos por encima de otro
-- con más.
ORDER BY p.Torneo_ID, p.Fase_ID, p.Grupo_ID NULLS FIRST, PTS DESC, DG DESC, GF DESC, ge.Orden_Manual NULLS LAST, Equipo;
