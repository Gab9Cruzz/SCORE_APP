-- ============================================================
-- 24_migracion_limites_y_walkover.sql
-- 3B-4 (límite de plantilla de fútbol), 3B-10 (cupo máximo de
-- inscripciones por torneo) y 3B-13 (walkover/retiro) —
-- docs/plans/cierre-backlog-todos-plan.md, decisiones confirmadas con el
-- usuario el 2026-09-02 — para una base YA provisionada (torneos_mvp). La
-- secuencia 01-06 ya quedó actualizada al estado final — mismo criterio
-- que 07/08/09/12/13/14/18/19/20/21/22/23.
--
-- Numerada 24 (sigue a 23_migracion_archivar_torneo_grupo.sql).
--
-- Aditiva pura + un backfill puntual (Fútbol 11 = 25, el único número que
-- el usuario dio — el resto de las modalidades de equipo grande quedan
-- sin tope hasta que alguien pida uno real para ellas):
--   - MODALIDAD.Tamano_Plantilla_Max (nullable)
--   - TORNEO.Cupo_Maximo_Inscripciones (nullable) y
--     TORNEO.Permite_Walkover_Grupos (default FALSE — ningún torneo
--     existente cambia de comportamiento)
--   - PARTIDOS.Es_Walkover/Walkover_Equipo_Ausente_ID (default FALSE/NULL)
--   - vw_resultados_partidos reemplazada (agrega el 3-0 fijo para
--     Es_Walkover, ver el comentario completo en 04_views.sql)
--   - fn_validar_partido_eliminacion_desempate y fn_propagar_ganador_bracket
--     reemplazadas (saltean el conteo de goles reales cuando Es_Walkover)
--
-- Re-ejecutable: ADD COLUMN / CREATE CONSTRAINT guardados con IF NOT
-- EXISTS o un chequeo contra pg_constraint, CREATE OR REPLACE
-- VIEW/FUNCTION, y el UPDATE de backfill solo toca la fila si todavía no
-- tiene el valor (no pisa un valor que un admin ya haya ajustado a mano).
-- ============================================================

-- ------------------------------------------------------------
-- PARTE A — 3B-4: MODALIDAD.Tamano_Plantilla_Max
-- ------------------------------------------------------------
ALTER TABLE MODALIDAD ADD COLUMN IF NOT EXISTS Tamano_Plantilla_Max INT;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_modalidad_plantilla_max') THEN
        ALTER TABLE MODALIDAD
            ADD CONSTRAINT chk_modalidad_plantilla_max CHECK (
                Tamano_Plantilla_Max IS NULL OR Tamano_Plantilla_Max >= Tamano_Equipo
            );
    END IF;
END $$;

UPDATE MODALIDAD m
   SET Tamano_Plantilla_Max = 25
  FROM DISCIPLINA d
 WHERE d.ID = m.Disciplina_ID
   AND d.Nombre = 'Fútbol'
   AND m.Nombre = 'Fútbol 11'
   AND m.Tamano_Plantilla_Max IS NULL;

-- ------------------------------------------------------------
-- PARTE B — 3B-10: TORNEO.Cupo_Maximo_Inscripciones
-- ------------------------------------------------------------
ALTER TABLE TORNEO ADD COLUMN IF NOT EXISTS Cupo_Maximo_Inscripciones INT;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_torneo_cupo_maximo') THEN
        ALTER TABLE TORNEO
            ADD CONSTRAINT chk_torneo_cupo_maximo CHECK (Cupo_Maximo_Inscripciones IS NULL OR Cupo_Maximo_Inscripciones > 0);
    END IF;
END $$;

