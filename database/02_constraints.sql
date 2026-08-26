-- ============================================================
-- 02_constraints.sql
-- Llaves foráneas, CHECK constraints y UNIQUE
-- Requiere que 01_schema.sql ya se haya ejecutado
--
-- Nota sobre ON DELETE CASCADE: 6 de las FK borran en cascada. La API
-- usa borrado lógico (Estado='Inactivo'), así que en operación normal
-- nunca se dispara. Un DELETE físico sobre TORNEO sí arrastraría
-- inscripciones, partidos y eventos: no lo expongas desde la API.
-- ============================================================

-- TORNEO
ALTER TABLE TORNEO
    ADD CONSTRAINT chk_torneo_estado CHECK (Estado IN ('Activo', 'Inactivo', 'Finalizado'));

-- EQUIPOS
ALTER TABLE EQUIPOS
    ADD CONSTRAINT chk_equipos_estado CHECK (Estado IN ('Activo', 'Inactivo'));

-- JUGADORES
ALTER TABLE JUGADORES
    ADD CONSTRAINT chk_jugadores_estado CHECK (Estado IN ('Activo', 'Inactivo'));

-- INSCRIPCIONES_TORNEO
ALTER TABLE INSCRIPCIONES_TORNEO
    ADD CONSTRAINT fk_inscripciones_torneo FOREIGN KEY (Torneo_ID) REFERENCES TORNEO(ID) ON DELETE CASCADE,
    ADD CONSTRAINT fk_inscripciones_equipo FOREIGN KEY (Equipo_ID) REFERENCES EQUIPOS(ID) ON DELETE CASCADE,
    ADD CONSTRAINT chk_inscripciones_estado CHECK (Estado IN ('Inscrito', 'Cancelado', 'Confirmado')),
    ADD CONSTRAINT unique_inscripcion UNIQUE (Torneo_ID, Equipo_ID);

-- JUGADOR_EQUIPO
ALTER TABLE JUGADOR_EQUIPO
    ADD CONSTRAINT fk_jugador_equipo_jugador FOREIGN KEY (JUGADOR_ID) REFERENCES JUGADORES(ID) ON DELETE CASCADE,
    ADD CONSTRAINT fk_jugador_equipo_equipo FOREIGN KEY (EQUIPO_ID) REFERENCES EQUIPOS(ID) ON DELETE CASCADE,
    ADD CONSTRAINT chk_jugador_equipo_estado CHECK (Estado IN ('Activo', 'Inactivo', 'Suspendido')),
    ADD CONSTRAINT unique_jugador_equipo UNIQUE (JUGADOR_ID, EQUIPO_ID, Fecha_Inicio);

-- PARTIDOS
-- fk_partidos_arbitro: ON DELETE SET NULL, no CASCADE/RESTRICT — los
-- usuarios se dan de baja lógica (Estado='Inactivo'), nunca se borran
-- físicamente en operación normal, pero si alguna vez se purga una fila
-- no tiene sentido que eso arrastre o bloquee el partido.
ALTER TABLE PARTIDOS
    ADD CONSTRAINT fk_partidos_torneo FOREIGN KEY (Torneo_ID) REFERENCES TORNEO(ID) ON DELETE CASCADE,
    ADD CONSTRAINT fk_partidos_local FOREIGN KEY (EQUIPOS_ID_LOCAL) REFERENCES EQUIPOS(ID),
    ADD CONSTRAINT fk_partidos_visitante FOREIGN KEY (EQUIPOS_ID_VISITANTE) REFERENCES EQUIPOS(ID),
    ADD CONSTRAINT fk_partidos_arbitro FOREIGN KEY (ARBITRO_ID) REFERENCES USUARIOS(ID) ON DELETE SET NULL,
    ADD CONSTRAINT chk_partidos_equipos_distintos CHECK (EQUIPOS_ID_LOCAL <> EQUIPOS_ID_VISITANTE),
    ADD CONSTRAINT chk_partidos_estado CHECK (Estado IN ('Programado', 'En curso', 'Finalizado', 'Cancelado')),
    ADD CONSTRAINT chk_partidos_fase CHECK (Fase IN ('Regular', 'Grupos', 'Octavos', 'Cuartos', 'Semifinal', 'Final', 'Tercer puesto')),
    ADD CONSTRAINT chk_partidos_jornada CHECK (Jornada IS NULL OR Jornada > 0),
    ADD CONSTRAINT unique_partido UNIQUE (Torneo_ID, EQUIPOS_ID_LOCAL, EQUIPOS_ID_VISITANTE, Fecha_Partido);

