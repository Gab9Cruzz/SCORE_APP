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

-- Torneo
INSERT INTO TORNEO (Nombre, Disciplina, Fecha_Inicio, Fecha_Fin) VALUES
    ('Copa Ecotec 2026', 'Fútbol', '2026-01-10', '2026-03-30');

-- Equipos
INSERT INTO EQUIPOS (Nombre) VALUES
    ('Tiburones FC'),
    ('Águilas del Sur'),
    ('Halcones United');

-- Jugadores
INSERT INTO JUGADORES (Nombre) VALUES
    ('Carlos Pérez'),
    ('Luis Andrade'),
    ('Mateo Salcedo'),
    ('Diego Ramírez'),
    ('Andrés Vera'),
    ('Bryan Chávez');

-- Inscripciones al torneo.
-- Van ANTES que los partidos: un partido exige que ambos equipos estén
-- inscritos (lo valida fn_validar_equipos_inscritos en 06_triggers.sql).
INSERT INTO INSCRIPCIONES_TORNEO (Torneo_ID, Equipo_ID) VALUES
    (1, 1),
    (1, 2),
    (1, 3);

-- Jugador_Equipo (plantillas).
-- Van ANTES que los eventos: un evento exige que el jugador perteneciera
-- a ese equipo en la fecha del partido (fn_validar_jugador_partido).
INSERT INTO JUGADOR_EQUIPO (JUGADOR_ID, EQUIPO_ID, Dorsal, Fecha_Inicio) VALUES
    (1, 1, 10, '2026-01-01'),
    (2, 1, 7,  '2026-01-01'),
    (3, 2, 9,  '2026-01-01'),
    (4, 2, 5,  '2026-01-01'),
    (5, 3, 11, '2026-01-01'),
    (6, 3, 4,  '2026-01-01');

-- Partidos
INSERT INTO PARTIDOS (Torneo_ID, EQUIPOS_ID_LOCAL, EQUIPOS_ID_VISITANTE, Fecha_Partido, Jornada, Estado) VALUES
    (1, 1, 2, '2026-01-15 16:00:00', 1, 'Finalizado'),
    (1, 2, 3, '2026-01-22 16:00:00', 2, 'Finalizado'),
    (1, 3, 1, '2026-01-29 16:00:00', 3, 'Programado');

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
