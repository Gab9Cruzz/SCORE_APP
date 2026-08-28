-- ============================================================
-- 10_demo_torneos_admin.sql
-- Datos de DEMOSTRACIÓN para docs/plans/torneos-admin-plan.md — carga el
-- escenario descrito en la sección "Emulación de Datos" del plan:
--
--   Liga Relámpago (Fútbol) con 2 ediciones SUPERPUESTAS en el tiempo:
--     Edición 1 — Halcones FC, Micky dorsal 9, se finaliza durante el
--                 script (dispara fn_cerrar_torneo_libera_jugadores de
--                 verdad, no se hardcodea el estado final).
--     Edición 2 — Tiburones FC, Micky dorsal 21, sigue Activa.
--   Copa Raíces (Tenis, Individual) — 1 edición, Micky con un perfil
--     de disciplina totalmente aislado del de Fútbol.
--
-- Demuestra en datos reales que TORNEO_GRUPO no interfiere con
-- fn_validar_exclusividad_torneo (EC-23 del plan, ver también el test
-- test_ec23_jugador_activo_en_dos_ediciones_del_mismo_grupo_simultaneamente
-- en test_torneo_grupos.py) ni con la agencia libre por torneo (EC-10,
-- equipos-jugadores-plan.md).
--
-- Puramente para tener algo que mostrar en un entorno de desarrollo — la
-- app funciona sin esto. Igual que 09_migracion_torneo_ediciones.sql: sin
-- Alembic, cada INSERT chequea si ya existe antes de crear, así que este
-- script se puede correr más de una vez sin duplicar nada. Uso: correr
-- una sola vez contra torneos_mvp (o cualquier entorno de desarrollo).
-- ============================================================

-- ------------------------------------------------------------
-- PARTE A — Catálogo de Tenis (el seed base solo trae Fútbol)
-- Ya no lleva Tipo (catálogo unificado — Decisión A1 de
-- ediciones-catalogo-disciplinas-plan.md); 11_catalogo_disciplinas.sql
-- también carga Tenis (con Singles/Dobles), así que en una base que ya
-- corrió ese script esto es un no-op por el WHERE NOT EXISTS.
-- ------------------------------------------------------------
INSERT INTO DISCIPLINA (Nombre)
SELECT 'Tenis'
 WHERE NOT EXISTS (SELECT 1 FROM DISCIPLINA WHERE Nombre = 'Tenis');

INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT (SELECT ID FROM DISCIPLINA WHERE Nombre = 'Tenis'), 'Individual', 1
 WHERE NOT EXISTS (
     SELECT 1 FROM MODALIDAD
      WHERE Nombre = 'Individual' AND Disciplina_ID = (SELECT ID FROM DISCIPLINA WHERE Nombre = 'Tenis')
 );

-- ------------------------------------------------------------
-- PARTE B — Liga Relámpago: grupo + 2 ediciones superpuestas
--
-- La disciplina "Fútbol" en esta base puede estar cargada como "Futbol"
-- (sin tilde, dato viejo) o "Fútbol" (05_seed.sql actual) — ILIKE con
-- '_' matchea cualquiera de las dos sin duplicar el catálogo.
--
-- Modalidad_ID es NOT NULL (catálogo unificado) — se asigna "Fútbol 11"
-- por el mismo criterio de backfill que Copa Ecotec 2026 en 05_seed.sql.
-- ------------------------------------------------------------
INSERT INTO TORNEO_GRUPO (Nombre)
SELECT 'Liga Relámpago' WHERE NOT EXISTS (SELECT 1 FROM TORNEO_GRUPO WHERE Nombre = 'Liga Relámpago');

