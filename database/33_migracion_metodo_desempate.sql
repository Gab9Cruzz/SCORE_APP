-- ============================================================
-- 33_migracion_metodo_desempate.sql
-- Desempate de eliminatoria: tiempo extra y penales — FASE 2
-- (docs/plans/desempate-tiempo-extra-penales-plan.md) — para una base YA
-- provisionada (torneos_mvp). La secuencia 01-06 ya quedó actualizada al
-- estado final.
--
-- Numerada 33 (sigue a 32_migracion_cierre_fase_y_llaves.sql). Fase 1 del
-- plan (`requiere_desempate` calculado en el servidor) no tiene migración
-- — es Python puro.
--
-- Aditiva pura, sin backfill destructivo:
--   - TORNEO: Metodo_Desempate_Eliminatoria VARCHAR(20) NOT NULL DEFAULT
--     'Manual' — todo torneo existente sigue en el comportamiento de hoy.
--     CHECK acotado a ('Manual', 'Penales_Directo') a propósito (F6): los
--     valores con prórroga llegan recién en la migración 34, junto con
--     las columnas que los sostienen.
--   - PARTIDOS: Metodo_Desempate, Penales_Local, Penales_Visitante,
--     Hubo_Tiempo_Extra (NOT NULL DEFAULT FALSE), Metodo_Desempate_Aplicable.
--     Todas NULL/FALSE para las 13 filas existentes hoy — ninguna estaba
--     resuelta por tiempo extra o penales.
--   - fn_validar_torneo_modalidad: extendida (Corrido => Manual) + el
--     trigger pasa a escuchar también UPDATE OF Metodo_Desempate_Eliminatoria.
--   - fn_validar_forma_desempate: función NUEVA (reglas de forma/rango/
--     coherencia de las 5 columnas de PARTIDOS).
--   - fn_validar_partido_eliminacion_desempate: reemplazada (mismo texto
--     que la versión final en 06_triggers.sql) — suma el carve-out de un
--     PATCH sobre un partido ya Finalizado y el chequeo desempate_en_ida_
--     no_permitido.
--
-- Re-ejecutable: ADD COLUMN IF NOT EXISTS, constraints guardadas con un
-- chequeo previo contra pg_constraint, CREATE OR REPLACE FUNCTION y
-- DROP TRIGGER IF EXISTS + CREATE TRIGGER (test_scripts_sql.py corre este
-- archivo DOS veces).
-- ============================================================

-- ------------------------------------------------------------
-- PARTE 1 — TORNEO.Metodo_Desempate_Eliminatoria
-- ------------------------------------------------------------
ALTER TABLE TORNEO ADD COLUMN IF NOT EXISTS Metodo_Desempate_Eliminatoria VARCHAR(20) NOT NULL DEFAULT 'Manual';

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_torneo_metodo_desempate_eliminatoria') THEN
        ALTER TABLE TORNEO
            ADD CONSTRAINT chk_torneo_metodo_desempate_eliminatoria CHECK (Metodo_Desempate_Eliminatoria IN ('Manual', 'Penales_Directo'));
    END IF;
END $$;

