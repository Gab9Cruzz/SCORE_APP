-- ============================================================
-- seed_portal_demo.sql
-- "Hello world" del Portal Público (portal-publico-feed-partidos-plan.md,
-- F1): sin esto, un dev que clona el repo, corre las migraciones y abre
-- "/" ve una página en blanco y no puede distinguir "lo implementé mal"
-- de "no hay partidos para hoy" — el tiempo-hasta-hello-world de esta
-- feature quedaba indefinido, no lento.
--
-- Crea 2 torneos publicados de 2 disciplinas (Fútbol, Baloncesto) con
-- partidos en CURRENT_DATE cubriendo los 3 estados visibles del feed
-- (D2): Programado, En curso, Finalizado. Requiere que 11_catalogo_-
-- disciplinas.sql (Baloncesto + su modalidad) y 31_migracion_portal_-
-- publico.sql (Publicado, Slug) ya hayan corrido.
--
-- Idempotente: cada INSERT chequea si ya existe antes de crear (mismo
-- patrón que 10_demo_torneos_admin.sql), pero los partidos se re-crean
-- cada corrida con la fecha de HOY — si corriste esto ayer, "hoy" movió
-- la ventana y los partidos viejos quedarían fuera del feed disfrazados
-- de "no hay nada". Se hace DELETE + INSERT de los 6 partidos de este
-- seed en cada corrida, identificados por Torneo_ID (exclusivos de este
-- seed, no toca partidos de otro origen).
--
-- Uso: correr contra un entorno de desarrollo, cuantas veces haga falta
-- (ej. cada mañana antes de abrir "/").
-- ============================================================

-- ------------------------------------------------------------
-- Torneo 1 — Fútbol
-- ------------------------------------------------------------
INSERT INTO TORNEO_GRUPO (Nombre)
SELECT 'Liga Demo Portal Público' WHERE NOT EXISTS (
    SELECT 1 FROM TORNEO_GRUPO WHERE Nombre = 'Liga Demo Portal Público'
);
UPDATE TORNEO_GRUPO SET Pais = 'Ecuador' WHERE Nombre = 'Liga Demo Portal Público' AND Pais IS NULL;

INSERT INTO TORNEO (Nombre, Disciplina_ID, Modalidad_ID, Torneo_Grupo_ID, Numero_Edicion, Fecha_Inicio, Fecha_Fin, Publicado)
SELECT
    'Liga Demo Portal Público - Edición 1',
    (SELECT ID FROM DISCIPLINA WHERE Nombre ILIKE 'f_tbol' LIMIT 1),
    (SELECT m.ID FROM MODALIDAD m WHERE m.Nombre = 'Fútbol 11'
        AND m.Disciplina_ID = (SELECT ID FROM DISCIPLINA WHERE Nombre ILIKE 'f_tbol' LIMIT 1)),
    (SELECT ID FROM TORNEO_GRUPO WHERE Nombre = 'Liga Demo Portal Público'),
    1, CURRENT_DATE - 30, CURRENT_DATE + 30, TRUE
 WHERE NOT EXISTS (
     SELECT 1 FROM TORNEO
      WHERE Torneo_Grupo_ID = (SELECT ID FROM TORNEO_GRUPO WHERE Nombre = 'Liga Demo Portal Público') AND Numero_Edicion = 1
 );
UPDATE TORNEO SET Publicado = TRUE
 WHERE Torneo_Grupo_ID = (SELECT ID FROM TORNEO_GRUPO WHERE Nombre = 'Liga Demo Portal Público') AND Numero_Edicion = 1;

INSERT INTO EQUIPOS (Nombre, Disciplina_ID, Modalidad_ID)
SELECT v.nombre, (SELECT ID FROM DISCIPLINA WHERE Nombre ILIKE 'f_tbol' LIMIT 1),
       (SELECT m.ID FROM MODALIDAD m WHERE m.Nombre = 'Fútbol 11'
           AND m.Disciplina_ID = (SELECT ID FROM DISCIPLINA WHERE Nombre ILIKE 'f_tbol' LIMIT 1))
  FROM (VALUES ('Demo FC Norte'), ('Demo FC Centro'), ('Demo FC Sur')) AS v(nombre)
 WHERE NOT EXISTS (SELECT 1 FROM EQUIPOS WHERE Nombre = v.nombre);

