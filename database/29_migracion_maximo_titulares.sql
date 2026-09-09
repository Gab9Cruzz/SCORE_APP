-- ============================================================
-- 29_migracion_maximo_titulares.sql
-- "Modo en Vivo": tope SUPERIOR de titulares por equipo
-- (docs/plans/modo-vivo-sustituciones-cierre-plan.md, Área 1, T2/T16/T18)
-- — reversión explícita de la Decisión Audit #12 del plan anterior
-- (gestionar-partido-alineaciones-plan.md:2275-2277, TODOS.md:462-464),
-- para una base YA provisionada (torneos_mvp). La secuencia 01-06 ya
-- quedó actualizada al estado final.
--
-- Numerada 29 (sigue a 28_migracion_reglas_cambio.sql).
--
-- Aditiva pura: 1 columna nueva en TORNEO, 1 constraint, 1 función +
-- trigger nuevos en CONVOCADO_A_PARTIDO. Sin backfill:
-- Maximo_Titulares_Permitido nace en NULL, que el service lee como "usar
-- Modalidad.Tamano_Equipo" — el trigger nuevo SÍ empieza a validar de
-- inmediato (a diferencia del mínimo, este es un fix de integridad de
-- datos, no una opción que cada torneo deba prender): una convocatoria ya
-- cargada con MÁS titulares que Tamano_Equipo (el "bug" real que motivó
-- este plan) no se corrige sola, pero ningún alta/cambio NUEVO puede
-- agravarla.
--
-- Re-ejecutable: ADD COLUMN IF NOT EXISTS, constraint guardada con un
-- chequeo contra pg_constraint, CREATE OR REPLACE FUNCTION + DROP TRIGGER
-- IF EXISTS previo (test_scripts_sql.py corre cada script dos veces).
-- ============================================================

ALTER TABLE TORNEO
    ADD COLUMN IF NOT EXISTS Maximo_Titulares_Permitido INT;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_torneo_maximo_titulares') THEN
        ALTER TABLE TORNEO
            ADD CONSTRAINT chk_torneo_maximo_titulares
            CHECK (Maximo_Titulares_Permitido IS NULL OR Maximo_Titulares_Permitido >= 1);
    END IF;
END $$;

-- ------------------------------------------------------------
-- Ver 06_triggers.sql para el comentario largo (mismo cuerpo exacto,
-- copiado acá para que una base vieja que corre solo migraciones,
-- 01-06 aparte, quede con la misma defensa en profundidad).
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

    PERFORM 1 FROM PARTIDOS WHERE ID = NEW.Partido_ID FOR UPDATE;

    SELECT v.Equipo_ID INTO v_equipo_id
      FROM vw_jugadores_activos_por_equipo v
      JOIN PARTIDOS p ON p.Torneo_ID = v.Torneo_ID
     WHERE p.ID = NEW.Partido_ID
       AND v.Jugador_Perfil_ID = NEW.Jugador_Perfil_ID
       AND v.Equipo_ID IN (p.EQUIPOS_ID_LOCAL, p.EQUIPOS_ID_VISITANTE)
     LIMIT 1;

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

DROP TRIGGER IF EXISTS trg_convocado_validar_tope_titulares ON CONVOCADO_A_PARTIDO;
CREATE TRIGGER trg_convocado_validar_tope_titulares
BEFORE INSERT OR UPDATE OF Titular ON CONVOCADO_A_PARTIDO
FOR EACH ROW EXECUTE FUNCTION fn_validar_tope_titulares();
