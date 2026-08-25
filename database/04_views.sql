-- ============================================================
-- 04_views.sql
-- Vistas de consulta para el sistema de torneos
--
-- Regla general: las vistas nunca deducen a qué equipo pertenece un
-- evento a partir de JUGADOR_EQUIPO. Usan EVENTOS_PARTIDO.EQUIPO_ID.
-- Deducirlo hacía que un jugador con historial en los dos equipos del
-- partido sumara su gol para ambos lados del marcador.
--
-- Orden de creación: vw_goles_acreditados primero, las demás dependen
-- de ella o de vw_resultados_partidos.
-- ============================================================

-- ------------------------------------------------------------
-- Base común: a qué equipo se le acredita cada gol.
-- Un 'Gol' suma al equipo del jugador. Un 'Autogol' suma al RIVAL.
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW vw_goles_acreditados AS
SELECT
    ep.ID              AS Evento_Partido_ID,
    ep.PARTIDOS_ID,
    p.TORNEO_ID,
    ep.JUGADOR_ID,
    ep.EQUIPO_ID       AS Equipo_Del_Jugador,
    ev.Nombre          AS Tipo_Gol,
    CASE
        WHEN ev.Nombre = 'Autogol' THEN
            CASE WHEN ep.EQUIPO_ID = p.EQUIPOS_ID_LOCAL
                 THEN p.EQUIPOS_ID_VISITANTE
                 ELSE p.EQUIPOS_ID_LOCAL
            END
        ELSE ep.EQUIPO_ID
    END                AS Equipo_Acreditado,
    ep.MINUTO
FROM EVENTOS_PARTIDO ep
JOIN EVENTOS ev  ON ev.ID = ep.EVENTOS_ID
JOIN PARTIDOS p  ON p.ID  = ep.PARTIDOS_ID
WHERE ep.Estado = 'Registrado'
  AND ev.Nombre IN ('Gol', 'Autogol');

-- ------------------------------------------------------------
-- Próximos partidos programados
-- Solo futuros y solo de torneos y equipos activos: un equipo dado de
-- baja no debe seguir apareciendo en el calendario.
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW vw_proximos_partidos AS
SELECT
    p.ID          AS Partido_ID,
    p.TORNEO_ID,
    t.Nombre      AS Torneo,
    el.ID         AS Equipo_Local_ID,
    el.Nombre     AS Equipo_Local,
    ev.ID         AS Equipo_Visitante_ID,
    ev.Nombre     AS Equipo_Visitante,
    p.Fecha_Partido,
    p.Jornada,
    p.Fase,
    p.Grupo,
    p.Estado
FROM PARTIDOS p
JOIN TORNEO  t  ON t.ID  = p.TORNEO_ID
JOIN EQUIPOS el ON el.ID = p.EQUIPOS_ID_LOCAL
JOIN EQUIPOS ev ON ev.ID = p.EQUIPOS_ID_VISITANTE
WHERE p.Estado = 'Programado'
  AND p.Fecha_Partido >= CURRENT_TIMESTAMP
  AND t.Estado  = 'Activo'
  AND el.Estado = 'Activo'
  AND ev.Estado = 'Activo'
ORDER BY p.Fecha_Partido;

-- ------------------------------------------------------------
-- Plantilla vigente por equipo, con dorsal
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW vw_jugadores_activos_por_equipo AS
SELECT
    e.ID      AS Equipo_ID,
    e.Nombre  AS Equipo,
    j.ID      AS Jugador_ID,
    j.Nombre  AS Jugador,
    je.Dorsal,
    je.Fecha_Inicio
FROM JUGADOR_EQUIPO je
JOIN JUGADORES j ON j.ID = je.JUGADOR_ID
JOIN EQUIPOS   e ON e.ID = je.EQUIPO_ID
WHERE je.Estado = 'Activo'
  AND je.Fecha_Fin IS NULL
  AND j.Estado = 'Activo'
  AND e.Estado = 'Activo';

