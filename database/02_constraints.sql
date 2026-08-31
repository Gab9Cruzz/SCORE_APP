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

-- DISCIPLINA
-- chk_disciplina_tipo se eliminó junto con la columna Tipo (catálogo
-- unificado bajo Modalidad.Tamano_Equipo — Decisión A1). unique_disciplina_nombre
-- también sostiene el ON CONFLICT (Nombre) DO NOTHING del seed idempotente
-- de 11_catalogo_disciplinas.sql.
ALTER TABLE DISCIPLINA
    ADD CONSTRAINT unique_disciplina_nombre UNIQUE (Nombre),
    ADD CONSTRAINT chk_disciplina_estado CHECK (Estado IN ('Activo', 'Inactivo'));

-- MODALIDAD
ALTER TABLE MODALIDAD
    ADD CONSTRAINT fk_modalidad_disciplina FOREIGN KEY (Disciplina_ID) REFERENCES DISCIPLINA(ID) ON DELETE CASCADE,
    ADD CONSTRAINT chk_modalidad_tamano CHECK (Tamano_Equipo > 0),
    ADD CONSTRAINT chk_modalidad_estado CHECK (Estado IN ('Activo', 'Inactivo')),
    ADD CONSTRAINT unique_modalidad_por_disciplina UNIQUE (Disciplina_ID, Nombre);

