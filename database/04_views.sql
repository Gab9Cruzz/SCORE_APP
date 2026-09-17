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
  -- Portal Público (portal-publico-feed-partidos-plan.md, C2/E-B3a): esta
  -- vista no tiene forma de saber quién pregunta (a diferencia de
  -- `GET /torneos/{id}`, que sí distingue anónimo de logueado vía
  -- `verificar_torneo_visible`), así que el filtro es incondicional — un
  -- torneo despublicado no aparece en "Próximos partidos" ni para un
  -- admin logueado. Decisión explícita (C18/E-B3a), no un descuido: el
  -- widget de Dashboard.tsx ya consume solo endpoints públicos.
  AND t.Publicado = TRUE
ORDER BY p.Fecha_Partido;

-- ------------------------------------------------------------
-- Plantilla vigente por equipo, con dorsal
--
-- JUGADOR_EQUIPO ya no referencia JUGADOR_ID/EQUIPO_ID directo: el roster
-- ahora es (Jugador_Perfil_ID, Inscripcion_Torneo_ID). Se llega a la
-- persona vía JUGADOR_PERFIL_DISCIPLINA y al equipo vía
-- INSCRIPCIONES_TORNEO — ver docs/plans/equipos-jugadores-plan.md.
-- Se agrega Torneo_ID: un equipo puede estar inscrito en varios torneos a
-- la vez (roster distinto en cada uno), así que Equipo_ID solo ya no
-- identifica una plantilla única.
-- ------------------------------------------------------------
-- Jugador_Perfil_ID (3B-2, docs/plans/cierre-backlog-todos-plan.md):
-- agregada para que el consumidor de esta vista (plantilla de un equipo)
-- pueda anclar CONVOCADO_A_PARTIDO sin una consulta aparte — aditiva,
-- ningún consumidor existente que lea columnas puntuales se entera.
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

-- ------------------------------------------------------------
-- Estado del perfil de jugador por disciplina: Suspendido / Activo /
-- Libre. Derivado, no almacenado (ver comentario en
-- JUGADOR_PERFIL_DISCIPLINA, 01_schema.sql, y EC-10/EC-11 del plan): así
-- "agencia libre" al finalizar un torneo no tiene una columna que
-- olvidar sincronizar, y un jugador con membresía activa en OTRO torneo
-- de la misma disciplina no queda libre por error.
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW vw_estado_perfil_disciplina AS
SELECT
    jpd.ID AS Jugador_Perfil_ID,
    jpd.Jugador_ID,
    jpd.Disciplina_ID,
    CASE
        WHEN jpd.Suspendido THEN 'Suspendido'
        WHEN EXISTS (
            SELECT 1 FROM JUGADOR_EQUIPO je
             WHERE je.Jugador_Perfil_ID = jpd.ID AND je.Estado = 'Activo'
        ) THEN 'Activo'
        ELSE 'Libre'
    END AS Estado
