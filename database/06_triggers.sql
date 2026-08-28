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

-- TORNEO_GRUPO también tiene Fecha_Modificacion — a diferencia de
-- DISCIPLINA/MODALIDAD (catálogos que casi no cambian), un grupo de
-- torneo SÍ se espera que el admin renombre alguna vez (torneos-admin-plan.md,
-- EC-25), vale la pena trazar cuándo.
CREATE TRIGGER trg_torneo_grupo_upd_fecha
BEFORE UPDATE ON TORNEO_GRUPO
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

-- JUGADOR_PERFIL_DISCIPLINA también tiene Fecha_Modificacion.
-- DISCIPLINA, MODALIDAD y TRASPASOS no la tienen (ver 01_schema.sql), así
-- que no llevan este trigger.
CREATE TRIGGER trg_perfil_disciplina_upd_fecha
BEFORE UPDATE ON JUGADOR_PERFIL_DISCIPLINA
FOR EACH ROW EXECUTE FUNCTION fn_actualizar_fecha_modificacion();

-- ------------------------------------------------------------
-- Función y trigger: coherencia de un evento de partido
--   1. el EQUIPO_ID del evento es uno de los dos que disputan el partido
--   2. el jugador pertenecía a ESE equipo, vigente en la fecha del partido
--   3. si el evento es 'Cambio', el jugador que entra cumple lo mismo
--
-- Desde equipos-jugadores-plan.md: JUGADOR_EQUIPO ya no guarda
-- JUGADOR_ID/EQUIPO_ID directo, sino (Jugador_Perfil_ID,
-- Inscripcion_Torneo_ID). "El jugador pertenecía a ese equipo" ahora se
-- resuelve: perfil de esa persona en la disciplina DEL TORNEO del
-- partido, con una membresía activa cuyo roster (Inscripcion_Torneo_ID)
-- ancla exactamente ese Torneo_ID + ese Equipo_ID.
-- ------------------------------------------------------------
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
-- Función y trigger: TORNEO.Modalidad_ID pertenece a TORNEO.Disciplina_ID.
-- Antes de docs/plans/ediciones-catalogo-disciplinas-plan.md (Decisión A1)
-- esta función también consultaba DISCIPLINA.Tipo para decidir si
-- Modalidad_ID era obligatorio/prohibido — esa columna ya no existe:
-- Modalidad_ID es NOT NULL a nivel de columna (01_schema.sql) para TODA
-- disciplina, así que solo queda una regla real por validar, y esa sí
-- cruza tablas (mismo motivo que fn_validar_equipos_inscritos no es una
-- FK: la regla vive en la combinación de dos tablas).
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_validar_torneo_modalidad()
RETURNS TRIGGER AS $$
DECLARE
    v_modalidad_disciplina INT;
BEGIN
    SELECT Disciplina_ID INTO v_modalidad_disciplina FROM MODALIDAD WHERE ID = NEW.Modalidad_ID;
    IF v_modalidad_disciplina IS NULL THEN
        RAISE EXCEPTION 'La modalidad indicada no existe.';
    END IF;
    IF v_modalidad_disciplina <> NEW.Disciplina_ID THEN
        RAISE EXCEPTION 'La modalidad indicada no pertenece a esta disciplina.';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_torneo_validar_modalidad
BEFORE INSERT OR UPDATE OF Disciplina_ID, Modalidad_ID ON TORNEO
FOR EACH ROW EXECUTE FUNCTION fn_validar_torneo_modalidad();

-- ------------------------------------------------------------
-- Función y trigger: exclusividad de un jugador por torneo.
-- Un mismo perfil de disciplina no puede tener dos membresías Activo al
-- mismo tiempo dentro del mismo TORNEO (aunque sea en dos equipos
-- distintos). No es un UNIQUE plano porque Torneo_ID no vive directo en
-- JUGADOR_EQUIPO — se deriva vía INSCRIPCIONES_TORNEO, evitando
-- denormalizar. El backend atrapa la excepción 'jugador_ya_activo_en_este_torneo'
-- y la traduce al mensaje de la sección Inválidos de la pantalla de
-- registro por lote (ver Fase 2 del plan) — la base es la fuente de
-- verdad, no un chequeo de aplicación saltable desde un script/seed.
-- ------------------------------------------------------------
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

CREATE TRIGGER trg_jugador_equipo_exclusividad
BEFORE INSERT OR UPDATE ON JUGADOR_EQUIPO
FOR EACH ROW EXECUTE FUNCTION fn_validar_exclusividad_torneo();

-- ------------------------------------------------------------
-- Función y trigger: agencia libre automática al finalizar un torneo.
-- Cierra (Estado='Inactivo') todas las membresías Activo de ese torneo.
-- NO toca JUGADOR_PERFIL_DISCIPLINA: no tiene columna de estado
-- activo/libre que "cerrar" — ese estado es derivado (ver
-- vw_estado_perfil_disciplina), así que un jugador con membresía activa
-- en OTRO torneo de la misma disciplina no queda libre por error (EC-10
-- del plan) — no hay campo que este trigger pudiera olvidar actualizar.
-- ------------------------------------------------------------
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

CREATE TRIGGER trg_torneo_finalizado_libera
AFTER UPDATE ON TORNEO
FOR EACH ROW EXECUTE FUNCTION fn_cerrar_torneo_libera_jugadores();

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
    -- (vía perfil de disciplina + roster de ese torneo, ver
    -- fn_validar_jugador_partido)
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
