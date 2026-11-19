-- 36 — TASK-019 (docs/audit/11_BACKLOG_IMPLEMENTACION.md, FUN-14/DB-03):
-- tipos de evento de sistema con código estable.
--
-- Goles, tarjetas y cambios se reconocían por EVENTOS.Nombre, editable y no
-- único: renombrar "Gol" ponía en cero todos los marcadores. Se agrega
-- EVENTOS.Codigo (relleno por nombre para los cinco tipos de sistema), la
-- unicidad de Nombre y Codigo, y vw_goles_acreditados / fn_validar_jugador_
-- partido pasan a comparar por código.
--
-- Se detiene sin tocar nada si hay nombres de evento repetidos: hay que
-- decidir a mano cuál queda.
--
-- Re-ejecutable. Aplicar con:
--   psql -h 127.0.0.1 -U postgres -d torneos_mvp -1 -f database/36_migracion_codigo_eventos.sql

ALTER TABLE EVENTOS ADD COLUMN IF NOT EXISTS Codigo VARCHAR(30);

DO $$
DECLARE
    v_repetidos TEXT;
BEGIN
    SELECT string_agg(Nombre, ', ') INTO v_repetidos
      FROM (SELECT Nombre FROM EVENTOS GROUP BY Nombre HAVING COUNT(*) > 1) r;
    IF v_repetidos IS NOT NULL THEN
        RAISE EXCEPTION 'Hay tipos de evento con el nombre repetido (%): unificalos antes de migrar.', v_repetidos;
    END IF;

    UPDATE EVENTOS SET Codigo = 'GOL'              WHERE Nombre = 'Gol'              AND Codigo IS NULL;
    UPDATE EVENTOS SET Codigo = 'AUTOGOL'          WHERE Nombre = 'Autogol'          AND Codigo IS NULL;
    UPDATE EVENTOS SET Codigo = 'TARJETA_AMARILLA' WHERE Nombre = 'Tarjeta Amarilla' AND Codigo IS NULL;
    UPDATE EVENTOS SET Codigo = 'TARJETA_ROJA'     WHERE Nombre = 'Tarjeta Roja'     AND Codigo IS NULL;
    UPDATE EVENTOS SET Codigo = 'CAMBIO'           WHERE Nombre = 'Cambio'           AND Codigo IS NULL;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'unique_eventos_nombre') THEN
        ALTER TABLE EVENTOS ADD CONSTRAINT unique_eventos_nombre UNIQUE (Nombre);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'unique_eventos_codigo') THEN
        ALTER TABLE EVENTOS ADD CONSTRAINT unique_eventos_codigo UNIQUE (Codigo);
    END IF;
END $$;

CREATE OR REPLACE VIEW vw_goles_acreditados AS
SELECT
    ep.ID              AS Evento_Partido_ID,
    ep.PARTIDOS_ID,
    p.TORNEO_ID,
    ep.JUGADOR_ID,
    ep.EQUIPO_ID       AS Equipo_Del_Jugador,
    -- TASK-019: por código, no por nombre. Tipo_Gol conserva sus dos
    -- valores de siempre para las vistas que lo leen.
    (CASE WHEN ev.Codigo = 'AUTOGOL' THEN 'Autogol' ELSE 'Gol' END)::VARCHAR(50) AS Tipo_Gol,
    CASE
        WHEN ev.Codigo = 'AUTOGOL' THEN
            CASE WHEN ep.EQUIPO_ID = p.EQUIPOS_ID_LOCAL
                 THEN p.EQUIPOS_ID_VISITANTE
                 ELSE p.EQUIPOS_ID_LOCAL
            END
        ELSE ep.EQUIPO_ID
    END                AS Equipo_Acreditado,
    ep.MINUTO
FROM EVENTOS_PARTIDO ep
JOIN EVENTOS ev  ON ev.ID = ep.EVENTOS_ID
JOIN PARTIDOS p  ON p.ID  = ep.PARTIDOS_ID
WHERE ep.Estado = 'Registrado'
  AND ev.Codigo IN ('GOL', 'AUTOGOL');

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

    -- TASK-019: por código, no por nombre.
    SELECT (Codigo IS NOT DISTINCT FROM 'CAMBIO') INTO v_es_cambio FROM EVENTOS WHERE ID = NEW.EVENTOS_ID;

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
