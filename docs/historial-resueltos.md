# Historial de pendientes resueltos

Lo que estaba en `TODOS.md` y ya se resolvió, movido acá el 2026-11-20 para
que `TODOS.md` muestre solo lo abierto. Varios comentarios del código citan
"TODOS.md" por una decisión que hoy está en esta página. El detalle de cada
cambio está en el commit que lo cerró y en `docs/plans/`.

## Resuelto (2026-11-20)

- **Filtrar por asignación los listados de un torneo** en `torneo-admin`.
  Ya estaba hecho y figuraba como pendiente por error: `GET /inscripciones`,
  `/plantillas`, `/traspasos` y `/partidos` recortan a un TorneoAdmin a sus
  torneos asignados, derivado del token y sin parámetro que el cliente pueda
  desactivar (`torneo_ids_permitidos`). Lo cubren las pruebas
  `test_torneo_admin_sin_asignacion_no_ve_*` de inscripciones, plantillas y
  traspasos. Equipos y jugadores no se recortan: son catálogos compartidos
  (decisión de TASK-013).
- **`GET /partidos/{id}/cronometro` respondía 400** (UX-21) en los torneos
  de `seed_portal_demo.sql`, que no les creaba configuración de tiempos.
  Corregido el seed, con prueba en `test_scripts_sql.py`.

## Resuelto (2026-11-18)

- **CI en GitHub Actions** (`.github/workflows/ci.yml`, TASK-003 de
  `docs/audit/11_BACKLOG_IMPLEMENTACION.md`). Estaba descartado como
  "infraestructura nueva"; se reabrió con evidencia nueva: la suite de
  frontend estuvo entera en rojo con Node 26 (`QA-01`) y una aserción
  quedó desactualizada (`QA-02`) sin que nadie lo notara. Corre backend
  (con PostgreSQL 16), frontend y el contrato de `schema.d.ts` en cada
  push y PR. `verificar.ps1` sigue siendo la verificación local.
- **`DESIGN.md`** (TASK-034, 2026-11-19). Estaba en el backlog sin urgencia
  ("recomendado por 5 planes, nunca ejecutado"). Describe la paleta, las
  escalas y los cuatro componentes base de `frontend/src/components/ui/`.
- **Tests de concurrencia real: tope de titulares y doble `Fin_Partido`**
  (T23/T24; TASK-024 y TASK-045, 2026-11-19). Las cuatro carreras de la
  auditoría (PR-050 titulares, PR-051 doble inicio, PR-052 doble fin,
  PR-053 doble sorteo) tienen prueba con dos conexiones reales, cada mitad
  contenciosa bajo `asyncio.timeout`, en `test_concurrencia_convocados.py`
  y `test_carreras.py`. Pasaron diez veces seguidas; `pytest -m
  concurrencia` en verde (7).

## Resuelto (2026-09-18)

Plan: `docs/plans/cierre-pendientes-todos-plan.md`, revisado en las cuatro
fases de `/autoplan` (CEO/eng/design/DX) antes de ejecutarse.

