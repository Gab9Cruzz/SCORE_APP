-- ============================================================
-- 20_migracion_control_mesa_tiempos.sql
-- Motor de Tiempos + Control de Mesa en vivo
-- (gestion-avanzada-equipos-control-mesa-plan.md, Fase 3), para una base
-- YA provisionada (torneos_mvp). La secuencia 01-06 ya quedó actualizada
-- al estado final — mismo criterio que 07/08/09/12/13/14/18/19.
--
-- Numerada 20 (sigue a 19_migracion_plantilla_base_equipo.sql, del mismo
-- plan).
--
-- Mayormente ADITIVA (tablas nuevas + una columna nueva en PARTIDOS), con
-- UN backfill real: cada TORNEO existente necesita una fila de
-- CONFIGURACION_TIEMPO_TORNEO — default 'Periodos'/2/45' para disciplinas
-- de equipo, 'Corrido' para individuales (Modalidad.Tamano_Equipo=1),
-- ajustable después desde la UI. No hay ambigüedad que frene el script:
-- Tamano_Equipo siempre resuelve un default determinístico.
--
-- Re-ejecutable: todo va con IF NOT EXISTS / guardas sobre pg_constraint,
-- y el backfill de CONFIGURACION_TIEMPO_TORNEO solo inserta para torneos
-- que todavía no tienen fila.
-- ============================================================