INSERT INTO TORNEO (Nombre, Disciplina_ID, Modalidad_ID, Torneo_Grupo_ID, Numero_Edicion, Fecha_Inicio, Fecha_Fin)
SELECT
    'Liga Relámpago - Edición 1',
    (SELECT ID FROM DISCIPLINA WHERE Nombre ILIKE 'f_tbol' LIMIT 1),
    (SELECT m.ID FROM MODALIDAD m WHERE m.Nombre = 'Fútbol 11' AND m.Disciplina_ID = (SELECT ID FROM DISCIPLINA WHERE Nombre ILIKE 'f_tbol' LIMIT 1)),
    (SELECT ID FROM TORNEO_GRUPO WHERE Nombre = 'Liga Relámpago'),
    1, '2026-03-01', '2026-05-15'
 WHERE NOT EXISTS (
     SELECT 1 FROM TORNEO
      WHERE Torneo_Grupo_ID = (SELECT ID FROM TORNEO_GRUPO WHERE Nombre = 'Liga Relámpago') AND Numero_Edicion = 1
 );

INSERT INTO TORNEO (Nombre, Disciplina_ID, Modalidad_ID, Torneo_Grupo_ID, Numero_Edicion, Fecha_Inicio, Fecha_Fin)
SELECT
    'Liga Relámpago - Edición 2',
    (SELECT ID FROM DISCIPLINA WHERE Nombre ILIKE 'f_tbol' LIMIT 1),
    (SELECT m.ID FROM MODALIDAD m WHERE m.Nombre = 'Fútbol 11' AND m.Disciplina_ID = (SELECT ID FROM DISCIPLINA WHERE Nombre ILIKE 'f_tbol' LIMIT 1)),
    (SELECT ID FROM TORNEO_GRUPO WHERE Nombre = 'Liga Relámpago'),
    2, '2026-04-01', '2026-06-30'
 WHERE NOT EXISTS (
     SELECT 1 FROM TORNEO
      WHERE Torneo_Grupo_ID = (SELECT ID FROM TORNEO_GRUPO WHERE Nombre = 'Liga Relámpago') AND Numero_Edicion = 2
 );

-- Equipos. "Tiburones FC" puede ya existir (dato histórico del seed base)
-- — se reusa tal cual, es exactamente el punto del catálogo global de
-- EQUIPOS (equipos-jugadores-plan.md, P5): un equipo puede jugar varios
-- torneos distintos a través del tiempo.
--
-- Disciplina_ID/Modalidad_ID son NOT NULL desde
-- equipos-disciplina-navegacion-plan.md, y el equipo tiene que ser de la
-- MISMA disciplina que el torneo al que se lo inscribe más abajo
-- (InscripcionTorneoService lo valida en la API; acá se inserta directo,
-- así que el dato tiene que nacer coherente o el trigger
-- trg_equipos_validar_modalidad lo rechaza).
INSERT INTO EQUIPOS (Nombre, Disciplina_ID, Modalidad_ID)
SELECT 'Halcones FC', (SELECT ID FROM DISCIPLINA WHERE Nombre ILIKE 'f_tbol' LIMIT 1), (SELECT m.ID FROM MODALIDAD m WHERE m.Nombre = 'Fútbol 11'
        AND m.Disciplina_ID = (SELECT ID FROM DISCIPLINA WHERE Nombre ILIKE 'f_tbol' LIMIT 1))
 WHERE NOT EXISTS (SELECT 1 FROM EQUIPOS WHERE Nombre = 'Halcones FC');
INSERT INTO EQUIPOS (Nombre, Disciplina_ID, Modalidad_ID)
SELECT 'Tiburones FC', (SELECT ID FROM DISCIPLINA WHERE Nombre ILIKE 'f_tbol' LIMIT 1), (SELECT m.ID FROM MODALIDAD m WHERE m.Nombre = 'Fútbol 11'
        AND m.Disciplina_ID = (SELECT ID FROM DISCIPLINA WHERE Nombre ILIKE 'f_tbol' LIMIT 1))
 WHERE NOT EXISTS (SELECT 1 FROM EQUIPOS WHERE Nombre = 'Tiburones FC');