- **Row-locking en `EventoPartidoService.create`** (camino en vivo) para 2
  tarjetas simultáneas del mismo jugador. Reestructurado a UNA sola
  transacción (antes commiteaba por evento, lo que liberaba el lock del
  partido ANTES de contar las amarillas): `SELECT ... FOR UPDATE` con
  `lock_timeout` leído de `Settings` (antes no existía — el default de
  Postgres es esperar para siempre); contención real devuelve 409
  (`ConcurrencyConflictError`, código estable `evento_conflicto_concurrente`
  en `detail`) ruteado por la cola de "evento pendiente" que ya existía
  para fallos de red, un solo camino de recuperación en la UI de mesa, no
  una segunda afordancia. Deadlock cruzado se reintenta una vez (defensa en
  profundidad). `anular()` toma el mismo lock cuando el evento objetivo es
  una tarjeta — misma carrera, dirección inversa (anular la amarilla #1 en
  paralelo con el insert de la #2). Espera larga sobre el lock se loguea
  estructurado (`app.concurrencia`) con `partido_id`/`usuario_id`. 526
  tests de backend en verde (520 + 6 nuevos, con la carrera simulada por
  monkeypatch) — la prueba con conexiones REALES está en el ítem de abajo.
- **Infraestructura de test de concurrencia real** — fixture
  `sesiones_paralelas` (`backend/tests/conftest.py`): dos `AsyncSession`
  independientes contra su propia base (`torneos_mvp_test_concurrencia`,
  reconstruida entera antes de cada test), sin el savepoint envolvente del
  harness normal, así que un `commit()` persiste de verdad — imposible de
  probar con el harness compartido, que es justo la infraestructura de
  test que faltaba. `@pytest.mark.concurrencia` (registrado en
  `pytest.ini` con `--strict-markers`) — no corre en `pytest -q` por
  default, `verificar.ps1 -Concurrencia` lo suma aparte. Con esto se
  escribió la prueba REAL (no simulada) de la carrera de doble amarilla
  (autogenera exactamente una roja) y de la contención de lock (409 +
  log), ambas en `backend/tests/test_concurrencia_eventos.py`. T23/T24
  (tope de titulares, doble `Fin_Partido`) se cerraron después — ver
  Resuelto (2026-11-18).
- **Retirar el formulario de Cambio duplicado dentro de `CargaEvento`**.
  `ModalSustitucion` ganó primero un punto de entrada sin convocatoria
  (fallback a la plantilla completa del equipo, con caption "Sin
  convocatoria guardada") para tener paridad real con el camino viejo
  antes de retirarlo — sin eso, un partido sin convocatoria se quedaba sin
  forma de cargar un Cambio en vivo, una regresión real. Recién con esa
  paridad confirmada se sacó "Cambio" de la grilla de `CargaEvento` y el
  código muerto que dependía de él. `MesaPanel.test.tsx` pasó de 5 a 13
  tests (no había cobertura del camino viejo que migrar).
- **Wireframe de 3 zonas** del panel en vivo. `MesaPanel` reorganizado en 3
  franjas fijas (primaria: marcador+estado, `sticky` a 375px; secundaria:
  cronómetro+carga de evento+alineación en vivo; terciaria: timeline),
  activadas en grid recién a ≥1000px — mismo breakpoint que ya usaba el
  drag-and-drop de `AlineacionEditor`, ninguno nuevo. Verificación visual y
  manual, no automatizada (JSDOM no prueba `sticky` real ni grid areas).
  De paso: confirmación de éxito `aria-live="polite"` tras cada carga de
  evento (antes NINGUNA carga la tenía) y badge de estado de tarjetas por
  jugador ("1A"/"2A"/"R", texto y forma además de color, visible en la
  fila de "Sacar" y en los candidatos de `ModalSustitucion`).
- **Migrar `DetalleEquipo.tsx` al `SelectorJugadorBuscable` compartido**.
  El modal de búsqueda inline (debounce + query propios, reimplementados
  desde el selector) se reemplazó por el compartido, que ya extraía ese
  mismo patrón para Traspasos — el selector se queda haciendo solo
  búsqueda, no ganó props nuevas; la confirmación de multimilitancia y el
  alta inline de jugador se quedaron alrededor, en `DetalleEquipo`.
  `ModalAgregarInscripcion.ModalIndividual`/`ModalEquipo` (torneo-dashboard)
  **no se tocaron**: filtran client-side una lista ya cargada y capada
  (sin `GET ?q=` al servidor), un patrón distinto al del selector —
  migrarlos habría cambiado su comportamiento (multi-selección secuencial
  sin cerrar el modal) sin remover duplicación real. `DetalleEquipo.test.tsx`
  nuevo (no tenía test propio).
- **Métricas de revocación de licencia** — **cerrado por falta de señal**
  (mismo criterio que la Fase 3 del desempate, Resuelto 2026-09-17): la
  consulta ad hoc corrió contra `torneos_mvp` durante la revisión del plan
  y dio CERO en las dos mitades — contador (`AUDITORIA`: 287 filas, CERO
  de la tabla `usuarios`; 3 usuarios con `Licencia_Activa=True` nunca
  tocada) y pico de 403 (`ACCESOS`: CERO filas con
  `Motivo='licencia_revocada'`). El `.sql` no se commiteó — no hay señal
  que valga releer. **No es un "no" definitivo, es "todavía no hay
  señal".** Se reabre con la primera fila de `usuarios` en `AUDITORIA` (la
  primera licencia realmente otorgada o revocada). Si se reescribe la
  consulta: `Tabla` se filtra en MINÚSCULA (`usuarios`) —
  `app/core/auditoria.py` guarda `obj.__tablename__`, `Tabla='USUARIOS'`
  da cero por casing, no por falta de datos. La alerta ACTIVA (mail/
  webhook) sigue bloqueada por la misma decisión de proveedor de correo
  que el ítem de `## Bloqueado`.
- **DX: onboarding de un clon nuevo.** `frontend/.env.example` (faltaba —
  sin él, un clon limpio hace login contra `undefined/api/v1/...` y el
  fallo se ve como error de red, no de configuración).
  `infrastructure/docker-compose.yml` gana el servicio `postgres` (imagen
  oficial, carga el esquema completo desde `/database` vía
  `docker-entrypoint-initdb.d` en la primera inicialización) — antes
  asumía Postgres ya instalado en el host con `torneos_mvp` cargado a
  mano, la suposición que rompía a la segunda persona que clonaba.
  Nombrado como camino recomendado en el `README.md` raíz, manual como
  alternativa. **No verificado end-to-end en esta sesión** (sin Docker
  disponible acá). *Actualización 2026-11-18 (TASK-006):* no funcionaba —
  montar `database/` entera corría las migraciones históricas y la 08
  abortaba la inicialización. Ahora `infrastructure/initdb/00_init.sh` carga
  solo `01`–`06` + `11`; la secuencia se verificó contra PostgreSQL 17
  local, pero el `docker compose up` en sí sigue sin probarse por falta de
  Docker.

## Resuelto (2026-09-17)

- **Motor de reglamento de torneo genérico** (`ReglamentoTorneo`) —
  **hecho, alcance Python-only.** Nuevo `app/services/reglamento_torneo.py`
  (dataclass `ReglamentoTorneo` + `validar_minimo_para_iniciar`/
  `validar_maximo_titulares`) unifica la resolución de los 8 campos de
  reglamento de `Torneo`, consumido por `torneo.py`, `hito_partido.py`,
  `convocado_a_partido.py` y `partido.py` — elimina las 2 duplicaciones
  reales encontradas (fallback `torneo.X or modalidad.tamano_equipo` entre
  `HitoPartidoService`/`ConvocadoAPartidoService`, y el snapshot de
  desempate entre `HitoPartidoService`/`PartidoService`). **Esquema de DB,
  contrato de API y frontend sin cambios a propósito** — eso seguiría
  siendo Effort L si algún día se decide (ver el detalle de alcance en
  `~/.claude/plans/optimized-tickling-garden.md` si hace falta retomarlo).
  520 tests backend en verde (incluye 8 nuevos en
  `test_reglamento_torneo.py`); los 7 archivos de tests dedicados a estos
  campos no se tocaron.

- **Fase 3 del desempate de eliminatoria** (tiempo extra como reloj real) —
  se corrió `docs/queries/metricas-desempate-tiempo-extra-penales.sql`
  contra `torneos_mvp` (dev). Resultado: **0 torneos de Eliminación en los
  últimos 30 días, 0 llaves desempatadas, 0 cierres en los últimos 90
  días** — la base de dev no tiene volumen real todavía, así que la
  métrica 4 (el gate, C10) no puede evaluarse por falta de datos, no
  porque domine la carga directa. **Conclusión: seguimos sin poder agendar
  Fase 3 con evidencia real** — no es un "no" definitivo, es "todavía no
  hay señal". Revisitar esta consulta cuando haya partidos de Eliminación
  reales cerrados (torneo en producción/uso real, no solo datos de
  desarrollo).
- **Vista consolidada de estadísticas cruzando ediciones** de un mismo
  `TORNEO_GRUPO` (3B-5) — **regla de negocio confirmada:** las
  estadísticas se cuentan por edición y por equipo tal como se jugaron —
  un jugador que jugó la edición 1 con el Equipo A y la edición 2 con el
  Equipo B aporta a las estadísticas de CADA equipo en SU edición, sin
  fusionar identidad entre ediciones (cada edición tiene sus propios
  equipos). Con esto ya no está bloqueada por diseño — pasa a
  "Backlog sin urgencia" abajo, lista para agendar cuando se pida.
