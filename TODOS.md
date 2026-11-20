# TODOS

Todo lo que ya estaba implementado/hecho fue retirado de esta lista el
2026-09-17. El detalle histórico de cada decisión (por qué se hizo así,
alternativas evaluadas, tests) sigue en `docs/plans/*.md` si hace falta
retomarlo — acá solo queda lo que sigue abierto.

## Pendiente — ya evaluado, falta ejecutar

- **`GET /partidos/{id}/cronometro` responde 400 cuando el torneo no tiene
  configuración de tiempos** (UX-21, `docs/audit/12_REVISION_VISUAL.md`). Es
  un estado normal, no un error: deja dos errores en la consola por visita a
  "Gestionar partido" y ensucia el monitoreo de 4xx. Devolver 200 con
  `null` (y adaptar `Cronometro.tsx`) o un 404 explícito. Prioridad P3.
- **Paginación con cursor en `/equipos` y `/jugadores`** (3B-9). TASK-039 ya
  pagina las grillas por desplazamiento (`skip`/`limit` + `X-Total-Count`,
  pie "1–50 de 312") y busca en el servidor; lo que queda diferido es pasar
  a cursor, que cambia el contrato de API. **Diferido con umbral numérico**
  (revisión del plan de cierre, 2026-09-18) — se reabre con (a) >150 equipos
  orgánicos o >150 jugadores orgánicos (75% del tope de página de 200), o
  (b) p95 medido >800ms en `GET /jugadores` o `GET /equipos`, o (c) un
  segundo cliente de la API que no sea este frontend. Hoy: 10 equipos y 37
  jugadores orgánicos (separados de los datos sintéticos de
  `backend/scripts/mock_estres_catalogo.py`, ver `docs/queries/README.md`).
- **Editar el catálogo maestro de disciplinas desde la UI**, no solo por
  migración SQL manual (EC-32 / 3B-11). **Diferido** — se reabre al SEGUNDO
  pedido real de alta de una disciplina fuera del catálogo de 28 (el
  primero se atiende con el script de migración que ya existe). Si se
  reabre: gatear `POST`/`PUT /disciplinas` a `AdminGeneral` (el toggle de
  `Estado` se queda en `TorneoAdmin`, son poderes distintos — no mezclar
  dos niveles de rol en la misma ruta); `Slug` no se edita desde la UI
  (lo consume el portal público); no se agrega un rol nuevo, `AdminGeneral`
  ya alcanza.
- **Filtrar por asignación los LISTADOS de sub-recursos** dentro de un
  torneo específico (equipos/jugadores/partidos) en `torneo-admin/*` —
  heredan protección de escritura pero no filtran el listado. Prioridad P3.
  Si se reabre: el alcance NO se expresa como query param elegible por el
  cliente (invierte el default seguro) — se deriva implícito del token vía
  `torneo_ids_permitidos` (mismo patrón que ya usan `torneos`/`partidos`).
  Un caso de alta/búsqueda que necesite ver filas no inscritas se expresa
  como flag de capacidad con nombre honesto (`incluir_no_inscritos=true`),
  nunca ampliando el techo de permisos del rol.

## Bloqueado — necesita una respuesta tuya

1. **Notificación por correo al jugador** cuando es traspasado o pasa a
   libre está parada porque falta elegir proveedor de correo (decisión de
   infraestructura). **Pospuesto explícitamente (2026-09-17)** hasta que el
   resto del proyecto esté más afinado.
2. **Despliegue a producción (Fase 5 del roadmap de `docs/audit/`):**
   TASK-049 (imagen del frontend, proxy inverso con TLS), TASK-050
   (configuración por entorno y secretos), TASK-051 (copias automáticas y
   restauración ensayada), TASK-052 (observabilidad), y después 053, 054 y
   056. Falta definir dónde se despliega, el dominio para HTTPS y el
   destino de las copias. **Pospuesto (2026-11-19)** hasta tener esas
   definiciones; el resto del roadmap sigue sin esperar.

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

## Backlog sin urgencia (evaluado, nadie lo pidió todavía)

- Clonar la plantilla de una edición a la siguiente (3B-6) — recomendación
  vigente: no construir hasta que se pida.
- Fusionar Modo en Vivo + Resultado Directo en un único motor de eventos —
  requiere antes medir qué fracción de partidos "resultado directo" tiene
  convocatoria guardada (esa métrica no existe hoy).
- Restaurar desde `localStorage` un batch de Resultado Directo no guardado
  tras un refresh accidental.
- Sanciones disciplinarias que acumulan tarjetas ENTRE partidos (ej. 3
  amarillas en el torneo = suspensión).
- Palmarés a través de las ediciones de un `TORNEO_GRUPO` — bloqueado por
  las columnas de podio y la página pública de campeón (UC2), ninguna
  existe todavía. Prioridad P3.
- Desempate por llave individual (override puntual de
  `Metodo_Desempate_Eliminatoria` para un solo cruce) — el hook de datos ya
  existe, falta la UI.
- Tanda de penales gol a gol (quién pateó/atajó, en qué orden).
- Unificar la edición de `formato_eliminatoria`/`metodo_desempate` en el
  formulario principal de torneo (hoy es un botón aparte) — cosmético.
- Bracket visual con líneas de conexión del árbol (hoy son columnas sin
  conectar) — trabajo de diseño gráfico, no bloquea funcionalidad.
- Badge visual de sanción pendiente en convocatoria — depende de un modelo
  de "sanciones" que no existe todavía.
- Exportar un resultado directo cargado a texto plano (para WhatsApp).
- Mecanismo genérico de "operación reversible con ventana de gracia" — se
  generaliza si aparece un segundo caso de uso además de
  `deshacer-cierre-forzado`.
- Portal público — pendientes menores, todos con mitigación ya en
  producción: auto-refresh en vivo del feed (hoy hay botón "Recargar"),
  uploader de imágenes para escudos/logos (hoy es URL de texto), preview de
  Open Graph por torneo/partido, `?fecha`/`?disciplina_id` en
  `GET /api/v1/partidos`, parámetro `tz` del feed, flag para forzar la
  barra de disciplinas con una sola activa, envelope de error con código
  estable, minuto en vivo en la fila del feed (hoy solo dice "EN VIVO").

## Descartado a propósito (no reabrir sin evidencia nueva)

- Equipo con roster autoritativo permanente — evaluado y rechazado 2 veces.
- Registro de resultados para disciplinas de marca/tiempo, combate o mente
  (Atletismo, Boxeo, Ajedrez, etc.) — necesita su propio diseño de
  producto, rechazado 2 veces.
- Categorías de peso/cinturón oficiales de una federación.
- eSports (brackets, integración con Riot/Steam).
- Catálogo de categorías etarias/de género (Sub-13, Libre, Femenino...).
- Iconos SVG propios por disciplina (hoy son emoji).
- `UNIQUE (Nombre, Disciplina_ID)` en `EQUIPOS` — rompería datos existentes.
- Importación masiva desde CSV/Excel para el registro por lote.
- Registrar el logout — requeriría una lista de tokens revocados (JWT es
  sin estado del lado del servidor hoy).
- Muerte súbita / gol de oro en el alargue — ninguna competencia real de
  este mercado lo usa.