INSERT INTO INSCRIPCIONES_TORNEO (Torneo_ID, Equipo_ID)
SELECT
    (SELECT t.ID FROM TORNEO t JOIN TORNEO_GRUPO g ON g.ID = t.Torneo_Grupo_ID WHERE g.Nombre = 'Liga Relámpago' AND t.Numero_Edicion = 1),
    (SELECT ID FROM EQUIPOS WHERE Nombre = 'Halcones FC')
 WHERE NOT EXISTS (
     SELECT 1 FROM INSCRIPCIONES_TORNEO
      WHERE Torneo_ID = (SELECT t.ID FROM TORNEO t JOIN TORNEO_GRUPO g ON g.ID = t.Torneo_Grupo_ID WHERE g.Nombre = 'Liga Relámpago' AND t.Numero_Edicion = 1)
        AND Equipo_ID = (SELECT ID FROM EQUIPOS WHERE Nombre = 'Halcones FC')
 );

INSERT INTO INSCRIPCIONES_TORNEO (Torneo_ID, Equipo_ID)
SELECT
    (SELECT t.ID FROM TORNEO t JOIN TORNEO_GRUPO g ON g.ID = t.Torneo_Grupo_ID WHERE g.Nombre = 'Liga Relámpago' AND t.Numero_Edicion = 2),
    (SELECT ID FROM EQUIPOS WHERE Nombre = 'Tiburones FC')
 WHERE NOT EXISTS (
     SELECT 1 FROM INSCRIPCIONES_TORNEO
      WHERE Torneo_ID = (SELECT t.ID FROM TORNEO t JOIN TORNEO_GRUPO g ON g.ID = t.Torneo_Grupo_ID WHERE g.Nombre = 'Liga Relámpago' AND t.Numero_Edicion = 2)
        AND Equipo_ID = (SELECT ID FROM EQUIPOS WHERE Nombre = 'Tiburones FC')
 );

-- ------------------------------------------------------------
-- PARTE C — Copa Raíces (Tenis, Individual): grupo + 1 edición
-- ------------------------------------------------------------
INSERT INTO TORNEO_GRUPO (Nombre)
SELECT 'Copa Raíces' WHERE NOT EXISTS (SELECT 1 FROM TORNEO_GRUPO WHERE Nombre = 'Copa Raíces');

INSERT INTO TORNEO (Nombre, Disciplina_ID, Modalidad_ID, Torneo_Grupo_ID, Numero_Edicion, Fecha_Inicio, Fecha_Fin)
SELECT
    'Copa Raíces - Edición 1',
    (SELECT ID FROM DISCIPLINA WHERE Nombre = 'Tenis'),
    (SELECT ID FROM MODALIDAD WHERE Nombre = 'Individual' AND Disciplina_ID = (SELECT ID FROM DISCIPLINA WHERE Nombre = 'Tenis')),
    (SELECT ID FROM TORNEO_GRUPO WHERE Nombre = 'Copa Raíces'),
    1, '2026-04-10', '2026-06-20'
 WHERE NOT EXISTS (
     SELECT 1 FROM TORNEO
      WHERE Torneo_Grupo_ID = (SELECT ID FROM TORNEO_GRUPO WHERE Nombre = 'Copa Raíces') AND Numero_Edicion = 1
 );

-- D-Eng-4 del plan: en una disciplina de Tamano_Equipo=1, el "equipo" es
-- el jugador mismo — se nombra igual que él, no se le inventa un nombre
-- de equipo aparte.
INSERT INTO EQUIPOS (Nombre, Disciplina_ID, Modalidad_ID)
SELECT 'Micky Fernández', (SELECT ID FROM DISCIPLINA WHERE Nombre = 'Tenis'), (SELECT ID FROM MODALIDAD WHERE Nombre = 'Individual'
        AND Disciplina_ID = (SELECT ID FROM DISCIPLINA WHERE Nombre = 'Tenis'))
 WHERE NOT EXISTS (SELECT 1 FROM EQUIPOS WHERE Nombre = 'Micky Fernández');

