-- 34 — TASK-008 (docs/audit/11_BACKLOG_IMPLEMENTACION.md, FUN-02):
-- validar la pertenencia del jugador a un partido por FECHA.
--
-- fn_validar_jugador_partido exigía además Estado = 'Activo' HOY, así que
-- tras un traspaso o una baja no se podía completar el acta de un partido
-- anterior, aunque el jugador sí estaba en el equipo esa fecha. Ahora vale
-- la membresía Activa, o Inactiva/Traspasada con Fecha_Fin, que cubría la
-- fecha del partido. 'Suspendido' sigue rechazado.
--
-- Re-ejecutable: solo reemplaza la función (el trigger no cambia).
-- Aplicar con: psql -h 127.0.0.1 -U postgres -d torneos_mvp -1 -f database/34_migracion_validar_jugador_por_fecha.sql

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
    -- En UPDATE solo revalida si cambió algo relevante
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
       -- TASK-008 (FUN-02): vale la membresía que CUBRÍA la fecha del
       -- partido, aunque hoy esté cerrada (traspaso o baja posteriores).
       -- Un cierre sin Fecha_Fin no tiene vigencia conocida y no cuenta;
       -- 'Suspendido' tampoco.
       AND (je.Estado = 'Activo'
            OR (je.Estado IN ('Inactivo', 'Traspasado') AND je.Fecha_Fin IS NOT NULL))
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
           AND (je.Estado = 'Activo'
                OR (je.Estado IN ('Inactivo', 'Traspasado') AND je.Fecha_Fin IS NOT NULL))
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
