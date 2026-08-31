-- ============================================================
-- 03_indexes.sql
-- Índices sobre columnas FK y de consulta frecuente
-- Postgres no indexa automáticamente las FK, así que se crean manualmente
-- ============================================================

-- MODALIDAD
CREATE INDEX idx_modalidad_disciplina ON MODALIDAD(Disciplina_ID);

-- TORNEO
CREATE INDEX idx_torneo_disciplina ON TORNEO(Disciplina_ID);
CREATE INDEX idx_torneo_modalidad ON TORNEO(Modalidad_ID);
-- Usado por el selector de ediciones (torneos-admin-plan.md, Fase 2/3):
-- "traer todas las ediciones de este grupo" filtra por esta columna en
-- cada carga del dashboard de un torneo.
CREATE INDEX idx_torneo_grupo ON TORNEO(Torneo_Grupo_ID);

-- ACCESOS (bitacora de login)
-- La pantalla de auditoria lista SIEMPRE por fecha descendente (lo ultimo
-- primero), de ahi el DESC en el indice. Los otros dos son los filtros que
-- ofrece: por cuenta y por el texto tipeado (que es lo que hay cuando el
-- usuario ni siquiera existe).
CREATE INDEX idx_accesos_fecha ON ACCESOS(Fecha DESC);
CREATE INDEX idx_accesos_usuario ON ACCESOS(Usuario_ID);
CREATE INDEX idx_accesos_username ON ACCESOS(Username);

-- EQUIPOS
-- Los dos filtros nuevos de GET /equipos?disciplina_id=&modalidad_id=
-- (equipos-disciplina-navegacion-plan.md, Mejora #1: los filtros
-- server-side son lo que evita que la grilla tope contra el limite de 200
-- filas sin que el admin se entere).
CREATE INDEX idx_equipos_disciplina ON EQUIPOS(Disciplina_ID);
CREATE INDEX idx_equipos_modalidad ON EQUIPOS(Modalidad_ID);

-- JUGADOR_PERFIL_DISCIPLINA
CREATE INDEX idx_perfil_disciplina_jugador ON JUGADOR_PERFIL_DISCIPLINA(Jugador_ID);
CREATE INDEX idx_perfil_disciplina_disciplina ON JUGADOR_PERFIL_DISCIPLINA(Disciplina_ID);

-- INSCRIPCIONES_TORNEO
CREATE INDEX idx_inscripciones_equipo ON INSCRIPCIONES_TORNEO(Equipo_ID);
CREATE INDEX idx_inscripciones_jugador_perfil ON INSCRIPCIONES_TORNEO(Jugador_Perfil_ID);

-- JUGADOR_EQUIPO
CREATE INDEX idx_jugador_equipo_perfil ON JUGADOR_EQUIPO(Jugador_Perfil_ID);
CREATE INDEX idx_jugador_equipo_inscripcion ON JUGADOR_EQUIPO(Inscripcion_Torneo_ID);
CREATE INDEX idx_jugador_equipo_vigencia ON JUGADOR_EQUIPO(Inscripcion_Torneo_ID, Fecha_Inicio, Fecha_Fin);

-- Un dorsal no se puede repetir dentro del mismo roster (equipo-en-este-
-- torneo). El índice es PARCIAL, sobre membresías vigentes: cuando un
-- jugador causa baja (Fecha_Fin) o es traspasado, su dorsal queda libre
-- para otro en ese mismo roster.
--
-- El plan (EC-13) pide un UNIQUE plano (Inscripcion_Torneo_ID, Dorsal) sin
-- condición de vigencia. Se mantiene la forma parcial que ya tenía este
-- índice antes de este cambio (uq_dorsal_por_equipo_vigente) porque un
-- UNIQUE sin WHERE deja el dorsal bloqueado para siempre en ese roster
-- incluso después de que el jugador se va — sería una regresión, no
-- solo un cierre de gap.
CREATE UNIQUE INDEX uq_dorsal_por_roster_vigente
    ON JUGADOR_EQUIPO (Inscripcion_Torneo_ID, Dorsal)
    WHERE Fecha_Fin IS NULL AND Estado = 'Activo' AND Dorsal IS NOT NULL;

-- TRASPASOS
CREATE INDEX idx_traspasos_perfil ON TRASPASOS(Jugador_Perfil_ID);
CREATE INDEX idx_traspasos_origen ON TRASPASOS(Inscripcion_Origen_ID);
CREATE INDEX idx_traspasos_destino ON TRASPASOS(Inscripcion_Destino_ID);
CREATE INDEX idx_traspasos_usuario ON TRASPASOS(Realizado_Por);

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

-- Motor de Formatos (motor-formatos-plantillas-navegacion-plan.md,
-- requerimiento #4)
CREATE INDEX idx_partidos_fase ON PARTIDOS(Fase_ID);
CREATE INDEX idx_partidos_grupo ON PARTIDOS(Grupo_ID);
-- Recorrido del árbol del bracket (vista de bracket, GET /torneos/{id}/bracket).
CREATE INDEX idx_partidos_siguiente ON PARTIDOS(Partido_Siguiente_ID);
CREATE INDEX idx_partidos_perdedor_siguiente ON PARTIDOS(Partido_Perdedor_Siguiente_ID);

CREATE INDEX idx_fase_torneo ON FASE(Torneo_ID);
CREATE INDEX idx_grupo_fase ON GRUPO(Fase_ID);
CREATE INDEX idx_grupo_equipo_grupo ON GRUPO_EQUIPO(Grupo_ID);
CREATE INDEX idx_grupo_equipo_inscripcion ON GRUPO_EQUIPO(Inscripcion_Torneo_ID);
CREATE INDEX idx_sorteos_fase ON SORTEOS(Fase_ID);

-- EVENTOS_PARTIDO
CREATE INDEX idx_eventos_partido_partido ON EVENTOS_PARTIDO(PARTIDOS_ID);
CREATE INDEX idx_eventos_partido_jugador ON EVENTOS_PARTIDO(JUGADOR_ID);
CREATE INDEX idx_eventos_partido_evento ON EVENTOS_PARTIDO(EVENTOS_ID);

-- AUDITORIA (bitacora de cambios)
-- Misma logica que ACCESOS: la pantalla lista siempre por fecha
-- descendente, y los otros dos son los filtros que ofrece GET /auditoria
-- (por entidad afectada y por quien lo hizo).
CREATE INDEX idx_auditoria_fecha ON AUDITORIA(Fecha DESC);
CREATE INDEX idx_auditoria_tabla_registro ON AUDITORIA(Tabla, Registro_ID);
CREATE INDEX idx_auditoria_usuario ON AUDITORIA(Usuario_ID);
CREATE INDEX idx_eventos_partido_equipo ON EVENTOS_PARTIDO(EQUIPO_ID);
