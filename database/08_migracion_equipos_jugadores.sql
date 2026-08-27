-- ============================================================
-- 08_migracion_equipos_jugadores.sql
-- Migración puntual para una base YA provisionada (torneos_mvp): aplica el
-- módulo de equipos-jugadores-plan.md — catálogo de disciplina/modalidad,
-- perfiles de jugador por disciplina, exclusividad por torneo, traspasos.
-- No es parte de la secuencia 01-06 (esa sigue siendo la definición
-- "desde cero" — ver 01_schema.sql, ya actualizado con el estado final).
--
-- Mismo criterio que 07_migracion_roles_arbitro.sql: sin Alembic en este
-- proyecto, y este script SÍ se puede correr más de una vez sin romper
-- nada — cada paso chequea si ya se aplicó antes de tocar el esquema o
-- de re-backfillear filas ya migradas.
--
-- Orden del archivo (importa — cada parte depende de la anterior):
--   A. Catálogo DISCIPLINA/MODALIDAD + backfill desde TORNEO.Disciplina
--   B. TORNEO: Disciplina_ID/Modalidad_ID (reemplaza el texto libre)
--   C. JUGADORES: Cedula/Correo_Electronico
--   D. JUGADOR_PERFIL_DISCIPLINA (nueva tabla) + backfill
--   E. JUGADOR_EQUIPO: reestructurar a (Jugador_Perfil_ID, Inscripcion_Torneo_ID)
--   F. TRASPASOS (nueva tabla, sin backfill — no hay traspasos históricos)
--   G. Triggers nuevos (se crean al final, después de todo backfill —
--      mismo motivo que 06_triggers.sql: no deben disparar sobre datos
--      viejos a mitad de migración)
--   H. Vistas nuevas
--   I. Verificación final
--
-- Uso: correr una sola vez contra torneos_mvp (o cualquier base que ya
-- tenga datos con el esquema viejo). Un entorno nuevo NO necesita esto —
-- nace correcto directamente desde 01-06.
-- ============================================================

-- ------------------------------------------------------------
-- PARTE A — Catálogo de disciplinas y modalidades
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS DISCIPLINA (
    ID SERIAL PRIMARY KEY,
    Nombre VARCHAR(50) NOT NULL,
    Tipo VARCHAR(20) NOT NULL,
    Estado VARCHAR(20) DEFAULT 'Activo'
);

