# Runbook — Portal Público

Notas operativas del plan `docs/plans/portal-publico-feed-partidos-plan.md`
(F14). Se completa a medida que cada release (R1/R2/R3) aterriza.

## Seed de desarrollo (F1)

Para tener algo que mostrar en un entorno nuevo sin esperar datos reales:

```
psql -d torneos_mvp -f database/seed_portal_demo.sql
```

Requiere que `01_schema.sql`...`06_triggers.sql`, `11_catalogo_disciplinas.sql`
y `31_migracion_portal_publico.sql` ya hayan corrido (el script asume que
existen Fútbol y Baloncesto en `DISCIPLINA`). Crea 2 ligas publicadas (una
de Fútbol, una de Baloncesto) con 3 partidos cada una en `CURRENT_DATE`,
cubriendo los 3 estados visibles del feed: `Programado`, `En curso`,
`Finalizado`. No es idempotente entre días: se puede — y conviene — correr
de nuevo cada vez que "hoy" cambió.

## Migración `31_migracion_portal_publico.sql`

Aditiva, idempotente. **Sin rollback necesario** (F11): agrega columnas
nuevas (`EQUIPOS.Logo_URL`, `TORNEO_GRUPO.Pais`/`Logo_URL`, `TORNEO.Publicado`,
`DISCIPLINA.Slug`) que el código viejo ignora. Si hace falta deshacerla a
mano: `ALTER TABLE ... DROP COLUMN ...` de cada una — no hay FKs nuevas ni
tablas nuevas que dependan de esto.

## Publicado — quién ve qué

`TORNEO.Publicado` gatea `GET /torneos/{id}`, las 3 rutas de
`/estadisticas/torneos/{id}/*`, `GET /torneos/{id}/bracket`,
`GET /torneos` (lista) y `GET /partidos?torneo_id=` — solo para caller
ANÓNIMO (`Usuario | None = Depends(get_current_user_optional)` es `None`).
Cualquier sesión ve el torneo completo, publicado o no (E-S1: no hay
ownership-check acá, solo anónimo/logueado — un `Arbitro`/`TorneoAdmin` de
OTRO torneo también lo ve; blast radius chico, documentado, no endurecido
en este plan).

Un torneo se publica/despublica desde `TorneosAdminPage` (botón
"Publicar"/"Despublicar" en la tarjeta) — `PATCH /api/v1/torneos/{id}`
con `{"publicado": true|false}`.

## Métrica (C6/F13/T5.2d)

Formato de línea, a stdout (`app/core/metricas.py`):

```
{"evt": "torneo_hit", "torneo_id": 42, "ts": 1770000000.123}
```

Retención: la que ya tenga configurada la infraestructura de stdout del
deploy — no se agregó infraestructura nueva.

Conteo (hits a la vista pública de torneo en la última semana):

```
grep '"evt": "torneo_hit"' <archivo-de-log> | wc -l
```

El mismo comando, cambiando el valor de `"evt"`, cuenta `feed_hit` — se
emite solo cuando `fecha_efectiva != fecha_pedida` (E-S3c), no en cada
hit.

**Umbral (C6):** si a las 4 semanas del release de R1 los hits a la vista
pública de torneo siguen en cero, R3 (feed + barra de deportes) no se
construye sin replantear el canal primero — ver C6 en el plan.

## curl de ejemplo

```
curl http://localhost:8000/api/v1/torneos/1
curl http://localhost:8000/api/v1/estadisticas/torneos/1/resultados
curl "http://localhost:8000/api/v1/partidos/feed?disciplina_id=1&limit=20"
curl "http://localhost:8000/api/v1/disciplinas/con-partidos"
```

## EXPLAIN de `vw_feed_partidos` (E-L2/C11/F15) — veredicto: OK, sin plan B

Corrido contra la base de test (pocas filas):

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT f.* FROM vw_feed_partidos f
WHERE f.Fecha_Partido >= CURRENT_DATE
  AND f.Fecha_Partido < (CURRENT_DATE + INTERVAL '1 day');
```

Con solo ~3 filas en `PARTIDOS`, el planner elige `Seq Scan on partidos`
dentro del plan — **correcto para ese volumen**, no un síntoma del
problema que este chequeo busca. El criterio real (F15) es si el
predicado es SARGABLE, no qué elige el planner con una tabla vacía.
Verificado forzando `SET enable_seqscan = off` sobre la misma condición:

```
Index Scan using idx_partidos_fecha on partidos p
  Index Cond: ((fecha_partido >= CURRENT_DATE) AND (fecha_partido < (CURRENT_DATE + '1 day'::interval)))
```

El índice SÍ es usable en esta forma exacta (rango semiabierto, sin
envolver la columna en una función) — el plan B de C11 (mover el filtro
de fecha a una query parametrizada fuera de la vista) no hace falta. Con
volumen real de producción el planner va a preferir el índice solo; si
alguna vez se ve `Seq Scan on partidos` en un `EXPLAIN` con datos reales
y el predicado sigue siendo esta misma forma de rango, revisar primero
que `idx_partidos_fecha` no se haya eliminado, antes de sospechar del
query.