FROM JUGADOR_PERFIL_DISCIPLINA jpd;

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
-- Fase_ID/Grupo_ID (Motor de Formatos) se agregan además de Fase/Grupo
-- (texto): un partido creado por el motor nuevo llena las FK, uno creado
-- a mano por el alta manual existente sigue llenando el texto — conviven
-- sin pisarse (ver comentario grande en 01_schema.sql, CREATE TABLE
-- PARTIDOS). INNER JOIN contra EQUIPOS a propósito: un shell de bracket
-- sin equipos definidos todavía ("Ganador Partido N") no tiene resultado
-- que mostrar acá — GET /torneos/{id}/bracket consulta PARTIDOS directo
-- con LEFT JOIN para poder mostrar esas casillas vacías.
-- Walkover (3B-13, docs/plans/cierre-backlog-todos-plan.md): un partido
-- Es_Walkover no tiene EVENTOS_PARTIDO reales (nadie jugó), así que
-- Goles_Local/Visitante se fuerzan a 3-0 a favor del equipo presente en
-- vez de contar eventos — el CASE gana sobre el COUNT normal solo para
-- esas filas, cualquier otro partido sigue exactamente igual que antes.
CREATE OR REPLACE VIEW vw_resultados_partidos AS
SELECT
    p.ID       AS Partido_ID,
    p.TORNEO_ID,
    el.ID      AS Equipo_Local_ID,
    el.Nombre  AS Equipo_Local,
    ev_eq.ID   AS Equipo_Visitante_ID,
    ev_eq.Nombre AS Equipo_Visitante,
    CASE
        WHEN p.Es_Walkover THEN (CASE WHEN p.Walkover_Equipo_Ausente_ID = p.EQUIPOS_ID_LOCAL THEN 0 ELSE 3 END)
        ELSE COUNT(ga.Evento_Partido_ID) FILTER (WHERE ga.Equipo_Acreditado = p.EQUIPOS_ID_LOCAL)
    END AS Goles_Local,
    CASE
        WHEN p.Es_Walkover THEN (CASE WHEN p.Walkover_Equipo_Ausente_ID = p.EQUIPOS_ID_VISITANTE THEN 0 ELSE 3 END)
        ELSE COUNT(ga.Evento_Partido_ID) FILTER (WHERE ga.Equipo_Acreditado = p.EQUIPOS_ID_VISITANTE)
    END AS Goles_Visitante,
    p.Fecha_Partido,
    p.Jornada,
    p.Fase,
    p.Grupo,
    p.Fase_ID,
    p.Grupo_ID,
    p.Estado,
    p.Es_Walkover,
    p.Walkover_Equipo_Ausente_ID,
    -- Desempate de eliminatoria: tiempo extra y penales (docs/plans/
    -- desempate-tiempo-extra-penales-plan.md, D-D9) — el CÓMO al lado del
    -- QUIÉN, para que el portal público (DetalleTorneoPublico.tsx) y
    -- PartidoEnVivo.tsx puedan renderizar "2-2 a.e.t. (4-2 pen.)" sin una
    -- segunda consulta por partido.
    p.Metodo_Desempate,
    p.Hubo_Tiempo_Extra,
    p.Penales_Local,
    p.Penales_Visitante
FROM PARTIDOS p
JOIN EQUIPOS el    ON el.ID    = p.EQUIPOS_ID_LOCAL
JOIN EQUIPOS ev_eq ON ev_eq.ID = p.EQUIPOS_ID_VISITANTE
LEFT JOIN vw_goles_acreditados ga ON ga.PARTIDOS_ID = p.ID
GROUP BY p.ID, p.TORNEO_ID, el.ID, el.Nombre, ev_eq.ID, ev_eq.Nombre,
         p.Fecha_Partido, p.Jornada, p.Fase, p.Grupo, p.Fase_ID, p.Grupo_ID, p.Estado,
         p.Es_Walkover, p.Walkover_Equipo_Ausente_ID,
         p.Metodo_Desempate, p.Hubo_Tiempo_Extra, p.Penales_Local, p.Penales_Visitante;

-- ------------------------------------------------------------
-- Feed de Partidos del Día — Portal Público
-- (portal-publico-feed-partidos-plan.md, T3.2/C5/E-L1/E-L3)
--
-- Construida SOBRE vw_resultados_partidos (Decisión Eng #10, prohibido
-- reimplementar el conteo de goles — esa vista ya resuelve autogol vía
-- vw_goles_acreditados y walkover). Le suma 5 JOIN explícitos: TORNEO,
-- TORNEO_GRUPO, DISCIPLINA y EQUIPOS ×2 (vw_resultados_partidos no
-- expone Logo_URL/Estado de los equipos, solo ID/Nombre).
--
-- Sin filtro de fecha acá adentro (E-L2): el predicado de fecha tiene que
-- ser un rango semiabierto (Fecha_Partido >= :fecha AND < :fecha+1) para
-- poder usar idx_partidos_fecha — lo aplica el caller (FeedRepository)
-- sobre esta vista, no la vista misma.
--
-- Filtros de estado (E-L3): EQUIPOS.Estado, TORNEO.Estado y
-- DISCIPLINA.Estado son todos nullable a nivel de columna — se usa
-- `IS DISTINCT FROM 'Inactivo'` en vez de `= 'Activo'`, que descartaría
-- filas NULL en silencio. TORNEO.Estado admite 'Finalizado' además de
-- 'Activo' (E-L1): un torneo que el admin marca Finalizado el día de la
-- final no debe desaparecer del feed de ese mismo día.
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW vw_feed_partidos AS
SELECT
    r.Partido_ID,
    r.Torneo_ID,
    t.Nombre                                                          AS Torneo,
    tg.ID                                                             AS Torneo_Grupo_ID,
    tg.Nombre                                                         AS Torneo_Grupo,
    tg.Pais,
    CASE WHEN tg.Logo_URL LIKE 'https://%' THEN tg.Logo_URL END       AS Logo_Torneo,
    t.Disciplina_ID,
    d.Nombre                                                          AS Disciplina,
    r.Equipo_Local_ID,
    r.Equipo_Local,
    CASE WHEN el.Logo_URL LIKE 'https://%' THEN el.Logo_URL END       AS Logo_Local,
    r.Equipo_Visitante_ID,
    r.Equipo_Visitante,
    CASE WHEN ev.Logo_URL LIKE 'https://%' THEN ev.Logo_URL END       AS Logo_Visitante,
    r.Fecha_Partido,
    r.Estado,
    r.Goles_Local,
    r.Goles_Visitante
