-- ============================================================
-- 05_seed.sql
-- Datos de prueba
--
-- Los EVENTOS_ID se resuelven por nombre y no por número. Antes se
-- escribían literales (1 = Gol, 3 = Tarjeta Amarilla) asumiendo el orden
-- en que el SERIAL los había asignado: si el catálogo se reordena o se
-- recarga, esos literales apuntan a otro evento sin avisar.
--
-- Nota sobre las fechas: la Copa Ecotec 2026 corrió del 2026-01-10 al
-- 2026-03-30 y queda con Estado='Activo'. Es un torneo ya terminado que
-- sigue marcado como activo; se conserva así porque son los datos que
-- están cargados hoy. Al montar un entorno nuevo conviene revisarlo.
-- ============================================================

-- Catálogo de eventos
INSERT INTO EVENTOS (Nombre, Descripcion) VALUES
    ('Gol', 'Gol anotado por el jugador'),
    ('Autogol', 'Gol en propia meta'),
    ('Tarjeta Amarilla', 'Amonestación'),
    ('Tarjeta Roja', 'Expulsión'),
    ('Cambio', 'Sustitución de jugador');

-- Catálogo de disciplinas.
-- Va ANTES que TORNEO: TORNEO.Disciplina_ID es NOT NULL (ver 01_schema.sql,
-- ya no es el texto libre 'Fútbol' de antes). Ya no lleva Tipo (catálogo
-- unificado — Decisión A1 de ediciones-catalogo-disciplinas-plan.md): toda
-- disciplina necesita al menos una MODALIDAD, así que se carga "Fútbol 11"
-- acá mismo. 11_catalogo_disciplinas.sql vuelve a insertar ambas filas
-- después (idempotente vía ON CONFLICT DO NOTHING) sin duplicarlas, junto
-- con el resto del catálogo maestro.
INSERT INTO DISCIPLINA (Nombre) VALUES
    ('Fútbol');

INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo) VALUES
    ((SELECT ID FROM DISCIPLINA WHERE Nombre = 'Fútbol'), 'Fútbol 11', 11);

-- Torneo Grupo — torneos-admin-plan.md, Fase 1/3. Cada TORNEO es una
-- edición de su grupo; "Copa Ecotec" tiene una sola edición cargada hoy.
INSERT INTO TORNEO_GRUPO (Nombre) VALUES
    ('Copa Ecotec');

-- Torneo
-- Modalidad_ID es NOT NULL (catálogo unificado) — Copa Ecotec 2026 se jugó
-- con 11 por lado, de ahí "Fútbol 11".
INSERT INTO TORNEO (Nombre, Disciplina_ID, Modalidad_ID, Torneo_Grupo_ID, Numero_Edicion, Fecha_Inicio, Fecha_Fin) VALUES
    ('Copa Ecotec 2026',
     (SELECT ID FROM DISCIPLINA WHERE Nombre = 'Fútbol'),
     (SELECT ID FROM MODALIDAD WHERE Nombre = 'Fútbol 11' AND Disciplina_ID = (SELECT ID FROM DISCIPLINA WHERE Nombre = 'Fútbol')),
     (SELECT ID FROM TORNEO_GRUPO WHERE Nombre = 'Copa Ecotec'), 1, '2026-01-10', '2026-03-30');

-- Configuración de tiempos del torneo (gestion-avanzada-equipos-control-
-- mesa-plan.md) — todo torneo creado vía TorneoService recibe una fila acá
-- (mismo criterio que la FASE inicial); el seed no pasa por el service,
-- se crea a mano. Fútbol 11 -> Periodos, 2x45'.
INSERT INTO CONFIGURACION_TIEMPO_TORNEO (Torneo_ID, Tipo_Cronometro, Cantidad_Periodos, Duracion_Periodo_Minutos, Duracion_Descanso_Minutos) VALUES
    (1, 'Periodos', 2, 45, 15);

