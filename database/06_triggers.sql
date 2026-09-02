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

-- EQUIPO_JUGADOR_BASE y CONFIGURACION_TIEMPO_TORNEO también tienen
-- Fecha_Modificacion (gestion-avanzada-equipos-control-mesa-plan.md).
-- HITOS_PARTIDO NO la tiene a propósito (ver el comentario en
-- 01_schema.sql) — no lleva este trigger.
CREATE TRIGGER trg_equipo_jugador_base_upd_fecha
BEFORE UPDATE ON EQUIPO_JUGADOR_BASE
FOR EACH ROW EXECUTE FUNCTION fn_actualizar_fecha_modificacion();

CREATE TRIGGER trg_config_tiempo_torneo_upd_fecha
BEFORE UPDATE ON CONFIGURACION_TIEMPO_TORNEO
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
    -- Motor de Formatos (Decisión Eng #13): un partido de ronda 2+ de un
    -- bracket de Eliminación nace con uno o los dos equipos en NULL
    -- ("Ganador Partido N", TBD) — el trigger de propagación del bracket
    -- los completa después. Nada que validar todavía si algún lado sigue
    -- sin definirse.
    IF NEW.EQUIPOS_ID_LOCAL IS NULL OR NEW.EQUIPOS_ID_VISITANTE IS NULL THEN
        RETURN NEW;
    END IF;

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
-- Funcion y trigger: la Modalidad de un EQUIPO pertenece a su Disciplina.
-- Espejo exacto de fn_validar_torneo_modalidad (arriba) — misma regla,
-- otra tabla (equipos-disciplina-navegacion-plan.md, D-Eng-15). Se duplica
-- la funcion en vez de generalizarla a una sola con parametros porque un
-- trigger BEFORE INSERT/UPDATE solo puede leer NEW de SU tabla; el costo
-- de la duplicacion son 10 lineas, el de la abstraccion seria dynamic SQL.
--
-- Es la red de seguridad para un INSERT crudo (psql, script, seed): el
-- mensaje legible para el admin lo da EquipoService.create antes de
-- llegar acá — mismo doble-cinturon que ya tenia TORNEO.
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_validar_equipo_modalidad()
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

CREATE TRIGGER trg_equipos_validar_modalidad
BEFORE INSERT OR UPDATE OF Disciplina_ID, Modalidad_ID ON EQUIPOS
FOR EACH ROW EXECUTE FUNCTION fn_validar_equipo_modalidad();

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
-- Motor de Formatos (motor-formatos-plantillas-navegacion-plan.md,
-- requerimiento #4). Tres triggers nuevos, mismos tres patrones ya
-- establecidos en este archivo (validación cruzada, propagación,
-- exclusividad) — ninguno introduce infraestructura nueva.
-- ------------------------------------------------------------

-- Un equipo no puede caer en 2 grupos de la MISMA fase — no se puede
-- expresar con un UNIQUE plano porque Fase_ID no vive en GRUPO_EQUIPO
-- (vive en GRUPO, un nivel arriba). Mismo patrón que
-- fn_validar_exclusividad_torneo.
CREATE OR REPLACE FUNCTION fn_validar_equipo_un_grupo_por_fase()
RETURNS TRIGGER AS $$
DECLARE
    v_conflicto INT;
BEGIN
    SELECT COUNT(*) INTO v_conflicto
    FROM GRUPO_EQUIPO ge
    JOIN GRUPO g_new ON g_new.ID = NEW.Grupo_ID
    JOIN GRUPO g_ge  ON g_ge.ID  = ge.Grupo_ID
    WHERE ge.Inscripcion_Torneo_ID = NEW.Inscripcion_Torneo_ID
      AND ge.ID <> COALESCE(NEW.ID, -1)
      AND g_ge.Fase_ID = g_new.Fase_ID;
    IF v_conflicto > 0 THEN
        RAISE EXCEPTION 'equipo_ya_asignado_a_otro_grupo_en_esta_fase';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_grupo_equipo_un_grupo_por_fase
BEFORE INSERT OR UPDATE ON GRUPO_EQUIPO
FOR EACH ROW EXECUTE FUNCTION fn_validar_equipo_un_grupo_por_fase();

-- Exige Ganador_Desempate_ID en CUALQUIER partido de una fase Eliminación
-- que termine empatado en goles — no solo los que propagan a un
-- siguiente partido. Es lo que hace que el partido de Tercer Lugar
-- (terminal, sin Partido_Siguiente_ID) también exija resolver el empate:
-- separado del trigger de propagación (Decisión Eng #17) porque un solo
-- trigger condicionado a "tiene siguiente" dejaría pasar ese caso sin
-- validar.
CREATE OR REPLACE FUNCTION fn_validar_partido_eliminacion_desempate()
RETURNS TRIGGER AS $$
DECLARE
    v_tipo_fase VARCHAR(20);
    v_goles_local INT;
    v_goles_visitante INT;
BEGIN
    -- 3B-13 (docs/plans/cierre-backlog-todos-plan.md): un walkover NUNCA
    -- está "empatado sin desempate" — es 3-0 por definición, así que este
    -- chequeo no aplica (sin este AND, un walkover en Eliminación con 0
    -- eventos reales de cada lado se vería como 0-0 y el trigger lo
    -- rechazaría pidiendo un Ganador_Desempate_ID que no tiene sentido acá).
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

CREATE TRIGGER trg_partido_validar_desempate
BEFORE UPDATE ON PARTIDOS
FOR EACH ROW EXECUTE FUNCTION fn_validar_partido_eliminacion_desempate();

-- Propaga el resultado de un partido de bracket: el GANADOR avanza vía
-- Partido_Siguiente_ID/Slot_Siguiente (a la ronda siguiente o a la
-- Final), y el PERDEDOR de una semifinal avanza vía
-- Partido_Perdedor_Siguiente_ID/Slot_Perdedor_Siguiente (al partido de
-- Tercer Lugar — Decisión Eng #18: el perdedor se calcula en el mismo
-- trigger, ya con el ganador resuelto en la misma fila, sin un tercer
-- trigger aparte). Corre AFTER el de validación de arriba, así que si
-- hubo empate, Ganador_Desempate_ID ya está garantizado no-NULL acá.
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

        -- 3B-13: un walkover resuelve el ganador directo por
        -- Walkover_Equipo_Ausente_ID (el OTRO equipo) — no hay eventos
        -- reales que contar (nadie jugó), así que el conteo normal de
        -- abajo se salta entero para estas filas.
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
                ELSE NEW.Ganador_Desempate_ID     -- ya validado NOT NULL por el trigger BEFORE si hubo empate
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

CREATE TRIGGER trg_partido_propagar_bracket
AFTER UPDATE ON PARTIDOS
FOR EACH ROW EXECUTE FUNCTION fn_propagar_ganador_bracket();
-- No dispara para partidos de Liga/Grupos (ambas columnas de "siguiente"
-- son NULL ahí): la propagación es exclusiva de partidos de bracket.

-- ------------------------------------------------------------
-- Motor de Tiempos + Control de Mesa en vivo
-- (gestion-avanzada-equipos-control-mesa-plan.md, Fase 3). Tres triggers
-- nuevos, mismos patrones ya establecidos en este archivo (validación
-- cruzada, propagación de estado, validación condicionada a config).
-- ------------------------------------------------------------

-- Valida secuencia y coherencia de un Hito: un torneo Corrido no admite
-- hitos de período, Numero_Periodo solo aplica (y en rango) a hitos de
-- período, y un mismo hito (tipo+período) no se repite en el mismo
-- partido — salvo Pausa/Reanudacion, que sí pueden pasar varias veces.
-- La secuencia ESTRICTA ("no Fin sin Inicio previo") queda del lado de
-- HitoPartidoService: requiere consultar qué hitos previos existen y es
-- la misma regla que decide qué botones habilita la UI — server-side
-- como defensa en profundidad, pero la fuente de la regla es una sola
-- función de servicio, no duplicada en SQL y en Python.
CREATE OR REPLACE FUNCTION fn_validar_hito_partido()
RETURNS TRIGGER AS $$
DECLARE
    v_tipo_cronometro VARCHAR(20);
    v_cantidad_periodos INT;
    v_ya_existe INT;
BEGIN
    SELECT c.Tipo_Cronometro, c.Cantidad_Periodos
      INTO v_tipo_cronometro, v_cantidad_periodos
      FROM PARTIDOS p
      JOIN CONFIGURACION_TIEMPO_TORNEO c ON c.Torneo_ID = p.Torneo_ID
     WHERE p.ID = NEW.Partido_ID;

    IF v_tipo_cronometro IS NULL THEN
        RAISE EXCEPTION 'Este torneo todavia no tiene configuracion de tiempos.';
    END IF;

    IF v_tipo_cronometro = 'Corrido' AND NEW.Tipo_Hito IN ('Inicio_Periodo', 'Fin_Periodo') THEN
        RAISE EXCEPTION 'Este torneo usa cronometro corrido, no admite hitos de periodo.';
    END IF;

    IF NEW.Tipo_Hito IN ('Inicio_Periodo', 'Fin_Periodo') THEN
        IF NEW.Numero_Periodo IS NULL OR NEW.Numero_Periodo < 1 OR NEW.Numero_Periodo > v_cantidad_periodos THEN
            RAISE EXCEPTION 'Numero de periodo invalido para este torneo.';
        END IF;
    ELSIF NEW.Numero_Periodo IS NOT NULL THEN
        RAISE EXCEPTION 'Numero_Periodo solo aplica a hitos de periodo.';
    END IF;

    IF NEW.Tipo_Hito NOT IN ('Pausa', 'Reanudacion') THEN
        SELECT COUNT(*) INTO v_ya_existe
          FROM HITOS_PARTIDO
         WHERE Partido_ID = NEW.Partido_ID
           AND Tipo_Hito = NEW.Tipo_Hito
           AND Numero_Periodo IS NOT DISTINCT FROM NEW.Numero_Periodo
           AND ID <> COALESCE(NEW.ID, -1);
        IF v_ya_existe > 0 THEN
            RAISE EXCEPTION 'hito_ya_registrado';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_hito_partido_validar
BEFORE INSERT OR UPDATE ON HITOS_PARTIDO
FOR EACH ROW EXECUTE FUNCTION fn_validar_hito_partido();

-- Sincroniza PARTIDOS.Estado con los hitos de inicio/fin de partido —
-- mismo patrón que fn_cerrar_torneo_libera_jugadores (un hito de dominio
-- dispara un efecto colateral en otra tabla). El PATCH /partidos/{id}
-- directo (estado='En curso'/'Finalizado') sigue funcionando sin cambios;
-- se recomienda que el dashboard dispare el Hito en su lugar para que
-- vw_duracion_partido tenga siempre un Inicio_Partido auditable.
CREATE OR REPLACE FUNCTION fn_hito_sincroniza_estado_partido()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.Tipo_Hito = 'Inicio_Partido' THEN
        UPDATE PARTIDOS SET Estado = 'En curso' WHERE ID = NEW.Partido_ID AND Estado = 'Programado';
    ELSIF NEW.Tipo_Hito = 'Fin_Partido' THEN
        UPDATE PARTIDOS SET Estado = 'Finalizado' WHERE ID = NEW.Partido_ID AND Estado = 'En curso';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_hito_sincroniza_estado
AFTER INSERT ON HITOS_PARTIDO
FOR EACH ROW EXECUTE FUNCTION fn_hito_sincroniza_estado_partido();

-- Exige Ganador_Corrido_ID al finalizar un partido de un torneo 'Corrido'
-- — mismo patrón exacto que fn_validar_partido_eliminacion_desempate, con
-- la disciplina de origen distinta (Tipo_Cronometro en vez de FASE.Tipo).
-- No colisiona con ese otro trigger: cada uno mira su propia columna de
-- configuración, y un partido Corrido normalmente no tiene FASE.Tipo='Eliminacion'.
CREATE OR REPLACE FUNCTION fn_validar_ganador_corrido()
RETURNS TRIGGER AS $$
DECLARE
    v_tipo_cronometro VARCHAR(20);
BEGIN
    IF NEW.Estado = 'Finalizado' AND OLD.Estado <> 'Finalizado' THEN
        SELECT Tipo_Cronometro INTO v_tipo_cronometro
          FROM CONFIGURACION_TIEMPO_TORNEO WHERE Torneo_ID = NEW.Torneo_ID;
        IF v_tipo_cronometro = 'Corrido' AND NEW.Ganador_Corrido_ID IS NULL THEN
            RAISE EXCEPTION 'partido_corrido_sin_ganador';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_partido_validar_ganador_corrido
BEFORE UPDATE ON PARTIDOS
FOR EACH ROW EXECUTE FUNCTION fn_validar_ganador_corrido();

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
