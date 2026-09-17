-- ============================================================
-- 32_migracion_cierre_fase_y_llaves.sql
-- Cierre de Fase Regular, Motor de Llaves (Ida/Vuelta/Mixto) y
-- Flexibilidad de Grupos — docs/plans/cierre-fase-regular-llaves-playoffs-
-- plan.md — para una base YA provisionada (torneos_mvp). La secuencia
-- 01-06 ya quedó actualizada al estado final.
--
-- Numerada 32 (sigue a 31_migracion_portal_publico.sql).
--
-- Aditiva pura, sin backfill destructivo:
--   - TORNEO: Campeon/Subcampeon/Tercer_Puesto_Equipo_ID, Fecha_Cierre,
--     Formato_Eliminatoria (default 'Unico' — ningún torneo existente
--     cambia de comportamiento), Orden_Podio_Manual (JSONB).
--   - PARTIDOS: Partido_Ida_ID (autorreferencial, ON DELETE SET NULL,
--     mismo patrón que Partido_Siguiente_ID).
--   - fn_marcador_partido / fn_resolver_llave: funciones NUEVAS.
--   - fn_validar_partido_eliminacion_desempate / fn_propagar_ganador_bracket:
--     reemplazadas (mismo texto que la versión final en 06_triggers.sql).
--   - fn_bloquear_escritura_torneo_cerrado + 3 triggers nuevos: bloquean
--     escritura de resultados en un torneo Finalizado.
--
-- Re-ejecutable: ADD COLUMN IF NOT EXISTS, constraints guardadas con un
-- chequeo previo contra pg_constraint, CREATE OR REPLACE FUNCTION y
-- DROP TRIGGER IF EXISTS + CREATE TRIGGER (test_scripts_sql.py corre este
-- archivo DOS veces).
-- ============================================================

-- ------------------------------------------------------------
-- PARTE A1/A2 — TORNEO: podio + Formato_Eliminatoria + orden manual
-- ------------------------------------------------------------
ALTER TABLE TORNEO ADD COLUMN IF NOT EXISTS Campeon_Equipo_ID INT;
ALTER TABLE TORNEO ADD COLUMN IF NOT EXISTS Subcampeon_Equipo_ID INT;
ALTER TABLE TORNEO ADD COLUMN IF NOT EXISTS Tercer_Puesto_Equipo_ID INT;
ALTER TABLE TORNEO ADD COLUMN IF NOT EXISTS Fecha_Cierre TIMESTAMP;
ALTER TABLE TORNEO ADD COLUMN IF NOT EXISTS Formato_Eliminatoria VARCHAR(20) NOT NULL DEFAULT 'Unico';
ALTER TABLE TORNEO ADD COLUMN IF NOT EXISTS Orden_Podio_Manual JSONB;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_torneo_campeon') THEN
        ALTER TABLE TORNEO
            ADD CONSTRAINT fk_torneo_campeon FOREIGN KEY (Campeon_Equipo_ID) REFERENCES EQUIPOS(ID) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_torneo_subcampeon') THEN
        ALTER TABLE TORNEO
            ADD CONSTRAINT fk_torneo_subcampeon FOREIGN KEY (Subcampeon_Equipo_ID) REFERENCES EQUIPOS(ID) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_torneo_tercer_puesto') THEN
        ALTER TABLE TORNEO
            ADD CONSTRAINT fk_torneo_tercer_puesto FOREIGN KEY (Tercer_Puesto_Equipo_ID) REFERENCES EQUIPOS(ID) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_torneo_formato_eliminatoria') THEN
        ALTER TABLE TORNEO
            ADD CONSTRAINT chk_torneo_formato_eliminatoria CHECK (Formato_Eliminatoria IN ('Unico', 'Ida_Vuelta', 'Mixto'));
    END IF;
END $$;