-- Equipos
-- Disciplina_ID/Modalidad_ID son NOT NULL desde
-- equipos-disciplina-navegacion-plan.md: los 3 equipos de prueba juegan la
-- Copa Ecotec 2026, así que su disciplina/modalidad son las del torneo
-- ('Fútbol' / 'Fútbol 11'). Sin esto la inscripción de más abajo violaría
-- la validación de disciplina que este mismo plan introduce.
INSERT INTO EQUIPOS (Nombre, Disciplina_ID, Modalidad_ID)
SELECT e.nombre,
       (SELECT ID FROM DISCIPLINA WHERE Nombre = 'Fútbol'),
       (SELECT ID FROM MODALIDAD WHERE Nombre = 'Fútbol 11'
          AND Disciplina_ID = (SELECT ID FROM DISCIPLINA WHERE Nombre = 'Fútbol'))
FROM (VALUES ('Tiburones FC'), ('Águilas del Sur'), ('Halcones United')) AS e(nombre);

-- Jugadores.
-- Cedula/Correo_Electronico son NOT NULL desde este plan (identidad de la
-- persona, no del perfil por disciplina) — datos de prueba, no cédulas
-- reales.
INSERT INTO JUGADORES (Nombre, Cedula, Correo_Electronico) VALUES
    ('Carlos Pérez',   '0900000001', 'carlos.perez@example.com'),
    ('Luis Andrade',   '0900000002', 'luis.andrade@example.com'),
    ('Mateo Salcedo',  '0900000003', 'mateo.salcedo@example.com'),
    ('Diego Ramírez',  '0900000004', 'diego.ramirez@example.com'),
    ('Andrés Vera',    '0900000005', 'andres.vera@example.com'),
    ('Bryan Chávez',   '0900000006', 'bryan.chavez@example.com');

-- Perfiles de jugador por disciplina.
-- Van ANTES que JUGADOR_EQUIPO: el roster ahora referencia el perfil, no
-- al jugador directo (ver 01_schema.sql).
INSERT INTO JUGADOR_PERFIL_DISCIPLINA (Jugador_ID, Disciplina_ID)
SELECT j.ID, (SELECT ID FROM DISCIPLINA WHERE Nombre = 'Fútbol')
  FROM JUGADORES j;

-- Inscripciones al torneo.
-- Van ANTES que los partidos: un partido exige que ambos equipos estén
-- inscritos (lo valida fn_validar_equipos_inscritos en 06_triggers.sql).
-- También son el ancla del roster que usa JUGADOR_EQUIPO abajo.
INSERT INTO INSCRIPCIONES_TORNEO (Torneo_ID, Equipo_ID) VALUES
    (1, 1),
    (1, 2),
    (1, 3);

-- Jugador_Equipo (plantillas): perfil de disciplina + roster del torneo.
-- Van ANTES que los eventos: un evento exige que el jugador perteneciera
-- a ese equipo en la fecha del partido (fn_validar_jugador_partido).
INSERT INTO JUGADOR_EQUIPO (Jugador_Perfil_ID, Inscripcion_Torneo_ID, Dorsal, Fecha_Inicio) VALUES
    ((SELECT ID FROM JUGADOR_PERFIL_DISCIPLINA WHERE Jugador_ID = 1), (SELECT ID FROM INSCRIPCIONES_TORNEO WHERE Torneo_ID = 1 AND Equipo_ID = 1), 10, '2026-01-01'),
    ((SELECT ID FROM JUGADOR_PERFIL_DISCIPLINA WHERE Jugador_ID = 2), (SELECT ID FROM INSCRIPCIONES_TORNEO WHERE Torneo_ID = 1 AND Equipo_ID = 1), 7,  '2026-01-01'),
    ((SELECT ID FROM JUGADOR_PERFIL_DISCIPLINA WHERE Jugador_ID = 3), (SELECT ID FROM INSCRIPCIONES_TORNEO WHERE Torneo_ID = 1 AND Equipo_ID = 2), 9,  '2026-01-01'),
    ((SELECT ID FROM JUGADOR_PERFIL_DISCIPLINA WHERE Jugador_ID = 4), (SELECT ID FROM INSCRIPCIONES_TORNEO WHERE Torneo_ID = 1 AND Equipo_ID = 2), 5,  '2026-01-01'),
    ((SELECT ID FROM JUGADOR_PERFIL_DISCIPLINA WHERE Jugador_ID = 5), (SELECT ID FROM INSCRIPCIONES_TORNEO WHERE Torneo_ID = 1 AND Equipo_ID = 3), 11, '2026-01-01'),
    ((SELECT ID FROM JUGADOR_PERFIL_DISCIPLINA WHERE Jugador_ID = 6), (SELECT ID FROM INSCRIPCIONES_TORNEO WHERE Torneo_ID = 1 AND Equipo_ID = 3), 4,  '2026-01-01');