-- ------------------------------------------------------------
-- PARTE C — 3B-13: TORNEO.Permite_Walkover_Grupos + PARTIDOS.Es_Walkover
-- ------------------------------------------------------------
ALTER TABLE TORNEO ADD COLUMN IF NOT EXISTS Permite_Walkover_Grupos BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE PARTIDOS ADD COLUMN IF NOT EXISTS Es_Walkover BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE PARTIDOS ADD COLUMN IF NOT EXISTS Walkover_Equipo_Ausente_ID INT;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_partidos_walkover_ausente') THEN
        ALTER TABLE PARTIDOS
            ADD CONSTRAINT fk_partidos_walkover_ausente FOREIGN KEY (Walkover_Equipo_Ausente_ID) REFERENCES EQUIPOS(ID);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_partidos_walkover') THEN
        ALTER TABLE PARTIDOS
            ADD CONSTRAINT chk_partidos_walkover CHECK (
                (NOT Es_Walkover AND Walkover_Equipo_Ausente_ID IS NULL)
             OR (Es_Walkover AND Walkover_Equipo_Ausente_ID IS NOT NULL)
            );
    END IF;
END $$;

-- Mismo texto que la versión final en 04_views.sql.
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
    p.Walkover_Equipo_Ausente_ID
FROM PARTIDOS p
JOIN EQUIPOS el    ON el.ID    = p.EQUIPOS_ID_LOCAL
JOIN EQUIPOS ev_eq ON ev_eq.ID = p.EQUIPOS_ID_VISITANTE
LEFT JOIN vw_goles_acreditados ga ON ga.PARTIDOS_ID = p.ID
GROUP BY p.ID, p.TORNEO_ID, el.ID, el.Nombre, ev_eq.ID, ev_eq.Nombre,
         p.Fecha_Partido, p.Jornada, p.Fase, p.Grupo, p.Fase_ID, p.Grupo_ID, p.Estado,
         p.Es_Walkover, p.Walkover_Equipo_Ausente_ID;

-- Mismo texto que la versión final en 06_triggers.sql.
CREATE OR REPLACE FUNCTION fn_validar_partido_eliminacion_desempate()
RETURNS TRIGGER AS $$
DECLARE
    v_tipo_fase VARCHAR(20);
    v_goles_local INT;
    v_goles_visitante INT;
BEGIN
    IF NEW.Estado = 'Finalizado' AND OLD.Estado <> 'Finalizado' AND NEW.Fase_ID IS NOT NULL
       AND NOT NEW.Es_Walkover THEN
        SELECT Tipo INTO v_tipo_fase FROM FASE WHERE ID = NEW.Fase_ID;
        IF v_tipo_fase = 'Eliminacion' THEN
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
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fn_propagar_ganador_bracket()
RETURNS TRIGGER AS $$
DECLARE
    v_ganador_id INT;
    v_perdedor_id INT;
    v_goles_local INT;
    v_goles_visitante INT;
BEGIN
    IF NEW.Estado = 'Finalizado' AND OLD.Estado <> 'Finalizado'
       AND (NEW.Partido_Siguiente_ID IS NOT NULL OR NEW.Partido_Perdedor_Siguiente_ID IS NOT NULL) THEN

        IF NEW.Es_Walkover THEN
            v_ganador_id := CASE WHEN NEW.Walkover_Equipo_Ausente_ID = NEW.EQUIPOS_ID_LOCAL
                                  THEN NEW.EQUIPOS_ID_VISITANTE ELSE NEW.EQUIPOS_ID_LOCAL END;
        ELSE
            SELECT
                COUNT(*) FILTER (WHERE ga.Equipo_Acreditado = NEW.EQUIPOS_ID_LOCAL),
                COUNT(*) FILTER (WHERE ga.Equipo_Acreditado = NEW.EQUIPOS_ID_VISITANTE)
              INTO v_goles_local, v_goles_visitante
              FROM vw_goles_acreditados ga
             WHERE ga.PARTIDOS_ID = NEW.ID;

            v_ganador_id := CASE
                WHEN v_goles_local > v_goles_visitante THEN NEW.EQUIPOS_ID_LOCAL
                WHEN v_goles_visitante > v_goles_local THEN NEW.EQUIPOS_ID_VISITANTE
                ELSE NEW.Ganador_Desempate_ID
            END;
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