-- ------------------------------------------------------------
-- Goleadores
-- Expone Torneo_ID para poder filtrar por torneo.
-- El autogol no premia a su autor: cuenta para el marcador (ver
-- vw_goles_acreditados) pero no como gol del jugador.
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW vw_goleadores AS
SELECT
    ga.TORNEO_ID,
    ga.JUGADOR_ID,
    j.Nombre  AS Jugador,
    ga.Equipo_Del_Jugador AS Equipo_ID,
    e.Nombre  AS Equipo,
    COUNT(*)  AS Goles
FROM vw_goles_acreditados ga
JOIN JUGADORES j ON j.ID = ga.JUGADOR_ID
JOIN EQUIPOS   e ON e.ID = ga.Equipo_Del_Jugador
WHERE ga.Tipo_Gol = 'Gol'
GROUP BY ga.TORNEO_ID, ga.JUGADOR_ID, j.Nombre, ga.Equipo_Del_Jugador, e.Nombre
ORDER BY ga.TORNEO_ID, Goles DESC, Jugador;

-- ------------------------------------------------------------
-- Marcador por partido
-- Los goles se cuentan por Equipo_Acreditado, así el autogol suma al
-- rival y un traspaso histórico no infla el resultado.
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW vw_resultados_partidos AS
SELECT
    p.ID       AS Partido_ID,
    p.TORNEO_ID,
    el.ID      AS Equipo_Local_ID,
    el.Nombre  AS Equipo_Local,
    ev_eq.ID   AS Equipo_Visitante_ID,
    ev_eq.Nombre AS Equipo_Visitante,
    COUNT(ga.Evento_Partido_ID)
        FILTER (WHERE ga.Equipo_Acreditado = p.EQUIPOS_ID_LOCAL)     AS Goles_Local,
    COUNT(ga.Evento_Partido_ID)
        FILTER (WHERE ga.Equipo_Acreditado = p.EQUIPOS_ID_VISITANTE) AS Goles_Visitante,
    p.Fecha_Partido,
    p.Jornada,
    p.Fase,
    p.Grupo,
    p.Estado
FROM PARTIDOS p
JOIN EQUIPOS el    ON el.ID    = p.EQUIPOS_ID_LOCAL
JOIN EQUIPOS ev_eq ON ev_eq.ID = p.EQUIPOS_ID_VISITANTE
LEFT JOIN vw_goles_acreditados ga ON ga.PARTIDOS_ID = p.ID
GROUP BY p.ID, p.TORNEO_ID, el.ID, el.Nombre, ev_eq.ID, ev_eq.Nombre,
         p.Fecha_Partido, p.Jornada, p.Fase, p.Grupo, p.Estado;

-- ------------------------------------------------------------
-- Tabla de posiciones
-- Solo cuenta partidos Finalizado. 3 puntos por victoria, 1 por empate.
-- Orden: puntos, diferencia de gol, goles a favor, nombre.
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW vw_tabla_posiciones AS
WITH lados AS (
    SELECT Torneo_ID, Equipo_Local_ID AS Equipo_ID,
           Goles_Local AS GF, Goles_Visitante AS GC
      FROM vw_resultados_partidos
     WHERE Estado = 'Finalizado'
    UNION ALL
    SELECT Torneo_ID, Equipo_Visitante_ID,
           Goles_Visitante, Goles_Local
      FROM vw_resultados_partidos
     WHERE Estado = 'Finalizado'
)
SELECT
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
     + COUNT(*) FILTER (WHERE l.GF = l.GC))::INT AS PTS
FROM lados l
JOIN EQUIPOS e ON e.ID = l.Equipo_ID
GROUP BY l.Torneo_ID, l.Equipo_ID, e.Nombre
ORDER BY l.Torneo_ID, PTS DESC, DG DESC, GF DESC, Equipo;
