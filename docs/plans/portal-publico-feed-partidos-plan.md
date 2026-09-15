<!-- /autoplan restore point: /c/Users/Gabo/.gstack/projects/Score-App/main-autoplan-restore-20260914-233821.md -->

# Portal Público: Navbar de Disciplinas + Feed de Partidos del Día

Estado: **BORRADOR — en revisión por /autoplan**

## Implementation plan

Convertir Score-App de "herramienta de administración con un dashboard
interno" a "portal público estilo SofaScore con un back-office detrás".
Un visitante sin cuenta entra a `/`, elige un deporte en la barra del
header y ve los partidos del día agrupados por torneo, con dos caminos de
navegación: al torneo (tabla de posiciones) o al partido (timeline).

## Lo que ya existe (verificado en código, no asumido)

| Pieza | Dónde | Estado |
|---|---|---|
| Barra horizontal de disciplinas tipo pill con icono | `frontend/src/pages/torneo-admin/FiltroDisciplinasBar.tsx` | Existe, con `role="tablist"`, `aria-pressed` y navegación por flechas |
| Iconos emoji por disciplina + fallback a inicial | `frontend/src/pages/torneo-admin/iconosDisciplina.ts` | Existe, 28 disciplinas mapeadas |
| Orden por popularidad global | `DISCIPLINA.Orden_Popularidad` (`database/15_migracion_popularidad_disciplinas.sql`) + `DisciplinaRepository.list` (order_by orden_popularidad NULLS LAST) | Existe y ya ordena |
| `GET /api/v1/disciplinas` público | `backend/app/api/routes/disciplinas.py` | Sin auth |
| `GET /api/v1/torneos` público | `backend/app/api/routes/torneos.py` | Sin auth |
| `GET /api/v1/partidos` público | `backend/app/api/routes/partidos.py:56` | Sin auth |
| `GET /api/v1/estadisticas/*` público (posiciones, goleadores, resultados, próximos) | `backend/app/api/routes/estadisticas.py` | Sin auth, 5 vistas de `04_views.sql` |
| Vista "Detalle del Partido" pública | Ruta `/partidos/:partidoId` -> `PartidoEnVivo.tsx` (App.tsx, sin `RequireRole`) | Existe y funciona anónimo (`/jugadores` devuelve `JugadorPublicOut` sin PII) |
| Hook de catálogo Disciplina/Modalidad | `frontend/src/hooks/useCatalogo.ts` | Existe |
| Avatar con fallback a iniciales | `frontend/src/pages/torneo-admin/avatarUtils.ts`, `AvatarJugador.tsx` | Existe (para jugadores) |

## Los huecos reales (lo que este plan tiene que construir)

1. **`EQUIPOS` no tiene columna de escudo/logo.** `database/01_schema.sql:168-176`.
   `JUGADORES` sí tiene foto; `EQUIPOS` no. El requerimiento pide "Escudo del
   Equipo Local vs Escudo del Equipo Visitante".
2. **`TORNEO`/`TORNEO_GRUPO` no tienen país ni logo.** `01_schema.sql:64-102`.
   El requerimiento pide "Icono/Logo del torneo, Nombre de la Competición y País".
3. **`PartidoOut` devuelve solo IDs** (`equipos_id_local`, `torneo_id`), sin
   nombres. Pintar el feed con `GET /partidos` obliga a cruzar `/equipos` y
   `/torneos` en el cliente.
4. **`vw_proximos_partidos` no sirve para "partidos del día".** Filtra
   `Estado='Programado' AND Fecha_Partido >= CURRENT_TIMESTAMP`
   (`04_views.sql:46-69`): se pierde todo lo que ya empezó o terminó hoy, que es
   justo la mitad de un feed estilo SofaScore.
5. **`GET /partidos` no filtra por fecha ni por disciplina.** Solo
   `torneo_id`, `estado`, `arbitro_id`, `solo_mios`, `incluir_archivados`.
6. **No existe una vista pública de detalle de torneo.** `/torneo-admin/torneos/:id`
   está detrás de `RequireRole` dentro de `TorneoAdminLayout`.
7. **El único acceso a `/control-de-mesa` (la lista) es el link del NavBar.**
   `grep -rn "control-de-mesa" frontend/src`: `MisPartidos.tsx` y
   `ControlDeMesa.tsx` navegan a `/control-de-mesa/partido/:id`, y
   `PartidosDelTorneo.tsx:184` navega a `/partidos/:id` (detalle), no a mesa.
   Quitar el link del NavBar **deja huérfana la lista** para TorneoAdmin y
   AdminGeneral (el Árbitro sigue entrando por `/arbitro`).

## Fuera de alcance (explícito)

- Subida de archivos de escudos/logos (uploader). Las columnas nuevas aceptan
  URL, mismo criterio que `JUGADORES.Foto_URL`.
- Búsqueda global, favoritos, notificaciones push, multi-idioma.
- Poblar escudos y países de datos reales — el plan entrega el soporte y el
  fallback, no el contenido.
- Rediseño visual del back-office (`/torneo-admin`, `/control-de-mesa`).
- SSR y preview de Open Graph POR torneo/partido (exige prerender). Los meta
  tags OG **estáticos** SÍ entran (C4).
- Auto-refresh en vivo del feed (polling/WebSocket).

---

## Fase 1 (R1) — Limpieza del acceso a Control de Mesa

**Hallazgo previo:** `/dashboard` (`frontend/src/pages/Dashboard.tsx`) **no
renderiza** ningún módulo de Control de Mesa: muestra selector de torneo,
tabla de posiciones, goleadores y próximos partidos. La visibilidad que el
requerimiento pide quitar es el `NavLink` global de `NavBar.tsx:14`.

- **T1.1 (C7)** Condicionar por rol el `<NavLink to="/control-de-mesa">` de
  `frontend/src/components/NavBar.tsx`: visible solo para TorneoAdmin,
  AdminGeneral y Arbitro. El público deja de verlo; el operador conserva su
  acceso. Las rutas quedan intactas con su `RequireRole`.
- **T1.2 (C7)** Condicionar por rol también el `NavLink` de "Dashboard", que
  hoy se le muestra a un visitante anónimo, y cambiar el catch-all
  `<Route path="*">` de `App.tsx` para que un anónimo caiga en la home
  pública y no en el dashboard interno.
- **T1.3** Agregar botón "Gestionar en Mesa" por fila en
  `PartidosDelTorneo.tsx` -> `/control-de-mesa/partido/:id`, junto al botón
  "Detalle" que ya navega a `/partidos/:id`.
- **T1.4** Actualizar `App.routing.test.tsx` y cualquier test que asuma el
  link del NavBar.

## Fase 2 (R3) — Barra pública de disciplinas en el header

- **T2.1** Mover `FiltroDisciplinasBar.tsx` + `iconosDisciplina.ts` de
  `pages/torneo-admin/` a `components/` (es ahora un componente compartido
  entre back-office y portal público). Actualizar los imports de
  `TorneosAdmin.tsx`, `EquiposAdmin.tsx` y demás consumidores.
- **T2.2 (C8)** Nuevo `components/BarraDisciplinasPublica.tsx`: una sola fila
  de pills (sin modalidades ni estados — el visitante no filtra por
  modalidad). **No** se alimenta de `useCatalogo()` (eso traería las 28 del
  catálogo): usa el sidecar `disciplinas_con_partidos` que devuelve
  `GET /partidos/feed`, calculado ANTES de aplicar `disciplina_id`. Con ≤1
  disciplina con contenido la barra no se renderiza.
- **T2.3** Montarla en `NavBar.tsx` como segunda fila bajo la marca
  "Score-App". Visible **sin sesión** (el `NavBar` ya se renderiza para
  anónimos).
- **T2.4** Estado de la disciplina elegida en la URL
  (`/?deporte=futbol` o `/deporte/:disciplinaId`) — no en `useState`, para
  que un refresh o un link compartido conserven el deporte.
- **T2.5** Estilos: reusar `.chip-disciplina` de `index.css`; scroll
  horizontal con `overflow-x: auto` en móvil.

## Fase 3 (R1 la migración, R2 la vista y el endpoint) — Datos para el feed

**Pitfall conocido del repo:** toda columna nueva va en TRES lugares —
`database/01_schema.sql`, el script de migración `NN_` idempotente, y la
lista `SCRIPTS_VIGENTES` de `backend/tests/test_scripts_sql.py:36-48`.
`conftest.py` arma la base de tests solo con `01`-`06`.

- **T3.1** `database/31_migracion_portal_publico.sql` (idempotente,
  re-ejecutable):
  - `EQUIPOS.Logo_URL VARCHAR(500) NULL`
  - `TORNEO_GRUPO.Pais VARCHAR(60) NULL`
  - `TORNEO_GRUPO.Logo_URL VARCHAR(500) NULL`
  - `TORNEO.Publicado BOOLEAN NOT NULL DEFAULT TRUE` + backfill TRUE (C2)

  **No** agregar índice sobre `PARTIDOS.Fecha_Partido`: `idx_partidos_fecha`
  ya existe (`03_indexes.sql:82`) y duplicarlo rompe la idempotencia.

  Espejar las tres en `01_schema.sql` y agregar el script a
  `SCRIPTS_VIGENTES`.
- **T3.2 (C5)** Nueva vista `vw_feed_partidos` en `04_views.sql` construida
  **SOBRE `vw_resultados_partidos`** (prohibido reimplementar el conteo de
  goles: esa vista ya resuelve autogol vía `vw_goles_acreditados` y walkover,
  y no filtra por estado). Le suma los JOIN a TORNEO, TORNEO_GRUPO y
  DISCIPLINA para `torneo`, `torneo_grupo`, `pais`, `logo_torneo`,
  `disciplina_id`, `disciplina` y los logos de ambos equipos.
  **`WHERE` explícito, escrito entero** (`vw_resultados_partidos` NO filtra
  estados, a diferencia de `vw_proximos_partidos`): `TORNEO.Publicado = TRUE`
  Y `TORNEO.Estado = 'Activo'` Y `TORNEO_GRUPO.Estado <> 'Archivado'`
  Y `PARTIDOS.Estado <> 'Cancelado'` Y ambos `EQUIPOS.Estado = 'Activo'`.
  Sin el `>= CURRENT_TIMESTAMP` ni el `Estado='Programado'` de
  `vw_proximos_partidos`, que rompen el caso "hoy". Los shells de bracket ya
  quedan fuera por el `JOIN EQUIPOS` interno heredado.
- **T3.3 (C12/C1/C8/C15)** `GET /api/v1/partidos/feed` — en el router de
  partidos (no en `/estadisticas/`; una lista de partidos no es una
  estadística), registrado ANTES de `/{partido_id}` para que FastAPI no lea
  "feed" como un id. Público. Params: `disciplina_id` (opcional), `fecha`
  (`date`, default `CURRENT_DATE` del servidor), `limit` (`le=200`).
  **Envelope, no lista plana** — `FeedResponseOut` en `schemas/partido.py`:
  `fecha_pedida`, `fecha_efectiva`, `disciplinas_con_partidos` (lista de
  `{id, nombre}`), `partidos` (lista de `FeedPartidoOut`) y `truncado` (bool).
  `FeedPartidoOut`: `partido_id`, `torneo_id`, `torneo`, `torneo_grupo`,
  `pais`, `logo_torneo`, `disciplina_id`, `disciplina`, `equipo_local_id`,
  `equipo_local`, `logo_local`, `equipo_visitante_id`, `equipo_visitante`,
  `logo_visitante`, `fecha_partido`, `estado`, `goles_local`,
  `goles_visitante`.
  `ORDER BY torneo_grupo.Nombre, torneo.ID, fecha_partido, partido_id` —
  determinista, y deja contiguos los partidos de un mismo torneo para que el
  cliente no tenga que reordenar. **Truncado:** si `limit` corta, corta en el
  borde de un torneo, nunca a mitad de un bloque, y marca `truncado: true`.
- **T3.4 (C3)** Exponer y hacer escribibles las columnas nuevas. Ojo con el
  esfuerzo real, verificado en código: `TorneoGrupoUpdate`
  (`schemas/torneo_grupo.py:19`) hoy solo acepta `nombre` y `estado`, y
  `TorneosAdmin.tsx` **no tiene formulario de edición de torneo** (su `Modo`
  es `lista | crear-grupo | nueva-edicion`; el único PATCH, línea 269, es el
  archivado del grupo). O sea:
  - `EquipoOut`/`EquipoUpdate` + campo "URL del escudo" en `EquiposAdmin.tsx`
    → barato, usa el builder genérico `camposEquipo`.
  - `TorneoGrupoOut`/`TorneoGrupoUpdate` + `pais` y `logo_url` + servicio +
    formulario de edición de grupo → **no existe, hay que crearlo**.
  - `TorneoUpdate.publicado` + mutación + affordance de publicar/despublicar
    → **no existe, hay que crearlo**.
- **T3.4b (C2)** Auth opcional en las rutas que `Publicado` tiene que
  proteger: agregar `usuario: Usuario | None = Depends(get_current_user_optional)`
  a `GET /torneos/{torneo_id}` (`routes/torneos.py:53`) y a los tres
  `GET /estadisticas/torneos/{torneo_id}/*`, devolviendo 404 **solo** si el
  caller es anónimo y el torneo no está publicado. Sin el matiz se rompe
  `MesaPanel.tsx:91`, que llama al mismo endpoint. Decidir también, y
  escribirlo, qué pasa con `GET /torneos` (lista),
  `GET /partidos?torneo_id=`, `GET /torneos/{id}/bracket` y
  `/estadisticas/proximos-partidos`, que hoy enumeran torneos sin filtrar: o
  filtran `Publicado` para anónimos, o se documenta por qué quedan abiertos.
  Y decidir el caso de `PartidoEnVivo.tsx:61`, que consume
  `/estadisticas/torneos/{id}/resultados`: si esa ruta 404ea para anónimos, la
  página pública de partido de un torneo despublicado queda a medio
  renderizar — o se gatea entera, o la query tolera el 404.
- **T3.5** Regenerar `frontend/src/api/schema.d.ts` (`npm run gen:api`).
- **T3.6** Tests backend, con el reloj congelado (C10f): feed vacío; 2 torneos
  de la misma disciplina; partido en curso incluido; partido finalizado hoy
  incluido; partido de mañana excluido; torneo archivado excluido; grupo
  archivado excluido; partido Cancelado excluido; equipo Inactivo excluido;
  torneo despublicado excluido; el mismo id devuelve 200 para TorneoAdmin y
  404 anónimo en las 4 rutas de T3.4b; `MesaPanel` sigue cargando un torneo
  despublicado; `PartidoEnVivo` anónimo sobre un torneo despublicado se
  comporta como se decidió en T3.4b; migración `31_` idempotente corrida dos
  veces.

## Fase 4 (R3) — Feed de Partidos del Día (frontend)

- **T4.1 (C16)** Nueva página `pages/publico/FeedPartidos.tsx`. `/` decide por
  sesión: anónimo ve el feed, logeado sigue redirigiendo a `/dashboard`. Es el
  único cambio que toca a todo usuario existente → va con su test y con un
  comentario en `App.tsx` explicando por qué la ruta decide por sesión.
- **T4.2** `components/publico/BloqueTorneo.tsx`: cabecera del torneo
  (logo o icono de disciplina como fallback, nombre de competición, país)
  + lista de filas de partido.
- **T4.3** `components/publico/FilaPartido.tsx`: hora (`HH:mm`), escudo
  local, nombre local, escudo visitante, nombre visitante, y marcador si
  el partido ya empezó. Escudo con fallback a iniciales reusando el patrón
  de `avatarUtils.ts`.
- **T4.4** Agrupación por torneo en el cliente a partir de las filas planas
  del endpoint (`Map<torneo_id, filas>`), preservando el orden del backend.
- **T4.5** Selector de fecha (hoy / ayer / mañana) sobre el mismo endpoint. La
  cabecera rotula la fecha explícitamente (C15), nunca solo "Hoy": el
  `TIMESTAMP` no lleva zona y un cliente en otro huso tiene que ver qué día
  está mirando.
- **T4.6 (C1)** Estados vacío / cargando / error. Cuando el día pedido está
  vacío, el backend cae a la fecha más cercana con partidos **acotada a ±7
  días**; fuera de esa ventana devuelve vacío de verdad, en vez de desenterrar
  una jornada de hace meses bajo un rótulo que parece actual. El texto dice
  "No hay partidos de Fútbol el 15/09. Mostrando la jornada del 13/09".
- **T4.7** Tests con MSW: agrupación correcta, orden por hora, fallback de
  escudo, empty state por disciplina.

## Fase 5 (R1) — Deep linking y vista pública de torneo

- **T5.1** Clic en la fila del partido -> `/partidos/:partidoId` (ruta
  pública que **ya existe**). Verificar que `PartidoEnVivo.tsx` se ve bien
  sin sesión.
- **T5.2** Nueva ruta pública `/torneos/:torneoId` ->
  `pages/publico/DetalleTorneoPublico.tsx`: tabla de posiciones,
  goleadores y resultados, con los endpoints públicos de
  `/estadisticas/*` que ya existen.
- **T5.2b (C4)** Botón "Compartir" en la vista pública de torneo y en el
  detalle de partido (copia el deep link con confirmación visible) + meta tags
  Open Graph **estáticos** en `frontend/index.html`. El preview de WhatsApp
  dirá "Score-App" para todo link: el preview por torneo exige prerender y
  queda diferido (C14).
- **T5.2c (C6)** Acción "Ver página pública" en la tarjeta de torneo de
  `TorneosAdmin.tsx`. Sin esto la vista pública de R1 **no tiene ninguna
  puerta de entrada** (el botón Compartir vive dentro de ella), y el umbral de
  4 semanas de C6 mediría cero por razones estructurales y mataría R3 con una
  señal falsa.
- **T5.2d (C6)** Instrumentación: el backend hoy **no tiene logging**
  (`grep -rn "import logging" backend/app` → cero hits; el patrón es
  `print()` en `main.py`). Hay que configurar un logger con handler y
  formateador que preserve `extra` (o escribir una línea JSON a stdout) y
  decidir dónde se retiene, antes de prometer "hits por semana".
- **T5.3** Clic en la cabecera del torneo -> `/torneos/:torneoId`.
  Cabecera y filas son elementos clicables **hermanos**, no anidados: un
  `<button>` dentro de otro `<button>` es HTML inválido y rompe el
  teclado.
- **T5.4** (absorbido por T4.1/C16: `/` decide por sesión, no se reemplaza el
  arranque de los usuarios logeados.)
- **T5.5** Tests de ruteo en `App.routing.test.tsx` para las dos rutas
  públicas nuevas.

## Riesgos y decisiones abiertas

- **D-A: Orden de popularidad.** El requerimiento dice "1. Fútbol, 2.
  Tenis, 3. Baloncesto"; la base dice Fútbol=1, **Baloncesto=2, Tenis=3**
  (`15_migracion_popularidad_disciplinas.sql`). Hay que elegir: cambiar el
  ranking en base o aceptar el que ya está.
- **D-B: RESUELTA (C8).** Solo las disciplinas con partidos publicados en la
  fecha efectiva, vía el sidecar del endpoint. Consecuencia aceptada: en un
  deployment de una sola liga la barra no se renderiza.
- **D-C: RESUELTA (C3).** Las columnas nacen vacías, pero con formulario para
  cargarlas. El fallback a iniciales es el estado por defecto, no el permanente.
- **D-D: RESUELTA (C16).** `/` decide por sesión; el logeado sigue en
  `/dashboard`.
- **D-E: RESUELTA (C5).** Vista SQL nueva, pero colgada de
  `vw_resultados_partidos`, no en paralelo.

## Verificación

`.\verificar.ps1` en verde: pytest backend (reconstruye `torneos_mvp_test`
desde `/database`, incluye `test_scripts_sql.py`), oxlint, `tsc -b
--noEmit`, vitest, `vite build`.


