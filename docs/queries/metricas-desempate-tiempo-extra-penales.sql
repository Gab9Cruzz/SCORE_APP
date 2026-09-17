-- ============================================================
-- Métricas de adopción — Desempate de eliminatoria: tiempo extra y
-- penales (docs/plans/desempate-tiempo-extra-penales-plan.md, §12-bis).
--
-- NO es una migración — no toca esquema, solo lee. Referencia de consulta
-- para correr a mano contra la base de desarrollo (o cablear a un panel)
-- ANTES de que el resto de fase 2 mergee (métricas 1-3) y ANTES de
-- agendar fase 3 (métrica 4, su gate — C10).
--
-- La métrica 3 también se loguea en caliente, evento estructurado
-- `desempate_manual_sobre_metodo_configurado` (backend/app/core/metricas.py,
-- emitido desde HitoPartidoService.registrar/_registrar_fin_forzado y
-- PartidoService.registrar_resultado_directo) — la query de acá sirve para
-- el volumen HISTÓRICO ya grabado en PARTIDOS, sin depender de que el log
-- se haya estado recolectando desde el día 1.
-- ============================================================

-- 1) % de torneos Eliminación con método distinto de 'Manual', a 30 días
--    de la fecha de corte — ¿alguien la está usando?
SELECT
    COUNT(*) FILTER (WHERE t.Metodo_Desempate_Eliminatoria <> 'Manual') AS con_metodo_configurado,
    COUNT(*)                                                            AS total_torneos_eliminacion,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE t.Metodo_Desempate_Eliminatoria <> 'Manual')
        / NULLIF(COUNT(*), 0),
        1
    ) AS porcentaje
FROM TORNEO t
WHERE t.Formato = 'Eliminacion'
  AND t.Fecha_Registro >= CURRENT_DATE - INTERVAL '30 days';

-- 2) % de llaves empatadas cerradas que traen marcador de tanda — ¿el dato
--    nuevo llega al acta o queda vacío? "Llave empatada cerrada" = un
--    partido de Eliminación Finalizado con Ganador_Desempate_ID NOT NULL
--    (la ida nunca lo tiene — D4/§6 — así que ya filtra solo a vueltas y
--    partidos únicos).
SELECT
    COUNT(*) FILTER (WHERE p.Metodo_Desempate = 'Penales') AS con_marcador_de_tanda,
    COUNT(*)                                                AS total_llaves_desempatadas,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE p.Metodo_Desempate = 'Penales')
        / NULLIF(COUNT(*), 0),
        1
    ) AS porcentaje
FROM PARTIDOS p
JOIN FASE f ON f.ID = p.Fase_ID
WHERE f.Tipo = 'Eliminacion'
  AND p.Estado = 'Finalizado'
  AND p.Ganador_Desempate_ID IS NOT NULL;

-- 3) Cierres 'Manual' sobre torneos configurados de otra forma (tasa de
--    escape, D-A1) — si es alta, el flujo en vivo no se parece a la
--    realidad de la cancha. Ver también el evento de log en caliente
--    arriba mencionado.
SELECT
    COUNT(*) FILTER (WHERE p.Metodo_Desempate = 'Manual') AS cierres_manual,
    COUNT(*)                                               AS total_llaves_desempatadas,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE p.Metodo_Desempate = 'Manual')
        / NULLIF(COUNT(*), 0),
        1
    ) AS porcentaje_escape
FROM PARTIDOS p
JOIN FASE f ON f.ID = p.Fase_ID
JOIN TORNEO t ON t.ID = p.Torneo_ID
WHERE f.Tipo = 'Eliminacion'
  AND p.Estado = 'Finalizado'
  AND p.Ganador_Desempate_ID IS NOT NULL
  AND t.Metodo_Desempate_Eliminatoria <> 'Manual';

-- 4) Split cronómetro EN VIVO vs carga directa en cierres de Eliminación,
--    90 días — GATE de fase 3 (C10): si domina la carga directa, se
--    reconsidera la forma de §4 antes de construirla. "En vivo" = el
--    partido tiene al menos un HITOS_PARTIDO de tipo Inicio_Periodo (la
--    carga directa nunca inserta hitos de período, solo Inicio_Partido/
--    Fin_Partido — ver el comentario de Hubo_Tiempo_Extra en 01_schema.sql).
SELECT
    COUNT(*) FILTER (
        WHERE EXISTS (
            SELECT 1 FROM HITOS_PARTIDO h
             WHERE h.Partido_ID = p.ID AND h.Tipo_Hito = 'Inicio_Periodo'
        )
    ) AS cierres_en_vivo,
    COUNT(*) FILTER (
        WHERE NOT EXISTS (
            SELECT 1 FROM HITOS_PARTIDO h
             WHERE h.Partido_ID = p.ID AND h.Tipo_Hito = 'Inicio_Periodo'
        )
    ) AS cierres_carga_directa,
    COUNT(*) AS total
FROM PARTIDOS p
JOIN FASE f ON f.ID = p.Fase_ID
WHERE f.Tipo = 'Eliminacion'
  AND p.Estado = 'Finalizado'
  AND p.Fecha_Modificacion >= CURRENT_DATE - INTERVAL '90 days';