INSERT INTO INSCRIPCIONES_TORNEO (Torneo_ID, Equipo_ID)
SELECT
    (SELECT t.ID FROM TORNEO t JOIN TORNEO_GRUPO g ON g.ID = t.Torneo_Grupo_ID WHERE g.Nombre = 'Copa Raíces' AND t.Numero_Edicion = 1),
    (SELECT ID FROM EQUIPOS WHERE Nombre = 'Micky Fernández')
 WHERE NOT EXISTS (
     SELECT 1 FROM INSCRIPCIONES_TORNEO
      WHERE Torneo_ID = (SELECT t.ID FROM TORNEO t JOIN TORNEO_GRUPO g ON g.ID = t.Torneo_Grupo_ID WHERE g.Nombre = 'Copa Raíces' AND t.Numero_Edicion = 1)
        AND Equipo_ID = (SELECT ID FROM EQUIPOS WHERE Nombre = 'Micky Fernández')
 );

-- ------------------------------------------------------------
-- PARTE D — Micky Fernández: identidad + perfil de Fútbol + perfil de
-- Tenis, completamente aislados (unique_perfil_por_disciplina)
-- ------------------------------------------------------------
INSERT INTO JUGADORES (Nombre, Cedula, Correo_Electronico)
SELECT 'Micky Fernández', '0102030405', 'micky.fernandez@example.com'
 WHERE NOT EXISTS (SELECT 1 FROM JUGADORES WHERE Cedula = '0102030405');

INSERT INTO JUGADOR_PERFIL_DISCIPLINA (Jugador_ID, Disciplina_ID)
SELECT
    (SELECT ID FROM JUGADORES WHERE Cedula = '0102030405'),
    (SELECT ID FROM DISCIPLINA WHERE Nombre ILIKE 'f_tbol' LIMIT 1)
 WHERE NOT EXISTS (
     SELECT 1 FROM JUGADOR_PERFIL_DISCIPLINA
      WHERE Jugador_ID = (SELECT ID FROM JUGADORES WHERE Cedula = '0102030405')
        AND Disciplina_ID = (SELECT ID FROM DISCIPLINA WHERE Nombre ILIKE 'f_tbol' LIMIT 1)
 );

INSERT INTO JUGADOR_PERFIL_DISCIPLINA (Jugador_ID, Disciplina_ID)
SELECT
    (SELECT ID FROM JUGADORES WHERE Cedula = '0102030405'),
    (SELECT ID FROM DISCIPLINA WHERE Nombre = 'Tenis')
 WHERE NOT EXISTS (
     SELECT 1 FROM JUGADOR_PERFIL_DISCIPLINA
      WHERE Jugador_ID = (SELECT ID FROM JUGADORES WHERE Cedula = '0102030405')
        AND Disciplina_ID = (SELECT ID FROM DISCIPLINA WHERE Nombre = 'Tenis')
 );

-- ------------------------------------------------------------
-- PARTE E — Membresías. Halcones FC (Edición 1) se inserta Activo y
-- LUEGO se finaliza el torneo con un UPDATE real (no un INSERT con
-- Estado='Finalizado' directo) para que fn_cerrar_torneo_libera_jugadores
-- (06_triggers.sql) dispare de verdad — la demo muestra el mecanismo
-- funcionando, no un estado final prearmado a mano.
-- ------------------------------------------------------------
INSERT INTO JUGADOR_EQUIPO (Jugador_Perfil_ID, Inscripcion_Torneo_ID, Dorsal, Fecha_Inicio)
SELECT
    (SELECT jpd.ID FROM JUGADOR_PERFIL_DISCIPLINA jpd
      WHERE jpd.Jugador_ID = (SELECT ID FROM JUGADORES WHERE Cedula = '0102030405')
        AND jpd.Disciplina_ID = (SELECT ID FROM DISCIPLINA WHERE Nombre ILIKE 'f_tbol' LIMIT 1)),
    (SELECT it.ID FROM INSCRIPCIONES_TORNEO it
      JOIN TORNEO t ON t.ID = it.Torneo_ID
      JOIN TORNEO_GRUPO g ON g.ID = t.Torneo_Grupo_ID
      WHERE g.Nombre = 'Liga Relámpago' AND t.Numero_Edicion = 1 AND it.Equipo_ID = (SELECT ID FROM EQUIPOS WHERE Nombre = 'Halcones FC')),
    9, '2026-03-01'
 WHERE NOT EXISTS (
     SELECT 1 FROM JUGADOR_EQUIPO je
      WHERE je.Jugador_Perfil_ID = (SELECT jpd.ID FROM JUGADOR_PERFIL_DISCIPLINA jpd
                                       WHERE jpd.Jugador_ID = (SELECT ID FROM JUGADORES WHERE Cedula = '0102030405')
                                         AND jpd.Disciplina_ID = (SELECT ID FROM DISCIPLINA WHERE Nombre ILIKE 'f_tbol' LIMIT 1))
        AND je.Inscripcion_Torneo_ID = (SELECT it.ID FROM INSCRIPCIONES_TORNEO it
                                          JOIN TORNEO t ON t.ID = it.Torneo_ID
                                          JOIN TORNEO_GRUPO g ON g.ID = t.Torneo_Grupo_ID
                                          WHERE g.Nombre = 'Liga Relámpago' AND t.Numero_Edicion = 1 AND it.Equipo_ID = (SELECT ID FROM EQUIPOS WHERE Nombre = 'Halcones FC'))
 );