-- TORNEO
-- Disciplina_ID/Modalidad_ID: ON DELETE sin especificar (NO ACTION) a
-- propósito — son catálogos que se dan de baja lógica (Estado), nunca se
-- borran físicamente, así que no hace falta CASCADE ni SET NULL acá.
-- Torneo_Grupo_ID: ON DELETE CASCADE — a diferencia de Disciplina/Modalidad,
-- un TORNEO_GRUPO sin ninguna edición no tiene razón de existir (no es un
-- catálogo compartido, es un agrupador 1:N de sus propias ediciones).
ALTER TABLE TORNEO
    ADD CONSTRAINT fk_torneo_disciplina FOREIGN KEY (Disciplina_ID) REFERENCES DISCIPLINA(ID),
    ADD CONSTRAINT fk_torneo_modalidad FOREIGN KEY (Modalidad_ID) REFERENCES MODALIDAD(ID),
    ADD CONSTRAINT fk_torneo_grupo FOREIGN KEY (Torneo_Grupo_ID) REFERENCES TORNEO_GRUPO(ID) ON DELETE CASCADE,
    ADD CONSTRAINT chk_torneo_numero_edicion CHECK (Numero_Edicion > 0),
    ADD CONSTRAINT unique_edicion_por_grupo UNIQUE (Torneo_Grupo_ID, Numero_Edicion),
    ADD CONSTRAINT chk_torneo_estado CHECK (Estado IN ('Activo', 'Inactivo', 'Finalizado')),
    -- Motor de Formatos (requerimiento #4). La coherencia de PARÁMETROS
    -- según el Formato (Ida_Vuelta solo en Liga, Equipos_Por_Grupo/
    -- Clasificados_Por_Grupo solo en Grupos_Playoffs) se valida en
    -- TorneoService, no acá: un CHECK violado cae al 409 genérico de
    -- IntegrityError (exceptions/handlers.py), y el plan pide un 400 con
    -- mensaje específico (T33) — mismo criterio que la validación de
    -- dorsal (EC-45): Python se anticipa para dar el mensaje claro.
    ADD CONSTRAINT chk_torneo_formato CHECK (Formato IN ('Liga', 'Eliminacion', 'Grupos_Playoffs'));

-- EQUIPOS
-- Disciplina_ID/Modalidad_ID: sin ON DELETE CASCADE a proposito — el
-- catalogo de disciplinas es solo-lectura desde la API y un equipo no
-- debe desaparecer porque alguien borro una disciplina a mano (mismo
-- criterio que fk_torneo_disciplina). No se agrega
-- UNIQUE (Nombre, Disciplina_ID): hoy tampoco hay UNIQUE sobre Nombre y
-- agregarlo romperia datos existentes (EC-43, anotado en TODOS.md).
ALTER TABLE EQUIPOS
    ADD CONSTRAINT fk_equipos_disciplina FOREIGN KEY (Disciplina_ID) REFERENCES DISCIPLINA(ID),
    ADD CONSTRAINT fk_equipos_modalidad FOREIGN KEY (Modalidad_ID) REFERENCES MODALIDAD(ID),
    ADD CONSTRAINT chk_equipos_estado CHECK (Estado IN ('Activo', 'Inactivo'));

-- JUGADORES
-- Correo_Electronico NO es UNIQUE a propósito (EC-12 del plan): dos
-- cédulas distintas pueden compartir un correo familiar.
ALTER TABLE JUGADORES
    ADD CONSTRAINT unique_jugador_cedula UNIQUE (Cedula),
    ADD CONSTRAINT chk_jugadores_estado CHECK (Estado IN ('Activo', 'Inactivo'));

-- JUGADOR_PERFIL_DISCIPLINA
ALTER TABLE JUGADOR_PERFIL_DISCIPLINA
    ADD CONSTRAINT fk_perfil_disciplina_jugador FOREIGN KEY (Jugador_ID) REFERENCES JUGADORES(ID) ON DELETE CASCADE,
    ADD CONSTRAINT fk_perfil_disciplina_disciplina FOREIGN KEY (Disciplina_ID) REFERENCES DISCIPLINA(ID),
    ADD CONSTRAINT unique_perfil_por_disciplina UNIQUE (Jugador_ID, Disciplina_ID);

-- INSCRIPCIONES_TORNEO
-- Equipo_ID/Jugador_Perfil_ID: exactamente uno de los dos, nunca ambos ni
-- ninguno (Decisión B1) — el service layer decide cuál setear según
-- Modalidad.Tamano_Equipo del torneo (=1 → Jugador_Perfil_ID; >=2 →
-- Equipo_ID). unique_inscripcion/unique_inscripcion_individual: Postgres
-- no compara NULLs como iguales en un UNIQUE, así que ambos conviven sin
-- chocar entre sí — cada uno cierra la duplicación dentro de su propio
-- camino (mismo Equipo dos veces / mismo Jugador dos veces en el mismo
-- torneo).
ALTER TABLE INSCRIPCIONES_TORNEO
    ADD CONSTRAINT fk_inscripciones_torneo FOREIGN KEY (Torneo_ID) REFERENCES TORNEO(ID) ON DELETE CASCADE,
    ADD CONSTRAINT fk_inscripciones_equipo FOREIGN KEY (Equipo_ID) REFERENCES EQUIPOS(ID) ON DELETE CASCADE,
    ADD CONSTRAINT fk_inscripciones_jugador_perfil FOREIGN KEY (Jugador_Perfil_ID) REFERENCES JUGADOR_PERFIL_DISCIPLINA(ID) ON DELETE CASCADE,
    ADD CONSTRAINT chk_inscripciones_estado CHECK (Estado IN ('Inscrito', 'Cancelado', 'Confirmado')),
    ADD CONSTRAINT chk_inscripcion_exactamente_uno CHECK (
        (Equipo_ID IS NOT NULL AND Jugador_Perfil_ID IS NULL) OR
        (Equipo_ID IS NULL AND Jugador_Perfil_ID IS NOT NULL)
    ),
    ADD CONSTRAINT unique_inscripcion UNIQUE (Torneo_ID, Equipo_ID),
    ADD CONSTRAINT unique_inscripcion_individual UNIQUE (Torneo_ID, Jugador_Perfil_ID);

-- JUGADOR_EQUIPO
-- unique_jugador_equipo: ya no es (JUGADOR_ID, EQUIPO_ID) sino (perfil,
-- roster-de-torneo) — el mismo perfil puede tener varias filas históricas
-- en el mismo roster (traspasos de ida y vuelta), nunca dos con la misma
-- Fecha_Inicio.
-- El dorsal único por roster vigente (antes uq_dorsal_por_equipo_vigente
-- en 03_indexes.sql, ya existía) se mantiene como índice PARCIAL en vez
-- del UNIQUE plano que sugiere el plan (EC-13): un UNIQUE sin condición
-- de vigencia deja el dorsal bloqueado para siempre en ese roster incluso
-- después de que el jugador se va — ver 03_indexes.sql.
ALTER TABLE JUGADOR_EQUIPO
    ADD CONSTRAINT fk_jugador_equipo_perfil FOREIGN KEY (Jugador_Perfil_ID) REFERENCES JUGADOR_PERFIL_DISCIPLINA(ID) ON DELETE CASCADE,
    ADD CONSTRAINT fk_jugador_equipo_inscripcion FOREIGN KEY (Inscripcion_Torneo_ID) REFERENCES INSCRIPCIONES_TORNEO(ID) ON DELETE CASCADE,
    ADD CONSTRAINT chk_jugador_equipo_estado CHECK (Estado IN ('Activo', 'Inactivo', 'Suspendido', 'Traspasado')),
    ADD CONSTRAINT unique_jugador_equipo UNIQUE (Jugador_Perfil_ID, Inscripcion_Torneo_ID, Fecha_Inicio);

-- TRASPASOS
-- Realizado_Por sin ON DELETE (NO ACTION): es un rastro de auditoría
-- append-only, no debe poder perder silenciosamente quién hizo el
-- traspaso porque alguien borró la fila de USUARIOS (que en operación
-- normal tampoco se borra físicamente, ver comentario de cabecera).
ALTER TABLE TRASPASOS
    ADD CONSTRAINT fk_traspasos_perfil FOREIGN KEY (Jugador_Perfil_ID) REFERENCES JUGADOR_PERFIL_DISCIPLINA(ID),
    ADD CONSTRAINT fk_traspasos_origen FOREIGN KEY (Inscripcion_Origen_ID) REFERENCES INSCRIPCIONES_TORNEO(ID),
    ADD CONSTRAINT fk_traspasos_destino FOREIGN KEY (Inscripcion_Destino_ID) REFERENCES INSCRIPCIONES_TORNEO(ID),
    ADD CONSTRAINT fk_traspasos_usuario FOREIGN KEY (Realizado_Por) REFERENCES USUARIOS(ID),
    ADD CONSTRAINT chk_traspasos_estado CHECK (Estado IN ('Completado', 'Anulado'));

-- FASE / GRUPO / GRUPO_EQUIPO / SORTEOS (Motor de Formatos, requerimiento #4)
ALTER TABLE FASE
    ADD CONSTRAINT fk_fase_torneo FOREIGN KEY (Torneo_ID) REFERENCES TORNEO(ID) ON DELETE CASCADE,
    ADD CONSTRAINT chk_fase_tipo CHECK (Tipo IN ('Liga', 'Grupos', 'Eliminacion')),
    ADD CONSTRAINT chk_fase_estado CHECK (Estado IN ('Pendiente', 'En_Curso', 'Finalizada')),
    ADD CONSTRAINT unique_fase_orden_por_torneo UNIQUE (Torneo_ID, Orden);

ALTER TABLE GRUPO
    ADD CONSTRAINT fk_grupo_fase FOREIGN KEY (Fase_ID) REFERENCES FASE(ID) ON DELETE CASCADE,
    ADD CONSTRAINT unique_grupo_nombre_por_fase UNIQUE (Fase_ID, Nombre);

-- fk_grupo_equipo_inscripcion sin ON DELETE: INSCRIPCIONES_TORNEO no se
-- borra físicamente en operación normal (mismo criterio que el resto del
-- esquema) — si algún día se agrega un borrado real, esta fila debería
-- bloquearlo (RESTRICT es el default), no desaparecer en silencio.
ALTER TABLE GRUPO_EQUIPO
    ADD CONSTRAINT fk_grupo_equipo_grupo FOREIGN KEY (Grupo_ID) REFERENCES GRUPO(ID) ON DELETE CASCADE,
    ADD CONSTRAINT fk_grupo_equipo_inscripcion FOREIGN KEY (Inscripcion_Torneo_ID) REFERENCES INSCRIPCIONES_TORNEO(ID),
    ADD CONSTRAINT unique_grupo_equipo UNIQUE (Grupo_ID, Inscripcion_Torneo_ID);

ALTER TABLE SORTEOS
    ADD CONSTRAINT fk_sorteos_fase FOREIGN KEY (Fase_ID) REFERENCES FASE(ID) ON DELETE CASCADE,
    ADD CONSTRAINT fk_sorteos_usuario FOREIGN KEY (Realizado_Por) REFERENCES USUARIOS(ID),
    ADD CONSTRAINT chk_sorteos_estado CHECK (Estado IN ('Completado', 'Rehecho'));

-- PARTIDOS
-- fk_partidos_arbitro: ON DELETE SET NULL, no CASCADE/RESTRICT — los
-- usuarios se dan de baja lógica (Estado='Inactivo'), nunca se borran
-- físicamente en operación normal, pero si alguna vez se purga una fila
-- no tiene sentido que eso arrastre o bloquee el partido.
--
-- EQUIPOS_ID_LOCAL/VISITANTE pasaron a nullable (Decisión Eng #13): con
-- NULL, chk_partidos_equipos_distintos y unique_partido no bloquean nada
-- (NULL <> NULL y una UNIQUE con NULL nunca son "iguales" en SQL
-- estándar) — un shell de bracket con ambos NULL, o con uno solo lleno
-- por un bye, sigue pasando las dos.
--
-- Los 4 FK de bracket (Partido_Siguiente/Partido_Perdedor_Siguiente,
-- ambos auto-referenciados) van ON DELETE SET NULL: PARTIDOS no tiene
-- borrado físico en operación normal (soft-delete vía Estado='Cancelado'),
-- esto es solo la red de seguridad si alguna vez se purga una fila.
ALTER TABLE PARTIDOS
    ADD CONSTRAINT fk_partidos_torneo FOREIGN KEY (Torneo_ID) REFERENCES TORNEO(ID) ON DELETE CASCADE,
    ADD CONSTRAINT fk_partidos_local FOREIGN KEY (EQUIPOS_ID_LOCAL) REFERENCES EQUIPOS(ID),
    ADD CONSTRAINT fk_partidos_visitante FOREIGN KEY (EQUIPOS_ID_VISITANTE) REFERENCES EQUIPOS(ID),
    ADD CONSTRAINT fk_partidos_arbitro FOREIGN KEY (ARBITRO_ID) REFERENCES USUARIOS(ID) ON DELETE SET NULL,
    ADD CONSTRAINT fk_partidos_fase FOREIGN KEY (Fase_ID) REFERENCES FASE(ID),
    ADD CONSTRAINT fk_partidos_grupo FOREIGN KEY (Grupo_ID) REFERENCES GRUPO(ID),
    ADD CONSTRAINT fk_partidos_siguiente FOREIGN KEY (Partido_Siguiente_ID) REFERENCES PARTIDOS(ID) ON DELETE SET NULL,
    ADD CONSTRAINT fk_partidos_perdedor_siguiente FOREIGN KEY (Partido_Perdedor_Siguiente_ID) REFERENCES PARTIDOS(ID) ON DELETE SET NULL,
    ADD CONSTRAINT fk_partidos_ganador_desempate FOREIGN KEY (Ganador_Desempate_ID) REFERENCES EQUIPOS(ID),
    ADD CONSTRAINT chk_partidos_equipos_distintos CHECK (EQUIPOS_ID_LOCAL IS NULL OR EQUIPOS_ID_VISITANTE IS NULL OR EQUIPOS_ID_LOCAL <> EQUIPOS_ID_VISITANTE),
    ADD CONSTRAINT chk_partidos_estado CHECK (Estado IN ('Programado', 'En curso', 'Finalizado', 'Cancelado')),
    ADD CONSTRAINT chk_partidos_fase CHECK (Fase IN ('Regular', 'Grupos', 'Octavos', 'Cuartos', 'Semifinal', 'Final', 'Tercer puesto')),
    ADD CONSTRAINT chk_partidos_jornada CHECK (Jornada IS NULL OR Jornada > 0),
    ADD CONSTRAINT chk_partidos_slot_siguiente CHECK (Slot_Siguiente IS NULL OR Slot_Siguiente IN ('Local', 'Visitante')),
    ADD CONSTRAINT chk_partidos_slot_perdedor_siguiente CHECK (Slot_Perdedor_Siguiente IS NULL OR Slot_Perdedor_Siguiente IN ('Local', 'Visitante')),
    ADD CONSTRAINT unique_partido UNIQUE (Torneo_ID, EQUIPOS_ID_LOCAL, EQUIPOS_ID_VISITANTE, Fecha_Partido);

-- EVENTOS
ALTER TABLE EVENTOS
    ADD CONSTRAINT chk_eventos_estado CHECK (Estado IN ('Activo', 'Inactivo'));

-- USUARIOS

-- ACCESOS (bitacora de login)
-- Sin ON DELETE: rastro de auditoria, mismo criterio que
-- TRASPASOS.Realizado_Por. chk_accesos_motivo mantiene coherente el par
-- (Exitoso, Motivo): un acceso exitoso no tiene motivo de fallo, y uno
-- fallido siempre dice por que — sin eso, "Motivo NULL" seria ambiguo
-- entre "entro bien" y "fallo y no anotamos por que".
ALTER TABLE ACCESOS
    ADD CONSTRAINT fk_accesos_usuario FOREIGN KEY (Usuario_ID) REFERENCES USUARIOS(ID),
    ADD CONSTRAINT chk_accesos_motivo CHECK (
        (Exitoso = TRUE AND Motivo IS NULL)
     OR (Exitoso = FALSE AND Motivo IN ('credenciales', 'inactivo'))
    );


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

-- AUDITORIA (bitacora de cambios)
-- Sin ON DELETE: rastro de auditoria, mismo criterio que ACCESOS.Usuario_ID
-- y TRASPASOS.Realizado_Por.
ALTER TABLE AUDITORIA
    ADD CONSTRAINT fk_auditoria_usuario FOREIGN KEY (Usuario_ID) REFERENCES USUARIOS(ID),
    ADD CONSTRAINT chk_auditoria_accion CHECK (Accion IN ('crear', 'modificar', 'eliminar'));