-- Motor de Formatos (motor-formatos-plantillas-navegacion-plan.md,
-- requerimiento #4): todo torneo tiene una FASE por defecto (Decisión
-- G1). El seed no pasa por TorneoService.create (que la arma sola para
-- cada torneo nuevo) — se crea a mano acá, mismo criterio. Copa Ecotec
-- 2026 es Formato='Liga' (default de TORNEO), 'En_Curso' porque ya tiene
-- partidos con resultado.
INSERT INTO FASE (Torneo_ID, Nombre, Tipo, Orden, Estado) VALUES
    (1, 'Liga Regular', 'Liga', 1, 'En_Curso');

-- Partidos
INSERT INTO PARTIDOS (Torneo_ID, EQUIPOS_ID_LOCAL, EQUIPOS_ID_VISITANTE, Fecha_Partido, Jornada, Estado, Fase_ID) VALUES
    (1, 1, 2, '2026-01-15 16:00:00', 1, 'Finalizado', (SELECT ID FROM FASE WHERE Torneo_ID = 1 AND Orden = 1)),
    (1, 2, 3, '2026-01-22 16:00:00', 2, 'Finalizado', (SELECT ID FROM FASE WHERE Torneo_ID = 1 AND Orden = 1)),
    (1, 3, 1, '2026-01-29 16:00:00', 3, 'Programado', (SELECT ID FROM FASE WHERE Torneo_ID = 1 AND Orden = 1));

-- Eventos del partido 1 (Tiburones vs Águilas).
-- EQUIPO_ID es obligatorio: es el equipo del jugador en ese partido.
INSERT INTO EVENTOS_PARTIDO (PARTIDOS_ID, JUGADOR_ID, EQUIPO_ID, EVENTOS_ID, MINUTO) VALUES
    (1, 1, 1, (SELECT ID FROM EVENTOS WHERE Nombre = 'Gol'), 23),               -- Gol de Carlos Pérez (Tiburones)
    (1, 3, 2, (SELECT ID FROM EVENTOS WHERE Nombre = 'Gol'), 55),               -- Gol de Mateo Salcedo (Águilas)
    (1, 2, 1, (SELECT ID FROM EVENTOS WHERE Nombre = 'Tarjeta Amarilla'), 70);  -- Amarilla a Luis Andrade

-- Eventos del partido 2 (Águilas vs Halcones)
INSERT INTO EVENTOS_PARTIDO (PARTIDOS_ID, JUGADOR_ID, EQUIPO_ID, EVENTOS_ID, MINUTO) VALUES
    (2, 5, 3, (SELECT ID FROM EVENTOS WHERE Nombre = 'Gol'), 12),  -- Gol de Andrés Vera (Halcones)
    (2, 3, 2, (SELECT ID FROM EVENTOS WHERE Nombre = 'Gol'), 40);  -- Gol de Mateo Salcedo (Águilas)
