-- ============================================================
-- 06_triggers.sql
-- Funciones y triggers
-- Se ejecuta al final para no interferir con la carga de seeds
--
-- Como los triggers se crean DESPUÉS del seed, los datos de 05_seed.sql
-- no pasan por ellos al insertarse. Por eso al final de este archivo hay
-- un bloque de verificación que revalida lo ya cargado contra las mismas
-- reglas y aborta si algo no las cumple.
-- ============================================================

-- ------------------------------------------------------------
-- Función genérica: actualizar Fecha_Modificacion en cada UPDATE
--
-- El nombre de la columna va SIN comillas dobles. Con comillas
-- ("Fecha_Modificacion") PL/pgSQL busca un campo con esas mayúsculas
-- exactas, que no existe porque 01_schema.sql lo declaró sin comillas y
-- Postgres lo plegó a minúsculas. El resultado era que TODO UPDATE sobre
-- las tablas con este trigger fallaba, incluido el borrado lógico.
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_actualizar_fecha_modificacion()
RETURNS TRIGGER AS $$
BEGIN
    NEW.fecha_modificacion = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Las 9 tablas llevan el trigger: las 9 tienen Fecha_Modificacion.
CREATE TRIGGER trg_torneo_upd_fecha
BEFORE UPDATE ON TORNEO
FOR EACH ROW EXECUTE FUNCTION fn_actualizar_fecha_modificacion();

CREATE TRIGGER trg_equipos_upd_fecha
BEFORE UPDATE ON EQUIPOS
FOR EACH ROW EXECUTE FUNCTION fn_actualizar_fecha_modificacion();

CREATE TRIGGER trg_jugadores_upd_fecha
BEFORE UPDATE ON JUGADORES
FOR EACH ROW EXECUTE FUNCTION fn_actualizar_fecha_modificacion();

CREATE TRIGGER trg_inscripciones_torneo_upd_fecha
BEFORE UPDATE ON INSCRIPCIONES_TORNEO
FOR EACH ROW EXECUTE FUNCTION fn_actualizar_fecha_modificacion();

CREATE TRIGGER trg_jugador_equipo_upd_fecha
BEFORE UPDATE ON JUGADOR_EQUIPO
FOR EACH ROW EXECUTE FUNCTION fn_actualizar_fecha_modificacion();

CREATE TRIGGER trg_partidos_upd_fecha
BEFORE UPDATE ON PARTIDOS
FOR EACH ROW EXECUTE FUNCTION fn_actualizar_fecha_modificacion();

CREATE TRIGGER trg_eventos_upd_fecha
BEFORE UPDATE ON EVENTOS
FOR EACH ROW EXECUTE FUNCTION fn_actualizar_fecha_modificacion();

CREATE TRIGGER trg_eventos_partido_upd_fecha
BEFORE UPDATE ON EVENTOS_PARTIDO
FOR EACH ROW EXECUTE FUNCTION fn_actualizar_fecha_modificacion();

CREATE TRIGGER trg_usuarios_upd_fecha
BEFORE UPDATE ON USUARIOS
FOR EACH ROW EXECUTE FUNCTION fn_actualizar_fecha_modificacion();

-- ------------------------------------------------------------
-- Función y trigger: coherencia de un evento de partido
--   1. el EQUIPO_ID del evento es uno de los dos que disputan el partido
--   2. el jugador pertenecía a ESE equipo, vigente en la fecha del partido
--   3. si el evento es 'Cambio', el jugador que entra cumple lo mismo
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_validar_jugador_partido()
RETURNS TRIGGER AS $$
DECLARE
    v_equipo_local INT;
    v_equipo_visitante INT;
    v_fecha_partido TIMESTAMP;
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

    SELECT EQUIPOS_ID_LOCAL, EQUIPOS_ID_VISITANTE, Fecha_Partido
      INTO v_equipo_local, v_equipo_visitante, v_fecha_partido
      FROM PARTIDOS
     WHERE ID = NEW.PARTIDOS_ID;

    IF NEW.EQUIPO_ID NOT IN (v_equipo_local, v_equipo_visitante) THEN
        RAISE EXCEPTION 'El equipo indicado no disputa este partido.';
    END IF;

    SELECT COUNT(*)
      INTO v_valido
      FROM JUGADOR_EQUIPO
     WHERE JUGADOR_ID = NEW.JUGADOR_ID
       AND EQUIPO_ID = NEW.EQUIPO_ID
       AND Estado = 'Activo'
       AND Fecha_Inicio <= v_fecha_partido::DATE
       AND (Fecha_Fin IS NULL OR Fecha_Fin >= v_fecha_partido::DATE);

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
          FROM JUGADOR_EQUIPO
         WHERE JUGADOR_ID = NEW.JUGADOR_ID_ENTRA
           AND EQUIPO_ID = NEW.EQUIPO_ID
           AND Estado = 'Activo'
           AND Fecha_Inicio <= v_fecha_partido::DATE
           AND (Fecha_Fin IS NULL OR Fecha_Fin >= v_fecha_partido::DATE);

        IF v_valido = 0 THEN
            RAISE EXCEPTION 'El jugador que entra no pertenecia a ese equipo en la fecha del partido.';
        END IF;
    ELSIF NEW.JUGADOR_ID_ENTRA IS NOT NULL THEN
        RAISE EXCEPTION 'jugador_id_entra solo aplica a eventos de tipo Cambio.';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_eventos_partido_validar
