-- ============================================================
-- 11_catalogo_disciplinas.sql
-- Catálogo maestro de disciplinas y modalidades (28 disciplinas / 66
-- modalidades) — docs/plans/ediciones-catalogo-disciplinas-plan.md,
-- D-Eng-8.
--
-- Idempotente: se apoya en unique_disciplina_nombre (DISCIPLINA) y
-- unique_modalidad_por_disciplina (MODALIDAD), ambos ya existentes desde
-- 02_constraints.sql, así que correrlo dos veces no duplica ninguna fila
-- (ON CONFLICT ... DO NOTHING en cada INSERT).
--
-- Cuándo correr esto:
--   - Entorno NUEVO (01_schema.sql en adelante): correr DESPUÉS de
--     06_triggers.sql, en cualquier momento. 05_seed.sql ya carga
--     'Fútbol'/'Fútbol 11' como parte del torneo de demo — este script
--     los vuelve a insertar (no-op por el ON CONFLICT) y agrega las 27
--     disciplinas restantes.
--   - Entorno YA PROVISIONADO (torneos_mvp): NO hace falta correr este
--     archivo — 12_migracion_catalogo_disciplinas.sql es autocontenido y
--     ya incluye este mismo catálogo inline en su Parte B (lo necesita
--     antes de su propio backfill de TORNEO.Modalidad_ID, así que no
--     podía depender de un archivo externo). Correr este 11 igual, antes
--     o después de 12, es inofensivo (mismos INSERT ... ON CONFLICT DO
--     NOTHING) pero redundante.
--
-- No es parte de la secuencia 01-06 (esa es la definición base "desde
-- cero"; el catálogo maestro es infraestructura de referencia que se
-- aplica encima, igual que 07/08/09/10) — ver D-Eng-8.
-- ============================================================

INSERT INTO DISCIPLINA (Nombre) VALUES
    ('Fútbol'), ('Fútbol Americano / Flag Football'),
    ('Baloncesto'), ('Voleibol'), ('Hándbol'), ('Rugby'),
    ('Tenis'), ('Ping Pong'), ('Bádminton'), ('Squash / Racquetball'),
    ('Pickleball'), ('Frontón / Pelota Vasca'),
    ('Atletismo'), ('Natación'), ('Ciclismo'), ('Gimnasia'), ('CrossFit'),
    ('MMA'), ('Boxeo'), ('Judo'), ('Taekwondo'), ('Karate'),
    ('League of Legends'), ('CS:GO'), ('Valorant'), ('Rocket League'),
    ('FIFA / EA FC'), ('Ajedrez')
ON CONFLICT (Nombre) DO NOTHING;

-- Cada bloque abajo resuelve Disciplina_ID por nombre y hace
-- ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING (constraint
-- unique_modalidad_por_disciplina, ya existente desde
-- equipos-jugadores-plan.md).

INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, m.nombre, m.tamano FROM DISCIPLINA d
JOIN (VALUES
    ('Fútbol 11', 11), ('Fútbol 7', 7), ('Fútbol 5', 5), ('Fútsal', 5)
) AS m(nombre, tamano) ON true
WHERE d.Nombre = 'Fútbol'
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, m.nombre, m.tamano FROM DISCIPLINA d
JOIN (VALUES ('5v5', 5), ('7v7 sin contacto', 7)) AS m(nombre, tamano) ON true
WHERE d.Nombre = 'Fútbol Americano / Flag Football'
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, m.nombre, m.tamano FROM DISCIPLINA d
JOIN (VALUES ('Tradicional', 5), ('3x3', 3)) AS m(nombre, tamano) ON true
WHERE d.Nombre = 'Baloncesto'
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, m.nombre, m.tamano FROM DISCIPLINA d
JOIN (VALUES ('Pista 6x6', 6), ('Playa 2x2', 2)) AS m(nombre, tamano) ON true
WHERE d.Nombre = 'Voleibol'
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, m.nombre, m.tamano FROM DISCIPLINA d
JOIN (VALUES ('Pista', 7), ('Playa', 4)) AS m(nombre, tamano) ON true
WHERE d.Nombre = 'Hándbol'
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, m.nombre, m.tamano FROM DISCIPLINA d
JOIN (VALUES ('Rugby 7', 7), ('Rugby 15', 15)) AS m(nombre, tamano) ON true
WHERE d.Nombre = 'Rugby'
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