INSERT INTO JUGADOR_EQUIPO (Jugador_Perfil_ID, Inscripcion_Torneo_ID, Dorsal, Fecha_Inicio)
SELECT
    (SELECT jpd.ID FROM JUGADOR_PERFIL_DISCIPLINA jpd
      WHERE jpd.Jugador_ID = (SELECT ID FROM JUGADORES WHERE Cedula = '0102030405')
        AND jpd.Disciplina_ID = (SELECT ID FROM DISCIPLINA WHERE Nombre ILIKE 'f_tbol' LIMIT 1)),
    (SELECT it.ID FROM INSCRIPCIONES_TORNEO it
      JOIN TORNEO t ON t.ID = it.Torneo_ID
      JOIN TORNEO_GRUPO g ON g.ID = t.Torneo_Grupo_ID
      WHERE g.Nombre = 'Liga Relámpago' AND t.Numero_Edicion = 2 AND it.Equipo_ID = (SELECT ID FROM EQUIPOS WHERE Nombre = 'Tiburones FC')),
    21, '2026-04-01'
 WHERE NOT EXISTS (
     SELECT 1 FROM JUGADOR_EQUIPO je
      WHERE je.Jugador_Perfil_ID = (SELECT jpd.ID FROM JUGADOR_PERFIL_DISCIPLINA jpd
                                       WHERE jpd.Jugador_ID = (SELECT ID FROM JUGADORES WHERE Cedula = '0102030405')
                                         AND jpd.Disciplina_ID = (SELECT ID FROM DISCIPLINA WHERE Nombre ILIKE 'f_tbol' LIMIT 1))
        AND je.Inscripcion_Torneo_ID = (SELECT it.ID FROM INSCRIPCIONES_TORNEO it
                                          JOIN TORNEO t ON t.ID = it.Torneo_ID
                                          JOIN TORNEO_GRUPO g ON g.ID = t.Torneo_Grupo_ID
                                          WHERE g.Nombre = 'Liga Relámpago' AND t.Numero_Edicion = 2 AND it.Equipo_ID = (SELECT ID FROM EQUIPOS WHERE Nombre = 'Tiburones FC'))
 );