-- EVENTOS
ALTER TABLE EVENTOS
    ADD CONSTRAINT chk_eventos_estado CHECK (Estado IN ('Activo', 'Inactivo'));

-- USUARIOS
-- Los roles siguen la separación de roles-3-modulos-plan.md (Fase 1):
--   AdminGeneral -- todo lo de TorneoAdmin, más crear/eliminar usuarios y
--                    cambiar roles (backend/app/api/routes/usuarios.py,
--                    gateado específicamente a este rol — NO a TorneoAdmin)
--   TorneoAdmin   -- crea y administra torneos, equipos, jugadores,
--                    partidos y plantillas (pool compartido, sin dueño)
--   Arbitro       -- solo ve/carga los partidos que tiene asignados
--                    (PARTIDOS.ARBITRO_ID) — goles, tarjetas y cambios
--   Publico       -- solo lectura de las consultas agregadas
-- AdminGeneral no aparece listado en los `require_roles(...)` de cada
-- endpoint: pasa cualquier chequeo vía un bypass centralizado en
-- backend/app/api/deps.py, no por estar enumerado ahí.
-- chk_usuarios_username_min evita el username vacío, que el NOT NULL
-- por sí solo deja pasar ('' no es NULL).
ALTER TABLE USUARIOS
    ADD CONSTRAINT unique_usuario_username UNIQUE (Username),
    ADD CONSTRAINT chk_usuarios_username_lower CHECK (Username = LOWER(Username)),
    ADD CONSTRAINT chk_usuarios_username_min CHECK (LENGTH(TRIM(Username)) >= 3),
    ADD CONSTRAINT chk_usuarios_password_hash CHECK (LENGTH(Password_Hash) >= 20),
    ADD CONSTRAINT chk_usuarios_rol CHECK (Rol IN ('AdminGeneral', 'TorneoAdmin', 'Arbitro', 'Publico')),
    ADD CONSTRAINT chk_usuarios_estado CHECK (Estado IN ('Activo', 'Inactivo'));

-- EVENTOS_PARTIDO
-- El rango de MINUTO llega a 130: cubre los 120' de prórroga más el
-- tiempo de descuento. Con el tope anterior de 120 no se podían
-- registrar goles de descuento ni definiciones por penales.
ALTER TABLE EVENTOS_PARTIDO
    ADD CONSTRAINT fk_eventos_partido_partido FOREIGN KEY (PARTIDOS_ID) REFERENCES PARTIDOS(ID) ON DELETE CASCADE,
    ADD CONSTRAINT fk_eventos_partido_jugador FOREIGN KEY (JUGADOR_ID) REFERENCES JUGADORES(ID),
    ADD CONSTRAINT fk_eventos_partido_equipo FOREIGN KEY (EQUIPO_ID) REFERENCES EQUIPOS(ID),
    ADD CONSTRAINT fk_eventos_partido_evento FOREIGN KEY (EVENTOS_ID) REFERENCES EVENTOS(ID),
    ADD CONSTRAINT fk_eventos_partido_jugador_entra FOREIGN KEY (JUGADOR_ID_ENTRA) REFERENCES JUGADORES(ID),
    ADD CONSTRAINT chk_eventos_partido_minuto CHECK (MINUTO >= 0 AND MINUTO <= 130),
    ADD CONSTRAINT chk_eventos_partido_cambio_distinto CHECK (JUGADOR_ID_ENTRA IS NULL OR JUGADOR_ID_ENTRA <> JUGADOR_ID),
    ADD CONSTRAINT chk_eventos_partido_estado CHECK (Estado IN ('Registrado', 'Anulado'));