INSERT INTO INSCRIPCIONES_TORNEO (Torneo_ID, Equipo_ID)
SELECT (SELECT t.ID FROM TORNEO t JOIN TORNEO_GRUPO g ON g.ID = t.Torneo_Grupo_ID
         WHERE g.Nombre = 'Liga Demo Portal Público' AND t.Numero_Edicion = 1),
       e.ID
  FROM EQUIPOS e WHERE e.Nombre IN ('Demo FC Norte', 'Demo FC Centro', 'Demo FC Sur')
   AND NOT EXISTS (
       SELECT 1 FROM INSCRIPCIONES_TORNEO i
        WHERE i.Torneo_ID = (SELECT t.ID FROM TORNEO t JOIN TORNEO_GRUPO g ON g.ID = t.Torneo_Grupo_ID
                               WHERE g.Nombre = 'Liga Demo Portal Público' AND t.Numero_Edicion = 1)
          AND i.Equipo_ID = e.ID
   );

DELETE FROM PARTIDOS WHERE Torneo_ID = (
    SELECT t.ID FROM TORNEO t JOIN TORNEO_GRUPO g ON g.ID = t.Torneo_Grupo_ID
     WHERE g.Nombre = 'Liga Demo Portal Público' AND t.Numero_Edicion = 1
);
INSERT INTO PARTIDOS (Torneo_ID, Equipos_ID_Local, Equipos_ID_Visitante, Fecha_Partido, Estado)
SELECT
    (SELECT t.ID FROM TORNEO t JOIN TORNEO_GRUPO g ON g.ID = t.Torneo_Grupo_ID
      WHERE g.Nombre = 'Liga Demo Portal Público' AND t.Numero_Edicion = 1),
    (SELECT ID FROM EQUIPOS WHERE Nombre = v.local),
    (SELECT ID FROM EQUIPOS WHERE Nombre = v.visitante),
    CURRENT_DATE + v.hora,
    v.estado
  FROM (VALUES
      ('Demo FC Norte', 'Demo FC Centro', TIME '20:00', 'Programado'),
      ('Demo FC Centro', 'Demo FC Sur',   TIME '12:00', 'En curso'),
      ('Demo FC Sur',    'Demo FC Norte', TIME '09:00', 'Finalizado')
  ) AS v(local, visitante, hora, estado);

-- ------------------------------------------------------------
-- Torneo 2 — Baloncesto (requiere 11_catalogo_disciplinas.sql)
-- ------------------------------------------------------------
INSERT INTO TORNEO_GRUPO (Nombre)
SELECT 'Liga Demo Básquet Portal Público' WHERE NOT EXISTS (
    SELECT 1 FROM TORNEO_GRUPO WHERE Nombre = 'Liga Demo Básquet Portal Público'
);
UPDATE TORNEO_GRUPO SET Pais = 'Ecuador' WHERE Nombre = 'Liga Demo Básquet Portal Público' AND Pais IS NULL;

INSERT INTO TORNEO (Nombre, Disciplina_ID, Modalidad_ID, Torneo_Grupo_ID, Numero_Edicion, Fecha_Inicio, Fecha_Fin, Publicado)
SELECT
    'Liga Demo Básquet Portal Público - Edición 1',
    (SELECT ID FROM DISCIPLINA WHERE Nombre = 'Baloncesto'),
    (SELECT m.ID FROM MODALIDAD m WHERE m.Nombre = 'Tradicional'
        AND m.Disciplina_ID = (SELECT ID FROM DISCIPLINA WHERE Nombre = 'Baloncesto')),
    (SELECT ID FROM TORNEO_GRUPO WHERE Nombre = 'Liga Demo Básquet Portal Público'),
    1, CURRENT_DATE - 30, CURRENT_DATE + 30, TRUE
 WHERE EXISTS (SELECT 1 FROM DISCIPLINA WHERE Nombre = 'Baloncesto')
   AND NOT EXISTS (
     SELECT 1 FROM TORNEO
      WHERE Torneo_Grupo_ID = (SELECT ID FROM TORNEO_GRUPO WHERE Nombre = 'Liga Demo Básquet Portal Público') AND Numero_Edicion = 1
 );