INSERT INTO JUGADOR_EQUIPO (Jugador_Perfil_ID, Inscripcion_Torneo_ID, Fecha_Inicio)
SELECT
    (SELECT jpd.ID FROM JUGADOR_PERFIL_DISCIPLINA jpd
      WHERE jpd.Jugador_ID = (SELECT ID FROM JUGADORES WHERE Cedula = '0102030405')
        AND jpd.Disciplina_ID = (SELECT ID FROM DISCIPLINA WHERE Nombre = 'Tenis')),
    (SELECT it.ID FROM INSCRIPCIONES_TORNEO it
      JOIN TORNEO t ON t.ID = it.Torneo_ID
      JOIN TORNEO_GRUPO g ON g.ID = t.Torneo_Grupo_ID
      WHERE g.Nombre = 'Copa Raíces' AND t.Numero_Edicion = 1),
    '2026-04-10'
 WHERE NOT EXISTS (
     SELECT 1 FROM JUGADOR_EQUIPO je
      WHERE je.Jugador_Perfil_ID = (SELECT jpd.ID FROM JUGADOR_PERFIL_DISCIPLINA jpd
                                       WHERE jpd.Jugador_ID = (SELECT ID FROM JUGADORES WHERE Cedula = '0102030405')
                                         AND jpd.Disciplina_ID = (SELECT ID FROM DISCIPLINA WHERE Nombre = 'Tenis'))
        AND je.Inscripcion_Torneo_ID = (SELECT it.ID FROM INSCRIPCIONES_TORNEO it
                                          JOIN TORNEO t ON t.ID = it.Torneo_ID
                                          JOIN TORNEO_GRUPO g ON g.ID = t.Torneo_Grupo_ID
                                          WHERE g.Nombre = 'Copa Raíces' AND t.Numero_Edicion = 1)
 );

-- Finaliza la Edición 1 de verdad — dispara fn_cerrar_torneo_libera_jugadores.
-- El guard "AND Estado <> 'Finalizado'" hace esto idempotente: en una
-- segunda corrida del script, el UPDATE no encuentra filas y el trigger
-- no vuelve a dispararse (no haría nada distinto igual, pero evita un
-- UPDATE de más).
UPDATE TORNEO t
   SET Estado = 'Finalizado'
  FROM TORNEO_GRUPO g
 WHERE g.ID = t.Torneo_Grupo_ID
   AND g.Nombre = 'Liga Relámpago'
   AND t.Numero_Edicion = 1
   AND t.Estado <> 'Finalizado';

-- ------------------------------------------------------------
-- PARTE F — Verificación
-- ------------------------------------------------------------
DO $$
DECLARE
    v_halcones_estado VARCHAR(20);
    v_tiburones_estado VARCHAR(20);
    v_perfil_futbol_estado TEXT;
BEGIN
    SELECT je.Estado INTO v_halcones_estado
      FROM JUGADOR_EQUIPO je
      JOIN INSCRIPCIONES_TORNEO it ON it.ID = je.Inscripcion_Torneo_ID
      JOIN EQUIPOS e ON e.ID = it.Equipo_ID
     WHERE e.Nombre = 'Halcones FC';

    SELECT je.Estado INTO v_tiburones_estado
      FROM JUGADOR_EQUIPO je
      JOIN INSCRIPCIONES_TORNEO it ON it.ID = je.Inscripcion_Torneo_ID
      JOIN EQUIPOS e ON e.ID = it.Equipo_ID
     WHERE e.Nombre = 'Tiburones FC' AND e.ID = (SELECT ID FROM EQUIPOS WHERE Nombre = 'Tiburones FC');

    SELECT vw.Estado INTO v_perfil_futbol_estado
      FROM vw_estado_perfil_disciplina vw
      JOIN JUGADORES j ON j.ID = vw.Jugador_ID
     WHERE j.Cedula = '0102030405' AND vw.Disciplina_ID = (SELECT ID FROM DISCIPLINA WHERE Nombre ILIKE 'f_tbol' LIMIT 1);

    RAISE NOTICE 'Demo cargada. Micky en Halcones FC (Edición 1, finalizada): %. Micky en Tiburones FC (Edición 2, activa): %. Estado del perfil de Fútbol: % (debe ser Activo, no Libre — EC-10).',
        v_halcones_estado, v_tiburones_estado, v_perfil_futbol_estado;

    IF v_perfil_futbol_estado IS DISTINCT FROM 'Activo' THEN
        RAISE WARNING 'El perfil de Fútbol de Micky no quedó Activo tras finalizar la Edición 1 — revisar (se esperaba que la membresía en Tiburones FC / Edición 2 lo mantuviera Activo, EC-10).';
    END IF;
END $$;
