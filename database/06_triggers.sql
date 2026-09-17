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

-- CONVOCADO_A_PARTIDO lleva el trigger desde
-- gestionar-partido-alineaciones-plan.md (H4-eng): su Fecha_Modificacion no es
-- solo informativa, es el ETag que usa ConvocadoAPartidoService para detectar
-- que otro operador tocó la convocatoria entre el GET y el PUT.
CREATE TRIGGER trg_convocado_upd_fecha
BEFORE UPDATE ON CONVOCADO_A_PARTIDO
FOR EACH ROW EXECUTE FUNCTION fn_actualizar_fecha_modificacion();

-- ------------------------------------------------------------
-- Tope de titulares por equipo (modo-vivo-sustituciones-cierre-plan.md,
-- Área 1, T16 — reversión explícita de la Decisión Audit #12 del plan
-- anterior; el pedido dejó de tratarse como "diferido a propósito" cuando
-- el usuario lo pidió de nuevo con evidencia concreta, ver ese plan).
--
-- Espejo, a nivel DB, del guard que ConvocadoAPartidoService ya aplica en
-- Python (reemplazar/agregar) — acá cierra la carrera de 2 requests
-- concurrentes cerca del tope (Eng subagent hallazgo alto #7): el
-- `SELECT COUNT(*)` de Python, sin lock, tiene la misma ventana TOCTOU que
-- fn_validar_hito_partido tenía para Fin_Partido antes del índice único
-- (T15/uq_hitos_partido_fin_unico) — acá no se puede resolver con un
-- índice único simple (el tope es un número, no una unicidad), así que la
-- herramienta es un lock de fila sobre el PARTIDO, no sobre el convocado.
--
-- Solo mira altas/cambios que MARCAN titular (Titular=TRUE): bajar a
-- suplente o convocar sin marcar titular nunca puede violar un tope
-- superior.
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_validar_tope_titulares()
RETURNS TRIGGER AS $$
DECLARE
    v_equipo_id INT;
    v_maximo INT;
    v_actuales INT;
BEGIN
    IF NOT NEW.Titular THEN
        RETURN NEW;
    END IF;

    -- Lock de fila del PARTIDO (no de CONVOCADO_A_PARTIDO): serializa 2
    -- altas/cambios concurrentes de la convocatoria del MISMO partido sin
    -- bloquear la convocatoria de otros partidos.
    PERFORM 1 FROM PARTIDOS WHERE ID = NEW.Partido_ID FOR UPDATE;

    -- ¿A cuál de los dos equipos de este partido pertenece el perfil? Mismo
    -- criterio que ConvocadoAPartidoService._perfiles_validos
    -- (vw_jugadores_activos_por_equipo, 04_views.sql).
    SELECT v.Equipo_ID INTO v_equipo_id
      FROM vw_jugadores_activos_por_equipo v
      JOIN PARTIDOS p ON p.Torneo_ID = v.Torneo_ID
     WHERE p.ID = NEW.Partido_ID
       AND v.Jugador_Perfil_ID = NEW.Jugador_Perfil_ID
       AND v.Equipo_ID IN (p.EQUIPOS_ID_LOCAL, p.EQUIPOS_ID_VISITANTE)
     LIMIT 1;

    -- Perfil ajeno a los dos equipos: no es este trigger el que lo rechaza
    -- (el service ya lo valida antes con un mensaje específico) — defensa
    -- en profundidad sin duplicar ese mensaje acá.
    IF v_equipo_id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT COALESCE(t.Maximo_Titulares_Permitido, m.Tamano_Equipo) INTO v_maximo
      FROM PARTIDOS p
      JOIN TORNEO t ON t.ID = p.Torneo_ID
      JOIN MODALIDAD m ON m.ID = t.Modalidad_ID
     WHERE p.ID = NEW.Partido_ID;

    SELECT COUNT(*) INTO v_actuales
      FROM CONVOCADO_A_PARTIDO c
      JOIN vw_jugadores_activos_por_equipo v2 ON v2.Jugador_Perfil_ID = c.Jugador_Perfil_ID
      JOIN PARTIDOS p2 ON p2.ID = c.Partido_ID AND p2.Torneo_ID = v2.Torneo_ID
     WHERE c.Partido_ID = NEW.Partido_ID
       AND c.Titular = TRUE
       AND v2.Equipo_ID = v_equipo_id
       AND c.ID <> COALESCE(NEW.ID, -1);

    IF v_actuales >= v_maximo THEN
        RAISE EXCEPTION 'Ya hay % titular(es) marcado(s) para este equipo — el máximo permitido es %.',
            v_actuales, v_maximo;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_convocado_validar_tope_titulares
BEFORE INSERT OR UPDATE OF Titular ON CONVOCADO_A_PARTIDO
FOR EACH ROW EXECUTE FUNCTION fn_validar_tope_titulares();

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
-- Desempate de eliminatoria: tiempo extra y penales (D5/§7, SPEC-REVIEW
-- S7/F2) suma acá el chequeo "Corrido => Manual" — reusa esta función
-- porque YA cruza TORNEO contra otra tabla, en vez de un trigger nuevo. El
-- trigger es column-scoped (`UPDATE OF ...`), así que Metodo_Desempate_
-- Eliminatoria se agrega a esa lista más abajo o el guard nunca corre.
-- El INSERT queda estructuralmente inguardable acá (CONFIGURACION_TIEMPO_
-- TORNEO tiene FK a TORNEO — en BEFORE INSERT esa fila todavía no existe,
-- Tipo_Cronometro lee NULL): lo cubre TorneoService.create en Python. La
-- dirección inversa (pasar Tipo_Cronometro a 'Corrido' en un torneo ya en
-- 'Penales_Directo') también es Python (TorneoService.update baja el
-- método a 'Manual'), no un segundo trigger cruzando en la dirección
-- opuesta — misma regla de la casa que el comentario de :360-366 de abajo.
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

CREATE TRIGGER trg_torneo_validar_modalidad
BEFORE INSERT OR UPDATE OF Disciplina_ID, Modalidad_ID, Metodo_Desempate_Eliminatoria ON TORNEO
FOR EACH ROW EXECUTE FUNCTION fn_validar_torneo_modalidad();

-- ------------------------------------------------------------
-- Funcion y trigger: Usuario_ID de una fila de ASIGNACION_TORNEO_ADMIN
-- debe ser una cuenta Rol='TorneoAdmin' (rbac-licencias-torneos-plan.md,
-- §3.2). Red de seguridad para un INSERT crudo — el mensaje legible para
-- el admin ya lo da AsignacionTorneoAdminService antes de llegar acá,
-- mismo doble-cinturon que fn_validar_torneo_modalidad.
--
-- Valida solo en el momento de INSERT/UPDATE de ESTA fila — no revalida
-- si el usuario cambia de Rol despues (el "catalogo" acá SI puede cambiar
-- mid-life, a diferencia de Disciplina/Modalidad). Ese caso lo cubre
-- UsuarioService.update() en Python, desactivando las filas Activo del
-- usuario cuando su Rol deja de ser 'TorneoAdmin' — no un segundo trigger
-- cruzando en la direccion opuesta.
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_validar_asignacion_torneo_admin_rol()
RETURNS TRIGGER AS $$
DECLARE
    v_rol VARCHAR(20);
BEGIN
    SELECT Rol INTO v_rol FROM USUARIOS WHERE ID = NEW.Usuario_ID;
    IF v_rol IS NULL THEN
        RAISE EXCEPTION 'El usuario indicado no existe.';
    END IF;
    IF v_rol <> 'TorneoAdmin' THEN
        RAISE EXCEPTION 'Solo se puede asignar torneos a cuentas con rol TorneoAdmin (esta cuenta es %).', v_rol;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_asignacion_validar_rol
BEFORE INSERT OR UPDATE OF Usuario_ID ON ASIGNACION_TORNEO_ADMIN
FOR EACH ROW EXECUTE FUNCTION fn_validar_asignacion_torneo_admin_rol();

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
-- Función y trigger: slug de DISCIPLINA (portal-publico-feed-partidos-
-- plan.md, E-B2). Único mecanismo de alta real de una disciplina fuera
-- de 05_seed.sql/11_catalogo_disciplinas.sql (routes/disciplinas.py no
-- tiene POST), así que el slug se genera acá, no en Python — evita un
-- slugify duplicado del lado del cliente que tenga que coincidir por
-- casualidad con el que generó un deep link ya compartido.
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_generar_disciplina_slug()
RETURNS TRIGGER AS $$
BEGIN
    -- Ojo con M7: en UPDATE solo si Slug todavía es NULL — un rename vía
    -- PATCH /disciplinas/{id} no debe cambiar (y romper) un deep link ya
    -- compartido.
    IF TG_OP = 'INSERT' OR NEW.Slug IS NULL THEN
        NEW.Slug := regexp_replace(
            regexp_replace(
                translate(lower(NEW.Nombre), 'áéíóúüñ', 'aeiouun'),
                '[^a-z0-9]+', '-', 'g'
            ),
            '(^-+)|(-+$)', '', 'g'
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_disciplina_generar_slug
BEFORE INSERT OR UPDATE OF Nombre ON DISCIPLINA
FOR EACH ROW EXECUTE FUNCTION fn_generar_disciplina_slug();

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

-- ------------------------------------------------------------
-- Cierre de Fase Regular + Llaves + Playoffs
-- (docs/plans/cierre-fase-regular-llaves-playoffs-plan.md, Fase B).
-- fn_marcador_partido/fn_resolver_llave se agregan ANTES de los dos
-- triggers que siguen porque ambos pasan a llamarlas.
-- ------------------------------------------------------------

-- B1: helper compartido — "quién ganó y con qué marcador" para UN
-- partido, sin importar la disciplina. Antes esta lógica estaba
-- duplicada en fn_propagar_ganador_bracket y en
-- fn_validar_partido_eliminacion_desempate; la llave a dos partidos la
-- necesitaría una tercera vez — se extrae una sola vez acá y los dos
-- triggers existentes pasan a llamarla (arreglo en la raíz, no un guard
-- por llamador).
--
-- Contrato (CEO review, corrige la redacción original de la Fase B1):
-- devuelve (ganador_equipo_id, goles_local, goles_visitante), resolviendo
-- GANADOR — no solo goles — en las 3 disciplinas del catálogo:
--   - Walkover: el equipo PRESENTE, 3-0 (Es_Walkover/Walkover_Equipo_Ausente_ID).
--   - 'Corrido' (Tenis/Ajedrez/LoL...): Ganador_Corrido_ID. Goles_Local/
--     Visitante salen NULL — no aplican, y fn_resolver_llave los ignora
--     para estas disciplinas (cuenta victorias de pierna, no goles).
--   - Goles (fútbol/básquet/etc.): cuenta vw_goles_acreditados; empate
--     resuelto por Ganador_Desempate_ID si ya está seteado (NULL si no).
-- Un partido sin ganador resoluble (ej. Corrido sin Ganador_Corrido_ID
-- todavía, o Cancelado) devuelve ganador_equipo_id NULL — no es un error,
-- lo interpreta el llamador (fn_resolver_llave: "esta pierna no aportó
-- una victoria a nadie").
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
        ganador_equipo_id := v_ganador_corrido;   -- puede ser NULL (pierna sin ganador todavía / Cancelada)
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
        ELSE v_ganador_desempate   -- NULL si el empate no está resuelto todavía
    END;
    RETURN NEXT;
    RETURN;
END;
$$ LANGUAGE plpgsql;

-- B2: resuelve el ganador de una llave a DOS partidos (Ida/Vuelta),
-- p_partido_vuelta_id es la VUELTA (la única que carga Partido_Ida_ID).
--
-- `p_ganador_desempate_override`: cuando se llama desde el trigger BEFORE
-- de validación (fn_validar_partido_eliminacion_desempate), la fila de la
-- VUELTA todavía no está físicamente actualizada en PARTIDOS — leer
-- Ganador_Desempate_ID de la tabla devolvería el valor VIEJO, no el que
-- viene en este mismo UPDATE. Se pasa NEW.Ganador_Desempate_ID acá para
-- no repetir ese bug (mismo motivo por el que el validador de partido
-- único usa NEW.Ganador_Desempate_ID directo, nunca una sub-consulta).
-- Desde el trigger AFTER de propagación no hace falta: para entonces la
-- fila ya está commiteada, así que el default NULL (leer de la tabla) ya
-- trae el valor correcto.
--
-- Reglas (CEO review): para una disciplina de goles, suma goles de AMBAS
-- piernas invirtiendo local/visitante de la IDA (la vuelta juega de local
-- quien fue visitante en la ida). Para 'Corrido', cuenta VICTORIAS DE
-- PIERNA (no goles) — 1 a 1 es empate y cae a Ganador_Desempate_ID de la
-- vuelta, igual que un empate de goles. Una pierna Cancelada aporta 0-0 y
-- ninguna victoria de pierna — nunca bloquea la resolución.
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

-- Exige Ganador_Desempate_ID en CUALQUIER partido de una fase Eliminación
-- que termine empatado en goles — no solo los que propagan a un
-- siguiente partido. Es lo que hace que el partido de Tercer Lugar
-- (terminal, sin Partido_Siguiente_ID) también exija resolver el empate:
-- separado del trigger de propagación (Decisión Eng #17) porque un solo
-- trigger condicionado a "tiene siguiente" dejaría pasar ese caso sin
-- validar.
--
-- Fase B4/B5 (llaves a dos partidos) suma dos reglas más, ambas ANTES de
-- la validación de empate de arriba (aplican a cualquier partido de
-- bracket, tenga o no Fase_ID de Eliminación en este chequeo puntual):
--   - F12: la VUELTA no puede finalizar mientras su IDA no esté resuelta
--     (Finalizado o Cancelado) — sin esto, dos operadores de mesa
--     finalizando fuera de orden hacen que fn_resolver_llave agregue
--     contra una ida todavía abierta y avance al equipo equivocado.
--   - Un 0-0 en la IDA es legal (se sale temprano, sin validar nada) — el
--     empate se valida sobre el GLOBAL de la llave, solo al finalizar la
--     VUELTA.
-- Desempate de eliminatoria: tiempo extra y penales (D3/§5, SPEC-REVIEW
-- S4/F3): reglas de FORMA/RANGO/COHERENCIA de las cinco columnas nuevas —
-- intrínsecas a la FILA, no dependen de ida/vuelta/agregado. Extraídas a
-- su propia función (D-A2 sigue valiendo: no es un trigger nuevo, la
-- llama la única función que ya vale como BEFORE UPDATE de PARTIDOS)
-- porque se necesitan desde DOS lugares del cuerpo de abajo: el camino
-- normal de cierre y el carve-out de un PATCH sobre un partido ya
-- Finalizado.
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
    -- Penales_Local/Visitante viajan juntos: los dos o ninguno.
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
        -- El alargue desempató con goles: el marcador ya decide
        -- (fn_marcador_partido nunca llega al ELSE v_ganador_desempate),
        -- así que Ganador_Desempate_ID tiene que seguir NULL acá.
        IF p_ganador_desempate_id IS NOT NULL THEN
            RAISE EXCEPTION 'metodo_desempate_incoherente';
        END IF;
        -- Séptima regla de coherencia (SPEC-REVIEW S3): sin esto,
        -- ('Tiempo_Extra', FALSE) es representable — la misma segunda
        -- fuente de verdad que §0 invoca contra Fase/Fase_ID.
        IF NOT p_hubo_tiempo_extra THEN
            RAISE EXCEPTION 'metodo_desempate_incoherente';
        END IF;
    ELSIF p_metodo_desempate = 'Manual' AND p_ganador_desempate_id IS NULL THEN
        -- 'Manual' sin ganador es un método declarado sin resolver quién
        -- avanza — incoherente, no "falta el método" (ese código es para
        -- el caso inverso, más abajo).
        RAISE EXCEPTION 'metodo_desempate_incoherente';
    END IF;

    -- F1/S3: Ganador_Desempate_ID NOT NULL exige que se sepa CÓMO — cierra
    -- la puerta a seguir grabando desempates ciegos.
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

    -- Carve-out (SPEC-REVIEW F1/F3): hoy esta función es inerte para un
    -- UPDATE sobre una fila ya Finalizada, así que un PATCH directo
    -- escribiendo Penales_* sobre un partido cerrado esquivaría todas las
    -- reglas nuevas. Deja entrar los UPDATEs que tocan cualquiera de las
    -- cinco columnas nuevas — pero ese camino corre SOLO las reglas de
    -- forma/rango/coherencia y termina: nunca vuelve a tomar el lock de
    -- la ida ni llama fn_resolver_llave sobre una llave ya resuelta.
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

    -- Reglas de forma/rango/coherencia (D-S1, S3, F1/F3/S4): inmediatamente
    -- después del gate de estado y ANTES del lock de la ida — para que
    -- también alcancen a un walkover con un Penales_* colgado, plausible y
    -- absurdo (una posición posterior a la salida por Fase_ID IS NULL OR
    -- Es_Walkover, más abajo, las dejaría fuera justo ahí).
    PERFORM fn_validar_forma_desempate(
        NEW.Metodo_Desempate, NEW.Penales_Local, NEW.Penales_Visitante,
        NEW.Hubo_Tiempo_Extra, NEW.Ganador_Desempate_ID,
        NEW.EQUIPOS_ID_LOCAL, NEW.EQUIPOS_ID_VISITANTE
    );

    IF NEW.Partido_Ida_ID IS NOT NULL THEN
        -- FOR UPDATE (accepted obligation del review): dos operadores de
        -- mesa finalizando la ida y la vuelta EN SIMULTÁNEO no deben poder
        -- pasar los dos esta lectura antes de que cualquiera escriba — el
        -- lock de fila serializa la carrera, no solo el chequeo de estado
        -- (que por sí solo es una ventana TOCTOU sin esto).
        SELECT Estado INTO v_estado_ida FROM PARTIDOS WHERE ID = NEW.Partido_Ida_ID FOR UPDATE;
        IF v_estado_ida NOT IN ('Finalizado', 'Cancelado') THEN
            RAISE EXCEPTION 'partido_vuelta_ida_sin_resolver';
        END IF;
    END IF;

    -- 3B-13: un walkover NUNCA está "empatado sin desempate" — es 3-0 por
    -- definición (mismo comentario que antes de esta migración).
    IF NEW.Fase_ID IS NULL OR NEW.Es_Walkover THEN
        RETURN NEW;
    END IF;

    SELECT Tipo INTO v_tipo_fase FROM FASE WHERE ID = NEW.Fase_ID;
    IF v_tipo_fase <> 'Eliminacion' THEN
        RETURN NEW;
    END IF;

    SELECT EXISTS(SELECT 1 FROM PARTIDOS WHERE Partido_Ida_ID = NEW.ID) INTO v_es_ida;
    IF v_es_ida THEN
        -- D4/§6: el desempate solo corresponde a la VUELTA (el GLOBAL) o a
        -- un partido único — una IDA nunca lo escribe.
        IF NEW.Metodo_Desempate IS NOT NULL OR NEW.Penales_Local IS NOT NULL
           OR NEW.Penales_Visitante IS NOT NULL OR NEW.Hubo_Tiempo_Extra THEN
            RAISE EXCEPTION 'desempate_en_ida_no_permitido';
        END IF;
        RETURN NEW;   -- B4: un 0-0 (o cualquier resultado) en la IDA es legal.
    END IF;

    IF NEW.Partido_Ida_ID IS NOT NULL THEN
        SELECT r.ganador_equipo_id INTO v_ganador_agregado
          FROM fn_resolver_llave(NEW.ID, NEW.Ganador_Desempate_ID) r;
        IF v_ganador_agregado IS NULL THEN
            RAISE EXCEPTION 'llave_empatada_en_global_sin_desempate';
        END IF;
    ELSE
        -- Partido único (Formato_Eliminatoria='Unico', o Tercer Lugar,
        -- siempre único) — comportamiento de siempre.
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
--
-- Fase B3 (llaves a dos partidos): un partido de IDA nunca entra acá con
-- nada que propagar (nace sin Partido_Siguiente_ID/Partido_Perdedor_
-- Siguiente_ID propios — "no propaga nada", termina y espera la vuelta).
-- Un partido de VUELTA (Partido_Ida_ID no-NULL) propaga el resultado
-- AGREGADO de fn_resolver_llave, no el de su propio marcador.
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

            -- Fase C1: si el destino es la VUELTA de una llave (tiene
            -- Partido_Ida_ID propio), el mismo ganador entra TAMBIÉN a su
            -- IDA, en el slot INVERTIDO — la vuelta invierte localía
            -- respecto de la ida (EC de diseño: un solo feeder alcanza
            -- para completar los DOS partidos de la llave destino, sin
            -- duplicar el encadenamiento en una segunda columna). No hace
            -- nada si el destino no es una vuelta (Partido_Ida_ID NULL ahí).
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
-- Cierre de Fase Regular + Llaves + Playoffs — bloqueo de escritura en un
-- torneo cerrado (Finding 4 / T3 del review: Torneo.Estado no lo leía
-- NINGÚN servicio, verificado — cerrar_torneo() sin esto no bloqueaba
-- nada). Un solo guard en la capa de trigger cubre los tres puntos de
-- escritura de un resultado (PARTIDOS, EVENTOS_PARTIDO, HITOS_PARTIDO) de
-- una sola vez: el patrón de guard-por-servicio ya demostró tener
-- agujeros (services/partido.py necesitó DOS guards de torneo archivado
-- en dos call-sites distintos, y services/evento_partido.py no tiene
-- ninguno hoy — bug preexistente, señalado pero no corregido acá, ver
-- docs/plans/cierre-fase-regular-llaves-playoffs-plan.md).
--
-- Alcance exacto: UPDATE en PARTIDOS (no INSERT/DELETE — generar un
-- bracket nuevo o rehacer un sorteo no pasa por acá, y de todos modos
-- ninguno de los dos corre sobre un torneo cerrado por regla de negocio
-- del service); INSERT/UPDATE/DELETE en EVENTOS_PARTIDO/HITOS_PARTIDO
-- (ahí es donde vive un gol, una tarjeta, o un Fin_Partido). Sin
-- excepción para cerrar_torneo()/reabrir_torneo(): ninguno de los dos
-- escribe en estas tres tablas (solo tocan TORNEO/FASE), así que no hay
-- conflicto que exceptuar.
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

CREATE TRIGGER trg_partidos_bloquear_torneo_cerrado
BEFORE UPDATE ON PARTIDOS
FOR EACH ROW EXECUTE FUNCTION fn_bloquear_escritura_torneo_cerrado();

CREATE TRIGGER trg_eventos_partido_bloquear_torneo_cerrado
BEFORE INSERT OR UPDATE OR DELETE ON EVENTOS_PARTIDO
FOR EACH ROW EXECUTE FUNCTION fn_bloquear_escritura_torneo_cerrado();

CREATE TRIGGER trg_hitos_partido_bloquear_torneo_cerrado
BEFORE INSERT OR UPDATE OR DELETE ON HITOS_PARTIDO
FOR EACH ROW EXECUTE FUNCTION fn_bloquear_escritura_torneo_cerrado();

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