FROM vw_resultados_partidos r
JOIN TORNEO       t  ON t.ID  = r.Torneo_ID
JOIN TORNEO_GRUPO tg ON tg.ID = t.Torneo_Grupo_ID
JOIN DISCIPLINA   d  ON d.ID  = t.Disciplina_ID
JOIN EQUIPOS      el ON el.ID = r.Equipo_Local_ID
JOIN EQUIPOS      ev ON ev.ID = r.Equipo_Visitante_ID
WHERE t.Publicado = TRUE
  AND t.Estado IS DISTINCT FROM 'Inactivo'
  AND tg.Estado <> 'Archivado'
  AND r.Estado <> 'Cancelado'
  AND el.Estado IS DISTINCT FROM 'Inactivo'
  AND ev.Estado IS DISTINCT FROM 'Inactivo';

-- ------------------------------------------------------------
-- Tabla de posiciones
-- Solo cuenta partidos Finalizado. 3 puntos por victoria, 1 por empate.
-- Orden: puntos, diferencia de gol, goles a favor, nombre.
--
-- Reescopada por (Fase_ID, Grupo_ID) — motor-formatos-plantillas-
-- navegacion-plan.md, requerimiento #4 (Decisión Eng #10: se reescopa la
-- vista existente en vez de crear una nueva en paralelo). Un torneo Liga
-- (1 sola FASE, sin GRUPO) sigue devolviendo exactamente una fila por
-- equipo bajo su Torneo_ID — no rompe a ningún consumidor que ya filtre
-- por Torneo_ID (T40, no-regresión). Un torneo Grupos_Playoffs con 3
-- grupos ahora produce 3 tablas separadas bajo el mismo Torneo_ID — el
-- consumidor tiene que filtrar también por Grupo_ID (EC-54).
-- ------------------------------------------------------------
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
    -- 3A-12 (EC-51): desempate manual del admin, solo aplica a partidos
    -- de una Fase de Grupos (Grupo_ID no-NULL) — Liga no tiene
    -- GRUPO_EQUIPO, así que ge.* sale NULL ahí por construcción, no hace
    -- falta filtrar aparte. Grupo_Equipo_ID va expuesto para que el
    -- frontend pueda dirigir el PATCH sin resolverlo aparte.
    ge.ID          AS Grupo_Equipo_ID,
    ge.Orden_Manual
FROM lados l
JOIN EQUIPOS e ON e.ID = l.Equipo_ID
LEFT JOIN INSCRIPCIONES_TORNEO it ON it.Torneo_ID = l.Torneo_ID AND it.Equipo_ID = l.Equipo_ID
LEFT JOIN GRUPO_EQUIPO ge ON ge.Grupo_ID = l.Grupo_ID AND ge.Inscripcion_Torneo_ID = it.ID
GROUP BY l.Fase_ID, l.Grupo_ID, l.Torneo_ID, l.Equipo_ID, e.Nombre, ge.ID, ge.Orden_Manual
-- Orden_Manual entra DESPUÉS de PTS/DG/GF a propósito (ver el comentario
-- de la columna en 01_schema.sql): es el desempate de última instancia,
-- nunca puede promover a un equipo con menos puntos por encima de otro
-- con más.
ORDER BY l.Torneo_ID, l.Fase_ID, l.Grupo_ID NULLS FIRST, PTS DESC, DG DESC, GF DESC, ge.Orden_Manual NULLS LAST, Equipo;
-- Partidos de una FASE Tipo='Eliminacion' no entran en la práctica a esta
-- vista (no hay "tabla de posiciones" en un bracket) — el filtro natural
-- es que el frontend/backend solo la consulten para fases Liga/Grupos.