CREATE TABLE IF NOT EXISTS MODALIDAD (
    ID SERIAL PRIMARY KEY,
    Disciplina_ID INT NOT NULL,
    Nombre VARCHAR(30) NOT NULL,
    Tamano_Equipo INT NOT NULL,
    Estado VARCHAR(20) DEFAULT 'Activo'
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'unique_disciplina_nombre') THEN
        ALTER TABLE DISCIPLINA ADD CONSTRAINT unique_disciplina_nombre UNIQUE (Nombre);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_disciplina_tipo') THEN
        ALTER TABLE DISCIPLINA ADD CONSTRAINT chk_disciplina_tipo CHECK (Tipo IN ('Equipo', 'Individual'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_disciplina_estado') THEN
        ALTER TABLE DISCIPLINA ADD CONSTRAINT chk_disciplina_estado CHECK (Estado IN ('Activo', 'Inactivo'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_modalidad_disciplina') THEN
        ALTER TABLE MODALIDAD ADD CONSTRAINT fk_modalidad_disciplina FOREIGN KEY (Disciplina_ID) REFERENCES DISCIPLINA(ID) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_modalidad_tamano') THEN
        ALTER TABLE MODALIDAD ADD CONSTRAINT chk_modalidad_tamano CHECK (Tamano_Equipo > 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_modalidad_estado') THEN
        ALTER TABLE MODALIDAD ADD CONSTRAINT chk_modalidad_estado CHECK (Estado IN ('Activo', 'Inactivo'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'unique_modalidad_por_disciplina') THEN
        ALTER TABLE MODALIDAD ADD CONSTRAINT unique_modalidad_por_disciplina UNIQUE (Disciplina_ID, Nombre);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_modalidad_disciplina ON MODALIDAD(Disciplina_ID);

-- Backfill: un valor DISCIPLINA por cada texto distinto que ya exista en
-- TORNEO.Disciplina. Tipo='Equipo' es un default seguro (es lo que hay
-- hoy: 'Fútbol') — si esta base ya tiene disciplinas individuales
-- (Tenis, Pádel) cargadas como texto libre, revisar manualmente después
-- y corregir Tipo a 'Individual' + crear su(s) MODALIDAD antes de que
-- algún TORNEO de esa disciplina dependa de Modalidad_ID.
-- Todo este bloque usa SQL dinámico (EXECUTE) guardado por un chequeo de
-- information_schema: TORNEO.Disciplina (texto) se dropea más abajo, así
-- que en una segunda corrida del script (idempotencia) la columna ya no
-- existe — una referencia ESTÁTICA a t.Disciplina fallaría en el parseo
-- del bloque entero, no solo en tiempo de ejecución del IF.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'torneo' AND column_name = 'disciplina'
    ) THEN
        EXECUTE $sql$
            INSERT INTO DISCIPLINA (Nombre, Tipo)
            SELECT DISTINCT t.Disciplina, 'Equipo'
              FROM TORNEO t
             WHERE t.Disciplina IS NOT NULL
               AND NOT EXISTS (SELECT 1 FROM DISCIPLINA d WHERE d.Nombre = t.Disciplina)
        $sql$;
    END IF;
END $$;

DO $$
DECLARE
    v_individuales INT;
BEGIN
    SELECT COUNT(*) INTO v_individuales FROM DISCIPLINA WHERE Tipo = 'Individual';
    IF v_individuales = 0 THEN
        RAISE NOTICE 'DISCIPLINA backfilleada solo con Tipo=Equipo (default). Si esta base maneja disciplinas individuales (Tenis, Pádel), revisar y corregir Tipo manualmente.';
    END IF;
END $$;

-- ------------------------------------------------------------
-- PARTE B — TORNEO: Disciplina_ID/Modalidad_ID reemplazan el texto libre
-- ------------------------------------------------------------
ALTER TABLE TORNEO ADD COLUMN IF NOT EXISTS Disciplina_ID INT;
ALTER TABLE TORNEO ADD COLUMN IF NOT EXISTS Modalidad_ID INT;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'torneo' AND column_name = 'disciplina'
    ) THEN
        EXECUTE $sql$
            UPDATE TORNEO t
               SET Disciplina_ID = d.ID
              FROM DISCIPLINA d
             WHERE d.Nombre = t.Disciplina
               AND t.Disciplina_ID IS NULL
        $sql$;
    END IF;
END $$;

DO $$
DECLARE
    v_sin_disciplina INT;
BEGIN
    SELECT COUNT(*) INTO v_sin_disciplina FROM TORNEO WHERE Disciplina_ID IS NULL;
    IF v_sin_disciplina > 0 THEN
        RAISE EXCEPTION '% torneo(s) sin Disciplina_ID resuelto tras el backfill — revisar TORNEO.Disciplina antes de continuar.', v_sin_disciplina;
    END IF;
END $$;

ALTER TABLE TORNEO ALTER COLUMN Disciplina_ID SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_torneo_disciplina') THEN
        ALTER TABLE TORNEO ADD CONSTRAINT fk_torneo_disciplina FOREIGN KEY (Disciplina_ID) REFERENCES DISCIPLINA(ID);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_torneo_modalidad') THEN
        ALTER TABLE TORNEO ADD CONSTRAINT fk_torneo_modalidad FOREIGN KEY (Modalidad_ID) REFERENCES MODALIDAD(ID);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_torneo_disciplina ON TORNEO(Disciplina_ID);
CREATE INDEX IF NOT EXISTS idx_torneo_modalidad ON TORNEO(Modalidad_ID);

-- La columna vieja ya no hace falta: todo lo que la usaba (JUGADOR_PERFIL_DISCIPLINA
-- en la Parte D) lee Disciplina_ID de acá en adelante.
ALTER TABLE TORNEO DROP COLUMN IF EXISTS Disciplina;

-- ------------------------------------------------------------
-- PARTE C — JUGADORES: Cedula / Correo_Electronico
-- ------------------------------------------------------------
ALTER TABLE JUGADORES ADD COLUMN IF NOT EXISTS Cedula VARCHAR(20);
ALTER TABLE JUGADORES ADD COLUMN IF NOT EXISTS Correo_Electronico VARCHAR(150);

-- Placeholder para filas existentes: esta base no tenía cédula real antes
-- de este plan (P1 del plan lo marca como "bloqueante de implementación,
-- no de este plan"). El placeholder es único por construcción (usa el ID)
-- así que no rompe el UNIQUE que se agrega abajo, pero SIGUE PENDIENTE
-- capturar la cédula real de cada jugador — ver el aviso en la
-- verificación final.
UPDATE JUGADORES
   SET Cedula = 'PENDIENTE-' || ID::text
 WHERE Cedula IS NULL;

UPDATE JUGADORES
   SET Correo_Electronico = 'pendiente+jugador' || ID::text || '@torneos.local'
 WHERE Correo_Electronico IS NULL;

ALTER TABLE JUGADORES ALTER COLUMN Cedula SET NOT NULL;
ALTER TABLE JUGADORES ALTER COLUMN Correo_Electronico SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'unique_jugador_cedula') THEN
        ALTER TABLE JUGADORES ADD CONSTRAINT unique_jugador_cedula UNIQUE (Cedula);
    END IF;
END $$;

-- ------------------------------------------------------------
-- PARTE D — JUGADOR_PERFIL_DISCIPLINA (nueva tabla)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS JUGADOR_PERFIL_DISCIPLINA (
    ID SERIAL PRIMARY KEY,
    Jugador_ID INT NOT NULL,
    Disciplina_ID INT NOT NULL,
    Suspendido BOOLEAN NOT NULL DEFAULT FALSE,
    Fecha_Registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Fecha_Modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_perfil_disciplina_jugador') THEN
        ALTER TABLE JUGADOR_PERFIL_DISCIPLINA ADD CONSTRAINT fk_perfil_disciplina_jugador FOREIGN KEY (Jugador_ID) REFERENCES JUGADORES(ID) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_perfil_disciplina_disciplina') THEN
        ALTER TABLE JUGADOR_PERFIL_DISCIPLINA ADD CONSTRAINT fk_perfil_disciplina_disciplina FOREIGN KEY (Disciplina_ID) REFERENCES DISCIPLINA(ID);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'unique_perfil_por_disciplina') THEN
        ALTER TABLE JUGADOR_PERFIL_DISCIPLINA ADD CONSTRAINT unique_perfil_por_disciplina UNIQUE (Jugador_ID, Disciplina_ID);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_perfil_disciplina_jugador ON JUGADOR_PERFIL_DISCIPLINA(Jugador_ID);
CREATE INDEX IF NOT EXISTS idx_perfil_disciplina_disciplina ON JUGADOR_PERFIL_DISCIPLINA(Disciplina_ID);

DROP TRIGGER IF EXISTS trg_perfil_disciplina_upd_fecha ON JUGADOR_PERFIL_DISCIPLINA;
CREATE TRIGGER trg_perfil_disciplina_upd_fecha
BEFORE UPDATE ON JUGADOR_PERFIL_DISCIPLINA
FOR EACH ROW EXECUTE FUNCTION fn_actualizar_fecha_modificacion();

-- Backfill: un perfil por (persona, disciplina) inferido de las filas
-- JUGADOR_EQUIPO existentes (todavía con JUGADOR_ID/EQUIPO_ID viejos en
-- este punto — se reestructura recién en la Parte E) vía el torneo en el
-- que estaba inscrito ese equipo.
--
-- Igual que en la Parte A/B: JUGADOR_ID/EQUIPO_ID se dropean más abajo,
-- así que en una segunda corrida (idempotencia) ya no existen — todo
-- este bloque (y el de la Parte E que sigue) va en SQL dinámico guardado
-- por information_schema, o el parseo del statement fallaría de entrada
-- en la segunda corrida aunque el IF nunca fuera a ejecutarlo.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'jugador_equipo' AND column_name = 'jugador_id'
    ) THEN
        EXECUTE $sql$
            INSERT INTO JUGADOR_PERFIL_DISCIPLINA (Jugador_ID, Disciplina_ID)
            SELECT DISTINCT je.JUGADOR_ID, t.Disciplina_ID
              FROM JUGADOR_EQUIPO je
              JOIN INSCRIPCIONES_TORNEO it ON it.Equipo_ID = je.EQUIPO_ID
              JOIN TORNEO t ON t.ID = it.Torneo_ID
             WHERE NOT EXISTS (
                    SELECT 1 FROM JUGADOR_PERFIL_DISCIPLINA jpd
                     WHERE jpd.Jugador_ID = je.JUGADOR_ID AND jpd.Disciplina_ID = t.Disciplina_ID)
        $sql$;
    END IF;
END $$;

-- ------------------------------------------------------------
-- PARTE E — JUGADOR_EQUIPO: (JUGADOR_ID, EQUIPO_ID) -> (Jugador_Perfil_ID, Inscripcion_Torneo_ID)
-- ------------------------------------------------------------
ALTER TABLE JUGADOR_EQUIPO ADD COLUMN IF NOT EXISTS Jugador_Perfil_ID INT;
ALTER TABLE JUGADOR_EQUIPO ADD COLUMN IF NOT EXISTS Inscripcion_Torneo_ID INT;

-- Backfill: por cada fila vieja se resuelve UNA inscripción candidata —
-- el torneo en el que ese EQUIPO_ID estaba inscrito y que no había
-- terminado todavía cuando arrancó la membresía (Fecha_Inicio de
-- JUGADOR_EQUIPO). No se exige que el torneo YA hubiera arrancado: es
-- normal armar el roster antes de la fecha de inicio del torneo (el seed
-- de 05_seed.sql es exactamente ese caso — jugadores desde 2026-01-01,
-- torneo desde 2026-01-10). El esquema viejo nunca distinguía torneo (un
-- equipo podía estar en varios a la vez), así que si hay más de una
-- candidata se toma la de ID de torneo más bajo (la más antigua) y queda
-- registrado en la verificación final para revisión manual — no hay
-- forma automática de saber cuál "quiso decir" el dato viejo.
-- (La condición del JOIN contra JUGADOR_PERFIL_DISCIPLINA no puede vivir
-- en el UPDATE ... FROM directamente: el alias del destino (je) no es
-- visible dentro de un JOIN anidado en la cláusula FROM, solo en el
-- WHERE de nivel superior — por eso jugador_id_orig viaja en la CTE en
-- vez de resolverse contra je ahí adentro.)
DO $$
DECLARE
    v_ambiguos INT;
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'jugador_equipo' AND column_name = 'jugador_id'
    ) THEN
        EXECUTE $sql$
            WITH candidato AS (
                SELECT je.ID AS jugador_equipo_id,
                       je.JUGADOR_ID AS jugador_id_orig,
                       it.ID AS inscripcion_id,
                       t.Disciplina_ID AS disciplina_id,
                       ROW_NUMBER() OVER (PARTITION BY je.ID ORDER BY t.ID) AS rn
                  FROM JUGADOR_EQUIPO je
                  JOIN INSCRIPCIONES_TORNEO it ON it.Equipo_ID = je.EQUIPO_ID
                  JOIN TORNEO t ON t.ID = it.Torneo_ID
                 WHERE je.Inscripcion_Torneo_ID IS NULL
                   AND (t.Fecha_Fin IS NULL OR t.Fecha_Fin >= je.Fecha_Inicio)
            ),
            elegido AS (
                SELECT c.jugador_equipo_id, c.inscripcion_id, jpd.ID AS perfil_id
                  FROM candidato c
                  JOIN JUGADOR_PERFIL_DISCIPLINA jpd
                    ON jpd.Jugador_ID = c.jugador_id_orig AND jpd.Disciplina_ID = c.disciplina_id
                 WHERE c.rn = 1
            )
            UPDATE JUGADOR_EQUIPO je
               SET Inscripcion_Torneo_ID = e.inscripcion_id,
                   Jugador_Perfil_ID = e.perfil_id
              FROM elegido e
             WHERE e.jugador_equipo_id = je.ID
        $sql$;

        -- Filas donde había más de una inscripción candidata (se tomó la
        -- más antigua por default) — advertencia, no aborta.
        EXECUTE $sql$
            SELECT COUNT(*) FROM (
                SELECT je.ID
                  FROM JUGADOR_EQUIPO je
                  JOIN INSCRIPCIONES_TORNEO it ON it.Equipo_ID = je.EQUIPO_ID
                  JOIN TORNEO t ON t.ID = it.Torneo_ID
                 WHERE (t.Fecha_Fin IS NULL OR t.Fecha_Fin >= je.Fecha_Inicio)
                 GROUP BY je.ID
                HAVING COUNT(*) > 1
            ) ambiguos
        $sql$ INTO v_ambiguos;

        IF v_ambiguos > 0 THEN
            RAISE WARNING '% fila(s) de JUGADOR_EQUIPO tenían más de una INSCRIPCIONES_TORNEO candidata (equipo en varios torneos solapados) — se tomó el torneo más antiguo por default, revisar manualmente.', v_ambiguos;
        END IF;
    END IF;
END $$;

DO $$
DECLARE
    v_sin_resolver INT;
BEGIN
    -- Filas que no se pudieron resolver del todo — esto SÍ aborta: la
    -- columna se vuelve NOT NULL a continuación y silenciar esto dejaría
    -- membresías huérfanas. No depende de JUGADOR_ID/EQUIPO_ID, así que
    -- no necesita SQL dinámico.
    SELECT COUNT(*) INTO v_sin_resolver
      FROM JUGADOR_EQUIPO
     WHERE Inscripcion_Torneo_ID IS NULL OR Jugador_Perfil_ID IS NULL;

    IF v_sin_resolver > 0 THEN
        RAISE EXCEPTION '% fila(s) de JUGADOR_EQUIPO no se pudieron migrar automáticamente (sin INSCRIPCIONES_TORNEO candidata cuyo rango de fechas cubra Fecha_Inicio) — resolver manualmente antes de continuar.', v_sin_resolver;
    END IF;
END $$;

ALTER TABLE JUGADOR_EQUIPO ALTER COLUMN Jugador_Perfil_ID SET NOT NULL;
ALTER TABLE JUGADOR_EQUIPO ALTER COLUMN Inscripcion_Torneo_ID SET NOT NULL;

-- La vista depende de JUGADOR_ID/EQUIPO_ID (las columnas que se van a
-- dropear más abajo) — hay que reemplazarla ANTES del DROP COLUMN, o
-- Postgres rechaza el drop porque la vista todavía depende de la
-- columna. DROP+CREATE (no OR REPLACE): la nueva versión agrega
-- Torneo_ID en medio de la lista de columnas, y OR REPLACE no admite
-- reordenar/insertar columnas que no sean al final.
DROP VIEW IF EXISTS vw_jugadores_activos_por_equipo;
CREATE VIEW vw_jugadores_activos_por_equipo AS
SELECT
    e.ID       AS Equipo_ID,
    e.Nombre   AS Equipo,
    it.Torneo_ID,
    j.ID       AS Jugador_ID,
    j.Nombre   AS Jugador,
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

-- fn_validar_jugador_partido lee JUGADOR_EQUIPO por texto SQL dentro del
-- cuerpo plpgsql — Postgres no lo trata como "dependiente" de la columna
-- (a diferencia de una vista), así que no bloquea el DROP COLUMN de
-- abajo, pero SÍ hay que reemplazarlo o el trigger sigue apuntando a
-- columnas que ya no existen la próxima vez que se dispare.
CREATE OR REPLACE FUNCTION fn_validar_jugador_partido()
RETURNS TRIGGER AS $$
DECLARE
    v_equipo_local INT;
    v_equipo_visitante INT;
    v_fecha_partido TIMESTAMP;
    v_torneo_id INT;
    v_disciplina_id INT;
    v_valido INT;
    v_es_cambio BOOLEAN;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF NEW.JUGADOR_ID = OLD.JUGADOR_ID
           AND NEW.PARTIDOS_ID = OLD.PARTIDOS_ID
           AND NEW.EQUIPO_ID IS NOT DISTINCT FROM OLD.EQUIPO_ID
           AND NEW.JUGADOR_ID_ENTRA IS NOT DISTINCT FROM OLD.JUGADOR_ID_ENTRA THEN
            RETURN NEW;
        END IF;
    END IF;

    SELECT p.EQUIPOS_ID_LOCAL, p.EQUIPOS_ID_VISITANTE, p.Fecha_Partido, p.Torneo_ID, t.Disciplina_ID
      INTO v_equipo_local, v_equipo_visitante, v_fecha_partido, v_torneo_id, v_disciplina_id
      FROM PARTIDOS p
      JOIN TORNEO t ON t.ID = p.Torneo_ID
     WHERE p.ID = NEW.PARTIDOS_ID;

    IF NEW.EQUIPO_ID NOT IN (v_equipo_local, v_equipo_visitante) THEN
        RAISE EXCEPTION 'El equipo indicado no disputa este partido.';
    END IF;

    SELECT COUNT(*)
      INTO v_valido
      FROM JUGADOR_EQUIPO je
      JOIN JUGADOR_PERFIL_DISCIPLINA jpd ON jpd.ID = je.Jugador_Perfil_ID
      JOIN INSCRIPCIONES_TORNEO it ON it.ID = je.Inscripcion_Torneo_ID
     WHERE jpd.Jugador_ID = NEW.JUGADOR_ID
       AND jpd.Disciplina_ID = v_disciplina_id
       AND it.Torneo_ID = v_torneo_id
       AND it.Equipo_ID = NEW.EQUIPO_ID
       AND je.Estado = 'Activo'
       AND je.Fecha_Inicio <= v_fecha_partido::DATE
       AND (je.Fecha_Fin IS NULL OR je.Fecha_Fin >= v_fecha_partido::DATE);

    IF v_valido = 0 THEN
        RAISE EXCEPTION 'El jugador no pertenecia a ese equipo en la fecha del partido.';
    END IF;

    SELECT (Nombre = 'Cambio') INTO v_es_cambio FROM EVENTOS WHERE ID = NEW.EVENTOS_ID;

    IF v_es_cambio THEN
        IF NEW.JUGADOR_ID_ENTRA IS NULL THEN
            RAISE EXCEPTION 'Un evento de tipo Cambio requiere jugador_id_entra.';
        END IF;

        SELECT COUNT(*)
          INTO v_valido
          FROM JUGADOR_EQUIPO je
          JOIN JUGADOR_PERFIL_DISCIPLINA jpd ON jpd.ID = je.Jugador_Perfil_ID
          JOIN INSCRIPCIONES_TORNEO it ON it.ID = je.Inscripcion_Torneo_ID
         WHERE jpd.Jugador_ID = NEW.JUGADOR_ID_ENTRA
           AND jpd.Disciplina_ID = v_disciplina_id
           AND it.Torneo_ID = v_torneo_id
           AND it.Equipo_ID = NEW.EQUIPO_ID
           AND je.Estado = 'Activo'
           AND je.Fecha_Inicio <= v_fecha_partido::DATE
           AND (je.Fecha_Fin IS NULL OR je.Fecha_Fin >= v_fecha_partido::DATE);

        IF v_valido = 0 THEN
            RAISE EXCEPTION 'El jugador que entra no pertenecia a ese equipo en la fecha del partido.';
        END IF;
    ELSIF NEW.JUGADOR_ID_ENTRA IS NOT NULL THEN
        RAISE EXCEPTION 'jugador_id_entra solo aplica a eventos de tipo Cambio.';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Ahora sí: fuera las columnas viejas y sus FKs/índices (Postgres los
-- dropea en cascada automáticamente por ser de la misma tabla — no hace
-- falta CASCADE explícito, eso solo aplica a objetos de OTRAS tablas
-- como la vista de arriba, ya reemplazada).
ALTER TABLE JUGADOR_EQUIPO DROP COLUMN IF EXISTS JUGADOR_ID;
ALTER TABLE JUGADOR_EQUIPO DROP COLUMN IF EXISTS EQUIPO_ID;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_jugador_equipo_perfil') THEN
        ALTER TABLE JUGADOR_EQUIPO ADD CONSTRAINT fk_jugador_equipo_perfil FOREIGN KEY (Jugador_Perfil_ID) REFERENCES JUGADOR_PERFIL_DISCIPLINA(ID) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_jugador_equipo_inscripcion') THEN
        ALTER TABLE JUGADOR_EQUIPO ADD CONSTRAINT fk_jugador_equipo_inscripcion FOREIGN KEY (Inscripcion_Torneo_ID) REFERENCES INSCRIPCIONES_TORNEO(ID) ON DELETE CASCADE;
    END IF;
END $$;

ALTER TABLE JUGADOR_EQUIPO DROP CONSTRAINT IF EXISTS chk_jugador_equipo_estado;
ALTER TABLE JUGADOR_EQUIPO ADD CONSTRAINT chk_jugador_equipo_estado
    CHECK (Estado IN ('Activo', 'Inactivo', 'Suspendido', 'Traspasado'));

ALTER TABLE JUGADOR_EQUIPO DROP CONSTRAINT IF EXISTS unique_jugador_equipo;
ALTER TABLE JUGADOR_EQUIPO ADD CONSTRAINT unique_jugador_equipo
    UNIQUE (Jugador_Perfil_ID, Inscripcion_Torneo_ID, Fecha_Inicio);

DROP INDEX IF EXISTS idx_jugador_equipo_jugador;
DROP INDEX IF EXISTS idx_jugador_equipo_equipo;
DROP INDEX IF EXISTS idx_jugador_equipo_vigencia;
DROP INDEX IF EXISTS uq_dorsal_por_equipo_vigente;

CREATE INDEX IF NOT EXISTS idx_jugador_equipo_perfil ON JUGADOR_EQUIPO(Jugador_Perfil_ID);
CREATE INDEX IF NOT EXISTS idx_jugador_equipo_inscripcion ON JUGADOR_EQUIPO(Inscripcion_Torneo_ID);
CREATE INDEX IF NOT EXISTS idx_jugador_equipo_vigencia ON JUGADOR_EQUIPO(Inscripcion_Torneo_ID, Fecha_Inicio, Fecha_Fin);

-- Ver el comentario largo en 03_indexes.sql: se mantiene la forma
-- PARCIAL (no el UNIQUE plano que sugiere el plan en EC-13) para que un
-- dorsal se libere cuando el jugador deja el roster.
CREATE UNIQUE INDEX IF NOT EXISTS uq_dorsal_por_roster_vigente
    ON JUGADOR_EQUIPO (Inscripcion_Torneo_ID, Dorsal)
    WHERE Fecha_Fin IS NULL AND Estado = 'Activo' AND Dorsal IS NOT NULL;

-- ------------------------------------------------------------
-- PARTE F — TRASPASOS (nueva tabla, sin backfill: no hay traspasos
-- históricos que reconstruir, la trayectoria empieza a registrarse desde
-- ahora)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS TRASPASOS (
    ID SERIAL PRIMARY KEY,
    Jugador_Perfil_ID INT NOT NULL,
    Inscripcion_Origen_ID INT,
    Inscripcion_Destino_ID INT NOT NULL,
    Dorsal_Nuevo INT,
    Realizado_Por INT NOT NULL,
    Motivo VARCHAR(200),
    Fecha_Traspaso TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Estado VARCHAR(20) DEFAULT 'Completado'
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_traspasos_perfil') THEN
        ALTER TABLE TRASPASOS ADD CONSTRAINT fk_traspasos_perfil FOREIGN KEY (Jugador_Perfil_ID) REFERENCES JUGADOR_PERFIL_DISCIPLINA(ID);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_traspasos_origen') THEN
        ALTER TABLE TRASPASOS ADD CONSTRAINT fk_traspasos_origen FOREIGN KEY (Inscripcion_Origen_ID) REFERENCES INSCRIPCIONES_TORNEO(ID);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_traspasos_destino') THEN
        ALTER TABLE TRASPASOS ADD CONSTRAINT fk_traspasos_destino FOREIGN KEY (Inscripcion_Destino_ID) REFERENCES INSCRIPCIONES_TORNEO(ID);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_traspasos_usuario') THEN
        ALTER TABLE TRASPASOS ADD CONSTRAINT fk_traspasos_usuario FOREIGN KEY (Realizado_Por) REFERENCES USUARIOS(ID);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_traspasos_estado') THEN
        ALTER TABLE TRASPASOS ADD CONSTRAINT chk_traspasos_estado CHECK (Estado IN ('Completado', 'Anulado'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_traspasos_perfil ON TRASPASOS(Jugador_Perfil_ID);
CREATE INDEX IF NOT EXISTS idx_traspasos_origen ON TRASPASOS(Inscripcion_Origen_ID);
CREATE INDEX IF NOT EXISTS idx_traspasos_destino ON TRASPASOS(Inscripcion_Destino_ID);
CREATE INDEX IF NOT EXISTS idx_traspasos_usuario ON TRASPASOS(Realizado_Por);

-- ------------------------------------------------------------
-- PARTE G — Triggers nuevos, recién ahora que todo backfill terminó
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_validar_torneo_modalidad()
RETURNS TRIGGER AS $$
DECLARE
    v_tipo VARCHAR(20);
    v_modalidad_disciplina INT;
BEGIN
    SELECT Tipo INTO v_tipo FROM DISCIPLINA WHERE ID = NEW.Disciplina_ID;

    IF v_tipo = 'Individual' AND NEW.Modalidad_ID IS NULL THEN
        RAISE EXCEPTION 'Un torneo de disciplina individual requiere Modalidad_ID.';
    END IF;

    IF v_tipo = 'Equipo' AND NEW.Modalidad_ID IS NOT NULL THEN
        RAISE EXCEPTION 'Un torneo de disciplina de equipo no admite Modalidad_ID.';
    END IF;

    IF NEW.Modalidad_ID IS NOT NULL THEN
        SELECT Disciplina_ID INTO v_modalidad_disciplina FROM MODALIDAD WHERE ID = NEW.Modalidad_ID;
        IF v_modalidad_disciplina <> NEW.Disciplina_ID THEN
            RAISE EXCEPTION 'La modalidad indicada no pertenece a esta disciplina.';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_torneo_validar_modalidad ON TORNEO;
CREATE TRIGGER trg_torneo_validar_modalidad
BEFORE INSERT OR UPDATE OF Disciplina_ID, Modalidad_ID ON TORNEO
FOR EACH ROW EXECUTE FUNCTION fn_validar_torneo_modalidad();

CREATE OR REPLACE FUNCTION fn_validar_exclusividad_torneo()
RETURNS TRIGGER AS $$
DECLARE
    v_conflicto INT;
BEGIN
    IF NEW.Estado = 'Activo' THEN
        SELECT COUNT(*) INTO v_conflicto
        FROM JUGADOR_EQUIPO je
        JOIN INSCRIPCIONES_TORNEO it_new ON it_new.ID = NEW.Inscripcion_Torneo_ID
        JOIN INSCRIPCIONES_TORNEO it_je  ON it_je.ID = je.Inscripcion_Torneo_ID
        WHERE je.Jugador_Perfil_ID = NEW.Jugador_Perfil_ID
          AND je.Estado = 'Activo'
          AND je.ID <> COALESCE(NEW.ID, -1)
          AND it_je.Torneo_ID = it_new.Torneo_ID;

        IF v_conflicto > 0 THEN
            RAISE EXCEPTION 'jugador_ya_activo_en_este_torneo';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_jugador_equipo_exclusividad ON JUGADOR_EQUIPO;
CREATE TRIGGER trg_jugador_equipo_exclusividad
BEFORE INSERT OR UPDATE ON JUGADOR_EQUIPO
FOR EACH ROW EXECUTE FUNCTION fn_validar_exclusividad_torneo();

CREATE OR REPLACE FUNCTION fn_cerrar_torneo_libera_jugadores()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.Estado = 'Finalizado' AND OLD.Estado <> 'Finalizado' THEN
        UPDATE JUGADOR_EQUIPO je
        SET Estado = 'Inactivo', Fecha_Fin = CURRENT_DATE
        FROM INSCRIPCIONES_TORNEO it
        WHERE je.Inscripcion_Torneo_ID = it.ID
          AND it.Torneo_ID = NEW.ID
          AND je.Estado = 'Activo';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_torneo_finalizado_libera ON TORNEO;
CREATE TRIGGER trg_torneo_finalizado_libera
AFTER UPDATE ON TORNEO
FOR EACH ROW EXECUTE FUNCTION fn_cerrar_torneo_libera_jugadores();

-- ------------------------------------------------------------
-- PARTE H — Vistas nuevas
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
-- PARTE I — Verificación final (informa, no rompe el script salvo que
-- diga explícitamente "abortando")
-- ------------------------------------------------------------
DO $$
DECLARE
    v_placeholder_cedula INT;
    v_malos INT;
BEGIN
    SELECT COUNT(*) INTO v_placeholder_cedula FROM JUGADORES WHERE Cedula LIKE 'PENDIENTE-%';
    IF v_placeholder_cedula > 0 THEN
        RAISE WARNING '% jugador(es) quedaron con cédula placeholder (PENDIENTE-<id>) — capturar la cédula real antes de depender de ella para identificar duplicados.', v_placeholder_cedula;
    END IF;

    -- Coherencia perfil-torneo: ningún evento de partido debería quedar
    -- huérfano de la revalidación (mismo chequeo que el bloque final de
    -- 06_triggers.sql, repetido acá porque este script puede correr
    -- contra una base con más historia que el seed de 05_seed.sql).
    SELECT COUNT(*) INTO v_malos
      FROM EVENTOS_PARTIDO ep
      JOIN PARTIDOS p ON p.ID = ep.PARTIDOS_ID
      JOIN TORNEO t ON t.ID = p.Torneo_ID
     WHERE NOT EXISTS (
            SELECT 1 FROM JUGADOR_EQUIPO je
             JOIN JUGADOR_PERFIL_DISCIPLINA jpd ON jpd.ID = je.Jugador_Perfil_ID
             JOIN INSCRIPCIONES_TORNEO it ON it.ID = je.Inscripcion_Torneo_ID
            WHERE jpd.Jugador_ID = ep.JUGADOR_ID
              AND jpd.Disciplina_ID = t.Disciplina_ID
              AND it.Torneo_ID = p.Torneo_ID
              AND it.Equipo_ID = ep.EQUIPO_ID
              AND je.Estado IN ('Activo', 'Inactivo', 'Traspasado')
              AND je.Fecha_Inicio <= p.Fecha_Partido::DATE
              AND (je.Fecha_Fin IS NULL OR je.Fecha_Fin >= p.Fecha_Partido::DATE));
    IF v_malos > 0 THEN
        RAISE WARNING '% evento(s) de partido ya no resuelven una membresía JUGADOR_EQUIPO coherente tras la migración — revisar manualmente (posible caso ambiguo de la Parte E).', v_malos;
    END IF;

    RAISE NOTICE 'Migracion equipos-jugadores aplicada. Revisar los WARNING de arriba si los hubo.';
END $$;