-- ------------------------------------------------------------
-- PARTE A — CONFIGURACION_TIEMPO_TORNEO + backfill
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS CONFIGURACION_TIEMPO_TORNEO (
    ID SERIAL PRIMARY KEY,
    Torneo_ID INT NOT NULL,
    Tipo_Cronometro VARCHAR(20) NOT NULL,
    Cantidad_Periodos INT,
    Duracion_Periodo_Minutos INT,
    Duracion_Descanso_Minutos INT,
    Fecha_Registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Fecha_Modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_config_tiempo_torneo') THEN
        ALTER TABLE CONFIGURACION_TIEMPO_TORNEO
            ADD CONSTRAINT fk_config_tiempo_torneo FOREIGN KEY (Torneo_ID) REFERENCES TORNEO(ID) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'unique_config_tiempo_torneo') THEN
        ALTER TABLE CONFIGURACION_TIEMPO_TORNEO
            ADD CONSTRAINT unique_config_tiempo_torneo UNIQUE (Torneo_ID);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_config_tiempo_tipo') THEN
        ALTER TABLE CONFIGURACION_TIEMPO_TORNEO
            ADD CONSTRAINT chk_config_tiempo_tipo CHECK (Tipo_Cronometro IN ('Periodos', 'Corrido'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_config_tiempo_periodos') THEN
        ALTER TABLE CONFIGURACION_TIEMPO_TORNEO
            ADD CONSTRAINT chk_config_tiempo_periodos CHECK (
                (Tipo_Cronometro = 'Periodos' AND Cantidad_Periodos IS NOT NULL AND Duracion_Periodo_Minutos IS NOT NULL)
                OR
                (Tipo_Cronometro = 'Corrido' AND Cantidad_Periodos IS NULL AND Duracion_Periodo_Minutos IS NULL)
            );
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_config_tiempo_torneo ON CONFIGURACION_TIEMPO_TORNEO(Torneo_ID);

DROP TRIGGER IF EXISTS trg_config_tiempo_torneo_upd_fecha ON CONFIGURACION_TIEMPO_TORNEO;
CREATE TRIGGER trg_config_tiempo_torneo_upd_fecha
BEFORE UPDATE ON CONFIGURACION_TIEMPO_TORNEO
FOR EACH ROW EXECUTE FUNCTION fn_actualizar_fecha_modificacion();

-- Backfill: un torneo es "individual" si su Modalidad.Tamano_Equipo=1
-- (mismo eje que ya usa el resto del sistema, ver 01_schema.sql — DISCIPLINA
-- ya no tiene columna Tipo desde ediciones-catalogo-disciplinas-plan.md).
DO $$
DECLARE
    v_backfilleados INT;
BEGIN
    INSERT INTO CONFIGURACION_TIEMPO_TORNEO (Torneo_ID, Tipo_Cronometro, Cantidad_Periodos, Duracion_Periodo_Minutos, Duracion_Descanso_Minutos)
    SELECT
        t.ID,
        CASE WHEN m.Tamano_Equipo = 1 THEN 'Corrido' ELSE 'Periodos' END,
        CASE WHEN m.Tamano_Equipo = 1 THEN NULL ELSE 2 END,
        CASE WHEN m.Tamano_Equipo = 1 THEN NULL ELSE 45 END,
        CASE WHEN m.Tamano_Equipo = 1 THEN NULL ELSE 15 END
      FROM TORNEO t
      JOIN MODALIDAD m ON m.ID = t.Modalidad_ID
     WHERE NOT EXISTS (SELECT 1 FROM CONFIGURACION_TIEMPO_TORNEO c WHERE c.Torneo_ID = t.ID);

    GET DIAGNOSTICS v_backfilleados = ROW_COUNT;
    IF v_backfilleados > 0 THEN
        RAISE NOTICE '% torneo(s) recibieron una CONFIGURACION_TIEMPO_TORNEO por defecto (Periodos 2x45'' para equipo, Corrido para individual) — ajustable desde la UI.', v_backfilleados;
    END IF;
END $$;

ALTER TABLE CONFIGURACION_TIEMPO_TORNEO ALTER COLUMN Torneo_ID SET NOT NULL;

-- ------------------------------------------------------------
-- PARTE B — HITOS_PARTIDO
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS HITOS_PARTIDO (
    ID SERIAL PRIMARY KEY,
    Partido_ID INT NOT NULL,
    Tipo_Hito VARCHAR(20) NOT NULL,
    Numero_Periodo INT,
    Timestamp_Real TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Minuto_Reloj INT,
    Registrado_Por INT NOT NULL,
    Fecha_Registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_hitos_partido_partido') THEN
        ALTER TABLE HITOS_PARTIDO
            ADD CONSTRAINT fk_hitos_partido_partido FOREIGN KEY (Partido_ID) REFERENCES PARTIDOS(ID) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_hitos_partido_usuario') THEN
        ALTER TABLE HITOS_PARTIDO
            ADD CONSTRAINT fk_hitos_partido_usuario FOREIGN KEY (Registrado_Por) REFERENCES USUARIOS(ID);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_hitos_partido_tipo') THEN
        ALTER TABLE HITOS_PARTIDO
            ADD CONSTRAINT chk_hitos_partido_tipo CHECK (Tipo_Hito IN (
                'Inicio_Partido', 'Inicio_Periodo', 'Fin_Periodo', 'Pausa', 'Reanudacion', 'Fin_Partido'
            ));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_hitos_partido_partido ON HITOS_PARTIDO(Partido_ID);
CREATE INDEX IF NOT EXISTS idx_hitos_partido_usuario ON HITOS_PARTIDO(Registrado_Por);

-- ------------------------------------------------------------
-- PARTE C — PARTIDOS.Ganador_Corrido_ID
-- ------------------------------------------------------------
ALTER TABLE PARTIDOS ADD COLUMN IF NOT EXISTS Ganador_Corrido_ID INT;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_partidos_ganador_corrido') THEN
        ALTER TABLE PARTIDOS
            ADD CONSTRAINT fk_partidos_ganador_corrido FOREIGN KEY (Ganador_Corrido_ID) REFERENCES EQUIPOS(ID);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_partidos_ganador_corrido ON PARTIDOS(Ganador_Corrido_ID);

-- ------------------------------------------------------------
-- PARTE D — Triggers (después de todo backfill, mismo motivo que
-- 06_triggers.sql/08_migracion_equipos_jugadores.sql: no deben disparar
-- sobre datos viejos a mitad de migración)
-- ------------------------------------------------------------
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

DROP TRIGGER IF EXISTS trg_hito_partido_validar ON HITOS_PARTIDO;
CREATE TRIGGER trg_hito_partido_validar
BEFORE INSERT OR UPDATE ON HITOS_PARTIDO
FOR EACH ROW EXECUTE FUNCTION fn_validar_hito_partido();

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

DROP TRIGGER IF EXISTS trg_hito_sincroniza_estado ON HITOS_PARTIDO;
CREATE TRIGGER trg_hito_sincroniza_estado
AFTER INSERT ON HITOS_PARTIDO
FOR EACH ROW EXECUTE FUNCTION fn_hito_sincroniza_estado_partido();

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

DROP TRIGGER IF EXISTS trg_partido_validar_ganador_corrido ON PARTIDOS;
CREATE TRIGGER trg_partido_validar_ganador_corrido
BEFORE UPDATE ON PARTIDOS
FOR EACH ROW EXECUTE FUNCTION fn_validar_ganador_corrido();

-- ------------------------------------------------------------
-- PARTE E — Vista vw_duracion_partido
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW vw_duracion_partido AS
WITH pausas AS (
    SELECT
        pausa.Partido_ID,
        SUM(
            EXTRACT(EPOCH FROM (reanuda.Timestamp_Real - pausa.Timestamp_Real))
        ) AS Segundos_Pausado
    FROM HITOS_PARTIDO pausa
    JOIN HITOS_PARTIDO reanuda
      ON reanuda.Partido_ID = pausa.Partido_ID
     AND reanuda.Tipo_Hito = 'Reanudacion'
     AND reanuda.Timestamp_Real = (
         SELECT MIN(r2.Timestamp_Real) FROM HITOS_PARTIDO r2
          WHERE r2.Partido_ID = pausa.Partido_ID AND r2.Tipo_Hito = 'Reanudacion'
            AND r2.Timestamp_Real > pausa.Timestamp_Real
     )
    WHERE pausa.Tipo_Hito = 'Pausa'
    GROUP BY pausa.Partido_ID
)
SELECT
    ini.Partido_ID,
    ini.Timestamp_Real AS Inicio,
    fin.Timestamp_Real AS Fin,
    (EXTRACT(EPOCH FROM (fin.Timestamp_Real - ini.Timestamp_Real)) - COALESCE(p.Segundos_Pausado, 0))::INT AS Duracion_Segundos
FROM HITOS_PARTIDO ini
JOIN HITOS_PARTIDO fin ON fin.Partido_ID = ini.Partido_ID AND fin.Tipo_Hito = 'Fin_Partido'
LEFT JOIN pausas p ON p.Partido_ID = ini.Partido_ID
WHERE ini.Tipo_Hito = 'Inicio_Partido';

-- ------------------------------------------------------------
-- Verificación
-- ------------------------------------------------------------
DO $$
DECLARE
    v_faltan TEXT := '';
    v_sin_config INT;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE lower(table_name) = 'hitos_partido') THEN
        RAISE EXCEPTION 'Migracion incompleta: la tabla HITOS_PARTIDO no existe.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE lower(table_name) = 'configuracion_tiempo_torneo') THEN
        RAISE EXCEPTION 'Migracion incompleta: la tabla CONFIGURACION_TIEMPO_TORNEO no existe.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'partidos' AND column_name = 'ganador_corrido_id') THEN
        v_faltan := v_faltan || ' partidos.ganador_corrido_id';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_config_tiempo_periodos') THEN
        v_faltan := v_faltan || ' chk_config_tiempo_periodos';
    END IF;
    IF v_faltan <> '' THEN
        RAISE EXCEPTION 'Migracion incompleta: faltan objetos:%', v_faltan;
    END IF;

    SELECT COUNT(*) INTO v_sin_config FROM TORNEO t
     WHERE NOT EXISTS (SELECT 1 FROM CONFIGURACION_TIEMPO_TORNEO c WHERE c.Torneo_ID = t.ID);
    IF v_sin_config > 0 THEN
        RAISE EXCEPTION 'Migracion incompleta: % torneo(s) sin CONFIGURACION_TIEMPO_TORNEO tras el backfill.', v_sin_config;
    END IF;

    RAISE NOTICE 'Motor de Tiempos + Control de Mesa listo: CONFIGURACION_TIEMPO_TORNEO (con backfill), HITOS_PARTIDO, PARTIDOS.Ganador_Corrido_ID, triggers de secuencia/sincronizacion/ganador-corrido y vw_duracion_partido creados.';
END $$;