<!-- autoplan-accepted:ceo -->
- **C1 — Densidad del feed.** `GET /partidos/feed` devuelve `fecha_efectiva` además de las filas. Si la fecha pedida no tiene partidos para esa disciplina, cae a la fecha más cercana que sí los tenga (hacia atrás primero, después hacia adelante) y el frontend lo rotula: "No hay partidos de {deporte} el {fecha}. Mostrando la jornada del {fecha_efectiva}". El default de `fecha` sigue siendo hoy. Test: día vacío devuelve `fecha_efectiva` distinta; base sin partidos devuelve lista vacía sin error.
- **C2 — Control de exposición pública.** Agregar `TORNEO.Publicado BOOLEAN NOT NULL DEFAULT TRUE` (en `TORNEO`, la edición — NO en `TORNEO_GRUPO`) en la migración `31_`, con backfill TRUE para las filas existentes: no cambia el comportamiento público que la API ya tiene hoy. **Mecanismo, no solo intención:** `GET /torneos/{torneo_id}` (`routes/torneos.py:54`) y los tres `GET /estadisticas/torneos/{torneo_id}/*` (posiciones, goleadores, resultados) hoy no tienen ninguna dependencia de auth; hay que agregarles `usuario: Usuario | None = Depends(get_current_user_optional)` y devolver 404 **solo cuando el caller es anónimo y `Publicado = FALSE`**. Sin ese matiz se rompe el back-office: `MesaPanel.tsx:91` llama exactamente al mismo `GET /torneos/{torneo_id}`. `vw_feed_partidos` filtra por `Publicado = TRUE`. Toggle "Publicar" en el formulario de edición de torneo (`TorneosAdmin.tsx`), solo TorneoAdmin/AdminGeneral. Tests: el mismo id devuelve 200 para TorneoAdmin y 404 anónimo, en las cuatro rutas; torneo despublicado excluido del feed; `MesaPanel` sigue cargando su torneo despublicado.
- **C3 — Camino de escritura para logos y país.** Además de exponer las columnas, agregar los inputs, nombrando tabla y formulario: `EQUIPOS.Logo_URL` → campo "URL del escudo" en el formulario de `EquiposAdmin.tsx`; `TORNEO_GRUPO.Pais` y `TORNEO_GRUPO.Logo_URL` → campos "País" y "URL del logo" en el formulario del grupo de torneo (`TorneoGrupoUpdate` + `PATCH /torneo-grupos/{id}` ya existen, es solo UI). Sin esto las columnas nacen y quedan NULL para siempre.
- **C4 — Canal de distribución.** Botón "Compartir" en la vista pública de torneo y en el detalle de partido, que copia el deep link al portapapeles con confirmación visible. Meta tags Open Graph **estáticos** en `frontend/index.html` (title, description, image). Alcance honesto: el preview de WhatsApp dice "Score-App", el mismo para todo link — un preview por torneo exigiría SSR o un endpoint de prerender, que queda diferido con su costo anotado (ver C14). El botón Compartir es el que entrega el valor; los OG estáticos solo evitan que el link se vea como texto pelado.
- **C5 — Una sola fuente de verdad del marcador.** `vw_feed_partidos` se construye SOBRE `vw_resultados_partidos` (que ya deriva goles con la regla de autogol vía `vw_goles_acreditados` y contempla walkover, y no filtra por estado), sumándole los JOIN a TORNEO, TORNEO_GRUPO y DISCIPLINA. Prohibido reimplementar el conteo de goles. Sigue la decisión Eng #10 ya registrada en `04_views.sql`.
- **C5b — Hueco #5, diferido con nombre.** Los query params `fecha` y `disciplina_id` en `GET /api/v1/partidos` NO entran en este plan: ningún consumidor de esta entrega los usa (el feed va por `/partidos/feed`), y agregarlos ahora sería exactamente el segundo camino paralelo que la Sección 5 marca como el riesgo principal. Se difiere a TODOS.md junto con C14, anotando que el hueco existe y por qué no se cierra todavía.
- **C6 — Saber si funciona.** Métrica declarada, acotada a lo que la instrumentación realmente soporta: **hits por semana a `/partidos/feed` y a la vista pública de torneo, y la razón entre ambos** (cuántos de los que ven el feed entran a un torneo). No se declara "sesiones" ni "conversión por sesión": el log no lleva identificador de sesión y no se va a agregar uno. Instrumentación: `logger.info("feed_hit", extra={...})` con `endpoint`, `disciplina_id`, `fecha`, `fecha_efectiva` — sin IP, sin user-agent, sin datos personales. Reemplaza el `print()` de `main.py` como patrón para código nuevo. Nada de infraestructura nueva. **Umbral y fecha de revisión:** si a las 4 semanas del release R1 los hits a la vista pública de torneo siguen en cero, R3 (feed + barra de deportes) no se construye — se replantea el canal primero.
- **C7 — Puerta de entrada a Control de Mesa.** En vez de mover la lista a una pestaña de `TorneoAdminLayout` (que está alcanzado a UN torneo mientras que la lista no lo está), el `NavLink` de `NavBar.tsx` se condiciona por rol: visible solo para TorneoAdmin, AdminGeneral y Arbitro. El público deja de verlo, que es lo que se pidió, y el operador conserva su acceso. Se mantiene además el botón por fila "Gestionar en Mesa" en `PartidosDelTorneo.tsx` hacia `/control-de-mesa/partido/:id`.
- **C8 — Barra de deportes con contenido.** La barra pública muestra solo las disciplinas que tienen al menos un partido publicado en la fecha visible; nunca las 28 del catálogo. **No es derivable de la respuesta filtrada** (una respuesta de Fútbol solo trae Fútbol): `GET /partidos/feed` devuelve un sidecar `disciplinas_con_partidos` calculado ANTES de aplicar `disciplina_id`. "Fecha visible" queda definida como `fecha_efectiva` (la que el fallback de C1 terminó mostrando), no la pedida. Con una sola disciplina con contenido la barra se oculta. **Consecuencia aceptada explícitamente:** en un deployment de una sola liga de fútbol —que es el wedge que el design doc describe— la barra no se renderiza y el requerimiento #2 queda latente hasta que exista una segunda disciplina con partidos. Es deliberado: 27 pills muertas son peores que ninguna barra.
- **C9 — Resecuenciar las fases.** Orden de entrega: **(R1)** migración `31_` (incluido `Publicado`) + vista pública de torneo + deep links + botón compartir + OG + log; **(R2)** vista `vw_feed_partidos` y endpoint `/partidos/feed`; **(R3)** feed, barra pública de deportes y cambio de `/`. La migración se adelanta a R1 a propósito: `Publicado` es lo que protege la vista pública de torneo, y publicar esa vista una release antes que su propio guard dejaría expuestos los torneos borrador justo en la ventana R1. Cada release es desplegable solo.
- **C10 — Cerrar los fallos silenciosos.** (a) Partidos sin equipos definidos (shells de bracket con `equipos_id_local`/`equipos_id_visitante` NULL) ya quedan excluidos gratis: `vw_resultados_partidos` usa `JOIN EQUIPOS` interno (`04_views.sql:193-195`) y `vw_feed_partidos` cuelga de ella. No agregar un `WHERE ... IS NOT NULL` redundante; sí agregar el test de regresión que lo fija. (b) El feed y la barra de deportes renderizan estado de error visible con reintento; la barra degrada a vacío sin romper el header. (c) Todo escudo o logo usa `onError` para caer a iniciales, reusando el patrón de `avatarUtils.ts`. (d) `Logo_URL` se valida en el backend contra el esquema `https:` y se renderiza solo como `src` de `<img>`, nunca como HTML. (e) Filas de partido y cabecera de torneo son elementos clicables hermanos (`<a>`/`<button>` reales), con alto mínimo de toque de 44px; nombres largos con `text-overflow: ellipsis`. (f) Todo test que dependa de "hoy" congela la fecha en vez de usar la del sistema.
- **C11 — Verificar el plan de ejecución, con plan B.** **Corrección: el índice ya existe** — `idx_partidos_fecha ON PARTIDOS(Fecha_Partido)` está en `database/03_indexes.sql:82`. No agregarlo (un `CREATE INDEX` duplicado rompería la idempotencia que C13 exige). Lo que sí hay que hacer: correr `EXPLAIN` una vez sobre el feed para confirmar que el predicado de fecha baja por debajo del `GROUP BY p.ID` que `vw_feed_partidos` hereda de `vw_resultados_partidos`. **Si no baja** (riesgo real: agregaría el historial entero para devolver un día), el plan B es que `vw_feed_partidos` aplique el rango de fechas como `WHERE` sobre `PARTIDOS` antes de unirse a la vista de resultados, o que el feed pase a ser una query parametrizada en el service en vez de una vista. Este es el único punto del enfoque que puede no funcionar, y ahora tiene salida.
- **C12 — Nombre correcto del endpoint.** El endpoint del feed vive en `GET /api/v1/partidos/feed`, en el router de partidos, no en `/estadisticas/`. Una lista de partidos no es una estadística. Se registra antes de `/{partido_id}` para que FastAPI no interprete "feed" como un id.
- **C13 — Disciplina de migración de este repo.** Toda columna nueva de C2/C3 se agrega en LOS TRES lugares: `database/01_schema.sql`, el script `database/31_migracion_portal_publico.sql` (idempotente, con guarda sobre `information_schema`, porque `test_scripts_sql.py` lo corre dos veces) y la lista `SCRIPTS_VIGENTES` de `backend/tests/test_scripts_sql.py`. Omitir cualquiera revienta las ~40 suites de backend con `UndefinedColumn`.
- **C14 — Diferidos a TODOS.md.** Cuatro ítems, cada uno con contexto y condición de reentrada, no como intención vaga: (1) auto-refresh en vivo del feed (polling o WebSocket); (2) uploader de imágenes para escudos y logos; (3) preview de Open Graph por torneo/partido, que exige SSR o un endpoint de prerender (ver C4); (4) los query params `fecha`/`disciplina_id` de `GET /partidos` (hueco #5, ver C5b).
- **C15 — Definir "día" antes de construir "los partidos del día".** `PARTIDOS.Fecha_Partido` es `TIMESTAMP` sin zona horaria. Se declara: la fecha es la del servidor, `fecha` por default es `CURRENT_DATE` del servidor, y la UI rotula la fecha explícitamente en la cabecera del feed en vez de decir "Hoy" a secas — así un cliente en otro huso ve qué día está mirando en vez de un feed corrido. Todos los tests congelan el reloj (ya cubierto por C10f). Queda anotado en el runbook.
- **C16 — `/` decide por sesión.** La home pública no reemplaza el arranque de los usuarios logeados: `/` renderiza el feed para un caller anónimo y sigue redirigiendo a `/dashboard` cuando hay sesión. Es el único cambio de esta entrega que toca a todo usuario existente, así que va con su test (`/` anónimo → feed; `/` logeado → `/dashboard`) y con un comentario en `App.tsx` explicando por qué la ruta decide por sesión.
- **C17 — La superficie pública de partido, decidida y no dejada a medias.** `PartidoEnVivo.tsx:61` consume `GET /estadisticas/torneos/{torneo_id}/resultados`. Si C2 hace que esa ruta devuelva 404 para anónimos, la página pública de un partido de un torneo despublicado queda a medio renderizar (equipos, marcador y eventos cargan; resultados revienta). Hay que elegir explícitamente una de las dos y testearla: (a) gatear también `/partidos/:id` y `GET /partidos/{id}` por `Publicado`, devolviendo un 404 limpio; o (b) declarar la superficie de partido pública pase lo que pase y hacer que la query de resultados tolere el 404. No queda a criterio del implementador.
- **C18 — Dónde NO alcanza `Publicado`, dicho en voz alta.** El guard de C2 cubre el detalle, pero hoy enumeran torneos sin filtrar y siguen públicos: `GET /torneos` (lista, `torneos.py:14`), `GET /partidos?torneo_id=`, `GET /torneos/{id}/bracket` (`motor_formatos.py:71`), `GET /estadisticas/proximos-partidos` y `GET /estadisticas/equipos/{id}/plantilla`. Con solo el detalle gateado, el listado sigue devolviendo el nombre y el fixture completo de un torneo borrador. Decisión obligatoria antes de implementar: o `GET /torneos` filtra `Publicado` para callers anónimos, o se documenta en el plan por qué cada superficie queda abierta. Silencio no es una respuesta.
- **C19 — El costo real de C3, corregido.** "Es solo UI" era falso. Verificado: `TorneoGrupoUpdate` (`schemas/torneo_grupo.py:19`) solo acepta `nombre` y `estado`, y `TorneosAdmin.tsx` no tiene formulario de edición de torneo (su `Modo` es `lista | crear-grupo | nueva-edicion`; el único PATCH, línea 269, archiva el grupo). Solo la mitad de Equipos es barata (usa el builder genérico `camposEquipo`). Lo demás exige campos de schema, servicio, mutación y formulario nuevos, en dos entidades distintas. El esfuerzo de C3 sube de S a M y así queda anotado.
- **C20 — Logging: es infraestructura, no una línea.** `grep -rn "import logging|getLogger" backend/app` devuelve cero hits: el backend no tiene logger, ni handler, ni formateador, y el único patrón es `print()` en `main.py`. Bajo el formateador por defecto de uvicorn, `logger.info(..., extra={...})` descarta los campos de `extra`, y el servidor se levanta a mano sin retención de logs. Así que C6 no es gratis: hay que configurar logger + handler + formateador (o emitir una línea JSON a stdout) y decidir dónde se retiene. Si eso no se hace, la métrica de C6 no se puede recolectar y el umbral de 4 semanas es una ficción — en ese caso se baja la métrica a lo que sí se pueda contar y se dice.
<!-- /autoplan-accepted:ceo -->

<!-- autoplan-accepted:design -->
- **D1 — El grid de la fila de partido, escrito.** T4.3 deja de ser una enumeración. Layout explícito: `grid-template-columns: 48px 1fr 40px` — columna de hora/minuto a la izquierda, columna de equipos al medio con DOS renglones apilados (local arriba, visitante abajo, cada uno con su escudo de 20-24px), columna de marcador a la derecha. Marcador y hora con `font-variant-numeric: tabular-nums` para que los dígitos no bailen entre filas. La enumeración horizontal de seis elementos no entra en 400px con nombres reales ("Deportivo Municipal" vs "Atlético Independiente"): el `text-overflow: ellipsis` de C10e era la confesión de que el layout no cabía.
- **D2 — Tabla estado → tratamiento visual, cerrada sobre el enum real.** `PARTIDOS.Estado` tiene exactamente 4 valores (`chk_partidos_estado`, `02_constraints.sql:251`): `Programado` → columna izquierda muestra la hora, sin marcador, texto normal; `En curso` → muestra el minuto, marcador visible, color de acento en vivo con punto indicador; `Finalizado` → muestra `FIN`, marcador visible en tono apagado; `Cancelado` → no aparece (el `WHERE` de T3.2 ya lo excluye). Distinguir "en curso" de "finalizado" es la razón por la que alguien abre un portal de resultados: no pueden compartir el mismo marcador neutro. Corrección a la voz de diseño: en este esquema NO existen `Suspendido` ni `Aplazado`, así que el `<> 'Cancelado'` no excluye nada por accidente.
- **D3 — El selector de fecha y el fallback dejan de contradecirse.** Se elige la opción barata: el fallback de ±7 días de C1 aplica **solo a la carga inicial sin `fecha` en la URL**. Cuando el usuario navega explícitamente (toca ayer/hoy/mañana o una fecha), NO hay fallback: si ese día no tiene partidos, se muestra el empty state de ese día. Sin esto, tocar "Mañana" podía devolver la jornada de hace tres días con la pill "Mañana" activa, y tocar "Ayer" podía no cambiar nada — el control mintiendo sobre su propio contenido.
- **D4 — `truncado` se renderiza o no existe.** Se renderiza: pie de lista con "Mostrando los primeros N partidos del día" y una acción que amplía el `limit`. Un campo del envelope que ningún componente pinta es un feed que termina en seco sin avisar.
- **D5 — La barra de deportes no salta ni se reordena bajo el dedo.** (a) Altura reservada desde el primer render (skeleton de pills o `min-height` fijo en el contenedor), para que la llegada de la respuesta no empuje el feed hacia abajo justo cuando el usuario va a tocar la primera fila. (b) El contenido de la barra se congela con el set de la PRIMERA respuesta de la sesión de navegación y no se reordena en cada cambio de filtro — si no, elegir Tenis cambia `fecha_efectiva`, que cambia el sidecar, que hace desaparecer pills vecinas. (c) Si la disciplina pedida por URL no está en el sidecar, su pill se muestra igual, activa, con el empty state del feed: nunca se borra el control que el usuario acaba de usar.
- **D6 — El feed tiene puerta de entrada para usuarios con sesión.** C16 manda al logeado a `/dashboard` y T1.2 le saca el link de Dashboard al anónimo; entre las dos, nadie con sesión puede llegar al feed — ni el TorneoAdmin que acaba de cargar los partidos. Se agrega un link "Portal público" en el `NavBar` para usuarios con sesión. Es el mismo razonamiento que C6 aplicó a la vista de torneo (T5.2c) y que no se había aplicado al feed. Una línea.
- **D7 — El detalle de partido recupera identidad y salida.** Verificado en `PartidoEnVivo.tsx:196-210`: hoy la página se identifica con `resultado?.equipo_local ?? "Local"` y `resultado ? marcador : "- : -"`. El visitante que llega desde WhatsApp ve dos nombres y un marcador flotando, sin torneo, sin fecha y sin vuelta. Se agrega cabecera con nombre y país del torneo enlazada a `/torneos/:torneoId` — el eslabón partido→torneo, que es justamente la segunda página vista que C6 quiere medir. Y si C17 se resuelve por la opción (b) (tolerar el 404), el estado degradado es un mensaje explícito "Resultados no disponibles para este torneo", nunca los placeholders `Local - : - Visitante`, que se leen como datos reales.
- **D8 — La vista pública de torneo deja de asumir liga.** (a) Las tres secciones se organizan en pestañas: Posiciones | Resultados | Goleadores, con Resultados por defecto si el torneo ya empezó. (b) Para un torneo de formato Eliminación no hay tabla de posiciones: se muestra el bracket (`GET /torneos/{id}/bracket`, `motor_formatos.py:71`) en su lugar, o se omite la pestaña. (c) Empty state por sección — un torneo recién creado no muestra tres tablas de ceros, que es la peor primera impresión posible de una página cuyo único propósito es ser compartida.
- **D9 — Frescura honesta en el feed.** `PartidoEnVivo.tsx:9` refresca cada 5s (`LIVE_POLL_MS`); el feed no refresca (C14, correcto). Pero el visitante que ve un marcador moverse en el detalle y vuelve a un feed congelado concluye que el feed está roto. Se agrega rótulo de frescura en la cabecera ("Actualizado 14:32") y un botón de recarga manual (`refetch` de react-query). Cero infraestructura, y hace honesta la promesa.
- **D10 — Estados específicos, no genéricos.** El patrón vigente del repo es `<p>Cargando partido...</p>` (`PartidoEnVivo.tsx:162`); un texto suelto en una pantalla en blanco no sirve como portada del producto. Carga: skeleton de 3-5 filas con la misma métrica del grid de D1 (no spinner — el feed tiene forma conocida). Y el vacío REAL (fuera de la ventana ±7 días) necesita su propio copy, distinto del copy del fallback que C1 ya escribió: "No hay partidos de Fútbol esta semana", con acción hacia otra disciplina.
- **D11 — La barra pública llega a 44px.** Medido: `.chip-disciplina` (`index.css:1122`) es `padding .45rem .85rem` + `font-size .9rem` ≈ 33px de alto, por debajo del mínimo de 44px que el propio plan se exige en C10e. Se crea la variante `.chip-disciplina--publico` con `min-height: 44px`, sin tocar el chip del back-office (no mover la densidad de `TorneosAdmin`).
- **D12 — La URL del deporte, decidida.** `/?deporte=<slug>` — slug legible, compartible, y deja `/` como home. Se descarta `/deporte/:disciplinaId` (id numérico, ilegible en un link de WhatsApp, y compite con `/` como ruta). Además se declara el estado por defecto: sin `?deporte`, el feed muestra TODAS las disciplinas agrupadas, y la barra pública NO lleva pill "Todos" (el estado "todos" es la ausencia de filtro, no un chip más).
- **D13 — El header público es su propia estructura.** Verificado: `.nav-bar` (`index.css:47`) es `flex` + `flex-wrap` con `.nav-bar__links{flex:1}`, y bajo 480px `.nav-bar__links` lleva `order:3; width:100%`. Meter la barra "como segunda fila" no es agregar un hijo: exige `order`/`width` propios y reordenar el móvil. Y con T1.2 el anónimo se queda sin ningún link, dejando `.nav-bar__links` vacío pero con `flex:1` — un hueco expansivo entre la marca y "Iniciar sesión". Se especifica: fila 1 marca + sesión, fila 2 la barra, y `nav-bar__links` no se renderiza cuando queda vacío.
- **D14 — Un sistema visual, no dos.** (a) El fallback del logo de torneo usa el patrón monocromo de iniciales de `avatarUtils.ts` (el mismo que ya usan los escudos en T4.3), NO el emoji de disciplina: escudos PNG reales y emojis del sistema conviviendo en la misma columna vertical tienen pesos ópticos incompatibles y renderizan distinto en Windows, Android e iOS. (b) `TORNEO_GRUPO.Pais` es `VARCHAR(60)` libre y se va a llenar con "Argentina", "ARG" y "argentina" en la misma pantalla: el formulario de C3 usa un `<select>` de países (o ISO-2), no un input de texto libre.
- **D15 — "Compartir" especificado hasta el fallback.** El botón intercambia su propio label por "¡Copiado!" durante 2s (sin introducir un sistema de toasts nuevo). En móvil usa `navigator.share` cuando está disponible. `navigator.clipboard` no existe en contexto inseguro: si falta, se muestra el link en un campo seleccionable en vez de que el botón no haga nada y no avise.
- **D16 — "Ver página pública" no engaña al admin.** Con su sesión, el admin abre un torneo despublicado y la página carga perfecto (por C2, el 404 es solo para anónimos), así que se va convencido de que el link funciona hasta que alguien lo recibe y ve un 404. En la tarjeta de `TorneosAdmin.tsx` se muestra el estado de publicación junto al botón, y si está despublicado el label pasa a "Vista previa (no publicado)" con un aviso en la propia vista pública visible solo para el admin. Además, el 404 público de un torneo despublicado necesita diseño: no la pantalla de error cruda del router.
- **D17 — Tematizar las superficies del navegador.** Color de selección, caret, focus ring, scrollbar y `underline-offset` salen hoy de los defaults del navegador, que no pertenecen a ningún sistema de diseño. Se definen desde la paleta de `index.css`. Es el reflejo más barato que separa una página diseñada de una ensamblada, y el que más se saltea.
<!-- /autoplan-accepted:design -->

<!-- autoplan-accepted:dx -->
- **F1 — Camino a "hello world" para el feed.** Agregar `database/seed_portal_demo.sql` (o un fixture de pytest reutilizable) que cree 2 torneos de 2 disciplinas, publicados, con partidos en `CURRENT_DATE` cubriendo los 3 estados visibles de D2 (`Programado`, `En curso`, `Finalizado`). Sin esto, un dev que clona el repo y corre las migraciones ve una página en blanco y no puede distinguir "lo implementé mal" de "no hay datos para hoy": el TTHW de esta feature es indefinido, no lento. Va con una línea en el runbook: correr el seed y abrir `/`.
- **F2 — El plan se refunde por release, no se lee con un anexo de correcciones.** Antes de implementar, las tareas se reescriben en UNA lista ordenada por R1 → R2 → R3, con cada obligación C/D ya aplicada al texto de la tarea y la referencia entre paréntesis como nota, no como fuente que hay que ir a buscar al final. Hoy el documento se contradice si se lee en orden: T2.4 ofrece dos formas de URL y D12 descarta una; T4.6 define el fallback en toda carga y D3 lo restringe a la inicial; C3 dice "es solo UI" y C19 dice que era falso; las Fases 1-5 no corren en el orden que C9 manda. Un implementador que lea de arriba a abajo construye la versión equivocada de cuatro cosas. Además: `T5.4` queda como tarea muerta ocupando un id, y `T3.4`/`T3.4b` agrupan como sub-items dos trabajos de tamaño muy distinto.
- **F3 — El slug del deporte existe en la base o la URL pública no resuelve.** D12 promete `/?deporte=<slug>`, pero `GET /partidos/feed` acepta `disciplina_id`, el sidecar devuelve `{id, nombre}` y `DISCIPLINA` no tiene columna de slug en ninguna parte. Un link de WhatsApp llega con un slug y el frontend necesita un id que solo viene en la respuesta del endpoint que todavía no puede llamar. Se agrega `DISCIPLINA.Slug VARCHAR(60) UNIQUE` en la migración `31_` (backfill con `lower` + `unaccent` + `regexp_replace`, en los TRES lugares de C13), el sidecar pasa a `{id, slug, nombre}`, y el endpoint acepta `deporte` (slug) además de `disciplina_id`. El slug se genera en un solo lugar: la base. Sin esto hay un `slugify` en el cliente que tiene que coincidir por casualidad con el que generó el link ("Fútbol" → `futbol` vs `fútbol`).
- **F4 — La semántica del sidecar deja de ser circular.** C8 dice que `disciplinas_con_partidos` se calcula ANTES del filtro de disciplina, y que se calcula sobre `fecha_efectiva` — pero `fecha_efectiva` se eligió aplicando ese mismo filtro (C1). Caso reproducible: hoy hay Fútbol y no Tenis; el usuario toca Tenis, `fecha_efectiva` cae al 09/09, el sidecar calculado sobre el 09/09 puede no incluir Fútbol y la pill de Fútbol desaparece. D5b congela la barra y tapa el síntoma en la UI, pero el contrato sigue siendo indefendible para cualquier otro consumidor. Se resuelve en el contrato: **el sidecar se calcula siempre sobre `fecha_pedida`**, independiente de todo filtro. Definición limpia y nombre honesto.
- **F5 — El fallback de fecha es un parámetro, no un `if` del cliente.** D3 resolvió bien el problema de producto pero lo puso en el frontend ("el fallback aplica solo cuando no hay `fecha` en la URL"), lo que deja al endpoint sin forma de expresar "dame el 16/09 y si está vacío, vacío", y al cliente sin forma de pedir "hoy sin fallback". Se agrega `ventana_fallback_dias: int = Query(7, ge=0, le=30)`, donde `0` desactiva el fallback. El frontend manda `7` en la carga inicial y `0` al navegar. La regla queda en el contrato, testeable desde el backend, y no en un `if` de un componente que el próximo consumidor no va a replicar.
- **F6 — Naming consistente en `FeedPartidoOut`.** Hoy conviven tres convenciones (`logo_torneo` entidad, `logo_local` rol, y ninguno con `_url` aunque el repo usa `Foto_URL`/`foto_url`), y 17 campos planos donde `partido.torneo` es un nombre y `partido.torneo_id` un entero. Se anida: `torneo: {id, nombre, grupo, pais, logo_url}`, `local: {id, nombre, logo_url, goles}`, `visitante: {...}`. El agrupamiento por torneo de T4.4 se vuelve trivial y el tipo generado se documenta solo.
- **F7 — `truncado` se completa o se elimina.** Falta `total_disponible` (el `COUNT` sale de la misma query), sin el cual el pie de D4 no puede decir "de M"; falta definir si N es el `limit` pedido o lo realmente devuelto tras cortar en borde de torneo (siempre menor); y falta el comportamiento en el tope `le=200` (¿el botón desaparece, se deshabilita, o sigue mintiendo?). Con `total_disponible` presente, `truncado` es derivable y puede eliminarse del envelope.
- **F9 — Un envelope de error, con código estable.** El plan no especifica un solo cuerpo de error en ningún punto. Se define `{detail, codigo, sugerencia}` con `codigo` estable (`torneo_no_publicado`, `torneo_inexistente`, `logo_url_insegura`) para todo lo nuevo. **Cuidado con la fuga:** devolver `torneo_no_publicado` a un anónimo revela que el torneo existe, así que para caller anónimo se devuelve un código genérico y el discriminador solo viaja con sesión. El frontend mapea `codigo` → copy; hoy mapea un status pelado a un copy que adivina, y el copy que D7 exige ("Resultados no disponibles para este torneo") solo es correcto en uno de los tres casos que producen ese 404. Incluye el mensaje que ve el TorneoAdmin que pegó una URL `http://` — la validación de C10d hoy pide el chequeo y no pide el mensaje.
- **F10 — El fallo más probable de la entrega se guarda en un test, no en prosa.** C13 dice que omitir uno de los tres lugares "revienta las ~40 suites con `UndefinedColumn`" — un modo de falla conocido, con causa y arreglo identificados, cuya única defensa es que el implementador recuerde leer C13. El síntoma no se autoexplica: el error dice `column "logo_url" does not exist`, no menciona `SCRIPTS_VIGENTES` ni `01_schema.sql`. Se agrega a `test_scripts_sql.py` un test que compare el set de columnas que produce `01_schema.sql` contra el que producen los scripts de `SCRIPTS_VIGENTES`, y falle con un mensaje que nombre el archivo faltante. Es el arreglo de mayor retorno por línea escrita de todo el plan: convierte 40 errores mudos en 1 error que dice qué hacer.
- **F11 — Decir que la migración no necesita rollback.** `31_` es aditiva e idempotente (y T3.6 la corre dos veces), pero no hay down-migration ni nota. C9 promete "cada release es desplegable solo", y desplegable no es replegable. Una línea en el encabezado del `.sql` y en el runbook: aditiva, sin rollback necesario, el código viejo ignora las columnas nuevas por `extra=ignore`.
- **F12 — El endpoint se documenta donde el dev lo va a leer.** `npm run gen:api` regenera tipos, no semántica: `fecha_efectiva: string` no dice que puede diferir de `fecha_pedida`, y `truncado: boolean` no dice que el corte respeta bordes de torneo. Docstring en el handler con las tres reglas no obvias (fallback y su ventana, orden `torneo_grupo → torneo → fecha → id`, corte en borde de bloque) + un `example` en `model_config` de la respuesta + un curl copy-paste en el runbook. El plan hoy no tiene un solo ejemplo copiable.
- **F13 — La métrica de C6 se cierra o se baja, pero no queda a medias.** C6 fija un gate duro (4 semanas, cero hits → R3 no se construye) y C20 admite que el logging es infraestructura inexistente. Antes de R1 hay que cerrar los tres pendientes: formato exacto de la línea (`{"evt":"feed_hit","endpoint":...,"disciplina_id":...,"fecha":...,"fecha_efectiva":...,"ts":...}` a stdout), dónde se retiene (archivo rotado o journald, con nombre), y el comando literal de conteo en el runbook. Si no se cierran, entonces se baja la métrica explícitamente y **se borra el umbral de 4 semanas**: un gate que no se puede evaluar se resuelve por default, y el default sería construir R3, que es justo lo que el gate quería impedir.
- **F14 — El runbook existe o no se lo cita.** C15 y F1 mandan anotar cosas "en el runbook" y ese archivo no existe ni tiene ruta. Se crea `docs/runbook-portal-publico.md` (seed, curl de ejemplo, comando de conteo de la métrica, nota de rollback, veredicto del `EXPLAIN`), o esas notas se mandan a `TODOS.md`, que sí existe y que el plan ya usa bien.
- **F15 — El `EXPLAIN` de C11 con criterio binario.** "Confirmar que el predicado de fecha baja por debajo del `GROUP BY`" no es evaluable como está. Se escribe el `EXPLAIN (ANALYZE, BUFFERS)` exacto a correr, el criterio binario que dispara el plan B (si el plan muestra un Seq Scan sobre `PARTIDOS` con el filtro de fecha aplicado DESPUÉS del Aggregate, se activa el plan B de C11), y dónde se pega el output (el runbook de F14).
- **F16 — `verificar.ps1` declara qué cubre.** El plan agrega pasos (migración `31_`, `EXPLAIN`, `npm run gen:api`) sin decir si entran en el único gate descrito. Un dev que ve verde no sabe si su `schema.d.ts` quedó desactualizado. Se agrega `gen:api` + `git diff --exit-code frontend/src/api/schema.d.ts` al script, que convierte "me olvidé de regenerar" en un fallo con nombre, y se lista explícitamente qué queda manual.
- **F17 — "Sesión de navegación" definida y con salida.** D5b congela la barra "con el set de la PRIMERA respuesta de la sesión de navegación" y ese término no está definido en ningún lado (¿montaje del componente? ¿vida de la pestaña? ¿`sessionStorage`?), así que cada implementador elige distinto. Peor: sin evento de descongelado, una pestaña abierta desde ayer muestra pills de ayer para siempre. Se define como el ciclo de vida del `QueryClient` (la barra lee un `useQuery` de key fija que la primera respuesta puebla) y se engancha el descongelado al botón de recarga manual que D9 ya introduce. Gratis.
- **F18 — La barra no dispara la query del feed en toda la app.** T2.3/D13 la montan en `NavBar`, que se renderiza en TODAS las rutas — incluidas `/torneos/:id`, `/partidos/:id` y el back-office — y T2.2 la alimenta del sidecar de `GET /partidos/feed`. Nunca se dice si eso significa una llamada de feed completa en cada página solo para pintar pills. Se decide y se escribe: la barra **lee la caché** de react-query con la key del feed y no dispara la query; con caché vacía no se renderiza, consistente con la regla "≤1 disciplina → no se renderiza" de C8.
- **F20 — `/dashboard` para anónimo, decidido.** T1.2 esconde el link y cambia el catch-all, pero no dice si `/dashboard` tipeado directo sigue alcanzable para un anónimo. Si sigue, se escondió el link sin cambiar la superficie; si no sigue, es un cambio de comportamiento sin `RequireRole` mencionado y sin test. Se escribe la decisión y se agrega el caso a `App.routing.test.tsx`. D6 ya resolvió bien la mitad simétrica (link "Portal público" para el logeado); falta esta.
- **F-DIFERIDOS — a TODOS.md, con condición de reentrada.** (1) `tz` como parámetro del feed (F8): C15 rotula la fecha en la UI, que alcanza para el wedge de una liga local, pero un consumidor en otro huso no tiene salida programática; reentra cuando exista un torneo fuera del huso del servidor. (2) Flag para forzar la barra de deportes con una sola disciplina (F19a): reentra si el requerimiento #2 hace falta demostrarlo antes de tener una segunda disciplina.
<!-- /autoplan-accepted:dx -->

<!-- autoplan-accepted:eng -->
- **E-B1 — La migración `31_` no puede depender de `unaccent`.** Verificado: `grep -rn "CREATE EXTENSION|unaccent" database/` devuelve **cero hits** — la extensión no está instalada ni declarada en ningún script, así que el backfill de slug de F3 haría fallar `31_` con `function unaccent(text) does not exist` en cualquier base limpia, incluida la que arma `test_scripts_sql.py`. Se reemplaza por `translate()` sobre el mapa de acentos del español: SQL puro, `IMMUTABLE` (a diferencia de `unaccent`, lo que además deja la puerta abierta a un índice de expresión o a una columna generada), y suficiente para un catálogo fijo de 28 filas. No se agrega la extensión: sumaría un requisito de privilegios en el entorno de deploy a cambio de nada.
- **E-B2 — El slug se genera para toda fila, no solo para el backfill.** F3 solo proponía un `UPDATE` en `31_`, pero `11_catalogo_disciplinas.sql` está en `SCRIPTS_VIGENTES`, es re-ejecutable, y es el único mecanismo real de alta (`routes/disciplinas.py` no tiene `POST`). Una disciplina agregada después de `31_` nacería con `Slug = NULL` y su deep link no resolvería, en silencio — y el `UNIQUE` no la atrapa porque acepta múltiples NULL. Se agrega un trigger `BEFORE INSERT OR UPDATE OF Nombre` en `06_triggers.sql` (mismo patrón que `fn_validar_torneo_modalidad`), el backfill de `31_` queda solo para las filas preexistentes, y `Slug` pasa a `NOT NULL` después del backfill. **Ojo con M7:** el trigger genera el slug en `INSERT`, y en `UPDATE` solo si `Slug IS NULL` — si no, un rename vía `PATCH /disciplinas/{id}` cambiaría el slug y rompería links ya compartidos.
- **E-B3 — Las dos decisiones que el plan identificó y no tomó, tomadas.** C18 decía "decisión obligatoria antes de implementar... silencio no es una respuesta" y después el plan calló; C17 decía "no queda a criterio del implementador" y T3.4b la re-delegó en una referencia circular. Se resuelven acá: **(a) `Publicado` filtra también donde los torneos son enumerables.** Con solo el detalle gateado, un anónimo igual obtiene el borrador completo por `GET /torneos` (`torneos.py:14`), `GET /partidos?torneo_id=` (`partidos.py:56`), `GET /torneos/{id}/bracket` y `GET /estadisticas/proximos-partidos` (cuya vista proyecta `t.Nombre AS Torneo`, `04_views.sql:50`). Gatear el detalle y dejar la lista abierta es el peor de los dos mundos: agrega auth a 4 rutas y no cierra nada. Se agrega el predicado `Publicado` para caller anónimo en `TorneoRepository.list` (junto a `incluir_archivados`, mismo lugar), en `PartidoRepository.list`, y en `vw_proximos_partidos`. **(b) C17 se resuelve por la opción (b):** la superficie de partido queda pública pase lo que pase, y la query de resultados tolera el 404 con el copy explícito de D7. La opción (a) rompería links ya compartidos y toca más superficie.
- **E-L1 — El feed no puede perder la final el día de la final.** `chk_torneo_estado` admite `'Activo'`, `'Inactivo'` y `'Finalizado'` (`02_constraints.sql:50`). El `WHERE TORNEO.Estado = 'Activo'` de T3.2 hace que, el día que el admin marca el torneo como `Finalizado` —típicamente el día de la final—, ese partido desaparezca del feed de hoy, del "ayer" de mañana y de toda la ventana de fallback. El predicado pasa a `TORNEO.Estado <> 'Inactivo'`. Test obligatorio: torneo `Finalizado` con partido hoy → aparece.
- **E-L2 — El predicado de fecha tiene que ser sargable.** `idx_partidos_fecha` está sobre el `TIMESTAMP` (`03_indexes.sql:82`), así que la forma natural de escribir "los partidos del día" (`DATE(Fecha_Partido) = :fecha` o `Fecha_Partido::date = :fecha`) **no puede usarlo**: la expresión no coincide con la clave. C11 dio el tema por cerrado porque el índice existe; el problema era cómo se escribe el predicado. Se obliga el rango semiabierto: `p.Fecha_Partido >= :fecha AND p.Fecha_Partido < :fecha + INTERVAL '1 day'`. Y el criterio binario de F15 se reescribe en función de esto, que sí es evaluable: el `EXPLAIN (ANALYZE, BUFFERS)` debe mostrar `Index Scan using idx_partidos_fecha`; un `Seq Scan on partidos` dispara el plan B. (Nota a favor del plan: el pushdown a través del `GROUP BY` de `vw_resultados_partidos` sí ocurre — `Fecha_Partido` es columna de agrupación y el qual no es volátil.)
- **E-L3 — Los 5 JOIN de `vw_feed_partidos`, enumerados, y los `Estado` nullable, contemplados.** `vw_resultados_partidos` proyecta solo `el.ID`, `el.Nombre`, `ev_eq.ID`, `ev_eq.Nombre` de `EQUIPOS` (`04_views.sql:169-201`): no expone `Estado` ni expondrá `Logo_URL`. T3.2 pedía filtrar por `EQUIPOS.Estado` y traer los logos sin enumerar que eso son **dos JOIN más a EQUIPOS**. Se escriben los 5 explícitos: TORNEO, TORNEO_GRUPO, DISCIPLINA y EQUIPOS ×2 (sobre `Equipo_Local_ID` y `Equipo_Visitante_ID`). Y como `EQUIPOS.Estado`, `TORNEO.Estado` y `DISCIPLINA.Estado` son todos nullable (`VARCHAR(20) DEFAULT 'Activo'` sin `NOT NULL`, y el `CHECK ... IN (...)` deja pasar `NULL` por lógica de tres valores), todos los filtros de estado usan `IS DISTINCT FROM 'Inactivo'` y no `= 'Activo'`, que descartaría filas en silencio.
- **E-L4/E-M3 — La barra de deportes tiene su propio endpoint; el sidecar se elimina.** Tres problemas se cierran con un solo cambio. (1) **L4:** con el sidecar sobre `fecha_pedida` (F4), un feriado sin partidos daba sidecar vacío → la barra no se renderiza (regla de C8) mientras el fallback muestra dos deportes llenos: un feed con contenido y sin control para cambiar de deporte, justo el día en que más hace falta. (2) **F18/M3:** la barra vive en `NavBar`, que se renderiza en toda ruta, y leer solo la caché la deja invisible en el deep link desde WhatsApp — que es el canal que C4/C6 declaran principal. (3) **F4:** la circularidad sidecar↔`fecha_efectiva`. Se resuelve con `GET /api/v1/disciplinas/con-partidos?fecha=&ventana_fallback_dias=`: endpoint propio y barato, que aplica la misma ventana de fallback **sin filtro de disciplina**, así que nunca está vacío mientras el feed tenga contenido. `disciplinas_con_partidos` sale del envelope del feed: una sola fuente, sin circularidad posible. **La barra se queda en el header global junto a la marca, como se pidió** — lo que cambia es de dónde se alimenta, no dónde vive.
- **E-L5 — El corte por bloque nunca devuelve cero partidos.** T3.3 manda cortar en borde de torneo; si el primer bloque tiene más partidos que `limit` (una liga de fin de semana con 30 partidos y `limit=20`), la regla devuelve `partidos: []` con `truncado: true` y `total_disponible: 250`: un feed vacío con un pie que dice "mostrando los primeros 0 de 250", y el botón de D4 topado en 200. Regla explícita: **siempre se devuelve al menos el primer bloque completo, aunque exceda `limit`** — `limit` es un mínimo redondeado hacia arriba al borde de bloque, no un máximo. El `N` del copy de D4 es lo realmente devuelto, no el `limit` pedido. Y hay que presupuestarlo: esto no es un `LIMIT` de SQL, es `dense_rank() OVER (ORDER BY torneo_grupo.Nombre, torneo.ID)` + `COUNT(*) OVER ()` con el recorte sobre el rank — medio día de trabajo que T3.3 presentaba como un bullet.
- **E-L6 — F10 son dos tests, no uno.** Verificado: `conftest.py` arma la base con `SQL_FILES = 01..06` y `test_scripts_sql.py` construye la suya igual y corre `SCRIPTS_VIGENTES` encima. El test de delta de columnas **sí** atrapa olvidar `01_schema.sql`, pero **no** atrapa olvidar agregar `31_` a `SCRIPTS_VIGENTES`: el archivo no se abre nunca, el delta da 0 y todo queda verde — y ese es el modo de falla más silencioso de los tres. Hacen falta dos: (1) el de delta, con el mensaje que nombre el archivo; (2) uno de cobertura de directorio — `set(glob("database/*.sql"))` menos `SQL_FILES` menos una lista explícita `SCRIPTS_HISTORICOS` debe ser igual a `SCRIPTS_VIGENTES`, fallando con "agregá `31_...sql` a SCRIPTS_VIGENTES o a SCRIPTS_HISTORICOS". El docstring de ese archivo ya explica en prosa por qué 07/08/09/12/13 quedan afuera; solo falta convertir esa prosa en una lista que el test lea.
- **E-S1 — Decir en voz alta cuál es la frontera.** `Publicado` gatea anónimo contra autenticado, **no** dueño contra el resto: un `Arbitro` cualquiera o un `TorneoAdmin` de otro torneo ve el borrador completo de un torneo ajeno. El blast radius es chico porque no hay self-registration (`routes/auth.py` solo expone `POST /login` y `GET /me`; las cuentas las crea AdminGeneral), y el repo ya tiene `require_torneo_access` si algún día hace falta endurecerlo. No se endurece en esta entrega, pero **queda escrito en el plan**: si no, el próximo que agregue datos sensibles al torneo va a asumir lo contrario.
- **E-S2 — `Logo_URL` se neutraliza también en lectura.** C10d validaba solo en escritura y razonaba el riesgo como XSS; un `<img src="javascript:...">` no ejecuta en ningún navegador moderno, así que el vector real es otro: una URL de tercero en una página pública filtra la IP y el `Referer` de cada visitante anónimo al host que el admin pegó, y un `http://` rompe la página por mixed-content. Validar solo en `EquipoUpdate`/`TorneoGrupoUpdate` además deja pasar todo lo que entre por SQL directo o por el seed de F1. Se agrega: filtro en la vista/serializer (`CASE WHEN Logo_URL LIKE 'https://%' THEN Logo_URL ELSE NULL END`), de modo que el fallback a iniciales cubra el dato sucio preexistente, y `referrerpolicy="no-referrer"` en los `<img>` de logos.
- **E-S3 — El endpoint público no se deja sin techo.** `/partidos/feed` es público, sin auth, sin rate limit (el repo solo lo tiene para login, `22_migracion_rate_limiting_login.sql`), corre un `GROUP BY` sobre el histórico de eventos por request, y C6/F13 le agregan una línea de log por hit sin retención definida — un bucle de requests satura CPU y llena el disco. Tres mitigaciones baratas: (a) caché en proceso por `(fecha, disciplina_id, limit)` con TTL 60s — el feed no tiene auto-refresh (C14), así que esa frescura es gratis y hace irrelevante el costo por request; (b) `ventana_fallback_dias` se acota a `le=7`, no a `le=30` como proponía F5 (30 multiplica por 4 el peor caso sin que ningún consumidor lo pida); (c) el log se emite solo cuando `fecha_efectiva != fecha_pedida`, y el resto se cuenta en memoria.
- **E-M1 — Un solo reloj.** C15 dice "la fecha es la del servidor", pero hay dos: el proceso Python (`date.today()`, con el `TZ` del contenedor de la app) y Postgres (`CURRENT_DATE`, con el `TimeZone` de la sesión). Pueden diferir en un día durante 3-5 horas cada noche. El default de `fecha` se resuelve **en Postgres, en la misma query**, y se documenta.
- **E-M2 — Un torneo nuevo no nace publicado.** `DEFAULT TRUE` es correcto para el backfill (no cambia el comportamiento existente), pero el mismo default aplica a los torneos nuevos: un torneo se publicaría en el instante en que el admin lo crea, con cero equipos y cero partidos — exactamente la primera impresión que D8c quiere evitar. La migración hace `ADD COLUMN DEFAULT TRUE` → `UPDATE` (backfill) → `ALTER COLUMN SET DEFAULT FALSE`. Las filas viejas siguen públicas; las nuevas se publican a propósito.
- **E-M4 — Commitear `schema.d.ts` antes de tocar `verificar.ps1`.** `git status` ya muestra `frontend/src/api/schema.d.ts` modificado, así que el `git diff --exit-code` que F16 agrega daría rojo en su primera corrida por un cambio anterior a este plan. Se commitea primero.
- **E-M5 — El movimiento de archivos va en su propio commit.** T2.1 mueve `FiltroDisciplinasBar.tsx` + `iconosDisciplina.ts` y toca `TorneosAdmin.tsx`, `EquiposAdmin.tsx` y demás consumidores. Mezclado con la feature, un revert de R3 arrastra el refactor. Commit separado, primero, sin ningún cambio de comportamiento ("make the change easy, then make the easy change").
- **E-M6 — El desempate del orden es contrato, no detalle.** `TORNEO_GRUPO.Nombre` es `VARCHAR(100) NOT NULL` sin `UNIQUE`, así que dos grupos homónimos se intercalan alfabéticamente y `torneo.ID` los desempata. El orden sigue siendo determinista y los bloques contiguos por `torneo_id` (el agrupamiento de T4.4 no se rompe), pero el desempate por `torneo.ID` queda anotado como parte del contrato del endpoint, con su test.
- **E-T — Los 11 tests que faltaban.** Además de lo que ya pedían T3.6 y T4.7: (1) corte en borde con un bloque mayor que `limit` (E-L5); (2) `ventana_fallback_dias=0` devuelve vacío y `=7` devuelve `fecha_efectiva` distinta — F5 introdujo el parámetro y nadie lo testeaba; (3) el endpoint de disciplinas sigue trayendo contenido cuando el día pedido está vacío y el fallback se activó (E-L4); (4) torneo `Finalizado` con partido hoy → aparece (E-L1); (5) fila con `Estado IS NULL` en EQUIPOS/TORNEO/DISCIPLINA → aparece (E-L3); (6) `31_` está en `SCRIPTS_VIGENTES` (E-L6 test 2); (7) `logo_url` con `http://`, `javascript:` y `data:` → rechazado en escritura con el `codigo` de F9 y neutralizado en lectura (E-S2); (8) NavBar por los 4 roles (anónimo, Arbitro, TorneoAdmin, AdminGeneral), incluido el link "Portal público" de D6; (9) `/dashboard` tipeado por un anónimo — verificado que hoy es alcanzable (`App.tsx:48` no tiene `RequireRole`), así que la decisión de F20 necesita su test; (10) frontera exacta del fallback: partido a `hoy-7d` incluido, a `hoy-8d` excluido; (11) orden determinista con dos grupos homónimos (E-M6). **Regla de regresión (sin preguntar):** el cambio de `/` (C16) y el gate de auth sobre `GET /torneos/{id}` (C2) modifican comportamiento existente hoy sin cobertura — sus tests de regresión entran como requisito crítico.
- **E-G1 — Orden de deportes: gana el del usuario (Final Gate, D2).** Supersede la decisión abierta D-A. El ranking pasa a **Fútbol=1, Tenis=2, Baloncesto=3**, y el resto de las 28 disciplinas se corre una posición. Se aplica como `UPDATE` idempotente dentro de `31_migracion_portal_publico.sql`, con el mismo patrón de match por `Nombre` que ya usa `15_migracion_popularidad_disciplinas.sql`. No hay código que tocar: `DisciplinaRepository.list` ya ordena por `orden_popularidad NULLS LAST`. Se descartó dejar el ranking previo y también ordenar dinámicamente por cantidad de partidos.
- **E-G2 — Control de Mesa: gate de rol, no eliminación (Final Gate, D3).** Confirma C7 contra la lectura literal del requerimiento original. El `NavLink` se condiciona a TorneoAdmin, AdminGeneral y Arbitro — hoy no tiene ningún gate, así que hasta un anónimo lo ve, que es exactamente lo que se pedía cerrar. Se descartó eliminarlo del todo (dejaba huérfana la lista `/control-de-mesa`: el botón de `PartidosDelTorneo.tsx:184` va a `/partidos/:id`, no a mesa) y moverlo a una pestaña de `TorneoAdminLayout` (alcanzado a UN torneo, mientras que la lista no lo está). Se mantiene el botón "Gestionar en Mesa" por fila.
- **E-G3 — El feed abre en la próxima jornada con partidos (Final Gate, D4).** **Supersede C1 y reformula D3**, y va contra la recomendación de esta revisión: el usuario eligió la opción B sobre la conservadora. `GET /partidos/feed` sin `fecha` resuelve directo a la fecha más cercana con partidos publicados para esa disciplina (atrás primero, después adelante, acotado a ±7 días; fuera de la ventana, vacío real). Ya no existe el estado "hoy vacío + cartel de disculpa" como camino principal. **Dos consecuencias obligatorias:** (a) la cabecera del feed **siempre** rotula la fecha real que muestra, nunca "Hoy" a secas — sin eso, un martes mostraría el domingo pasado como si fuera actual, y la distinción En curso / Finalizado de D2 pierde sentido; (b) el selector de D3 deja de ser tres pills fijas hoy/ayer/mañana (mentirían: "Hoy" activo sobre el domingo pasado) y pasa a ser una tira de fechas reales donde la seleccionada **es** `fecha_efectiva`. El fallback sigue aplicando solo a la resolución inicial: navegar explícitamente a una fecha no cae a otra. Razón del usuario, aceptada: los torneos amateur juegan fin de semana, y una portada que dice "no hay partidos" de lunes a jueves era el escenario de 6 meses que la revisión CEO marcó como el mayor riesgo del plan.
<!-- /autoplan-accepted:eng -->
## Review record

_Registro de las revisiones de /autoplan. Las obligaciones aceptadas por fase
se anotan acá y se aplican arriba, en Implementation plan._

<!-- autoplan-baseline-edits:ceo {"sourceSha256":"eaabe262723fdc2439d9bc94f4fbc0abd1318b726f4e74264cdd16dd6c4e7753","replacements":[{"oldText":"- SSR / SEO / meta tags Open Graph para las vistas públicas.\n","newText":"- SSR y preview de Open Graph POR torneo/partido (exige prerender). Los meta\n  tags OG **estáticos** SÍ entran (C4).\n"},{"oldText":"## Fase 1 — Limpieza del acceso a Control de Mesa\n","newText":"## Fase 1 (R1) — Limpieza del acceso a Control de Mesa\n"},{"oldText":"- **T1.1** Quitar el `<NavLink to=\"/control-de-mesa\">` de\n  `frontend/src/components/NavBar.tsx`. Las rutas `/control-de-mesa` y\n  `/control-de-mesa/partido/:partidoId` quedan intactas con su `RequireRole`.\n- **T1.2** Reemplazar la puerta de entrada perdida: agregar la pestaña\n  \"Control de Mesa\" dentro de `TorneoAdminLayout.tsx` (visible para\n  TorneoAdmin/AdminGeneral), que es su ruta operativa natural.\n","newText":"- **T1.1 (C7)** Condicionar por rol el `<NavLink to=\"/control-de-mesa\">` de\n  `frontend/src/components/NavBar.tsx`: visible solo para TorneoAdmin,\n  AdminGeneral y Arbitro. El público deja de verlo; el operador conserva su\n  acceso. Las rutas quedan intactas con su `RequireRole`.\n- **T1.2 (C7)** Condicionar por rol también el `NavLink` de \"Dashboard\", que\n  hoy se le muestra a un visitante anónimo, y cambiar el catch-all\n  `<Route path=\"*\">` de `App.tsx` para que un anónimo caiga en la home\n  pública y no en el dashboard interno.\n"},{"oldText":"## Fase 2 — Barra pública de disciplinas en el header\n","newText":"## Fase 2 (R3) — Barra pública de disciplinas en el header\n"},{"oldText":"- **T2.2** Nuevo `components/BarraDisciplinasPublica.tsx`: una sola fila de\n  pills (sin la fila de modalidades ni la de estados — el visitante no\n  filtra por modalidad), alimentada por `useCatalogo()` con\n  `estado=Activo`, ordenada por `orden_popularidad` (ya viene ordenada del\n  backend).\n","newText":"- **T2.2 (C8)** Nuevo `components/BarraDisciplinasPublica.tsx`: una sola fila\n  de pills (sin modalidades ni estados — el visitante no filtra por\n  modalidad). **No** se alimenta de `useCatalogo()` (eso traería las 28 del\n  catálogo): usa el sidecar `disciplinas_con_partidos` que devuelve\n  `GET /partidos/feed`, calculado ANTES de aplicar `disciplina_id`. Con ≤1\n  disciplina con contenido la barra no se renderiza.\n"},{"oldText":"## Fase 3 — Datos para el feed (backend + base)\n","newText":"## Fase 3 (R1 la migración, R2 la vista y el endpoint) — Datos para el feed\n"},{"oldText":"  - `EQUIPOS.Logo_URL VARCHAR(500) NULL`\n  - `TORNEO_GRUPO.Pais VARCHAR(60) NULL`\n  - `TORNEO_GRUPO.Logo_URL VARCHAR(500) NULL`\n","newText":"  - `EQUIPOS.Logo_URL VARCHAR(500) NULL`\n  - `TORNEO_GRUPO.Pais VARCHAR(60) NULL`\n  - `TORNEO_GRUPO.Logo_URL VARCHAR(500) NULL`\n  - `TORNEO.Publicado BOOLEAN NOT NULL DEFAULT TRUE` + backfill TRUE (C2)\n\n  **No** agregar índice sobre `PARTIDOS.Fecha_Partido`: `idx_partidos_fecha`\n  ya existe (`03_indexes.sql:82`) y duplicarlo rompe la idempotencia.\n"},{"oldText":"- **T3.2** Nueva vista `vw_feed_partidos` en `04_views.sql`: partidos con\n  `torneo`, `torneo_grupo`, `pais`, `logo_torneo`, `disciplina_id`,\n  `disciplina`, nombres y logos de ambos equipos, `fecha_partido`,\n  `estado`, y marcador (goles local/visitante, derivado igual que\n  `vw_resultados_partidos`). **Sin** el filtro `>= CURRENT_TIMESTAMP` ni el\n  `Estado='Programado'` que rompen el caso \"hoy\".\n","newText":"- **T3.2 (C5)** Nueva vista `vw_feed_partidos` en `04_views.sql` construida\n  **SOBRE `vw_resultados_partidos`** (prohibido reimplementar el conteo de\n  goles: esa vista ya resuelve autogol vía `vw_goles_acreditados` y walkover,\n  y no filtra por estado). Le suma los JOIN a TORNEO, TORNEO_GRUPO y\n  DISCIPLINA para `torneo`, `torneo_grupo`, `pais`, `logo_torneo`,\n  `disciplina_id`, `disciplina` y los logos de ambos equipos.\n  **`WHERE` explícito, escrito entero** (`vw_resultados_partidos` NO filtra\n  estados, a diferencia de `vw_proximos_partidos`): `TORNEO.Publicado = TRUE`\n  Y `TORNEO.Estado = 'Activo'` Y `TORNEO_GRUPO.Estado <> 'Archivado'`\n  Y `PARTIDOS.Estado <> 'Cancelado'` Y ambos `EQUIPOS.Estado = 'Activo'`.\n  Sin el `>= CURRENT_TIMESTAMP` ni el `Estado='Programado'` de\n  `vw_proximos_partidos`, que rompen el caso \"hoy\". Los shells de bracket ya\n  quedan fuera por el `JOIN EQUIPOS` interno heredado.\n"},{"oldText":"- **T3.3** `GET /api/v1/estadisticas/feed-partidos` — público, params\n  `disciplina_id` (opcional), `fecha` (`date`, default hoy), `limit`.\n  Schema `FeedPartidoOut` en `schemas/estadisticas.py`.\n","newText":"- **T3.3 (C12/C1/C8/C15)** `GET /api/v1/partidos/feed` — en el router de\n  partidos (no en `/estadisticas/`; una lista de partidos no es una\n  estadística), registrado ANTES de `/{partido_id}` para que FastAPI no lea\n  \"feed\" como un id. Público. Params: `disciplina_id` (opcional), `fecha`\n  (`date`, default `CURRENT_DATE` del servidor), `limit` (`le=200`).\n  **Envelope, no lista plana** — `FeedResponseOut` en `schemas/partido.py`:\n  `fecha_pedida`, `fecha_efectiva`, `disciplinas_con_partidos` (lista de\n  `{id, nombre}`), `partidos` (lista de `FeedPartidoOut`) y `truncado` (bool).\n  `FeedPartidoOut`: `partido_id`, `torneo_id`, `torneo`, `torneo_grupo`,\n  `pais`, `logo_torneo`, `disciplina_id`, `disciplina`, `equipo_local_id`,\n  `equipo_local`, `logo_local`, `equipo_visitante_id`, `equipo_visitante`,\n  `logo_visitante`, `fecha_partido`, `estado`, `goles_local`,\n  `goles_visitante`.\n  `ORDER BY torneo_grupo.Nombre, torneo.ID, fecha_partido, partido_id` —\n  determinista, y deja contiguos los partidos de un mismo torneo para que el\n  cliente no tenga que reordenar. **Truncado:** si `limit` corta, corta en el\n  borde de un torneo, nunca a mitad de un bloque, y marca `truncado: true`.\n"},{"oldText":"- **T3.4** Exponer `logo_url` en `EquipoOut` y `pais`/`logo_url` en\n  `TorneoGrupoOut`; permitirlos en los `*Update` correspondientes para que\n  el back-office los pueda cargar.\n","newText":"- **T3.4 (C3)** Exponer y hacer escribibles las columnas nuevas. Ojo con el\n  esfuerzo real, verificado en código: `TorneoGrupoUpdate`\n  (`schemas/torneo_grupo.py:19`) hoy solo acepta `nombre` y `estado`, y\n  `TorneosAdmin.tsx` **no tiene formulario de edición de torneo** (su `Modo`\n  es `lista | crear-grupo | nueva-edicion`; el único PATCH, línea 269, es el\n  archivado del grupo). O sea:\n  - `EquipoOut`/`EquipoUpdate` + campo \"URL del escudo\" en `EquiposAdmin.tsx`\n    → barato, usa el builder genérico `camposEquipo`.\n  - `TorneoGrupoOut`/`TorneoGrupoUpdate` + `pais` y `logo_url` + servicio +\n    formulario de edición de grupo → **no existe, hay que crearlo**.\n  - `TorneoUpdate.publicado` + mutación + affordance de publicar/despublicar\n    → **no existe, hay que crearlo**.\n- **T3.4b (C2)** Auth opcional en las rutas que `Publicado` tiene que\n  proteger: agregar `usuario: Usuario | None = Depends(get_current_user_optional)`\n  a `GET /torneos/{torneo_id}` (`routes/torneos.py:53`) y a los tres\n  `GET /estadisticas/torneos/{torneo_id}/*`, devolviendo 404 **solo** si el\n  caller es anónimo y el torneo no está publicado. Sin el matiz se rompe\n  `MesaPanel.tsx:91`, que llama al mismo endpoint. Decidir también, y\n  escribirlo, qué pasa con `GET /torneos` (lista),\n  `GET /partidos?torneo_id=`, `GET /torneos/{id}/bracket` y\n  `/estadisticas/proximos-partidos`, que hoy enumeran torneos sin filtrar: o\n  filtran `Publicado` para anónimos, o se documenta por qué quedan abiertos.\n  Y decidir el caso de `PartidoEnVivo.tsx:61`, que consume\n  `/estadisticas/torneos/{id}/resultados`: si esa ruta 404ea para anónimos, la\n  página pública de partido de un torneo despublicado queda a medio\n  renderizar — o se gatea entera, o la query tolera el 404.\n"},{"oldText":"- **T3.6** Tests backend: feed vacío, feed con 2 torneos de la misma\n  disciplina, partido en curso incluido, partido finalizado hoy incluido,\n  partido de mañana excluido, torneo archivado excluido.\n","newText":"- **T3.6** Tests backend, con el reloj congelado (C10f): feed vacío; 2 torneos\n  de la misma disciplina; partido en curso incluido; partido finalizado hoy\n  incluido; partido de mañana excluido; torneo archivado excluido; grupo\n  archivado excluido; partido Cancelado excluido; equipo Inactivo excluido;\n  torneo despublicado excluido; el mismo id devuelve 200 para TorneoAdmin y\n  404 anónimo en las 4 rutas de T3.4b; `MesaPanel` sigue cargando un torneo\n  despublicado; `PartidoEnVivo` anónimo sobre un torneo despublicado se\n  comporta como se decidió en T3.4b; migración `31_` idempotente corrida dos\n  veces.\n"},{"oldText":"## Fase 4 — Feed de Partidos del Día (frontend)\n","newText":"## Fase 4 (R3) — Feed de Partidos del Día (frontend)\n"},{"oldText":"- **T4.1** Nueva página `pages/publico/FeedPartidos.tsx` montada en `/`\n  (hoy `/` redirige a `/dashboard`).\n","newText":"- **T4.1 (C16)** Nueva página `pages/publico/FeedPartidos.tsx`. `/` decide por\n  sesión: anónimo ve el feed, logeado sigue redirigiendo a `/dashboard`. Es el\n  único cambio que toca a todo usuario existente → va con su test y con un\n  comentario en `App.tsx` explicando por qué la ruta decide por sesión.\n"},{"oldText":"- **T4.5** Selector de fecha (hoy / ayer / mañana) sobre el mismo endpoint.\n- **T4.6** Estados vacío / cargando / error: \"No hay partidos de Fútbol\n  hoy\", no una lista en blanco.\n","newText":"- **T4.5** Selector de fecha (hoy / ayer / mañana) sobre el mismo endpoint. La\n  cabecera rotula la fecha explícitamente (C15), nunca solo \"Hoy\": el\n  `TIMESTAMP` no lleva zona y un cliente en otro huso tiene que ver qué día\n  está mirando.\n- **T4.6 (C1)** Estados vacío / cargando / error. Cuando el día pedido está\n  vacío, el backend cae a la fecha más cercana con partidos **acotada a ±7\n  días**; fuera de esa ventana devuelve vacío de verdad, en vez de desenterrar\n  una jornada de hace meses bajo un rótulo que parece actual. El texto dice\n  \"No hay partidos de Fútbol el 15/09. Mostrando la jornada del 13/09\".\n"},{"oldText":"## Fase 5 — Deep linking y vista pública de torneo\n","newText":"## Fase 5 (R1) — Deep linking y vista pública de torneo\n"},{"oldText":"- **T5.2** Nueva ruta pública `/torneos/:torneoId` ->\n  `pages/publico/DetalleTorneoPublico.tsx`: tabla de posiciones,\n  goleadores y resultados, con los endpoints públicos de\n  `/estadisticas/*` que ya existen.\n","newText":"- **T5.2** Nueva ruta pública `/torneos/:torneoId` ->\n  `pages/publico/DetalleTorneoPublico.tsx`: tabla de posiciones,\n  goleadores y resultados, con los endpoints públicos de\n  `/estadisticas/*` que ya existen.\n- **T5.2b (C4)** Botón \"Compartir\" en la vista pública de torneo y en el\n  detalle de partido (copia el deep link con confirmación visible) + meta tags\n  Open Graph **estáticos** en `frontend/index.html`. El preview de WhatsApp\n  dirá \"Score-App\" para todo link: el preview por torneo exige prerender y\n  queda diferido (C14).\n- **T5.2c (C6)** Acción \"Ver página pública\" en la tarjeta de torneo de\n  `TorneosAdmin.tsx`. Sin esto la vista pública de R1 **no tiene ninguna\n  puerta de entrada** (el botón Compartir vive dentro de ella), y el umbral de\n  4 semanas de C6 mediría cero por razones estructurales y mataría R3 con una\n  señal falsa.\n- **T5.2d (C6)** Instrumentación: el backend hoy **no tiene logging**\n  (`grep -rn \"import logging\" backend/app` → cero hits; el patrón es\n  `print()` en `main.py`). Hay que configurar un logger con handler y\n  formateador que preserve `extra` (o escribir una línea JSON a stdout) y\n  decidir dónde se retiene, antes de prometer \"hits por semana\".\n"},{"oldText":"- **T5.4** Cambiar el redirect de `/` — la home pasa a ser el feed\n  público; `/dashboard` sigue existiendo para usuarios logeados.\n","newText":"- **T5.4** (absorbido por T4.1/C16: `/` decide por sesión, no se reemplaza el\n  arranque de los usuarios logeados.)\n"},{"oldText":"- **D-B: Qué disciplinas mostrar.** Las 28 del catálogo son un muro. La\n  barra del back-office solo muestra las que **tienen torneos**. Aplicar el\n  mismo criterio en público requiere derivarlo de `/torneos`.\n- **D-C: Escudos y países sin datos.** Las columnas nacen vacías; el feed\n  se ve con iniciales y sin país hasta que alguien los cargue.\n- **D-D: Home pública vs `/dashboard`.** Mover `/` al feed cambia el\n  arranque de todos los usuarios logeados.\n- **D-E: Alcance del endpoint de feed.** Vista SQL nueva vs. cruce en el\n  cliente sobre endpoints que ya existen.\n","newText":"- **D-B: RESUELTA (C8).** Solo las disciplinas con partidos publicados en la\n  fecha efectiva, vía el sidecar del endpoint. Consecuencia aceptada: en un\n  deployment de una sola liga la barra no se renderiza.\n- **D-C: RESUELTA (C3).** Las columnas nacen vacías, pero con formulario para\n  cargarlas. El fallback a iniciales es el estado por defecto, no el permanente.\n- **D-D: RESUELTA (C16).** `/` decide por sesión; el logeado sigue en\n  `/dashboard`.\n- **D-E: RESUELTA (C5).** Vista SQL nueva, pero colgada de\n  `vw_resultados_partidos`, no en paralelo.\n"}]} -->

---

# FASE 1 — CEO REVIEW (estrategia y alcance)

Modo: **SELECTIVE EXPANSION** (override de /autoplan; el default por contexto
también sería SELECTIVE EXPANSION — es una iteración sobre un sistema que ya
existe, no greenfield).
Voces: Claude subagent **[subagent-only]** — Codex CLI no está instalado
(`command -v codex` → not found), así que no hay lectura de un modelo externo.

## Auditoría previa del sistema

- 30 commits recientes: el trabajo de los últimos meses fue back-office (Control
  de Mesa, motor de formatos, RBAC, auditoría). Nada público.
- `git stash list` vacío. Nada en vuelo.
- **Cero `TODO`/`FIXME`/`HACK` reales en `backend/app`, `frontend/src` y
  `database`.** Los ~15 hits de `grep TODO` son la palabra española "TODO/TODOS"
  dentro de comentarios, más `TODOS.md`. El repo no lleva deuda anotada en
  código.
- Archivos más tocados en 30 días: `frontend/src/index.css` (16),
  `database/01_schema.sql` (13), `frontend/src/App.tsx` (12),
  `TorneosAdmin.tsx` (11). Los cuatro están en el blast radius de este plan.
- `TODOS.md`: el backlog fue triado el 2026-09-01. No hay ítem aparcado que
  este plan desbloquee o pise.
- Design doc encontrado y leído: `docs/designs/frontend-inicial-dashboard-mesa-en-vivo.md`
  (2026-08-25, APPROVED). Es la fuente de verdad del problema original.
- Retrospectiva: `TorneosAdmin.tsx` y `01_schema.sql` fueron reescritos varias
  veces por revisiones previas. Este plan los vuelve a tocar → se revisan con
  más agresividad.
- Calibración de gusto — patrones bien hechos a imitar: `vw_goles_acreditados`
  (base común de la que cuelgan las demás vistas, sin duplicar la regla del
  autogol), `iconosDisciplina.ts` (módulo propio para que cambiar iconos sea
  reemplazar un archivo), y la decisión Eng #10 registrada en `04_views.sql`
  ("se reescopa la vista existente en vez de crear una nueva en paralelo").
  Antipatrón a no repetir: componentes de pantalla que arman su propio cruce de
  catálogo — ya costó el hook `useCatalogo` para deduplicar seis copias.

## 0A. Premise Challenge

| # | Premisa que el plan asume | Veredicto |
|---|---|---|
| P1 | Existe (o se puede crear) tráfico anónimo a `/` | **NO SOSTENIDA.** SEO, OG tags, share y búsqueda están todos fuera de alcance. Sin canal, un portal público solo lo ven quienes ya son usuarios. |
| P2 | Hay suficientes partidos por día para llenar un feed diario | **NO VERIFICADA.** Torneos amateur juegan fin de semana. Nadie contó partidos/día en la base real. |
| P3 | El visitante quiere navegar por deporte | **DUDOSA.** El design doc dice que el wedge es *una liga de fútbol*, no multideporte. Navegar por deporte es la UI de un agregador con 40 ligas. |
| P4 | Escudos y países se van a poblar | **NO SOSTENIDA con el plan como está.** T3.1/T3.4 agregan columnas y las exponen, pero ningún task agrega el input al formulario. La única forma de cargar un logo sería un UPDATE a mano. |
| P5 | Exponer todos los torneos públicamente es aceptable | **PARCIALMENTE VÁLIDA, con matiz.** La voz CEO afirmó que hoy los torneos están protegidos por `RequireRole` — **es falso**: `GET /torneos`, `GET /partidos` y `GET /estadisticas/*` ya son públicos sin auth (verificado en `routes/torneos.py`, `routes/partidos.py:56`, `routes/estadisticas.py:16`). El dato ya está expuesto por API. Lo que cambia es la *descubribilidad* en la UI, que sigue siendo un cambio real de producto. |
| P6 | El backend soporta el feed | **VÁLIDA y bien documentada.** Los 7 huecos del plan están verificados contra archivo y línea, no asumidos. |

**Aceptadas (P6, y P5 con el matiz corregido).** P1-P4 se convierten en
obligaciones o viajan al Final Gate.

## 0B. Existing Code Leverage

| Sub-problema | Código que ya lo resuelve | ¿El plan lo reusa? |
|---|---|---|
| Barra de pills con icono, accesible | `FiltroDisciplinasBar.tsx` (`role=tablist`, `aria-pressed`, flechas ←→) | Sí (T2.1 la mueve a `components/`) |
| Icono por disciplina + fallback | `iconosDisciplina.ts` | Sí |
| Orden por popularidad | `DISCIPLINA.Orden_Popularidad` + `DisciplinaRepository.list` | Sí — **ya está implementado, no hay nada que construir** |
| Marcador de un partido (con walkover y autogol) | `vw_resultados_partidos` sobre `vw_goles_acreditados` — sin filtro de estado, sirve para cualquier partido | **NO en el plan original.** T3.2 decía "derivado igual que `vw_resultados_partidos`" = copiar la lógica. Corregido abajo. |
| Nombres de equipo + torneo en una fila | `vw_resultados_partidos`, `vw_proximos_partidos` | Parcial |
| Detalle de partido público | Ruta `/partidos/:id` → `PartidoEnVivo.tsx`, sin `RequireRole` | Sí — **ya existe y funciona anónimo** |
| Tabla de posiciones / goleadores / resultados públicos | `GET /estadisticas/*`, sin auth | Sí (T5.2) |
| Avatar con fallback a iniciales | `avatarUtils.ts`, `AvatarJugador.tsx` | Sí (T4.3) |
| Catálogo Disciplina/Modalidad en un hook | `useCatalogo.ts` | Sí |

Nada se reconstruye desde cero. El único riesgo de duplicación era la
derivación del marcador, y queda cerrado por la obligación C5.

## 0C. Dream State Mapping

```
  CURRENT STATE                THIS PLAN                    12-MONTH IDEAL
  ─────────────                ─────────                    ──────────────
  Back-office completo    ──▶  + home pública con feed  ──▶  El organizador
  (mesa, formatos, RBAC,       del día por deporte           publica y la liga
  auditoría, estadísticas)     + torneo público             entera (jugadores,
                               + deep links                  familias, rivales)
  API ya pública pero          + escudos/país/publicado      la sigue sin cuenta,
  sin ninguna UI que la        + share + OG                  en vivo, desde un
  consuma sin login                                          link de WhatsApp
  ────────────────────────────────────────────────────────────────────────────
  El visitante no tiene   ──▶  Ve el día, entra al      ──▶  Recibe el link,
  puerta de entrada            torneo o al partido            comparte, vuelve
```

## 0C-bis. Implementation Alternatives

```
APPROACH A: Portal completo de una (el plan como fue escrito)
  Summary: Fases 1→5 en orden. Migración + vista + endpoint + feed + torneo
           público, todo antes del primer release.
  Effort:  L        (human: ~2 semanas / CC: ~3-4 h)
  Risk:    Med
  Pros:    Entrega exactamente los 4 requerimientos pedidos, de una.
           Una sola migración, un solo ciclo de verificar.ps1.
  Cons:    La pieza más cara (migración + vista + endpoint) se paga antes de
           saber si alguien mira la página. La pieza con audiencia real
           (tabla de posiciones pública) queda última.
  Reuses:  FiltroDisciplinasBar, iconosDisciplina, /estadisticas/*, PartidoEnVivo.

APPROACH B: Mínimo viable — solo lo que ya existe, expuesto
  Summary: Hacer `/dashboard` legible sin sesión y agregar `/torneos/:id`
           público. Cero cambios de esquema, cero endpoints nuevos.
  Effort:  S        (human: ~1 día / CC: ~20 min)
  Risk:    Low
  Pros:    Casi todo el valor (posiciones, goleadores, próximos partidos ya
           se renderizan hoy) por una fracción del trabajo. Test de demanda
           gratis.
  Cons:    No entrega el feed agrupado ni la barra de deportes — o sea, no
           entrega los requerimientos 2 y 3. No es lo que se pidió.
  Reuses:  Dashboard.tsx entero, /estadisticas/*.

APPROACH C: Arquitectura ideal, resecuenciada (RECOMENDADA)
  Summary: El alcance completo de A, pero en el orden que aprende antes:
           primero el torneo público + deep links + share (sin migración),
           después el feed y la barra. La vista del feed se construye SOBRE
           vw_resultados_partidos en vez de duplicar su lógica.
  Effort:  L        (human: ~2 semanas / CC: ~3-4 h)
  Risk:    Low-Med
  Pros:    Mismo alcance entregado, pero el primer release no depende de una
           migración. Cierra la duplicación de la derivación del marcador.
           Cada fase es desplegable sola.
  Cons:    Dos despliegues en vez de uno. Exige decidir `Publicado` y el
           default de fecha antes de construir el feed.
  Reuses:  Todo lo de A, más vw_resultados_partidos y vw_goles_acreditados.
```

**RECOMMENDATION: Approach C** — entrega el alcance completo que se pidió
(a diferencia de B) pero paga la migración después de que haya evidencia,
y respeta la preferencia de ingeniería "DRY: flag repetition aggressively"
al colgar el feed de la vista que ya calcula el marcador.
Completeness: A=8/10, B=4/10, C=10/10.

## 0F. Mode Selection

**SELECTIVE EXPANSION**, confirmado. El plan toca un sistema vivo; el baseline
es el alcance pedido por el usuario, y las expansiones (share, OG, métricas,
`Publicado`) se ofrecen una por una. Auto-decidido por /autoplan.

## 0D. Análisis de modo (SELECTIVE EXPANSION)

**Complexity check:** el plan toca ~18 archivos y agrega 3 columnas, 1 vista,
1 endpoint y 5 componentes. Por encima del umbral de 8 archivos → se revisó si
el mismo objetivo se logra con menos piezas. Sí en dos lugares: (a) la vista del
feed puede colgar de `vw_resultados_partidos` en vez de reimplementar el
marcador, y (b) `T1.2` (pestaña dentro de `TorneoAdminLayout`) se reemplaza por
un gate de rol en el `NavLink` que ya existe — menos piezas, mismo resultado.

**Mínimo que logra el objetivo:** T5.2 + T5.3 + T1.1 + T1.3. Todo lo demás es
incremento sobre eso.

**Scan de expansión (candidatos, decididos abajo):**
1. Botón Compartir + meta tags OG estáticos → **ACEPTADO** (blast radius, <1d CC).
2. Flag `TORNEO.Publicado` → **ACEPTADO** (control de exposición, en blast radius).
3. Contador de tráfico en endpoints públicos + métrica de éxito declarada → **ACEPTADO**.
4. Write path (inputs de URL de logo y país en los formularios admin) → **ACEPTADO** (sin esto las columnas nacen muertas).
5. Fallback a la jornada más cercana cuando el día pedido está vacío → **ACEPTADO**.
6. Auto-refresh en vivo del feed (polling/WebSocket) → **DIFERIDO a TODOS.md** (fuera de blast radius, infra nueva).
7. Búsqueda global de equipos/jugadores → **DESCARTADO** (no relacionado).
8. Uploader de imágenes → **DIFERIDO a TODOS.md** (el plan ya lo declaró fuera de alcance; las columnas aceptan URL).

## 0E. Temporal Interrogation

```
  HOUR 1 (fundaciones)    ¿La columna Publicado va en TORNEO o en TORNEO_GRUPO?
                          → TORNEO. Una edición puede publicarse y la siguiente
                            no; TORNEO_GRUPO es la competición, no la edición.
                          ¿Default TRUE o FALSE? → TRUE + backfill, para no
                            cambiar el comportamiento público que la API ya tiene.

  HOUR 2-3 (core)         ¿El feed agrupa en SQL o en el cliente?
                          → Filas planas ordenadas por (torneo, hora); agrupa el
                            cliente. Agrupar en SQL obliga a JSON anidado.
                          ¿Qué pasa con un partido sin equipos (shell de bracket,
                            equipos_id_local NULL)? → se excluye del feed: una
                            fila "Ganador Partido 3 vs TBD" no es un partido.

  HOUR 4-5 (integración)  ¿`/` público rompe a los logeados? → `/` decide por
                            sesión: anónimo ve el feed, logeado sigue yendo a
                            /dashboard. Sin esto se rompe la costumbre de todos.
                          ¿El NavBar con dos filas rompe el layout en 375px?
                            → la fila de pills scrollea horizontal; se prueba.

  HOUR 6+ (pulido/tests)  ¿Qué se testea del feed? Agrupación, orden por hora,
                            empty state, fallback de escudo, exclusión de
                            partidos sin equipos y de torneos no publicados.
                          ¿Timezone? Fecha_Partido es TIMESTAMP sin tz. "Hoy"
                            se calcula con la fecha del servidor; hay que
                            declararlo o el feed se corre de día para el cliente.
```

## Step 0.5 — Dual Voices

### CODEX SAYS (CEO — strategy challenge)

```
[codex-unavailable: binary not found]
Codex CLI no está instalado en esta máquina. No hay lectura de un modelo
externo para esta fase. Instalar con: npm install -g @openai/codex
```

### CLAUDE SUBAGENT (CEO — strategic independence)

9 hallazgos, veredicto "conditional go, re-secuenciado y recortado a la mitad".
Resumen fiel:

- **C1 CRITICAL** — El feed no tiene plan de densidad de contenido. `fecha=hoy`
  por default deja "No hay partidos" la mayoría de los días.
- **C2 CRITICAL** — Todo torneo de la base queda listado públicamente; no hay
  flag `publicado`.
- **C3 HIGH** — Las columnas de logo/país no tienen camino de escritura: nacen
  y quedan NULL.
- **C4 HIGH** — Un portal público sin share ni SEO no tiene canal de adquisición.
- **C5 HIGH** — Dos fuentes de verdad para "qué es un partido": el plan
  identifica que `GET /partidos` no filtra por fecha/disciplina y que
  `PartidoOut` no trae nombres, y después no arregla ninguno de los dos:
  construye un camino paralelo.
- **C6 HIGH** — 25 tasks, una migración y un cambio de ruteo que afecta a todo
  usuario logeado, sin una sola métrica de éxito.
- **C7 MEDIUM** — La nueva puerta de entrada a Control de Mesa está mal
  alcanzada: `TorneoAdminLayout` es scoped a UN torneo, la lista no lo es.
- **C8 MEDIUM** — La barra de 28 pills es UI para un catálogo que no existe en
  este deployment.
- **C9 MEDIUM** — El orden de fases paga lo caro antes de aprender.

### CEO DUAL VOICES — CONSENSUS TABLE

```
CEO DUAL VOICES — CONSENSUS TABLE:
═══════════════════════════════════════════════════════════════
  Dimension                             Claude   Codex   Consensus
  ────────────────────────────────────  ───────  ──────  ─────────
  1. Premises valid?                    NO (4)   N/A     N/A
  2. Right problem to solve?            PARTLY   N/A     N/A
  3. Scope calibration correct?         NO       N/A     N/A
  4. Alternatives sufficiently explored? NO      N/A     N/A
  5. Competitive/market risks covered?  NO       N/A     N/A
  6. 6-month trajectory sound?          AT RISK  N/A     N/A
═══════════════════════════════════════════════════════════════
Outside voice unavailable (Codex CLI not installed) → las seis celdas de
Consensus son N/A, nunca CONFIRMED. Los hallazgos nativos quedan separados.
SINGLE-VOICE CRITICALS (C1, C2): sin confirmación cruzada — señalados como
tales y llevados al Final Gate en vez de tratarse como consenso.
```

## Secciones 1-11

### Sección 1 — Architecture Review

```
  ARQUITECTURA PROPUESTA (nuevo en ►)

  ┌─────────────────────────── FRONTEND ───────────────────────────┐
  │                                                                 │
  │  NavBar ──► BarraDisciplinasPublica ◄─ useCatalogo             │
  │    │            (?deporte=N en la URL)                         │
  │    ▼                                                            │
  │  Routes                                                         │
  │    ├─ "/"        ► FeedPartidos      (anónimo)                 │
  │    │                  └─► BloqueTorneo ─► FilaPartido           │
  │    ├─ "/dashboard"   DashboardPage    (logeado, sin cambios)    │
  │    ├─ "/torneos/:id" ► DetalleTorneoPublico (anónimo)          │
  │    ├─ "/partidos/:id"  PartidoEnVivo  (YA existía, anónimo)     │
  │    └─ "/control-de-mesa"  RequireRole (sin cambios)             │
  └─────────────────────────────────────────────────────────────────┘
                                │ openapi-fetch
  ┌─────────────────────────── BACKEND ────────────────────────────┐
  │  GET /disciplinas          (existe, público, ya ordena)        │
  │  GET /estadisticas/*       (existe, público)                   │
  │  GET /partidos  ► +fecha  +disciplina_id                       │
  │  GET /partidos/feed ◄── NUEVO, público                         │
  └─────────────────────────────────────────────────────────────────┘
                                │
  ┌──────────────────────────── BASE ──────────────────────────────┐
  │  vw_goles_acreditados  (regla del autogol — base común)        │
  │         ▲                                                       │
  │  vw_resultados_partidos (marcador + walkover, sin filtro estado)│
  │         ▲                                                       │
  │  ► vw_feed_partidos  = resultados + TORNEO/GRUPO/DISCIPLINA     │
  │                        + Publicado + logos                      │
  └─────────────────────────────────────────────────────────────────┘
```

**Acoplamiento nuevo:** `NavBar` pasa a depender de `useCatalogo` (query de
disciplinas) y por lo tanto de TanStack Query en TODA ruta, incluido `/login`.
Antes el NavBar era puro. Justificado, pero implica que un backend caído hace
fallar la query del header en toda la app → la barra debe degradar a nada, no
a un error.

**Escala:** el feed devuelve como máximo `limit` filas de un día. Con 28
disciplinas y torneos amateur, 10x es ~200 partidos/día: una query indexada.
Lo que rompe primero es la falta de índice sobre `PARTIDOS.Fecha_Partido` para
el filtro por día → obligación abajo.

**SPOF:** ninguno nuevo. Todo es lectura sobre Postgres.

**Rollback:** la migración es puramente aditiva (3 columnas nullable + 1
boolean con default). `git revert` del código + `DROP COLUMN` opcional. Las
vistas son `CREATE OR REPLACE`; revertir es re-correr `04_views.sql` del commit
anterior. Ventana: minutos.

**Seguridad de la arquitectura:** los 3 endpoints nuevos/modificados son GET
sin auth, igual que los que ya existen. No hay mutación nueva. Detalle en la
Sección 3.

Hallazgos: **C5** (duplicación de la derivación del marcador), **C7**
(`TorneoAdminLayout` es scoped a un torneo y la lista de mesa no), falta de
índice por fecha, y degradación del NavBar. Todos decididos abajo.

### Sección 2 — Error & Rescue Map

```
  MÉTODO/CODEPATH                | QUÉ PUEDE FALLAR                | EXCEPCIÓN
  -------------------------------|---------------------------------|------------------
  GET /partidos/feed             | fecha con formato inválido      | RequestValidationError (422, ya mapeado)
                                 | disciplina_id inexistente       | — devuelve lista vacía
                                 | base caída                      | OperationalError
                                 | limit > máximo                  | RequestValidationError (le=200)
  vw_feed_partidos               | partido sin equipos (bracket)   | — ya excluido por el JOIN
                                 | torneo sin TORNEO_GRUPO         | imposible (FK NOT NULL)
  FeedPartidos.tsx (query)       | red caída                       | TanStack isError
                                 | respuesta vacía                 | — no es error, es empty state
  BarraDisciplinasPublica        | /disciplinas falla              | TanStack isError
  DetalleTorneoPublico           | torneo_id inexistente           | 404 de /torneos/{id}
                                 | torneo no publicado             | 404 (decidido abajo)
  <img src={logo_url}>           | URL rota / 404 / mixed content  | evento onError del DOM

  EXCEPCIÓN                      | RESCATADA | ACCIÓN                  | EL USUARIO VE
  -------------------------------|-----------|-------------------------|------------------
  RequestValidationError         | Y         | handlers.py → 422       | "Fecha inválida"
  OperationalError               | Y         | handlers.py → 500       | "No se pudo cargar"
  Partido sin equipos            | Y (base)  | JOIN interno lo excluye | no aparece en el feed
  TanStack isError (feed)        | N ← GAP   | —                       | página en blanco ← MAL
  TanStack isError (barra)       | N ← GAP   | —                       | header sin pills, sin aviso
  img onError                    | N ← GAP   | —                       | icono roto del navegador ← MAL
  404 de torneo no publicado     | N ← GAP   | —                       | pantalla vacía sin explicación
```

5 filas sin rescate en el plan original. Una (partido sin equipos) resulta
ya cubierta por el `JOIN` interno de `vw_resultados_partidos` — queda solo su
test. Las otras 4 son GAPs reales, cerradas por la obligación **C10**.

### Sección 3 — Security & Threat Model

| Amenaza | Prob. | Impacto | ¿Mitigada por el plan original? |
|---|---|---|---|
| Exposición de torneos borrador/prueba en la home | **Alta** | Media | **No** → C2 |
| IDOR en `/torneos/:id` público (enumerar torneos por id) | Alta | Baja | La API ya es pública hoy; `Publicado` lo acota (C2) |
| Fuga de PII de jugadores en el detalle público | Baja | Alta | **Ya mitigada**: `/jugadores` devuelve `JugadorPublicOut` sin cédula ni correo para caller anónimo (`routes/jugadores.py:30-56`) |
| XSS vía `Logo_URL` cargada por un admin | Media | Alta | **No** → C10 exige validar esquema `https:` y renderizar solo en `<img src>`, nunca en `dangerouslySetInnerHTML` |
| Mixed content (logo `http:` en una página `https:`) | Media | Baja | **No** → misma obligación |
| Escaneo/scraping del feed público | Media | Baja | Sin cambio: la API ya era pública. `limit` con `le=200` acota. |
| Inyección SQL en `fecha`/`disciplina_id` | Baja | Alta | Mitigada: SQLAlchemy parametriza; Pydantic tipa `date`/`int` |
| Nuevos secretos | — | — | Ninguno. Sin dependencias nuevas. |

Sin endpoints de escritura nuevos. La única superficie realmente nueva es
`Logo_URL` como dato controlado por admin que el navegador carga → C10.

### Sección 4 — Data Flow & Interaction Edge Cases

```
  INPUT ─────▶ VALIDACIÓN ─────▶ QUERY ──────▶ AGRUPACIÓN ─────▶ RENDER
  (?deporte,      │                 │              │                 │
   fecha)         ▼                 ▼              ▼                 ▼
              [fecha mal       [0 filas?]     [torneo_id       [logo roto?]
               formada?]       [base caída?]   repetido?]      [nombre 47 ch?]
              [deporte no      [limit tope?]  [partido sin     [hora en otra tz?]
               existe?]                        equipos?]
```

| Interacción | Edge case | ¿Manejado? | Cómo |
|---|---|---|---|
| Clic en pill de deporte | doble clic rápido | Sí | La URL es el estado; idempotente |
| Clic en pill | deporte sin partidos | **GAP → C10** | Empty state nombrando el deporte |
| Fila de partido | clic mientras la cabecera también es clicable | **GAP → C10** | Hermanos, no anidados (ya estaba en T5.3) |
| Fila de partido | partido sin equipos (shell de bracket) | **Ya cubierto** | El `JOIN EQUIPOS` interno de `vw_resultados_partidos` los excluye; solo falta el test (C10a) |
| Feed | 0 resultados hoy | **GAP → C1** | Fallback a la jornada más cercana + etiqueta |
| Feed | 10.000 partidos | Sí | `limit le=200` |
| Feed | resultados cambian mientras se mira | Aceptado | Sin auto-refresh (diferido) |
| Nombre de equipo largo | 47 caracteres | **GAP → C10** | `text-overflow: ellipsis`, no wrap que rompa la fila |
| Navegar atrás desde el partido | volver al feed con el mismo deporte y fecha | Sí | Ambos viven en la URL |
| Sesión revocada mientras se mira el feed | `licenseRevoked` reemplaza el shell entero | Sí | Ya lo hace `App.tsx` |

### Sección 5 — Code Quality Review

- **DRY, hallazgo principal:** T3.2 como estaba escrito ("marcador derivado
  igual que `vw_resultados_partidos`") era una copia de la regla de autogol +
  walkover. `vw_resultados_partidos` no filtra por estado, así que sirve tal
  cual → C5.
- **DRY, segundo:** T2.1 mueve `FiltroDisciplinasBar` a `components/` y T2.2
  crea `BarraDisciplinasPublica`. Dos componentes de barra. Se justifica solo si
  la pública realmente no usa las filas de modalidad/estado — y es así (esas
  props ya son opcionales). Se mantiene, pero la pública debe *envolver* a la
  compartida, no reimplementar el markup de las pills.
- **Naming:** `/estadisticas/feed-partidos` nombra mal — una lista de partidos
  no es una estadística. Se mueve a `GET /api/v1/partidos/feed` (mismo router
  que el recurso que devuelve).
- **Over-engineering:** ninguno detectado. No hay abstracción nueva sin dos
  usuarios.
- **Under-engineering:** el plan original no definía qué pasa con
  `equipos_id_local = NULL` (shell de bracket), que es un estado real del
  modelo → C10.
- **Complejidad ciclomática:** ningún método nuevo pasa de 5 ramas.

### Sección 6 — Test Review

```
  NUEVOS FLUJOS UX
    - Visitante anónimo elige deporte en el header
    - Visitante ve el feed del día agrupado por torneo
    - Visitante entra al torneo desde la cabecera
    - Visitante entra al partido desde la fila
    - Operador llega a Control de Mesa por su ruta operativa
    - Cualquiera comparte el link de un torneo/partido

  NUEVOS FLUJOS DE DATOS
    - DISCIPLINA ──▶ barra de pills
    - vw_feed_partidos ──▶ GET /partidos/feed ──▶ agrupación cliente

  NUEVOS CODEPATHS
    - filtro por fecha / por disciplina / por Publicado
    - fallback a la jornada más cercana (fecha_efectiva)
    - fallback de escudo a iniciales
    - decisión de "/" por sesión (anónimo vs logeado)

  NUEVAS INTEGRACIONES
    - ninguna externa

  NUEVOS CAMINOS DE ERROR
    - los 5 GAPs de la Sección 2
```

| Ítem | Tipo | Happy | Falla | Edge |
|---|---|---|---|---|
| `vw_feed_partidos` | Integración (pytest) | 2 torneos misma disciplina | torneo archivado excluido | partido sin equipos excluido; no publicado excluido |
| `GET /partidos/feed` | Integración | devuelve `fecha_efectiva` | fecha inválida → 422 | día vacío → cae a la jornada más cercana |
| filtros de `GET /partidos` | Integración | `fecha` + `disciplina_id` | combinación sin resultados | no rompe a `solo_mios` ni a `incluir_archivados` |
| `BarraDisciplinasPublica` | Unit (vitest+MSW) | ordena por popularidad | query falla → sin pills, sin crash | solo 1 disciplina → barra oculta |
| `FeedPartidos` | Unit | agrupa por torneo, ordena por hora | `isError` → mensaje | empty state nombra el deporte |
| `FilaPartido` | Unit | escudo renderiza | `onError` → iniciales | nombre de 47 caracteres |
| Ruteo | Unit (`App.routing.test.tsx`) | `/torneos/:id` anónimo | `/control-de-mesa` sigue gateado | `/` anónimo vs logeado |
| `Publicado` | Integración | default TRUE tras backfill | torneo despublicado → 404 | migración idempotente corrida 2 veces |

**Test de las 2 AM del viernes:** que `verificar.ps1` pruebe que la migración
`31_` es idempotente (`test_scripts_sql.py` la corre dos veces) y que las ~40
suites de backend no revientan con `UndefinedColumn` — el pitfall conocido de
este repo exige que la columna esté en `01_schema.sql` *y* en el script `NN_`
*y* en `SCRIPTS_VIGENTES`.
**Test que escribiría un QA hostil:** publicar un torneo, ponerle un
`Logo_URL` con `javascript:alert(1)`, y ver si llega al DOM.
**Riesgo de flakiness:** todo test que use "hoy". Hay que congelar la fecha,
no usar `CURRENT_DATE` real → C10.

### Sección 7 — Performance Review

- **Índice: ya existe.** `idx_partidos_fecha ON PARTIDOS(Fecha_Partido)` está en
  `database/03_indexes.sql:82` (corrección del spec review; la primera pasada de
  esta sección afirmó que faltaba y era falso). No hay nada que agregar, y
  agregarlo rompería la idempotencia de la migración.
- **N+1:** ninguno. El feed es una query; la agrupación es en memoria sobre
  ≤200 filas.
- **`vw_feed_partidos` sobre `vw_resultados_partidos` — el riesgo real:** hereda
  su `GROUP BY p.ID` sobre `vw_goles_acreditados`. Si Postgres no empuja el
  predicado de fecha por debajo de esa agregación, el feed agrega el historial
  entero para devolver un día. Es el único punto del enfoque que puede fallar de
  verdad → `EXPLAIN` obligatorio + plan B escrito (C11).
- **Payload:** ≤200 filas con ~12 campos ≈ 40 KB. Bien.
- **NavBar:** una query de catálogo extra en toda ruta, cacheada por TanStack
  con la misma `queryKey` que ya usa el back-office → 0 requests extra en la
  práctica.

### Sección 8 — Observability & Debuggability

- Hoy el proyecto no tiene métricas ni dashboards; el patrón existente es
  `print()` en `main.py` y la tabla `AUDITORIA` para escrituras.
- El feed es de solo lectura → no entra en `AUDITORIA` (que audita altas/bajas).
- **Gap:** ninguna forma de saber si el portal público se usa → C6.
- Lo proporcionado al proyecto: una línea de log estructurada por hit a
  `/partidos/feed` y a `/torneos/{id}` anónimo (sin PII, sin IP), con deporte y
  fecha. Ni Prometheus ni infra nueva — eso sería sobredimensionar un proyecto
  que hoy se levanta a mano.
- **Runbook:** "el feed sale vacío" → chequear (1) `Publicado`, (2) `Estado` del
  torneo y su grupo, (3) que haya partidos en la fecha. Se documenta en el plan.

### Sección 9 — Deployment & Rollout

- Migración `31_` **aditiva**: 3 columnas nullable + 1 boolean con default.
  Sin lock de tabla relevante en Postgres 11+ para `ADD COLUMN ... DEFAULT`.
  Compatible hacia atrás.
- **Orden:** migrar → desplegar backend → desplegar frontend. El frontend viejo
  contra el backend nuevo funciona (campos nuevos ignorados por
  `extra=ignore`); el frontend nuevo contra el backend viejo **no** (falta
  `/partidos/feed`) → el orden importa.
- **Ventana de riesgo:** entre backend y frontend, ninguna — el feed no existe
  todavía en la UI vieja.
- **Feature flag:** no hace falta. `Publicado` ya funciona como interruptor por
  torneo, y el release 1 (torneo público) no toca esquema.
- **Verificación post-deploy:** `/torneos/{id}` de un torneo publicado carga en
  incógnito; `/` en incógnito muestra el feed; un usuario logeado sigue cayendo
  en `/dashboard`.
- **Rollback:** `git revert` + re-correr `04_views.sql` anterior. Las columnas
  pueden quedar; nadie las lee.

### Sección 10 — Long-Term Trajectory

- **Reversibilidad: 4/5.** Todo aditivo salvo el cambio de `/`, que es una línea.
- **Deuda introducida:** `Logo_URL`/`Pais` sin uploader es deuda de producto
  asumida a propósito (queda anotada). `Pais` en una liga barrial es una columna
  constante — se mantiene porque el usuario la pidió explícitamente, pero se
  marca como candidata a retiro si a los 6 meses sigue NULL en todas las filas.
- **Dependencia de camino:** `vw_feed_partidos` colgando de
  `vw_resultados_partidos` sigue la decisión Eng #10 que ya vive en el repo →
  un cambio futuro de la regla de marcador se hace en un solo lugar.
- **La pregunta del año:** un ingeniero nuevo leyendo esto en 12 meses entiende
  por qué hay un feed y por qué cuelga de la vista de resultados, porque queda
  escrito. Lo que no va a entender sin la nota es por qué `/` decide por sesión
  → se comenta en `App.tsx`.
- **Qué viene después:** auto-refresh en vivo, SEO/SSR, favoritos. La
  arquitectura los soporta sin reescritura.

### Sección 11 — Design & UX Review (UI scope detectado)

```
  FLUJO DEL VISITANTE

  [ / anónimo ]
       │  header: logo + pills de deporte (scroll horizontal en móvil)
       ▼
  ┌── Feed del día ──────────────────────────┐
  │  ⚽ LigaPro · Ecuador        ◄ cabecera  │──clic──▶ /torneos/:id
  │  ──────────────────────────────────────  │           (posiciones,
  │  15:00  [E] Aucas   vs  Barcelona [E]    │──clic──▶ goleadores,
  │  17:30  [E] Emelec  vs  LDU       [E]    │  /partidos/:id  resultados)
  └──────────────────────────────────────────┘
       │ (0 resultados)
       ▼
  "No hay partidos de Fútbol el 14/09. Mostrando la jornada del 12/09."
```

| Feature | LOADING | EMPTY | ERROR | SUCCESS | PARTIAL |
|---|---|---|---|---|---|
| Barra de deportes | skeleton de pills | barra oculta si ≤1 disciplina | sin pills, sin crash | pills ordenadas | — |
| Feed | skeleton de 3 bloques | mensaje nombrando el deporte + jornada más cercana | "No se pudo cargar el feed" + reintentar | bloques agrupados | escudo roto → iniciales |
| Detalle torneo público | skeleton de tabla | "Todavía no hay partidos finalizados" (ya existe) | mensaje | tabla | — |

- **Jerarquía:** primero el deporte (header), después la competición (cabecera
  del bloque), después el partido (fila). Coincide con SofaScore y con el modelo
  mental del hincha.
- **Riesgo de AI slop:** el plan describe UI específica (hora, escudo, nombres,
  orden), no "una lista bonita". Bajo.
- **Responsive:** T2.5 nombra el scroll horizontal. Falta declarar el alto
  mínimo de toque (44px) para las pills y las filas → obligación C10.
- **Accesibilidad:** la barra compartida ya trae `role=tablist`, `aria-pressed`
  y flechas ←→. Las filas de partido deben ser `<button>`/`<a>` reales, no
  `<div onClick>`, y la cabecera del torneo un hermano clicable, no un padre.
- **Recomendación:** correr `/plan-design-review` — se hace en la Fase 2 de
  este mismo pipeline.

## Registros obligatorios

### Error & Rescue Registry
Ver la tabla de la Sección 2 (13 codepaths, 5 GAPs, todos cerrados por C10).

### Failure Modes Registry

```
  CODEPATH                    | FAILURE MODE                | RESCUED? | TEST? | USER SEES        | LOGGED?
  ----------------------------|-----------------------------|----------|-------|------------------|--------
  GET /partidos/feed          | fecha inválida              | Y        | Y     | 422 "Fecha..."   | Y
  GET /partidos/feed          | base caída                  | Y        | N     | 500 genérico     | Y
  GET /partidos/feed          | día sin partidos            | Y (C1)   | Y     | jornada cercana  | Y
  vw_feed_partidos            | partido sin equipos         | Y (base) | Y     | no aparece       | N
  vw_feed_partidos            | torneo no publicado         | Y (C2)   | Y     | no aparece       | N
  FeedPartidos.tsx            | query falla                 | Y (C10)  | Y     | msg + reintentar | N
  BarraDisciplinasPublica     | query falla                 | Y (C10)  | Y     | header sin pills | N
  FilaPartido <img>           | logo roto / 404             | Y (C10)  | Y     | iniciales        | N
  FilaPartido <img>           | Logo_URL con javascript:    | Y (C10)  | Y     | iniciales        | Y
  DetalleTorneoPublico        | torneo despublicado         | Y (C2)   | Y     | 404 explicado    | N
  "/" decide por sesión       | sesión expira a mitad       | Y        | Y     | feed público     | N
  Migración 31_               | corrida dos veces           | Y        | Y     | —                | Y
  ----------------------------|-----------------------------|----------|-------|------------------|--------
  CRITICAL GAPS: 0 (todos los RESCUED=N del plan original quedan cerrados)
```

### Diagramas producidos
1. Arquitectura del sistema (Sección 1)
2. Flujo de datos con shadow paths (Sección 4)
3. Flujo de usuario / pantallas (Sección 11)
4. Dream state (0C)
5. Secuencia de despliegue (Sección 9, en prosa ordenada)

### Auditoría de diagramas obsoletos
Los diagramas ASCII existentes viven en comentarios de `01_schema.sql`,
`04_views.sql` y `motor_formatos.py`. Ninguno describe partidos/vistas de
lectura de forma que este plan invalide. **Cero diagramas obsoletos.**

### Dream state delta
Este plan deja el producto con la cara pública construida y con el control de
qué se publica, pero sin liveness (auto-refresh) ni indexación (SSR/SEO). Es
~60% del ideal a 12 meses. Lo que falta está identificado y diferido, no
olvidado.

### "NOT in scope"
- Auto-refresh en vivo del feed — infra nueva, fuera del blast radius. → TODOS.md
- Uploader de imágenes — las columnas aceptan URL, mismo criterio que `JUGADORES.Foto_URL`. → TODOS.md
- SSR / indexación en buscadores — los OG tags estáticos cubren el caso de compartir, que es el canal real. → TODOS.md
- Búsqueda global, favoritos, notificaciones, multi-idioma — no relacionado.
- Rediseño visual del back-office — no relacionado.
- Poblar los datos de escudos y países — es contenido, no código.

## Decision Audit Trail

| # | Fase | Decisión | Clasificación | Principio | Razón | Rechazado |
|---|---|---|---|---|---|---|
| 1 | CEO | Modo SELECTIVE EXPANSION | Mechanical | P6 | Default por contexto (iteración sobre sistema vivo) | EXPANSION, HOLD, REDUCTION |
| 2 | CEO | Approach C (alcance completo, resecuenciado) | **Taste** | P1+P3 | Entrega todo lo pedido y paga la migración después de la evidencia | A (orden original), B (mínimo, no entrega req. 2 y 3) |
| 3 | CEO | C5: `vw_feed_partidos` cuelga de `vw_resultados_partidos` | Mechanical | P4 DRY | La vista ya calcula marcador con autogol y walkover, sin filtro de estado | Copiar la lógica; reescribir `PartidoOut` entero |
| 4 | CEO | C5b: **diferir** `fecha`/`disciplina_id` en `GET /partidos` a TODOS.md | Mechanical | P3 | Ningun consumidor de esta entrega los usa; agregarlos seria el segundo camino paralelo que la Seccion 5 marca como riesgo | Cerrarlo ahora |
| 5 | CEO | C2: `TORNEO.Publicado`, default TRUE + backfill | **Taste** | P1 | Da control de exposición sin cambiar el comportamiento público que la API ya tiene hoy | Default FALSE (deja el feed vacío el día 1) |
| 6 | CEO | C3: agregar los inputs de URL de logo y país al back-office | Mechanical | P1 | Sin write path la columna nace muerta | Cortar las columnas; dejarlas sin formulario |
| 7 | CEO | C4: botón Compartir + meta tags OG estáticos | **Taste** | P2 | En blast radius, <1d CC, y es el canal real (WhatsApp) | Diferir a TODOS.md |
| 8 | CEO | C6: línea de log estructurada en endpoints públicos | Mechanical | P1 | Observabilidad es alcance, no post-launch | Prometheus (sobredimensionado); nada |
| 9 | CEO | C1: fallback a la jornada más cercana en día vacío | Mechanical | P1 | Cierra el peor empty state sin cambiar el default que el usuario pidió | Cambiar el default a "próxima jornada" (→ Gate) |
| 10 | CEO | C8: la barra solo muestra disciplinas con partidos publicados | Mechanical | P4 | Misma regla que ya usa la barra del back-office | Las 28 del catálogo |
| 11 | CEO | C9: resecuenciar fases (torneo público primero) | **Taste** | P6 | Mismo alcance, primer release sin migración | Orden 1→5 original |
| 12 | CEO | C7: gate de rol en el NavLink en vez de pestaña en TorneoAdminLayout | **Taste** | P5+P3 | Menos piezas; `TorneoAdminLayout` es scoped a UN torneo y la lista no | Pestaña en el layout (T1.2 original) |
| 13 | CEO | Renombrar a `GET /partidos/feed` | Mechanical | P5 | Una lista de partidos no es una estadística | `/estadisticas/feed-partidos` |
| 14 | CEO | **Corregido por el spec review:** el indice ya existe (`03_indexes.sql:82`). Queda solo `EXPLAIN` + plan B | Mechanical | P1 | Agregarlo habria duplicado un `CREATE INDEX` y roto la idempotencia que C13 exige | Agregar el indice (habria fallado) |
| 15 | CEO | C10: cerrar los 5 GAPs de error + a11y + validar `Logo_URL` | Mechanical | P1 | Prime Directive 1: cero fallos silenciosos | Dejarlos abiertos |
| 16 | CEO | Auto-refresh y uploader → TODOS.md | Mechanical | P3 | Fuera del blast radius, infra nueva | Meterlos en este plan |
| 17 | CEO | D-A orden Fútbol/Tenis/Baloncesto | **User Challenge** | — | El usuario dictó un orden distinto al que ya está en la base | — (va al Gate) |
| 18 | GATE | **D2 — El usuario eligió su orden:** Fútbol, Tenis, Baloncesto | User Challenge resuelta | — | Lo pidió explícitamente; cuesta un `UPDATE` y es reversible | Dejar el ranking de la base; ordenar por partidos reales |
| 19 | GATE | **D3 — El usuario eligió gatear por rol** el NavLink de Control de Mesa | User Challenge resuelta | — | El público deja de verlo sin dejar huérfana la lista `/control-de-mesa` | Eliminarlo del todo; moverlo a pestaña de Torneo Admin |
| 20 | GATE | **D4 — El usuario eligió abrir en la próxima jornada con partidos**, no en "hoy" | Taste resuelta (contra mi recomendación) | — | Los torneos amateur juegan fin de semana; una portada vacía de lunes a jueves era el mayor riesgo del plan | Hoy + fallback rotulado (mi recomendación); solo hoy sin fallback |

## Obligaciones aceptadas — Fase CEO

<!-- autoplan-accepted:ceo -->
- **C1 — Densidad del feed.** `GET /partidos/feed` devuelve `fecha_efectiva` además de las filas. Si la fecha pedida no tiene partidos para esa disciplina, cae a la fecha más cercana que sí los tenga (hacia atrás primero, después hacia adelante) y el frontend lo rotula: "No hay partidos de {deporte} el {fecha}. Mostrando la jornada del {fecha_efectiva}". El default de `fecha` sigue siendo hoy. Test: día vacío devuelve `fecha_efectiva` distinta; base sin partidos devuelve lista vacía sin error.
- **C2 — Control de exposición pública.** Agregar `TORNEO.Publicado BOOLEAN NOT NULL DEFAULT TRUE` (en `TORNEO`, la edición — NO en `TORNEO_GRUPO`) en la migración `31_`, con backfill TRUE para las filas existentes: no cambia el comportamiento público que la API ya tiene hoy. **Mecanismo, no solo intención:** `GET /torneos/{torneo_id}` (`routes/torneos.py:54`) y los tres `GET /estadisticas/torneos/{torneo_id}/*` (posiciones, goleadores, resultados) hoy no tienen ninguna dependencia de auth; hay que agregarles `usuario: Usuario | None = Depends(get_current_user_optional)` y devolver 404 **solo cuando el caller es anónimo y `Publicado = FALSE`**. Sin ese matiz se rompe el back-office: `MesaPanel.tsx:91` llama exactamente al mismo `GET /torneos/{torneo_id}`. `vw_feed_partidos` filtra por `Publicado = TRUE`. Toggle "Publicar" en el formulario de edición de torneo (`TorneosAdmin.tsx`), solo TorneoAdmin/AdminGeneral. Tests: el mismo id devuelve 200 para TorneoAdmin y 404 anónimo, en las cuatro rutas; torneo despublicado excluido del feed; `MesaPanel` sigue cargando su torneo despublicado.
- **C3 — Camino de escritura para logos y país.** Además de exponer las columnas, agregar los inputs, nombrando tabla y formulario: `EQUIPOS.Logo_URL` → campo "URL del escudo" en el formulario de `EquiposAdmin.tsx`; `TORNEO_GRUPO.Pais` y `TORNEO_GRUPO.Logo_URL` → campos "País" y "URL del logo" en el formulario del grupo de torneo (`TorneoGrupoUpdate` + `PATCH /torneo-grupos/{id}` ya existen, es solo UI). Sin esto las columnas nacen y quedan NULL para siempre.
- **C4 — Canal de distribución.** Botón "Compartir" en la vista pública de torneo y en el detalle de partido, que copia el deep link al portapapeles con confirmación visible. Meta tags Open Graph **estáticos** en `frontend/index.html` (title, description, image). Alcance honesto: el preview de WhatsApp dice "Score-App", el mismo para todo link — un preview por torneo exigiría SSR o un endpoint de prerender, que queda diferido con su costo anotado (ver C14). El botón Compartir es el que entrega el valor; los OG estáticos solo evitan que el link se vea como texto pelado.
- **C5 — Una sola fuente de verdad del marcador.** `vw_feed_partidos` se construye SOBRE `vw_resultados_partidos` (que ya deriva goles con la regla de autogol vía `vw_goles_acreditados` y contempla walkover, y no filtra por estado), sumándole los JOIN a TORNEO, TORNEO_GRUPO y DISCIPLINA. Prohibido reimplementar el conteo de goles. Sigue la decisión Eng #10 ya registrada en `04_views.sql`.
- **C5b — Hueco #5, diferido con nombre.** Los query params `fecha` y `disciplina_id` en `GET /api/v1/partidos` NO entran en este plan: ningún consumidor de esta entrega los usa (el feed va por `/partidos/feed`), y agregarlos ahora sería exactamente el segundo camino paralelo que la Sección 5 marca como el riesgo principal. Se difiere a TODOS.md junto con C14, anotando que el hueco existe y por qué no se cierra todavía.
- **C6 — Saber si funciona.** Métrica declarada, acotada a lo que la instrumentación realmente soporta: **hits por semana a `/partidos/feed` y a la vista pública de torneo, y la razón entre ambos** (cuántos de los que ven el feed entran a un torneo). No se declara "sesiones" ni "conversión por sesión": el log no lleva identificador de sesión y no se va a agregar uno. Instrumentación: `logger.info("feed_hit", extra={...})` con `endpoint`, `disciplina_id`, `fecha`, `fecha_efectiva` — sin IP, sin user-agent, sin datos personales. Reemplaza el `print()` de `main.py` como patrón para código nuevo. Nada de infraestructura nueva. **Umbral y fecha de revisión:** si a las 4 semanas del release R1 los hits a la vista pública de torneo siguen en cero, R3 (feed + barra de deportes) no se construye — se replantea el canal primero.
- **C7 — Puerta de entrada a Control de Mesa.** En vez de mover la lista a una pestaña de `TorneoAdminLayout` (que está alcanzado a UN torneo mientras que la lista no lo está), el `NavLink` de `NavBar.tsx` se condiciona por rol: visible solo para TorneoAdmin, AdminGeneral y Arbitro. El público deja de verlo, que es lo que se pidió, y el operador conserva su acceso. Se mantiene además el botón por fila "Gestionar en Mesa" en `PartidosDelTorneo.tsx` hacia `/control-de-mesa/partido/:id`.
- **C8 — Barra de deportes con contenido.** La barra pública muestra solo las disciplinas que tienen al menos un partido publicado en la fecha visible; nunca las 28 del catálogo. **No es derivable de la respuesta filtrada** (una respuesta de Fútbol solo trae Fútbol): `GET /partidos/feed` devuelve un sidecar `disciplinas_con_partidos` calculado ANTES de aplicar `disciplina_id`. "Fecha visible" queda definida como `fecha_efectiva` (la que el fallback de C1 terminó mostrando), no la pedida. Con una sola disciplina con contenido la barra se oculta. **Consecuencia aceptada explícitamente:** en un deployment de una sola liga de fútbol —que es el wedge que el design doc describe— la barra no se renderiza y el requerimiento #2 queda latente hasta que exista una segunda disciplina con partidos. Es deliberado: 27 pills muertas son peores que ninguna barra.
- **C9 — Resecuenciar las fases.** Orden de entrega: **(R1)** migración `31_` (incluido `Publicado`) + vista pública de torneo + deep links + botón compartir + OG + log; **(R2)** vista `vw_feed_partidos` y endpoint `/partidos/feed`; **(R3)** feed, barra pública de deportes y cambio de `/`. La migración se adelanta a R1 a propósito: `Publicado` es lo que protege la vista pública de torneo, y publicar esa vista una release antes que su propio guard dejaría expuestos los torneos borrador justo en la ventana R1. Cada release es desplegable solo.
- **C10 — Cerrar los fallos silenciosos.** (a) Partidos sin equipos definidos (shells de bracket con `equipos_id_local`/`equipos_id_visitante` NULL) ya quedan excluidos gratis: `vw_resultados_partidos` usa `JOIN EQUIPOS` interno (`04_views.sql:193-195`) y `vw_feed_partidos` cuelga de ella. No agregar un `WHERE ... IS NOT NULL` redundante; sí agregar el test de regresión que lo fija. (b) El feed y la barra de deportes renderizan estado de error visible con reintento; la barra degrada a vacío sin romper el header. (c) Todo escudo o logo usa `onError` para caer a iniciales, reusando el patrón de `avatarUtils.ts`. (d) `Logo_URL` se valida en el backend contra el esquema `https:` y se renderiza solo como `src` de `<img>`, nunca como HTML. (e) Filas de partido y cabecera de torneo son elementos clicables hermanos (`<a>`/`<button>` reales), con alto mínimo de toque de 44px; nombres largos con `text-overflow: ellipsis`. (f) Todo test que dependa de "hoy" congela la fecha en vez de usar la del sistema.
- **C11 — Verificar el plan de ejecución, con plan B.** **Corrección: el índice ya existe** — `idx_partidos_fecha ON PARTIDOS(Fecha_Partido)` está en `database/03_indexes.sql:82`. No agregarlo (un `CREATE INDEX` duplicado rompería la idempotencia que C13 exige). Lo que sí hay que hacer: correr `EXPLAIN` una vez sobre el feed para confirmar que el predicado de fecha baja por debajo del `GROUP BY p.ID` que `vw_feed_partidos` hereda de `vw_resultados_partidos`. **Si no baja** (riesgo real: agregaría el historial entero para devolver un día), el plan B es que `vw_feed_partidos` aplique el rango de fechas como `WHERE` sobre `PARTIDOS` antes de unirse a la vista de resultados, o que el feed pase a ser una query parametrizada en el service en vez de una vista. Este es el único punto del enfoque que puede no funcionar, y ahora tiene salida.
- **C12 — Nombre correcto del endpoint.** El endpoint del feed vive en `GET /api/v1/partidos/feed`, en el router de partidos, no en `/estadisticas/`. Una lista de partidos no es una estadística. Se registra antes de `/{partido_id}` para que FastAPI no interprete "feed" como un id.
- **C13 — Disciplina de migración de este repo.** Toda columna nueva de C2/C3 se agrega en LOS TRES lugares: `database/01_schema.sql`, el script `database/31_migracion_portal_publico.sql` (idempotente, con guarda sobre `information_schema`, porque `test_scripts_sql.py` lo corre dos veces) y la lista `SCRIPTS_VIGENTES` de `backend/tests/test_scripts_sql.py`. Omitir cualquiera revienta las ~40 suites de backend con `UndefinedColumn`.
- **C14 — Diferidos a TODOS.md.** Cuatro ítems, cada uno con contexto y condición de reentrada, no como intención vaga: (1) auto-refresh en vivo del feed (polling o WebSocket); (2) uploader de imágenes para escudos y logos; (3) preview de Open Graph por torneo/partido, que exige SSR o un endpoint de prerender (ver C4); (4) los query params `fecha`/`disciplina_id` de `GET /partidos` (hueco #5, ver C5b).
- **C15 — Definir "día" antes de construir "los partidos del día".** `PARTIDOS.Fecha_Partido` es `TIMESTAMP` sin zona horaria. Se declara: la fecha es la del servidor, `fecha` por default es `CURRENT_DATE` del servidor, y la UI rotula la fecha explícitamente en la cabecera del feed en vez de decir "Hoy" a secas — así un cliente en otro huso ve qué día está mirando en vez de un feed corrido. Todos los tests congelan el reloj (ya cubierto por C10f). Queda anotado en el runbook.
- **C16 — `/` decide por sesión.** La home pública no reemplaza el arranque de los usuarios logeados: `/` renderiza el feed para un caller anónimo y sigue redirigiendo a `/dashboard` cuando hay sesión. Es el único cambio de esta entrega que toca a todo usuario existente, así que va con su test (`/` anónimo → feed; `/` logeado → `/dashboard`) y con un comentario en `App.tsx` explicando por qué la ruta decide por sesión.
- **C17 — La superficie pública de partido, decidida y no dejada a medias.** `PartidoEnVivo.tsx:61` consume `GET /estadisticas/torneos/{torneo_id}/resultados`. Si C2 hace que esa ruta devuelva 404 para anónimos, la página pública de un partido de un torneo despublicado queda a medio renderizar (equipos, marcador y eventos cargan; resultados revienta). Hay que elegir explícitamente una de las dos y testearla: (a) gatear también `/partidos/:id` y `GET /partidos/{id}` por `Publicado`, devolviendo un 404 limpio; o (b) declarar la superficie de partido pública pase lo que pase y hacer que la query de resultados tolere el 404. No queda a criterio del implementador.
- **C18 — Dónde NO alcanza `Publicado`, dicho en voz alta.** El guard de C2 cubre el detalle, pero hoy enumeran torneos sin filtrar y siguen públicos: `GET /torneos` (lista, `torneos.py:14`), `GET /partidos?torneo_id=`, `GET /torneos/{id}/bracket` (`motor_formatos.py:71`), `GET /estadisticas/proximos-partidos` y `GET /estadisticas/equipos/{id}/plantilla`. Con solo el detalle gateado, el listado sigue devolviendo el nombre y el fixture completo de un torneo borrador. Decisión obligatoria antes de implementar: o `GET /torneos` filtra `Publicado` para callers anónimos, o se documenta en el plan por qué cada superficie queda abierta. Silencio no es una respuesta.
- **C19 — El costo real de C3, corregido.** "Es solo UI" era falso. Verificado: `TorneoGrupoUpdate` (`schemas/torneo_grupo.py:19`) solo acepta `nombre` y `estado`, y `TorneosAdmin.tsx` no tiene formulario de edición de torneo (su `Modo` es `lista | crear-grupo | nueva-edicion`; el único PATCH, línea 269, archiva el grupo). Solo la mitad de Equipos es barata (usa el builder genérico `camposEquipo`). Lo demás exige campos de schema, servicio, mutación y formulario nuevos, en dos entidades distintas. El esfuerzo de C3 sube de S a M y así queda anotado.
- **C20 — Logging: es infraestructura, no una línea.** `grep -rn "import logging|getLogger" backend/app` devuelve cero hits: el backend no tiene logger, ni handler, ni formateador, y el único patrón es `print()` en `main.py`. Bajo el formateador por defecto de uvicorn, `logger.info(..., extra={...})` descarta los campos de `extra`, y el servidor se levanta a mano sin retención de logs. Así que C6 no es gratis: hay que configurar logger + handler + formateador (o emitir una línea JSON a stdout) y decidir dónde se retiene. Si eso no se hace, la métrica de C6 no se puede recolectar y el umbral de 4 semanas es una ficción — en ese caso se baja la métrica a lo que sí se pueda contar y se dice.
<!-- /autoplan-accepted:ceo -->

## MEGA PLAN REVIEW — COMPLETION SUMMARY (CEO)

```
  +====================================================================+
  |            MEGA PLAN REVIEW — COMPLETION SUMMARY                   |
  +====================================================================+
  | Mode selected        | SELECTIVE EXPANSION                         |
  | System Audit         | 0 TODO/FIXME reales; 0 stash; 4 archivos    |
  |                      | calientes dentro del blast radius           |
  | Step 0               | Approach C; 4 de 6 premisas no sostenidas   |
  | Section 1  (Arch)    | 4 issues found                              |
  | Section 2  (Errors)  | 13 error paths mapped, 4 GAPS               |
  | Section 3  (Security)| 3 issues found, 1 High severity (Logo_URL)  |
  | Section 4  (Data/UX) | 11 edge cases mapped, 4 unhandled           |
  | Section 5  (Quality) | 4 issues found                              |
  | Section 6  (Tests)   | Diagram produced, 8 gaps                    |
  | Section 7  (Perf)    | 1 issue found (EXPLAIN + plan B)            |
  | Section 8  (Observ)  | 1 gap found (cero metricas)                 |
  | Section 9  (Deploy)  | 1 risk flagged (orden backend->frontend)    |
  | Section 10 (Future)  | Reversibility: 4/5, debt items: 2           |
  | Section 11 (Design)  | 3 issues                                    |
  +--------------------------------------------------------------------+
  | NOT in scope         | written (6 items)                           |
  | What already exists  | written (9 piezas mapeadas)                 |
  | Dream state delta    | written (~60% del ideal a 12 meses)         |
  | Error/rescue registry| 13 codepaths, 0 CRITICAL GAPS tras C10      |
  | Failure modes        | 12 total, 0 CRITICAL GAPS                   |
  | TODOS.md updates     | 4 items proposed (C14)                      |
  | Scope proposals      | 8 proposed, 4 accepted, 3 deferred, 1 cut   |
  | CEO plan             | written                                     |
  | Outside voice        | codex: unavailable (CLI no instalado)       |
  | Lake Score           | 7/8 recommendations chose complete option   |
  | Diagrams produced    | 5 (arquitectura, flujo datos, flujo UX,     |
  |                      | dream state, secuencia de despliegue)       |
  | Stale diagrams found | 0                                           |
  | Unresolved decisions | 2 (D-A orden de deportes; C1 default fecha) |
  +====================================================================+
```

### Unresolved Decisions (CEO)
- **D-A (User Challenge):** el usuario dictó "1. Fútbol, 2. Tenis, 3.
  Baloncesto"; la base ya tiene Fútbol=1, Baloncesto=2, Tenis=3 de un design
  review previo. Va al Final Approval Gate.
- **C1-fuerte (Taste):** cambiar el default de `fecha` de "hoy" a "próxima
  jornada con partidos". Auto-decidido en la versión conservadora (default hoy
  + fallback etiquetado); la versión fuerte va al Gate.

---

# FASE 2 — DESIGN REVIEW (UI/UX del plan)

Voces: Claude subagent **[subagent-only]** — Codex CLI no instalado.
Mockups: **no generados.** El binario del diseñador existe
(`~/.claude/skills/gstack/design/dist/design`) pero no hay API key de OpenAI
(`No OpenAI API key found`), así que esta revisión es text-only sobre
wireframes ASCII. Es una degradación real y hay que decirlo: las decisiones
visuales de abajo no fueron vistas, fueron razonadas.

## Step 0 — Design Scope Assessment

**0A. Rating inicial: 5/10.** El plan especifica la capa de datos con rigor
poco común (contrato del endpoint, envelope, `ORDER BY`, `WHERE` entero) y
deja la capa que el visitante realmente mira como una enumeración. T4.3 dice
literalmente "hora, escudo local, nombre local, escudo visitante, nombre
visitante, y marcador": seis sustantivos en fila, que no es un layout.
Un 10 para ESTE plan sería: el grid de la fila de partido con sus columnas y
tamaños, la tabla estado→tratamiento visual, los cinco estados del feed
(incluido `truncado`, que el plan inventó y nunca renderiza), y la URL del
deporte decidida.

**0B. DESIGN.md: no existe.** No hay sistema de diseño declarado. Las
decisiones se calibran contra los principios universales y contra los patrones
que ya viven en `index.css`. Recomendación de fondo: `/design-consultation`
antes de R3.

**0C. Existing Design Leverage** (verificado en código, no asumido):

| Patrón | Dónde | Reusar |
|---|---|---|
| `.chip-disciplina` | `index.css:1122` — `padding .45rem .85rem`, `font-size .9rem` | Sí, con variante pública (ver D11: mide ~33px, el plan exige 44px) |
| `.nav-bar` | `index.css:47` — `flex` + `flex-wrap`, `.nav-bar__links{flex:1}`, y en `@media(max-width:480px)` `order:3; width:100%` | Sí, pero insertar una segunda fila NO es gratis (D13) |
| `badge--{estado}` | `index.css`, usado en `PartidoEnVivo.tsx:206` | Como referencia de color de estado, no como badge por fila |
| Avatar con iniciales | `avatarUtils.ts`, `AvatarJugador.tsx` | Sí — y también para el logo de torneo, no emoji (D14) |
| Polling en vivo | `PartidoEnVivo.tsx:9`, `LIVE_POLL_MS = 5000` | Referencia: el detalle refresca, el feed no (D9) |

**0D. Focus areas:** las 7 dimensiones (P1 — completeness). Auto-decidido.

## Step 0.5 — Dual Voices

### CODEX SAYS (design critique)

```
[codex-unavailable: binary not found]
```

### CLAUDE SUBAGENT (design completeness)

16 hallazgos: 4 críticos (D1-D4), 5 altos (D5-D9), 7 medios (D10-D16).
Verificó `NavBar.tsx`, `index.css`, `FiltroDisciplinasBar.tsx` y
`PartidoEnVivo.tsx` antes de opinar.

### DESIGN OUTSIDE VOICES — LITMUS SCORECARD

```
DESIGN OUTSIDE VOICES — LITMUS SCORECARD:
═══════════════════════════════════════════════════════════════
  Check                                    Claude   Codex  Consensus
  ─────────────────────────────────────── ───────  ─────── ─────────
  1. Brand unmistakable in first screen?   NOT SPEC'D  N/A   N/A
  2. One strong visual anchor?             NO (D1)     N/A   N/A
  3. Scannable by headlines only?          YES         N/A   N/A
  4. Each section has one job?             YES         N/A   N/A
  5. Cards actually necessary?             YES (no hay card mosaic)  N/A  N/A
  6. Motion improves hierarchy?            NOT SPEC'D  N/A   N/A
  7. Premium without decorative shadows?   NOT SPEC'D  N/A   N/A
  ─────────────────────────────────────── ───────  ─────── ─────────
  Hard rejections triggered:               0          N/A   N/A
═══════════════════════════════════════════════════════════════
Outside voice unavailable → Consensus N/A en las 7, nunca CONFIRMED.
```

Clasificador: **OPERATE (App UI)** para el feed y el detalle de torneo — el
visitante viene a terminar una tarea (ver un resultado), no a ser persuadido.
Se aplican las App UI rules: jerarquía de superficie calma, denso pero
legible, lenguaje utilitario, chrome mínimo, cards solo si la card ES la
interacción. Cero hard rejections: el plan no propone card mosaic, ni hero,
ni carousel, ni grid de 3 columnas.

## Pass 1: Information Architecture — 6/10 → 9/10

El plan sí define el orden deporte → competición → partido, y la jerarquía
coincide con el modelo mental del hincha. Lo que falta es la jerarquía DENTRO
de la fila (D1) y qué manda dentro de la vista de torneo (D8: tres tablas
apiladas sin orden declarado, y ninguna respuesta para un torneo de bracket,
que en este repo existe — `motor_formatos.py:71`).

```
  FEED (grid de la fila, D1)
  ┌──────┬────────────────────────────────┬────────┐
  │ 48px │ 1fr                            │  40px  │
  │ HORA │ [escudo] Equipo Local          │   2    │
  │ 15:00│ [escudo] Equipo Visitante      │   1    │
  └──────┴────────────────────────────────┴────────┘
   ^ columna fija     ^ dos renglones        ^ tabular-nums
```

## Pass 2: Interaction State Coverage — 4/10 → 9/10

El hueco más grande de la revisión. `FeedPartidoOut` devuelve `estado` y
ningún task dice cómo se pinta — y distinguir "en curso" de "terminado" es
literalmente la razón por la que alguien abre un portal de resultados.
Además `truncado` se inventa en el envelope y no se renderiza en ningún lado.

| Feature | LOADING | EMPTY | ERROR | SUCCESS | PARTIAL |
|---|---|---|---|---|---|
| Barra de deportes | skeleton de pills, altura reservada | oculta si ≤1 | sin pills, header intacto | pills, activa sólida | — |
| Feed | skeleton de 3-5 filas con el grid de D1 | "No hay partidos de Fútbol esta semana" + acción a otra disciplina | "No se pudo cargar" + Reintentar | bloques agrupados | `truncado`: pie "Mostrando los primeros N" + Ver todos |
| Fila de partido | — | — | — | ver tabla de estados | escudo roto → iniciales |
| Detalle torneo | skeleton de tabla | empty por sección, no tabla de ceros | mensaje | pestañas | — |

**Tabla estado → tratamiento visual** (los 4 valores reales de
`chk_partidos_estado`, `02_constraints.sql:251` — **corrección a la voz de
diseño: no existen Suspendido ni Aplazado en este esquema**, así que el
`<> 'Cancelado'` de T3.2 no excluye nada por accidente):

| `PARTIDOS.Estado` | Columna izquierda | Marcador | Color |
|---|---|---|---|
| `Programado` | hora `HH:mm` | — | texto normal |
| `En curso` | minuto (`67'`) | visible | acento en vivo, con punto |
| `Finalizado` | `FIN` | visible | apagado (muted) |
| `Cancelado` | — | — | no aparece: el `WHERE` lo excluye |

## Pass 3: User Journey & Emotional Arc — 5/10 → 8/10

| Paso | El usuario hace | Siente | ¿El plan lo sostiene? |
|---|---|---|---|
| 1 | Recibe el link por WhatsApp | curiosidad | Sí (C4), aunque el preview dice "Score-App" para todo |
| 2 | Abre el torneo, ve la tabla | reconocimiento | Sí (T5.2), salvo torneo vacío o bracket (D8) |
| 3 | Toca un partido | expectativa | Sí |
| 4 | Ve el detalle | **desorientación** | **NO (D7)**: sin nombre de torneo, sin fecha, sin vuelta |
| 5 | Quiere volver al torneo | frustración | **NO (D7)**: partido→torneo no existe |
| 6 | Vuelve al feed, ve todo congelado | duda ("¿está roto?") | **NO (D9)**: el detalle refresca cada 5s, el feed no y no lo dice |

El arco se rompe exactamente donde C6 quiere medir: la segunda página vista.

## Pass 4: AI Slop Risk — 8/10 → 9/10

Clasificado OPERATE. Cero patrones de la blacklist: no hay gradientes
morados, ni grid de 3 columnas con iconos en círculos, ni todo centrado, ni
blobs decorativos, ni copy genérico. El plan describe UI específica (hora,
escudo, nombres, orden), no "una lista limpia y moderna".
Dos tells menores que sí aplican: **emoji como elemento de diseño** (D14 — el
fallback de logo de torneo usa el emoji de disciplina, que convive mal con
escudos PNG reales en la misma columna y renderiza distinto por SO), y
**superficies del navegador sin tematizar** (selección, caret, focus ring,
scrollbar) — el reflejo que ningún detector atrapa y que separa "diseñado" de
"ensamblado".

## Pass 5: Design System Alignment — 5/10 → 8/10

No hay DESIGN.md, así que se puntúa la especificación explícita del propio
plan. Sube porque las obligaciones de abajo fijan grid, tamaños, estados y
tokens de color por estado. Queda corto de 10 porque el sistema sigue sin
existir como archivo: los valores viven en el plan, no en un vocabulario
compartido. Recomendación: `/design-consultation` antes de R3.

## Pass 6: Responsive & Accessibility — 5/10 → 9/10

- **D11 verificado:** `.chip-disciplina` mide ~33px de alto
  (`padding .45rem .85rem` + `font-size .9rem`). El plan se exige 44px a sí
  mismo en C10e para las filas. El control de navegación primario del portal
  quedaba por debajo de su propio umbral.
- **D13 verificado:** `.nav-bar` es `flex/wrap` con `.nav-bar__links{flex:1}`
  y `order:3; width:100%` bajo 480px. Meter una segunda fila exige `order` y
  `width` propios. Y con T1.2 el anónimo se queda sin ningún link:
  `.nav-bar__links` vacío pero con `flex:1` deja un hueco expansivo entre la
  marca y "Iniciar sesión".
- **D5:** la barra que aparece cuando llega la respuesta empuja el feed hacia
  abajo (CLS) justo mientras el dedo va a la primera fila.
- Lo que el plan ya traía bien: `role=tablist`, `aria-pressed`, flechas ←→
  heredadas de `FiltroDisciplinasBar`, y hermanos clicables en vez de
  `<button>` anidado (C10e).

## Pass 7: Unresolved Design Decisions

| Decisión | Si se difiere, qué pasa |
|---|---|
| Forma de la URL del deporte (D12) | Se congela el día 1 en la forma que salga; los links compartidos la heredan para siempre |
| Selector de fecha vs fallback ±7 días (D3) | El implementador elige la combinación que miente sobre el contenido |
| País: texto libre vs ISO/select (D14) | "Argentina", "ARG" y "argentina" en la misma pantalla |
| Pestañas vs scroll en el torneo público (D8) | Tres tablas apiladas, y un torneo de bracket sin respuesta |

## Obligaciones aceptadas — Fase DESIGN

<!-- autoplan-accepted:design -->
- **D1 — El grid de la fila de partido, escrito.** T4.3 deja de ser una enumeración. Layout explícito: `grid-template-columns: 48px 1fr 40px` — columna de hora/minuto a la izquierda, columna de equipos al medio con DOS renglones apilados (local arriba, visitante abajo, cada uno con su escudo de 20-24px), columna de marcador a la derecha. Marcador y hora con `font-variant-numeric: tabular-nums` para que los dígitos no bailen entre filas. La enumeración horizontal de seis elementos no entra en 400px con nombres reales ("Deportivo Municipal" vs "Atlético Independiente"): el `text-overflow: ellipsis` de C10e era la confesión de que el layout no cabía.
- **D2 — Tabla estado → tratamiento visual, cerrada sobre el enum real.** `PARTIDOS.Estado` tiene exactamente 4 valores (`chk_partidos_estado`, `02_constraints.sql:251`): `Programado` → columna izquierda muestra la hora, sin marcador, texto normal; `En curso` → muestra el minuto, marcador visible, color de acento en vivo con punto indicador; `Finalizado` → muestra `FIN`, marcador visible en tono apagado; `Cancelado` → no aparece (el `WHERE` de T3.2 ya lo excluye). Distinguir "en curso" de "finalizado" es la razón por la que alguien abre un portal de resultados: no pueden compartir el mismo marcador neutro. Corrección a la voz de diseño: en este esquema NO existen `Suspendido` ni `Aplazado`, así que el `<> 'Cancelado'` no excluye nada por accidente.
- **D3 — El selector de fecha y el fallback dejan de contradecirse.** Se elige la opción barata: el fallback de ±7 días de C1 aplica **solo a la carga inicial sin `fecha` en la URL**. Cuando el usuario navega explícitamente (toca ayer/hoy/mañana o una fecha), NO hay fallback: si ese día no tiene partidos, se muestra el empty state de ese día. Sin esto, tocar "Mañana" podía devolver la jornada de hace tres días con la pill "Mañana" activa, y tocar "Ayer" podía no cambiar nada — el control mintiendo sobre su propio contenido.
- **D4 — `truncado` se renderiza o no existe.** Se renderiza: pie de lista con "Mostrando los primeros N partidos del día" y una acción que amplía el `limit`. Un campo del envelope que ningún componente pinta es un feed que termina en seco sin avisar.
- **D5 — La barra de deportes no salta ni se reordena bajo el dedo.** (a) Altura reservada desde el primer render (skeleton de pills o `min-height` fijo en el contenedor), para que la llegada de la respuesta no empuje el feed hacia abajo justo cuando el usuario va a tocar la primera fila. (b) El contenido de la barra se congela con el set de la PRIMERA respuesta de la sesión de navegación y no se reordena en cada cambio de filtro — si no, elegir Tenis cambia `fecha_efectiva`, que cambia el sidecar, que hace desaparecer pills vecinas. (c) Si la disciplina pedida por URL no está en el sidecar, su pill se muestra igual, activa, con el empty state del feed: nunca se borra el control que el usuario acaba de usar.
- **D6 — El feed tiene puerta de entrada para usuarios con sesión.** C16 manda al logeado a `/dashboard` y T1.2 le saca el link de Dashboard al anónimo; entre las dos, nadie con sesión puede llegar al feed — ni el TorneoAdmin que acaba de cargar los partidos. Se agrega un link "Portal público" en el `NavBar` para usuarios con sesión. Es el mismo razonamiento que C6 aplicó a la vista de torneo (T5.2c) y que no se había aplicado al feed. Una línea.
- **D7 — El detalle de partido recupera identidad y salida.** Verificado en `PartidoEnVivo.tsx:196-210`: hoy la página se identifica con `resultado?.equipo_local ?? "Local"` y `resultado ? marcador : "- : -"`. El visitante que llega desde WhatsApp ve dos nombres y un marcador flotando, sin torneo, sin fecha y sin vuelta. Se agrega cabecera con nombre y país del torneo enlazada a `/torneos/:torneoId` — el eslabón partido→torneo, que es justamente la segunda página vista que C6 quiere medir. Y si C17 se resuelve por la opción (b) (tolerar el 404), el estado degradado es un mensaje explícito "Resultados no disponibles para este torneo", nunca los placeholders `Local - : - Visitante`, que se leen como datos reales.
- **D8 — La vista pública de torneo deja de asumir liga.** (a) Las tres secciones se organizan en pestañas: Posiciones | Resultados | Goleadores, con Resultados por defecto si el torneo ya empezó. (b) Para un torneo de formato Eliminación no hay tabla de posiciones: se muestra el bracket (`GET /torneos/{id}/bracket`, `motor_formatos.py:71`) en su lugar, o se omite la pestaña. (c) Empty state por sección — un torneo recién creado no muestra tres tablas de ceros, que es la peor primera impresión posible de una página cuyo único propósito es ser compartida.
- **D9 — Frescura honesta en el feed.** `PartidoEnVivo.tsx:9` refresca cada 5s (`LIVE_POLL_MS`); el feed no refresca (C14, correcto). Pero el visitante que ve un marcador moverse en el detalle y vuelve a un feed congelado concluye que el feed está roto. Se agrega rótulo de frescura en la cabecera ("Actualizado 14:32") y un botón de recarga manual (`refetch` de react-query). Cero infraestructura, y hace honesta la promesa.
- **D10 — Estados específicos, no genéricos.** El patrón vigente del repo es `<p>Cargando partido...</p>` (`PartidoEnVivo.tsx:162`); un texto suelto en una pantalla en blanco no sirve como portada del producto. Carga: skeleton de 3-5 filas con la misma métrica del grid de D1 (no spinner — el feed tiene forma conocida). Y el vacío REAL (fuera de la ventana ±7 días) necesita su propio copy, distinto del copy del fallback que C1 ya escribió: "No hay partidos de Fútbol esta semana", con acción hacia otra disciplina.
- **D11 — La barra pública llega a 44px.** Medido: `.chip-disciplina` (`index.css:1122`) es `padding .45rem .85rem` + `font-size .9rem` ≈ 33px de alto, por debajo del mínimo de 44px que el propio plan se exige en C10e. Se crea la variante `.chip-disciplina--publico` con `min-height: 44px`, sin tocar el chip del back-office (no mover la densidad de `TorneosAdmin`).
- **D12 — La URL del deporte, decidida.** `/?deporte=<slug>` — slug legible, compartible, y deja `/` como home. Se descarta `/deporte/:disciplinaId` (id numérico, ilegible en un link de WhatsApp, y compite con `/` como ruta). Además se declara el estado por defecto: sin `?deporte`, el feed muestra TODAS las disciplinas agrupadas, y la barra pública NO lleva pill "Todos" (el estado "todos" es la ausencia de filtro, no un chip más).
- **D13 — El header público es su propia estructura.** Verificado: `.nav-bar` (`index.css:47`) es `flex` + `flex-wrap` con `.nav-bar__links{flex:1}`, y bajo 480px `.nav-bar__links` lleva `order:3; width:100%`. Meter la barra "como segunda fila" no es agregar un hijo: exige `order`/`width` propios y reordenar el móvil. Y con T1.2 el anónimo se queda sin ningún link, dejando `.nav-bar__links` vacío pero con `flex:1` — un hueco expansivo entre la marca y "Iniciar sesión". Se especifica: fila 1 marca + sesión, fila 2 la barra, y `nav-bar__links` no se renderiza cuando queda vacío.
- **D14 — Un sistema visual, no dos.** (a) El fallback del logo de torneo usa el patrón monocromo de iniciales de `avatarUtils.ts` (el mismo que ya usan los escudos en T4.3), NO el emoji de disciplina: escudos PNG reales y emojis del sistema conviviendo en la misma columna vertical tienen pesos ópticos incompatibles y renderizan distinto en Windows, Android e iOS. (b) `TORNEO_GRUPO.Pais` es `VARCHAR(60)` libre y se va a llenar con "Argentina", "ARG" y "argentina" en la misma pantalla: el formulario de C3 usa un `<select>` de países (o ISO-2), no un input de texto libre.
- **D15 — "Compartir" especificado hasta el fallback.** El botón intercambia su propio label por "¡Copiado!" durante 2s (sin introducir un sistema de toasts nuevo). En móvil usa `navigator.share` cuando está disponible. `navigator.clipboard` no existe en contexto inseguro: si falta, se muestra el link en un campo seleccionable en vez de que el botón no haga nada y no avise.
- **D16 — "Ver página pública" no engaña al admin.** Con su sesión, el admin abre un torneo despublicado y la página carga perfecto (por C2, el 404 es solo para anónimos), así que se va convencido de que el link funciona hasta que alguien lo recibe y ve un 404. En la tarjeta de `TorneosAdmin.tsx` se muestra el estado de publicación junto al botón, y si está despublicado el label pasa a "Vista previa (no publicado)" con un aviso en la propia vista pública visible solo para el admin. Además, el 404 público de un torneo despublicado necesita diseño: no la pantalla de error cruda del router.
- **D17 — Tematizar las superficies del navegador.** Color de selección, caret, focus ring, scrollbar y `underline-offset` salen hoy de los defaults del navegador, que no pertenecen a ningún sistema de diseño. Se definen desde la paleta de `index.css`. Es el reflejo más barato que separa una página diseñada de una ensamblada, y el que más se saltea.
<!-- /autoplan-accepted:design -->

## DESIGN PLAN REVIEW — COMPLETION SUMMARY

```
  +====================================================================+
  |         DESIGN PLAN REVIEW — COMPLETION SUMMARY                    |
  +====================================================================+
  | System Audit         | Sin DESIGN.md; UI scope alto (feed, barra,  |
  |                      | torneo publico, detalle de partido)         |
  | Step 0               | 5/10 inicial; foco en las 7 dimensiones     |
  | Pass 1  (Info Arch)  | 6/10 -> 9/10 after fixes                    |
  | Pass 2  (States)     | 4/10 -> 9/10 after fixes                    |
  | Pass 3  (Journey)    | 5/10 -> 8/10 after fixes                    |
  | Pass 4  (AI Slop)    | 8/10 -> 9/10 after fixes                    |
  | Pass 5  (Design Sys) | 5/10 -> 8/10 after fixes                    |
  | Pass 6  (Responsive) | 5/10 -> 9/10 after fixes                    |
  | Pass 7  (Decisions)  | 4 resueltas, 0 diferidas                    |
  +--------------------------------------------------------------------+
  | NOT in scope         | written (heredado de CEO, 6 items)          |
  | What already exists  | written (5 patrones verificados en codigo)  |
  | TODOS.md updates     | 1 item propuesto (design-consultation)      |
  | Approved Mockups     | 0 generados (sin API key), 0 aprobados      |
  | Decisions made       | 17 (D1-D17) agregadas al plan               |
  | Decisions deferred   | 0                                           |
  | Overall design score | 4/10 -> 8/10                                |
  +====================================================================+
```

Overall = el menor de los 6 pases puntuados: 4/10 antes, 8/10 después.
Todos los pases quedan en 8+: el plan es design-complete **sobre el papel**.
La salvedad honesta: sin mockups, nada de esto fue visto. Correr
`/design-review` sobre el sitio renderizado después de implementar.

### Unresolved Decisions (Design)
Ninguna. Las 4 ambigüedades del Pass 7 quedaron resueltas en D3, D8, D12 y D14.

---

# FASE 2.5 — DX REVIEW (experiencia de desarrollador)

Voces: Claude subagent **[subagent-only]** — Codex CLI no instalado.
Modo: **DX POLISH** (override de /autoplan; el default por contexto coincide —
es una mejora sobre un producto que ya existe).
Tipo de producto detectado: **API/Service** — el plan agrega
`GET /api/v1/partidos/feed`, modifica `GET /torneos/{id}` y los tres
`/estadisticas/torneos/{id}/*`. El disparador de alcance DX fue mecánico y
verificable: `API` x11, `endpoint` x3, `npm` x1 = 15 coincidencias sobre un
umbral de 2 (`gstack-autoplan-snapshot detectDxScope`).

## Step 0A — Developer Persona Card

```
TARGET DEVELOPER PERSONA
========================
Who:       Dev full-stack solo que mantiene Score-App (FastAPI + Postgres +
           React/Vite), trabaja en Windows, verifica con .\verificar.ps1.
Context:   Vuelve al repo cada varios dias; retoma un plan escrito semanas
           antes. Tambien: cualquier consumidor futuro del endpoint publico
           (la API ya es publica sin auth).
Tolerance: Alta para leer codigo, BAJA para ambiguedad de contrato. No
           abandona el producto — es suyo — pero implementa la version
           equivocada si el documento se contradice.
Expects:   Que el plan sea ejecutable en el orden en que esta escrito, y que
           el contrato del endpoint no tenga huecos que descubra en produccion.
```

Persona inferida del README, de `CLAUDE.md` y de `verificar.ps1` (P6:
auto-decidida, sin preguntar). No es un SDK con miles de usuarios: el "dev"
principal es quien mantiene el repo, y el costo de un mal DX acá no es
abandono, es implementar mal.

## Step 0B — Developer Empathy Narrative

> Abro `docs/plans/portal-publico-feed-partidos-plan.md`. Arranca con "Lo que
> ya existe", verificado línea por línea — bien, confío. Bajo a Fase 1 y
> empiezo: T1.1, T1.2, T1.3. Fase 2: T2.4 me dice "`/?deporte=futbol` **o**
> `/deporte/:disciplinaId`". Elijo el segundo, se parece más al resto del
> ruteo del repo. Sigo. Fase 3: escribo la vista, el endpoint, el envelope.
> Fase 4: implemento el fallback de ±7 días en todas las cargas, como dice
> T4.6. Llego al final del archivo y encuentro un bloque de obligaciones
> C1-C20 y D1-D17 que **corrige cuatro cosas que ya implementé**: D12 descarta
> la URL que elegí, D3 restringe el fallback que acabo de escribir, C19 me
> dice que "es solo UI" era falso y que me faltan dos formularios enteros, y
> C9 me dice que el orden de fases que seguí no era el orden de entrega.
> Vuelvo atrás. Después levanto el entorno, corro la migración, abro `/` y
> veo una página en blanco: no sé si la vista está mal o si no hay partidos
> hoy. No hay seed. Busco "runbook" porque el plan lo menciona dos veces —
> no existe ese archivo.

Esa narrativa es el hallazgo F2 + F1 contados desde adentro. El plan no falla
por falta de rigor: falla porque el rigor quedó **apendizado** en vez de
fundido en las tareas.

## Step 0C — Competitive DX Benchmark

Aside no está instalado (`NEEDS_ASIDE`) y no se usó WebSearch, así que se
aplican los benchmarks de referencia del propio skill — declarado, no
inventado:

```
COMPETITIVE DX BENCHMARK
=========================
Tool           | TTHW    | Notable DX Choice                    | Source
Stripe         | ~30s    | una key, un curl, el dinero se mueve | referencia del skill
Vercel         | ~2min   | push-to-deploy                       | referencia del skill
Firebase       | ~3min   | consola con datos de ejemplo         | referencia del skill
Docker         | ~5min   | docker run hello-world               | referencia del skill
SCORE-APP FEED | INDEF.  | sin seed: la pagina arranca vacia    | este plan (F1)
```

**Tier objetivo auto-decidido: Competitive (2-5 min)** (P5: el camino más
simple que alcanza el tier). Para esta feature eso significa: correr la
migración, correr un seed, abrir `/` y ver partidos. Hoy el TTHW es
literalmente indefinido, no lento — un dev no puede distinguir "lo implementé
mal" de "no hay datos para hoy".

## Step 0D — Magical Moment

El momento mágico de esta feature no es para un dev externo: es **abrir `/` en
una ventana de incógnito y ver partidos reales agrupados por torneo, sin
login**. Vehículo de entrega elegido (P5, el de menor esfuerzo que alcanza el
tier): **comando copy-paste** — un script de seed + una URL. Nada de
playground hosteado ni tutorial guiado; esto es un repo de una persona.

## Step 0E — Mode: DX POLISH (auto-decidido)

## Step 0F — Developer Journey Map

```
STAGE           | DEVELOPER DOES                    | FRICTION POINTS        | STATUS
----------------|-----------------------------------|------------------------|--------
1. Discover     | Lee el plan de arriba a abajo     | F2: obligaciones       | fixed (F2)
                |                                   | apendizadas corrigen   |
                |                                   | 4 tareas ya leidas     |
2. Install      | Corre la migracion 31_            | F10: si olvida uno de  | fixed (F10)
                |                                   | los 3 lugares, 40      |
                |                                   | suites mudas           |
3. Hello World  | Abre / y espera ver el feed       | F1: sin seed, pagina   | fixed (F1)
                |                                   | en blanco, causa       |
                |                                   | indistinguible         |
4. Real Usage   | Llama al endpoint con un slug     | F3: el slug no existe  | fixed (F3)
                |                                   | en ningun contrato     |
                |                                   | F5: el fallback no es  | fixed (F5)
                |                                   | expresable en la API   |
5. Debug        | Recibe un 404                     | F9: sin discriminador, | fixed (F9)
                |                                   | el copy adivina        |
6. Upgrade      | Redespliega / revierte            | F11: idempotente pero  | fixed (F11)
                |                                   | sin nota de reversion  |
```

## Step 0G — First-Time Developer Confusion Report

```
FIRST-TIME DEVELOPER REPORT
============================
Persona: dev full-stack solo que mantiene Score-App
Attempting: implementar R1 del plan

T+0:00  Abro el plan. "Lo que ya existe" esta verificado con archivo:linea.
        Confio en el documento.
T+0:10  Fase 2, T2.4: "/?deporte=futbol o /deporte/:disciplinaId". Elijo
        uno. Sigo.
T+0:40  Fase 4, T4.6: implemento el fallback de +-7 dias en toda carga.
T+1:10  Llego al bloque de obligaciones al final. D12 descarta mi URL. D3
        restringe mi fallback. C19 dice que me faltan dos formularios.
        Vuelvo atras.
T+1:30  Corro la migracion. Abro /. Pagina en blanco. No se si es la vista
        o si no hay datos. Busco el runbook que el plan cita dos veces: no
        existe.
T+2:00  Escribo el endpoint. El frontend tiene el slug "futbol" y necesita
        un disciplina_id. El sidecar trae {id, nombre}, sin slug. Escribo un
        slugify en el cliente y me pregunto si coincide con el que genero
        el link ("Futbol" con acento?).
```

Los 4 puntos de confusión (F2, F1, F14, F3) quedan cerrados por las
obligaciones de abajo. Auto-decidido "todos" (P1 — completeness).

## Step 0.5 — Dual Voices

### CODEX SAYS (DX — developer experience challenge)

```
[codex-unavailable: binary not found]
```

### CLAUDE SUBAGENT (DX — independent review)

20 hallazgos: 3 críticos (F1, F3, F5), 8 altos, 9 medios. Los dos que más
caros salen tarde: **F3** (el slug que la URL pública promete no existe en
ningún contrato) y **F5** (el fallback de fecha vive en un `if` del cliente,
no en el contrato) — arreglarlos después cuesta una migración de URL pública
y un redeploy de la API.

### DX DUAL VOICES — CONSENSUS TABLE

```
DX DUAL VOICES — CONSENSUS TABLE:
═══════════════════════════════════════════════════════════════
  Dimension                           Claude   Codex  Consensus
  ──────────────────────────────────── ───────  ─────── ─────────
  1. Getting started < 5 min?          NO (F1)  N/A     N/A
  2. API/CLI naming guessable?         NO (F3,F6) N/A   N/A
  3. Error messages actionable?        NO (F9)  N/A     N/A
  4. Docs findable & complete?         NO (F12,F14) N/A N/A
  5. Upgrade path safe?                PARCIAL (F11) N/A N/A
  6. Dev environment friction-free?    NO (F10,F16) N/A N/A
═══════════════════════════════════════════════════════════════
Outside voice unavailable → las 6 celdas N/A, nunca CONFIRMED.
SINGLE-VOICE CRITICALS (F1, F3, F5): sin confirmacion cruzada.
```

## Passes 1-8

**Pass 1 — Getting Started: 2/10 → 8/10.** Un 2 porque el TTHW es
indefinido: sin seed, la primera ejecución muestra una página en blanco cuya
causa no se puede distinguir (F1). Sube a 8 con el seed + el comando en el
runbook. No llega a 10 porque sigue requiriendo Postgres levantado y la
migración corrida a mano.

**Pass 2 — API/CLI/SDK: 4/10 → 9/10.** Un 4 por tres huecos de contrato: el
slug que la URL pública promete no existe en ningún schema (F3), el fallback
no es expresable como parámetro (F5), y el sidecar tiene semántica circular
(F4). Más naming inconsistente dentro del mismo schema (F6: `logo_torneo`,
`logo_local`, ninguno con `_url`, mientras el repo usa `foto_url`).

**Pass 3 — Error Messages: 3/10 → 8/10.** Un 3 porque el plan no especifica
un solo cuerpo de error. Tres caminos concretos sin contrato: el 404 de
torneo despublicado (indistinguible de "no existe" y de "sin resultados", y
D7 exige un copy que solo es correcto en uno de los tres casos), la validación
`https:` de `Logo_URL` (¿qué ve el admin que pegó `http://`?), y el 422 de
fecha inválida (que la Sección 2 de la fase CEO atribuyó a un handler que
**no existe**: `exceptions/handlers.py` no registra `RequestValidationError`).

**Pass 4 — Documentation: 3/10 → 8/10.** `schema.d.ts` da tipos, no
semántica (F12): `fecha_efectiva` aparece como `string` sin decir que puede
diferir de `fecha_pedida`. Cero ejemplos copy-paste en todo el plan. El
"runbook" se invoca dos veces y no existe como archivo (F14).

**Pass 5 — Upgrade Path: 6/10 → 8/10.** La migración es aditiva e
idempotente, con test que la corre dos veces — eso está bien. Falta decir que
es irreversible-por-innecesaria y que el código viejo ignora las columnas
nuevas (F11).

**Pass 6 — Dev Environment: 4/10 → 9/10.** El modo de falla más probable de
toda la entrega está documentado en prosa (C13) en vez de guardado en código
(F10). Y `verificar.ps1` no declara si `gen:api` entra o no, así que un
`schema.d.ts` desactualizado pasa en verde (F16).

**Pass 7 — Community & Ecosystem: N/A → sin score.** Repo privado de una
persona, sin comunidad, sin plugins, sin pricing. No hay hallazgos y no se
inventa un score. Se examinó: no hay CONTRIBUTING.md, ni canal, ni ecosistema
de extensiones, y nada en este plan los introduce.

**Pass 8 — DX Measurement: 2/10 → 7/10.** C6 fija un gate duro (si a las 4
semanas los hits son cero, R3 no se construye) y C20 admite que el logging no
existe. Entre los dos queda sin definir el formato, la retención y el comando
de conteo (F13). Un gate que no se puede evaluar se resuelve por default, y
el default sería "sí, construyamos R3" — que es exactamente lo que el gate
quería impedir.

## Obligaciones aceptadas — Fase DX

<!-- autoplan-accepted:dx -->
- **F1 — Camino a "hello world" para el feed.** Agregar `database/seed_portal_demo.sql` (o un fixture de pytest reutilizable) que cree 2 torneos de 2 disciplinas, publicados, con partidos en `CURRENT_DATE` cubriendo los 3 estados visibles de D2 (`Programado`, `En curso`, `Finalizado`). Sin esto, un dev que clona el repo y corre las migraciones ve una página en blanco y no puede distinguir "lo implementé mal" de "no hay datos para hoy": el TTHW de esta feature es indefinido, no lento. Va con una línea en el runbook: correr el seed y abrir `/`.
- **F2 — El plan se refunde por release, no se lee con un anexo de correcciones.** Antes de implementar, las tareas se reescriben en UNA lista ordenada por R1 → R2 → R3, con cada obligación C/D ya aplicada al texto de la tarea y la referencia entre paréntesis como nota, no como fuente que hay que ir a buscar al final. Hoy el documento se contradice si se lee en orden: T2.4 ofrece dos formas de URL y D12 descarta una; T4.6 define el fallback en toda carga y D3 lo restringe a la inicial; C3 dice "es solo UI" y C19 dice que era falso; las Fases 1-5 no corren en el orden que C9 manda. Un implementador que lea de arriba a abajo construye la versión equivocada de cuatro cosas. Además: `T5.4` queda como tarea muerta ocupando un id, y `T3.4`/`T3.4b` agrupan como sub-items dos trabajos de tamaño muy distinto.
- **F3 — El slug del deporte existe en la base o la URL pública no resuelve.** D12 promete `/?deporte=<slug>`, pero `GET /partidos/feed` acepta `disciplina_id`, el sidecar devuelve `{id, nombre}` y `DISCIPLINA` no tiene columna de slug en ninguna parte. Un link de WhatsApp llega con un slug y el frontend necesita un id que solo viene en la respuesta del endpoint que todavía no puede llamar. Se agrega `DISCIPLINA.Slug VARCHAR(60) UNIQUE` en la migración `31_` (backfill con `lower` + `unaccent` + `regexp_replace`, en los TRES lugares de C13), el sidecar pasa a `{id, slug, nombre}`, y el endpoint acepta `deporte` (slug) además de `disciplina_id`. El slug se genera en un solo lugar: la base. Sin esto hay un `slugify` en el cliente que tiene que coincidir por casualidad con el que generó el link ("Fútbol" → `futbol` vs `fútbol`).
- **F4 — La semántica del sidecar deja de ser circular.** C8 dice que `disciplinas_con_partidos` se calcula ANTES del filtro de disciplina, y que se calcula sobre `fecha_efectiva` — pero `fecha_efectiva` se eligió aplicando ese mismo filtro (C1). Caso reproducible: hoy hay Fútbol y no Tenis; el usuario toca Tenis, `fecha_efectiva` cae al 09/09, el sidecar calculado sobre el 09/09 puede no incluir Fútbol y la pill de Fútbol desaparece. D5b congela la barra y tapa el síntoma en la UI, pero el contrato sigue siendo indefendible para cualquier otro consumidor. Se resuelve en el contrato: **el sidecar se calcula siempre sobre `fecha_pedida`**, independiente de todo filtro. Definición limpia y nombre honesto.
- **F5 — El fallback de fecha es un parámetro, no un `if` del cliente.** D3 resolvió bien el problema de producto pero lo puso en el frontend ("el fallback aplica solo cuando no hay `fecha` en la URL"), lo que deja al endpoint sin forma de expresar "dame el 16/09 y si está vacío, vacío", y al cliente sin forma de pedir "hoy sin fallback". Se agrega `ventana_fallback_dias: int = Query(7, ge=0, le=30)`, donde `0` desactiva el fallback. El frontend manda `7` en la carga inicial y `0` al navegar. La regla queda en el contrato, testeable desde el backend, y no en un `if` de un componente que el próximo consumidor no va a replicar.
- **F6 — Naming consistente en `FeedPartidoOut`.** Hoy conviven tres convenciones (`logo_torneo` entidad, `logo_local` rol, y ninguno con `_url` aunque el repo usa `Foto_URL`/`foto_url`), y 17 campos planos donde `partido.torneo` es un nombre y `partido.torneo_id` un entero. Se anida: `torneo: {id, nombre, grupo, pais, logo_url}`, `local: {id, nombre, logo_url, goles}`, `visitante: {...}`. El agrupamiento por torneo de T4.4 se vuelve trivial y el tipo generado se documenta solo.
- **F7 — `truncado` se completa o se elimina.** Falta `total_disponible` (el `COUNT` sale de la misma query), sin el cual el pie de D4 no puede decir "de M"; falta definir si N es el `limit` pedido o lo realmente devuelto tras cortar en borde de torneo (siempre menor); y falta el comportamiento en el tope `le=200` (¿el botón desaparece, se deshabilita, o sigue mintiendo?). Con `total_disponible` presente, `truncado` es derivable y puede eliminarse del envelope.
- **F9 — Un envelope de error, con código estable.** El plan no especifica un solo cuerpo de error en ningún punto. Se define `{detail, codigo, sugerencia}` con `codigo` estable (`torneo_no_publicado`, `torneo_inexistente`, `logo_url_insegura`) para todo lo nuevo. **Cuidado con la fuga:** devolver `torneo_no_publicado` a un anónimo revela que el torneo existe, así que para caller anónimo se devuelve un código genérico y el discriminador solo viaja con sesión. El frontend mapea `codigo` → copy; hoy mapea un status pelado a un copy que adivina, y el copy que D7 exige ("Resultados no disponibles para este torneo") solo es correcto en uno de los tres casos que producen ese 404. Incluye el mensaje que ve el TorneoAdmin que pegó una URL `http://` — la validación de C10d hoy pide el chequeo y no pide el mensaje.
- **F10 — El fallo más probable de la entrega se guarda en un test, no en prosa.** C13 dice que omitir uno de los tres lugares "revienta las ~40 suites con `UndefinedColumn`" — un modo de falla conocido, con causa y arreglo identificados, cuya única defensa es que el implementador recuerde leer C13. El síntoma no se autoexplica: el error dice `column "logo_url" does not exist`, no menciona `SCRIPTS_VIGENTES` ni `01_schema.sql`. Se agrega a `test_scripts_sql.py` un test que compare el set de columnas que produce `01_schema.sql` contra el que producen los scripts de `SCRIPTS_VIGENTES`, y falle con un mensaje que nombre el archivo faltante. Es el arreglo de mayor retorno por línea escrita de todo el plan: convierte 40 errores mudos en 1 error que dice qué hacer.
- **F11 — Decir que la migración no necesita rollback.** `31_` es aditiva e idempotente (y T3.6 la corre dos veces), pero no hay down-migration ni nota. C9 promete "cada release es desplegable solo", y desplegable no es replegable. Una línea en el encabezado del `.sql` y en el runbook: aditiva, sin rollback necesario, el código viejo ignora las columnas nuevas por `extra=ignore`.
- **F12 — El endpoint se documenta donde el dev lo va a leer.** `npm run gen:api` regenera tipos, no semántica: `fecha_efectiva: string` no dice que puede diferir de `fecha_pedida`, y `truncado: boolean` no dice que el corte respeta bordes de torneo. Docstring en el handler con las tres reglas no obvias (fallback y su ventana, orden `torneo_grupo → torneo → fecha → id`, corte en borde de bloque) + un `example` en `model_config` de la respuesta + un curl copy-paste en el runbook. El plan hoy no tiene un solo ejemplo copiable.
- **F13 — La métrica de C6 se cierra o se baja, pero no queda a medias.** C6 fija un gate duro (4 semanas, cero hits → R3 no se construye) y C20 admite que el logging es infraestructura inexistente. Antes de R1 hay que cerrar los tres pendientes: formato exacto de la línea (`{"evt":"feed_hit","endpoint":...,"disciplina_id":...,"fecha":...,"fecha_efectiva":...,"ts":...}` a stdout), dónde se retiene (archivo rotado o journald, con nombre), y el comando literal de conteo en el runbook. Si no se cierran, entonces se baja la métrica explícitamente y **se borra el umbral de 4 semanas**: un gate que no se puede evaluar se resuelve por default, y el default sería construir R3, que es justo lo que el gate quería impedir.
- **F14 — El runbook existe o no se lo cita.** C15 y F1 mandan anotar cosas "en el runbook" y ese archivo no existe ni tiene ruta. Se crea `docs/runbook-portal-publico.md` (seed, curl de ejemplo, comando de conteo de la métrica, nota de rollback, veredicto del `EXPLAIN`), o esas notas se mandan a `TODOS.md`, que sí existe y que el plan ya usa bien.
- **F15 — El `EXPLAIN` de C11 con criterio binario.** "Confirmar que el predicado de fecha baja por debajo del `GROUP BY`" no es evaluable como está. Se escribe el `EXPLAIN (ANALYZE, BUFFERS)` exacto a correr, el criterio binario que dispara el plan B (si el plan muestra un Seq Scan sobre `PARTIDOS` con el filtro de fecha aplicado DESPUÉS del Aggregate, se activa el plan B de C11), y dónde se pega el output (el runbook de F14).
- **F16 — `verificar.ps1` declara qué cubre.** El plan agrega pasos (migración `31_`, `EXPLAIN`, `npm run gen:api`) sin decir si entran en el único gate descrito. Un dev que ve verde no sabe si su `schema.d.ts` quedó desactualizado. Se agrega `gen:api` + `git diff --exit-code frontend/src/api/schema.d.ts` al script, que convierte "me olvidé de regenerar" en un fallo con nombre, y se lista explícitamente qué queda manual.
- **F17 — "Sesión de navegación" definida y con salida.** D5b congela la barra "con el set de la PRIMERA respuesta de la sesión de navegación" y ese término no está definido en ningún lado (¿montaje del componente? ¿vida de la pestaña? ¿`sessionStorage`?), así que cada implementador elige distinto. Peor: sin evento de descongelado, una pestaña abierta desde ayer muestra pills de ayer para siempre. Se define como el ciclo de vida del `QueryClient` (la barra lee un `useQuery` de key fija que la primera respuesta puebla) y se engancha el descongelado al botón de recarga manual que D9 ya introduce. Gratis.
- **F18 — La barra no dispara la query del feed en toda la app.** T2.3/D13 la montan en `NavBar`, que se renderiza en TODAS las rutas — incluidas `/torneos/:id`, `/partidos/:id` y el back-office — y T2.2 la alimenta del sidecar de `GET /partidos/feed`. Nunca se dice si eso significa una llamada de feed completa en cada página solo para pintar pills. Se decide y se escribe: la barra **lee la caché** de react-query con la key del feed y no dispara la query; con caché vacía no se renderiza, consistente con la regla "≤1 disciplina → no se renderiza" de C8.
- **F20 — `/dashboard` para anónimo, decidido.** T1.2 esconde el link y cambia el catch-all, pero no dice si `/dashboard` tipeado directo sigue alcanzable para un anónimo. Si sigue, se escondió el link sin cambiar la superficie; si no sigue, es un cambio de comportamiento sin `RequireRole` mencionado y sin test. Se escribe la decisión y se agrega el caso a `App.routing.test.tsx`. D6 ya resolvió bien la mitad simétrica (link "Portal público" para el logeado); falta esta.
- **F-DIFERIDOS — a TODOS.md, con condición de reentrada.** (1) `tz` como parámetro del feed (F8): C15 rotula la fecha en la UI, que alcanza para el wedge de una liga local, pero un consumidor en otro huso no tiene salida programática; reentra cuando exista un torneo fuera del huso del servidor. (2) Flag para forzar la barra de deportes con una sola disciplina (F19a): reentra si el requerimiento #2 hace falta demostrarlo antes de tener una segunda disciplina.
<!-- /autoplan-accepted:dx -->

## DX PLAN REVIEW — SCORECARD

```
+====================================================================+
|              DX PLAN REVIEW — SCORECARD                             |
+====================================================================+
| Dimension            | Score  | Prior  | Trend  |
|----------------------|--------|--------|--------|
| Getting Started      |  8/10  |  --    | nuevo  |
| API/CLI/SDK          |  9/10  |  --    | nuevo  |
| Error Messages       |  8/10  |  --    | nuevo  |
| Documentation        |  8/10  |  --    | nuevo  |
| Upgrade Path         |  8/10  |  --    | nuevo  |
| Dev Environment      |  9/10  |  --    | nuevo  |
| Community            |  N/A   |  --    | n/a    |
| DX Measurement       |  7/10  |  --    | nuevo  |
+--------------------------------------------------------------------+
| TTHW                 | indefinido -> ~3 min (seed + abrir /)        |
| Competitive Rank     | Competitive (2-5 min), tras F1               |
| Magical Moment       | designed via comando copy-paste (seed + URL) |
| Product Type         | API/Service                                  |
| Mode                 | DX POLISH                                    |
| Overall DX           |  2/10  ->  7/10                              |
+====================================================================+
| DX PRINCIPLE COVERAGE                                               |
| Zero Friction      | covered (F1)                                   |
| Learn by Doing     | covered (F1 seed + F12 curl)                   |
| Fight Uncertainty  | covered (F9 codigo de error + F10 test)        |
| Opinionated + Escape Hatches | covered (F5 ventana_fallback_dias)   |
| Code in Context    | covered (F12 ejemplo + F14 runbook)            |
| Magical Moments    | covered (abrir / en incognito y ver partidos)  |
+====================================================================+
```

Overall = el menor de los pases puntuados (DX Measurement, 7/10) — 2/10 antes
de las obligaciones. Ningún pase queda por debajo de 6, así que no hay deuda
de DX crítica. Community queda `N/A` a propósito: es un repo privado de una
persona, no se inventa un score.

## DX IMPLEMENTATION CHECKLIST

```
DX IMPLEMENTATION CHECKLIST
============================
[ ] TTHW < 5 min: seed + abrir / (F1)
[ ] La migracion corre con un comando y es idempotente (C13)
[ ] Un test falla con nombre si falta un lugar de los tres (F10)
[ ] Momento magico: / en incognito muestra partidos reales
[ ] Todo error nuevo lleva codigo estable + sugerencia (F9)
[ ] El codigo de error no filtra existencia a un anonimo (F9)
[ ] El endpoint acepta el slug que la URL publica promete (F3)
[ ] El fallback de fecha es un parametro, no un if del cliente (F5)
[ ] El sidecar se calcula sobre fecha_pedida, sin circularidad (F4)
[ ] total_disponible presente; comportamiento en el tope definido (F7)
[ ] Docstring + example + curl copy-paste (F12)
[ ] Runbook creado y citado por ruta real (F14)
[ ] EXPLAIN con criterio binario y veredicto registrado (F15)
[ ] verificar.ps1 declara que cubre; gen:api con diff --exit-code (F16)
[ ] Nota de rollback en el encabezado de 31_ (F11)
[ ] schema.d.ts regenerado y commiteado
```

### Unresolved Decisions (DX)
Ninguna. Los 20 hallazgos quedaron en obligaciones aceptadas o diferidos con
condición de reentrada (F8, F19a).

---

# FASE 3 — ENG REVIEW (el gate requerido, sobre el plan final enmendado)

Voces: Claude subagent **[subagent-only]** — Codex CLI no instalado.
Esta fase corre última y revisó el plan **ya enmendado** por CEO, Design y DX
(49.871 bytes de Implementation plan, sha `da7dc7cb…`).

## Step 0 — Scope Challenge

**Complexity check: DISPARA.** El plan toca ~22 archivos e introduce 1 vista,
2 endpoints, 4 columnas y ~6 componentes. Por override de /autoplan el alcance
**no se reduce** (P2), pero el disparo obliga a nombrar qué se simplificó:
tres cosas se sacaron por ser trabajo que no agrega cobertura (C5b diferido,
el índice de C11 que ya existía, el `WHERE IS NOT NULL` de C10a que el JOIN
interno ya hace), y una se simplificó de raíz en esta fase (E-M3 abajo).

**Mínimo que logra el objetivo:** sigue siendo R1 (torneo público + deep
links + compartir). No se recorta.

**Search check:** Aside no instalado, WebSearch no usado — *búsqueda no
disponible, se procede con conocimiento en distribución*. Los dos patrones
que importaban se resolvieron contra el código del propio repo, que es mejor
evidencia: colgar de `vw_resultados_partidos` **[Layer 1]** (la decisión Eng
#10 ya registrada en `04_views.sql`), y el predicado de rango semiabierto
sobre un `TIMESTAMP` indexado **[Layer 1]**.

**TODOS cross-reference:** `TODOS.md` fue triado el 2026-09-01; ningún ítem
aparcado bloquea este plan ni se desbloquea con él. Los 6 diferidos nuevos
(C14 ×4, F8, F19a) se agregan.

**Distribution check:** no introduce artefacto nuevo (ni binario, ni paquete,
ni imagen). No aplica.

## Step 0.5 — Dual Voices

### CODEX SAYS (eng — architecture challenge)

```
[codex-unavailable: binary not found]
```

### CLAUDE SUBAGENT (eng — independent review)

Veredicto: **no implementable como está** — 3 bloqueantes, 6 defectos de
lógica, 3 de seguridad, 7 menores. Verificó cada afirmación contra el código.
Los tres que más duelen, **confirmados por mí contra el repo**:

| Hallazgo | Verificación |
|---|---|
| **B1** `unaccent` no existe | `grep -rn "CREATE EXTENSION\|unaccent" database/` → **cero hits**. La migración `31_` de F3 fallaría con `function unaccent(text) does not exist` en cualquier base limpia, incluida la de `test_scripts_sql.py`. |
| **L1** `Estado='Activo'` borra torneos terminados | `chk_torneo_estado CHECK (Estado IN ('Activo','Inactivo','Finalizado'))` (`02_constraints.sql:50`). El día que el admin marca el torneo `Finalizado` —el día de la final— **la final desaparece del feed**. |
| **L3** `Estado` es nullable | `EQUIPOS.Estado VARCHAR(20) DEFAULT 'Activo'` sin `NOT NULL` (`01_schema.sql:175`). `WHERE Estado = 'Activo'` descarta en silencio toda fila con `Estado IS NULL` (lógica de tres valores). |

### ENG DUAL VOICES — CONSENSUS TABLE

```
ENG DUAL VOICES — CONSENSUS TABLE:
═══════════════════════════════════════════════════════════════
  Dimension                           Claude      Codex  Consensus
  ──────────────────────────────────── ───────    ─────── ─────────
  1. Architecture sound?               SI, con L3  N/A     N/A
  2. Test coverage sufficient?         NO (11 huecos) N/A  N/A
  3. Performance risks addressed?      NO (L2, S3) N/A     N/A
  4. Security threats covered?         NO (B3, S1-S3) N/A  N/A
  5. Error paths handled?              PARCIAL     N/A     N/A
  6. Deployment risk manageable?       NO (B1)     N/A     N/A
═══════════════════════════════════════════════════════════════
Outside voice unavailable → las 6 celdas N/A, nunca CONFIRMED.
SINGLE-VOICE BLOCKERS (B1, B2, B3): sin confirmacion cruzada, pero B1 y L1
verificados directamente contra el codigo por el orquestador.
```

## Sección 1 — Architecture Review

```
  GRAFO DE DEPENDENCIAS (▲ = nuevo o modificado en esta entrega)

                        ┌──────────────────┐
                        │ vw_goles_acredit.│  (regla autogol — base comun)
                        └────────▲─────────┘
                                 │
                        ┌────────┴─────────┐
                        │vw_resultados_part│  (marcador + walkover, sin
                        └────────▲─────────┘   filtro de estado)
                                 │
              ┌──────────────────┴───────────┐
              │  ▲ vw_feed_partidos           │  + JOIN TORNEO, TORNEO_GRUPO,
              │    (5 JOIN explicitos, L3)    │    DISCIPLINA, EQUIPOS x2
              └──────────────────┬───────────┘
                                 │
     ┌───────────────────────────┼──────────────────────────┐
     │                           │                          │
 ▲ GET /partidos/feed   ▲ GET /disciplinas/     GET /estadisticas/*
   (publico, cache 60s)    con-partidos           (▲ +auth opcional)
     │                     (publico, barato)             │
     │                           │                       │
     ▼                           ▼                       ▼
 ▲ FeedPartidos.tsx      ▲ BarraDisciplinas     DetalleTorneoPublico ▲
   BloqueTorneo ▲           Publica (en NavBar,    PartidoEnVivo
   FilaPartido  ▲           en TODA ruta)

  ACOPLAMIENTO NUEVO: NavBar -> un endpoint propio y barato (E-M3), NO al
  feed. Antes de E-M3, NavBar dependia de la query del feed en toda ruta.
```

**SPOF:** ninguno nuevo; todo es lectura sobre Postgres.
**Escala:** lo que rompe primero es el `GROUP BY` sobre el histórico de
eventos cuando el predicado de fecha no usa el índice (L2) — no el volumen de
filas devueltas.
**Fallo de producción realista por cada integración nueva:** `/partidos/feed`
bajo un bucle de requests anónimos (S3) satura CPU por el `GROUP BY` y llena
el disco con el log de C6/F13; mitigado por caché de 60s + ventana acotada a
7 días + log condicional.
**Rollback:** aditivo. `git revert` + re-correr el `04_views.sql` anterior.
Las columnas pueden quedar; nadie las lee.
**Diagramas en código:** `vw_feed_partidos` merece un comentario ASCII en
`04_views.sql` mostrando de qué vista cuelga, siguiendo el patrón que ya usan
`vw_tabla_posiciones` y `vw_goles_acreditados`.

**Hallazgos:** L3 (2 JOIN a EQUIPOS que el plan no enumeraba), B3 (la
frontera de `Publicado` deja 4 rutas abiertas), E-M3 (el acoplamiento
NavBar→feed se elimina de raíz).

## Sección 2 — Code Quality Review

- **DRY:** ninguna violación nueva. C5 ya evitó la grande. El sidecar
  duplicado entre el feed y el header se elimina con E-M3 — una sola fuente.
- **Error handling:** F9 lo cubre; falta el discriminador de los 3 casos que
  producen el mismo 404 (cubierto por E-B3 al elegir C17b).
- **Sub/over-engineering:** `truncado` era under-specified (L5); el corte por
  bloque no es un `LIMIT` de SQL sino una ventana (`dense_rank()` +
  `COUNT(*) OVER ()`), trabajo real que T3.3 presentaba como un bullet.
- **Diagramas obsoletos en archivos tocados:** ninguno. Los comentarios ASCII
  de `01_schema.sql`, `04_views.sql` y `motor_formatos.py` siguen siendo
  exactos tras estos cambios.
- **Refactor mezclado con feature (E-M5):** T2.1 mueve archivos compartidos
  dentro de la release de la feature.

## Sección 3 — Test Review

**Framework detectado:** `CLAUDE.md` no tiene sección Testing. Auto-detección:
`RUNTIME:python` (`pyproject.toml`), `RUNTIME:node` (`package.json`),
`SCRIPT:package.json test` → pytest (backend) + vitest (frontend), ambos
orquestados por `.\verificar.ps1`.

```
CODE PATHS                                        USER FLOWS
[+] vw_feed_partidos                              [+] Visitante anonimo ve el dia
  ├── WHERE Publicado                               ├── [GAP] Feed agrupado por torneo
  │   ├── [GAP] publicado -> aparece                ├── [GAP] Empty state real (fuera de +-7d)
  │   └── [GAP] despublicado -> no aparece          └── [GAP] Fallback rotulado
  ├── WHERE Estado torneo
  │   ├── [GAP] Activo    -> aparece              [+] Deep link desde WhatsApp
  │   ├── [GAP] Finalizado-> aparece (L1!)          ├── [GAP] /torneos/:id anonimo
  │   └── [GAP] Inactivo  -> no aparece             ├── [GAP] /partidos/:id anonimo
  ├── WHERE Estado IS NULL                          └── [GAP] torneo despublicado -> 404
  │   └── [GAP] NULL -> aparece (L3!)
  ├── JOIN EQUIPOS x2 (interno)                   [+] Operador llega a Mesa
  │   └── [OK-heredado] shell de bracket fuera      ├── [GAP] NavBar por los 4 roles
  └── marcador                                      └── [GAP] MesaPanel con torneo despublicado
      └── [OK-heredado] autogol + walkover
[+] GET /partidos/feed                            [+] Back-office publica
  ├── fecha default (CURRENT_DATE de PG, M1)        ├── [GAP] toggle Publicar
  │   └── [GAP] default resuelto en PG              └── [GAP] Ver pagina publica (E-M2: nuevo=FALSE)
  ├── ventana_fallback_dias
  │   ├── [GAP] =0 -> vacio                       [+] Error states
  │   ├── [GAP] =7 -> fecha_efectiva distinta       ├── [GAP] logo http:// neutralizado
  │   └── [GAP] frontera exacta -7d / -8d           ├── [GAP] logo javascript: rechazado
  ├── corte por bloque                              └── [GAP] feed isError con reintento
  │   ├── [GAP] bloque > limit -> no vacio (L5!)
  │   └── [GAP] orden determinista, 2 grupos homonimos (M6)
  └── [GAP] cache 60s no sirve datos de otra fecha
[+] GET /disciplinas/con-partidos
  └── [GAP] nunca vacio mientras el feed tenga contenido (L4)
[+] Migracion 31_
  ├── [GAP] idempotente x2
  ├── [GAP] 31_ esta en SCRIPTS_VIGENTES (L6 test 2)
  └── [GAP] delta de columnas 01_schema vs SCRIPTS_VIGENTES (L6 test 1)

COVERAGE: 2/30 paths cubiertos (7%) - los 2 son heredados de vistas existentes
GAPS: 28  |  [->E2E]: 3 (deep link anonimo, NavBar x4 roles, publicar->ver)
```

Los 28 GAPs se convierten en requisitos de test en las obligaciones E-T
abajo. **Regla de regresión (IRON RULE):** el cambio de `/` (C16) y el gate
de auth en `GET /torneos/{id}` (C2) modifican comportamiento existente que
hoy no está cubierto — sus tests de regresión entran como requisito crítico,
sin preguntar.

### Test Plan Artifact
Escrito a `~/.gstack/projects/Score-App/Gabo-main-eng-review-test-plan-20260915-003100.md`.

## Sección 4 — Performance Review

- **L2 (el hallazgo caro):** `idx_partidos_fecha` existe, pero
  `DATE(Fecha_Partido) = :fecha` **no puede usarlo** — la expresión no
  coincide con la clave. El plan daba el tema por cerrado porque el índice
  existe. Se obliga el rango semiabierto.
- **Pushdown a través del `GROUP BY`:** sí ocurre — `p.Fecha_Partido` es
  columna de agrupación y el qual no es volátil. El riesgo real era el
  predicado, no el pushdown.
- **S3:** endpoint público sin auth ni rate limit, con `GROUP BY` sobre el
  histórico de eventos y hasta 15 días de ventana si el fallback se activa
  (F5 proponía `le=30`, que multiplica por 4 el peor caso sin que nadie lo
  pida). Se acota a 7 y se cachea 60s — gratis, porque el feed no tiene
  auto-refresh (C14).
- **N+1:** ninguno.

## Obligaciones aceptadas — Fase ENG

<!-- autoplan-accepted:eng -->
- **E-B1 — La migración `31_` no puede depender de `unaccent`.** Verificado: `grep -rn "CREATE EXTENSION|unaccent" database/` devuelve **cero hits** — la extensión no está instalada ni declarada en ningún script, así que el backfill de slug de F3 haría fallar `31_` con `function unaccent(text) does not exist` en cualquier base limpia, incluida la que arma `test_scripts_sql.py`. Se reemplaza por `translate()` sobre el mapa de acentos del español: SQL puro, `IMMUTABLE` (a diferencia de `unaccent`, lo que además deja la puerta abierta a un índice de expresión o a una columna generada), y suficiente para un catálogo fijo de 28 filas. No se agrega la extensión: sumaría un requisito de privilegios en el entorno de deploy a cambio de nada.
- **E-B2 — El slug se genera para toda fila, no solo para el backfill.** F3 solo proponía un `UPDATE` en `31_`, pero `11_catalogo_disciplinas.sql` está en `SCRIPTS_VIGENTES`, es re-ejecutable, y es el único mecanismo real de alta (`routes/disciplinas.py` no tiene `POST`). Una disciplina agregada después de `31_` nacería con `Slug = NULL` y su deep link no resolvería, en silencio — y el `UNIQUE` no la atrapa porque acepta múltiples NULL. Se agrega un trigger `BEFORE INSERT OR UPDATE OF Nombre` en `06_triggers.sql` (mismo patrón que `fn_validar_torneo_modalidad`), el backfill de `31_` queda solo para las filas preexistentes, y `Slug` pasa a `NOT NULL` después del backfill. **Ojo con M7:** el trigger genera el slug en `INSERT`, y en `UPDATE` solo si `Slug IS NULL` — si no, un rename vía `PATCH /disciplinas/{id}` cambiaría el slug y rompería links ya compartidos.
- **E-B3 — Las dos decisiones que el plan identificó y no tomó, tomadas.** C18 decía "decisión obligatoria antes de implementar... silencio no es una respuesta" y después el plan calló; C17 decía "no queda a criterio del implementador" y T3.4b la re-delegó en una referencia circular. Se resuelven acá: **(a) `Publicado` filtra también donde los torneos son enumerables.** Con solo el detalle gateado, un anónimo igual obtiene el borrador completo por `GET /torneos` (`torneos.py:14`), `GET /partidos?torneo_id=` (`partidos.py:56`), `GET /torneos/{id}/bracket` y `GET /estadisticas/proximos-partidos` (cuya vista proyecta `t.Nombre AS Torneo`, `04_views.sql:50`). Gatear el detalle y dejar la lista abierta es el peor de los dos mundos: agrega auth a 4 rutas y no cierra nada. Se agrega el predicado `Publicado` para caller anónimo en `TorneoRepository.list` (junto a `incluir_archivados`, mismo lugar), en `PartidoRepository.list`, y en `vw_proximos_partidos`. **(b) C17 se resuelve por la opción (b):** la superficie de partido queda pública pase lo que pase, y la query de resultados tolera el 404 con el copy explícito de D7. La opción (a) rompería links ya compartidos y toca más superficie.
- **E-L1 — El feed no puede perder la final el día de la final.** `chk_torneo_estado` admite `'Activo'`, `'Inactivo'` y `'Finalizado'` (`02_constraints.sql:50`). El `WHERE TORNEO.Estado = 'Activo'` de T3.2 hace que, el día que el admin marca el torneo como `Finalizado` —típicamente el día de la final—, ese partido desaparezca del feed de hoy, del "ayer" de mañana y de toda la ventana de fallback. El predicado pasa a `TORNEO.Estado <> 'Inactivo'`. Test obligatorio: torneo `Finalizado` con partido hoy → aparece.
- **E-L2 — El predicado de fecha tiene que ser sargable.** `idx_partidos_fecha` está sobre el `TIMESTAMP` (`03_indexes.sql:82`), así que la forma natural de escribir "los partidos del día" (`DATE(Fecha_Partido) = :fecha` o `Fecha_Partido::date = :fecha`) **no puede usarlo**: la expresión no coincide con la clave. C11 dio el tema por cerrado porque el índice existe; el problema era cómo se escribe el predicado. Se obliga el rango semiabierto: `p.Fecha_Partido >= :fecha AND p.Fecha_Partido < :fecha + INTERVAL '1 day'`. Y el criterio binario de F15 se reescribe en función de esto, que sí es evaluable: el `EXPLAIN (ANALYZE, BUFFERS)` debe mostrar `Index Scan using idx_partidos_fecha`; un `Seq Scan on partidos` dispara el plan B. (Nota a favor del plan: el pushdown a través del `GROUP BY` de `vw_resultados_partidos` sí ocurre — `Fecha_Partido` es columna de agrupación y el qual no es volátil.)
- **E-L3 — Los 5 JOIN de `vw_feed_partidos`, enumerados, y los `Estado` nullable, contemplados.** `vw_resultados_partidos` proyecta solo `el.ID`, `el.Nombre`, `ev_eq.ID`, `ev_eq.Nombre` de `EQUIPOS` (`04_views.sql:169-201`): no expone `Estado` ni expondrá `Logo_URL`. T3.2 pedía filtrar por `EQUIPOS.Estado` y traer los logos sin enumerar que eso son **dos JOIN más a EQUIPOS**. Se escriben los 5 explícitos: TORNEO, TORNEO_GRUPO, DISCIPLINA y EQUIPOS ×2 (sobre `Equipo_Local_ID` y `Equipo_Visitante_ID`). Y como `EQUIPOS.Estado`, `TORNEO.Estado` y `DISCIPLINA.Estado` son todos nullable (`VARCHAR(20) DEFAULT 'Activo'` sin `NOT NULL`, y el `CHECK ... IN (...)` deja pasar `NULL` por lógica de tres valores), todos los filtros de estado usan `IS DISTINCT FROM 'Inactivo'` y no `= 'Activo'`, que descartaría filas en silencio.
- **E-L4/E-M3 — La barra de deportes tiene su propio endpoint; el sidecar se elimina.** Tres problemas se cierran con un solo cambio. (1) **L4:** con el sidecar sobre `fecha_pedida` (F4), un feriado sin partidos daba sidecar vacío → la barra no se renderiza (regla de C8) mientras el fallback muestra dos deportes llenos: un feed con contenido y sin control para cambiar de deporte, justo el día en que más hace falta. (2) **F18/M3:** la barra vive en `NavBar`, que se renderiza en toda ruta, y leer solo la caché la deja invisible en el deep link desde WhatsApp — que es el canal que C4/C6 declaran principal. (3) **F4:** la circularidad sidecar↔`fecha_efectiva`. Se resuelve con `GET /api/v1/disciplinas/con-partidos?fecha=&ventana_fallback_dias=`: endpoint propio y barato, que aplica la misma ventana de fallback **sin filtro de disciplina**, así que nunca está vacío mientras el feed tenga contenido. `disciplinas_con_partidos` sale del envelope del feed: una sola fuente, sin circularidad posible. **La barra se queda en el header global junto a la marca, como se pidió** — lo que cambia es de dónde se alimenta, no dónde vive.
- **E-L5 — El corte por bloque nunca devuelve cero partidos.** T3.3 manda cortar en borde de torneo; si el primer bloque tiene más partidos que `limit` (una liga de fin de semana con 30 partidos y `limit=20`), la regla devuelve `partidos: []` con `truncado: true` y `total_disponible: 250`: un feed vacío con un pie que dice "mostrando los primeros 0 de 250", y el botón de D4 topado en 200. Regla explícita: **siempre se devuelve al menos el primer bloque completo, aunque exceda `limit`** — `limit` es un mínimo redondeado hacia arriba al borde de bloque, no un máximo. El `N` del copy de D4 es lo realmente devuelto, no el `limit` pedido. Y hay que presupuestarlo: esto no es un `LIMIT` de SQL, es `dense_rank() OVER (ORDER BY torneo_grupo.Nombre, torneo.ID)` + `COUNT(*) OVER ()` con el recorte sobre el rank — medio día de trabajo que T3.3 presentaba como un bullet.
- **E-L6 — F10 son dos tests, no uno.** Verificado: `conftest.py` arma la base con `SQL_FILES = 01..06` y `test_scripts_sql.py` construye la suya igual y corre `SCRIPTS_VIGENTES` encima. El test de delta de columnas **sí** atrapa olvidar `01_schema.sql`, pero **no** atrapa olvidar agregar `31_` a `SCRIPTS_VIGENTES`: el archivo no se abre nunca, el delta da 0 y todo queda verde — y ese es el modo de falla más silencioso de los tres. Hacen falta dos: (1) el de delta, con el mensaje que nombre el archivo; (2) uno de cobertura de directorio — `set(glob("database/*.sql"))` menos `SQL_FILES` menos una lista explícita `SCRIPTS_HISTORICOS` debe ser igual a `SCRIPTS_VIGENTES`, fallando con "agregá `31_...sql` a SCRIPTS_VIGENTES o a SCRIPTS_HISTORICOS". El docstring de ese archivo ya explica en prosa por qué 07/08/09/12/13 quedan afuera; solo falta convertir esa prosa en una lista que el test lea.
- **E-S1 — Decir en voz alta cuál es la frontera.** `Publicado` gatea anónimo contra autenticado, **no** dueño contra el resto: un `Arbitro` cualquiera o un `TorneoAdmin` de otro torneo ve el borrador completo de un torneo ajeno. El blast radius es chico porque no hay self-registration (`routes/auth.py` solo expone `POST /login` y `GET /me`; las cuentas las crea AdminGeneral), y el repo ya tiene `require_torneo_access` si algún día hace falta endurecerlo. No se endurece en esta entrega, pero **queda escrito en el plan**: si no, el próximo que agregue datos sensibles al torneo va a asumir lo contrario.
- **E-S2 — `Logo_URL` se neutraliza también en lectura.** C10d validaba solo en escritura y razonaba el riesgo como XSS; un `<img src="javascript:...">` no ejecuta en ningún navegador moderno, así que el vector real es otro: una URL de tercero en una página pública filtra la IP y el `Referer` de cada visitante anónimo al host que el admin pegó, y un `http://` rompe la página por mixed-content. Validar solo en `EquipoUpdate`/`TorneoGrupoUpdate` además deja pasar todo lo que entre por SQL directo o por el seed de F1. Se agrega: filtro en la vista/serializer (`CASE WHEN Logo_URL LIKE 'https://%' THEN Logo_URL ELSE NULL END`), de modo que el fallback a iniciales cubra el dato sucio preexistente, y `referrerpolicy="no-referrer"` en los `<img>` de logos.
- **E-S3 — El endpoint público no se deja sin techo.** `/partidos/feed` es público, sin auth, sin rate limit (el repo solo lo tiene para login, `22_migracion_rate_limiting_login.sql`), corre un `GROUP BY` sobre el histórico de eventos por request, y C6/F13 le agregan una línea de log por hit sin retención definida — un bucle de requests satura CPU y llena el disco. Tres mitigaciones baratas: (a) caché en proceso por `(fecha, disciplina_id, limit)` con TTL 60s — el feed no tiene auto-refresh (C14), así que esa frescura es gratis y hace irrelevante el costo por request; (b) `ventana_fallback_dias` se acota a `le=7`, no a `le=30` como proponía F5 (30 multiplica por 4 el peor caso sin que ningún consumidor lo pida); (c) el log se emite solo cuando `fecha_efectiva != fecha_pedida`, y el resto se cuenta en memoria.
- **E-M1 — Un solo reloj.** C15 dice "la fecha es la del servidor", pero hay dos: el proceso Python (`date.today()`, con el `TZ` del contenedor de la app) y Postgres (`CURRENT_DATE`, con el `TimeZone` de la sesión). Pueden diferir en un día durante 3-5 horas cada noche. El default de `fecha` se resuelve **en Postgres, en la misma query**, y se documenta.
- **E-M2 — Un torneo nuevo no nace publicado.** `DEFAULT TRUE` es correcto para el backfill (no cambia el comportamiento existente), pero el mismo default aplica a los torneos nuevos: un torneo se publicaría en el instante en que el admin lo crea, con cero equipos y cero partidos — exactamente la primera impresión que D8c quiere evitar. La migración hace `ADD COLUMN DEFAULT TRUE` → `UPDATE` (backfill) → `ALTER COLUMN SET DEFAULT FALSE`. Las filas viejas siguen públicas; las nuevas se publican a propósito.
- **E-M4 — Commitear `schema.d.ts` antes de tocar `verificar.ps1`.** `git status` ya muestra `frontend/src/api/schema.d.ts` modificado, así que el `git diff --exit-code` que F16 agrega daría rojo en su primera corrida por un cambio anterior a este plan. Se commitea primero.
- **E-M5 — El movimiento de archivos va en su propio commit.** T2.1 mueve `FiltroDisciplinasBar.tsx` + `iconosDisciplina.ts` y toca `TorneosAdmin.tsx`, `EquiposAdmin.tsx` y demás consumidores. Mezclado con la feature, un revert de R3 arrastra el refactor. Commit separado, primero, sin ningún cambio de comportamiento ("make the change easy, then make the easy change").
- **E-M6 — El desempate del orden es contrato, no detalle.** `TORNEO_GRUPO.Nombre` es `VARCHAR(100) NOT NULL` sin `UNIQUE`, así que dos grupos homónimos se intercalan alfabéticamente y `torneo.ID` los desempata. El orden sigue siendo determinista y los bloques contiguos por `torneo_id` (el agrupamiento de T4.4 no se rompe), pero el desempate por `torneo.ID` queda anotado como parte del contrato del endpoint, con su test.
- **E-T — Los 11 tests que faltaban.** Además de lo que ya pedían T3.6 y T4.7: (1) corte en borde con un bloque mayor que `limit` (E-L5); (2) `ventana_fallback_dias=0` devuelve vacío y `=7` devuelve `fecha_efectiva` distinta — F5 introdujo el parámetro y nadie lo testeaba; (3) el endpoint de disciplinas sigue trayendo contenido cuando el día pedido está vacío y el fallback se activó (E-L4); (4) torneo `Finalizado` con partido hoy → aparece (E-L1); (5) fila con `Estado IS NULL` en EQUIPOS/TORNEO/DISCIPLINA → aparece (E-L3); (6) `31_` está en `SCRIPTS_VIGENTES` (E-L6 test 2); (7) `logo_url` con `http://`, `javascript:` y `data:` → rechazado en escritura con el `codigo` de F9 y neutralizado en lectura (E-S2); (8) NavBar por los 4 roles (anónimo, Arbitro, TorneoAdmin, AdminGeneral), incluido el link "Portal público" de D6; (9) `/dashboard` tipeado por un anónimo — verificado que hoy es alcanzable (`App.tsx:48` no tiene `RequireRole`), así que la decisión de F20 necesita su test; (10) frontera exacta del fallback: partido a `hoy-7d` incluido, a `hoy-8d` excluido; (11) orden determinista con dos grupos homónimos (E-M6). **Regla de regresión (sin preguntar):** el cambio de `/` (C16) y el gate de auth sobre `GET /torneos/{id}` (C2) modifican comportamiento existente hoy sin cobertura — sus tests de regresión entran como requisito crítico.
- **E-G1 — Orden de deportes: gana el del usuario (Final Gate, D2).** Supersede la decisión abierta D-A. El ranking pasa a **Fútbol=1, Tenis=2, Baloncesto=3**, y el resto de las 28 disciplinas se corre una posición. Se aplica como `UPDATE` idempotente dentro de `31_migracion_portal_publico.sql`, con el mismo patrón de match por `Nombre` que ya usa `15_migracion_popularidad_disciplinas.sql`. No hay código que tocar: `DisciplinaRepository.list` ya ordena por `orden_popularidad NULLS LAST`. Se descartó dejar el ranking previo y también ordenar dinámicamente por cantidad de partidos.
- **E-G2 — Control de Mesa: gate de rol, no eliminación (Final Gate, D3).** Confirma C7 contra la lectura literal del requerimiento original. El `NavLink` se condiciona a TorneoAdmin, AdminGeneral y Arbitro — hoy no tiene ningún gate, así que hasta un anónimo lo ve, que es exactamente lo que se pedía cerrar. Se descartó eliminarlo del todo (dejaba huérfana la lista `/control-de-mesa`: el botón de `PartidosDelTorneo.tsx:184` va a `/partidos/:id`, no a mesa) y moverlo a una pestaña de `TorneoAdminLayout` (alcanzado a UN torneo, mientras que la lista no lo está). Se mantiene el botón "Gestionar en Mesa" por fila.
- **E-G3 — El feed abre en la próxima jornada con partidos (Final Gate, D4).** **Supersede C1 y reformula D3**, y va contra la recomendación de esta revisión: el usuario eligió la opción B sobre la conservadora. `GET /partidos/feed` sin `fecha` resuelve directo a la fecha más cercana con partidos publicados para esa disciplina (atrás primero, después adelante, acotado a ±7 días; fuera de la ventana, vacío real). Ya no existe el estado "hoy vacío + cartel de disculpa" como camino principal. **Dos consecuencias obligatorias:** (a) la cabecera del feed **siempre** rotula la fecha real que muestra, nunca "Hoy" a secas — sin eso, un martes mostraría el domingo pasado como si fuera actual, y la distinción En curso / Finalizado de D2 pierde sentido; (b) el selector de D3 deja de ser tres pills fijas hoy/ayer/mañana (mentirían: "Hoy" activo sobre el domingo pasado) y pasa a ser una tira de fechas reales donde la seleccionada **es** `fecha_efectiva`. El fallback sigue aplicando solo a la resolución inicial: navegar explícitamente a una fecha no cae a otra. Razón del usuario, aceptada: los torneos amateur juegan fin de semana, y una portada que dice "no hay partidos" de lunes a jueves era el escenario de 6 meses que la revisión CEO marcó como el mayor riesgo del plan.
<!-- /autoplan-accepted:eng -->

## Failure Modes Registry (final)

```
  CODEPATH                  | FAILURE MODE                  | RESCUED? | TEST? | USER SEES        | LOGGED?
  --------------------------|-------------------------------|----------|-------|------------------|--------
  Migracion 31_             | unaccent no existe            | Y (E-B1) | Y     | deploy falla     | Y
  Migracion 31_             | falta en SCRIPTS_VIGENTES     | Y (E-L6) | Y     | test con nombre  | Y
  DISCIPLINA nueva          | Slug NULL, deep link muerto   | Y (E-B2) | Y     | no aparece       | N
  vw_feed_partidos          | torneo Finalizado desaparece  | Y (E-L1) | Y     | (ya no pasa)     | N
  vw_feed_partidos          | Estado IS NULL descarta fila  | Y (E-L3) | Y     | (ya no pasa)     | N
  GET /partidos/feed        | Seq Scan sobre el historico   | Y (E-L2) | Y     | lento            | Y
  GET /partidos/feed        | bloque > limit -> feed vacio  | Y (E-L5) | Y     | (ya no pasa)     | N
  GET /partidos/feed        | bucle de requests anonimos    | Y (E-S3) | N     | lento            | Y
  GET /torneos (lista)      | enumera torneos borrador      | Y (E-B3) | Y     | no aparece       | N
  GET /disciplinas/con-part.| vacio con feed lleno          | Y (E-L4) | Y     | (ya no pasa)     | N
  Logo_URL de tercero       | fuga de IP/Referer del visitante | Y (E-S2) | Y  | iniciales        | N
  Torneo recien creado      | publicado con 0 equipos       | Y (E-M2) | Y     | no aparece       | N
  Default de fecha          | PG y Python difieren un dia   | Y (E-M1) | Y     | (ya no pasa)     | N
  --------------------------|-------------------------------|----------|-------|------------------|--------
  CRITICAL GAPS: 0 (todo lo que era RESCUED=N quedo cerrado; E-S3 sin test
  automatico es riesgo aceptado y anotado, no un fallo silencioso)
```

## Worktree parallelization strategy

| Step | Módulos tocados | Depende de |
|---|---|---|
| S1 Migración + trigger + vista | `database/` | — |
| S2 Guards de auth + endpoints | `backend/app/api/`, `backend/app/repositories/` | S1 |
| S3 Refactor de componentes (E-M5) | `frontend/src/components/`, `frontend/src/pages/torneo-admin/` | — |
| S4 Portal público | `frontend/src/pages/publico/`, `frontend/src/components/publico/` | S2, S3 |
| S5 Back-office (formularios, toggle) | `frontend/src/pages/torneo-admin/` | S2 |

```
Lane A: S1 -> S2 (secuencial, el endpoint necesita la vista)
Lane B: S3 (independiente, solo mueve archivos)
Lane C: S4 -> (espera A y B)
Lane D: S5 -> (espera A)

Orden: A y B en paralelo. Merge. Despues C y D en paralelo.
CONFLICTO: S3 y S5 tocan ambos frontend/src/pages/torneo-admin/ -> NO
correrlos en paralelo. S3 va primero y solo, por E-M5.
```

## PLAN ENG REVIEW — COMPLETION SUMMARY

```
  +====================================================================+
  |            ENG PLAN REVIEW — COMPLETION SUMMARY                    |
  +====================================================================+
  | Scope challenge      | Complexity check DISPARA (22 archivos);     |
  |                      | sin reducir (P2), 1 simplificacion neta     |
  | Section 1 (Arch)     | 3 issues (L3, B3, M3) + diagrama producido  |
  | Section 2 (Quality)  | 3 issues (L5, M5, error discriminator)      |
  | Section 3 (Tests)    | Diagrama producido, 28 GAPs, 2 regresiones  |
  | Section 4 (Perf)     | 2 issues (L2 sargabilidad, S3 sin techo)    |
  +--------------------------------------------------------------------+
  | Bloqueantes          | 3 (B1, B2, B3) - los 3 cerrados             |
  | Defectos de logica   | 6 (L1-L6) - los 6 cerrados                  |
  | Seguridad            | 3 (S1-S3) - cerrados; S1 documentado        |
  | Menores              | 7 (M1-M7) - cerrados                        |
  | NOT in scope         | written (heredado + 6 diferidos)            |
  | What already exists  | written                                     |
  | Test plan artifact   | escrito a ~/.gstack/projects/Score-App/     |
  | Failure modes        | 13 total, 0 CRITICAL GAPS                   |
  | Diagramas producidos | 3 (dependencias, cobertura, lanes)          |
  | Diagramas obsoletos  | 0                                           |
  | Outside voice        | codex: unavailable (CLI no instalado)       |
  | Unresolved decisions | 0 en esta fase                              |
  +====================================================================+
```

### Unresolved Decisions (Eng)
Ninguna. B3 tomó las dos decisiones que el plan había identificado y dejado
abiertas. Las 3 que viajan al Final Gate vienen de fases anteriores y son
cambios a la dirección declarada por el usuario, no huecos de ingeniería.

---

## Temas cruzados entre fases

Concerns que aparecieron en 2+ fases de forma independiente. Señal de alta
confianza: dos revisores con contexto fresco y sin verse llegaron al mismo
lugar.

- **Tema: el contrato del feed estaba a medio definir.** Flagueado en DX (F3
  slug inexistente, F5 fallback no expresable, F7 `truncado` sin
  `total_disponible`) y en Eng (L5 el corte por bloque puede devolver cero
  filas, L4 el sidecar se apaga cuando más hace falta). Dos fases distintas
  atacaron el mismo envelope y encontraron huecos distintos. Resultado: el
  endpoint se rediseñó dos veces y terminó partido en dos
  (`/partidos/feed` + `/disciplinas/con-partidos`).
- **Tema: el plan afirmaba cosas del repo que no eran.** CEO se corrigió a sí
  mismo vía spec review (el índice ya existía, los shells de bracket ya
  estaban excluidos, `Publicado` no tenía mecanismo), y Eng encontró tres más
  del mismo tipo (`unaccent` no existe, `Finalizado` es un estado válido,
  `Estado` es nullable). El patrón: el plan verificaba **que algo existía**
  pero no **qué valores admitía**.
- **Tema: puertas de entrada que nadie abrió.** CEO (C6: la vista pública de
  R1 no tiene cómo llegarse), Design (D6: el feed no tiene entrada para
  usuarios con sesión) y Eng (M3: la barra no se renderiza en el deep link,
  que es el canal declarado) encontraron la misma clase de fallo en tres
  superficies distintas: se construye la página y no el camino hacia ella.
- **Tema: decisiones declaradas obligatorias y después no tomadas.** CEO
  escribió "decisión obligatoria antes de implementar... silencio no es una
  respuesta" (C18) y "no queda a criterio del implementador" (C17), y ninguna
  de las dos se tomó hasta que Eng las forzó (E-B3). DX lo vio desde otro
  ángulo (F2: el documento se contradice leído en orden).

## Decision Audit Trail — fases Design, DX y Eng

Las 17 filas de arriba cubren la fase CEO. Las otras tres fases registraron
sus decisiones como obligaciones con su razón; resumen de clasificación:

| Fase | Auto-decididas (Mechanical) | Taste (al gate) | Diferidas |
|---|---|---|---|
| Design | 15 (D1, D2, D4-D11, D13-D17) | 2 (D3 selector vs fallback, D12 forma de la URL) | 0 |
| DX | 17 (F1-F7, F9-F18, F20) | 0 | 2 (F8 tz, F19a flag de barra) |
| Eng | 18 (E-B1/B2/B3, E-L1..L6, E-S1..S3, E-M1/M2/M4/M5/M6/M7, E-T) | 0 | 0 |

Ninguna de las de Design/DX/Eng contradice la dirección declarada por el
usuario, así que ninguna viaja al gate como User Challenge. Las 3 que sí
viajan vienen de CEO.

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` (via /autoplan) | Scope & strategy | 1 | issues_open | 10 propuestas, 4 aceptadas, 4 diferidas, 1 descartada; 2 decisiones al gate |
| Outside Review | codex — no invocado (CLI ausente) | Independent 2nd opinion | 0 | unavailable | sin cobertura externa en ninguna fase |
| Eng Review | `/plan-eng-review` (via /autoplan) | Architecture & tests (required) | 1 | clean | 19 issues, 0 critical gaps (3 bloqueantes cerrados) |
| Design Review | `/plan-design-review` (via /autoplan) | UI/UX gaps | 1 | clean | score: 4/10 → 8/10, 17 decisiones |
| DX Review | `/plan-devex-review` (via /autoplan) | Developer experience gaps | 1 | clean | score: 2/10 → 7/10, TTHW: indefinido → ~3 min |

- **OUTSIDE COVERAGE:** codex — `unavailable` en las 4 fases (ceo, design, dx, eng). El binario no está instalado (`command -v codex` → not found), así que **ninguna fase tuvo lectura de un modelo externo**. Las 4 corrieron con subagente Claude (contexto fresco, mismo harness; identidad de modelo desconocida). Los 6 hallazgos marcados single-voice (CEO C1/C2, DX F1/F3/F5, Eng B1/B2/B3) no tienen confirmación cruzada. Para habilitarla: `npm install -g @openai/codex`.
- **CROSS-MODEL:** no aplica — no hubo pase externo completado, así que no hay solapamiento que analizar. Las tablas de consenso de las 4 fases quedan en N/A, nunca CONFIRMED.
- **VERDICT:** CEO + DESIGN + DX + ENG CLEARED — listo para implementar. Las 3 decisiones abiertas se resolvieron con el usuario en el Final Gate (D2 orden de deportes, D3 gate de rol en Control de Mesa, D4 el feed abre en la próxima jornada con partidos).

NO UNRESOLVED DECISIONS
