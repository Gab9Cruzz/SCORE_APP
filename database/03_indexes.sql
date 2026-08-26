-- ============================================================
-- 03_indexes.sql
-- Índices sobre columnas FK y de consulta frecuente
-- Postgres no indexa automáticamente las FK, así que se crean manualmente
-- ============================================================

-- INSCRIPCIONES_TORNEO
CREATE INDEX idx_inscripciones_equipo ON INSCRIPCIONES_TORNEO(Equipo_ID);

-- JUGADOR_EQUIPO
CREATE INDEX idx_jugador_equipo_jugador ON JUGADOR_EQUIPO(JUGADOR_ID);
CREATE INDEX idx_jugador_equipo_equipo ON JUGADOR_EQUIPO(EQUIPO_ID);
CREATE INDEX idx_jugador_equipo_vigencia ON JUGADOR_EQUIPO(EQUIPO_ID, Fecha_Inicio, Fecha_Fin);

-- Un dorsal no se puede repetir dentro del mismo equipo.
-- El índice es PARCIAL, sobre plantillas vigentes: cuando un jugador
-- causa baja (Fecha_Fin) su dorsal queda libre para otro.
CREATE UNIQUE INDEX uq_dorsal_por_equipo_vigente
    ON JUGADOR_EQUIPO (EQUIPO_ID, Dorsal)
    WHERE Fecha_Fin IS NULL AND Estado = 'Activo' AND Dorsal IS NOT NULL;

-- PARTIDOS
CREATE INDEX idx_partidos_torneo ON PARTIDOS(Torneo_ID);
CREATE INDEX idx_partidos_local ON PARTIDOS(EQUIPOS_ID_LOCAL);
CREATE INDEX idx_partidos_visitante ON PARTIDOS(EQUIPOS_ID_VISITANTE);
CREATE INDEX idx_partidos_fecha ON PARTIDOS(Fecha_Partido);
CREATE INDEX idx_partidos_estado ON PARTIDOS(Estado);
CREATE INDEX idx_partidos_jornada ON PARTIDOS(Torneo_ID, Jornada);
-- Usado por el ownership-check de Árbitro (Fase 1) y por "Mis partidos"
-- (Fase 3) — ambos filtran por ARBITRO_ID en cada request.
CREATE INDEX idx_partidos_arbitro ON PARTIDOS(ARBITRO_ID);

-- EVENTOS_PARTIDO
CREATE INDEX idx_eventos_partido_partido ON EVENTOS_PARTIDO(PARTIDOS_ID);
CREATE INDEX idx_eventos_partido_jugador ON EVENTOS_PARTIDO(JUGADOR_ID);
CREATE INDEX idx_eventos_partido_evento ON EVENTOS_PARTIDO(EVENTOS_ID);
CREATE INDEX idx_eventos_partido_equipo ON EVENTOS_PARTIDO(EQUIPO_ID);