-- Raqueta y pala: mismo patrón Singles(1)/Dobles(2) para las 5 disciplinas.
INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, m.nombre, m.tamano FROM DISCIPLINA d
JOIN (VALUES ('Singles', 1), ('Dobles', 2)) AS m(nombre, tamano) ON true
WHERE d.Nombre IN ('Tenis', 'Ping Pong', 'Bádminton', 'Squash / Racquetball', 'Pickleball')
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, m.nombre, m.tamano FROM DISCIPLINA d
JOIN (VALUES ('Individual', 1), ('Parejas', 2)) AS m(nombre, tamano) ON true
WHERE d.Nombre = 'Frontón / Pelota Vasca'
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

-- Marcas y tiempos: todas Tamano_Equipo=1 (individual, sin excepción).
INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, m.nombre, 1 FROM DISCIPLINA d
JOIN (VALUES ('100m'), ('5K'), ('10K'), ('Maratón')) AS m(nombre) ON true
WHERE d.Nombre = 'Atletismo'
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, m.nombre, 1 FROM DISCIPLINA d
JOIN (VALUES ('Libre'), ('Espalda'), ('Pecho'), ('Mariposa')) AS m(nombre) ON true
WHERE d.Nombre = 'Natación'
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, m.nombre, 1 FROM DISCIPLINA d
JOIN (VALUES ('Ruta'), ('MTB'), ('BMX'), ('Velódromo')) AS m(nombre) ON true
WHERE d.Nombre = 'Ciclismo'
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, m.nombre, 1 FROM DISCIPLINA d
JOIN (VALUES ('Artística'), ('Rítmica'), ('Trampolín')) AS m(nombre) ON true
WHERE d.Nombre = 'Gimnasia'
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, 'WODs', 1 FROM DISCIPLINA d WHERE d.Nombre = 'CrossFit'
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

-- Combate: 3 categorías genéricas de peso por disciplina (ver EC-32 —
-- placeholder editable-por-migración, no la tabla oficial de una
-- federación específica).
INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, m.nombre, 1 FROM DISCIPLINA d
JOIN (VALUES ('Peso Ligero'), ('Peso Medio'), ('Peso Pesado')) AS m(nombre) ON true
WHERE d.Nombre IN ('MMA', 'Boxeo', 'Judo', 'Taekwondo', 'Karate')
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

-- eSports y estrategia.
INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, '5v5', 5 FROM DISCIPLINA d
WHERE d.Nombre IN ('League of Legends', 'CS:GO', 'Valorant')
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, '3v3', 3 FROM DISCIPLINA d WHERE d.Nombre = 'Rocket League'
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, m.nombre, m.tamano FROM DISCIPLINA d
JOIN (VALUES ('1v1', 1), ('2v2', 2)) AS m(nombre, tamano) ON true
WHERE d.Nombre = 'FIFA / EA FC'
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

INSERT INTO MODALIDAD (Disciplina_ID, Nombre, Tamano_Equipo)
SELECT d.ID, m.nombre, 1 FROM DISCIPLINA d
JOIN (VALUES ('Clásico'), ('Rápido'), ('Blitz')) AS m(nombre) ON true
WHERE d.Nombre = 'Ajedrez'
ON CONFLICT (Disciplina_ID, Nombre) DO NOTHING;

-- ------------------------------------------------------------
-- Verificación final
-- ------------------------------------------------------------
DO $$
DECLARE
    v_disciplinas INT;
    v_modalidades INT;
BEGIN
    SELECT COUNT(*) INTO v_disciplinas FROM DISCIPLINA;
    SELECT COUNT(*) INTO v_modalidades FROM MODALIDAD;
    RAISE NOTICE 'Catalogo de disciplinas aplicado: % disciplina(s), % modalidad(es) en total (esperado: 28 y 66 si esta es la unica fuente de datos).', v_disciplinas, v_modalidades;
END $$;