-- ------------------------------------------------------------
-- PARTE A3 — PARTIDOS.Partido_Ida_ID (llave a dos partidos)
-- ------------------------------------------------------------
ALTER TABLE PARTIDOS ADD COLUMN IF NOT EXISTS Partido_Ida_ID INT;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_partidos_ida') THEN
        ALTER TABLE PARTIDOS
            ADD CONSTRAINT fk_partidos_ida FOREIGN KEY (Partido_Ida_ID) REFERENCES PARTIDOS(ID) ON DELETE SET NULL;
    END IF;
END $$;

-- ------------------------------------------------------------
-- PARTE B — Motor: resolución de llaves a dos partidos (SQL)
-- Mismo texto que la versión final en 06_triggers.sql.
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION fn_marcador_partido(p_partido_id INT)
RETURNS TABLE(ganador_equipo_id INT, goles_local INT, goles_visitante INT) AS $$
DECLARE
    v_local INT;
    v_visitante INT;
    v_es_walkover BOOLEAN;
    v_walkover_ausente INT;
    v_ganador_desempate INT;
    v_ganador_corrido INT;
    v_torneo_id INT;
    v_tipo_cronometro VARCHAR(20);
    v_gl INT;
    v_gv INT;
BEGIN
    SELECT EQUIPOS_ID_LOCAL, EQUIPOS_ID_VISITANTE, Es_Walkover, Walkover_Equipo_Ausente_ID,
           Ganador_Desempate_ID, Ganador_Corrido_ID, Torneo_ID
      INTO v_local, v_visitante, v_es_walkover, v_walkover_ausente,
           v_ganador_desempate, v_ganador_corrido, v_torneo_id
      FROM PARTIDOS WHERE ID = p_partido_id;

    IF v_es_walkover THEN
        ganador_equipo_id := CASE WHEN v_walkover_ausente = v_local THEN v_visitante ELSE v_local END;
        goles_local := CASE WHEN v_walkover_ausente = v_local THEN 0 ELSE 3 END;
        goles_visitante := CASE WHEN v_walkover_ausente = v_visitante THEN 0 ELSE 3 END;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT Tipo_Cronometro INTO v_tipo_cronometro FROM CONFIGURACION_TIEMPO_TORNEO WHERE Torneo_ID = v_torneo_id;

    IF v_tipo_cronometro = 'Corrido' THEN
        ganador_equipo_id := v_ganador_corrido;
        goles_local := NULL;
        goles_visitante := NULL;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT
        COUNT(*) FILTER (WHERE ga.Equipo_Acreditado = v_local),
        COUNT(*) FILTER (WHERE ga.Equipo_Acreditado = v_visitante)
      INTO v_gl, v_gv
      FROM vw_goles_acreditados ga
     WHERE ga.PARTIDOS_ID = p_partido_id;

    goles_local := COALESCE(v_gl, 0);
    goles_visitante := COALESCE(v_gv, 0);
    ganador_equipo_id := CASE
        WHEN goles_local > goles_visitante THEN v_local
        WHEN goles_visitante > goles_local THEN v_visitante
        ELSE v_ganador_desempate
    END;
    RETURN NEXT;
    RETURN;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fn_resolver_llave(p_partido_vuelta_id INT, p_ganador_desempate_override INT DEFAULT NULL)
RETURNS TABLE(ganador_equipo_id INT) AS $$
DECLARE
    v_ida_id INT;
    v_torneo_id INT;
    v_local_vta INT;
    v_visit_vta INT;
    v_ganador_desempate INT;
    v_tipo_cronometro VARCHAR(20);
    ida_ganador INT; ida_gl INT; ida_gv INT;
    vta_ganador INT; vta_gl INT; vta_gv INT;
    v_gl_total INT;
    v_gv_total INT;
    v_victorias_local INT := 0;
    v_victorias_visit INT := 0;
