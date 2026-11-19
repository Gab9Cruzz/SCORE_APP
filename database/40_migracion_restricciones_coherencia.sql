-- 40 — TASK-026 (docs/audit/11_BACKLOG_IMPLEMENTACION.md, DB-01/DB-02):
-- estados obligatorios y coherencia de fechas, rangos y nombres.
--
-- Primero comprueba que no haya filas que las violen y, si las hay, se
-- detiene sin tocar nada y dice cuáles: hay que corregirlas a mano. El
-- cierre de torneo (fn_cerrar_torneo_libera_jugadores) pasa a no dejar una
-- baja anterior al alta.
--
-- Re-ejecutable. Aplicar con:
--   psql -h 127.0.0.1 -U postgres -d torneos_mvp -1 -f database/40_migracion_restricciones_coherencia.sql

DO $$
DECLARE
    v_n INT;
    v_problemas TEXT := '';
BEGIN
    SELECT COUNT(*) INTO v_n FROM DISCIPLINA WHERE Estado IS NULL;
    IF v_n > 0 THEN v_problemas := v_problemas || format('%s filas de DISCIPLINA con Estado nulo; ', v_n); END IF;
    SELECT COUNT(*) INTO v_n FROM MODALIDAD WHERE Estado IS NULL;
    IF v_n > 0 THEN v_problemas := v_problemas || format('%s filas de MODALIDAD con Estado nulo; ', v_n); END IF;
    SELECT COUNT(*) INTO v_n FROM TORNEO WHERE Estado IS NULL;
    IF v_n > 0 THEN v_problemas := v_problemas || format('%s filas de TORNEO con Estado nulo; ', v_n); END IF;
    SELECT COUNT(*) INTO v_n FROM EQUIPOS WHERE Estado IS NULL;
    IF v_n > 0 THEN v_problemas := v_problemas || format('%s filas de EQUIPOS con Estado nulo; ', v_n); END IF;
    SELECT COUNT(*) INTO v_n FROM JUGADORES WHERE Estado IS NULL;
    IF v_n > 0 THEN v_problemas := v_problemas || format('%s filas de JUGADORES con Estado nulo; ', v_n); END IF;
    SELECT COUNT(*) INTO v_n FROM INSCRIPCIONES_TORNEO WHERE Estado IS NULL;
    IF v_n > 0 THEN v_problemas := v_problemas || format('%s filas de INSCRIPCIONES_TORNEO con Estado nulo; ', v_n); END IF;
    SELECT COUNT(*) INTO v_n FROM JUGADOR_EQUIPO WHERE Estado IS NULL;
    IF v_n > 0 THEN v_problemas := v_problemas || format('%s filas de JUGADOR_EQUIPO con Estado nulo; ', v_n); END IF;
    SELECT COUNT(*) INTO v_n FROM TRASPASOS WHERE Estado IS NULL;
    IF v_n > 0 THEN v_problemas := v_problemas || format('%s filas de TRASPASOS con Estado nulo; ', v_n); END IF;
    SELECT COUNT(*) INTO v_n FROM EQUIPO_JUGADOR_BASE WHERE Estado IS NULL;
    IF v_n > 0 THEN v_problemas := v_problemas || format('%s filas de EQUIPO_JUGADOR_BASE con Estado nulo; ', v_n); END IF;
    SELECT COUNT(*) INTO v_n FROM PARTIDOS WHERE Estado IS NULL;
    IF v_n > 0 THEN v_problemas := v_problemas || format('%s filas de PARTIDOS con Estado nulo; ', v_n); END IF;
    SELECT COUNT(*) INTO v_n FROM EVENTOS WHERE Estado IS NULL;
    IF v_n > 0 THEN v_problemas := v_problemas || format('%s filas de EVENTOS con Estado nulo; ', v_n); END IF;
    SELECT COUNT(*) INTO v_n FROM USUARIOS WHERE Estado IS NULL;
    IF v_n > 0 THEN v_problemas := v_problemas || format('%s filas de USUARIOS con Estado nulo; ', v_n); END IF;
    SELECT COUNT(*) INTO v_n FROM EVENTOS_PARTIDO WHERE Estado IS NULL;
    IF v_n > 0 THEN v_problemas := v_problemas || format('%s filas de EVENTOS_PARTIDO con Estado nulo; ', v_n); END IF;
    SELECT COUNT(*) INTO v_n FROM TORNEO WHERE NOT (Fecha_Fin >= Fecha_Inicio);
    IF v_n > 0 THEN v_problemas := v_problemas || format('%s torneos con fecha de fin anterior a la de inicio; ', v_n); END IF;
    SELECT COUNT(*) INTO v_n FROM TORNEO WHERE NOT (Equipos_Por_Grupo IS NULL OR Equipos_Por_Grupo > 0);
    IF v_n > 0 THEN v_problemas := v_problemas || format('%s torneos con Equipos_Por_Grupo <= 0; ', v_n); END IF;
    SELECT COUNT(*) INTO v_n FROM TORNEO WHERE NOT (Clasificados_Por_Grupo IS NULL OR Clasificados_Por_Grupo > 0);
    IF v_n > 0 THEN v_problemas := v_problemas || format('%s torneos con Clasificados_Por_Grupo <= 0; ', v_n); END IF;
    SELECT COUNT(*) INTO v_n FROM TORNEO WHERE NOT (btrim(Nombre) <> '');
    IF v_n > 0 THEN v_problemas := v_problemas || format('%s torneos sin nombre; ', v_n); END IF;
    SELECT COUNT(*) INTO v_n FROM JUGADOR_EQUIPO WHERE NOT (Fecha_Fin IS NULL OR Fecha_Fin >= Fecha_Inicio);
    IF v_n > 0 THEN v_problemas := v_problemas || format('%s membresías con fin anterior al inicio; ', v_n); END IF;
    SELECT COUNT(*) INTO v_n FROM JUGADOR_EQUIPO WHERE NOT (Dorsal IS NULL OR Dorsal > 0);
    IF v_n > 0 THEN v_problemas := v_problemas || format('%s membresías con dorsal <= 0; ', v_n); END IF;
    SELECT COUNT(*) INTO v_n FROM CONFIGURACION_TIEMPO_TORNEO WHERE NOT (Cantidad_Periodos IS NULL OR Cantidad_Periodos > 0);
    IF v_n > 0 THEN v_problemas := v_problemas || format('%s configuraciones con Cantidad_Periodos <= 0; ', v_n); END IF;
    SELECT COUNT(*) INTO v_n FROM CONFIGURACION_TIEMPO_TORNEO WHERE NOT (Duracion_Periodo_Minutos IS NULL OR Duracion_Periodo_Minutos > 0);
    IF v_n > 0 THEN v_problemas := v_problemas || format('%s configuraciones con Duracion_Periodo_Minutos <= 0; ', v_n); END IF;
    SELECT COUNT(*) INTO v_n FROM CONFIGURACION_TIEMPO_TORNEO WHERE NOT (Duracion_Descanso_Minutos IS NULL OR Duracion_Descanso_Minutos >= 0);
    IF v_n > 0 THEN v_problemas := v_problemas || format('%s configuraciones con descanso negativo; ', v_n); END IF;
    SELECT COUNT(*) INTO v_n FROM HITOS_PARTIDO WHERE NOT (Minuto_Reloj IS NULL OR Minuto_Reloj >= 0);
    IF v_n > 0 THEN v_problemas := v_problemas || format('%s hitos con minuto negativo; ', v_n); END IF;
    SELECT COUNT(*) INTO v_n FROM EQUIPOS WHERE NOT (btrim(Nombre) <> '');
    IF v_n > 0 THEN v_problemas := v_problemas || format('%s equipos sin nombre; ', v_n); END IF;
    SELECT COUNT(*) INTO v_n FROM JUGADORES WHERE NOT (btrim(Nombre) <> '');
    IF v_n > 0 THEN v_problemas := v_problemas || format('%s jugadores sin nombre; ', v_n); END IF;
    SELECT COUNT(*) INTO v_n FROM EVENTOS WHERE NOT (btrim(Nombre) <> '');
    IF v_n > 0 THEN v_problemas := v_problemas || format('%s tipos de evento sin nombre; ', v_n); END IF;
    IF v_problemas <> '' THEN
        RAISE EXCEPTION 'Datos que violan las restricciones nuevas: %', v_problemas;
    END IF;

    ALTER TABLE DISCIPLINA ALTER COLUMN Estado SET NOT NULL;
    ALTER TABLE MODALIDAD ALTER COLUMN Estado SET NOT NULL;
    ALTER TABLE TORNEO ALTER COLUMN Estado SET NOT NULL;
    ALTER TABLE EQUIPOS ALTER COLUMN Estado SET NOT NULL;
    ALTER TABLE JUGADORES ALTER COLUMN Estado SET NOT NULL;
    ALTER TABLE INSCRIPCIONES_TORNEO ALTER COLUMN Estado SET NOT NULL;
    ALTER TABLE JUGADOR_EQUIPO ALTER COLUMN Estado SET NOT NULL;
    ALTER TABLE TRASPASOS ALTER COLUMN Estado SET NOT NULL;
    ALTER TABLE EQUIPO_JUGADOR_BASE ALTER COLUMN Estado SET NOT NULL;
    ALTER TABLE PARTIDOS ALTER COLUMN Estado SET NOT NULL;
    ALTER TABLE EVENTOS ALTER COLUMN Estado SET NOT NULL;
    ALTER TABLE USUARIOS ALTER COLUMN Estado SET NOT NULL;
    ALTER TABLE EVENTOS_PARTIDO ALTER COLUMN Estado SET NOT NULL;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_torneo_fechas') THEN
        ALTER TABLE TORNEO ADD CONSTRAINT chk_torneo_fechas CHECK (Fecha_Fin >= Fecha_Inicio);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_torneo_equipos_por_grupo') THEN
        ALTER TABLE TORNEO ADD CONSTRAINT chk_torneo_equipos_por_grupo CHECK (Equipos_Por_Grupo IS NULL OR Equipos_Por_Grupo > 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_torneo_clasificados_por_grupo') THEN
        ALTER TABLE TORNEO ADD CONSTRAINT chk_torneo_clasificados_por_grupo CHECK (Clasificados_Por_Grupo IS NULL OR Clasificados_Por_Grupo > 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_torneo_nombre_no_vacio') THEN
        ALTER TABLE TORNEO ADD CONSTRAINT chk_torneo_nombre_no_vacio CHECK (btrim(Nombre) <> '');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_jugador_equipo_fechas') THEN
        ALTER TABLE JUGADOR_EQUIPO ADD CONSTRAINT chk_jugador_equipo_fechas CHECK (Fecha_Fin IS NULL OR Fecha_Fin >= Fecha_Inicio);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_jugador_equipo_dorsal') THEN
        ALTER TABLE JUGADOR_EQUIPO ADD CONSTRAINT chk_jugador_equipo_dorsal CHECK (Dorsal IS NULL OR Dorsal > 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_config_tiempo_cantidad_periodos') THEN
        ALTER TABLE CONFIGURACION_TIEMPO_TORNEO ADD CONSTRAINT chk_config_tiempo_cantidad_periodos CHECK (Cantidad_Periodos IS NULL OR Cantidad_Periodos > 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_config_tiempo_duracion_periodo') THEN
        ALTER TABLE CONFIGURACION_TIEMPO_TORNEO ADD CONSTRAINT chk_config_tiempo_duracion_periodo CHECK (Duracion_Periodo_Minutos IS NULL OR Duracion_Periodo_Minutos > 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_config_tiempo_duracion_descanso') THEN
        ALTER TABLE CONFIGURACION_TIEMPO_TORNEO ADD CONSTRAINT chk_config_tiempo_duracion_descanso CHECK (Duracion_Descanso_Minutos IS NULL OR Duracion_Descanso_Minutos >= 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_hitos_partido_minuto_reloj') THEN
        ALTER TABLE HITOS_PARTIDO ADD CONSTRAINT chk_hitos_partido_minuto_reloj CHECK (Minuto_Reloj IS NULL OR Minuto_Reloj >= 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_equipos_nombre_no_vacio') THEN
        ALTER TABLE EQUIPOS ADD CONSTRAINT chk_equipos_nombre_no_vacio CHECK (btrim(Nombre) <> '');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_jugadores_nombre_no_vacio') THEN
        ALTER TABLE JUGADORES ADD CONSTRAINT chk_jugadores_nombre_no_vacio CHECK (btrim(Nombre) <> '');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_eventos_nombre_no_vacio') THEN
        ALTER TABLE EVENTOS ADD CONSTRAINT chk_eventos_nombre_no_vacio CHECK (btrim(Nombre) <> '');
    END IF;
END $$;

CREATE OR REPLACE FUNCTION fn_cerrar_torneo_libera_jugadores()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.Estado = 'Finalizado' AND OLD.Estado <> 'Finalizado' THEN
        UPDATE JUGADOR_EQUIPO je
        -- TASK-026: una membresía que todavía no empezó cierra el día que
        -- empieza (chk_jugador_equipo_fechas).
        SET Estado = 'Inactivo', Fecha_Fin = GREATEST(CURRENT_DATE, je.Fecha_Inicio)
        FROM INSCRIPCIONES_TORNEO it
        WHERE je.Inscripcion_Torneo_ID = it.ID
          AND it.Torneo_ID = NEW.ID
          AND je.Estado = 'Activo';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