-- ------------------------------------------------------------
-- PARTE 2 — PARTIDOS: el CÓMO al lado del QUIÉN
-- ------------------------------------------------------------
ALTER TABLE PARTIDOS ADD COLUMN IF NOT EXISTS Metodo_Desempate VARCHAR(20);
ALTER TABLE PARTIDOS ADD COLUMN IF NOT EXISTS Penales_Local INT;
ALTER TABLE PARTIDOS ADD COLUMN IF NOT EXISTS Penales_Visitante INT;
ALTER TABLE PARTIDOS ADD COLUMN IF NOT EXISTS Hubo_Tiempo_Extra BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE PARTIDOS ADD COLUMN IF NOT EXISTS Metodo_Desempate_Aplicable VARCHAR(20);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_partidos_metodo_desempate') THEN
        ALTER TABLE PARTIDOS
            ADD CONSTRAINT chk_partidos_metodo_desempate CHECK (Metodo_Desempate IS NULL OR Metodo_Desempate IN ('Tiempo_Extra', 'Penales', 'Manual'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_partidos_metodo_desempate_aplicable') THEN
        ALTER TABLE PARTIDOS
            ADD CONSTRAINT chk_partidos_metodo_desempate_aplicable CHECK (Metodo_Desempate_Aplicable IS NULL OR Metodo_Desempate_Aplicable IN ('Manual', 'Penales_Directo', 'Tiempo_Extra_Penales'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_partidos_penales_rango') THEN
        ALTER TABLE PARTIDOS
            ADD CONSTRAINT chk_partidos_penales_rango CHECK (Penales_Local IS NULL OR Penales_Local BETWEEN 0 AND 99);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_partidos_penales_visitante_rango') THEN
        ALTER TABLE PARTIDOS
            ADD CONSTRAINT chk_partidos_penales_visitante_rango CHECK (Penales_Visitante IS NULL OR Penales_Visitante BETWEEN 0 AND 99);
    END IF;
END $$;

-- ------------------------------------------------------------
-- PARTE 3 — Regresión obligatoria (§13 del plan): los cuatro caminos que
-- YA escriben Ganador_Desempate_ID hoy tienen que seguir cerrando un
-- empate manual sin explotar contra la regla nueva "Ganador_Desempate_ID
-- NOT NULL => Metodo_Desempate NOT NULL" — backfill de las filas
-- existentes que ya tienen un desempate manual resuelto, para que la
-- regla nueva no las deje en un estado retroactivamente inválido.
-- ------------------------------------------------------------
UPDATE PARTIDOS SET Metodo_Desempate = 'Manual'
 WHERE Ganador_Desempate_ID IS NOT NULL AND Metodo_Desempate IS NULL;

-- ------------------------------------------------------------
-- PARTE 4 — fn_validar_torneo_modalidad: suma "Corrido => Manual"
-- (D5/§7, SPEC-REVIEW S7/F2). Mismo texto que la versión final en
-- 06_triggers.sql.
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_validar_torneo_modalidad()
RETURNS TRIGGER AS $$
DECLARE
    v_modalidad_disciplina INT;
    v_tipo_cronometro VARCHAR(20);
BEGIN
    SELECT Disciplina_ID INTO v_modalidad_disciplina FROM MODALIDAD WHERE ID = NEW.Modalidad_ID;
    IF v_modalidad_disciplina IS NULL THEN
        RAISE EXCEPTION 'La modalidad indicada no existe.';
    END IF;
    IF v_modalidad_disciplina <> NEW.Disciplina_ID THEN
        RAISE EXCEPTION 'La modalidad indicada no pertenece a esta disciplina.';
    END IF;

    IF NEW.Metodo_Desempate_Eliminatoria <> 'Manual' THEN
        SELECT Tipo_Cronometro INTO v_tipo_cronometro
          FROM CONFIGURACION_TIEMPO_TORNEO WHERE Torneo_ID = NEW.ID;
        IF v_tipo_cronometro = 'Corrido' THEN
            RAISE EXCEPTION 'penales_no_aplican_a_corrido';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_torneo_validar_modalidad ON TORNEO;
CREATE TRIGGER trg_torneo_validar_modalidad
BEFORE INSERT OR UPDATE OF Disciplina_ID, Modalidad_ID, Metodo_Desempate_Eliminatoria ON TORNEO
FOR EACH ROW EXECUTE FUNCTION fn_validar_torneo_modalidad();

-- ------------------------------------------------------------
-- PARTE 5 — fn_validar_forma_desempate (función nueva) +
-- fn_validar_partido_eliminacion_desempate (reemplazada). Mismo texto que
-- la versión final en 06_triggers.sql.
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_validar_forma_desempate(
    p_metodo_desempate VARCHAR(20),
    p_penales_local INT,
    p_penales_visitante INT,
    p_hubo_tiempo_extra BOOLEAN,
    p_ganador_desempate_id INT,
    p_equipo_local INT,
    p_equipo_visitante INT
) RETURNS VOID AS $$
DECLARE
    v_ganador_tanda INT;
BEGIN
    IF (p_penales_local IS NULL) <> (p_penales_visitante IS NULL) THEN
        RAISE EXCEPTION 'tanda_penales_fuera_de_rango';
    END IF;

    IF p_penales_local IS NOT NULL THEN
        IF p_penales_local NOT BETWEEN 0 AND 99 OR p_penales_visitante NOT BETWEEN 0 AND 99 THEN
            RAISE EXCEPTION 'tanda_penales_fuera_de_rango';
        END IF;
        IF p_penales_local = p_penales_visitante THEN
            RAISE EXCEPTION 'tanda_penales_empatada';
        END IF;
        IF p_metodo_desempate IS DISTINCT FROM 'Penales' THEN
            RAISE EXCEPTION 'metodo_desempate_incoherente';
        END IF;
        v_ganador_tanda := CASE WHEN p_penales_local > p_penales_visitante THEN p_equipo_local ELSE p_equipo_visitante END;
        IF p_ganador_desempate_id IS DISTINCT FROM v_ganador_tanda THEN
            RAISE EXCEPTION 'ganador_desempate_contradice_tanda';
        END IF;
    ELSIF p_metodo_desempate = 'Penales' THEN
        RAISE EXCEPTION 'metodo_desempate_incoherente';
    END IF;

    IF p_metodo_desempate = 'Tiempo_Extra' THEN
        IF p_ganador_desempate_id IS NOT NULL THEN
            RAISE EXCEPTION 'metodo_desempate_incoherente';
        END IF;
        IF NOT p_hubo_tiempo_extra THEN
            RAISE EXCEPTION 'metodo_desempate_incoherente';
        END IF;
    ELSIF p_metodo_desempate = 'Manual' AND p_ganador_desempate_id IS NULL THEN
        RAISE EXCEPTION 'metodo_desempate_incoherente';
    END IF;

    IF p_ganador_desempate_id IS NOT NULL AND p_metodo_desempate IS NULL THEN
        RAISE EXCEPTION 'desempate_sin_metodo';
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fn_validar_partido_eliminacion_desempate()
RETURNS TRIGGER AS $$
DECLARE
    v_tipo_fase VARCHAR(20);
    v_estado_ida VARCHAR(20);
    v_es_ida BOOLEAN;
    v_ganador_agregado INT;
    v_goles_local INT;
    v_goles_visitante INT;
    v_toco_columnas_desempate BOOLEAN;
BEGIN
    v_toco_columnas_desempate := (
        NEW.Metodo_Desempate IS DISTINCT FROM OLD.Metodo_Desempate
        OR NEW.Penales_Local IS DISTINCT FROM OLD.Penales_Local
        OR NEW.Penales_Visitante IS DISTINCT FROM OLD.Penales_Visitante
        OR NEW.Hubo_Tiempo_Extra IS DISTINCT FROM OLD.Hubo_Tiempo_Extra
        OR NEW.Ganador_Desempate_ID IS DISTINCT FROM OLD.Ganador_Desempate_ID
    );

    IF OLD.Estado = 'Finalizado' THEN
        IF v_toco_columnas_desempate THEN
            PERFORM fn_validar_forma_desempate(
                NEW.Metodo_Desempate, NEW.Penales_Local, NEW.Penales_Visitante,
                NEW.Hubo_Tiempo_Extra, NEW.Ganador_Desempate_ID,
                NEW.EQUIPOS_ID_LOCAL, NEW.EQUIPOS_ID_VISITANTE
            );
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.Estado <> 'Finalizado' THEN
        RETURN NEW;
    END IF;

    PERFORM fn_validar_forma_desempate(
        NEW.Metodo_Desempate, NEW.Penales_Local, NEW.Penales_Visitante,
        NEW.Hubo_Tiempo_Extra, NEW.Ganador_Desempate_ID,
        NEW.EQUIPOS_ID_LOCAL, NEW.EQUIPOS_ID_VISITANTE
    );

    IF NEW.Partido_Ida_ID IS NOT NULL THEN
        SELECT Estado INTO v_estado_ida FROM PARTIDOS WHERE ID = NEW.Partido_Ida_ID FOR UPDATE;
        IF v_estado_ida NOT IN ('Finalizado', 'Cancelado') THEN
            RAISE EXCEPTION 'partido_vuelta_ida_sin_resolver';
        END IF;
    END IF;

    IF NEW.Fase_ID IS NULL OR NEW.Es_Walkover THEN
        RETURN NEW;
    END IF;

    SELECT Tipo INTO v_tipo_fase FROM FASE WHERE ID = NEW.Fase_ID;
    IF v_tipo_fase <> 'Eliminacion' THEN
        RETURN NEW;
    END IF;

    SELECT EXISTS(SELECT 1 FROM PARTIDOS WHERE Partido_Ida_ID = NEW.ID) INTO v_es_ida;
    IF v_es_ida THEN
        IF NEW.Metodo_Desempate IS NOT NULL OR NEW.Penales_Local IS NOT NULL
           OR NEW.Penales_Visitante IS NOT NULL OR NEW.Hubo_Tiempo_Extra THEN
            RAISE EXCEPTION 'desempate_en_ida_no_permitido';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.Partido_Ida_ID IS NOT NULL THEN
        SELECT r.ganador_equipo_id INTO v_ganador_agregado
          FROM fn_resolver_llave(NEW.ID, NEW.Ganador_Desempate_ID) r;
        IF v_ganador_agregado IS NULL THEN
            RAISE EXCEPTION 'llave_empatada_en_global_sin_desempate';
        END IF;
    ELSE
        SELECT
            COUNT(*) FILTER (WHERE ga.Equipo_Acreditado = NEW.EQUIPOS_ID_LOCAL),
            COUNT(*) FILTER (WHERE ga.Equipo_Acreditado = NEW.EQUIPOS_ID_VISITANTE)
          INTO v_goles_local, v_goles_visitante
          FROM vw_goles_acreditados ga
         WHERE ga.PARTIDOS_ID = NEW.ID;
        IF v_goles_local = v_goles_visitante AND NEW.Ganador_Desempate_ID IS NULL THEN
            RAISE EXCEPTION 'partido_eliminacion_empatado_sin_desempate';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- El trigger en sí no cambia (sigue BEFORE UPDATE ON PARTIDOS, sin
-- columnas específicas) — CREATE OR REPLACE FUNCTION alcanza, no hace
-- falta DROP/CREATE TRIGGER acá.

-- ------------------------------------------------------------
-- PARTE 6 — vw_resultados_partidos: suma las 4 columnas de desempate
-- (D-D9) para que el portal público las muestre sin una segunda consulta
-- por partido. Mismo texto que la versión final en 04_views.sql.
-- vw_feed_partidos (construida encima) selecciona columnas explícitas —
-- no hace falta re-crearla, las nuevas no se le filtran.
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW vw_resultados_partidos AS
SELECT
    p.ID       AS Partido_ID,
    p.TORNEO_ID,
    el.ID      AS Equipo_Local_ID,
    el.Nombre  AS Equipo_Local,
    ev_eq.ID   AS Equipo_Visitante_ID,
    ev_eq.Nombre AS Equipo_Visitante,
    CASE
        WHEN p.Es_Walkover THEN (CASE WHEN p.Walkover_Equipo_Ausente_ID = p.EQUIPOS_ID_LOCAL THEN 0 ELSE 3 END)
        ELSE COUNT(ga.Evento_Partido_ID) FILTER (WHERE ga.Equipo_Acreditado = p.EQUIPOS_ID_LOCAL)
    END AS Goles_Local,
    CASE
        WHEN p.Es_Walkover THEN (CASE WHEN p.Walkover_Equipo_Ausente_ID = p.EQUIPOS_ID_VISITANTE THEN 0 ELSE 3 END)
        ELSE COUNT(ga.Evento_Partido_ID) FILTER (WHERE ga.Equipo_Acreditado = p.EQUIPOS_ID_VISITANTE)
    END AS Goles_Visitante,
    p.Fecha_Partido,
    p.Jornada,
    p.Fase,
    p.Grupo,
    p.Fase_ID,
    p.Grupo_ID,
    p.Estado,
    p.Es_Walkover,
    p.Walkover_Equipo_Ausente_ID,
    p.Metodo_Desempate,
    p.Hubo_Tiempo_Extra,
    p.Penales_Local,
    p.Penales_Visitante
FROM PARTIDOS p
JOIN EQUIPOS el    ON el.ID    = p.EQUIPOS_ID_LOCAL
JOIN EQUIPOS ev_eq ON ev_eq.ID = p.EQUIPOS_ID_VISITANTE
LEFT JOIN vw_goles_acreditados ga ON ga.PARTIDOS_ID = p.ID
GROUP BY p.ID, p.TORNEO_ID, el.ID, el.Nombre, ev_eq.ID, ev_eq.Nombre,
         p.Fecha_Partido, p.Jornada, p.Fase, p.Grupo, p.Fase_ID, p.Grupo_ID, p.Estado,
         p.Es_Walkover, p.Walkover_Equipo_Ausente_ID,
         p.Metodo_Desempate, p.Hubo_Tiempo_Extra, p.Penales_Local, p.Penales_Visitante;