BEGIN
    SELECT Partido_Ida_ID, Torneo_ID, EQUIPOS_ID_LOCAL, EQUIPOS_ID_VISITANTE, Ganador_Desempate_ID
      INTO v_ida_id, v_torneo_id, v_local_vta, v_visit_vta, v_ganador_desempate
      FROM PARTIDOS WHERE ID = p_partido_vuelta_id;

    IF p_ganador_desempate_override IS NOT NULL THEN
        v_ganador_desempate := p_ganador_desempate_override;
    END IF;

    SELECT Tipo_Cronometro INTO v_tipo_cronometro FROM CONFIGURACION_TIEMPO_TORNEO WHERE Torneo_ID = v_torneo_id;

    SELECT m.ganador_equipo_id, m.goles_local, m.goles_visitante INTO ida_ganador, ida_gl, ida_gv
      FROM fn_marcador_partido(v_ida_id) m;
    SELECT m.ganador_equipo_id, m.goles_local, m.goles_visitante INTO vta_ganador, vta_gl, vta_gv
      FROM fn_marcador_partido(p_partido_vuelta_id) m;

    IF v_tipo_cronometro = 'Corrido' THEN
        IF ida_ganador IS NOT NULL AND ida_ganador = v_local_vta THEN v_victorias_local := v_victorias_local + 1; END IF;
        IF ida_ganador IS NOT NULL AND ida_ganador = v_visit_vta THEN v_victorias_visit := v_victorias_visit + 1; END IF;
        IF vta_ganador IS NOT NULL AND vta_ganador = v_local_vta THEN v_victorias_local := v_victorias_local + 1; END IF;
        IF vta_ganador IS NOT NULL AND vta_ganador = v_visit_vta THEN v_victorias_visit := v_victorias_visit + 1; END IF;

        ganador_equipo_id := CASE
            WHEN v_victorias_local > v_victorias_visit THEN v_local_vta
            WHEN v_victorias_visit > v_victorias_local THEN v_visit_vta
            ELSE v_ganador_desempate
        END;
    ELSE
        v_gl_total := COALESCE(vta_gl, 0) + COALESCE(ida_gv, 0);
        v_gv_total := COALESCE(vta_gv, 0) + COALESCE(ida_gl, 0);
        ganador_equipo_id := CASE
            WHEN v_gl_total > v_gv_total THEN v_local_vta
            WHEN v_gv_total > v_gl_total THEN v_visit_vta
            ELSE v_ganador_desempate
        END;
    END IF;
    RETURN NEXT;
    RETURN;
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
BEGIN
    IF NEW.Estado <> 'Finalizado' OR OLD.Estado = 'Finalizado' THEN
        RETURN NEW;
    END IF;

    IF NEW.Partido_Ida_ID IS NOT NULL THEN
        SELECT Estado INTO v_estado_ida FROM PARTIDOS WHERE ID = NEW.Partido_Ida_ID;
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

CREATE OR REPLACE FUNCTION fn_propagar_ganador_bracket()
RETURNS TRIGGER AS $$
DECLARE
    v_ganador_id INT;
    v_perdedor_id INT;