UPDATE TORNEO SET Publicado = TRUE
 WHERE Torneo_Grupo_ID = (SELECT ID FROM TORNEO_GRUPO WHERE Nombre = 'Liga Demo Básquet Portal Público') AND Numero_Edicion = 1;

INSERT INTO EQUIPOS (Nombre, Disciplina_ID, Modalidad_ID)
SELECT v.nombre, (SELECT ID FROM DISCIPLINA WHERE Nombre = 'Baloncesto'),
       (SELECT m.ID FROM MODALIDAD m WHERE m.Nombre = 'Tradicional'
           AND m.Disciplina_ID = (SELECT ID FROM DISCIPLINA WHERE Nombre = 'Baloncesto'))
  FROM (VALUES ('Demo Basket Este'), ('Demo Basket Oeste'), ('Demo Basket Valle')) AS v(nombre)
 WHERE EXISTS (SELECT 1 FROM DISCIPLINA WHERE Nombre = 'Baloncesto')
   AND NOT EXISTS (SELECT 1 FROM EQUIPOS WHERE Nombre = v.nombre);

INSERT INTO INSCRIPCIONES_TORNEO (Torneo_ID, Equipo_ID)
SELECT (SELECT t.ID FROM TORNEO t JOIN TORNEO_GRUPO g ON g.ID = t.Torneo_Grupo_ID
         WHERE g.Nombre = 'Liga Demo Básquet Portal Público' AND t.Numero_Edicion = 1),
       e.ID
  FROM EQUIPOS e WHERE e.Nombre IN ('Demo Basket Este', 'Demo Basket Oeste', 'Demo Basket Valle')
   AND NOT EXISTS (
       SELECT 1 FROM INSCRIPCIONES_TORNEO i
        WHERE i.Torneo_ID = (SELECT t.ID FROM TORNEO t JOIN TORNEO_GRUPO g ON g.ID = t.Torneo_Grupo_ID
                               WHERE g.Nombre = 'Liga Demo Básquet Portal Público' AND t.Numero_Edicion = 1)
          AND i.Equipo_ID = e.ID
   );

DELETE FROM PARTIDOS WHERE Torneo_ID = (
    SELECT t.ID FROM TORNEO t JOIN TORNEO_GRUPO g ON g.ID = t.Torneo_Grupo_ID
     WHERE g.Nombre = 'Liga Demo Básquet Portal Público' AND t.Numero_Edicion = 1
);
INSERT INTO PARTIDOS (Torneo_ID, Equipos_ID_Local, Equipos_ID_Visitante, Fecha_Partido, Estado)
SELECT
    (SELECT t.ID FROM TORNEO t JOIN TORNEO_GRUPO g ON g.ID = t.Torneo_Grupo_ID
      WHERE g.Nombre = 'Liga Demo Básquet Portal Público' AND t.Numero_Edicion = 1),
    (SELECT ID FROM EQUIPOS WHERE Nombre = v.local),
    (SELECT ID FROM EQUIPOS WHERE Nombre = v.visitante),
    CURRENT_DATE + v.hora,
    v.estado
  FROM (VALUES
      ('Demo Basket Este',  'Demo Basket Oeste', TIME '21:00', 'Programado'),
      ('Demo Basket Oeste', 'Demo Basket Valle', TIME '13:00', 'En curso'),
      ('Demo Basket Valle', 'Demo Basket Este',  TIME '10:00', 'Finalizado')
  ) AS v(local, visitante, hora, estado)
 WHERE EXISTS (
     SELECT 1 FROM TORNEO t JOIN TORNEO_GRUPO g ON g.ID = t.Torneo_Grupo_ID
      WHERE g.Nombre = 'Liga Demo Básquet Portal Público' AND t.Numero_Edicion = 1
 );
