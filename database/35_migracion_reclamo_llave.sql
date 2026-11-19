-- 35 — TASK-009 (docs/audit/11_BACKLOG_IMPLEMENTACION.md, FUN-03): reclamo
-- sobre un partido de llave ya cerrado.
--
-- Decisión del propietario (2026-11-18): si un equipo ya avanzó de llave,
-- el resultado no se cambia anulando eventos; si prospera un reclamo, se
-- resuelve a favor del equipo que perdió en cancha y ese equipo avanza.
-- Ganador_Reclamo_ID guarda ese ganador; fn_marcador_partido y
-- fn_resolver_llave lo devuelven como ganador (el marcador no cambia).
--
-- Re-ejecutable: ADD COLUMN IF NOT EXISTS, constraints guardadas contra
-- pg_constraint, CREATE OR REPLACE de las dos funciones.
-- Aplicar con: psql -h 127.0.0.1 -U postgres -d torneos_mvp -1 -f database/35_migracion_reclamo_llave.sql

ALTER TABLE PARTIDOS ADD COLUMN IF NOT EXISTS Ganador_Reclamo_ID INT;
ALTER TABLE PARTIDOS ADD COLUMN IF NOT EXISTS Reclamo_Motivo VARCHAR(500);
ALTER TABLE PARTIDOS ADD COLUMN IF NOT EXISTS Reclamo_Fecha TIMESTAMP;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_partidos_ganador_reclamo') THEN
        ALTER TABLE PARTIDOS
            ADD CONSTRAINT fk_partidos_ganador_reclamo FOREIGN KEY (Ganador_Reclamo_ID) REFERENCES EQUIPOS(ID);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_partidos_reclamo') THEN
        ALTER TABLE PARTIDOS
            ADD CONSTRAINT chk_partidos_reclamo CHECK (
                (Ganador_Reclamo_ID IS NULL AND Reclamo_Motivo IS NULL AND Reclamo_Fecha IS NULL)
             OR (Ganador_Reclamo_ID IS NOT NULL AND Reclamo_Motivo IS NOT NULL AND Reclamo_Fecha IS NOT NULL
                 AND Ganador_Reclamo_ID IN (EQUIPOS_ID_LOCAL, EQUIPOS_ID_VISITANTE))
            );
    END IF;
END $$;

CREATE OR REPLACE FUNCTION fn_marcador_partido(p_partido_id INT)
RETURNS TABLE(ganador_equipo_id INT, goles_local INT, goles_visitante INT) AS $$
DECLARE
    v_local INT;
    v_visitante INT;
    v_es_walkover BOOLEAN;
    v_walkover_ausente INT;
    v_ganador_desempate INT;
    v_ganador_corrido INT;
    v_ganador_reclamo INT;
    v_torneo_id INT;
    v_tipo_cronometro VARCHAR(20);
    v_gl INT;
    v_gv INT;
BEGIN
    SELECT EQUIPOS_ID_LOCAL, EQUIPOS_ID_VISITANTE, Es_Walkover, Walkover_Equipo_Ausente_ID,
           Ganador_Desempate_ID, Ganador_Corrido_ID, Torneo_ID, Ganador_Reclamo_ID
      INTO v_local, v_visitante, v_es_walkover, v_walkover_ausente,
           v_ganador_desempate, v_ganador_corrido, v_torneo_id, v_ganador_reclamo
      FROM PARTIDOS WHERE ID = p_partido_id;

    IF v_es_walkover THEN
        ganador_equipo_id := CASE WHEN v_walkover_ausente = v_local THEN v_visitante ELSE v_local END;
        goles_local := CASE WHEN v_walkover_ausente = v_local THEN 0 ELSE 3 END;
        goles_visitante := CASE WHEN v_walkover_ausente = v_visitante THEN 0 ELSE 3 END;
        ganador_equipo_id := COALESCE(v_ganador_reclamo, ganador_equipo_id);  -- TASK-009: reclamo
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT Tipo_Cronometro INTO v_tipo_cronometro FROM CONFIGURACION_TIEMPO_TORNEO WHERE Torneo_ID = v_torneo_id;

    IF v_tipo_cronometro = 'Corrido' THEN
        ganador_equipo_id := v_ganador_corrido;   -- puede ser NULL (pierna sin ganador todavía / Cancelada)
        goles_local := NULL;
        goles_visitante := NULL;
        ganador_equipo_id := COALESCE(v_ganador_reclamo, ganador_equipo_id);  -- TASK-009: reclamo
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
        ELSE v_ganador_desempate   -- NULL si el empate no está resuelto todavía
    END;
    ganador_equipo_id := COALESCE(v_ganador_reclamo, ganador_equipo_id);  -- TASK-009: reclamo
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
    v_ganador_reclamo INT;
    v_tipo_cronometro VARCHAR(20);
    ida_ganador INT; ida_gl INT; ida_gv INT;
    vta_ganador INT; vta_gl INT; vta_gv INT;
    v_gl_total INT;
    v_gv_total INT;
    v_victorias_local INT := 0;
    v_victorias_visit INT := 0;
BEGIN
    SELECT Partido_Ida_ID, Torneo_ID, EQUIPOS_ID_LOCAL, EQUIPOS_ID_VISITANTE, Ganador_Desempate_ID,
           Ganador_Reclamo_ID
      INTO v_ida_id, v_torneo_id, v_local_vta, v_visit_vta, v_ganador_desempate, v_ganador_reclamo
      FROM PARTIDOS WHERE ID = p_partido_vuelta_id;

    -- TASK-009: un reclamo resuelto sobre la vuelta decide la llave entera,
    -- sin importar el agregado.
    IF v_ganador_reclamo IS NOT NULL THEN
        ganador_equipo_id := v_ganador_reclamo;
        RETURN NEXT;
        RETURN;
    END IF;

    IF p_ganador_desempate_override IS NOT NULL THEN
        v_ganador_desempate := p_ganador_desempate_override;
    END IF;

    -- Mismo FOR UPDATE que el BEFORE trigger de validación (defensa en
    -- profundidad: esta función también se llama desde Python para
    -- resolver el podio, fuera de ese trigger) — bloquea la fila de la
    -- IDA por el resto de esta transacción mientras se lee su marcador,
    -- para que un finalize concurrente de la ida no pise esta lectura.
    IF v_ida_id IS NOT NULL THEN
        PERFORM 1 FROM PARTIDOS WHERE ID = v_ida_id FOR UPDATE;
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
        -- ida_gv (goles del VISITANTE de la ida) es el mismo equipo que
        -- v_local_vta (local de la vuelta) — de ahí el cruce.
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