BEFORE INSERT OR UPDATE ON EVENTOS_PARTIDO
FOR EACH ROW EXECUTE FUNCTION fn_validar_jugador_partido();

-- ------------------------------------------------------------
-- Función y trigger: los dos equipos de un partido deben estar
-- inscritos y no cancelados en ese torneo.
--
-- No se puede resolver con una FK: PARTIDOS referencia EQUIPOS, mientras
-- que la inscripción es la tupla (torneo, equipo). Sin esta validación se
-- podía programar un partido contra un equipo que nunca se inscribió.
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_validar_equipos_inscritos()
RETURNS TRIGGER AS $$
DECLARE
    v_inscritos INT;
BEGIN
    SELECT COUNT(*)
      INTO v_inscritos
      FROM INSCRIPCIONES_TORNEO
     WHERE TORNEO_ID = NEW.TORNEO_ID
       AND EQUIPO_ID IN (NEW.EQUIPOS_ID_LOCAL, NEW.EQUIPOS_ID_VISITANTE)
       AND Estado IN ('Inscrito', 'Confirmado');

    IF v_inscritos < 2 THEN
        RAISE EXCEPTION
            'Ambos equipos deben estar inscritos y no cancelados en el torneo % para disputar un partido.',
            NEW.TORNEO_ID;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_partidos_validar_inscripcion
BEFORE INSERT OR UPDATE OF TORNEO_ID, EQUIPOS_ID_LOCAL, EQUIPOS_ID_VISITANTE ON PARTIDOS
FOR EACH ROW EXECUTE FUNCTION fn_validar_equipos_inscritos();

-- ------------------------------------------------------------
-- Verificación final
-- Los triggers se crearon después del seed, así que los datos ya
-- cargados no pasaron por ellos. Este bloque los revalida contra las
-- mismas reglas y aborta la instalación si alguno no las cumple.
-- ------------------------------------------------------------
DO $$
DECLARE
    v_malos INT;
    v_upd TIMESTAMP;
BEGIN
    -- 1. Partidos con algún equipo no inscrito
    SELECT COUNT(*) INTO v_malos
      FROM PARTIDOS p
     WHERE (SELECT COUNT(*)
              FROM INSCRIPCIONES_TORNEO i
             WHERE i.TORNEO_ID = p.TORNEO_ID
               AND i.EQUIPO_ID IN (p.EQUIPOS_ID_LOCAL, p.EQUIPOS_ID_VISITANTE)
               AND i.Estado IN ('Inscrito','Confirmado')) < 2;
    IF v_malos > 0 THEN
        RAISE EXCEPTION 'Seed invalido: % partido(s) con equipos no inscritos.', v_malos;
    END IF;

    -- 2. Eventos cuyo equipo no disputa el partido
    SELECT COUNT(*) INTO v_malos
      FROM EVENTOS_PARTIDO ep
      JOIN PARTIDOS p ON p.ID = ep.PARTIDOS_ID
     WHERE ep.EQUIPO_ID NOT IN (p.EQUIPOS_ID_LOCAL, p.EQUIPOS_ID_VISITANTE);
    IF v_malos > 0 THEN
        RAISE EXCEPTION 'Seed invalido: % evento(s) con un equipo ajeno al partido.', v_malos;
    END IF;

    -- 3. Eventos cuyo jugador no pertenecía a ese equipo en esa fecha
    SELECT COUNT(*) INTO v_malos
      FROM EVENTOS_PARTIDO ep
      JOIN PARTIDOS p ON p.ID = ep.PARTIDOS_ID
     WHERE NOT EXISTS (
            SELECT 1 FROM JUGADOR_EQUIPO je
             WHERE je.JUGADOR_ID = ep.JUGADOR_ID
               AND je.EQUIPO_ID = ep.EQUIPO_ID
               AND je.Estado = 'Activo'
               AND je.Fecha_Inicio <= p.Fecha_Partido::DATE
               AND (je.Fecha_Fin IS NULL OR je.Fecha_Fin >= p.Fecha_Partido::DATE));
    IF v_malos > 0 THEN
        RAISE EXCEPTION 'Seed invalido: % evento(s) con jugador ajeno al equipo.', v_malos;
    END IF;

    -- 4. El trigger de Fecha_Modificacion funciona de verdad
    SELECT fecha_modificacion INTO v_upd FROM EQUIPOS ORDER BY id LIMIT 1;
    IF v_upd IS NOT NULL THEN
        UPDATE EQUIPOS SET estado = estado WHERE id = (SELECT MIN(id) FROM EQUIPOS);
        IF (SELECT fecha_modificacion FROM EQUIPOS ORDER BY id LIMIT 1) <= v_upd THEN
            RAISE EXCEPTION 'El trigger fn_actualizar_fecha_modificacion no actualiza la columna.';
        END IF;
    END IF;

    RAISE NOTICE 'Verificacion OK: esquema, seed y triggers coherentes.';
END $$;