BEGIN
    IF NEW.Estado = 'Finalizado' AND OLD.Estado <> 'Finalizado'
       AND (NEW.Partido_Siguiente_ID IS NOT NULL OR NEW.Partido_Perdedor_Siguiente_ID IS NOT NULL) THEN

        IF NEW.Partido_Ida_ID IS NOT NULL THEN
            SELECT r.ganador_equipo_id INTO v_ganador_id FROM fn_resolver_llave(NEW.ID) r;
        ELSE
            SELECT m.ganador_equipo_id INTO v_ganador_id FROM fn_marcador_partido(NEW.ID) m;
        END IF;

        v_perdedor_id := CASE WHEN v_ganador_id = NEW.EQUIPOS_ID_LOCAL
                               THEN NEW.EQUIPOS_ID_VISITANTE ELSE NEW.EQUIPOS_ID_LOCAL END;

        IF NEW.Partido_Siguiente_ID IS NOT NULL THEN
            UPDATE PARTIDOS
               SET EQUIPOS_ID_LOCAL     = CASE WHEN NEW.Slot_Siguiente = 'Local'
                                                THEN v_ganador_id ELSE EQUIPOS_ID_LOCAL END,
                   EQUIPOS_ID_VISITANTE = CASE WHEN NEW.Slot_Siguiente = 'Visitante'
                                                THEN v_ganador_id ELSE EQUIPOS_ID_VISITANTE END
             WHERE ID = NEW.Partido_Siguiente_ID;

            UPDATE PARTIDOS AS ida
               SET EQUIPOS_ID_LOCAL     = CASE WHEN NEW.Slot_Siguiente = 'Visitante'
                                                THEN v_ganador_id ELSE ida.EQUIPOS_ID_LOCAL END,
                   EQUIPOS_ID_VISITANTE = CASE WHEN NEW.Slot_Siguiente = 'Local'
                                                THEN v_ganador_id ELSE ida.EQUIPOS_ID_VISITANTE END
              FROM PARTIDOS AS vuelta
             WHERE vuelta.ID = NEW.Partido_Siguiente_ID
               AND ida.ID = vuelta.Partido_Ida_ID;
        END IF;

        IF NEW.Partido_Perdedor_Siguiente_ID IS NOT NULL THEN
            UPDATE PARTIDOS
               SET EQUIPOS_ID_LOCAL     = CASE WHEN NEW.Slot_Perdedor_Siguiente = 'Local'
                                                THEN v_perdedor_id ELSE EQUIPOS_ID_LOCAL END,
                   EQUIPOS_ID_VISITANTE = CASE WHEN NEW.Slot_Perdedor_Siguiente = 'Visitante'
                                                THEN v_perdedor_id ELSE EQUIPOS_ID_VISITANTE END
             WHERE ID = NEW.Partido_Perdedor_Siguiente_ID;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ------------------------------------------------------------
-- PARTE C — Bloqueo de escritura en un torneo cerrado
-- Mismo texto que la versión final en 06_triggers.sql.
-- ------------------------------------------------------------

CREATE OR REPLACE FUNCTION fn_bloquear_escritura_torneo_cerrado()
RETURNS TRIGGER AS $$
DECLARE
    v_torneo_id INT;
    v_partido_id INT;
    v_estado_torneo VARCHAR(20);
BEGIN
    IF TG_TABLE_NAME = 'partidos' THEN
        v_torneo_id := COALESCE(NEW.Torneo_ID, OLD.Torneo_ID);
    ELSIF TG_TABLE_NAME = 'eventos_partido' THEN
        v_partido_id := COALESCE(NEW.PARTIDOS_ID, OLD.PARTIDOS_ID);
        SELECT Torneo_ID INTO v_torneo_id FROM PARTIDOS WHERE ID = v_partido_id;
    ELSE
        v_partido_id := COALESCE(NEW.Partido_ID, OLD.Partido_ID);
        SELECT Torneo_ID INTO v_torneo_id FROM PARTIDOS WHERE ID = v_partido_id;
    END IF;

    SELECT Estado INTO v_estado_torneo FROM TORNEO WHERE ID = v_torneo_id;
    IF v_estado_torneo = 'Finalizado' THEN
        RAISE EXCEPTION 'torneo_cerrado_resultados_bloqueados';
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_partidos_bloquear_torneo_cerrado ON PARTIDOS;
CREATE TRIGGER trg_partidos_bloquear_torneo_cerrado
BEFORE UPDATE ON PARTIDOS
FOR EACH ROW EXECUTE FUNCTION fn_bloquear_escritura_torneo_cerrado();

DROP TRIGGER IF EXISTS trg_eventos_partido_bloquear_torneo_cerrado ON EVENTOS_PARTIDO;
CREATE TRIGGER trg_eventos_partido_bloquear_torneo_cerrado
BEFORE INSERT OR UPDATE OR DELETE ON EVENTOS_PARTIDO
FOR EACH ROW EXECUTE FUNCTION fn_bloquear_escritura_torneo_cerrado();

DROP TRIGGER IF EXISTS trg_hitos_partido_bloquear_torneo_cerrado ON HITOS_PARTIDO;
CREATE TRIGGER trg_hitos_partido_bloquear_torneo_cerrado
BEFORE INSERT OR UPDATE OR DELETE ON HITOS_PARTIDO
FOR EACH ROW EXECUTE FUNCTION fn_bloquear_escritura_torneo_cerrado();
