-- 41 — TASK-027 (docs/audit/11_BACKLOG_IMPLEMENTACION.md, DB-06): un torneo
-- cerrado es inmutable salvo reapertura. El guard ya cubría eventos, hitos y
-- la edición de partidos; ahora también crear o borrar partidos, las
-- convocatorias y las inscripciones.
--
-- Re-ejecutable. Aplicar con:
--   psql -h 127.0.0.1 -U postgres -d torneos_mvp -1 -f database/41_migracion_bloqueo_torneo_cerrado.sql

CREATE OR REPLACE FUNCTION fn_bloquear_escritura_torneo_cerrado()
RETURNS TRIGGER AS $$
DECLARE
    v_torneo_id INT;
    v_partido_id INT;
    v_estado_torneo VARCHAR(20);
BEGIN
    -- TASK-027 (DB-06): también inscripciones y convocatorias, y en
    -- PARTIDOS también INSERT/DELETE (antes solo UPDATE).
    IF TG_TABLE_NAME IN ('partidos', 'inscripciones_torneo') THEN
        v_torneo_id := COALESCE(NEW.Torneo_ID, OLD.Torneo_ID);
    ELSIF TG_TABLE_NAME = 'convocado_a_partido' THEN
        v_partido_id := COALESCE(NEW.Partido_ID, OLD.Partido_ID);
        SELECT Torneo_ID INTO v_torneo_id FROM PARTIDOS WHERE ID = v_partido_id;
    ELSIF TG_TABLE_NAME = 'eventos_partido' THEN
        v_partido_id := COALESCE(NEW.PARTIDOS_ID, OLD.PARTIDOS_ID);
        SELECT Torneo_ID INTO v_torneo_id FROM PARTIDOS WHERE ID = v_partido_id;
    ELSE -- hitos_partido
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
BEFORE INSERT OR UPDATE OR DELETE ON PARTIDOS
FOR EACH ROW EXECUTE FUNCTION fn_bloquear_escritura_torneo_cerrado();

DROP TRIGGER IF EXISTS trg_convocado_bloquear_torneo_cerrado ON CONVOCADO_A_PARTIDO;
CREATE TRIGGER trg_convocado_bloquear_torneo_cerrado
BEFORE INSERT OR UPDATE OR DELETE ON CONVOCADO_A_PARTIDO
FOR EACH ROW EXECUTE FUNCTION fn_bloquear_escritura_torneo_cerrado();

DROP TRIGGER IF EXISTS trg_inscripciones_torneo_bloquear_torneo_cerrado ON INSCRIPCIONES_TORNEO;
CREATE TRIGGER trg_inscripciones_torneo_bloquear_torneo_cerrado
BEFORE INSERT OR UPDATE OR DELETE ON INSCRIPCIONES_TORNEO
FOR EACH ROW EXECUTE FUNCTION fn_bloquear_escritura_torneo_cerrado();