-- ------------------------------------------------------------
-- Goleadores consolidados por disciplina, cross-torneo.
--
-- vw_goles_acreditados cuenta por JUGADOR_ID (persona), no por perfil —
-- una misma persona con perfiles en Fútbol y Tenis solo tiene un
-- JUGADOR_ID. Sin el segundo JOIN contra TORNEO (que ancla el gol a la
-- disciplina de SU torneo), un gol de fútbol se contaría también en el
-- perfil de tenis de la misma persona.
--
-- COUNT(t.ID), no COUNT(ga.Evento_Partido_ID): con un LEFT JOIN encadenado
-- así, un gol de OTRA disciplina sigue presente en la fila (con t.* en
-- NULL) — hay que contar la columna que solo es NOT NULL cuando la
-- disciplina del torneo del gol coincide con la del perfil, o el conteo
-- incluye goles de la disciplina equivocada.
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW vw_goleadores_por_disciplina AS
SELECT
    jpd.ID AS Jugador_Perfil_ID,
    j.Nombre AS Jugador,
    d.Nombre AS Disciplina,
    COUNT(t.ID) AS Goles_Totales
FROM JUGADOR_PERFIL_DISCIPLINA jpd
JOIN JUGADORES j ON j.ID = jpd.Jugador_ID
JOIN DISCIPLINA d ON d.ID = jpd.Disciplina_ID
LEFT JOIN vw_goles_acreditados ga ON ga.JUGADOR_ID = jpd.Jugador_ID AND ga.Tipo_Gol = 'Gol'
LEFT JOIN TORNEO t ON t.ID = ga.TORNEO_ID AND t.Disciplina_ID = jpd.Disciplina_ID
GROUP BY jpd.ID, j.Nombre, d.Nombre;

-- ------------------------------------------------------------
-- Duración real de un partido (gestion-avanzada-equipos-control-mesa-plan.md,
-- Requerimiento 5) — se DERIVA de los Hitos, nunca se guarda como columna
-- que alguien tendría que recordar actualizar (mismo criterio que
-- vw_estado_perfil_disciplina/vw_goleadores_por_disciplina). Resta el
-- tiempo total pausado: cada Pausa se empareja con la PRIMERA Reanudacion
-- posterior a ella. Funciona igual para partidos de Períodos (da la
-- duración total incluyendo entretiempo) aunque el requerimiento solo la
-- pide para Corrido. Sin Fin_Partido todavía, no produce fila (partido en
-- curso) — GET /partidos/{id}/duracion lo maneja como "todavía sin dato".
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW vw_duracion_partido AS
WITH pausas AS (
    SELECT
        pausa.Partido_ID,
        SUM(
            EXTRACT(EPOCH FROM (reanuda.Timestamp_Real - pausa.Timestamp_Real))
        ) AS Segundos_Pausado
    FROM HITOS_PARTIDO pausa
    JOIN HITOS_PARTIDO reanuda
      ON reanuda.Partido_ID = pausa.Partido_ID
     AND reanuda.Tipo_Hito = 'Reanudacion'
     AND reanuda.Timestamp_Real = (
         SELECT MIN(r2.Timestamp_Real) FROM HITOS_PARTIDO r2
          WHERE r2.Partido_ID = pausa.Partido_ID AND r2.Tipo_Hito = 'Reanudacion'
            AND r2.Timestamp_Real > pausa.Timestamp_Real
     )
    WHERE pausa.Tipo_Hito = 'Pausa'
    GROUP BY pausa.Partido_ID
)
SELECT
    ini.Partido_ID,
    ini.Timestamp_Real AS Inicio,
    fin.Timestamp_Real AS Fin,
    (EXTRACT(EPOCH FROM (fin.Timestamp_Real - ini.Timestamp_Real)) - COALESCE(p.Segundos_Pausado, 0))::INT AS Duracion_Segundos
FROM HITOS_PARTIDO ini
JOIN HITOS_PARTIDO fin ON fin.Partido_ID = ini.Partido_ID AND fin.Tipo_Hito = 'Fin_Partido'
LEFT JOIN pausas p ON p.Partido_ID = ini.Partido_ID
WHERE ini.Tipo_Hito = 'Inicio_Partido';
