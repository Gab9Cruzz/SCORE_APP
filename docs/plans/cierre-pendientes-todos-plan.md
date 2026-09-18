<!-- /autoplan restore point: "C:\\Users\\Gabo\\.gstack\\projects\\Score-App\\main-autoplan-restore-20260918-110924.md" -->
<!-- /autoplan restore point: "C:\\Users\\Gabo\\.gstack\\projects\\Score-App\\main-autoplan-restore-20260917-161003.md" -->
# Cierre de los pendientes abiertos de TODOS.md

## Implementation plan

### Contexto y alcance

`TODOS.md` (141 líneas, reescrito el 2026-09-17) tiene cinco secciones. Este
plan cierra **una sola**: `## Pendiente — ya evaluado, falta ejecutar`, que
tiene **9 ítems**. Las otras cuatro quedan fuera a propósito:

- `## Bloqueado` (1 ítem: notificación por correo al jugador) — **pospuesto
  explícitamente por el usuario el 2026-09-17** hasta que el resto del
  proyecto esté más afinado. Necesita elegir proveedor de correo, que es una
  decisión de infraestructura, no de código.
- `## Resuelto (2026-09-17)` — ya hecho.
- `## Backlog sin urgencia` (17 ítems) — el propio archivo dice "evaluado,
  nadie lo pidió todavía".
- `## Descartado a propósito` (11 ítems) — "no reabrir sin evidencia nueva".

**Baseline de trabajo:** el árbol de trabajo tiene el motor
`ReglamentoTorneo` sin commitear (`backend/app/services/reglamento_torneo.py`,
`backend/tests/test_reglamento_torneo.py` untracked, más
`convocado_a_partido.py` / `hito_partido.py` / `partido.py` / `torneo.py` /
`MesaPanel.tsx` / `TODOS.md` modificados). Ese trabajo está marcado como
Resuelto en TODOS.md y con 520 tests en verde. **Se commitea antes de empezar
la Fase 1** — ninguna fase de este plan se construye sobre un árbol sucio de
otra feature.

Suite actual: 486 funciones `def test_` en `backend/tests/` (52 archivos,
~520 casos con parametrize), 37 archivos de test en el frontend.

---

### Track A — Integridad de concurrencia en el camino en vivo

Backend puro, sin cambio de contrato de API ni de esquema. Es el track más
barato y el que tapa riesgo real de datos, así que va primero.

#### Fase A1 — Row-locking en `EventoPartidoService.create` (ítem 7)

Hoy `backend/app/services/evento_partido.py:76` hace
`await self.partido_repo.get_or_404(data.partidos_id)`, lee `partido.estado`
una vez en `_verificar_partido_en_curso`, y después encadena varios `flush()`
antes del `commit()` final sin ningún lock. Dos requests concurrentes
(doble-tap antes de que React re-renderice `isPending`, o dos pestañas del
mismo árbitro) pasan ambos el guard y ambos insertan el evento. El caso que
importa es **dos tarjetas simultáneas del mismo jugador**: cada request cuenta
las amarillas previas por su lado en `procesar_doble_amarilla`
(`backend/app/services/reglas_tarjetas.py:46-53`, `if len(amarillas) < 2`),
ve 1, y ninguno dispara la roja automática — el jugador queda con 2 amarillas
y sin expulsión.

**El helper ya existe.** `PartidoRepository.get_or_404_bloqueado`
(`backend/app/repositories/partido.py:16-30`) hace
`session.get(model, id_, with_for_update=True)` y hoy lo consume un solo
llamador: `PartidoService.registrar_resultado_directo`
(`backend/app/services/partido.py:198`). El lock se libera en el
`commit()`/rollback que el método ya tiene, sin reestructurar la transacción.

Cambio:

- `backend/app/services/evento_partido.py:76` — `get_or_404` →
  `get_or_404_bloqueado`. Comentario que nombre el caso de la doble amarilla,
  con el mismo formato que el docstring del helper.
- **No** se toca `corregir_minuto` ni `anular`: esos operan sobre un evento ya
  existente por su propio ID, no sobre el estado compartido del partido, y
  EC-15 permite corregir un partido 'Finalizado' a propósito.

Tests: `backend/tests/test_eventos_partido.py` (o el archivo que cubra este
camino) — un test secuencial que confirme que el camino feliz no se rompe. El
test de concurrencia real de este lock va en la Fase A3, que es la que aporta
la infraestructura.

#### Fase A2 — Infraestructura de test de concurrencia real (habilitador del ítem 4)

`backend/tests/conftest.py` envuelve cada test en una transacción con
savepoints (`join_transaction_mode="create_savepoint"`) que se revierte al
final, así que un `session.commit()` dentro de un repositorio **no persiste de
verdad**. Con eso es imposible escribir un test de 2 conexiones genuinamente
paralelas: la segunda conexión no ve nada de lo que escribió la primera. Esto
es exactamente la "infraestructura de test que el repo no tiene todavía" que
menciona TODOS.md, y es la razón por la que T23/T24 quedaron cubiertos solo en
el caso secuencial.

Nueva fixture en `conftest.py`, al lado de las existentes (no reemplaza
ninguna):

- `sesiones_paralelas` — fixture que entrega **dos `AsyncSession`
  independientes**, cada una con su propia conexión al pool, **sin** el
  savepoint envolvente, es decir con `commit()` real contra
  `torneos_mvp_test`.
- Limpieza explícita: como los commits son reales, la fixture registra qué
  filas creó y hace `TRUNCATE ... CASCADE` (o un `DELETE` acotado por las
  tablas tocadas) en el teardown. **No** se apoya en el rollback de la
  fixture normal, porque acá no hay rollback que la salve.
- Marker `@pytest.mark.concurrencia` para poder excluirla
  (`pytest -m "not concurrencia"`) — estos tests son más lentos y no son
  herméticos del mismo modo que el resto.
- Recordatorio de plataforma: `conftest.py:13-21` ya fija
  `WindowsSelectorEventLoopPolicy` antes de que pytest-asyncio cree el primer
  loop (psycopg async se niega a correr sobre ProactorEventLoop). La fixture
  nueva vive en el mismo archivo, así que hereda eso; no hay que repetirlo.

**Riesgo conocido:** si las dos sesiones toman el lock en orden cruzado, el
test puede quedarse colgado en vez de fallar. Cada test de este marker lleva
un `asyncio.wait_for(..., timeout=N)` explícito, así un deadlock sale como
fallo con mensaje, no como una corrida colgada.

#### Fase A3 — Tests de concurrencia real T23/T24 + el lock de A1 (ítem 4)

Sobre la fixture de A2, tres tests:

1. **Tope de titulares (T23)** — dos sesiones convocan al titular N+1 a la
   vez contra la misma fila. Uno tiene que ganar, el otro tiene que fallar con
   el error de dominio de máximo de titulares. Ojo: la resolución del máximo
   ahora pasa por `ReglamentoTorneo.validar_maximo_titulares`
   (`backend/app/services/reglamento_torneo.py`, el trabajo del baseline), así
   que el test valida el camino real post-unificación, no el viejo.
2. **Doble `Fin_Partido` (T24)** — dos sesiones cierran el mismo partido a la
   vez. `backend/tests/test_fin_forzado.py:7` ya documenta T23/T24 como
   cubiertos en secuencial; este test es el par concurrente, y va **al lado**
   de los existentes, no los reemplaza.
3. **Doble tarjeta amarilla del mismo jugador** — el caso que A1 arregla. Sin
   el lock este test falla (0 rojas automáticas donde debería haber 1); con el
   lock pasa. Es la prueba de que A1 hace algo.

---

### Track B — Alcance de datos por asignación y observabilidad de licencias

#### Fase B1 — Filtrar por asignación los listados de sub-recursos (ítem 8, P3)

Estado real hoy: el patrón `torneo_ids_permitidos` ya existe y funciona en
**dos** recursos —

- `backend/app/api/routes/torneos.py:47-55` → `TorneoService.list`
  (`services/torneo.py:66-89`) → `TorneoRepository.list`
  (`repositories/torneo.py:51-80`)
- `backend/app/api/routes/partidos.py:136-145` → `PartidoService.list`
  (`services/partido.py:58-79`) → `PartidoRepository.list`
  (`repositories/partido.py:37-67`)

En ambos, `None` = sin restricción y `[]` = lista vacía (no "todo"), que es la
parte fácil de arruinar.

**Los partidos ya están cubiertos.** Lo que falta son `equipos` y `jugadores`,
y ahí hay un problema de modelo que TODOS.md no nombra: **un equipo y un
jugador no pertenecen a un torneo.** Pertenecen a una disciplina, y se
relacionan con un torneo a través de `INSCRIPCION_TORNEO`. No hay una columna
`torneo_id` en `EQUIPOS` ni en `JUGADORES` que filtrar. Filtrar "por
asignación" significa por fuerza un `EXISTS` contra las inscripciones de los
torneos asignados, y trae dos preguntas de producto que hay que contestar
antes de escribir el filtro:

- Un equipo de la disciplina que **todavía no** está inscrito en ningún torneo
  asignado: ¿el TorneoAdmin lo ve? Si no lo ve, no puede inscribirlo, y el
  flujo de inscripción se rompe.
- Un jugador libre (sin equipo): mismo problema, agravado, porque el alta de
  jugador y el buscador (`GET /jugadores?q=`) son el camino de entrada de
  `SelectorJugadorBuscable` y del `ModalIndividual` de `DetalleEquipo`.

Resolución propuesta (a confirmar en la revisión CEO): **el filtro se aplica
solo a los listados de navegación/administración, nunca a los buscadores de
alta.** Concretamente:

- `GET /equipos` y `GET /jugadores` aceptan un parámetro explícito de alcance
  (por ejemplo `alcance=asignados|disciplina`), con default que **preserva el
  comportamiento actual**. Las páginas `EquiposAdmin.tsx` / `JugadoresAdmin.tsx`
  piden `asignados`; `SelectorJugadorBuscable.tsx` y el modal de
  `DetalleEquipo.tsx` siguen pidiendo el alcance amplio.
- Alternativa más simple si la revisión la prefiere: no tocar el listado y
  cerrar el ítem como "no aplica por modelo de datos", documentando por qué en
  TODOS.md. Es un resultado legítimo para un P3 cuya premisa no se sostiene.

Nueva capa de repositorio: `EquipoRepository.list` y `JugadorRepository.list`
ganan `torneo_ids_permitidos: Sequence[int] | None` con la misma semántica
`None`/`[]` que los otros dos, para que el patrón siga siendo uno y no tres.

Tests: los casos de los otros dos recursos ya existen y sirven de molde —
`None` ve todo, `[]` ve nada, lista con IDs ve exactamente los de esos
torneos, y el buscador de alta **sigue viendo todo** (ese es el test que
protege el flujo de inscripción de la regresión).

#### Fase B2 — Métricas y alerta de revocación de licencia (ítem 9, P3)

Hoy la revocación queda solo en `AUDITORIA`.
`AsignacionTorneoAdminService.set_licencia`
(`backend/app/services/asignacion_torneo_admin.py`) muta `licencia_activa` por
ORM directo, precisamente para que el listener genérico de auditoría
(`backend/app/core/auditoria.py`) lo capture gratis — así que **los datos ya
están**; lo que falta es leerlos.

Lo que pide TODOS.md: contador de otorgadas/revocadas por día, y alerta de
pico de 403 post-revocación.

El repo ya tiene precedente de "métrica como consulta SQL versionada, no como
dashboard": `docs/queries/metricas-desempate-tiempo-extra-penales.sql`, que se
corrió a mano contra dev y cuyo resultado se registró en TODOS.md. Se sigue el
mismo camino, que es el proporcionado a un P3:

- `docs/queries/metricas-revocacion-licencia.sql` — otorgadas/revocadas por
  día desde `AUDITORIA` (filtrando `Tabla='USUARIOS'` y el campo
  `Licencia_Activa`), y el conteo de 403 por usuario en la ventana posterior a
  cada revocación, cruzando con `ACCESOS`
  (`backend/app/api/routes/accesos.py`, `repositories/acceso.py`).
- `database/README.md` o `docs/queries/README.md` — cómo correrla y qué
  umbral cuenta como "pico".
- **No** se construye página de dashboard ni alerta activa (mail/webhook) en
  esta fase. Una alerta activa necesita el mismo proveedor de correo que
  bloquea el ítem de `## Bloqueado`, y el usuario ya pospuso esa decisión el
  2026-09-17. Queda anotado en TODOS.md como la Fase 2 de este ítem,
  desbloqueada por la misma decisión de infraestructura.

Verificación: correr la consulta contra `torneos_mvp` (dev) y registrar el
resultado, incluido "no hay volumen suficiente" si es el caso — mismo criterio
con el que se cerró la Fase 3 del desempate.

---

### Track C — Deduplicación de UI (dos caminos vivos para lo mismo)

#### Fase C1 — `DetalleEquipo` / `ModalIndividual` al selector compartido (ítem 3)

`frontend/src/pages/torneo-admin/DetalleEquipo.tsx` (369 líneas) tiene su
propio modal de búsqueda inline (~líneas 182-360): `useDebouncedValue`,
`useQuery(["jugadores-buscar", textoDebounced])` contra
`GET /api/v1/jugadores`, alerta de conflicto de inscripción, y un "Crear
jugador nuevo" embebido. Eso es una reimplementación de
`frontend/src/components/admin/SelectorJugadorBuscable.tsx`, que hoy consume
un solo llamador: `TraspasosDelTorneo.tsx`.

Trabajo:

1. Leer los dos y listar las diferencias reales de comportamiento. La que ya
   se ve: `DetalleEquipo` tiene el paso de **confirmación de conflicto**
   (`⚠️ {nombre} ya está inscrito en {equipos}`, líneas 224-251) y el alta
   inline de jugador. Si `SelectorJugadorBuscable` no los soporta, o se le
   agregan como props opcionales, o el selector queda para la búsqueda y el
   conflicto/alta se quedan en `DetalleEquipo` alrededor. **La decisión se
   toma con los dos archivos leídos, no antes.**
2. Sumar el hook de resolución de nombres —
   `frontend/src/hooks/useEtiquetaJugadorPorPerfil.ts` y/o
   `useFetchFaltantes.ts`, según cuál sea el que TODOS.md llama "el hook de
   resolución de nombres"; se confirma leyéndolos.
3. Reemplazar el modal inline. Borrar el código muerto en el mismo commit —
   si el `ModalIndividual` viejo queda al lado del nuevo camino, el ítem no
   está cerrado, solo movido.
4. Mismo pase por `ModalAgregarInscripcion.tsx` y
   `ModalGestionarPlantilla.tsx` (`pages/torneo-admin/torneo-dashboard/`), que
   aparecen en la misma búsqueda y probablemente comparten el patrón. Si lo
   comparten entran acá (está en el radio de acción y es el mismo cambio); si
   no, se dice por qué no y se dejan.

Tests: `DetalleEquipo` no tiene archivo de test propio hoy (sí lo tienen
`EquiposAdmin`, `JugadoresAdmin`, `PerfilJugadorAdmin`). Se crea
`DetalleEquipo.test.tsx` cubriendo búsqueda, conflicto de inscripción y alta
inline **antes** de refactorizar, para que el refactor tenga red. Los tests de
`TraspasosDelTorneo.test.tsx` y `ResourceForm`/`ResourceTable` no deberían
moverse; si se mueven, el cambio en el selector compartido rompió a su
llamador original y hay que revisarlo.

#### Fase C2 — Retirar el formulario de Cambio duplicado de `CargaEvento` (ítem 5)

`frontend/src/components/MesaPanel.tsx` (1002 líneas) tiene **dos** caminos de
UI para registrar un Cambio:

- `ModalSustitucion` (`components/ModalSustitucion.tsx`, 71 líneas), abierto
  desde la alineación en vivo con el botón "Sacar" (MesaPanel:582-667). Es el
  camino nuevo.
- El `tipo === "Cambio"` dentro de `CargaEvento` (MesaPanel:809-1002, ramas en
  866-979: `disponiblesParaSalirCambio`, `sale`, `entra`). Es el camino viejo.

Ya comparten la heurística de elegibilidad en vez de duplicarla
(MesaPanel:554-560 lo dice explícitamente: "este componente calculaba su
propia elegibilidad de Cambio ... compartido que la alineación en vivo y
ModalSustitucion"). Lo que sigue vivo es el **segundo camino de UI**.

Trabajo:

1. Confirmar que `ModalSustitucion` cubre todo lo que cubre la rama de
   `CargaEvento`, **incluido `props.sinConvocatoria`** (MesaPanel:874) — un
   partido sin convocatoria guardada es el caso para el que existe la
   degradación con gracia de la decisión D4. Si `ModalSustitucion` no maneja
   ese caso, primero se le agrega; recién después se retira el camino viejo.
   Este es el orden que no se puede invertir.
2. Sacar `"Cambio"` de la grilla de tipos de `CargaEvento` y borrar las ramas
   866-979 que dependen de él, incluido `disponiblesParaSalirCambio` si no
   queda otro consumidor.
3. `MesaPanel.test.tsx` (208 líneas) con cuidado, como avisa TODOS.md: los
   tests que hoy cargan un Cambio por `CargaEvento` tienen que pasar a
   `ModalSustitucion`, **no borrarse**. Un test borrado es cobertura perdida,
   no un test arreglado. Si la cuenta de tests de Cambio baja, el cambio está
   mal.

---

### Track D — Layout del panel en vivo

#### Fase D1 — Wireframe de 3 zonas (ítem 6)

Design Fase 2 del plan de Modo en Vivo
(`docs/plans/modo-vivo-sustituciones-cierre-plan.md`): el layout nunca se
reorganizó en franjas fijas primaria / secundaria / terciaria. Hoy `MesaPanel`
apila `card`s (`marcador`, `card carga-evento`, `card alineacion-en-vivo`,
`eventos-timeline`) en el flujo normal de `.page`, y el CSS es un único
`frontend/src/index.css` de 2315 líneas con media queries a 480 / 640 / 800 /
1000px.

**Va después de C2 a propósito.** Reorganizar el layout antes de retirar el
formulario de Cambio duplicado significa acomodar en franjas un bloque que se
va a borrar.

Trabajo:

1. Inventario de lo que se renderiza hoy, con su clase y su rol real, después
   de C2.
2. Asignación a zonas: primaria = marcador + reloj (lo que el mesero mira sin
   tocar), secundaria = carga de evento + alineación en vivo (donde toca),
   terciaria = timeline + acciones de cierre. La asignación se confirma en la
   revisión de diseño, no acá.
3. CSS grid con `grid-template-areas` nombradas en `index.css`, siguiendo las
   media queries que ya existen (no se inventa un breakpoint nuevo: 1000px ya
   es el corte "escritorio" del archivo, y la decisión activa del 2026-09-08
   ya usa >=1000px como el umbral de drag-and-drop en este mismo panel).
   Móvil (375px) se queda en una columna: el panel en vivo se usa en el
   teléfono al borde de la cancha, ese es el caso principal, no el de
   escritorio.
4. Sin cambios de comportamiento. Es puro layout, así que
   `MesaPanel.test.tsx` no debería moverse; si se mueve, el cambio se salió de
   "puro layout" y hay que mirarlo.

---

### Track E — Cambio de contrato de API (ciclo propio)

#### Fase E1 — Paginación con cursor en `/equipos` y `/jugadores` (ítem 1, 3B-9)

Hoy `backend/app/repositories/base.py:34-39` hace
`order_by(self.model.id).offset(skip).limit(limit)` para **todos** los
recursos, y **doce** routes exponen `skip`/`limit`: `accesos`, `auditoria`,
`disciplinas`, `equipos`, `estadisticas`, `eventos`, `jugadores`,
`modalidades`, `partidos`, `perfiles`, `torneos`, `usuarios`. En `equipos.py`
son las líneas 20-21/33-34 y en `jugadores.py` las 41-42/52.

Esto rompe a cualquier cliente que asuma offset, y el único cliente es este
mismo frontend. **Requiere su propio ciclo** — TODOS.md ya lo dice y el plan
lo respeta.

Decisiones que hay que tomar antes de escribir código (van a la revisión):

- **Alcance:** solo `/equipos` y `/jugadores` (lo que pide el ítem) o los 12
  routes. La recomendación de arranque es **solo los 2**: son los únicos dos
  listados que pueden crecer sin techo (un torneo grande tiene cientos de
  equipos y miles de jugadores; hay 28 disciplinas y 66 modalidades fijas, y
  `auditoria` ya tiene `purgar_anteriores_a`). Migrar los 12 es ganas de
  romper once contratos para resolver dos problemas.
- **Convivencia:** `skip`/`limit` siguen funcionando durante la transición, o
  se cortan de una. Recomendación: conviven, con el cursor como camino nuevo
  y el offset deprecado en el docstring de la route. El repositorio base no se
  toca para nadie más.
- **Forma del cursor:** `order_by(id)` ya es estable y único, así que un
  cursor opaco sobre `id` alcanza; no hace falta keyset compuesto mientras el
  orden siga siendo por ID.
- **Envelope:** el repo ya tiene precedente de envelope con el feed del portal
  público (`GET /partidos/feed`) y de "envelope de error con código estable"
  como pendiente menor del portal. La respuesta paginada devuelve
  `{items, siguiente_cursor}`; `siguiente_cursor: null` = fin.

Frontend: `frontend/src/hooks/useResourceCrud.ts` y
`frontend/src/components/admin/ResourceTable.tsx` son los dos puntos donde la
paginación se consume hoy. `SelectorJugadorBuscable` pide
`GET /jugadores?q=` — el buscador se queda en la primera página, no pagina
(nadie scrollea un autocomplete de 2000 nombres; para eso está `q`).

Tests: los del contrato viejo **no se tocan** mientras `skip`/`limit` siga
soportado — esa es la prueba de que la convivencia funciona. Tests nuevos para
el cursor: primera página, página siguiente, última página
(`siguiente_cursor: null`), cursor inválido, y un cursor que apunta a una fila
borrada entremedio.

---

### Track F — Capacidad nueva

#### Fase F1 — Editar el catálogo maestro de disciplinas desde la UI (ítem 2, EC-32 / 3B-11)

Estado real: `backend/app/api/routes/disciplinas.py` es catálogo **de solo
lectura + toggle de Estado**, por la Decisión C1 de
`docs/plans/ediciones-catalogo-disciplinas-plan.md`. No hay `POST` a
propósito: el catálogo lo carga `database/11_catalogo_disciplinas.sql` (28
disciplinas / 66 modalidades). El único `PATCH` acepta solo `estado`
(`DisciplinaUpdate`) y está gateado a `require_roles("TorneoAdmin")`. En el
frontend existe `pages/torneo-admin/CatalogoDisciplinas.tsx`.

**Premisa a desafiar:** TODOS.md dice que este ítem "toca el `CHECK` de roles
y cada `require_roles(...)` del código — mismo orden de magnitud que la
paginación". Eso no se sostiene contra el código. El `CHECK` de roles es
`chk_usuarios_rol CHECK (Rol IN ('AdminGeneral','TorneoAdmin','Arbitro',
'Publico'))` (`database/02_constraints.sql:359`, repetido en
`07_migracion_roles_arbitro.sql:35`), y hay 89 usos de `require_roles` con
solo cuatro combinaciones distintas. Agregar escritura al catálogo **gateada a
`AdminGeneral`** — que ya existe y ya es el rol de `GET /auditoria`,
`GET /accesos` y de toda la gestión de licencias — no requiere tocar el
`CHECK` ni ninguno de los 89 usos. El Effort L de TODOS.md parece venir de
asumir un rol nuevo (tipo `AdminCatalogo`) que nadie pidió.

Si la revisión acepta esa reducción, el trabajo real es:

1. `POST /disciplinas` + ampliar `PATCH /disciplinas/{id}` más allá de
   `estado`, ambos con `dependencies=[Depends(require_roles("AdminGeneral"))]`
   — más estricto que el `TorneoAdmin` del toggle actual, que se queda como
   está (desactivar una disciplina y reescribir el catálogo maestro no son el
   mismo poder).
2. Schemas: `DisciplinaCreate`, y `DisciplinaUpdate` pasa de un solo campo
   `estado` a los campos editables. **`Slug` es el campo con filo**: lo agregó
   `31_migracion_portal_publico.sql` y lo consume el portal público, así que
   editarlo cambia URLs públicas. Recomendación: `Slug` se genera al crear y
   **no** se edita desde la UI; si hay que cambiarlo, es migración, igual que
   hoy.
3. Modalidades: una disciplina sin modalidades no sirve para armar un torneo.
   El alta tiene que o pedir al menos una modalidad, o dejar la disciplina en
   `Estado='Inactivo'` hasta que tenga una. Se decide en la revisión CEO; la
   recomendación es la segunda, porque reusa el `estado` que ya existe en vez
   de inventar validación nueva.
4. Borrado: **no**. Una disciplina referenciada por torneos históricos no se
   puede borrar, y el repo ya resolvió esto en todos lados con soft-delete por
   `Estado` — el toggle actual ya es el borrado.
5. `CatalogoDisciplinas.tsx` gana el alta/edición, con `RequireRole` para que
   un `TorneoAdmin` no vea botones que el backend le va a rechazar con 403.

**Guardia de migración obligatoria** (pitfall confirmado de este repo): toda
columna nueva va en **tres** lugares o revientan ~40 archivos de test con
`UndefinedColumn` — `database/01_schema.sql`, el script `NN_` de migración
(idempotente con `IF NOT EXISTS`, porque `test_scripts_sql.py` lo corre dos
veces) y la lista `SCRIPTS_VIGENTES` de `test_scripts_sql.py:36-48`.
`conftest.py:39-47` arma la base de tests **solo** con
`01_schema.sql`..`06_triggers.sql`, nunca con los `07+`. Esta fase
probablemente no agregue columnas, pero si el punto 2 agrega alguna, aplica.

Tests: 403 para `TorneoAdmin` en las rutas nuevas, 200 para `AdminGeneral`,
alta con y sin modalidades, `Slug` no editable, y que el catálogo de 28/66 de
`11_catalogo_disciplinas.sql` siga cargando igual.

---

### Orden de ejecución y dependencias

```
A0 commit del baseline ReglamentoTorneo
  |
  +-- A1 row-lock  ---> A2 fixture concurrencia ---> A3 tests T23/T24 + doble amarilla
  |
  +-- B1 filtrar listados por asignación
  +-- B2 métricas de revocación (consulta SQL)
  |
  +-- C1 DetalleEquipo -> selector compartido
  |
  +-- C2 retirar Cambio de CargaEvento ---> D1 wireframe 3 zonas
  |
  +-- E1 paginación con cursor        (ciclo propio, contrato de API)
  +-- F1 catálogo de disciplinas editable
```

Dependencias duras, las únicas que no se pueden reordenar:

- **A2 antes de A3** — sin la fixture, los tests de concurrencia no se pueden
  escribir.
- **A1 antes de A3** — el test de doble amarilla es el que prueba A1.
- **C2 antes de D1** — no se acomoda en franjas un bloque que se va a borrar.
- **A0 antes de todo** — no se construye sobre un árbol sucio de otra feature.

B1, B2, C1, E1 y F1 son independientes entre sí y de las demás.

### Fuera de alcance, explícito

- El ítem de `## Bloqueado` (correo al jugador) — pospuesto por el usuario el
  2026-09-17, necesita decisión de proveedor.
- La alerta **activa** de pico de 403 (la parte 2 del ítem 9) — mismo bloqueo
  de proveedor.
- Los 17 ítems de `## Backlog sin urgencia` y los 11 de
  `## Descartado a propósito`.
- Migrar los otros 10 routes a cursor (ver E1: la recomendación es 2, no 12).
- Un rol nuevo tipo `AdminCatalogo` (ver F1: `AdminGeneral` ya alcanza).
- Borrado duro de disciplinas (ver F1 punto 4).

### Lo que ya existe y se reusa, no se reescribe

- `PartidoRepository.get_or_404_bloqueado` — el lock de A1 ya está escrito,
  solo hay un llamador nuevo.
- El patrón `torneo_ids_permitidos` con semántica `None` / `[]` en `torneos` y
  `partidos` — B1 lo extiende, no inventa uno nuevo.
- `AUDITORIA` + su listener ORM genérico — B2 solo consulta, la captura ya
  funciona.
- `docs/queries/metricas-*.sql` como formato de métrica versionada — B2 clona
  el precedente del desempate.
- `SelectorJugadorBuscable` + `useDebouncedValue` + los hooks de resolución de
  nombres — C1 los consume.
- `ModalSustitucion` + la heurística de elegibilidad compartida — C2 se apoya
  en ellos.
- Las media queries de 480/640/800/1000px de `index.css` — D1 no agrega
  breakpoints.
- El rol `AdminGeneral` y `require_roles` — F1 no agrega roles.
- El soft-delete por `Estado` — F1 no agrega borrado.

### Verificación

- Backend: `pytest` completo (baseline 486 `def test_` / ~520 casos en 52
  archivos). Ningún test existente se borra; los de A3 corren aparte con
  `-m concurrencia`.
- Frontend: los 37 archivos de test. `MesaPanel.test.tsx` es el archivo
  sensible (C2) y `DetalleEquipo.test.tsx` es nuevo (C1).
- `verificar.ps1` para el pase completo del repo.
- B2 cierra corriendo su consulta contra `torneos_mvp` (dev) y registrando el
  resultado en TODOS.md, incluido "sin volumen suficiente" si aplica.
- TODOS.md se actualiza al cerrar cada track: el ítem baja de `## Pendiente` a
  `## Resuelto` con el detalle de alcance, siguiendo el formato que ya usa la
  sección del 2026-09-17.


<!-- autoplan-accepted:ceo -->
- A0 deja de ser fase y pasa a precondición, con condición de terminado DEFINIDA (la revisión 2 decía "7 archivos" en un lugar y "5 modificados" en otro; `git status --porcelain` da **8** entradas). Las 8, y a qué commit va cada una: **al commit del baseline `ReglamentoTorneo` van 6** — los 2 untracked (`backend/app/services/reglamento_torneo.py`, `backend/tests/test_reglamento_torneo.py`) y los 4 servicios que lo consumen (`convocado_a_partido.py`, `hito_partido.py`, `partido.py`, `torneo.py`). **`TODOS.md` va en ese mismo commit** porque su sección "Resuelto (2026-09-17)" describe exactamente ese trabajo. **`frontend/src/components/MesaPanel.tsx` va aparte**: son 5 líneas de otra feature (timeline ascendente) y es justo el archivo que D1 y la expansión 1 reorganizan, así que mezclarlo con el baseline es lo que hace irreversible un revert de D1. Verificación: `git status --porcelain` vacío antes de la primera edición de cualquier track.
- **A1 se REESTRUCTURA, no se parchea.** El swap `get_or_404` → `get_or_404_bloqueado` NO cierra la carrera: `BaseRepository.create` (`repositories/base.py:43-48`) hace `commit()`, que libera el `FOR UPDATE` antes de que `_procesar_doble_amarilla_si_corresponde` lea el conteo de amarillas. `create` pasa a una sola transacción: sin el `repo.create` que auto-commitea, `flush()` en vez de `commit()`, **y sacando también el segundo `commit()`, el de `_procesar_doble_amarilla_si_corresponde` (`evento_partido.py:124-125`)** — son DOS los commits a eliminar, no uno (corrección de la revisión 3). Un solo `commit()` al final, siguiendo la forma que `PartidoService.registrar_resultado_directo` ya usa. El docstring de `procesar_doble_amarilla` (`reglas_tarjetas.py:36-45`) documenta explícitamente las disciplinas transaccionales divergentes de sus dos llamadores, así que queda obsoleto y se actualiza en el mismo cambio. Effort M (human: ~3 h / CC: ~25 min), no ~15 min, **más el radio de regresión**: pasar de commit-por-evento a transacción única cambia semántica de la que dependen tests existentes; el cambio corre la suite completa de backend, no solo el test nuevo. Verificación: test de dos sesiones que hoy falla (2 amarillas / 0 rojas) y pasa con la transacción única, MÁS los 486 tests existentes en verde.
- A1 incluye rescate de `DeadlockDetected`, **condicionado a la reestructuración anterior y en el mismo cambio**: reintento único y, si vuelve a fallar, `DomainRuleError` con mensaje accionable ("otro operador está cargando un evento en este partido, reintentá"). Mientras `create` no sea atómico el reintento está PROHIBIDO — con la estructura de hoy, un deadlock posterior al commit de la amarilla haría que el reintento inserte una segunda amarilla, y `EVENTOS_PARTIDO` no tiene unique sobre `(jugador_id, eventos_id)`. Verificación: test que fuerza el deadlock cruzado con `registrar_resultado_directo` y afirma 4xx con ese mensaje y exactamente una amarilla persistida.
- A1 loguea de forma estructurada cuando la espera del `FOR UPDATE` supera un umbral, con `partido_id` y `usuario_id`. El umbral, el destino del log y quién lo lee se nombran en el mismo cambio (este repo no tiene pipeline de métricas, así que un log sin consumidor es trabajo invisible). Verificación: assert sobre el log en el test de contención.
- A1 lleva una línea de runbook en su docstring: si la espera es constante, revisar `pg_stat_activity` por una transacción abierta sobre ese partido.
- Guard de nombre de base ante operación destructiva en `backend/tests/conftest.py`: verifica el nombre contra un patrón test-only (`%_test`) y levanta ANTES de ejecutar. Aplica al `DROP DATABASE IF EXISTS` que **ya existe hoy sin guard** en `_recreate_test_database`, y a cualquier `TRUNCATE` que agregue A2. **No depende de A2**: si el Gate corta A2, el guard del `DROP DATABASE` sigue siendo necesario y pasa a TODO propio. Verificación: test unitario que apunta el helper a `torneos_mvp` y afirma que levanta sin ejecutar el DROP.
- C2 no se mergea hasta que exista un test de `ModalSustitucion` con `sinConvocatoria=true` que pase; el retiro del camino viejo va después, nunca antes. Verificación: ese test existe y pasa en el commit previo al retiro.
- C2 cuenta los tests de Cambio en `MesaPanel.test.tsx` antes de editar y la cuenta no baja al terminar. Verificación: el número antes y después, escrito en el commit.
- C1 mantiene `SelectorJugadorBuscable` haciendo búsqueda; la confirmación de conflicto y el alta inline se quedan alrededor en `DetalleEquipo`, no se absorben como props opcionales. Verificación: el selector no gana props booleanas nuevas.
- C1 crea `DetalleEquipo.test.tsx` cubriendo búsqueda, conflicto de inscripción y alta inline ANTES de refactorizar. Verificación: ese archivo existe y pasa en el commit previo al refactor.
- D1 lee y cita `docs/designs/frontend-inicial-dashboard-mesa-en-vivo.md` antes de asignar zonas, y conserva `.tap-button` como tamaño mínimo de target en la zona secundaria. Verificación: el plan de D1 nombra el doc; ningún control nuevo de la zona secundaria es más chico que `.tap-button`.
- D1 no agrega breakpoints: reusa 480/640/800/1000px de `index.css`. Móvil 375px queda en una columna. Verificación: `git diff` de `index.css` no introduce un `@media` con un ancho nuevo.
- B2 se invierte y con eso **ya está ejecutado**: la consulta ad hoc corrió durante esta revisión y dio cero en sus DOS mitades — contador (`AUDITORIA`: 287 filas, CERO de la tabla `usuarios`; 3 usuarios con `Licencia_Activa=True` nunca tocada) y pico de 403 (`ACCESOS`: CERO filas con `Motivo='licencia_revocada'`; únicos motivos `credenciales`=3 y NULL=17). `docs/queries/metricas-revocacion-licencia.sql` NO se commitea: no hay señal que valga releer. El ítem se cierra por falta de señal y se reabre con la primera fila de `usuarios` en `AUDITORIA`. Si alguna vez se escribe esa consulta, `Tabla` se filtra en MINÚSCULA (`usuarios`), porque guarda `obj.__tablename__` — `Tabla='USUARIOS'` da cero por casing, no por falta de datos.
- Los umbrales que reabren los diferidos van escritos como números en `TODOS.md`, no como intenciones. **Corregidos en la revisión 3**: la revisión 2 puso el disparador de E1 en 5.000 jugadores, 25x más arriba que el tope de página de 200 que su propio argumento identifica como la restricción real — garantizaba que el ítem quedara cerrado justo en todo el rango donde empieza a doler. Y no tenía disparador de equipos, aunque el motivo del diferimiento hablaba de equipos. Quedan así, atados a la restricción real (el tope de 200) y medidos sobre filas ORGÁNICAS, no crudas:
  - **E1** se reabre con (a) **>150 equipos orgánicos** o **>150 jugadores orgánicos** (75% del tope de 200, es decir antes de que el banner de truncado pase a ser la experiencia normal y no la excepción), o (b) un p95 medido >800 ms en `GET /jugadores` o `GET /equipos`, o (c) un segundo cliente de la API que no sea este frontend. Hoy: 10 equipos y 37 jugadores orgánicos.
  - **F1** se reabre al SEGUNDO pedido real de alta de una disciplina fuera del catálogo de 28 (el primero se atiende con el script de migración que ya existe).
  - **B2** se reabre con la primera fila de la tabla `usuarios` en `AUDITORIA` (es decir, la primera licencia realmente otorgada o revocada).
- Los diferimientos se redactan con la fórmula que el repo ya usa para la Fase 3 del desempate — "sin señal todavía, revisitar con datos de uso real" — no como rechazos. Y Track A se justifica por CONSECUENCIA (un registro disciplinario incorrecto en un partido cerrado no se puede arreglar y el fallo es silencioso), no por frecuencia: la frecuencia medida es CERO casos de 2 amarillas sin roja.
- Toda medición contra `torneos_mvp` que se use como argumento separa filas orgánicas de las sintéticas que dejó `backend/scripts/mock_estres_catalogo.py`: 1750 de 1787 jugadores tienen cédula `MOCK-` y 68 de 83 torneos son del grupo "Prueba de Estrés". Orgánico real: 37 jugadores, 15 torneos.
- Si la expansión 1 (estado de tarjetas visible) se aprueba, la derivación de estado de tarjetas por jugador va en **`frontend/src/components/eventos.ts`**, el módulo de derivación compartido que `MesaPanel` ya consume y que ya exporta `deriveHistorialElegibilidad` (línea 56), `deriveTitularSuplente` (91) y `deriveEnCancha` (119), y que ya rastrea `"Tarjeta Roja"` en la línea 60. **Corrección de la revisión 3:** la revisión 2 apuntaba a la preview de `ModalResultadoDirecto.tsx`, que es el target equivocado — esa deriva de estado local de un batch sin guardar (`otrosEventos: OtroEventoLocal[]`) dentro de un modal de carga retroactiva, mientras la expansión necesita estado desde eventos ya persistidos en el servidor (`eventosRegistrados`, `MesaPanel.tsx:215`). Mismo objetivo (no una tercera copia de la regla), mecanismo correcto. Y el effort de la expansión se revisa de S a **S-M** (human: ~6 h / CC: ~30 min): es extracción en un módulo compartido más trabajo de layout en el mismo archivo de 1002 líneas que D1 está reorganizando.
- Los tracks corren en orden serial con stop-the-line (`A0 → A1 → A2 → A3 → C1 → C2 → D1 → exp.1`): ninguno arranca hasta que el anterior bajó a la sección Resuelto de `TODOS.md`. Verificación: un solo track con archivos modificados a la vez.
- **A2 es el ítem menos especificado del plan y está segundo en una cadena serial que bloquea a A3/C1/C2/D1 — riesgo de cronograma que hay que nombrar (revisión 3).** `conftest.py:112-145` envuelve cada test en una sola sesión con savepoints; una fixture de conexiones genuinamente paralelas significa optar POR FUERA de ese harness, que es una tarea de diseño, no un ajuste de fixture. A2 no arranca sin un bosquejo de enfoque escrito de una página: cómo se crean las 2 sesiones, cómo se limpia sin depender del rollback que no existe ahí, y qué pasa si el test se cuelga. Si el bosquejo no cierra, A2 se mueve al final de la cadena (detrás de D1) para no bloquear el resto, y A3 se hace con la opción determinista de servicio.
- Cada track lleva un resultado observable declarado (la tabla de 0D), no solo "tests verdes". Verificación: el resultado está escrito en el track antes de empezarlo.
- Si F1 procede en algún momento: no se escribe lógica de slug en Python (`fn_generar_disciplina_slug` ya lo hace con `translate()` y preserva el slug en rename); `DISCIPLINA.Estado` se fija `NOT NULL` con default en la misma migración; el `limit=200` hardcodeado de `services/disciplina.py:30` sale; se valida que el slug derivado no sea vacío; la reversión de la Decisión C1 se escribe con su motivo; y la guardia de tres lugares (`01_schema.sql` + script `NN_` idempotente + `SCRIPTS_VIGENTES` de `test_scripts_sql.py:36-48`) es obligatoria para toda columna nueva.
- Si E1 procede en algún momento: el cursor lleva campo de versión desde el día 1, y el caso "cursor apunta a una fila borrada" tiene test y comportamiento definido.
<!-- /autoplan-accepted:ceo -->
<!-- autoplan-accepted:design -->
- D1 arranca con la asignación de zonas FIJADA, no delegada: primaria = marcador + reloj + estado; secundaria = grilla de tipos de evento + alineación en vivo; terciaria = timeline + `Finalizar partido`. Referencia concreta: `~/.gstack/projects/Score-App/designs/mesa-panel-3-zonas-20260917/wireframe-zonas.html` (375px y ≥1000px). Verificación: el plan de D1 cita el wireframe y ya no contiene "se confirma en la revisión de diseño".
- D1 entrega la zona primaria a 375px con `position: sticky; top: 0` sobre `.marcador` + `.marcador__estado` (`MesaPanel.tsx:452-457`). Sin esto, una grilla de 3 zonas que colapsa a una columna no cambia nada para el caso principal declarado (teléfono al borde de la cancha) y D1 sería mejora solo de escritorio. Verificación: a 375px el marcador y el reloj siguen visibles después de scrollear a la zona 2.
- D1 agrega una confirmación `aria-live="polite"` anclada en la zona donde se tocó, con el contenido del evento (ej. "Cambio registrado: sale #7 López, entra #14 Díaz (72')"). Hoy hay CERO `aria-live` en `MesaPanel.tsx` y ninguna confirmación de éxito, mientras 6 archivos del repo ya usan el patrón. El orden ascendente del timeline NO se toca (decisión activa del usuario del 2026-09-09). Verificación: test que afirma la región `aria-live` y su contenido tras una carga exitosa.
- SUPERSEDE de la obligación de Fase 1 sobre C2 ("C2 no se mergea hasta que exista un test de `ModalSustitucion` con `sinConvocatoria=true` que pase"): esa obligación era INAPLICABLE porque no existe camino `sinConvocatoria` hacia `ModalSustitucion` — el botón "Sacar" solo se renderiza dentro de `titularesEquipo.map(...)`, `titularesEquipo` se deriva de la convocatoria, y sin convocatoria la lista sale vacía sin ningún botón (el propio comentario del código lo dice). Reemplazo: C2 se divide en **C2a** (diseñar y construir el punto de entrada sin convocatoria; forma recomendada: la lista de alineación en vivo cae a la `plantilla` completa con el caption "Sin convocatoria guardada — mostrando plantilla completa", una sola lista para los dos estados, preservando D4) y **C2b** (recién después, retirar la rama de `CargaEvento`). Gate elevado: no "un test pasa", sino "un árbitro completa un cambio de punta a punta en un partido sin convocatoria guardada, con el mismo gesto que con convocatoria".
- El empty state de `ModalSustitucion` (`ModalSustitucion.tsx:43-44`) gana una acción primaria que rutea a "Gestionar Partido › Convocatoria" y vuelve al partido al guardar. Hoy es instrucción sin navegación (solo "Cancelar"), y después de C2b sería el estado terminal de todo partido con convocatoria incompleta. Prerrequisito de C2b.
- El rescate de `DeadlockDetected` de A1 recibe tratamiento visual distinto del error de validación permanente, y un botón "Reintentar" que re-envía el mismo payload. Hoy ambas superficies (`submitError` de `CargaEvento`, `error` de `ModalSustitucion`) renderizan todo error igual como `<p className="error-text">`, así que el único error transitorio del sistema se vería idéntico a un rechazo definitivo. Verificación: el error de deadlock no comparte clase con un 4xx de validación, y el botón re-envía sin que el usuario rearme el formulario.
- La expansión 1 (si se aprueba) especifica el tratamiento visual, no solo la ubicación del código: badge en la fila del jugador con TEXTO Y FORMA además de color (`1A`, `2A`, `R`), mostrado en la lista de alineación en vivo y en los candidatos `.tap-button` de `ModalSustitucion`. Color solo es la codificación que falla para daltonismo bajo sol directo, que es el entorno real de uso. Verificación: el badge se distingue en escala de grises.
- D1 declara `min-width` mobile-first para las áreas nuevas y nombra 1000px como el ÚNICO breakpoint de activación de las 3 zonas (consistente con el umbral de drag-and-drop de la decisión activa del 2026-09-08). `index.css` mezcla direcciones (`min-width` en 800/1000, `max-width` en 480/640), así que la verificación de Fase 1 ("no introduce un `@media` con un ancho nuevo") se podía satisfacer rompiendo el rango 640-799px. Verificación añadida: inspección explícita entre 640 y 799px.
- D1 fija accesibilidad: 44px mínimo para todo target de las zonas 1 y 2, incluido el botón "Sacar" (hoy es `.link-button`, un link de texto como target táctil primario a 375px); contraste de cuerpo ≥4.5:1 (el escenario es sol directo); orden de tabulación siguiendo el orden de zonas.
- C1 especifica la secuencia de pasos antes de refactorizar: dos paneles dentro de UN modal — el selector queda montado y visible pero inerte (atenuado, no enfocable) mientras la confirmación de conflicto se renderiza directamente debajo de la fila elegida, con "Volver a buscar" a un toque. Sin esto quedan tres secuencias posibles, ninguna elegida, y la elige el implementador.
- Cada fase reorganizada nombra su tratamiento de estado pending en una línea. Hoy `isPending` solo deshabilita botones, así que con red lenta y sin mensaje de éxito la pantalla se ve muerta.
- El orden serial pasa a `A0 → A1 → C1 → C2a → C2b → D1 → exp.1 → A2 → A3`: A2/A3 van detrás de D1 de forma INCONDICIONAL, no sujeta a un juicio bajo presión de cronograma. A2 es el ítem menos especificado del plan y bloqueaba todo lo visible para el usuario; A1 no depende de A2 y conserva su valor.
- Si E1 se reabre: el control es "Cargar más" que appendea en el lugar; el banner `truncado` y su string se retiran en el MISMO commit (si no, la página muestra a la vez un cargar-más y un aviso que dice filtrá); `siguiente_cursor: null` muestra "Fin de la lista", no un botón deshabilitado sin explicación; las filas quedan montadas con una fila de carga agregada, nunca se blanquea la tabla en un fetch de página siguiente.
- Si F1 se reabre: el alta pide o agenda la primera modalidad (una disciplina sin modalidades es un registro roto), y el `Slug` se muestra como campo de solo lectura con la leyenda "Definido al crear; cambiarlo requiere migración".
- Si B1 se reabre como scoping forzado server-side: requiere una TERCERA rama de empty state nombrando la causa real ("No tenés torneos asignados con equipos inscritos. Pedí una asignación a un AdminGeneral."), un indicador persistente de alcance, y rewrite del banner `truncado`. `EquiposAdmin.tsx:268-277` distingue a propósito vacío-filtrado de vacío-real y `hayFiltros` sería `false` para el filtro de alcance, así que el listado habría dicho "No hay equipos creados todavía" a un TorneoAdmin sin asignaciones: factualmente falso.
<!-- /autoplan-accepted:design -->

<!-- autoplan-accepted:dx -->
- DX-1: agregar `frontend/.env.example` con `VITE_API_BASE_URL=http://127.0.0.1:8000`. Verificado: `frontend/src/api/client.ts:4` lee `import.meta.env.VITE_API_BASE_URL` sin default, `frontend/src/auth/AuthContext.tsx:72` la interpola directo en el `fetch` del login, y `.gitignore:14-15` (`.env` + `!.env.example`) ignora el `frontend/.env` local; `backend/.env.example` está commiteado y `frontend/.env.example` no existe. En un clon limpio el login POSTea a `undefined/api/v1/auth/login` y el backend nunca ve el request. NO se agrega un default en `client.ts`: convertiría un fallo de configuración en un fallo de red intermitente. Verificación: clon limpio sin `frontend/.env` propio, copiar el example, y el login entra.
- DX-2: extender `infrastructure/docker-compose.yml` con el servicio Postgres y la carga inicial de `database/01_schema.sql`–`06_triggers.sql`, y nombrarlo en la sección "Levantar todo" del `README.md` como camino recomendado, dejando el manual como alternativa. El compose ya existe y ya levanta la API con `extra_hosts: host.docker.internal:host-gateway` resuelto para Windows, Mac y Linux; hoy asume "Postgres corre en el host (ya lo tenés instalado y con torneos_mvp cargado)", que es la suposición que rompe a la segunda persona que clone. Verificación: TTHW de clon a `.\verificar.ps1` en verde medido en <= 5 min.
- A2 registra la marca `concurrencia` en `backend/pytest.ini` bajo un bloque `markers =` con descripción de una línea, y agrega `addopts = --strict-markers`. Verificado: hoy `pytest.ini` tiene solo los tres settings de asyncio, ningún `markers` y ningún `addopts`, así que una marca no registrada solo emite `PytestUnknownMarkWarning` y un typo en `-m "not concurenica"` no deselecciona nada y reporta verde — el escape hatch que el plan promete no es alcanzable. Verificación: `pytest -m concurrencia --collect-only` selecciona exactamente los tests de A3, y una marca inventada falla la corrida en vez de advertir.
- A2 cambia `verificar.ps1:46` a `python -m pytest -q -m "not concurrencia"`, agrega un switch opt-in `-Concurrencia` y un `Paso "Backend — concurrencia"` propio, para que los tests de A3 sigan corriendo, visibles, en su propio bucket. Sin esto los tests de A3 (commits reales + `TRUNCATE`) entran en la corrida por defecto que el README manda correr antes de dar algo por terminado, dentro de un script cuya cabecera (`verificar.ps1:22-24`) promete que "pytest crea y destruye sus propias bases; nunca toca `torneos_mvp`" — el guard de nombre de base protege los datos pero no esa promesa. Se documenta en `backend/README.md` (3 líneas, "cómo correr los tests de concurrencia", junto a la línea de pytest que ya está) y en el comentario de cabecera de `verificar.ps1`. Como el orden serial mueve A2/A3 al final, esto se escribe AHORA en la definición de terminado de A2. Verificación: `.\verificar.ps1` muestra los dos pasos por separado y el paso por defecto no incluye tests de concurrencia.
- A2 modifica, en el mismo cambio, el docstring de módulo de `backend/tests/conftest.py` para describir los DOS harness (el de savepoints donde un `commit()` de repositorio no persiste, y el de conexiones paralelas donde sí) y cuándo usar cada uno; y agrega a `backend/README.md` una sección "cómo escribir un test de concurrencia" con un test de ejemplo copiable ENTERO, no prosa. Hoy ese docstring enseña explícitamente que un `session.commit()` dentro de un repositorio no persiste nada de verdad, y la fixture de A2 invierte exactamente eso. La métrica real de A2 no es "el autor escribe el test 1" sino "otro escribe el test 4 en diez minutos". Verificación: el docstring nombra los dos harness y el README contiene un test que se puede pegar y correr.
- **A1 usa el mecanismo de códigos de error estables que el repo YA tiene, no prosa.** Se agrega `ConcurrencyConflictError` a `backend/app/exceptions/errors.py`, mapeada en `handlers.py` a **409 con header discriminante `X-Reintentable: true`** (mismo patrón que `LicenseRevokedError` → 403 + `X-License-Revoked` y `RateLimitError` → 429 + `Retry-After`, `handlers.py:68-95`), y con `detail = "evento_conflicto_concurrente"`, código que se agrega a `CODIGOS_ERROR_TRADUCIDOS` (`frontend/src/api/client.ts:73-86`) con su copy en español y su acción de recuperación. SUPERSEDE de la forma que decía Fase 1 (`DomainRuleError` con mensaje en prosa): `DomainRuleError` mapea a 400 (`handlers.py:50-52`), o sea mismo status, misma forma `{detail: "<prosa>"}` y misma clase CSS que un rechazo de validación permanente, con lo cual el único discriminador que le quedaría al frontend es hacer substring-match sobre texto en español — exactamente lo que `CODIGOS_ERROR_TRADUCIDOS` existe para evitar, y lo que vuelve inimplementable la obligación de Fase 2 de que "el error de deadlock no comparte clase con un 4xx de validación". El 409 ya está ocupado por `IntegrityError` y `PreconditionFailedError` eligió 412 por eso (`handlers.py:81-88`), así que la desambiguación la hace el HEADER, no el status solo; `client.ts` lo lee sin clonar el stream de la respuesta (el comentario de `client.ts:23-31` explica por qué eso importa) y `apiErrorMessage` renderiza el texto gratis. Verificación: test que fuerza el deadlock y afirma 409 + `X-Reintentable`; test de frontend que afirma que el botón "Reintentar" aparece sin depender del texto del mensaje.
- **Este plan lleva su propia sección "§ Copy de errores"**, siguiendo la convención que `client.ts:62-66` cita por nombre, con una fila por error nuevo: código, status, texto y acción de recuperación. Las seis filas mínimas: conflicto de concurrencia de A1; cursor inválido de E1; cursor que apunta a fila cuyo estado cambió (E1); timeout de test de A2 (mensaje que nombre las dos sesiones y la fila en disputa, no un `TimeoutError` pelado); valor inválido de `alcance` en B1 (hoy sería el 422 crudo sin traducir de FastAPI); y 403 de F1. Hoy el plan especifica copy para UNO solo de sus errores (el tercer empty state de B1, que además está bien: nombra causa y acción, "Pedí una asignación a un AdminGeneral"). Verificación: la sección existe y cada error nuevo aparece en ella antes de implementarse.
- Política de errores del plan, dicha una vez: la acción de recuperación va en el mensaje al usuario y el puntero de diagnóstico va en el docstring (como ya hace la línea de runbook de A1 con `pg_stat_activity`). No se agregan URLs de docs a los mensajes: cero errores del repo las llevan hoy y es una herramienta interna en español con acciones de recuperación in-app.
- El umbral de espera del `FOR UPDATE` y el conteo de reintentos de A1 salen de `Settings` (`backend/app/core/config.py`, que ya lee `.env` con pydantic-settings), no de literales en el código. El sink del log se nombra concreto: `logging.getLogger("app.concurrencia")` a stdout. Verificación: cambiar el umbral por variable de entorno cambia el comportamiento sin editar código.
- A1 deja registrado en el docstring de `BaseRepository.create` que `EventoPartidoService` maneja su propia transacción, para que el próximo que lea "create no commitea" no lo "arregle" de vuelta. Colapsar `create` a una sola transacción es correcto, pero cambia una expectativa que cualquier llamador futuro puede dar por sentada. Verificación: el docstring lo dice.
- El mensaje de 403 de F1 se testea por CONTENIDO, no solo por status. Como `RequireRole` ya esconde los botones, un 403 real significa token viejo o cambio de rol a mitad de sesión: el mensaje dice eso y manda a re-loguear. Hoy una llamada directa recibe `deps.py:132-134` ("Esta operación requiere rol X (tenés: Y)"), que tiene problema y causa pero no arreglo. Verificación: el test afirma el texto, no solo el código.
- **Toda fase que cambie el contrato de la API (B1, E1, F1) nombra como paso numerado "regenerar `frontend/src/api/schema.d.ts` con `npm run gen:api` (backend arriba) en el MISMO commit".** Verificado: `frontend/package.json:12` genera el cliente contra `http://127.0.0.1:8000/openapi.json`, o sea contra un backend VIVO, y `verificar.ps1` explícitamente no necesita el servidor levantado (cabecera, línea 22) — así que el drift de contrato no lo detecta nadie: o el typecheck pasa en verde contra un contrato viejo, o `tsc` tira un error que nunca dice "corré gen:api". Verificación: cada una de esas fases tiene el paso escrito, y el `schema.d.ts` regenerado entra en el mismo commit.
- Cada ruta nueva o modificada por este plan lleva una URL de ejemplo ejecutable en su docstring, siguiendo el precedente que ya existe en `backend/app/api/routes/partidos.py:92` (`Ejemplo: GET /api/v1/partidos/feed?disciplina_id=1&limit=20`). Verificación: la ruta tiene el ejemplo y la URL responde tal cual está escrita.
- **El plan gana una tabla de estado al principio** — fase, viva o diferida, y disparador de reapertura — y los encabezados de las fases diferidas se reescriben como `#### Fase E1 — DIFERIDA (ver umbral)`, conservando el cuerpo como diseño de referencia. Hoy los Tracks A-F se leen como nueve ítems comprometidos con instrucciones a nivel de archivo, y las correcciones del final revierten cuatro en silencio (B2 "ya está ejecutado", F1/E1/B1 pasan a "si se reabre"), mientras el orden serial de ejecución omite B1, B2, E1 y F1 sin decirlo y el grafo de dependencias los sigue presentando como en alcance. Quien lea "Track B" y arranque `EquipoRepository.list(torneo_ids_permitidos=...)` está haciendo trabajo diferido, y la frase que lo habría frenado está 380 líneas más abajo. Además se reescriben en el cuerpo A0, A1 y B2 para que digan lo que las revisiones 2 y 3 corrigieron, quedando las correcciones al final solo como changelog corto — hoy el cuerpo afirma que A1 se arregla cambiando `get_or_404` por `get_or_404_bloqueado` mientras la corrección dice que eso no cierra la carrera, y la sección Verificación sigue pidiendo "B2 cierra corriendo su consulta" cuando la consulta ya corrió y su archivo no se commitea. Verificación: leer el plan de arriba hacia abajo no lleva a empezar trabajo diferido.
- **El tratamiento de estado pending se decide UNA vez, global, no por fase.** SUPERSEDE de la obligación de Fase 2 que decía "cada fase reorganizada nombra su tratamiento de estado pending en una línea": eso devuelve la decisión al implementador, que es el modo de fallo exacto que las propias obligaciones de Fase 2 sobre zonas FIJADAS y sobre la secuencia del modal de C1 se agregaron para eliminar; cinco fases reinventándolo dan cinco tratamientos distintos. Queda así: control deshabilitado + spinner inline + la región `aria-live` que ya pide Fase 2 anunciando "Guardando…" y después la confirmación de éxito. Verificación: hay un solo patrón de pending en el diff.
- La guardia de tres lugares para columnas nuevas (`01_schema.sql` + script `NN_` idempotente + `SCRIPTS_VIGENTES` de `backend/tests/test_scripts_sql.py:36-48`) se escribe UNA vez en `database/README.md` y el plan apunta ahí en vez de restatearla. Hoy está en el plan dos veces y en el README de la base ninguna, y es la que produce el `UndefinedColumn` en ~40 archivos de test. Verificación: `database/README.md` la cubre y el plan la referencia sin repetirla.
- La trampa de casing de `AUDITORIA.Tabla` se preserva en el criterio de reapertura de B2 en `TODOS.md`, en una línea: "`Tabla` se filtra en minúscula (`usuarios`) — guarda `__tablename__`". Verificado: `backend/app/core/auditoria.py:111,119,137,163,178,193` usan `obj.__tablename__`, así que `Tabla='USUARIOS'` da cero por casing, no por falta de datos — es la trampa exacta que hizo mal la especificación original de B2. Esto NO contradice la obligación de Fase 1 de no commitear `docs/queries/metricas-revocacion-licencia.sql`: preserva el dato sin el archivo. Si además se commitea la consulta, es la decisión T-3 del Gate. Verificación: el criterio de reapertura de B2 en `TODOS.md` incluye esa línea.
- `docs/queries/` gana una fila en la tabla "Dónde está cada cosa" del `README.md` raíz y un `docs/queries/README.md` de 10 líneas (cómo correr una consulta, contra qué base, y que un resultado en cero es un hallazgo que vale registrar). Verificado: el directorio tiene un solo `.sql` y ningún README, y grepear "queries" en `README.md`, `database/README.md` y `backend/README.md` da CERO resultados — es indescubrible. Va independientemente de lo que se resuelva sobre T-3 y sobre B2.
- La regla de nombres de parámetros de query queda escrita en `backend/README.md`: sustantivos de dominio en español, primitivas de paginación y búsqueda en inglés. Hoy el repo mezcla (`skip`/`limit`/`q` contra `disciplina_id`/`estado`) y el plan suma `alcance` sin fijar la regla, así que el próximo parámetro la vuelve a litigar. Verificación: la regla está escrita y el parámetro siguiente la cumple.
- Los umbrales de reapertura ya escritos como números en `TODOS.md` llevan al lado el nombre de la consulta que los evalúa, para que revisarlos sea leer y correr en vez de reconstruir. Verificación: cada umbral tiene su consulta nombrada.
- **Si F1 se reabre: la autorización se resuelve partiendo rutas, no ampliando la que existe.** El plan pide ampliar `PATCH /disciplinas/{id}` más allá de `estado`, gatearlo `AdminGeneral`, y a la vez conservar el toggle de `TorneoAdmin` "como está". Eso no es expresable: `backend/app/api/routes/disciplinas.py:77-86` tiene UNA sola ruta PATCH, gateada `dependencies=[Depends(require_roles("TorneoAdmin"))]`, cuyo docstring dice que el único cambio permitido es activar/desactivar; y `require_roles` (`backend/app/api/deps.py:118-136`) es dependencia a NIVEL DE RUTA, no por campo. Tener `estado` en TorneoAdmin y el resto de los campos en AdminGeneral sobre la misma ruta obliga a mover la autorización al servicio, abandonando el patrón que el plan dice preservar (89 usos, cuatro combinaciones). Queda: `PATCH /disciplinas/{id}/estado` conserva `TorneoAdmin`; un `PUT /disciplinas/{id}` (edición completa del catálogo) y un `POST /disciplinas` toman `AdminGeneral`. La autorización se queda donde los otros 89 call sites la ponen, los dos poderes quedan visiblemente distintos, y `RequireRole` en `CatalogoDisciplinas.tsx` tiene dos cosas limpias sobre las que decidir. Confirmado de paso: `require_roles` ya hace bypass para `AdminGeneral` (`deps.py:130`), así que el razonamiento del plan sobre eso sí se sostiene. Verificación: ninguna ruta mezcla dos niveles de rol para campos distintos.
- Si F1 se reabre: el `limit=200` de `backend/app/services/disciplina.py:30` **se sube y se promueve a constante nombrada, o se pagina — NO se quita**. SUPERSEDE de la obligación de Fase 1 que decía "el `limit=200` hardcodeado de `services/disciplina.py:30` sale": está en `list_con_modalidades`, cuyo docstring explica que la cota es deliberada para un catálogo fijo de 28 disciplinas / 66 modalidades de solo lectura. La premisa entera de F1 es volver ese catálogo escribible por el usuario, así que la cota deja de ser cosmética exactamente cuando F1 la eliminaría.
- Si E1 se reabre: (a) se actualiza `RESPUESTA_LISTA_JUGADORES` (y `RESPUESTA_JUGADOR`/`RESPUESTA_PERFIL` si se tocan) al union envuelto, MÁS un test de backend que afirme que `app.openapi()["paths"]["/api/v1/jugadores"]["get"]["responses"]["200"]` contiene `siguiente_cursor`. `GET /jugadores` es la única ruta que se sale de la red de seguridad del codegen: usa `response_model=None` con el dict mantenido a mano de `backend/app/api/routes/jugadores.py:22-24,39` por la proyección de PII para callers anónimos. Sin esa actualización, `openapi.json` sigue anunciando la forma vieja, `npm run gen:api` regenera un cliente tipado a la forma vieja, `tsc -b` pasa verde, y la rotura aparece en runtime como `.map is not a function` — rompiendo la garantía que `README.md:68-69` vende como convención central. (b) `{items, siguiente_cursor}` es el envelope paginado genérico y la regla queda escrita en `backend/README.md`; `FeedResponseOut` (`backend/app/schemas/partido.py:290-303`, `{fecha_pedida, fecha_efectiva, total_disponible, partidos}`) se declara por escrito forma legacy de una sola vez que NO se migra. (c) se define el destino del banner `truncado` de `frontend/src/hooks/useResourceCrud.ts:40,131`, que hoy depende de `LIMITE_LISTA = 200` para saber que hay más. (d) el page size del cursor hereda el `le=200` que ya existe en `routes/equipos.py:21` y `routes/jugadores.py:42`. (e) cursor inválido: 400 con código estable en `CODIGOS_ERROR_TRADUCIDOS`, texto "El cursor no es válido o expiró; recargá el listado", nunca fallback silencioso a la página 1; un campo de versión distinto devuelve ese mismo error en vez de reinterpretar bytes viejos; y como estos recursos usan soft-delete por `Estado`, el caso real es "fila cuyo estado cambió y ya no matchea el filtro", que con un cursor de id opaco se resuelve continuando desde ese id igual.
- Si B1 se reabre: el alcance del listado NO se expresa como query param elegible por el cliente (`alcance=asignados|disciplina` con default ancho, como decía el plan). El techo de permisos se queda implícito y derivado del token vía `torneo_ids_permitidos`, con la semántica `None`/`[]` que el plan ya documenta bien, como ya hacen `routes/torneos.py` y `routes/partidos.py`. Dos motivos: invierte el default seguro, y `alcance=asignados|disciplina` mezcla una audiencia con un eje de datos, así que nadie va a adivinar cuál es cuál — es el problema de "uno y no tres" que el propio plan se niega a crear un párrafo antes. Si el camino de alta o de búsqueda necesita ver filas no inscritas, se expresa como flag de CAPACIDAD con nombre honesto (`incluir_no_inscritos=true`), y el servidor garantiza que nunca amplía más allá de lo que el rol del caller ya permite. Además: empty state y encabezado del listado dicen "mostrando solo equipos de tus torneos asignados" con un toggle "ver todos" — ese toggle es a la vez el escape hatch, la documentación y lo que evita el reporte de bug.
<!-- /autoplan-accepted:dx -->

<!-- autoplan-accepted:eng -->
- **A2 corre contra su PROPIA base de datos, `torneos_mvp_test_concurrencia`, construida por el mismo helper `_recreate_test_database`, con scope de módulo.** Verificado: `backend/tests/conftest.py:89-91` declara `_test_db_ready` con `scope="session"` y reconstruye la base UNA vez por corrida ejecutando `01_schema.sql`–`06_triggers.sql`; `database/05_seed.sql` inserta en 14 tablas, entre ellas `EVENTOS` (el catálogo), `DISCIPLINA`, `MODALIDAD`, `PARTIDOS`, `EQUIPOS`, `JUGADORES` y `EVENTOS_PARTIDO`, y los ~520 tests dependen de esas filas protegidos solo por el rollback de savepoint de `db_session` (`conftest.py:112-125`). El `TRUNCATE ... CASCADE` con commits reales que A2 propone NO se revierte con ese savepoint y se propaga por el `ON DELETE CASCADE` de `EVENTOS_PARTIDO`, sin re-seed: la suite pasa a fallar según el orden en que pytest corra, o sea verde local y rojo en CI. Con base propia el TRUNCATE sale gratis y los 520 tests quedan intocables por construcción. RECHAZADO: "DELETE acotado a las tablas tocadas" — las tablas que A3 toca son justamente las sembradas. Verificación: correr la suite completa dos veces seguidas en la misma sesión, con los tests de A3 incluidos, da el mismo resultado.
- **A1 fija `lock_timeout` y reemplaza el test de deadlock por un test de contención.** Verificado: `get_or_404_bloqueado` tiene un solo llamador hoy, `PartidoService.registrar_resultado_directo` (`backend/app/services/partido.py:198`), y A1 haría que los dos caminos adquieran el `FOR UPDATE` sobre la MISMA fila de partido, PRIMERO. Ordenamiento idéntico sobre un único recurso produce CONTENCIÓN, no `DeadlockDetected`: Postgres levanta 40P01 solo ante adquisición cruzada de 2+ recursos, así que el "test que fuerza el deadlock cruzado con `registrar_resultado_directo`" que pide Fase 1 es inescribible y terminaría descartado o satisfecho con un test falso. Y el fallo real queda descubierto: `lock_timeout` no aparece en `backend/app` ni en `database/` (verificado; los únicos hits están dentro de `.venv`), y el default de Postgres es 0 = esperar para siempre, así que un cliente que muere reteniendo el lock cuelga indefinidamente todo evento posterior de ese partido, con `verificar.ps1` en verde. Queda: `SET LOCAL lock_timeout` leído desde `Settings` (el mismo `config.py` por el que ya se rutea el umbral del log — se usa para el timeout REAL, no solo para loguear); `LockNotAvailable`/`QueryCanceled` mapeadas a `ConcurrencyConflictError`; el rescate de `DeadlockDetected` se conserva como defensa en profundidad. SUPERSEDE de la obligación de Fase 1 en la parte del test: en vez del deadlock cruzado, un test de CONTENCIÓN (la sesión B espera, vence el timeout y recibe 409). RECHAZADO: `nowait=True`, que falla al instante — para un árbitro que toca dos veces, una espera acotada es mejor experiencia que un rechazo inmediato. Corolario incluido: el log de "espera del `FOR UPDATE` por encima del umbral" solo puede dispararse DESPUÉS de que la espera termina, así que sin timeout la alerta para un cuelgue indefinido nunca se emite; con `lock_timeout` el log se vuelve trivialmente correcto. Son un solo arreglo. Verificación: test de dos sesiones donde la B vence el timeout y recibe 409 con el código estable, y assert sobre el log de contención.
- **Se elimina el header `X-Reintentable`. El 409 lleva solo el código estable en `detail`.** SUPERSEDE de la obligación de Fase 2.5 que especificaba `409 + X-Reintentable: true` razonando por analogía con `X-License-Revoked`. La analogía se rompe y está verificado: `X-License-Revoked` lo consume el interceptor GLOBAL `onResponse` (`frontend/src/api/client.ts:44-56`) como efecto de sesión, llamando a `onLicenseRevoked()`, mientras que un botón "Reintentar" por mutación necesita la señal EN el call site — y todos los call sites la descartan: `frontend/src/components/MesaPanel.tsx:79-80, 91-94, 104-105, 114-115, 124-125, 137-140, 149-152` y siguientes hacen `const { data, error } = await api.GET(...)` seguido de `if (error) throw error`, con `response` desestructurado afuera; `mutation.error` es el body parseado y nada más, en ~40 sitios. La otra mitad de la obligación ya alcanza: `detail = "evento_conflicto_concurrente"` es un código estable y `CODIGOS_ERROR_TRADUCIDOS` (`client.ts:73-86`) es el mecanismo existente. El componente discrimina con `error.detail === "evento_conflicto_concurrente"`. SALVEDAD obligatoria: `apiErrorMessage` colapsa código a texto en español, así que el chequeo del reintento lee `error.detail` ANTES de traducir, nunca el string renderizado — si no, se reintroduce una capa más arriba el substring-matching que la obligación buscaba evitar. Verificación: test de frontend que afirma el botón de reintento a partir de `error.detail`, sin leer texto renderizado y sin plomería nueva en los call sites.
- **`anular` toma el mismo lock del partido cuando el evento objetivo es una tarjeta.** SUPERSEDE de la exención de Fase 1 que afirmaba que "`anular` opera sobre un evento ya existente por su propio ID, no sobre el estado compartido del partido". Es falso y se verifica en dos archivos: `procesar_doble_amarilla` (`backend/app/services/reglas_tarjetas.py`) cuenta las amarillas filtrando `estado="Registrado"`, y `anular` hace exactamente `save_changes(evento, estado="Anulado")` (`backend/app/services/evento_partido.py:192`) sobre esa misma columna, tomando el partido con `get_or_404` SIN lock (línea 190). Anular la amarilla #1 en paralelo con el insert de la amarilla #2 corre la carrera en las dos direcciones: una roja para un jugador con una sola amarilla válida, o la desaparición de la roja que A1 busca garantizar — el mismo resultado silencioso e irreparable tras el cierre que justifica Track A entero. `corregir_minuto` SÍ es genuinamente seguro porque la regla no lee el minuto: se dice explícitamente en vez de agrupar los dos bajo una exención común. Verificación: test de dos sesiones que anula la amarilla #1 mientras se inserta la #2 y afirma el conteo final correcto.
- **El reintento de A1 hace `await session.rollback()` antes de reintentar y re-corre el read-validate-insert COMPLETO, no solo el insert.** Tras cualquier error DBAPI, SQLAlchemy deja la sesión en pending-rollback, así que sin el rollback previo el reintento falla con un `PendingRollbackError` confuso en vez de reintentar. Y el `minuto` sale de `calcular_minuto_actual(..., datetime.now())`: reusar el valor previo al fallo escribe un minuto viejo, y `chk_eventos_partido_minuto` no lo atrapa porque sigue estando entre 0 y 130. Refuerzo verificado: NO hay UNIQUE sobre `EVENTOS_PARTIDO` (`database/02_constraints.sql:374-386` solo tiene FKs y checks), así que la base no es red de seguridad contra un doble insert. Verificación: test que fuerza el fallo, afirma que el reintento recalcula el minuto y que queda exactamente un evento persistido.
- **El 409 se rutea por el mecanismo de recuperación de "evento pendiente" que ya existe en `frontend/src/components/MesaPanel.tsx:377`** ("El evento pendiente no se pudo guardar — cargalo de nuevo."), en vez de agregar una segunda afordancia de reintento. Hoy el plan sumaría una segunda y no dice cómo componen; un 409 sobre un evento pendiente dispararía las dos. Verificación: hay un solo camino de recuperación en la UI de mesa y el 409 entra por él.
- **A3 llama a los servicios directo, no por las rutas, y eso se escribe en el bosquejo de una página que A2 ya tiene como precondición.** Verificado: la fixture `client` (`backend/tests/conftest.py:127-145`) sobreescribe `get_db` con la `db_session` única y compartida, así que dos sesiones genuinamente independientes no pueden pasar por ella. Consecuencia que hay que nombrar antes de empezar: A3 prueba el invariante del servicio pero NO el camino HTTP, así que `verificar_arbitro_asignado`, `require_roles` y el mapeo del handler a 409 quedan sin cubrir por A3 y llevan su propio test con la fixture `client`. Descubrir esto a mitad de A2 es exactamente el riesgo de cronograma que el plan ya señala. Verificación: el bosquejo lo dice y existe el test HTTP del 409 aparte.
- **REGRESIÓN (obligatoria, sin pregunta): test que afirma que NADA persiste a mitad de camino si el request falla después del insert y antes del commit.** A1 cambia comportamiento existente: hoy `repo.create()` commitea (`backend/app/repositories/base.py:43-48`) y un fallo posterior deja el evento escrito; después de A1 no debe quedar nada. Se suma el barrido: grepear los tests existentes que crean dos eventos en secuencia y afirman persistencia intermedia, porque son los que el commit-por-evento venía sosteniendo en silencio. Verificación: ese test falla contra el código de hoy y pasa después de A1, más los 486 tests existentes en verde.
- **Test del invariante real de A1: la roja automática cae en la MISMA transacción que la segunda amarilla.** "Dos amarillas producen una roja" ya pasa hoy en el caso secuencial, así que no prueba lo que A1 compra. Verificación: el test afirma atomicidad, no solo el resultado final.
- **El guard de nombre de base va al PRINCIPIO de `_recreate_test_database`, no delante del `DROP DATABASE`.** SUPERSEDE parcial de la obligación de Fase 1, que lo ata al DROP. Verificado: dentro de `backend/tests/conftest.py:67-75`, el `pg_terminate_backend(pid) ... WHERE datname = $1` corre en la línea 71 y el `DROP DATABASE IF EXISTS` en la 75 — un nombre mal apuntado mata todas las conexiones vivas a `torneos_mvp` antes de llegar al DROP guardado. Verificación: el test unitario que apunta el helper a `torneos_mvp` afirma que levanta ANTES de ejecutar el terminate, no solo antes del DROP.
- **C2a lleva un test automatizado compañero además del recorrido humano.** La corrección de Fase 2 acierta en que no existe camino `sinConvocatoria` hacia `ModalSustitucion`, pero su reemplazo (C2a construye la lista con fallback a plantilla, gateado en "un árbitro completa un cambio de punta a punta") quedó sin verificación automatizada, y entonces el invariante de Fase 1 de "la cuenta de tests de Cambio no baja" no tiene contra qué contar, porque los tests viejos de `CargaEvento` se mudan a un camino que no existía cuando se tomó la cuenta. El test compañero afirma dos cosas: que la lista de fallback renderiza con su caption, y que un Cambio enviado desde ella produce el mismo body de POST que el camino con convocatoria. El recorrido humano queda encima, no en lugar de. Verificación: ese test existe y pasa antes del retiro de C2b.
- Antes de comprometerse con `addopts = --strict-markers` se corre `pytest --collect-only -W error::pytest.PytestUnknownMarkWarning`: convierte un aviso en fallo duro sobre 49 archivos de test que nunca se chequearon. Y se deja escrito que `addopts` en `pytest.ini` compone con el `-q` de `verificar.ps1:46`. Verificación: la corrida de colección pasa limpia antes del commit que agrega el flag.
- Si B1 se reabre, `incluir_no_inscritos=true` lleva un test que afirma que `torneo_ids_permitidos` SIGUE aplicando con el flag puesto. Implementado de forma ingenua como "saltear el filtro", es un bypass de autorización alcanzable por query string. Verificación: el test afirma que un TorneoAdmin con el flag no ve filas fuera de sus torneos asignados.
- El test del 403 de F1 maneja un token real de `TorneoAdmin` a través de la ruta, no una aserción sobre el string del rol: `require_roles` hace bypass para `AdminGeneral` (`backend/app/api/deps.py:130`), así que un test mal armado pasa sin probar nada. Verificación: el test usa la fixture `client` con un token de TorneoAdmin.
- **La verificación de D1 se declara VISUAL Y MANUAL en el plan.** JSDOM no prueba grid areas, ni `position: sticky`, ni targets de 44px, así que dejar que "`MesaPanel.test.tsx` no se mueve" se lea como prueba sería falso. Se agrega la advertencia concreta: `position: sticky` falla en silencio bajo cualquier ancestro con `overflow` scrollable, y `frontend/src/index.css` mezcla `min-width` (800/1000) con `max-width` (480/640), así que hay que inspeccionar la cadena de ancestros a 375px. Verificación: el plan dice que D1 se verifica a ojo, en un dispositivo, y lista los tres puntos a mirar.
- **El cuerpo del plan se corrige ANTES de que arranque la ejecución, no como tarea al final.** Refuerza la obligación de Fase 2.5 y sube su prioridad a bloqueante de arranque. Las cuatro contradicciones vivas hoy: A1 = cambiar a `get_or_404_bloqueado` (cuerpo) contra "ese cambio no cierra la carrera" (corrección); B2 = escribir y commitear el `.sql` (cuerpo) contra "ya corrió, no se commitea" (corrección); orden serial `A0→A1→A2→A3→C1…` (cuerpo) contra `A0→A1→C1→C2a→C2b→D1→exp.1→A2→A3` (corrección); el gate de merge de C2 de Fase 1 contra "ese gate es inaplicable" de Fase 2. Mientras no se aplique, el grafo de dependencias del cuerpo instruye activamente a empezar trabajo diferido. Verificación: `git status` limpio y el cuerpo corregido en el commit anterior al arranque de A1.
- **La parte frontend de A1 (leer `error.detail`, mostrar el reintento) se hace DESPUÉS de D1, dentro del mismo lane que reorganiza `MesaPanel.tsx`; el lane de A1 queda backend puro.** A1 tocaría `frontend/src/api/client.ts` y `frontend/src/components/MesaPanel.tsx`, y D1 reorganiza `MesaPanel.tsx` entero: correr los dos lanes en paralelo choca en ese archivo. Esto además respeta la obligación de Fase 1 de mantener `MesaPanel.tsx` fuera del commit del baseline. Verificación: ningún commit toca `MesaPanel.tsx` desde dos tracks a la vez.
- A1 declara su resultado observable en términos medibles, no solo "tests verdes": el p95 de `POST /eventos-partido` antes y después. El plan ya exige un resultado observable por track (obligación de Fase 1) y este es el de A1. Verificación: los dos números escritos en el track antes de cerrarlo.
<!-- /autoplan-accepted:eng -->
## Review record

### Fase 1 — CEO review (SELECTIVE EXPANSION, single-model)

Voces: nativa Claude subagent **completada** (INPUT hash
`74295417…217e6c` verificado). Codex **no disponible**
(`CODEX_MODE: not_installed`) — fase etiquetada `[single-model]`, las 6 celdas
de consenso quedan `N/A`, nunca `CONFIRMED`.

#### Auditoría previa del sistema

- `git stash list` vacío. Sin trabajo escondido.
- **Cero marcadores TODO/FIXME/HACK reales en el código del proyecto.** Los 20
  hits son la palabra española "todo/TODOS" en comentarios y referencias a
  `TODOS.md`. Es una señal buena y poco común: la deuda de este repo está
  documentada en `TODOS.md`, no dispersa en comentarios.
- Archivos más tocados en 30 días: `frontend/src/index.css` (19),
  `TODOS.md` (19), `frontend/src/api/schema.d.ts` (17),
  `database/02_constraints.sql` (16), `database/01_schema.sql` (16). El CSS y el
  esquema son los puntos calientes — D1 toca el primero, F1 el segundo.
- Doc de diseño encontrado:
  `docs/designs/frontend-inicial-dashboard-mesa-en-vivo.md` (206 líneas),
  directamente relevante a D1.
- **Chequeo retrospectivo:** `git log` muestra 7 commits consecutivos de
  "cierre backlog TODOS.md" (`a1f2c6d`..`3c1eed6`, fases 3A y 3B). Este plan es
  la octava iteración del mismo ciclo. Que el mismo archivo vuelva ocho veces
  no es un olor arquitectónico del código, pero sí dice algo del proceso: el
  backlog se cierra por secciones, y las secciones se rellenan.

**Mediciones contra la base de dev (`torneos_mvp`).** Corregidas tras el spec
review: la base tiene datos de prueba de estrés que dejó
`backend/scripts/mock_estres_catalogo.py` a propósito, así que **los totales
crudos no miden uso** y hay que separarlos:

| Tabla | Crudo | Sintético (`MOCK-%` / grupo "Prueba de Estrés") | **Orgánico** |
|---|---|---|---|
| `JUGADORES` | 1787 | 1750 (`MOCK-%`) | **37** |
| `TORNEO` | 83 | 68 (grupo "Prueba de Estrés") | **15** |
| `EQUIPOS` | 270 | **260** (inscriptos en grupos de estrés) | **10** |
| `DISCIPLINA` | 28 | 0 | **28** |
| `PARTIDOS` | 13 | — | 13 |
| `EVENTOS_PARTIDO` | 35 | — | 35 |
| `AUDITORIA` (total) | 287 | — | 287 |
| `AUDITORIA` tabla `usuarios` | **0** | — | **0** |
| `ACCESOS` (total) | 20 | — | 20 |
| `ACCESOS` con `Motivo='licencia_revocada'` | **0** | — | **0** (de 20 reales) |
| 2 amarillas sin roja registrada | 0 | — | 0 (pero ver abajo) |
| `DISCIPLINA` con `Estado` NULL | 0 | — | 0 |

**Corrección de la revisión 3 — la celda de `EQUIPOS` estaba sin medir y era
justamente la premisa de E1.** Medida: **260 de 270 equipos** están inscriptos
en torneos del grupo "Prueba de Estrés", con jugadores `MOCK-`. **Orgánico: 10
equipos**, es decir el **5%** del tope de 200, no el 135%. El banner de
truncado de `EquiposAdmin` existe y funciona, pero **solo lo dispara data
sintética**: nada orgánico se acercó nunca al tope. El diferimiento de E1 no
cambia — se vuelve mucho más sólido — pero el motivo que la revisión 2 le puso
era falso, y hay que corregirlo (abajo, Premisa 3).

**Corrección de la revisión 3 — la fila de "2 amarillas sin roja" contesta la
pregunta equivocada.** El único jugador con 2 amarillas (partido 12, jugador
1779, minutos 3 y 5, cédula `0134567890`, o sea orgánico) **sí** tiene una roja
registrada, pero **no es la automática**: está al **minuto 55**, y
`procesar_doble_amarilla` crea la roja siempre en el minuto de la segunda
amarilla (`reglas_tarjetas.py:65-72`, `minuto=minuto`). Y el dato decisivo:
los eventos de ese partido son del **2026-09-08 18:35-18:41**, mientras que
`backend/app/services/reglas_tarjetas.py` se commiteó por primera vez el
**2026-09-14** (`b7b2feb`), seis días después. **La regla no existía cuando se
cargaron esos eventos.**

La afirmación correcta, entonces, no es "el bug nunca ocurrió" sino algo más
fuerte y más incómodo: **la regla de doble amarilla no tiene ni un solo
ejercicio sobre datos reales, y el único caso real de doble amarilla de la base
es anterior a la regla.** Eso refuerza Track A en vez de debilitarlo — no hay
evidencia de que la red de seguridad haya sostenido nunca, porque nunca se
probó.

#### 0A. Desafío de premisas

**Premisa 1: "cerrar la sección Pendiente de TODOS.md es un objetivo."**
**Cuestionada.** Es higiene de backlog, no un resultado. Los 9 ítems no
comparten usuario, ni problema, ni métrica; comparten un encabezado de
markdown. La verificación del plan es `pytest` verde + editar `TODOS.md`, todo
interno. Un plan puede cumplir todos sus criterios y no mover nada para nadie.
Aceptada como **pedido literal del usuario** (P6), pero con un resultado
observable agregado por track (ver 0D) para que el plan pueda priorizarse.

**Premisa 2: "los 9 ítems están 'ya evaluados, falta ejecutar'."**
**Falsa para 3 de los 9.** El propio plan descubre que la premisa de B1 no se
sostiene (equipos y jugadores no pertenecen a un torneo), y desarma la
estimación Effort L de F1. Las mediciones de arriba desarman E1. "Ya evaluado"
describía el estado en el momento de escribir `TODOS.md`, no hoy.

**Premisa 3: "paginación con cursor resuelve un problema en `/equipos` y
`/jugadores`." Refutada, pero por otro motivo que el de la revisión 1.**
El argumento original ("~10k es el umbral de degradación, hay 5.6x de margen")
**se retira**: era una estimación disfrazada de medición, y además apunta a un
riesgo que no puede ocurrir. `limit` está topado en `le=200` (`equipos.py:21`,
`jugadores.py:42`) y **ningún cliente manda `skip`** (cero llamadas con
`skip=` en `frontend/src`), así que `offset` es permanentemente 0 y la
degradación por offset es inalcanzable con cualquier cantidad de filas.

El motivo correcto (corregido en la revisión 3, porque la revisión 2 también se
equivocó acá): **los listados orgánicos están a un orden de magnitud del tope,
y el mecanismo de escape ya existe.**

- **Orgánico: 10 equipos y 37 jugadores.** El tope de página es 200. Están al
  5% y al 18% respectivamente.
- La revisión 2 argumentaba que "el techo de 200 ya se alcanza en `EQUIPOS`
  (270 filas) y ya está mitigado". **Falso**: 260 de esos 270 son equipos de
  prueba de estrés. El banner de truncado de
  `frontend/src/pages/torneo-admin/EquiposAdmin.tsx:258` se dispara hoy, sí,
  pero **solo por data sintética**. Presentarlo como "una mitigación
  funcionando en producción" era incorrecto: nada orgánico llegó nunca ahí.
- El mecanismo de escape sí existe y está construido:
  `frontend/src/hooks/useResourceCrud.ts:40,131` define `LIMITE_LISTA = 200` y
  calcula `truncado`, el banner avisa, hay filtro server-side por disciplina y
  categoría, y `useNombrePorIdConFaltantes` resuelve por ID lo que quede
  afuera.
- Y **no hay p95 medido** en ninguno de los dos endpoints.

Lo que falta no es paginar: es navegar por búsqueda y filtro, que ya está.

**Premisa 4: "editar el catálogo de disciplinas desde la UI hace falta."**
**Sin evidencia de demanda.** `DISCIPLINA` tiene exactamente 28 filas, el mismo
número que carga `11_catalogo_disciplinas.sql`. **Nadie agregó una sola
disciplina desde el seed.** Y el ítem revierte la Decisión C1 de
`docs/plans/ediciones-catalogo-disciplinas-plan.md`, que hizo el catálogo de
solo lectura a propósito.

**Premisa 5: "los datos de revocación de licencia ya están en `AUDITORIA`."**
**Mecánicamente cierta, empíricamente vacía — en las dos mitades.** Verificado:
`_TABLAS_EXCLUIDAS = {"auditoria","accesos"}` (`app/core/auditoria.py:53`) no
excluye `usuarios`, y `_CAMPOS_REDACTADOS` redacta `usuarios.password_hash`
(línea 58), lo que prueba que el listener cubre esa tabla. Pero:

- Mitad "contador de otorgadas/revocadas": `AUDITORIA` tiene **cero filas de
  `usuarios`** en 287, y los 3 usuarios tienen `Licencia_Activa = True` sin
  haber sido tocada nunca.
- Mitad "pico de 403 post-revocación" (que la revisión 1 no midió): `ACCESOS`
  tiene **cero filas con `Motivo='licencia_revocada'`** — sus únicos motivos
  son `credenciales` (3) y NULL (17).

La consulta de B2 devolvería cero filas en ambas mitades, para un evento que
ocurrió cero veces.

**Trampa de casing, detectada en el spec review:** el plan revisado dice
filtrar `Tabla='USUARIOS'` en mayúscula. `AUDITORIA.Tabla` guarda
`obj.__tablename__`, que es minúscula (`usuarios`), así que ese filtro
devolvería 0 **siempre, por casing**, no por falta de datos — un cero falso que
habría "confirmado" la conclusión correcta por el motivo equivocado. Las
mediciones de arriba se hicieron case-insensitive.

**Premisa 6: "si no hacemos nada, pasa algo malo."** Cierta solo para A1. Es
el único ítem con un modo de fallo que corrompe datos sin que nadie lo vea.

#### 0B. Mapa de código existente (leverage)

| Sub-problema | Código que ya lo resuelve | ¿El plan lo reusa? |
|---|---|---|
| Lock de fila sobre partido | `PartidoRepository.get_or_404_bloqueado` (`repositories/partido.py:16-30`) | Sí — A1 solo agrega un llamador |
| Alcance por asignación | `torneo_ids_permitidos` en `torneos.py:47-55` y `partidos.py:136-145`, semántica `None`/`[]` | Sí, pero ver Sección 1 — B1 no puede reusarlo |
| Captura de auditoría | listener ORM `app/core/auditoria.py`, 18 tablas | Sí — B2 solo consulta |
| Métrica versionada | `docs/queries/metricas-desempate-tiempo-extra-penales.sql` | Sí, formato clonado |
| Selector de jugador | `SelectorJugadorBuscable.tsx` + `useDebouncedValue` | Sí — C1 |
| Sustitución | `ModalSustitucion.tsx` + heurística compartida (`MesaPanel.tsx:554-560`) | Sí — C2 |
| Generación de slug | `fn_generar_disciplina_slug` (`06_triggers.sql:449-470`), ya usa `translate()`, no regenera en rename | **El plan no lo sabía** — ver Sección 5 |
| Soft-delete | `Estado` + `chk_disciplina_estado` | Sí — F1 no agrega borrado |
| Roles | `AdminGeneral` + 89 usos de `require_roles`, 4 combinaciones | Sí — F1 no agrega roles |

**¿Reconstruye algo que ya existe?** No en el backend. En el frontend, C1 y C2
existen precisamente para *borrar* reconstrucciones que ya se hicieron.

#### 0C. Dream state

```
  ESTADO ACTUAL                  ESTE PLAN                    IDEAL 12 MESES
  ─────────────                  ─────────                    ──────────────
  Mesa en vivo funciona,     →   Row-lock cierra un      →    Carga en vivo en
  layout apilado en el           hueco de integridad.         teléfono sin errores
  teléfono.                      UI deduplicada.              posibles: el estado
                                 Layout en 3 zonas.           de tarjetas es
  Dos caminos de UI para                                      visible, la segunda
  el mismo Cambio.           →   (B1 muerto, B2         →     amarilla YA es roja
                                 invertido, E1 y F1            en pantalla.
  Portal público en              diferidos por falta
  producción con                 de evidencia)                Portal público que
  pendientes menores.                                         se refresca solo.
                             →   TODOS.md con 9 ítems   →     Backlog que se
  Backlog cerrado por            menos en Pendiente.          vacía por resultado,
  secciones, 8 ciclos.                                        no por sección.
```

**Delta:** el plan mueve la integridad y la limpieza interna hacia el ideal.
No mueve el portal público ni la velocidad de carga en vivo, que es donde este
producto compite. Ver Sección 10.

#### 0C-bis. Alternativas de implementación

```
APPROACH A: Ejecutar los 9 ítems como está escrito
  Summary: 6 tracks, orden por dependencias, cierra la sección Pendiente completa.
  Effort:  XL  (human: ~3-4 semanas / CC: ~6-9 h)
  Risk:    Med-High
  Pros:    Cumple el pedido literal; cierra la sección entera; nada queda a medias.
  Cons:    Gasta el ciclo entero en 2 ítems sin problema medido (E1, F1) y 1 con
           premisa refutada (B1); agrega un contrato de API permanente y un
           fixture de tests no hermético por evidencia que no existe.
  Reuses:  Todo lo del mapa 0B.
  Completeness: 10/10 (cubre los 9 ítems)

APPROACH B: Ejecutar solo lo que tiene evidencia
            (A0 + A1-reestructurado + A2 + A3 + C1 + C2 + D1, y exp. 1 si el Gate la aprueba)
  Summary: Cierra el hueco de integridad real (reestructurando create, no
           parchándolo), deduplica las dos UIs, reorganiza el panel en 3 zonas.
           Descarta B1. Difiere E1/F1/B2 con el número que los desbloquea escrito.
  Effort:  M-L (human: ~1.5 semanas / CC: ~3-4 h)
  Risk:    Low-Med  (la reestructuración de `create` toca el camino en vivo)
  Pros:    Cada ítem tiene un modo de fallo o una duplicación verificada detrás;
           no agrega contratos de API; deja E1/F1/B2 accionables con umbral
           explícito en vez de un "algún día".
  Cons:    No cierra la sección Pendiente completa — 4 ítems siguen abiertos
           (reetiquetados, no ejecutados). No es lo que el usuario pidió literalmente.
           La reestructuración de `create` es más riesgosa que el swap de una línea.
  Reuses:  Todo lo del mapa 0B, más el patrón de transacción única de
           `registrar_resultado_directo` y la preview de `ModalResultadoDirecto`.
  Completeness: 6/10 (5 de 9 ítems ejecutados, 4 resueltos por decisión documentada)

  CORRECCIONES (revisión 2): A0 y A2 faltaban en esta línea — A2 es
  prerrequisito duro de A3 ("sin la fixture, los tests de concurrencia no se
  pueden escribir") y la revisión 1 aceptaba alcance DENTRO de A2 sin agendarla.
  A1 pasa de S a M por el Hallazgo 1.0. Y el recuento va de 6/3 a 5/4: B2 ya se
  ejecutó dentro de esta misma revisión (la consulta ad hoc corrió y dio cero en
  sus dos mitades), así que es un cuarto diferimiento, no un ítem ejecutado.

APPROACH C: Invertir el ciclo — portal público y velocidad de carga en vivo
  Summary: Dejar los 9 ítems donde están y gastar el ciclo en auto-refresh del feed,
           minuto en vivo, y estado de tarjetas visible en el panel.
  Effort:  L   (human: ~2 semanas / CC: ~4 h)
  Risk:    Med
  Pros:    Es lo único de la lista que un usuario real nota; ataca donde el producto
           compite (velocidad de carga en vivo, resultados compartibles).
  Cons:    Ignora el pedido explícito del usuario; deja abierto el hueco de
           integridad de A1, que es barato y real. Sale del alcance pedido.
  Reuses:  `GET /partidos/feed`, `FeedService`, los slugs del portal.
  Completeness: 2/10 respecto de lo pedido (no cierra Pendiente)
```

**RECOMENDACIÓN: Approach B.** Mapea a "engineered enough" y a bias-toward-
action: cada ítem que sobrevive tiene un modo de fallo verificado o una
duplicación contada, y los dos que se caen se caen contra datos medidos, no
contra una opinión. A es completitud sobre un alcance cuya premisa no aguanta
en 3 de 9 puntos — completitud es baratísima con CC, pero completitud sobre el
ítem equivocado sigue siendo el ítem equivocado. C tiene la mejor lectura de
producto y no es lo que se pidió; su contenido va a TODOS.md como el ciclo
siguiente.

**Clasificación: esto es un USER CHALLENGE, no una auto-decisión.** El usuario
pidió cerrar *todos* los pendientes. Recomendar B es recomendar cerrar 6 y
reetiquetar 3. Va al Gate Final.

#### 0F. Selección de modo

**SELECTIVE EXPANSION** (default de /autoplan; también el default contextual
para iteración sobre un sistema existente). El alcance escrito es la línea
base; las expansiones se ofrecen como cherry-picks individuales.
`Note: options differ in kind, not coverage — no completeness score.`

#### 0D. Análisis del modo (SELECTIVE EXPANSION)

**Chequeo de complejidad.** El plan toca, por conteo conservador: 6 tracks,
~10 archivos de backend, ~8 de frontend, `index.css`, `conftest.py`, 2 nuevos
`docs/queries`, `TODOS.md`. Muy por encima del umbral de 8 archivos → olor de
complejidad confirmado, y es el argumento central del Approach B.

**Conjunto mínimo que logra el objetivo declarado.** Si el objetivo es
"integridad + limpieza": A1 + A3 + C1 + C2. D1 es el único con valor visible
para el usuario. B1/B2/E1/F1 son diferibles sin bloquear nada.

**Resultado observable agregado por track** (respuesta al hueco de la
Premisa 1):

| Track | Resultado observable | Cómo se verifica |
|---|---|---|
| A1+A3 | Un jugador con 2 amarillas nunca queda sin roja, ni con dos pestañas abiertas | Test determinista que falla sin el lock |
| B1 | (muerto) | — |
| B2 | Se sabe si alguna licencia fue revocada alguna vez | La consulta corre y da un número |
| C1 | El buscador de jugador se comporta igual en los 3 lugares donde aparece | `DetalleEquipo.test.tsx` nuevo |
| C2 | Un solo camino para cargar un Cambio; la cuenta de tests de Cambio no baja | `MesaPanel.test.tsx` |
| D1 | El mesero ve marcador y reloj sin scrollear en 375px | Inspección en 375px |
| E1 | (diferido) Desbloquea cuando `COUNT(*) > 10000` | Umbral en TODOS.md |
| F1 | (diferido) Desbloquea con la 1ª solicitud real de alta de disciplina | Umbral en TODOS.md |

**Escaneo de expansiones (candidatos, no alcance todavía):**

1. **Estado de tarjetas visible en el panel en vivo.** El reframe: A1 arregla
   el *registro*; no arregla que el árbitro no vea que el jugador ya tiene
   amarilla. La versión 10x de Track A es que la segunda amarilla ya se vea
   roja en pantalla y el estado inconsistente sea imposible de producir. Vive
   en `MesaPanel`, que D1 ya está reorganizando, en el mismo teléfono al borde
   de la cancha que el plan nombra como caso principal.
   Efecto: el árbitro deja de tener que recordar. Effort S
   (human: ~4 h / CC: ~20 min). En radio de acción de D1, <1 día CC.
2. **Guard de nombre de base antes de `TRUNCATE`.** Ver Sección 3 — no es
   expansión, es requisito de seguridad. Auto-aprobado.
3. **Minuto en vivo en la fila del feed** (hoy dice solo "EN VIVO"). Está en
   el Backlog sin urgencia de `TODOS.md`. Effort S. Fuera de radio.
4. **Auto-refresh del feed público** (hoy hay botón "Recargar"). Backlog.
   Effort M. Fuera de radio.
5. **Umbral medido en vez de "algún día"** para E1 y F1: escribir el número
   exacto que los desbloquea. Effort XS (human: ~10 min / CC: ~2 min).
   Convierte dos diferimientos vagos en dos disparadores accionables.

Cherry-picks 1, 2 y 5 se recomiendan; 3 y 4 quedan como el ciclo siguiente
(fuera de radio, P3, van a `TODOS.md`).

#### 0E. Interrogación temporal

```
  HORA 1 (fundaciones):   ¿El baseline ReglamentoTorneo está commiteado? Si no,
                          nada más empieza. ¿A1 es un cambio de una línea o el
                          lock cambia la forma de la transacción? (Es de una línea.)
  HORA 2-3 (core):        ¿ModalSustitucion cubre `sinConvocatoria`? Si no, se
                          agrega ANTES de retirar el camino viejo (C2 punto 1).
                          ¿Cuál de los dos hooks es "el de resolución de nombres",
                          useEtiquetaJugadorPorPerfil o useFetchFaltantes?
  HORA 4-5 (integración): ¿SelectorJugadorBuscable soporta confirmación de
                          conflicto y alta inline, o se quedan alrededor? Sorpresa
                          probable: el selector se vuelve un componente con 6 props
                          opcionales y deja de ser el "compartido" que era.
  HORA 6+ (pulido/tests): Van a desear haber decidido la asignación de zonas de D1
                          antes de tocar 2315 líneas de CSS, y haber contado los
                          tests de Cambio ANTES de editar MesaPanel.test.tsx.
```

#### Step 0.5 — Voces duales

**Claude SUBAGENT (CEO — independencia estratégica): completada.** 11
hallazgos. Veredicto: "well-researched plan and a poorly framed one";
recomienda A1+C1+C2+D1, matar B1, invertir B2, diferir E1 y F1. Coincide
independientemente con el análisis primario en los cuatro puntos de alcance.
Aportó dos cosas que el análisis primario no tenía: el reframe del panel
(candidato de expansión 1) y el riesgo de los dos nombres de base a una letra
de distancia (Sección 3).

**Codex (CEO — desafío de estrategia): no disponible** (`not_installed`).
Sin cobertura externa en esta fase.

```
CEO DUAL VOICES — CONSENSUS TABLE:
═══════════════════════════════════════════════════════════════
  Dimension                            Claude  Codex  Consensus
  ──────────────────────────────────── ─────── ─────── ─────────
  1. Premises valid?                   NO      —      N/A
  2. Right problem to solve?           NO      —      N/A
  3. Scope calibration correct?        NO      —      N/A
  4. Alternatives sufficiently explored? NO    —      N/A
  5. Competitive/market risks covered? NO      —      N/A
  6. 6-month trajectory sound?         PARTIAL —      N/A
═══════════════════════════════════════════════════════════════
Cobertura externa ausente → 6 celdas N/A, nunca CONFIRMED. [single-model]
Hallazgos nativos se mantienen separados; sin outside voice no hay
desacuerdo cross-model que resolver.
```

#### Sección 1: Arquitectura

```
  DEPENDENCIAS — ANTES                      DESPUÉS (con este plan)
  ────────────────────                      ───────────────────────
  routes/equipos ──┐                        routes/equipos ──┐
  routes/jugadores─┼─▶ BaseRepository        routes/jugadores─┼─▶ BaseRepository
  routes/torneos ──┤   .list(skip,limit)     ...              │   .list(skip,limit)
  (+9 routes más) ─┘                        (12 routes)       │   + cursor  ◀── E1
                                                              │   (2 contratos)
  torneos.list ────┐                        torneos.list ────┐
  partidos.list ───┴─▶ torneo_ids_permitidos partidos.list ──┤
                                            equipos.list ────┼─▶ torneo_ids_
                                            jugadores.list ──┘   permitidos ◀── B1
                                                                  + EXISTS sobre
                                                                  INSCRIPCION_TORNEO

  EventoPartidoService.create                EventoPartidoService.create
    └─▶ get_or_404                             └─▶ get_or_404_bloqueado ◀── A1
```

**Hallazgo 1.1 (ALTA) — B1 acopla dos recursos globales al modelo de torneos.**
`EQUIPOS` y `JUGADORES` no tienen `torneo_id`; se relacionan vía
`INSCRIPCION_TORNEO`. Filtrar "por asignación" obliga a un `EXISTS` correlado
en el listado más caliente del sistema (1787 jugadores, es el que alimenta el
buscador). Acopla el catálogo global de jugadores al grafo de asignaciones de
torneos, que es exactamente el acoplamiento que `INSCRIPCION_TORNEO` existe
para evitar. *Decisión: matar B1* (P4 — la premisa duplica una relación que ya
está modelada; y el `alcance=` con default permisivo no es autorización).

**Hallazgo 1.2 (ALTA) — E1 deja dos contratos de paginación vivos para
siempre.** El plan propone convivencia con offset "deprecado en el docstring".
Un docstring no deprecia nada: no hay header de sunset, no hay métrica de
adopción, y el único cliente es este frontend. Con 270/1787 filas no hay nada
que pagar por ese costo. *Decisión: diferir E1* (ver User Challenge).

**Hallazgo 1.0 (CRÍTICO — el hallazgo más importante de la fase) — A1 como
está especificado NO cierra la carrera.** Detectado por el spec review loop y
verificado contra el código antes de aceptarlo.

`BaseRepository.create` (`repositories/base.py:43-48`) hace
`session.add(obj)` y después `await self.session.commit()`. Y
`EventoPartidoService.create` (`services/evento_partido.py:72-95`) llama a ese
`repo.create(...)` y **después** a
`_procesar_doble_amarilla_si_corresponde(...)`, que es donde
`procesar_doble_amarilla` **lee** el conteo de amarillas y condicionalmente
inserta la roja, con un `commit()` propio.

```
  get_or_404_bloqueado(partido)  ══ toma FOR UPDATE ══╗
  ...                                                 ║
  repo.create(**datos)                                ║
    └─ session.add(); await session.commit()  ◀══ LIBERA EL LOCK ACÁ
  _procesar_doble_amarilla_si_corresponde()            ║
    └─ lee conteo de amarillas  ◀══ FUERA DEL LOCK ════╝
    └─ inserta roja + commit propio  ◀══ FUERA DEL LOCK
```

El propio docstring de `get_or_404_bloqueado` (`repositories/partido.py:16-27`)
lo dice: "el lock se libera en el `commit()`/rollback ya existente de ese
método". En `registrar_resultado_directo` eso es inocuo, porque ese método
sostiene una sola transacción hasta el final — por eso el helper funciona ahí.
En `create` hay **dos commits en el medio**, así que la lectura-y-escritura que
el lock debía proteger queda afuera.

Cambiar `get_or_404` por `get_or_404_bloqueado` en la línea 76 **no arregla
nada**. Dos requests concurrentes siguen produciendo 2 amarillas / 0 rojas, o
2 rojas.

**El arreglo real:** reestructurar `create` a una sola transacción — no usar el
`repo.create` que auto-commitea, `flush()` en vez de `commit()`, y un solo
`commit()` al final. Es la forma que `registrar_resultado_directo` ya usa, así
que hay precedente en el repo (rung 1 de la escalera de reuso, patrón no
código). **Effort M (human: ~3 h / CC: ~25 min), no los ~15 min estimados.**

*Decisión: A1 se reestructura, no se parchea. Y el rescate de
`DeadlockDetected` del Hallazgo 2.1 queda CONDICIONADO a esta
reestructuración — ver la corrección en esa sección.*

**Hallazgo 1.3 (MEDIA) — 5 tracks "independientes" en un repo de un solo
desarrollador.** El plan presenta la independencia de B1/B2/C1/E1/F1 como
ventaja. Con un desarrollador es ausencia de secuenciación: 5 ramas a medias y
un árbol sucio, que es precisamente la condición que A0 existe para limpiar.
El baseline sin commitear es la evidencia. *Decisión: orden serial con
stop-the-line — nada arranca hasta que el anterior bajó a Resuelto.*

**Escalado.** Lo que se rompe primero a 10x no es la paginación: son los 35
eventos de partido creciendo a 35.000 con el listener de `AUDITORIA`
escribiendo una fila por mutación ORM. `AUDITORIA` ya tiene
`purgar_anteriores_a`, así que el mecanismo existe; lo que no existe es quién
lo llama.

**Puntos únicos de fallo.** El trigger `fn_validar_jugador_partido`
(`06_triggers.sql`) es el único validador de la relación jugador/equipo/partido
— el servicio lo documenta y no lo duplica a propósito. Correcto, y significa
que una migración que lo toque sin test es un fallo de un solo punto.

**Postura de rollback.** A1 = `git revert` de una línea. C1/C2/D1 = revert de
frontend, sin estado persistido. B2 = archivo nuevo, borrarlo. E1/F1 = ambos
tocan contrato o esquema; E1 necesita que ningún cliente haya migrado al
cursor y F1 podría necesitar rollback de migración. Los dos ítems más caros son
también los dos menos reversibles. Refuerza diferirlos.

#### Sección 2: Mapa de error y rescate

```
  MÉTODO/CODEPATH                    | QUÉ PUEDE FALLAR                  | CLASE
  -----------------------------------|-----------------------------------|------------------
  EventoPartidoService.create (A1)   | Lock en orden cruzado → deadlock  | DeadlockDetected
                                     | Lock espera a otra tx larga       | (timeout de tx)
                                     | Partido no existe                 | NotFoundError
                                     | Partido no 'En curso'             | DomainRuleError
  fixture sesiones_paralelas (A2)     | TRUNCATE contra base equivocada   | (sin clase — ver S3)
                                     | Deadlock cruzado → suite colgada  | asyncio.TimeoutError
                                     | Commit real sobrevive al teardown | (fuga de datos)
  metricas-revocacion (B2)           | Cero filas → métrica vacía        | (no es error)
  cursor pagination (E1)             | Cursor malformado/no decodificable| ValidationError
                                     | Cursor apunta a fila borrada      | (silencioso ← GAP)
                                     | Cursor de formato viejo           | (sin versión ← GAP)
  POST /disciplinas (F1)             | Nombre cuyo slug deriva vacío     | IntegrityError
                                     | Estado NULL insertado             | (silencioso ← GAP)
                                     | Disciplina sin modalidades        | DomainRuleError
```

```
  CLASE                    | ¿RESCATADA? | ACCIÓN                      | USUARIO VE
  -------------------------|-------------|-----------------------------|------------------
  DeadlockDetected         | N ← GAP     | —                           | 500 ← MAL
  NotFoundError            | Y           | handlers.py → 404           | "no encontrado"
  DomainRuleError          | Y           | handlers.py → 4xx           | mensaje de regla
  IntegrityError           | Y           | handlers.py → 412           | mensaje de conflicto
  DBAPIError (UndefinedCol)| Y pero MAL  | handlers.py → **400**       | "error de validación"
                           |             |                             | ← oculta la causa
  asyncio.TimeoutError(A2) | Y (planeado)| falla el test con mensaje   | (solo dev)
  TRUNCATE mal dirigido    | N ← GAP     | —                           | pérdida de datos
  Cursor inválido (E1)     | Y (planeado)| 422                         | "cursor inválido"
  Estado NULL (F1)         | N ← GAP     | —                           | fila invisible
```

**Hallazgo 2.1 (ALTA) — `DeadlockDetected` no está rescatado en ninguna parte.**
A1 agrega el segundo `SELECT ... FOR UPDATE` del sistema. Con dos lockers sobre
`PARTIDOS`, un orden cruzado es posible y Postgres aborta una de las
transacciones. Hoy eso sale como 500. *Decisión: A1 incluye rescate explícito
de `DeadlockDetected` → reintento único, y si vuelve a fallar, `DomainRuleError`
con "otro operador está cargando un evento en este partido, reintentá".* El
árbitro ve un mensaje accionable, no una pantalla rota. (P1 completitud: el
lock sin su camino de error es la mitad del arreglo.)

**CORRECCIÓN (revisión 2) — el reintento es INSEGURO hasta que A1 se
reestructure.** Con la estructura de hoy, si el deadlock aparece *después* de
que `repo.create` ya commiteó la amarilla (ver Hallazgo 1.0), un reintento
ciego de `create` inserta una **segunda amarilla**. Y `EVENTOS_PARTIDO` no
tiene unique constraint sobre `(jugador_id, eventos_id)` —
`services/reglas_tarjetas.py` lo dice explícitamente — así que nada la frena.
El reintento convertiría un deadlock en corrupción de datos, que es peor que el
500 que tiene hoy. *Decisión revisada: el reintento se implementa en el mismo
cambio que la reestructuración a transacción única, nunca antes. Si por algún
motivo A1 se hiciera sin reestructurar, el rescate se limita a traducir el
deadlock a un 4xx accionable SIN reintentar.*

**Hallazgo 2.2 (MEDIA, preexistente, fuera de este plan) —
`handlers.py` mapea todo `DBAPIError` a 400.** Ya está registrado como
investigación previa (`migracion-31-portal-publico-no-aplicada`): un
`UndefinedColumn` de Postgres se le presenta al cliente como error de
validación. F1, si agrega columnas, camina directo a ese pozo. *Decisión:
señalarlo (REPO_MODE solo), no arreglarlo en este plan — es una mejora de
observabilidad de alcance propio. A TODOS.md.*

**Hallazgo 2.3 (ALTA) — el cursor de E1 no tiene campo de versión.** Práctica
establecida: incluir versión en el payload del cursor desde el día 1, cueste lo
que cueste (es negligible), porque cambiar el formato después rompe cursores en
vuelo. El plan no lo menciona. *Decisión: si E1 procede, versión obligatoria.
Registrado para cuando se desbloquee.*

#### Sección 3: Seguridad y modelo de amenaza

**Hallazgo 3.1 (ALTA, seguridad de datos) — operación destructiva sin guard de
nombre de base.** `torneos_mvp` (dev) y `torneos_mvp_test`. `conftest.py`
deriva el nombre de test de
`settings.test_database_url or database_url.rsplit("/",1)[0] + "/torneos_mvp_test"`
(`conftest.py:50-53`) — si `TEST_DATABASE_URL` queda mal seteada en `.env`, el
fallback se arma a partir de donde apunte `DATABASE_URL`.

**CORRECCIÓN (revisión 2), y el alcance del guard cambia.** La revisión 1 decía
"a una letra de distancia", que es falso: los nombres difieren en el sufijo
`_test`, 5 caracteres. Más importante, la revisión 1 proponía el guard para un
`TRUNCATE` que **todavía no existe** (no hay ningún `TRUNCATE` en el repo hoy)
mientras que `_recreate_test_database` ya ejecuta
`DROP DATABASE IF EXISTS "{TEST_DB_NAME}"` (`conftest.py:~73`) **hoy, sin
ningún guard de nombre** — y un `DROP DATABASE` es estrictamente peor que un
`TRUNCATE`. El guard protegía lo hipotético e ignoraba lo real.

*Decisión (auto-aprobada, no es expansión — es un guard de operación
destructiva): el guard verifica el nombre de la base contra un patrón test-only
(`%_test`) y levanta ANTES de ejecutar, aplicado al `DROP DATABASE` que ya
existe **y** a cualquier `TRUNCATE` que agregue A2. Amenaza: probabilidad
media × impacto alto (perder `torneos_mvp` es perder la base de dev entera).
Si el Gate corta A2, el guard del `DROP DATABASE` **sigue siendo necesario** y
pasa a TODO propio — no depende de A2.*

**Hallazgo 3.2 (ALTA) — B1 no es autorización.** Un parámetro `alcance=` que el
cliente elige, con default que preserva el comportamiento actual, no restringe
nada: cualquier cliente manda `alcance=disciplina` y ve todo. Si hay una fuga
real de datos entre TorneoAdmins, el arreglo es scoping forzado en el servidor
sin opt-out del cliente, que es una decisión más grande y con su propio ciclo.
Vender el parámetro como mejora de seguridad sería teatro con costo de
mantenimiento. *Decisión: matar B1; si hay fuga, es otro plan.*

**Hallazgo 3.3 (MEDIA) — F1 amplía superficie de escritura sobre el catálogo
maestro.** `POST /disciplinas` gateado a `AdminGeneral` es correcto (más
estricto que el `TorneoAdmin` del toggle actual). Validación de entrada
requerida: `Nombre` cuyo slug derivado sea vacío (nombre todo-puntuación, o no
latino) produce `Slug = ''`, que pasa el `NOT NULL` y colisiona con
`unique_disciplina_slug` en el segundo caso. Probabilidad baja, impacto medio.
*Decisión: si F1 procede, validar que el slug derivado sea no vacío.*

**Resto de la superficie.** A1/A3/C1/C2/D1 no agregan endpoints, ni params, ni
secretos, ni dependencias. C1/C2/D1 son frontend sobre endpoints existentes.
Sin PII nueva. Sin vectores de inyección nuevos (el `EXISTS` de B1 habría sido
el único SQL nuevo, y muere). Auditoría: el listener ORM ya cubre las 18 tablas
de negocio.

#### Sección 4: Flujo de datos y casos borde de interacción

```
  A1 — EVENTO EN VIVO, DOS REQUESTS CONCURRENTES
  ══════════════════════════════════════════════
  SIN LOCK (hoy):
  req A: get_or_404(12) ─▶ estado='En curso' ─▶ cuenta amarillas=1 ─┐
  req B:   get_or_404(12) ─▶ estado='En curso' ─▶ cuenta amarillas=1 ─┤
  estado compartido:  [amarillas jugador X = 1]                      │
  resultado:   A inserta amarilla #2 (sin roja) ◀───────────────────┘
               B inserta amarilla #3 (sin roja)
               ▶ jugador con 2-3 amarillas, CERO rojas, sigue en cancha

  CON LOCK (A1):
  req A: get_or_404_bloqueado(12) ═══ FOR UPDATE ═══▶ cuenta=1 ─▶ inserta #2
                                                      ─▶ procesar_doble_amarilla
                                                      ─▶ inserta ROJA ─▶ commit
  req B:                    (espera el lock) ─────────────────▶ cuenta=2 ─▶ ya hay roja
  estado compartido:  [amarillas=1] ──────────────▶ [amarillas=2, rojas=1]
```

Ambos órdenes de finalización evaluados: A-antes-que-B y B-antes-que-A dan el
mismo resultado con el lock, porque el segundo en entrar lee el conteo ya
actualizado. El orden que queda sin cubrir es **deadlock cruzado** con
`registrar_resultado_directo`, que toma el mismo lock sobre la misma fila
(`services/partido.py:198`) — mecanismo que lo previene: ninguno; de ahí el
Hallazgo 2.1.

```
  INTERACCIÓN              | CASO BORDE                | ¿CUBIERTO? | CÓMO
  -------------------------|---------------------------|------------|------------------
  Carga de evento (A1)     | Doble-tap                 | SÍ (A1)    | FOR UPDATE
                           | Deadlock cruzado          | NO ← GAP   | → Hallazgo 2.1
                           | Árbitro sin conexión      | SÍ (ya)    | mesa-offline-aviso
  Buscador de jugador (C1) | Cero resultados           | SÍ (ya)    | "Ningún jugador coincide"
                           | Jugador ya inscrito       | SÍ (ya)    | confirmación de conflicto
                           | Alta inline + conflicto   | ? ← verificar en C1
  Cambio (C2)              | Partido sin convocatoria  | ? ← GAP    | C2 punto 1, orden fijo
                           | Tope de cambios alcanzado | SÍ (ya)    | maximoCambios
  Panel en vivo (D1)       | 375px, marcador off-screen| NO ← GAP   | es lo que D1 arregla
                           | Estado de tarjetas oculto | NO ← GAP   | → expansión 1
  Listado (E1/B1)          | 10.000 resultados         | N/A        | hay 1787, tope 200
```

**Hallazgo 4.1 (ALTA) — el orden de C2 es un invariante, no una preferencia.**
Si `ModalSustitucion` no maneja `sinConvocatoria` y se retira primero el camino
viejo, un partido sin convocatoria guardada se queda **sin ninguna forma de
cargar un Cambio**. El plan lo dice; lo eleva a invariante verificable: *el
retiro no se mergea hasta que exista un test de `ModalSustitucion` con
`sinConvocatoria=true`.*

#### Sección 5: Calidad de código

**Hallazgo 5.1 (MEDIA) — el plan reconstruye lógica de slug que el trigger ya
hace.** F1 punto 2 propone "Slug se genera al crear y no se edita". Verificado:
`fn_generar_disciplina_slug` (`06_triggers.sql:449-470`) ya lo hace, ya usa
`translate(lower(Nombre),'áéíóúüñ','aeiouun')` (correcto — este repo no tiene
`unaccent`, y `translate` es `IMMUTABLE`), y ya preserva el slug en rename
(`IF TG_OP='INSERT' OR NEW.Slug IS NULL`, comentario M7, para no romper deep
links). *Decisión: F1 no escribe nada de slug en Python. Rung 1 de la escalera
de reuso. Corrige el plan.*

**Hallazgo 5.2 (MEDIA) — `list_con_modalidades` tiene `limit=200` hardcodeado.**
`services/disciplina.py:30`: `self.repo.list(skip=0, limit=200, estado=estado)`.
Con 28 disciplinas es invisible. Si F1 deja agregar disciplinas sin techo, es
truncado silencioso del catálogo — la clase de fallo que la Prime Directive #1
prohíbe. *Decisión: si F1 procede, el 200 mágico sale.*

**Hallazgo 5.3 (BAJA) — riesgo de que C1 mate al componente compartido.**
`SelectorJugadorBuscable` hoy tiene un llamador. Si absorbe confirmación de
conflicto + alta inline + resolución de nombres como props opcionales, termina
con ~6 props booleanas y deja de ser "compartido" para ser "configurable", que
es el olor de premature abstraction. *Decisión: C1 mantiene el selector
haciendo búsqueda; conflicto y alta se quedan alrededor en `DetalleEquipo`. P5
— explícito sobre clever.*

**Chequeo de sub-ingeniería.** B2 tal como está escrito commitea el artefacto
antes de saber si hay señal, y el plan pre-admite el resultado probable ("sin
volumen suficiente"). El precedente citado
(`metricas-desempate-tiempo-extra-penales.sql`) funcionó como investigación de
una sola vez cuyo resultado fue a `TODOS.md`, no como métrica recurrente: no
tiene cadencia ni dueño. *Decisión: invertir B2 — correr la consulta ad hoc
primero; commitear el `.sql` solo si hay señal que valga releer.*

#### Sección 6: Tests

```
  NUEVOS FLUJOS UX:
    C1 buscador unificado en DetalleEquipo / ModalAgregarInscripcion / ModalGestionarPlantilla
    C2 único camino de Cambio (ModalSustitucion)
    D1 panel en 3 zonas
    (expansión 1) estado de tarjetas visible

  NUEVOS FLUJOS DE DATOS:
    A1 create() bajo FOR UPDATE
    (B1 muerto — sin flujo nuevo)

  NUEVOS CODEPATHS:
    A1 rama de DeadlockDetected (Hallazgo 2.1)
    F1 POST /disciplinas, PATCH ampliado   [diferido]
    E1 decodificación de cursor            [diferido]

  NUEVO TRABAJO ASYNC:
    A2 fixture de 2 sesiones con commit real

  NUEVAS INTEGRACIONES: ninguna

  NUEVOS CAMINOS DE ERROR/RESCATE:
    A1 DeadlockDetected → reintento → DomainRuleError
    A2 guard de nombre de base → levanta antes de TRUNCATE
```

| Ítem | Tipo | ¿Existe? | Happy path | Camino de fallo | Borde |
|---|---|---|---|---|---|
| A1 lock | Integración | NO | evento se carga normal | 2ª amarilla → roja automática | deadlock cruzado |
| A1 deadlock | Integración | NO | — | reintento único y después 4xx | ambos órdenes |
| A2 guard base | Unit | NO | matchea `%_test` | levanta contra `torneos_mvp` | `TEST_DATABASE_URL` vacía |
| A3 T23 titulares | Concurrencia | NO (secuencial sí) | uno gana | el otro falla con regla | vía `ReglamentoTorneo` |
| A3 T24 Fin_Partido | Concurrencia | NO (secuencial sí) | uno cierra | el otro no re-cierra | ambos órdenes |
| C1 | Componente | **NO — se crea** | búsqueda devuelve filas | cero resultados | conflicto + alta inline |
| C2 | Componente | SÍ, hay que migrar | Cambio por modal | `sinConvocatoria=true` | cuenta de tests no baja |
| D1 | Visual | no aplica | — | — | 375px sin scroll |

**Hallazgo 6.1 (ALTA) — la cuenta de tests es el invariante de C2, y el plan lo
acertó.** "Si la cuenta de tests de Cambio baja, el cambio está mal" es un
invariante verificable en vez de una intención. Se conserva tal cual y se le
agrega el número concreto: contar los tests de Cambio en `MesaPanel.test.tsx`
(208 líneas) **antes** de editar.

**Hallazgo 6.2 (ALTA) — A3 depende de A2, y la frecuencia medida del bug es
CERO.** Medición completada en la revisión 2 (el spec review señaló, con razón,
que la revisión 1 no había cerrado esta consulta): amarillas agrupadas por
`(Partidos_ID, Jugador_ID)` con `HAVING COUNT(*)>=2` y `NOT EXISTS` de una roja
del mismo jugador en el mismo partido → **vacío**. El único jugador con 2
amarillas (partido 12, jugador 1779, minutos 3 y 5) **sí** tiene su roja
registrada.

**Corregido en la revisión 3:** esa consulta contesta "¿hay un registro roto?"
y la respuesta es no. Pero la pregunta que importa es "¿la regla automática
alguna vez funcionó?", y ahí la respuesta es **nunca se probó**. El único caso
real de doble amarilla (partido 12, jugador 1779, orgánico) es del
**2026-09-08**, y `reglas_tarjetas.py` se commiteó el **2026-09-14** — seis
días después. La roja que ese jugador tiene está al minuto 55, no al minuto de
la segunda amarilla (5), así que es una roja directa cargada a mano, no la
automática.

Así que: **la regla de doble amarilla tiene cero ejercicio sobre datos
reales.** Eso refuerza la justificación en vez de debilitarla, y cambia cuál
es el argumento, no la decisión.

*Track A no se justifica por frecuencia — se justifica por consecuencia.* Un
registro disciplinario incorrecto en un partido ya cerrado no se puede
arreglar después (no hay flujo de corrección de tarjetas retroactivo), y el
modo de fallo es silencioso: nadie se enteraría. Prime Directive #1. Esa razón
alcanza sola, y es más honesta que "pasó una vez de 35".

**Y corrige una asimetría real de la revisión 1**, que el spec review nombró
bien: se difería E1/F1/B2 *porque* dev está vacío, y se expandía Track A sobre
1 caso en 35. O el volumen de dev es evidencia o no lo es. Ahora los
diferimientos usan la fórmula que el propio repo ya usa para la Fase 3 del
desempate ("no es un 'no' definitivo, es 'todavía no hay señal'") y Track A se
apoya en consecuencia. Coherente en las dos direcciones.

*Decisión: TASTE — fixture completa (A2 entera, Completeness 10/10) vs test
determinista a nivel de servicio con dos sesiones controladas por punto de
pausa (Completeness 7/10, sin romper el modelo hermético). Recomiendo la
fixture completa con el guard del Hallazgo 3.1, porque T23/T24 piden 2
conexiones reales y ya están anotados como pendientes de infraestructura en
`test_fin_forzado.py:7-8` — pero con frecuencia medida cero, la opción
determinista es defendible y más barata. Va al Gate.*

**Test que da confianza un viernes 2am:** el de doble amarilla concurrente. Es
el único cuyo fallo corrompe el resultado de un partido real.
**Test de un QA hostil:** dos pestañas, la misma tarjeta, tap simultáneo,
mientras un tercer request cierra el partido.
**Test de caos:** matar la conexión entre el `flush()` de la amarilla y el de la
roja automática.

**Pirámide.** El repo está sano: 486 funciones de test backend / 52 archivos y
37 archivos de frontend, casi todo unit e integración. A3 agrega los primeros
tests de concurrencia real — pocos y arriba, que es donde van.
**Riesgo de flakiness:** A3 es la única fuente nueva, y es real (orden de lock).
Mitigado por el `asyncio.wait_for` que el plan ya propone.
**LLM/prompts:** `CLAUDE.md` no tiene patrones de prompt/LLM. No aplica.

#### Sección 7: Performance

**Hallazgo 7.1 (ALTA) — E1 optimiza lo que no está lento, medido.** 270 equipos
/ 1787 jugadores, `limit` topado en 200, `ORDER BY id` sobre PK indexada. El
peor offset real descarta ~1600 entradas de índice. No hay N+1 nuevo, no hay
índice faltante, no hay p95 citado. La queja real detrás del ítem es más
probablemente "el listado de jugadores es incómodo de navegar", que es un
problema de búsqueda/filtro (`q` ya existe), y el cursor no lo arregla.
*Decisión: diferir E1 con umbral explícito — se desbloquea con
`COUNT(*) > 10000` en cualquiera de las dos tablas, o con un p95 medido por
encima del presupuesto.*

**Hallazgo 7.2 (MEDIA) — B1 habría metido un `EXISTS` correlado en el listado
más caliente.** 1787 jugadores, y es el endpoint que alimenta el buscador con
debounce (se llama por tecleo). Muere con B1.

Índices: A1 no agrega consultas. B2 lee `AUDITORIA`, que ya tiene
`idx_auditoria_fecha`, `idx_auditoria_tabla_registro`, `idx_auditoria_usuario`
(`03_indexes.sql:134-136`) — la consulta de B2 filtra por `Tabla` y ordena por
`Fecha`, ambos cubiertos. Memoria: la fixture de A2 mantiene 2 conexiones
extra del pool durante los tests de concurrencia; con `-m concurrencia`
aparte, sin presión. Caché: nada que cachear.

#### Sección 8: Observabilidad

**Hallazgo 8.1 (ALTA) — A1 agrega un camino de espera invisible.** Un
`FOR UPDATE` que espera no deja rastro: si dos árbitros se pisan seguido, nadie
lo ve, y el síntoma que llega es "la app se siente lenta al cargar tarjetas".
*Decisión: A1 loguea cuando el lock esperó por encima de un umbral, con
`partido_id` y `usuario_id`. Observabilidad es alcance, no post-launch
(Prime Directive #5). Es una línea de log estructurado.*

**Hallazgo 8.2 (MEDIA) — B2 no nombra dueño ni cadencia.** Una consulta `.sql`
versionada es una métrica solo si alguien la corre con alguna frecuencia. El
plan no dice quién ni cada cuánto, y el precedente que cita tampoco los tuvo.
Sumado a las **cero filas de `usuarios` en `AUDITORIA`** (verificado, 287
filas, ninguna de licencias, 3 usuarios con `Licencia_Activa` nunca tocada),
la métrica arrancaría vacía. *Decisión: B2 invertido — correr ad hoc, registrar
el número, y commitear el `.sql` solo si hay señal.*

**Hallazgo 8.3 (MEDIA) — no hay runbook para el modo de fallo nuevo.** "El
árbitro ve 'otro operador está cargando un evento, reintentá'" necesita una
línea de qué hacer si pasa siempre (respuesta: un partido quedó con una
transacción abierta; revisar `pg_stat_activity`). *Decisión: una línea en el
docstring de A1. No un documento.*

Dashboards día 1: ninguno nuevo justificado a esta escala (3 usuarios, 13
partidos). Debuggability a 3 semanas: `AUDITORIA` + `ACCESOS` ya reconstruyen
qué pasó; A1 agrega el log de espera de lock, que es lo que faltaba.

#### Sección 9: Despliegue

**Hallazgo 9.1 (MEDIA) — F1 es el único ítem con riesgo de migración, y este
repo tiene tres trampas documentadas.** Si F1 agrega columnas:
(a) toda columna nueva va en **tres** lugares o ~40 archivos de test revientan
con `UndefinedColumn` — `01_schema.sql`, el script `NN_` idempotente con
`IF NOT EXISTS` (porque `test_scripts_sql.py` lo corre dos veces) y la lista
`SCRIPTS_VIGENTES` de `test_scripts_sql.py:36-48`, dado que `conftest.py:39-47`
arma la base solo con `01`..`06`;
(b) toda migración que toque una vista existente necesita
`DROP VIEW IF EXISTS` + `CREATE`, nunca `CREATE OR REPLACE`, que aborta la
transacción entera sobre la base real y `test_scripts_sql.py` no lo detecta;
(c) `DISCIPLINA.Estado` es `VARCHAR(20) DEFAULT 'Activo'` **sin `NOT NULL`**, y
`chk_disciplina_estado CHECK (Estado IN ('Activo','Inactivo'))` deja pasar
`NULL` por lógica de tres valores. Hoy hay 0 filas con `Estado` nulo
(verificado), así que es latente, no activo — pero un `POST` nuevo es
exactamente por donde entraría un `NULL`, y después
`WHERE Estado = 'Activo'` la descarta en silencio.
*Decisión: si F1 procede, `Estado` se fija `NOT NULL` con default en la misma
migración, y la guardia de tres lugares es obligatoria. Prior learning
applied: `score-app-conftest-solo-corre-01-06` (10/10), 
`score-app-estado-columns-nullable` (9/10),
`score-app-create-or-replace-view-columna-al-medio` (9/10).*

**Hallazgo 9.2 (BAJA) — orden de rollout.** A1/C1/C2/D1 son deploy simple sin
migración. E1 necesita backend antes que frontend (el frontend viejo con
`skip`/`limit` tiene que seguir funcionando durante la ventana). F1 necesita
migración antes que deploy. Feature flags: ninguno justificado a esta escala.
**Ventana de riesgo con código viejo y nuevo simultáneo:** solo E1 la tiene, y
es el argumento final para diferirlo.

Verificación post-deploy: `verificar.ps1` existe y hace el pase completo.
Nota: `TODOS.md` lista "mover `verificar.ps1` a CI" como **descartado a
propósito** (infraestructura nueva), así que la verificación sigue siendo
manual, a mano, por decisión vigente. Se respeta.

#### Sección 10: Trayectoria

**Reversibilidad:** A1 **5/5** (una línea). C1 **4/5**. C2 **3/5** (borra un
camino de UI; volver es resucitar código). D1 **4/5** (CSS). B2-invertido
**5/5**. E1 **2/5** (contrato de API público). F1 **2/5** (esquema + revierte
una decisión documentada). Los dos ítems menos reversibles son los dos sin
evidencia. La calibración de velocidad de Bezos dice exactamente esto: rápido
por default, lento solo para puertas de una sola dirección.

**Deuda introducida.** Approach A introduce: dos contratos de paginación (deuda
de código), un marker de test excluido por default que nadie recuerda cómo
correr (deuda de testing), un `alcance=` cuyo valor seguro nadie manda (deuda
conceptual), y una pantalla de CRUD de disciplinas usada dos veces (deuda de
producto). Approach B introduce: un fixture de concurrencia con guard, y dos
umbrales escritos en `TODOS.md`.

**Hallazgo 10.1 (MEDIA) — F1 revierte la Decisión C1 sin retirar su
fundamento.** `docs/plans/ediciones-catalogo-disciplinas-plan.md` hizo el
catálogo de solo lectura a propósito. Revertir una decisión dejando su
argumento vivo en disco es cómo un repo acumula contradicciones. *Decisión: si
F1 procede, la reversión de C1 se escribe explícitamente con su motivo. Si no
procede, C1 sigue en pie sin cambios.*

**Hallazgo 10.2 (MEDIA) — riesgo competitivo: nada de este plan es
diferenciador, y eso es el hallazgo.** El software de torneos amateur compite
en velocidad de carga en vivo desde un teléfono, resultados públicos
compartibles, y tiempo hasta el primer torneo. Este plan gasta su presupuesto
en integridad interna y mecánica de API. El portal público existe en este
codebase (`GET /partidos/feed`, `FeedService`, slugs consumidos por URLs
públicas — el propio plan marca `Slug` como carga-pesada en F1) y recibe cero
atención; sus pendientes menores (auto-refresh del feed, minuto en vivo)
están en el Backlog sin urgencia. Nadie le gana a este producto por paginación
con cursor. *Decisión: el próximo ciclo es velocidad de carga en vivo + portal
público. A `TODOS.md` como recomendación fechada, fuera del alcance de hoy
(P3 — fuera de radio de acción).*

**La pregunta del año.** Un ingeniero nuevo en 12 meses leyendo Approach A
preguntaría "¿por qué hay dos formas de paginar y ninguna se usa?". Leyendo
Approach B preguntaría "¿por qué el fixture de concurrencia tiene un guard de
nombre de base?" — y la respuesta está en su docstring. La segunda pregunta es
la buena.

#### Sección 11: Diseño y UX

```
  PANEL EN VIVO — FLUJO (después de C2 + D1 + expansión 1)
  ═══════════════════════════════════════════════════════

  [375px, al borde de la cancha]
  ┌──────────────────────────┐
  │ ZONA PRIMARIA            │ ← mira sin tocar
  │  Tiburones 2 - 1 Águilas │
  │  ⏱ 67'  EN CURSO         │
  ├──────────────────────────┤
  │ ZONA SECUNDARIA          │ ← donde toca
  │  [Gol][🟨][🟥][Cambio]   │
  │  Alineación en vivo:     │
  │   9 Pérez   🟨  [Sacar]  │ ← expansión 1: la 🟨 se ve
  │   7 Gómez       [Sacar]  │
  ├──────────────────────────┤
  │ ZONA TERCIARIA           │ ← consulta / cierre
  │  67' 🟨 Pérez            │
  │  45' ⚽ Gómez            │
  │  [Finalizar partido]     │
  └──────────────────────────┘
       │
       │ tap [Sacar] en Pérez
       ▼
  ModalSustitucion: "¿Por quién ingresa?"  ← único camino desde C2
       │
       │ tap 🟨 sobre un jugador que ya tiene 🟨
       ▼
  Confirmación: "Segunda amarilla → roja automática"  ← expansión 1
```

| Feature | LOADING | EMPTY | ERROR | SUCCESS | PARTIAL |
|---|---|---|---|---|---|
| Buscador (C1) | debounce | "Ningún jugador coincide" | ? ← verificar | fila elegible | conflicto de inscripción |
| Cambio (C2) | `isPending` | "No hay nadie disponible para salir" | mensaje de regla | evento en timeline | `sinConvocatoria` ← GAP |
| Panel (D1) | — | partido sin eventos | `mesa-offline-aviso` | 3 zonas | — |
| Tarjetas (exp. 1) | — | sin tarjetas | — | 🟨 visible | — |

**Hallazgo 11.1 (ALTA) — D1 sin la expansión 1 arregla la mitad del problema
del mesero.** Reorganizar en franjas resuelve "el marcador está fuera de
pantalla". No resuelve "no sé si este jugador ya tiene amarilla", que es la
información que decide la siguiente acción del árbitro y hoy vive únicamente en
el timeline de la zona terciaria, es decir abajo, es decir scrolleando, es
decir en el momento de menos tiempo. *Decisión: expansión 1 recomendada como
cherry-pick (en radio de D1, <1 día CC, P2 boil-lakes). Al Gate.*

**Hallazgo 11.2 (MEDIA) — D1 no nombra accesibilidad ni tamaño de target.** El
panel se usa con el pulgar, de pie, posiblemente con sol directo. El repo ya
tiene `.tap-button`/`.tap-grid` y un `@media (prefers-reduced-motion: reduce)`
(`index.css:223`), así que el sistema existe. *Decisión: D1 conserva
`.tap-button` como el tamaño mínimo de target de la zona secundaria y no
introduce controles más chicos. Una línea de restricción, no un rediseño.*

**Alineación con el doc de diseño.** `docs/designs/frontend-inicial-dashboard-mesa-en-vivo.md`
existe (206 líneas) y es específicamente sobre este panel. D1 tiene que leerlo
antes de asignar zonas — es la fuente de verdad del problema declarado, y el
plan no lo cita. *Decisión: D1 lo cita explícitamente.*

**Riesgo de AI slop:** bajo. El plan describe zonas por rol de información
("lo que el mesero mira sin tocar"), no "un dashboard moderno y limpio".

**Recomendación:** este plan tiene alcance de UI real (C1, C2, D1, expansión 1)
— conviene `/plan-design-review`, que corre a continuación como Fase 2.

---

#### "NOT in scope"

| Ítem | Motivo |
|---|---|
| Notificación por correo al jugador (`## Bloqueado`) | Pospuesto por el usuario el 2026-09-17; necesita elegir proveedor |
| Alerta **activa** de pico de 403 (parte 2 del ítem 9) | Mismo bloqueo de proveedor |
| 17 ítems de `## Backlog sin urgencia` | El archivo mismo dice "nadie lo pidió" |
| 11 ítems de `## Descartado a propósito` | "No reabrir sin evidencia nueva" |
| Migrar los otros 10 routes a cursor | Ver E1: 2 no 12, y ninguno de los 2 con problema medido |
| Rol nuevo `AdminCatalogo` | `AdminGeneral` ya alcanza; 0 de 89 `require_roles` cambian |
| Borrado duro de disciplinas | Soft-delete por `Estado` ya es el borrado |
| Scoping forzado server-side de equipos/jugadores | Si hay fuga real, es otro plan (Hallazgo 3.2) |
| Arreglar `handlers.py` → 400 para todo `DBAPIError` | Preexistente, alcance propio; a TODOS.md (Hallazgo 2.2) |
| Auto-refresh del feed y minuto en vivo | Fuera de radio, P3; es el ciclo siguiente (Hallazgo 10.2) |
| `verificar.ps1` a CI | Descartado a propósito por decisión vigente |

#### "What already exists"

Ver el mapa 0B. Los dos hallazgos que cambian el plan:
`PartidoRepository.get_or_404_bloqueado` ya implementa el lock de A1 (A1 es un
llamador nuevo, no código nuevo), y `fn_generar_disciplina_slug` ya implementa
toda la lógica de slug que F1 proponía escribir en Python, con el
`translate()` correcto para este repo y la preservación en rename.

#### Registro de modos de fallo

```
  CODEPATH                        | MODO DE FALLO            |RESCATADO|TEST|USUARIO VE      |LOGUEADO
  --------------------------------|--------------------------|---------|----|----------------|--------
  EventoPartidoService.create     | 2 amarillas sin roja     | **NO con  | A3 | nada (silencioso)| no   ← CRITICAL GAP
                                  | (frecuencia medida: 0)   | A1 como   |    |                |        el lock se libera en el
                                  |                          | está esp.)|    |                |        commit de repo.create;
                                  |                          | SÍ con la |    |                |        requiere transacción única
                                  |                          | reestruct.|    |                |        (Hallazgo 1.0)
  EventoPartidoService.create     | deadlock cruzado         | **N**   | **N**| **500**      | **N**  ← CRITICAL GAP
  EventoPartidoService.create     | reintento inserta 2ª     | **N**   | **N**| tarjeta de   | **N**  ← CRITICAL GAP
                                  | amarilla (si se reintenta|         |      | más, silenc. |        (sin unique sobre
                                  | sin reestructurar)       |         |      |              |        jugador_id+eventos_id)
  EventoPartidoService.create     | espera de lock invisible | n/a     | N  | "va lento"     | **N**  ← CRITICAL GAP
  conftest._recreate_test_database| DROP DATABASE sin guard  | **N**   | **N**| pérdida de   | **N**  ← CRITICAL GAP
                                  | de nombre (existe HOY)   |         |      | base de dev  |        (independiente de A2)
  fixture sesiones_paralelas      | TRUNCATE base equivocada | **N**   | **N**| pérdida datos| **N**  ← CRITICAL GAP
  fixture sesiones_paralelas      | deadlock → suite colgada | SÍ      | SÍ | (dev) fallo    | sí
  ModalSustitucion sinConvocatoria| sin camino para Cambio   | **N**   | **N**| botón muerto | **N**  ← CRITICAL GAP
  DISCIPLINA.Estado NULL [F1]     | fila invisible en listado| **N**   | N  | disciplina     | **N**  ← CRITICAL GAP
                                  |                          |         |    | desaparecida   |        (latente: 0 filas hoy)
  list_con_modalidades limit=200   | truncado silencioso [F1] | **N**   | N  | catálogo corto | **N**  ← CRITICAL GAP (latente)
  cursor de fila borrada [E1]     | página salteada silenciosa| **N**  | N  | fila faltante  | **N**  ← CRITICAL GAP (diferido)
```

**11 CRITICAL GAPS** (eran 8 en la revisión 1; +3 del spec review). 7 activos
en el alcance recomendado: la doble amarilla **sin arreglar por A1 tal como
estaba especificado** (Hallazgo 1.0), el deadlock, el reintento que duplicaría
la amarilla, la espera de lock invisible, el `DROP DATABASE` sin guard que
existe hoy, el `TRUNCATE` futuro de A2, y `sinConvocatoria`. Los 7 tienen
remedio decidido arriba. 4 latentes o diferidos (los 2 de F1, el de E1, y el
truncado del 200).

El gap #1 es el que importa: **el arreglo central del plan no arreglaba nada**,
y solo se vio al leer `BaseRepository.create`. Es exactamente lo que este
pipeline existe para encontrar.

#### Delta del dream state

Con Approach B, el sistema queda: integridad del camino en vivo cerrada y
probada, un solo camino de UI por acción, panel legible en el teléfono con
estado de tarjetas visible, y dos ítems diferidos con su disparador numérico
escrito. Lo que **no** queda: el portal público sigue con botón "Recargar" en
vez de auto-refresh, y el feed sigue diciendo "EN VIVO" sin minuto. Esa es la
distancia real al ideal de 12 meses, y es el próximo ciclo.

#### Resumen de finalización — Fase 1 (CEO)

```
  +====================================================================+
  |            MEGA PLAN REVIEW — COMPLETION SUMMARY (CEO)             |
  +====================================================================+
  | Mode selected        | SELECTIVE EXPANSION                          |
  | System Audit         | 0 TODO/FIXME reales; baseline sin commitear; |
  |                      | 8º ciclo de cierre de TODOS.md; 9 métricas   |
  |                      | medidas contra torneos_mvp                   |
  | Step 0               | 6 premisas evaluadas, 4 refutadas con datos  |
  | Section 1  (Arch)    | 4 issues (1 CRÍTICO, 2 ALTA, 1 MEDIA)        |
  | Section 2  (Errors)  | 12 caminos mapeados, 5 GAPS                  |
  | Section 3  (Security)| 3 issues, 2 ALTA                             |
  | Section 4  (Data/UX) | 13 casos borde mapeados, 4 sin cubrir        |
  | Section 5  (Quality) | 3 issues                                     |
  | Section 6  (Tests)   | Diagrama producido, 2 gaps                   |
  | Section 7  (Perf)    | 2 issues (E1 sin problema medido)            |
  | Section 8  (Observ)  | 3 gaps                                       |
  | Section 9  (Deploy)  | 2 riesgos (3 trampas de migración citadas)   |
  | Section 10 (Future)  | Reversibilidad: A1 5/5, E1 2/5, F1 2/5;      |
  |                      | 4 items de deuda si va Approach A            |
  | Section 11 (Design)  | 3 issues                                     |
  +--------------------------------------------------------------------+
  | NOT in scope         | written (11 items)                           |
  | What already exists  | written (9 mapeos, 2 correcciones al plan)   |
  | Dream state delta    | written                                      |
  | Error/rescue registry| 12 métodos, 5 CRITICAL GAPS                  |
  | Failure modes        | 12 total, 11 CRITICAL GAPS (7 activos)       |
  | TODOS.md updates     | 6 items propuestos                           |
  | Scope proposals      | 5 propuestos, 3 aceptados/recomendados       |
  | CEO plan             | written (revisión 2, tras spec review)       |
  | Spec review loop     | 1 iteración, 6/10 → 16 hallazgos aceptados,  |
  |                      | 1 rechazado con motivo                       |
  | Outside voice        | codex / unavailable (not_installed)          |
  | Lake Score           | 3/4 recomendaciones eligieron la completa    |
  | Diagrams produced    | 6 (dependencias, dream state, async A1,      |
  |                      | flujo UX, zonas del panel, commit boundary)  |
  | Stale diagrams found | 0                                            |
  | Unresolved decisions | 4 (3 User Challenges + 1 Taste, al Gate)     |
  +====================================================================+
```

#### Spec review loop — resultado

**Dos iteraciones, 6/10 → 8/10, convergido en "proceder al Gate con
correcciones".** Cada hallazgo se verificó contra el código y la base antes de
aceptarlo.

**Iteración 1 (6/10):** 16 hallazgos aceptados, 1 rechazado. Los tres que
cambian trabajo real:

1. **A1 no funcionaba** (`BaseRepository.create` commitea y libera el lock
   antes de la lectura de la doble amarilla) — Hallazgo 1.0.
2. **A0 y A2 faltaban** en la línea de recomendación; A2 es prerrequisito duro
   de A3, y la revisión 1 aceptaba alcance dentro de A2 sin agendarla.
3. **Los conteos eran sintéticos** (1750 de 1787 jugadores son `MOCK-`), y el
   argumento "5.6x de margen" de E1 era una estimación disfrazada de medición
   apuntada a un riesgo inalcanzable.

Rechazado: que la revisión descartara el desarme del Effort L de F1. Ese
desarme sigue en pie (premisa del `CHECK` de roles) — F1 se difiere por falta
de demanda, no por costo; que sea más barato de lo que decía `TODOS.md` no lo
vuelve necesario.

**Iteración 2 (8/10):** confirmó 7 de 10 resueltos y reprodujo cada número.
Encontró **dos hechos que la iteración 1 había arreglado mal** y tres
contradicciones internas nuevas. Los dos importantes, verificados:

4. **`EQUIPOS` orgánico es 10, no 270.** 260 de 270 son de grupos "Prueba de
   Estrés". El defecto sintético/orgánico que la iteración 1 señaló volvió a
   aparecer justo en la única celda que la tabla marcaba sin medir — y esa
   celda era la premisa entera de E1. Corregido: los orgánicos están al 5% del
   tope, no al 135%, y los umbrales de reapertura se re-anclaron al tope real
   de 200 (150 orgánicos) en vez de a 5.000.
5. **La roja del caso de doble amarilla no es la automática.** Está al minuto
   55, y `procesar_doble_amarilla` la crea en el minuto de la segunda amarilla
   (5). Decisivo: los eventos son del **2026-09-08** y
   `reglas_tarjetas.py` se commiteó el **2026-09-14** (`b7b2feb`) — la regla no
   existía. La afirmación correcta es más fuerte: **la regla de doble amarilla
   tiene cero ejercicio sobre datos reales.**

Más: A0 declaraba "7 archivos" y "5 modificados" contra 8 reales, sin decir
cuáles van en el commit del baseline (definido ahora); un cross-reference
"M1" colgado; A1 omitía el segundo `commit()`; y el target de reuso de la
expansión 1 era el equivocado (`ModalResultadoDirecto` deriva de estado local
sin guardar; el correcto es `components/eventos.ts`, el módulo compartido que
`MesaPanel` ya consume).

**El loop paga dos veces.** Sin la iteración 1, el plan shipeaba un "arreglo"
de concurrencia que no arregla la concurrencia. Sin la iteración 2, lo shipeaba
justificado con dos hechos falsos: un tope de página que en realidad nunca se
alcanzó con datos reales, y una red de seguridad que se daba por probada
cuando nunca corrió. Ninguna de las 5 decisiones de alcance cambió en ninguna
de las dos iteraciones — cambiaron los motivos, y dos de ellos se volvieron
más fuertes.

#### Decisiones que van al Gate Final (no auto-decididas)

- **UC-1** Diferir E1 (paginación con cursor) — refutada con datos medidos.
- **UC-2** Diferir F1 (catálogo editable) — sin demanda; revierte Decisión C1.
- **UC-3** Matar B1 (filtrar listados) — premisa falsa por modelo de datos.
- **T-1** A2: fixture de concurrencia completa vs test determinista de servicio.

Y 3 cherry-picks de expansión recomendados (exp. 1 estado de tarjetas, exp. 2
guard de base — ya auto-aprobado como guard destructivo, exp. 5 umbrales
numéricos).

<!-- autoplan-accepted:ceo -->
- A0 deja de ser fase y pasa a precondición, con condición de terminado DEFINIDA (la revisión 2 decía "7 archivos" en un lugar y "5 modificados" en otro; `git status --porcelain` da **8** entradas). Las 8, y a qué commit va cada una: **al commit del baseline `ReglamentoTorneo` van 6** — los 2 untracked (`backend/app/services/reglamento_torneo.py`, `backend/tests/test_reglamento_torneo.py`) y los 4 servicios que lo consumen (`convocado_a_partido.py`, `hito_partido.py`, `partido.py`, `torneo.py`). **`TODOS.md` va en ese mismo commit** porque su sección "Resuelto (2026-09-17)" describe exactamente ese trabajo. **`frontend/src/components/MesaPanel.tsx` va aparte**: son 5 líneas de otra feature (timeline ascendente) y es justo el archivo que D1 y la expansión 1 reorganizan, así que mezclarlo con el baseline es lo que hace irreversible un revert de D1. Verificación: `git status --porcelain` vacío antes de la primera edición de cualquier track.
- **A1 se REESTRUCTURA, no se parchea.** El swap `get_or_404` → `get_or_404_bloqueado` NO cierra la carrera: `BaseRepository.create` (`repositories/base.py:43-48`) hace `commit()`, que libera el `FOR UPDATE` antes de que `_procesar_doble_amarilla_si_corresponde` lea el conteo de amarillas. `create` pasa a una sola transacción: sin el `repo.create` que auto-commitea, `flush()` en vez de `commit()`, **y sacando también el segundo `commit()`, el de `_procesar_doble_amarilla_si_corresponde` (`evento_partido.py:124-125`)** — son DOS los commits a eliminar, no uno (corrección de la revisión 3). Un solo `commit()` al final, siguiendo la forma que `PartidoService.registrar_resultado_directo` ya usa. El docstring de `procesar_doble_amarilla` (`reglas_tarjetas.py:36-45`) documenta explícitamente las disciplinas transaccionales divergentes de sus dos llamadores, así que queda obsoleto y se actualiza en el mismo cambio. Effort M (human: ~3 h / CC: ~25 min), no ~15 min, **más el radio de regresión**: pasar de commit-por-evento a transacción única cambia semántica de la que dependen tests existentes; el cambio corre la suite completa de backend, no solo el test nuevo. Verificación: test de dos sesiones que hoy falla (2 amarillas / 0 rojas) y pasa con la transacción única, MÁS los 486 tests existentes en verde.
- A1 incluye rescate de `DeadlockDetected`, **condicionado a la reestructuración anterior y en el mismo cambio**: reintento único y, si vuelve a fallar, `DomainRuleError` con mensaje accionable ("otro operador está cargando un evento en este partido, reintentá"). Mientras `create` no sea atómico el reintento está PROHIBIDO — con la estructura de hoy, un deadlock posterior al commit de la amarilla haría que el reintento inserte una segunda amarilla, y `EVENTOS_PARTIDO` no tiene unique sobre `(jugador_id, eventos_id)`. Verificación: test que fuerza el deadlock cruzado con `registrar_resultado_directo` y afirma 4xx con ese mensaje y exactamente una amarilla persistida.
- A1 loguea de forma estructurada cuando la espera del `FOR UPDATE` supera un umbral, con `partido_id` y `usuario_id`. El umbral, el destino del log y quién lo lee se nombran en el mismo cambio (este repo no tiene pipeline de métricas, así que un log sin consumidor es trabajo invisible). Verificación: assert sobre el log en el test de contención.
- A1 lleva una línea de runbook en su docstring: si la espera es constante, revisar `pg_stat_activity` por una transacción abierta sobre ese partido.
- Guard de nombre de base ante operación destructiva en `backend/tests/conftest.py`: verifica el nombre contra un patrón test-only (`%_test`) y levanta ANTES de ejecutar. Aplica al `DROP DATABASE IF EXISTS` que **ya existe hoy sin guard** en `_recreate_test_database`, y a cualquier `TRUNCATE` que agregue A2. **No depende de A2**: si el Gate corta A2, el guard del `DROP DATABASE` sigue siendo necesario y pasa a TODO propio. Verificación: test unitario que apunta el helper a `torneos_mvp` y afirma que levanta sin ejecutar el DROP.
- C2 no se mergea hasta que exista un test de `ModalSustitucion` con `sinConvocatoria=true` que pase; el retiro del camino viejo va después, nunca antes. Verificación: ese test existe y pasa en el commit previo al retiro.
- C2 cuenta los tests de Cambio en `MesaPanel.test.tsx` antes de editar y la cuenta no baja al terminar. Verificación: el número antes y después, escrito en el commit.
- C1 mantiene `SelectorJugadorBuscable` haciendo búsqueda; la confirmación de conflicto y el alta inline se quedan alrededor en `DetalleEquipo`, no se absorben como props opcionales. Verificación: el selector no gana props booleanas nuevas.
- C1 crea `DetalleEquipo.test.tsx` cubriendo búsqueda, conflicto de inscripción y alta inline ANTES de refactorizar. Verificación: ese archivo existe y pasa en el commit previo al refactor.
- D1 lee y cita `docs/designs/frontend-inicial-dashboard-mesa-en-vivo.md` antes de asignar zonas, y conserva `.tap-button` como tamaño mínimo de target en la zona secundaria. Verificación: el plan de D1 nombra el doc; ningún control nuevo de la zona secundaria es más chico que `.tap-button`.
- D1 no agrega breakpoints: reusa 480/640/800/1000px de `index.css`. Móvil 375px queda en una columna. Verificación: `git diff` de `index.css` no introduce un `@media` con un ancho nuevo.
- B2 se invierte y con eso **ya está ejecutado**: la consulta ad hoc corrió durante esta revisión y dio cero en sus DOS mitades — contador (`AUDITORIA`: 287 filas, CERO de la tabla `usuarios`; 3 usuarios con `Licencia_Activa=True` nunca tocada) y pico de 403 (`ACCESOS`: CERO filas con `Motivo='licencia_revocada'`; únicos motivos `credenciales`=3 y NULL=17). `docs/queries/metricas-revocacion-licencia.sql` NO se commitea: no hay señal que valga releer. El ítem se cierra por falta de señal y se reabre con la primera fila de `usuarios` en `AUDITORIA`. Si alguna vez se escribe esa consulta, `Tabla` se filtra en MINÚSCULA (`usuarios`), porque guarda `obj.__tablename__` — `Tabla='USUARIOS'` da cero por casing, no por falta de datos.
- Los umbrales que reabren los diferidos van escritos como números en `TODOS.md`, no como intenciones. **Corregidos en la revisión 3**: la revisión 2 puso el disparador de E1 en 5.000 jugadores, 25x más arriba que el tope de página de 200 que su propio argumento identifica como la restricción real — garantizaba que el ítem quedara cerrado justo en todo el rango donde empieza a doler. Y no tenía disparador de equipos, aunque el motivo del diferimiento hablaba de equipos. Quedan así, atados a la restricción real (el tope de 200) y medidos sobre filas ORGÁNICAS, no crudas:
  - **E1** se reabre con (a) **>150 equipos orgánicos** o **>150 jugadores orgánicos** (75% del tope de 200, es decir antes de que el banner de truncado pase a ser la experiencia normal y no la excepción), o (b) un p95 medido >800 ms en `GET /jugadores` o `GET /equipos`, o (c) un segundo cliente de la API que no sea este frontend. Hoy: 10 equipos y 37 jugadores orgánicos.
  - **F1** se reabre al SEGUNDO pedido real de alta de una disciplina fuera del catálogo de 28 (el primero se atiende con el script de migración que ya existe).
  - **B2** se reabre con la primera fila de la tabla `usuarios` en `AUDITORIA` (es decir, la primera licencia realmente otorgada o revocada).
- Los diferimientos se redactan con la fórmula que el repo ya usa para la Fase 3 del desempate — "sin señal todavía, revisitar con datos de uso real" — no como rechazos. Y Track A se justifica por CONSECUENCIA (un registro disciplinario incorrecto en un partido cerrado no se puede arreglar y el fallo es silencioso), no por frecuencia: la frecuencia medida es CERO casos de 2 amarillas sin roja.
- Toda medición contra `torneos_mvp` que se use como argumento separa filas orgánicas de las sintéticas que dejó `backend/scripts/mock_estres_catalogo.py`: 1750 de 1787 jugadores tienen cédula `MOCK-` y 68 de 83 torneos son del grupo "Prueba de Estrés". Orgánico real: 37 jugadores, 15 torneos.
- Si la expansión 1 (estado de tarjetas visible) se aprueba, la derivación de estado de tarjetas por jugador va en **`frontend/src/components/eventos.ts`**, el módulo de derivación compartido que `MesaPanel` ya consume y que ya exporta `deriveHistorialElegibilidad` (línea 56), `deriveTitularSuplente` (91) y `deriveEnCancha` (119), y que ya rastrea `"Tarjeta Roja"` en la línea 60. **Corrección de la revisión 3:** la revisión 2 apuntaba a la preview de `ModalResultadoDirecto.tsx`, que es el target equivocado — esa deriva de estado local de un batch sin guardar (`otrosEventos: OtroEventoLocal[]`) dentro de un modal de carga retroactiva, mientras la expansión necesita estado desde eventos ya persistidos en el servidor (`eventosRegistrados`, `MesaPanel.tsx:215`). Mismo objetivo (no una tercera copia de la regla), mecanismo correcto. Y el effort de la expansión se revisa de S a **S-M** (human: ~6 h / CC: ~30 min): es extracción en un módulo compartido más trabajo de layout en el mismo archivo de 1002 líneas que D1 está reorganizando.
- Los tracks corren en orden serial con stop-the-line (`A0 → A1 → A2 → A3 → C1 → C2 → D1 → exp.1`): ninguno arranca hasta que el anterior bajó a la sección Resuelto de `TODOS.md`. Verificación: un solo track con archivos modificados a la vez.
- **A2 es el ítem menos especificado del plan y está segundo en una cadena serial que bloquea a A3/C1/C2/D1 — riesgo de cronograma que hay que nombrar (revisión 3).** `conftest.py:112-145` envuelve cada test en una sola sesión con savepoints; una fixture de conexiones genuinamente paralelas significa optar POR FUERA de ese harness, que es una tarea de diseño, no un ajuste de fixture. A2 no arranca sin un bosquejo de enfoque escrito de una página: cómo se crean las 2 sesiones, cómo se limpia sin depender del rollback que no existe ahí, y qué pasa si el test se cuelga. Si el bosquejo no cierra, A2 se mueve al final de la cadena (detrás de D1) para no bloquear el resto, y A3 se hace con la opción determinista de servicio.
- Cada track lleva un resultado observable declarado (la tabla de 0D), no solo "tests verdes". Verificación: el resultado está escrito en el track antes de empezarlo.
- Si F1 procede en algún momento: no se escribe lógica de slug en Python (`fn_generar_disciplina_slug` ya lo hace con `translate()` y preserva el slug en rename); `DISCIPLINA.Estado` se fija `NOT NULL` con default en la misma migración; el `limit=200` hardcodeado de `services/disciplina.py:30` sale; se valida que el slug derivado no sea vacío; la reversión de la Decisión C1 se escribe con su motivo; y la guardia de tres lugares (`01_schema.sql` + script `NN_` idempotente + `SCRIPTS_VIGENTES` de `test_scripts_sql.py:36-48`) es obligatoria para toda columna nueva.
- Si E1 procede en algún momento: el cursor lleva campo de versión desde el día 1, y el caso "cursor apunta a una fila borrada" tiene test y comportamiento definido.
<!-- /autoplan-accepted:ceo -->

### Fase 2 — Design review (single-model)

Voces: nativa Claude subagent **completada** (INPUT hash
`8b4bfe2e…f7c6963` verificado). Codex **no disponible** — `[single-model]`,
las 7 celdas del litmus quedan `N/A`.

**Mockups: no disponibles.** El binario del designer existe
(`DESIGN_READY`) pero no hay API key de OpenAI — error textual:
`No OpenAI API key found`. Se usó el fallback documentado (`DESIGN_SKETCH`):
wireframe HTML estructural en
`~/.gstack/projects/Score-App/designs/mesa-panel-3-zonas-20260917/wireframe-zonas.html`,
con las 3 zonas a 375px y a ≥1000px. Es wireframe de estructura, no propuesta
visual. Para mockups de IA: `design setup` o `OPENAI_API_KEY`.

#### Step 0 — Alcance de diseño

**0A. Rating inicial: 2/10.** Duro pero correcto. El plan es fuerte en
ingeniería y delgado en diseño: cada fase que toca a un humano (C1, C2, D1,
expansión 1) describe **dónde va el código**, no **qué ve el usuario**. Y la
única fase cuyo propósito entero es diseño (D1) no contiene diseño: delega la
asignación de zonas a "la revisión de diseño", que es esta, a la que el plan no
entregó wireframe, ni dimensiones, ni comportamiento de scroll.

Un 10 para ESTE plan sería: qué se ve sin scrollear a 375px, qué pasa cuando la
carga tiene éxito, qué pasa cuando no hay convocatoria, y cómo se ve una
amarilla acumulada en la fila del jugador.

**0B. DESIGN.md: no existe.** `TODOS.md` lo lista en Backlog sin urgencia con
la nota "recomendado por 5 planes consecutivos, nunca ejecutado". **Este es el
sexto.** Cinco recomendaciones ignoradas dejan de ser una recomendación y pasan
a ser un dato: no se va a escribir por recomendación. Se califica contra
principios universales y contra los patrones que ya existen en el repo, que de
hecho son bastante consistentes (ver 0C).

**0C. Leverage de diseño existente** (lo que el plan NO debe reinventar):

| Patrón existente | Dónde | ¿Lo usa el plan? |
|---|---|---|
| `.tap-button` / `.tap-grid` | `index.css` | Sí — target mínimo de zona 2 |
| Breakpoints 480/640/800/1000 | `index.css` | Sí — sin agregar nuevos |
| `prefers-reduced-motion` | `index.css:223` | Sí — nada de animación nueva |
| `aria-live` | 6 archivos (`ModalResultadoDirecto`, `AlineacionEditor`, `Cronometro`, `GestionarPartido`, `PartidosDelTorneo`) | **No, y es el hallazgo 2.1** |
| Empty-state filtrado vs real | `EquiposAdmin.tsx:268-277` | **No, y es el hallazgo 7.2** |
| `mesa-offline-aviso` + `useOnlineStatus` | `MesaPanel.tsx` | Sí — resuelve la Open Question del design doc |
| `deriveHistorialElegibilidad` / `deriveEnCancha` | `components/eventos.ts` | Sí — exp. 1 se deriva ahí |

**0D. Áreas de foco: las 7 dimensiones** (auto-decidido, P1 completitud).

**Chequeo retrospectivo.** 3 revisiones de diseño previas en esta rama
(2026-08-27; 2026-09-09 inicial 4→9; 2026-09-15 inicial 4→8 con 17
decisiones), todas cerradas "clean". El diseño de este repo arranca en ~4/10 y
se arregla en la revisión. Este plan arranca en **2**, más abajo que los tres
anteriores, porque es el primero cuya fase de diseño delega su propia decisión.

**Alineación con el design doc aprobado**
(`docs/designs/frontend-inicial-dashboard-mesa-en-vivo.md`, APPROVED
2026-08-25). Tres extractos que el plan debía citar y no citó:

1. Criterio de éxito de Control de Mesa: "cargar eventos desde un navegador de
   **celular** (no solo desktop — es el escenario real de uso en cancha)...
   **2-3 toques, sin tipear**". El mobile-first de D1 no es preferencia de esta
   revisión: es criterio de éxito aceptado.
2. "Edición concurrente en Control de Mesa (dos árbitros, o Admin + Árbitro,
   actuando sobre el mismo partido): sin resolución de conflictos en esta fase
   — last-write-wins... **Se revisita si en la práctica genera choques.**"
   **Track A es exactamente ese revisitar.** Justificación documentada, más
   fuerte que el argumento de consecuencia que usó la Fase 1.
3. Open Question: "¿Qué pasa cuando el árbitro pierde conectividad?" —
   **ya resuelta** por `mesa-offline-aviso` + `useOnlineStatus`. El design doc
   quedó desactualizado en ese punto; vale anotarlo.

#### Step 0.5 — Litmus scorecard

```
DESIGN OUTSIDE VOICES — LITMUS SCORECARD:
═══════════════════════════════════════════════════════════════
  Check                                    Claude  Codex  Consensus
  ─────────────────────────────────────── ─────── ─────── ─────────
  1. Brand unmistakable in first screen?   N/A     —      N/A  (APP UI, sin marca)
  2. One strong visual anchor?             NO      —      N/A  (el marcador se pierde)
  3. Scannable by headlines only?          NO      —      N/A  (4 cards sin jerarquía)
  4. Each section has one job?             YES     —      N/A
  5. Cards actually necessary?             NO      —      N/A  (4 `.card` donde van franjas)
  6. Motion improves hierarchy?            N/A     —      N/A  (no hay motion, y está bien)
  7. Premium without decorative shadows?   YES     —      N/A
  ─────────────────────────────────────── ─────── ─────── ─────────
  Hard rejections triggered:               1       —      N/A
═══════════════════════════════════════════════════════════════
Cobertura externa ausente → 7 celdas N/A, nunca CONFIRMED. [single-model]
```

**Clasificador: APP UI / OPERATE.** El mesero termina una tarea; escaneabilidad
y expectativas nativas le ganan a la expresión.

**Hard rejection #7 disparada: "App UI made of stacked cards instead of
layout."** Hoy `MesaPanel` es literalmente eso: `marcador`,
`card carga-evento`, `card alineacion-en-vivo`, `eventos-timeline` apiladas en
el flujo de `.page`. Es lo que D1 viene a arreglar, así que la rejection es un
argumento **a favor** de D1. Se levanta como primer ítem del Pass 1.

#### Pass 1: Arquitectura de la información — 3/10 → 8/10

**[HARD REJECTION] 1.1 — cards apiladas en vez de layout.** Ver arriba.

**1.2 (CRÍTICO) — D1 delega su propia decisión a esta revisión, y no entregó
nada que decidir.** El plan dice "la asignación se confirma en la revisión de
diseño, no acá" y ofrece una línea de conjetura sin wireframe, sin
proporciones, sin modelo de scroll, sin decir qué es visible sin scrollear a
375×667. Una decisión ruteada a una revisión tiene que llegar con opciones y
recomendación; si no, no está diferida, está **descartada** — y aterriza en el
implementador al teclado, que es justo lo que el criterio 5 del propio plan
dice que hay que evitar.

*Decisión (estructural → auto-fix, P5):* D1 arranca con la asignación de zonas
**fijada, no delegada**, y el wireframe de esta revisión es la referencia
concreta a 375px y ≥1000px.

**1.3 (CRÍTICO) — D1 se auto-excluye de su caso principal.** El plan declara
móvil 375px como caso principal ("el panel en vivo se usa en el teléfono al
borde de la cancha") **y** deja móvil en una columna. Una grilla de 3 zonas que
colapsa a una columna en el breakpoint principal **no cambia nada para el
usuario principal**: D1 tal como está escrita es una mejora de escritorio a una
pantalla que se usa en el teléfono.

*Decisión (estructural → auto-fix, P5):* el mecanismo que entrega "lo que el
mesero mira sin tocar" en una sola columna es `position: sticky; top: 0` sobre
`.marcador` + `.marcador__estado` (`MesaPanel.tsx:452-457`).

#### Pass 2: Cobertura de estados de interacción — 2/10 → 8/10

```
  FEATURE            | LOADING        | EMPTY              | ERROR              | SUCCESS       | PARTIAL
  -------------------|----------------|--------------------|--------------------|---------------|-------------------
  Carga de evento    | solo `disabled`| n/a                | `.error-text`      | **NINGUNO**   | n/a
                     | ← GAP          |                    | (igual que un 4xx  | ← GAP CRÍTICO |
                     |                |                    | permanente ← GAP)  |               |
  Cambio (modal)     | `confirmando`  | callejón sin salida| `.error-text`      | **NINGUNO**   | sin convocatoria:
                     |                | ← GAP CRÍTICO      |                    | ← GAP CRÍTICO | **se rompe** ← CRÍT.
  Alineación en vivo | —              | "Sin nadie en      | —                  | —             | —
                     |                | cancha marcado..." |                    |               |
  Timeline           | —              | partido sin eventos| —                  | —             | —
  Panel offline      | —              | —                  | `mesa-offline-     | —             | —
                     |                |                    | aviso` ✔           |               |
```

**2.1 (CRÍTICO) — no existe estado de éxito en el panel en vivo, y el timeline
ascendente manda el evento nuevo abajo del fold.** Verificado: **cero
`aria-live` en `MesaPanel.tsx`**, mientras 6 archivos del repo sí lo usan. La
única confirmación de que un evento se registró es que aparece en "Eventos
cargados", que por decisión explícita del usuario (Gate del 2026-09-09)
renderiza **ascendente** — el evento nuevo va al final.

Minuto 70, teléfono, una columna: el mesero toca "Sacar", elige el reemplazo,
el modal cierra, y el evento nuevo se renderiza debajo de decenas de filas,
fuera de pantalla. Lo que siente es "no pasó nada". Lo que hace es **tocar de
nuevo**.

**Y eso es exactamente el doble-submit contra el que Track A gasta todo su
presupuesto en la base de datos.** El backend se blinda contra una carrera que
el frontend está invitando. Es el hallazgo con mejor relación valor/costo del
plan y no figuraba en ninguna parte.

*Decisión (estructural → auto-fix, P5):* confirmación `aria-live="polite"`
anclada en la zona donde se tocó. El patrón ya existe en 6 archivos — rung 1 de
la escalera de reuso. **El orden ascendente NO se toca**: decisión activa del
usuario del 2026-09-09.

**2.2 (CRÍTICO) — el empty state de `ModalSustitucion` es un callejón sin
salida, y C2 lo vuelve terminal.** Verbatim (`ModalSustitucion.tsx:43-44`):
"No hay suplentes disponibles para entrar (todos ya entraron o fueron
expulsados). Sumá un suplente desde la convocatoria del partido si llegó
alguien tarde." Instrucción sin navegación: no hay link ni botón, solo
"Cancelar". El comentario del código lo llama "un estado vacío que NO es un
callejón sin salida", pero lo es; solo que se disculpa primero.

Hoy se tolera porque `CargaEvento` es un segundo camino. Después de C2 es el
estado **terminal** de todo partido con convocatoria incompleta, a mitad de
partido, en un teléfono, con jugadores esperando.

*Decisión (estructural → auto-fix, P5):* el empty state gana una acción
primaria que rutea a "Gestionar Partido › Convocatoria" y vuelve al partido al
guardar.

**2.3 (CRÍTICO — corrige una obligación de la Fase 1 que era inaplicable) — C2
borra el único camino de sustitución sin convocatoria, y el reemplazo no tiene
punto de entrada.** El propio comentario del código lo dice:

> "Este flujo solo se dispara tocando un titular en la lista de arriba, que
> **YA exige convocatoria guardada (si no hay, la lista sale vacía)** — así que
> acá siempre hay convocatoria y se puede filtrar estrictamente a suplentes."

La cadena verificada:

- "Sacar" solo se renderiza dentro de `titularesEquipo.map(...)`.
- `titularesEquipo` filtra por `enCanchaJugadorIds`, derivado de la convocatoria.
- Sin convocatoria → `titularesEquipo.length === 0` → "Sin nadie en cancha
  marcado en la convocatoria." → **no existe ningún botón "Sacar"**.
- `elegibles` filtra estrictamente por `suplentesJugadorIds`, vacío sin
  convocatoria.

O sea: **`ModalSustitucion` es inalcanzable sin convocatoria.** No falta una
prop en un modal de 71 líneas: falta un **afordance nuevo** que el plan no
diseña ni presupuesta.

Mientras tanto, la rama `tipo === "Cambio"` de `CargaEvento` sí lo maneja hoy
(`MesaPanel.tsx:874`):
`disponiblesParaSalirCambio = props.sinConvocatoria ? disponiblesParaSalir : ...`,
comentada como "degrada con gracia a la plantilla completa (**D4**) — mismo
comportamiento que tenía antes de este plan". **Esa es la rama que C2 borra.**

Efecto neto si C2 se implementa literalmente: un árbitro al borde de la cancha
con la convocatoria sin guardar **pierde la capacidad de registrar un cambio**,
y la decisión D4 queda revocada en silencio.

*Decisión (estructural → auto-fix, P5), y **supersede** de la obligación de
Fase 1:* se divide en **C2a** (construir el punto de entrada sin convocatoria)
y **C2b** (recién después retirar la rama de `CargaEvento`), con el gate
elevado a un recorrido de punta a punta, no a un test de render.

**2.4 (ALTA) — el mensaje de deadlock de A1 no tiene casa ni forma de
reintentar.** Las dos superficies plausibles renderizan errores idénticamente
como `<p className="error-text">`. Así, el único error transitorio y
auto-recuperable del sistema se ve **igual** que un rechazo permanente, y su
instrucción le pide al mesero repetir un gesto que cree que ya funcionó.

*Decisión (estructural → auto-fix, P5):* tratamiento visual distinto y botón
**"Reintentar"** que re-envía el mismo payload.

**2.5 (MEDIA) — estados de carga sin especificar.** Hoy `isPending` solo
deshabilita botones: sin spinner y, por 2.1, sin mensaje de éxito, una red
lenta se ve como pantalla muerta. *Decisión (auto-fix):* una línea por fase.

#### Pass 3: Viaje del usuario y arco emocional — 3/10 → 8/10

```
  PASO | EL MESERO HACE              | SIENTE                   | ¿EL PLAN LO ESPECIFICA?
  -----|-----------------------------|--------------------------|------------------------
  1    | Abre el panel, mira el      | "¿vamos 2-1?"            | NO — el marcador se
       | marcador                    |                          | pierde al scrollear (1.3)
  2    | Scrollea a cargar un evento | "¿dónde quedó?"          | NO — es el gap de D1
  3    | Toca 🟨 sobre un jugador     | "¿este ya tenía una?"    | NO — exp. 1
  4    | Confirma                    | "¿se guardó?"            | **NO — gap crítico 2.1**
  5    | No ve nada cambiar          | "no pasó nada"           | NO
  6    | **Toca de nuevo**           | (genera el doble-submit) | Track A lo atrapa en la DB
  7    | Sin convocatoria, busca el  | "no hay ningún Sacar"    | **NO — gap crítico 2.3**
       | botón de cambio             |                          |
```

Horizontes: **5 segundos** — el marcador tiene que estar sin tocar nada; hoy se
pierde. **5 minutos** — cada carga necesita acuse de recibo; hoy no hay.
**5 años** — el mesero confía en que el registro del partido es correcto; el
gap 2.3 y el bug de doble amarilla erosionan exactamente eso.

El paso 6 es el hallazgo: **el arco roto en 4-5 produce el bug que Track A
arregla en la base de datos.** Arreglar el paso 4 es más barato que el lock, y
hay que hacer los dos.

#### Pass 4: Riesgo de AI slop — 7/10 → 8/10

Clasificador APP UI / OPERATE. Lo que está bien y es genuino: el plan describe
las zonas **por rol de información** ("lo que el mesero mira sin tocar", "donde
toca"), no como "un dashboard moderno y limpio". Eso es lenguaje de utilidad,
que es lo que pide OPERATE. **Cero hits de la blacklist de 11 patrones**: sin
gradientes violeta, sin grilla de 3 features con iconos en círculos, sin
centrado de todo, sin blobs decorativos, sin copy de hero genérico.

El emoji como icono de evento (⚽🟨🟥🔁) roza el patrón 7, pero acá son
**datos** (el catálogo de `EVENTOS`), no decoración, y "Iconos SVG propios por
disciplina" está en **Descartado a propósito** de `TODOS.md`. Decisión vigente,
no se re-litiga.

Único hallazgo: la hard rejection #7, que D1 arregla. No llega a 10 porque sin
DESIGN.md no hay voz tipográfica ni paleta declarada contra la que calibrar.

#### Pass 5: Alineación con el sistema de diseño — 4/10 → 7/10

**Sin DESIGN.md**, sexto plan consecutivo que lo señala. Se califican las
especificaciones explícitas: el plan cita `.tap-button` como target mínimo,
reusa los breakpoints, respeta `prefers-reduced-motion`. Eso es más de lo que
traen la mayoría de los planes de este repo, y es el techo alcanzable sin
tokens declarados: **7/10 es el máximo posible acá**, y por eso el score
general queda en 7.

**5.1 (MEDIA) — "reusar los breakpoints existentes" no es coherentemente
alcanzable, y la verificación de Fase 1 pasa igual.** `index.css` mezcla
direcciones: `min-width` en 800/1000 (201, 634, 1858, 1903) y `max-width` en
480/640 (892, 1807, 1970). No hay cascada mobile-first única que extender, así
que un refactor a `grid-template-areas` tiene que elegir dirección y va a
contradecir la mitad que no elija. Y "el `git diff` no introduce un `@media`
con un ancho nuevo" se puede satisfacer **rompiendo el rango 640-799px**. El
plan tampoco dice en qué breakpoint se activan las zonas: cita 800 y 1000.

*Decisión (estructural → auto-fix, P5):* `min-width` mobile-first para las
áreas nuevas, **1000px** como único breakpoint de activación (consistente con
el umbral de drag-and-drop de la decisión activa del 2026-09-08), y
verificación explícita en 640-799px.

*Decisión (TODO):* DESIGN.md formal vía `/design-consultation`. Sexta vez
recomendado — el próximo paso útil es agendarlo o descartarlo a propósito, no
recomendarlo una séptima vez.

#### Pass 6: Responsive y accesibilidad — 3/10 → 8/10

**6.1 (CRÍTICO, ya decidido en 1.3)** — móvil es el caso principal declarado y
no recibía ningún cambio. Resuelto con el sticky de la zona primaria.

**6.2 (ALTA) — accesibilidad no especificada en ninguna fase.** El panel se usa
con el pulgar, de pie, posiblemente con sol directo. Lo que falta: targets
(solo `.tap-button` está nombrado; el botón "Sacar" de la alineación es
`.link-button`, o sea un link de texto como target táctil primario a 375px);
anuncio a lectores de pantalla (cero `aria-live`); contraste (no especificado,
y el escenario es sol directo); orden de tabulación.

*Decisión (estructural → auto-fix, P5):* 44px mínimo para todo target de zonas
1 y 2 incluido "Sacar"; contraste de cuerpo ≥4.5:1; `aria-live="polite"` para
la confirmación; orden de tab siguiendo el orden de zonas.

**6.3 (ALTA) — la expansión 1 está especificada como ubicación de código, no
como diseño.** La Fase 1 resolvió *dónde* vive la derivación y el effort. Falta
todo lo visual: sin tratamiento, sin decir si una y dos amarillas se leen
distinto, sin ubicación, y **sin codificación independiente del color** — que es
justo la que falla para daltonismo bajo sol directo.

*Decisión (estructural → auto-fix, P5):* badge con **texto y forma además de
color** (`1A`, `2A`, `R`), en la lista de alineación **y** en los candidatos
`.tap-button` de `ModalSustitucion`.

#### Pass 7: Decisiones de diseño sin resolver

```
  DECISIÓN NECESARIA                         | SI SE DIFIERE, QUÉ PASA
  -------------------------------------------|---------------------------------------
  ¿Se puede sustituir sin convocatoria? (2.3)| La respuesta que implica el plan es NO,
                                             | y nadie lo dijo en voz alta
  ¿Qué se ve sin scrollear a 375px? (1.2)    | El implementador lo inventa al teclado
  ¿El mesero se entera de que su toque       | Toca de nuevo → el doble-submit que
  funcionó? (2.1)                            | Track A atrapa en la DB
  Orden buscar → conflicto → confirmar (7.1) | Tres formas posibles, ninguna elegida
  ¿Se escribe DESIGN.md? (Pass 5)            | Séptima recomendación ignorada
```

**7.1 (ALTA) — C1 deja sin decidir la secuencia de pasos, que es LA pregunta de
diseño.** La advertencia de conflicto (`⚠️ {nombre} ya está inscrito en
{equipos}`, `DetalleEquipo.tsx:224-251`) se dispara **después** de una
selección, y el selector es dueño de la selección. ¿La advertencia reemplaza la
búsqueda en el lugar, aparece debajo con los resultados visibles, o es un
segundo paso de modal? ¿El campo queda enfocado o se bloquea? ¿Dónde vive
"Crear jugador nuevo" respecto de cero resultados? Nada contestado, y todo eso
es lo que el implementador inventa a las 11 de la noche.

*Decisión (estructural → auto-fix, P5):* dos paneles dentro de **un** modal —
el selector queda montado y visible pero inerte (atenuado, no enfocable)
mientras la confirmación se renderiza debajo de la fila elegida, con "Volver a
buscar" a un toque.

**7.2 (refuerza el descarte de B1, no pide arreglo) — el empty state de B1
habría enviado una mentira al usuario.** `EquiposAdmin.tsx:268-277` distingue a
propósito el vacío filtrado del real, con el comentario explicando por qué: "un
empty-state que no los distingue manda al admin a crear un duplicado de un
equipo que ya existe en otra disciplina". Las dos cadenas conmutan sobre
`hayFiltros`.

B1 introducía una **tercera** causa de vacío (`alcance=asignados`) que no es un
filtro puesto por el usuario, así que `hayFiltros` es `false` y el listado
caería en "No hay equipos creados todavía." — **factualmente falso** para un
TorneoAdmin sin asignaciones, y precisamente el modo de fallo que ese código se
escribió para evitar.

*Decisión: ninguna acción — B1 ya se descarta (Fase 1, Hallazgo 3.2). Esto es
evidencia adicional a favor del descarte.*

**7.3 (MEDIA) — el orden serial pone todo lo visible detrás de la fase menos
especificada.** Todo el programa de UI queda detrás de A2, que la propia Fase 1
marca como riesgo de cronograma. *Decisión (auto-fix, P6):* se vuelve
**incondicional** — orden nuevo
**`A0 → A1 → C1 → C2a → C2b → D1 → exp.1 → A2 → A3`**.

**7.4 (MEDIA) — si E1 o F1 se reabren, les falta toda la UI.** E1 no dice qué
clickea el usuario, y la paginación con cursor no puede renderizar páginas
numeradas, así que el modelo de interacción es una elección forzada que el plan
no hace; tampoco dice que el banner `truncado` se retira en el mismo cambio.
F1 resume su UI en una oración y deja abiertas dos cosas de diseño: el flujo
para **agregar** la modalidad y si el `Slug` se muestra o se esconde.
*Decisión: restricciones de reapertura, no trabajo de hoy.*

#### "NOT in scope" — Fase 2

| Ítem | Motivo |
|---|---|
| Cambiar el orden ascendente del timeline | Decisión activa del usuario (2026-09-09) |
| Iconos SVG por disciplina en vez de emoji | `TODOS.md`, Descartado a propósito |
| Rediseño visual (tipografía, paleta) | Sin DESIGN.md no hay contra qué calibrar; D1 es estructura |
| Navegación por teclado completa | Caso principal es un pulgar; se fija orden de tab y nada más |
| UI de E1 y F1 | Diferidos en Fase 1; quedan como restricciones de reapertura |
| Tercera rama de empty state de B1 | B1 descartado; requisito solo si reabre |

#### "What already exists" — Fase 2

Ver 0C. Los dos que el plan ignoraba y ahora reusa: el patrón `aria-live`
(6 archivos) para la confirmación de 2.1, y la distinción de empty-state
filtrado-vs-real de `EquiposAdmin` como precedente de por qué 7.2 importa.

#### Resumen de finalización — Fase 2 (Design)

```
  +====================================================================+
  |         DESIGN PLAN REVIEW — COMPLETION SUMMARY                    |
  +====================================================================+
  | System Audit         | Sin DESIGN.md (6º plan); UI scope: C1, C2,  |
  |                      | D1, exp.1 (+E1/F1 diferidos)                |
  | Step 0               | 2/10 inicial; foco: las 7 dimensiones       |
  | Pass 1  (Info Arch)  | 3/10 → 8/10                                 |
  | Pass 2  (States)     | 2/10 → 8/10                                 |
  | Pass 3  (Journey)    | 3/10 → 8/10                                 |
  | Pass 4  (AI Slop)    | 7/10 → 8/10                                 |
  | Pass 5  (Design Sys) | 4/10 → 7/10  (techo sin DESIGN.md)          |
  | Pass 6  (Responsive) | 3/10 → 8/10                                 |
  | Pass 7  (Decisions)  | 4 resueltas, 2 registradas para reapertura  |
  +--------------------------------------------------------------------+
  | NOT in scope         | written (6 items)                           |
  | What already exists  | written (7 patrones)                        |
  | TODOS.md updates     | 1 item propuesto (DESIGN.md formal)         |
  | Approved Mockups     | 0 IA (sin API key), 1 wireframe HTML        |
  | Decisions made       | 13 auto-decididas (estructurales, P5)       |
  | Decisions deferred   | 0 sin resolver; 1 taste al Gate             |
  | Overall design score | 2/10 → 7/10  (mínimo de los 6 passes)       |
  +====================================================================+
```

**Overall 7/10**, no 8+, por el techo del Pass 5: sin DESIGN.md no se puede
calificar alineación de sistema más alto. Los otros cinco passes quedan en 8.

#### Decisión de taste al Gate — Fase 2

- **T-2** D1 a 375px: `position: sticky` en la zona primaria (recomendado —
  hace que D1 sirva al caso principal declarado) vs diferir D1 entera hasta que
  exista DESIGN.md (evita shipear una reorganización de escritorio a una
  pantalla de teléfono).

<!-- autoplan-accepted:design -->
- D1 arranca con la asignación de zonas FIJADA, no delegada: primaria = marcador + reloj + estado; secundaria = grilla de tipos de evento + alineación en vivo; terciaria = timeline + `Finalizar partido`. Referencia concreta: `~/.gstack/projects/Score-App/designs/mesa-panel-3-zonas-20260917/wireframe-zonas.html` (375px y ≥1000px). Verificación: el plan de D1 cita el wireframe y ya no contiene "se confirma en la revisión de diseño".
- D1 entrega la zona primaria a 375px con `position: sticky; top: 0` sobre `.marcador` + `.marcador__estado` (`MesaPanel.tsx:452-457`). Sin esto, una grilla de 3 zonas que colapsa a una columna no cambia nada para el caso principal declarado (teléfono al borde de la cancha) y D1 sería mejora solo de escritorio. Verificación: a 375px el marcador y el reloj siguen visibles después de scrollear a la zona 2.
- D1 agrega una confirmación `aria-live="polite"` anclada en la zona donde se tocó, con el contenido del evento (ej. "Cambio registrado: sale #7 López, entra #14 Díaz (72')"). Hoy hay CERO `aria-live` en `MesaPanel.tsx` y ninguna confirmación de éxito, mientras 6 archivos del repo ya usan el patrón. El orden ascendente del timeline NO se toca (decisión activa del usuario del 2026-09-09). Verificación: test que afirma la región `aria-live` y su contenido tras una carga exitosa.
- SUPERSEDE de la obligación de Fase 1 sobre C2 ("C2 no se mergea hasta que exista un test de `ModalSustitucion` con `sinConvocatoria=true` que pase"): esa obligación era INAPLICABLE porque no existe camino `sinConvocatoria` hacia `ModalSustitucion` — el botón "Sacar" solo se renderiza dentro de `titularesEquipo.map(...)`, `titularesEquipo` se deriva de la convocatoria, y sin convocatoria la lista sale vacía sin ningún botón (el propio comentario del código lo dice). Reemplazo: C2 se divide en **C2a** (diseñar y construir el punto de entrada sin convocatoria; forma recomendada: la lista de alineación en vivo cae a la `plantilla` completa con el caption "Sin convocatoria guardada — mostrando plantilla completa", una sola lista para los dos estados, preservando D4) y **C2b** (recién después, retirar la rama de `CargaEvento`). Gate elevado: no "un test pasa", sino "un árbitro completa un cambio de punta a punta en un partido sin convocatoria guardada, con el mismo gesto que con convocatoria".
- El empty state de `ModalSustitucion` (`ModalSustitucion.tsx:43-44`) gana una acción primaria que rutea a "Gestionar Partido › Convocatoria" y vuelve al partido al guardar. Hoy es instrucción sin navegación (solo "Cancelar"), y después de C2b sería el estado terminal de todo partido con convocatoria incompleta. Prerrequisito de C2b.
- El rescate de `DeadlockDetected` de A1 recibe tratamiento visual distinto del error de validación permanente, y un botón "Reintentar" que re-envía el mismo payload. Hoy ambas superficies (`submitError` de `CargaEvento`, `error` de `ModalSustitucion`) renderizan todo error igual como `<p className="error-text">`, así que el único error transitorio del sistema se vería idéntico a un rechazo definitivo. Verificación: el error de deadlock no comparte clase con un 4xx de validación, y el botón re-envía sin que el usuario rearme el formulario.
- La expansión 1 (si se aprueba) especifica el tratamiento visual, no solo la ubicación del código: badge en la fila del jugador con TEXTO Y FORMA además de color (`1A`, `2A`, `R`), mostrado en la lista de alineación en vivo y en los candidatos `.tap-button` de `ModalSustitucion`. Color solo es la codificación que falla para daltonismo bajo sol directo, que es el entorno real de uso. Verificación: el badge se distingue en escala de grises.
- D1 declara `min-width` mobile-first para las áreas nuevas y nombra 1000px como el ÚNICO breakpoint de activación de las 3 zonas (consistente con el umbral de drag-and-drop de la decisión activa del 2026-09-08). `index.css` mezcla direcciones (`min-width` en 800/1000, `max-width` en 480/640), así que la verificación de Fase 1 ("no introduce un `@media` con un ancho nuevo") se podía satisfacer rompiendo el rango 640-799px. Verificación añadida: inspección explícita entre 640 y 799px.
- D1 fija accesibilidad: 44px mínimo para todo target de las zonas 1 y 2, incluido el botón "Sacar" (hoy es `.link-button`, un link de texto como target táctil primario a 375px); contraste de cuerpo ≥4.5:1 (el escenario es sol directo); orden de tabulación siguiendo el orden de zonas.
- C1 especifica la secuencia de pasos antes de refactorizar: dos paneles dentro de UN modal — el selector queda montado y visible pero inerte (atenuado, no enfocable) mientras la confirmación de conflicto se renderiza directamente debajo de la fila elegida, con "Volver a buscar" a un toque. Sin esto quedan tres secuencias posibles, ninguna elegida, y la elige el implementador.
- Cada fase reorganizada nombra su tratamiento de estado pending en una línea. Hoy `isPending` solo deshabilita botones, así que con red lenta y sin mensaje de éxito la pantalla se ve muerta.
- El orden serial pasa a `A0 → A1 → C1 → C2a → C2b → D1 → exp.1 → A2 → A3`: A2/A3 van detrás de D1 de forma INCONDICIONAL, no sujeta a un juicio bajo presión de cronograma. A2 es el ítem menos especificado del plan y bloqueaba todo lo visible para el usuario; A1 no depende de A2 y conserva su valor.
- Si E1 se reabre: el control es "Cargar más" que appendea en el lugar; el banner `truncado` y su string se retiran en el MISMO commit (si no, la página muestra a la vez un cargar-más y un aviso que dice filtrá); `siguiente_cursor: null` muestra "Fin de la lista", no un botón deshabilitado sin explicación; las filas quedan montadas con una fila de carga agregada, nunca se blanquea la tabla en un fetch de página siguiente.
- Si F1 se reabre: el alta pide o agenda la primera modalidad (una disciplina sin modalidades es un registro roto), y el `Slug` se muestra como campo de solo lectura con la leyenda "Definido al crear; cambiarlo requiere migración".
- Si B1 se reabre como scoping forzado server-side: requiere una TERCERA rama de empty state nombrando la causa real ("No tenés torneos asignados con equipos inscritos. Pedí una asignación a un AdminGeneral."), un indicador persistente de alcance, y rewrite del banner `truncado`. `EquiposAdmin.tsx:268-277` distingue a propósito vacío-filtrado de vacío-real y `hayFiltros` sería `false` para el filtro de alcance, así que el listado habría dicho "No hay equipos creados todavía" a un TorneoAdmin sin asignaciones: factualmente falso.
<!-- /autoplan-accepted:design -->

#### Decision Audit Trail — Fase 1

| # | Fase | Decisión | Clasificación | Principio | Rationale | Rechazado |
|---|---|---|---|---|---|---|
| 1 | ceo | Modo SELECTIVE EXPANSION | Mechanical | P6 | Default de /autoplan e iteración sobre sistema existente | Los otros 3 modos |
| 2 | ceo | A0 pasa de fase a precondición | Mechanical | P6 | Un `git clean` borra un motor de reglas con 520 tests verdes | Dejarlo como fase |
| 3 | ceo | A1 rescata `DeadlockDetected`, **condicionado a #21** | Mechanical | P1 | Segundo locker sobre `PARTIDOS`; hoy el deadlock sale 500. Reintento inseguro hasta que `create` sea atómico | Lock sin camino de error; reintento ciego |
| 4 | ceo | A1 loguea espera de lock, con umbral y consumidor nombrados | Mechanical | P1 | Prime Directive #5: observabilidad es alcance. Sin consumidor sería trabajo invisible | Diferir a post-launch; log sin destino |
| 5 | ceo | Guard de nombre de base ante operación destructiva, alcance corregido al `DROP DATABASE` existente | Mechanical | P1 | `_recreate_test_database` ya hace `DROP DATABASE IF EXISTS` sin guard hoy; no hay ningún `TRUNCATE` todavía | Guardar solo el `TRUNCATE` hipotético |
| 6 | ceo | C2 antes de D1, y test de `sinConvocatoria` antes del retiro | Mechanical | P1 | Sin él, un partido sin convocatoria queda sin camino para Cambio | Retirar primero |
| 7 | ceo | C1 no absorbe conflicto/alta en el selector | Mechanical | P5 | 6 props opcionales = configurable, no compartido | Selector con props |
| 8 | ceo | C1 escribe su test antes de refactorizar | Mechanical | P1 | `DetalleEquipo` no tiene test hoy | Refactor sin red |
| 9 | ceo | F1 no escribe lógica de slug | Mechanical | P4 | `fn_generar_disciplina_slug` ya lo hace correcto | Reimplementar en Python |
| 10 | ceo | Orden serial con stop-the-line | Mechanical | P5 | 5 tracks paralelos con 1 dev = 5 ramas a medias | Independencia paralela |
| 11 | ceo | B2 invertido (ad hoc antes del artefacto) | Mechanical | P3 | 0 filas de `usuarios` en `AUDITORIA`, medido | Commitear el .sql primero |
| 12 | ceo | Resultado observable por track | Mechanical | P1 | Sin eje de resultado el plan no puede priorizar | Solo "tests verdes" |
| 13 | ceo | Auto-refresh/minuto en vivo → TODOS.md | Mechanical | P3 | Fuera de radio de acción, P3 | Meterlo en este ciclo |
| 14 | ceo | `handlers.py` 400-para-todo → TODOS.md | Mechanical | P3 | Preexistente, alcance propio | Arreglarlo acá |
| 15 | ceo | Expansión 1 (estado de tarjetas) recomendada | **Taste** | P2 | En radio de D1, <1 día CC; arregla la otra mitad del problema del mesero | Solo reorganizar franjas |
| 16 | ceo | Umbrales numéricos para E1/F1 | Mechanical | P1 | Convierte "algún día" en disparador accionable | Diferimiento vago |
| 17 | ceo | A2 fixture completa vs test determinista | **Taste → Gate** | P1 vs P3 | 1 ocurrencia en 35 eventos; T23/T24 piden 2 conexiones reales | — |
| 18 | ceo | Diferir E1 | **User Challenge → Gate** | P3 | 270/1787 filas, `limit` 200, PK indexada; sin p95 medido | Ejecutarlo |
| 19 | ceo | Diferir F1 | **User Challenge → Gate** | P3 | 28 disciplinas = el seed exacto; revierte Decisión C1 | Ejecutarlo |
| 20 | ceo | Descartar B1 como está propuesto (se reabre como scoping forzado si hay fuga) | **User Challenge → Gate** | P4 | Sin `torneo_id`; `alcance=` con default permisivo no es autorización | Ejecutarlo como está |
| 21 | ceo | **A1 se reestructura a transacción única, no se parchea** | Mechanical | P1 | `BaseRepository.create` commitea y libera el `FOR UPDATE` antes de la lectura de la doble amarilla; el swap de una línea no arregla nada | Swap de una línea (lo que decía el plan) |
| 22 | ceo | A0 y A2 se agregan a la línea de Approach B | Mechanical | P1 | A2 es prerrequisito duro de A3; la revisión 1 aceptaba alcance dentro de A2 sin agendarla | Dejarlas implícitas |
| 23 | ceo | Recuento 6/3 → 5/4; B2 cuenta como diferido | Mechanical | P6 | B2 ya se ejecutó en esta revisión y dio cero; contarlo como ejecutado inflaba el cierre | Contar B2 como ejecutado |
| 24 | ceo | Separar filas orgánicas de sintéticas en toda medición | Mechanical | P1 | 1750 de 1787 jugadores son `MOCK-`; los totales crudos no miden uso | Usar los totales crudos |
| 25 | ceo | Retirar el argumento "5.6x de margen" de E1 | Mechanical | P6 | Era una estimación disfrazada de medición, y apunta a un riesgo inalcanzable (`offset` siempre 0) | Mantenerlo |
| 26 | ceo | Track A se justifica por consecuencia, no frecuencia | Mechanical | P6 | Frecuencia medida = 0 casos de 2 amarillas sin roja; el estándar de evidencia tiene que ser simétrico | Justificarlo por "pasó 1 de 35" |
| 27 | ceo | Umbrales de reapertura escritos como números | Mechanical | P1 | La revisión 1 los prometía sin escribirlos | Diferimiento vago |
| 28 | ceo | Expansión 1 reusa la preview de `ModalResultadoDirecto` | Mechanical | P4 | Ya hay 2 copias de la regla de doble amarilla; una tercera es slop | Escribirla de nuevo |
| 29 | ceo | Casing minúscula en el filtro `Tabla` de B2 | Mechanical | P6 | `Tabla` guarda `__tablename__`; `'USUARIOS'` da cero falso | `Tabla='USUARIOS'` como decía el plan |
| 30 | ceo | `EQUIPOS` orgánico = 10, no 270; se re-deriva el motivo de E1 | Mechanical | P6 | 260 de 270 son de grupos de estrés; el banner solo lo dispara data sintética | "el techo ya se alcanza y está mitigado" |
| 31 | ceo | Umbral de E1 re-anclado a 150 orgánicos, no 5.000 | Mechanical | P1 | El tope de página es 200; 5.000 dejaba el ítem cerrado en todo el rango donde duele | 5.000 jugadores |
| 32 | ceo | La regla de doble amarilla tiene CERO ejercicio real | Mechanical | P6 | Eventos del 2026-09-08; `reglas_tarjetas.py` commiteado el 2026-09-14; la roja está al min 55, no al 5 | "el bug nunca ocurrió, la red sostuvo" |
| 33 | ceo | Condición de terminado de A0 definida: 8 archivos, 6+TODOS.md al baseline, MesaPanel aparte | Mechanical | P1 | La revisión 2 decía 7 en un lugar y 5 en otro contra 8 reales, sin decir cuáles | Dejarlo ambiguo |
| 34 | ceo | A1 elimina DOS commits, no uno | Mechanical | P1 | `_procesar_doble_amarilla_si_corresponde` tiene su propio `commit()` en :124-125 | Solo el de `repo.create` |
| 35 | ceo | Expansión 1 se deriva en `components/eventos.ts` | Mechanical | P4 | `ModalResultadoDirecto` deriva de batch local sin guardar — shape equivocado; `eventos.ts` ya es el módulo compartido de `MesaPanel` | `ModalResultadoDirecto` |
| 36 | ceo | A2 necesita bosquejo de enfoque antes de arrancar, o se mueve al final | Mechanical | P6 | Es el ítem menos especificado y bloquea a 4 tracks en cadena serial | Dejarlo segundo sin bosquejo |
| 37 | design | D1 arranca con zonas FIJADAS + wireframe de referencia | Mechanical | P5 | Delegar a "la revisión de diseño" sin wireframe = decisión descartada, no diferida | Delegar la asignación |
| 38 | design | `position: sticky` en zona primaria a 375px | **Taste → Gate** | P1 | Sin esto, 3 zonas que colapsan a 1 columna no cambian nada para el caso principal declarado | Solo reorganizar escritorio |
| 39 | design | Confirmación `aria-live` en la zona donde se tocó | Mechanical | P5 | 0 `aria-live` en MesaPanel vs 6 archivos que ya lo usan; sin acuse el mesero toca de nuevo | Sin estado de éxito |
| 40 | design | **SUPERSEDE** C2 → C2a (entrada sin convocatoria) + C2b (retiro) | Mechanical | P1 | La obligación de Fase 1 era inaplicable: no hay camino `sinConvocatoria` hacia `ModalSustitucion` | El test de render de Fase 1 |
| 41 | design | Gate de C2 elevado a recorrido punta a punta | Mechanical | P1 | Un test de render "pasaría" afirmando un estado que la UI nunca alcanza | "un test con sinConvocatoria pasa" |
| 42 | design | Empty state de `ModalSustitucion` gana acción primaria | Mechanical | P5 | Instrucción sin navegación; después de C2b es estado terminal | Dejarlo como callejón |
| 43 | design | Error de deadlock con tratamiento distinto + "Reintentar" | Mechanical | P5 | El único error transitorio se vería igual que un rechazo permanente | Reusar `.error-text` |
| 44 | design | Badge de tarjetas con texto y forma, no solo color | Mechanical | P1 | Color solo falla para daltonismo bajo sol directo, que es el entorno real | Solo color |
| 45 | design | Breakpoint único de activación 1000px, mobile-first | Mechanical | P5 | `index.css` mezcla min/max-width; la verificación de Fase 1 pasaba rompiendo 640-799px | "reusar los existentes" sin elegir |
| 46 | design | 44px mínimo en zonas 1 y 2, incluido "Sacar" | Mechanical | P5 | "Sacar" es `.link-button`: un link de texto como target táctil a 375px | Dejarlo como link |
| 47 | design | C1 fija la secuencia buscar → conflicto → confirmar | Mechanical | P5 | Tres secuencias posibles; la elegiría el implementador a las 11pm | Dejarla abierta |
| 48 | design | Orden serial: A2/A3 detrás de D1, incondicional | Mechanical | P6 | Todo lo visible para el usuario estaba detrás del ítem menos especificado | Condicionarlo a un juicio |
| 49 | design | Restricciones de reapertura para E1/F1/B1 registradas | Mechanical | P1 | Diferir sin registrar la UI faltante es perder el hallazgo | Omitirlas |
| 50 | design | DESIGN.md formal → TODO (6ª vez recomendado) | Mechanical | P3 | 5 recomendaciones previas no movieron nada; agendarlo o descartarlo, no recomendarlo de nuevo | Recomendarlo otra vez sin más |


### Fase 2.5 — DX review (single-model, DX POLISH)

Alcance DX disparado por el helper: `dxRequired: true`, 10 matches (`API`×9,
`webhook`×1) sobre umbral 2. Voz externa: **codex no disponible
(not_installed)** — cayó a un subagente de Claude (contexto fresco, mismo
harness; identidad de modelo desconocida). Toda afirmación cargada del
subagente se verificó contra el código antes de aceptarla; las que no se
pudieron verificar no entraron.

#### Step 0A — Persona del desarrollador

Este producto no es una herramienta para desarrolladores. Es una app de
gestión de torneos. Fingir lo contrario haría inútil la revisión. La
superficie de desarrollador real que este plan toca son dos, y las dos
importan:

```
TARGET DEVELOPER PERSONA
========================
Who:       Contribuidor de este repo. Hoy sos vos; manana, la segunda persona
           que clone SCORE_APP. Python + TypeScript, sin contexto previo del
           dominio de torneos.
Context:   Clona el repo para arreglar un bug o sumar una fase de un plan de
           docs/plans/. Primer acto: levantar el stack y correr verificar.ps1.
Tolerance: ~15 min hasta el primer verde. Pasado eso empieza a sospechar que
           el repo esta roto, no su maquina.
Expects:   Un comando de setup, un .env.example por cada .env que el codigo
           lee, y que la suite por defecto sea rapida y hermetica.

PERSONA SECUNDARIA (consumidor de la API)
=========================================
Who:       El frontend de este mismo repo — el UNICO cliente de la API.
Context:   Consume un cliente TypeScript generado del OpenAPI (npm run gen:api).
Tolerance: Cero para roturas silenciosas: su garantia declarada es que tsc
           avisa cuando el contrato cambia.
Expects:   Que esa garantia valga en el 100% de las rutas. Hoy no vale en una.
```

Auto-decidido (P6, tipo de desarrollador más común del producto). Sin usuario
externo que instale o integre esto, la persona "contribuidor" es la única con
demanda real.

#### Step 0B — Narrativa de empatía (primera persona)

> Clono SCORE_APP. El README es de los buenos: en la primera pantalla me dice
> qué es, con qué está hecho y cómo levantarlo. Corro `pip install -r
> backend/requirements.txt` y `npm install`. Voy a `database/README.md` como me
> indica y armo `torneos_mvp` con los scripts 01 a 06. Copio
> `backend/.env.example` a `backend/.env` y le pongo mi clave.
>
> Levanto el backend: `python run.py`. `http://localhost:8000/health` dice
> `{"status":"ok"}`. Voy ganando.
>
> Levanto el frontend: `npm run dev`. Compila. Abro `localhost:5173`, me pide
> login, pongo admin/admin1234 y... no pasa nada. La pestaña de red dice que
> hizo un POST a `undefined/api/v1/auth/login`. No hay error en la consola del
> backend porque el request nunca llegó al backend.
>
> Busco "undefined" en el repo. Nada. Busco la URL del login y llego a
> `AuthContext.tsx:72`: `${import.meta.env.VITE_API_BASE_URL}`. Busco esa
> variable: `client.ts:4` la lee sin default. Busco `frontend/.env.example`.
> **No existe.** `.gitignore` ignora `.env` y solo deja pasar `.env.example`,
> que alguien creó para `backend/` y nunca para `frontend/`.
>
> Son 18 minutos. El arreglo es una línea. No hay forma de deducirla del README.

**Verificado, no hipotético:** `frontend/src/api/client.ts:4` es
`const BASE_URL = import.meta.env.VITE_API_BASE_URL as string;` sin fallback;
`frontend/src/auth/AuthContext.tsx:72` la interpola directo en el `fetch` del
login; `.gitignore:14-15` es `.env` + `!.env.example`; `backend/.env.example`
existe en el repo y `frontend/.env.example` no. El `frontend/.env` que tenés
en tu máquina (`VITE_API_BASE_URL=http://127.0.0.1:8000`) está ignorado por
git, así que nadie más lo recibe.

#### Step 0C — Benchmark competitivo

Aside no está instalado (`NEEDS_ASIDE`); la búsqueda corrió por WebSearch.

```
COMPETITIVE DX BENCHMARK
=========================
Referencia                  | TTHW      | Eleccion DX notable          | Fuente
Monorepo con Docker         | < 5 min   | un compose levanta todo      | vintasoftware (Django+React)
FastAPI (generico)          | ~minutos  | Swagger/ReDoc de fabrica     | ecosistema FastAPI
API onboarding (industria)  | 5 min     | "time-to-first-call" como KPI| youngcopy
Stripe / Vercel (referencia)| 30s / 2min| sandbox sin instalar         | tabla de referencia gstack
SCORE-APP (medido hoy)      | ~25 min   | README honesto y bien escrito| este repo
```

Los ~25 min salen del camino real del README: Postgres + `pip install` +
`npm install` + armar la base desde `database/` + `backend/.env` + el pozo de
`frontend/.env` de 0B. Sin ese pozo son ~12 min; con él, hasta que alguien
lee `client.ts`, es abierto.

**Tier elegido: Competitive (2-5 min).** Auto-decidido (P1 + P5: siempre
optimizar hacia menos pasos). Champion (<2 min) exigiría un devcontainer y
una base sembrada de fábrica — infraestructura nueva, fuera del blast radius
de este plan.

#### Step 0D — Momento mágico

Para un contribuidor, el momento mágico no es el hello world de la API. Es
**`.\verificar.ps1` en verde sobre un clon recién hecho**: 486 tests de
backend, lint, typecheck, tests de frontend y build de producción, todo de un
comando. Ese único comando es lo mejor que tiene este repo en DX y hoy está
detrás de un setup manual de 25 minutos.

**Vehículo elegido (P5, el de menor esfuerzo que alcanza el tier, y P4, reusa
lo que ya existe):** extender `infrastructure/docker-compose.yml` para que
también levante Postgres y corra `database/01`–`06` al inicializar, más
`frontend/.env.example`. El compose ya existe y ya levanta la API; hoy asume
"Postgres corre en el host (ya lo tenés instalado y con torneos_mvp
cargado)", que es exactamente la suposición que rompe a la segunda persona.
Rechazado: devcontainer (infraestructura nueva), script `setup.ps1` a mano
(duplica lo que el compose ya sabe hacer, viola P4).

(human: ~4 h / CC: ~30 min)

#### Step 0E — Modo

**DX POLISH.** Override de /autoplan, y además el default correcto por
contexto: esto es mejora de un producto existente, no un producto nuevo
orientado a desarrolladores. Sin adiciones de alcance; rigor máximo sobre
cada punto de contacto que el plan ya toca.

#### Step 0F — Traza del viaje del desarrollador (6 etapas, POLISH)

| Etapa | El dev hace | Fricción (con evidencia) | Estado |
|---|---|---|---|
| 1. Discover | Lee `README.md` | Ninguna. La primera pantalla dice qué es, con qué, y cómo levantarlo. El mejor artefacto del repo. | ok |
| 2. Install | `pip install`, `npm install`, arma la base desde `database/` | `infrastructure/docker-compose.yml` existe pero el README solo lo nombra en la tabla "Dónde está cada cosa", nunca en "Levantar todo". El camino documentado es el manual. | fixed (DX-2) |
| 3. Hello World | `python run.py` → `/health`, `npm run dev` → login | **`frontend/.env.example` no existe.** `client.ts:4` lee `VITE_API_BASE_URL` sin default; el login POSTea a `undefined/...`. Falla en silencio del lado del backend. | fixed (DX-1) |
| 4. Real Usage | Cambia un schema, corre `npm run gen:api`, `tsc` avisa | La garantía del README:68-69 no vale en `GET /jugadores`: `response_model=None` + `responses=RESPUESTA_LISTA_JUGADORES` mantenido a mano (`routes/jugadores.py:22-24,39`). E1 lo rompería en silencio. | fixed (C2, como condición de reapertura) |
| 5. Debug | Lee el error, corre `.\verificar.ps1` | `verificar.ps1:46` es `python -m pytest -q` sin filtro de marcas; A2/A3 meten tests lentos y no herméticos en la corrida por defecto. `backend/pytest.ini` no tiene bloque `markers =` ni `--strict-markers`, así que un typo en `-m "not concurenica"` deselecciona nada y reporta verde. | fixed (H1) |
| 6. Upgrade | Aplica migraciones de `database/` | La guardia de tres lugares (`01_schema.sql` + script `NN_` + `SCRIPTS_VIGENTES` de `test_scripts_sql.py:36-48`) está en el plan dos veces y en `database/README.md` ninguna. Es el que produce el `UndefinedColumn` en ~40 archivos de test. | fixed (M7) |

#### Step 0G — Reporte de confusión del primer día

```
FIRST-TIME DEVELOPER REPORT
============================
Persona: contribuidor nuevo de SCORE_APP
Attempting: clon -> verificar.ps1 en verde

CONFUSION LOG:
T+0:00  Clono. Leo README.md. Claro. Corro pip install y npm install.
T+0:04  database/README.md me advierte que la numeracion no es cronologica.
        Lo agradezco. Armo torneos_mvp con 01-06.
T+0:09  cp backend/.env.example backend/.env. Genero JWT_SECRET_KEY.
        python run.py. /health responde ok. Todo bien hasta aca.
T+0:11  npm run dev. Compila. Login con admin/admin1234. No pasa nada.
T+0:14  Red: POST a undefined/api/v1/auth/login. El backend no registra nada
        porque el request nunca salio hacia el.
T+0:18  Llego a client.ts:4. Busco frontend/.env.example. No existe.
        Escribo el .env a mano. Entro.
T+0:22  Corro .\verificar.ps1. Verde. Ahora si empiezo a trabajar.
```

Auto-decidido: **arreglar todos los puntos de confusión** (P1 completeness).
Los dos son de un archivo cada uno y están en el blast radius del plan (el
plan ya toca `verificar.ps1` implícitamente vía A2/A3 y ya toca el setup de
tests).

#### Step 0.5 — Voces duales (DX)

**CODEX SAYS (DX):** no disponible — `CODEX_MODE: not_installed`. Sin
cobertura externa en esta fase. `outside_status: unavailable`.

**OUTSIDE VOICE (subagente Claude, DX):** completado. INPUT
`dx bbb02b87ccaf446d8835a707434a3ef7b86d652ceaf4b5270ffe40fba8544eaf`
verificado contra el snapshot. 2 críticos, 8 altos, 9 medios.

```
DX DUAL VOICES — CONSENSUS TABLE:
===============================================================
  Dimension                           Claude  Codex  Consensus
  ----------------------------------- ------- ------ ---------
  1. Getting started < 5 min?          NO      N/A    N/A
  2. API/CLI naming guessable?         NO      N/A    N/A
  3. Error messages actionable?        NO      N/A    N/A
  4. Docs findable & complete?         PARCIAL N/A    N/A
  5. Upgrade path safe?                PARCIAL N/A    N/A
  6. Dev environment friction-free?    NO      N/A    N/A
===============================================================
0/6 CONFIRMED. Codex ausente => N/A en las 6, nunca CONFIRMED.
Todo hallazgo de esta fase es de una sola voz. Marcados abajo.
```

**Hallazgo crítico de una sola voz (marcado según la regla):** C1 y C2 abajo
vienen del subagente sin confirmación externa. Los acepto igual porque los
verifiqué contra el código yo mismo, no porque un segundo modelo los avale.

#### Pass 1: Getting Started — 3/10 → 8/10

Es un 3 porque el contribuidor de 0A tarda ~25 min contra un tier objetivo de
2-5, y porque el pozo de `frontend/.env.example` (verificado en
`client.ts:4` + `.gitignore:14-15`) no tiene forma de deducirse del README:
el síntoma es un POST a `undefined/...` que el backend nunca ve. Un 10 acá es
`docker compose up` + `.\verificar.ps1` verde, sin pasos manuales.

Fixes (todos Mechanical): **DX-1** agregar `frontend/.env.example` con
`VITE_API_BASE_URL=http://127.0.0.1:8000`; **DX-2** extender
`infrastructure/docker-compose.yml` con el servicio Postgres y la carga de
`database/01`–`06`, y nombrarlo en "Levantar todo" del README como el camino
recomendado, dejando el manual como alternativa.

No se agrega un default en `client.ts`: un default silencioso convierte un
fallo de configuración en un fallo de red intermitente, que es peor de
diagnosticar. El `.env.example` es el arreglo correcto (P5, explícito sobre
ingenioso).

#### Pass 2: API/CLI/SDK Design — 3/10 → 8/10

Es un 3 por tres cosas, todas verificadas:

1. **Dos formas de envelope para el mismo concepto.** E1 especifica
   `{items, siguiente_cursor}` citando el feed como precedente. El precedente
   real, `FeedResponseOut` (`backend/app/schemas/partido.py:290-303`), es
   `{fecha_pedida, fecha_efectiva, total_disponible, partidos}` — colección
   nombrada por el recurso, más un total. Shippear `items` deja dos
   convenciones y bifurca cada camino de listado del frontend.
2. **B1 deja que el cliente elija su propio alcance de autorización.** Hoy el
   scoping es implícito y derivado del token. El `alcance=asignados|disciplina`
   del plan lo vuelve un query param con default ancho.
3. **Regla de nombres sin escribir.** `alcance` (español) al lado de
   `skip`/`limit`/`q` (inglés) y `disciplina_id`/`estado` (español). El repo
   ya mezcla; el plan suma sin fijar la regla, así que el próximo parámetro la
   vuelve a litigar.

E1 y B1 están **diferidos**, así que estos no son trabajo de hoy: pasan a
**condiciones de reapertura**, que es donde el plan ya guarda este tipo de
restricción. Fix de (1): `{items, siguiente_cursor}` como envelope paginado
genérico, con el feed declarado por escrito como forma legacy de una sola vez
que no se migra, y la regla en `backend/README.md`. Fix de (3): una línea en
`backend/README.md` — sustantivos de dominio en español, primitivas de
paginación y búsqueda en inglés.

Sobre (2): el subagente llega, por otro camino, a la misma conclusión que el
plan ya tiene registrada como alternativa más simple (cerrar B1 como "no
aplica por modelo de datos"). Eso refuerza **UC-3**, que ya va al Gate desde
Fase 1. No lo auto-decido acá.

#### Pass 3: Error Messages & Debugging — 2/10 → 8/10

La dimensión más débil del plan. Ningún camino de error nuevo especifica
problema + causa + arreglo + puntero a docs. Tres caminos trazados:

**Camino 1 — deadlock de A1.** El plan especifica `DomainRuleError`, que
`handlers.py:50-52` mapea a **400**. Un 400 le dice al cliente "tu request
era inválido", pero el request era válido y reintentar probablemente funcione.
Peor: obliga a `MesaPanel` a hacer string-match sobre prosa en español para
decidir si muestra un botón de reintentar. **El repo ya resolvió esta clase
de problema dos veces**: `RateLimitError` → 429 con `Retry-After`
(`handlers.py:90-95`) y `LicenseRevokedError` → 403 con `X-License-Revoked`,
cuyo comentario dice textualmente que el header existe "para que `client.ts`
distinga esto de un 403 genérico". Fix (P4, reusar el patrón que ya existe):
`ConcurrencyRetryError` → **409 + `Retry-After: 1`**, registrado en
`handlers.py` junto a los otros. Matiz que el subagente no vio y que el
código sí dice: el 409 ya está ocupado por `IntegrityError`, y
`PreconditionFailedError` eligió 412 justamente por eso
(`handlers.py:81-88`). Así que la desambiguación la tiene que hacer el
**header**, exactamente como `X-License-Revoked` hace con el 403 — no el
status solo. La UI de mesa renderiza el reintento leyendo status + header,
nunca el texto del mensaje.

**Camino 2 — cursor inválido de E1.** Listado como caso de test, nunca
definido: ni status, ni mensaje, ni si el cliente cae en silencio a la página
1 (lo que le parecería un loop infinito al usuario). Fix, como condición de
reapertura de E1: 400 con "El cursor no es válido o expiró; recargá el
listado", nunca fallback silencioso; un campo de versión distinto devuelve ese
mismo error en vez de reinterpretar bytes viejos. Estos recursos usan
soft-delete por `Estado`, así que el caso real no es "fila borrada" sino
"fila cuyo estado cambió y ya no matchea el filtro"; con el cursor siendo un
id opaco, "seguir desde ese id igual" lo resuelve.

**Camino 3 — 403 de F1.** El plan testea solo el status. Como `RequireRole`
ya esconde los botones, un 403 real significa token viejo o cambio de rol a
mitad de sesión: el mensaje tiene que decir eso y mandar a re-loguear, no
"No autorizado".

**Contexto que suma y que ya está registrado como learning del proyecto:**
`handlers.py` mapea cualquier `DBAPIError` a 400, lo que ya hizo pasar un
`UndefinedColumn` de Postgres por error de validación y costó una
investigación entera (migración 31 sin aplicar). Esa es la misma familia de
problema que el camino 1: un status que miente sobre la causa. No se expande
el alcance a arreglarlo acá (es código existente, no del plan), pero queda
dicho.

Auto-decidido además (P5): los tres mensajes nuevos llevan puntero a docs,
extendiendo la convención que el repo ya usa de citar el plan que los
gobierna.

#### Pass 4: Documentation & Learning — 4/10 → 8/10

Precisión excelente (cada fase nombra archivo y línea), y a la vez cuatro
defectos reales:

1. **El plan se contradice a sí mismo en tres lugares.** Las correcciones de
   las revisiones 2 y 3 se agregaron al final **revirtiendo** el cuerpo sin
   editarlo. En A1 el cuerpo dice que el fix es cambiar `get_or_404` por
   `get_or_404_bloqueado` y que "el helper ya existe"; la corrección dice que
   ese cambio **no cierra la carrera** y que hay que sacar dos `commit()`. En
   B2 el cuerpo especifica escribir la consulta y su README; la corrección
   dice que la consulta ya corrió, dio cero, y el archivo explícitamente no se
   commitea — pero la sección Verificación sigue pidiendo "B2 cierra
   corriendo su consulta". En A0 el cuerpo trata el baseline como un bloque
   único; la corrección lo parte en dos commits. Quien ejecute el plan de
   arriba hacia abajo hace lo incorrecto. Fix: reescribir A1, A0 y B2 **en el
   cuerpo**, y dejar las correcciones como changelog corto al final.
2. **A2 vuelve falso el docstring de `conftest.py`.** Ese docstring es de lo
   mejor documentado del repo: enseña que un `session.commit()` dentro de un
   repositorio no persiste nada de verdad. A2 agrega una fixture donde eso se
   invierte. Fix: A2 modifica el docstring para describir los dos harness y
   cuándo usar cada uno, y agrega a `backend/README.md` un test de
   concurrencia de ejemplo copiable entero, no prosa.
3. **B2 tira la única cosa que el ejercicio produjo.** `AUDITORIA.Tabla`
   guarda `obj.__tablename__`, o sea minúscula, así que `Tabla='USUARIOS'` da
   cero **por casing**, no por falta de datos. Es la trampa exacta que hizo
   mal la especificación original. No commitear la consulta deja ese dato en
   una entrada de TODOS.md que nadie que escriba una query de AUDITORIA va a
   leer. **Esto choca con una obligación aceptada en Fase 1** ("`docs/queries/
   metricas-revocacion-licencia.sql` NO se commitea"), así que va al Gate como
   decisión de taste, no se auto-decide.
4. **Cero ejemplos copiables** para la superficie nueva, y `docs/queries/`
   sin README (verificado: un solo `.sql`, ninguna instrucción). El mejor
   precedente del propio repo es el docstring del feed
   (`routes/partidos.py:92`): `Ejemplo: GET /api/v1/partidos/feed?disciplina_id=1&limit=20`.
   Fix: criterio de aceptación por ruta nueva, más un `docs/queries/README.md`
   de 10 líneas que diga cómo correr una, contra qué base, y que un resultado
   en cero es un hallazgo que vale registrar.

Y la guardia de tres lugares está en el plan dos veces y en
`database/README.md` ninguna: va al README una vez y el plan apunta ahí
(P4, DRY).

#### Pass 5: Upgrade & Migration Path — 5/10 → 8/10

Lo mejor del plan en esta dimensión ya estaba: los disparadores de reapertura
escritos como números (>150 equipos orgánicos, >150 jugadores orgánicos, p95
>800 ms, segundo cliente de la API) en vez de intenciones. Eso es mejor que
lo que hace la mayoría de los planes y no lo toco.

Lo que falta, y es de verdad: **`GET /jugadores` es la única ruta que se sale
de la red de seguridad del repo.** Usa `response_model=None` con un dict
`RESPUESTA_LISTA_JUGADORES` mantenido a mano
(`backend/app/api/routes/jugadores.py:22-24,39`) por la proyección de PII
para callers anónimos. El `README.md:68-69` vende el codegen como convención
central: "si cambiás un schema de Pydantic, corré `npm run gen:api` y `tsc` te
va a decir qué se rompió del otro lado". **Ahí no vale.** Si E1 envuelve la
respuesta y solo cambia el tipo de retorno de Python, el `openapi.json` sigue
anunciando `list[JugadorOut] | list[JugadorPublicOut]`, `npm run gen:api`
regenera un cliente tipado a la forma vieja, `tsc -b` pasa en verde, y la
rotura aparece en runtime como `.map is not a function`. El plan nunca
menciona `RESPUESTA_LISTA_JUGADORES`.

Fix, como condición de reapertura de E1 (E1 está diferido): actualizar
`RESPUESTA_LISTA_JUGADORES` (y `RESPUESTA_JUGADOR`/`RESPUESTA_PERFIL` si se
tocan) al union envuelto, **más** un test de backend que afirme que
`app.openapi()["paths"]["/api/v1/jugadores"]["get"]["responses"]["200"]`
contiene `siguiente_cursor`. Sin esa afirmación el agujero se reabre en la
siguiente edición.

Además: el page size del cursor hereda el `le=200` que ya existe
(`routes/equipos.py:21`, `routes/jugadores.py:42`) o es superficie nueva sin
cota.

#### Pass 6: Developer Environment & Tooling — 3/10 → 8/10

Es un 3 por el estado de la marca de concurrencia, verificado en los tres
archivos:

- `verificar.ps1:46` es `Paso "Backend — pytest" "backend" { python -m pytest -q }`,
  sin filtro de marcas. Es el único gate que el README manda correr antes de
  dar algo por terminado. A3 mete ahí tests lentos, no herméticos y propensos
  a deadlock, y el plan nunca toca `verificar.ps1`.
- `backend/pytest.ini` tiene tres settings de asyncio y **ningún bloque
  `markers =` ni `addopts`**. Una marca no registrada levanta
  `PytestUnknownMarkWarning`, y un typo en `-m "not concurenica"` no
  deselecciona nada y reporta verde. El escape hatch que el plan promete
  (`-m concurrencia`, línea 521) no es alcanzable hoy.

Fix (Mechanical, criterios de aceptación de A2): registrar `concurrencia` en
`pytest.ini` bajo `markers =` con descripción; agregar
`addopts = --strict-markers`; cambiar `verificar.ps1` a
`python -m pytest -q -m "not concurrencia"` y sumar un `Paso "Backend —
concurrencia"` propio para que sigan corriendo, visibles, en su bucket; una
línea en `backend/README.md` y en el comentario de cabecera de
`verificar.ps1`.

Cross-platform: el repo es PowerShell-first (`verificar.ps1`, `.venv\Scripts\
activate`) y el `docker-compose.yml` ya resuelve `host.docker.internal` para
Windows, Mac y Linux vía `extra_hosts`. DX-2 se apoya en eso; no se inventa
una capa nueva.

#### Pass 7: Community & Ecosystem — 3/10 → 6/10 (techo real)

Sin `CONTRIBUTING.md`, sin licencia, sin canal. Pero es un repo privado de un
solo autor: invertir en ecosistema acá sería trabajo para nadie, y
recomendarlo sería exactamente el tipo de expansión que P2 (blast radius) y el
propio principio de alcance del plan rechazan. La pregunta que sí aplica —
"¿puede sumarse una segunda persona?" — la contestan Pass 1 y Pass 6, y ahí sí
hay trabajo.

Sube a 6 y no más: los arreglos de Pass 1/6 dejan el on-ramp funcionando, pero
sin `CONTRIBUTING.md` que diga cómo se trabaja (el README ya tiene la sección
"Cómo se trabaja acá", que es medio camino andado) el techo se queda ahí. No
se propone crearlo: nadie lo pidió, y `docs/plans/` ya cumple esa función
mejor que un CONTRIBUTING genérico.

#### Pass 8: DX Measurement & Feedback Loops — 4/10 → 7/10

El plan no instrumenta nada de TTHW. Pero tiene una disciplina de medición
que vale más que la instrumentación y que hay que nombrar: B2 se **cerró
midiendo** (la consulta corrió y dio cero en las dos mitades), y E1 se difirió
contra números orgánicos separados de los sintéticos de
`mock_estres_catalogo.py`. Ese es el ciclo de medición correcto: medir antes
de construir.

Lo que falta es el otro lado: los disparadores de reapertura son números, pero
nadie los mide periódicamente. Sube a 7 y no a 8+ porque no se agrega
instrumentación (sería alcance nuevo, fuera del blast radius). Fix mínimo
auto-decidido: los umbrales quedan escritos en `TODOS.md` con la consulta que
los evalúa nombrada al lado, para que revisarlos sea leer y correr, no
reconstruir.

#### "NOT in scope" — Fase 2.5

- Devcontainer / Codespaces — infraestructura nueva, fuera del blast radius.
- `CONTRIBUTING.md` y licencia — repo privado de un autor, sin demanda (Pass 7).
- Instrumentar TTHW con telemetría — alcance nuevo (Pass 8).
- Arreglar el mapeo `DBAPIError` → 400 de `handlers.py` — código existente, no
  del plan; queda nombrado en Pass 3 como contexto, no como trabajo.
- Migrar `FeedResponseOut` al envelope genérico — se declara legacy por
  escrito, no se migra.
- Reescribir la API para un segundo cliente — no existe; es justamente el
  disparador (c) de reapertura de E1.

#### "What already exists" — Fase 2.5

- `infrastructure/docker-compose.yml` — ya levanta la API con `extra_hosts`
  resuelto para los tres SO. DX-2 lo extiende, no lo reemplaza.
- `backend/.env.example` — el patrón correcto ya existe; DX-1 solo lo replica
  en `frontend/`.
- `handlers.py:68-95` — `X-License-Revoked` y `Retry-After` son el patrón
  exacto que necesita el error de deadlock (Pass 3). No se inventa nada.
- `routes/partidos.py:92` — docstring con URL de ejemplo ejecutable: el
  formato que M4 replica.
- `docs/queries/metricas-desempate-tiempo-extra-penales.sql` — precedente de
  consulta de métrica versionada.
- `conftest.py` (docstring de módulo) — la mejor pieza de docs del repo; A2 la
  extiende en vez de dejarla mintiendo.
- `.gitignore:14-15` (`.env` + `!.env.example`) — la política ya está bien;
  faltaba ejercerla en `frontend/`.
- `pytest.ini` — el archivo existe y ya documenta el porqué de sus settings de
  asyncio; agregarle `markers` sigue su propia forma.

#### TTHW

**Actual ~25 min → objetivo ≤5 min (tier Competitive).** El delta lo cierran
DX-1 (una línea, elimina el pozo de 0B por completo) y DX-2 (el compose deja
el setup en un comando). Ninguno de los dos toca código de producto.

#### Resumen de finalización — Fase 2.5 (DX)

```
  +====================================================================+
  |               DX PLAN REVIEW — SCORECARD                            |
  +====================================================================+
  | Dimension            | Inicial | Final  | Nota                      |
  |----------------------|---------|--------|---------------------------|
  | Getting Started      |  3/10   |  8/10  | pozo de frontend/.env     |
  | API/CLI/SDK          |  3/10   |  8/10  | 2 envelopes, alcance      |
  | Error Messages       |  2/10   |  8/10  | la mas debil del plan     |
  | Documentation        |  4/10   |  8/10  | el plan se contradice     |
  | Upgrade Path         |  5/10   |  8/10  | agujero del codegen       |
  | Dev Environment      |  3/10   |  8/10  | marca no registrada       |
  | Community            |  3/10   |  6/10  | techo: repo privado       |
  | DX Measurement       |  4/10   |  7/10  | mide bien, no instrumenta |
  +--------------------------------------------------------------------+
  | TTHW                 | ~25 min | <=5 min| tier Competitive          |
  | Competitive Rank     | Needs Work -> Competitive                    |
  | Magical Moment       | disenado: compose + verificar.ps1 en verde   |
  | Product Type         | API/Service interna + repo de contribuidor   |
  | Mode                 | DX POLISH                                    |
  | Overall DX           |  2/10   |  6/10  | minimo de los 8 passes    |
  +====================================================================+
  | DX PRINCIPLE COVERAGE                                               |
  | Zero Friction      | gap -> cubierto por DX-1 + DX-2                |
  | Learn by Doing     | gap -> cubierto por H2 (ejemplo copiable) + M4 |
  | Fight Uncertainty  | gap -> cubierto por H5 + H6 + M8 + M9          |
  | Opinionated + Escape Hatches | cubierto (F1 slug, soft-delete)      |
  | Code in Context    | gap -> cubierto por M4                         |
  | Magical Moments    | cubierto (0D)                                  |
  +====================================================================+
```

**Overall 6/10**, no más alto, por el techo de Pass 7: es un repo privado de
un autor y la dimensión de ecosistema no se puede calificar mejor sin
inventarle demanda. Los otros siete quedan en 7-8.

```
DX IMPLEMENTATION CHECKLIST
============================
[ ] frontend/.env.example existe y el login funciona en un clon limpio
[ ] docker compose up levanta Postgres + API y carga database/01-06
[ ] README "Levantar todo" nombra el compose como camino recomendado
[ ] TTHW de clon a verificar.ps1 verde medido en <= 5 min
[ ] concurrencia registrada en pytest.ini markers + addopts --strict-markers
[ ] verificar.ps1 corre -m "not concurrencia" y tiene su Paso propio
[ ] conftest.py describe los DOS harness de test
[ ] backend/README.md tiene un test de concurrencia copiable entero
[ ] ConcurrencyRetryError -> 409 + Retry-After, registrado en handlers.py
[ ] La UI de mesa decide el reintento por status + header, nunca por texto
[ ] Mensaje de 403 de F1 testeado por contenido, no solo por status
[ ] Cada ruta nueva tiene URL de ejemplo ejecutable en su docstring
[ ] docs/queries/README.md existe
[ ] La guardia de tres lugares esta en database/README.md una sola vez
[ ] Regla de nombres de parametros escrita en backend/README.md
[ ] Cuerpo del plan (A0, A1, B2) reescrito; correcciones como changelog
[ ] Umbrales de reapertura en TODOS.md con su consulta nombrada al lado
```

#### Decisiones de taste al Gate — Fase 2.5

- **T-3** Commitear `docs/queries/metricas-revocacion-licencia.sql` igual
  (recomendado — 20 líneas que preservan la trampa del casing de
  `AUDITORIA.Tabla`, y una consulta commiteada que da cero *es* el hallazgo
  documentado) vs mantener la obligación de Fase 1 de no commitearla y poner
  la nota de casing en `database/README.md`. **Choca con una obligación ya
  aceptada en Fase 1**, por eso no se auto-decide.
- **T-4** Partir A1 en tres commits (recomendado — reestructuración
  transaccional, rescate de deadlock, log+runbook; el orden preserva la
  restricción de seguridad de Fase 1 de que el reintento nunca shipee antes
  de la atomicidad) vs el "en el mismo cambio" que Fase 1 aceptó
  explícitamente. La reestructuración cambia semántica de la que dependen
  tests existentes; un revert quirúrgico vale más cuanto mayor es el radio.

<!-- autoplan-accepted:dx -->
- DX-1: agregar `frontend/.env.example` con `VITE_API_BASE_URL=http://127.0.0.1:8000`. Verificado: `frontend/src/api/client.ts:4` lee `import.meta.env.VITE_API_BASE_URL` sin default, `frontend/src/auth/AuthContext.tsx:72` la interpola directo en el `fetch` del login, y `.gitignore:14-15` (`.env` + `!.env.example`) ignora el `frontend/.env` local; `backend/.env.example` está commiteado y `frontend/.env.example` no existe. En un clon limpio el login POSTea a `undefined/api/v1/auth/login` y el backend nunca ve el request. NO se agrega un default en `client.ts`: convertiría un fallo de configuración en un fallo de red intermitente. Verificación: clon limpio sin `frontend/.env` propio, copiar el example, y el login entra.
- DX-2: extender `infrastructure/docker-compose.yml` con el servicio Postgres y la carga inicial de `database/01_schema.sql`–`06_triggers.sql`, y nombrarlo en la sección "Levantar todo" del `README.md` como camino recomendado, dejando el manual como alternativa. El compose ya existe y ya levanta la API con `extra_hosts: host.docker.internal:host-gateway` resuelto para Windows, Mac y Linux; hoy asume "Postgres corre en el host (ya lo tenés instalado y con torneos_mvp cargado)", que es la suposición que rompe a la segunda persona que clone. Verificación: TTHW de clon a `.\verificar.ps1` en verde medido en <= 5 min.
- A2 registra la marca `concurrencia` en `backend/pytest.ini` bajo un bloque `markers =` con descripción de una línea, y agrega `addopts = --strict-markers`. Verificado: hoy `pytest.ini` tiene solo los tres settings de asyncio, ningún `markers` y ningún `addopts`, así que una marca no registrada solo emite `PytestUnknownMarkWarning` y un typo en `-m "not concurenica"` no deselecciona nada y reporta verde — el escape hatch que el plan promete no es alcanzable. Verificación: `pytest -m concurrencia --collect-only` selecciona exactamente los tests de A3, y una marca inventada falla la corrida en vez de advertir.
- A2 cambia `verificar.ps1:46` a `python -m pytest -q -m "not concurrencia"`, agrega un switch opt-in `-Concurrencia` y un `Paso "Backend — concurrencia"` propio, para que los tests de A3 sigan corriendo, visibles, en su propio bucket. Sin esto los tests de A3 (commits reales + `TRUNCATE`) entran en la corrida por defecto que el README manda correr antes de dar algo por terminado, dentro de un script cuya cabecera (`verificar.ps1:22-24`) promete que "pytest crea y destruye sus propias bases; nunca toca `torneos_mvp`" — el guard de nombre de base protege los datos pero no esa promesa. Se documenta en `backend/README.md` (3 líneas, "cómo correr los tests de concurrencia", junto a la línea de pytest que ya está) y en el comentario de cabecera de `verificar.ps1`. Como el orden serial mueve A2/A3 al final, esto se escribe AHORA en la definición de terminado de A2. Verificación: `.\verificar.ps1` muestra los dos pasos por separado y el paso por defecto no incluye tests de concurrencia.
- A2 modifica, en el mismo cambio, el docstring de módulo de `backend/tests/conftest.py` para describir los DOS harness (el de savepoints donde un `commit()` de repositorio no persiste, y el de conexiones paralelas donde sí) y cuándo usar cada uno; y agrega a `backend/README.md` una sección "cómo escribir un test de concurrencia" con un test de ejemplo copiable ENTERO, no prosa. Hoy ese docstring enseña explícitamente que un `session.commit()` dentro de un repositorio no persiste nada de verdad, y la fixture de A2 invierte exactamente eso. La métrica real de A2 no es "el autor escribe el test 1" sino "otro escribe el test 4 en diez minutos". Verificación: el docstring nombra los dos harness y el README contiene un test que se puede pegar y correr.
- **A1 usa el mecanismo de códigos de error estables que el repo YA tiene, no prosa.** Se agrega `ConcurrencyConflictError` a `backend/app/exceptions/errors.py`, mapeada en `handlers.py` a **409 con header discriminante `X-Reintentable: true`** (mismo patrón que `LicenseRevokedError` → 403 + `X-License-Revoked` y `RateLimitError` → 429 + `Retry-After`, `handlers.py:68-95`), y con `detail = "evento_conflicto_concurrente"`, código que se agrega a `CODIGOS_ERROR_TRADUCIDOS` (`frontend/src/api/client.ts:73-86`) con su copy en español y su acción de recuperación. SUPERSEDE de la forma que decía Fase 1 (`DomainRuleError` con mensaje en prosa): `DomainRuleError` mapea a 400 (`handlers.py:50-52`), o sea mismo status, misma forma `{detail: "<prosa>"}` y misma clase CSS que un rechazo de validación permanente, con lo cual el único discriminador que le quedaría al frontend es hacer substring-match sobre texto en español — exactamente lo que `CODIGOS_ERROR_TRADUCIDOS` existe para evitar, y lo que vuelve inimplementable la obligación de Fase 2 de que "el error de deadlock no comparte clase con un 4xx de validación". El 409 ya está ocupado por `IntegrityError` y `PreconditionFailedError` eligió 412 por eso (`handlers.py:81-88`), así que la desambiguación la hace el HEADER, no el status solo; `client.ts` lo lee sin clonar el stream de la respuesta (el comentario de `client.ts:23-31` explica por qué eso importa) y `apiErrorMessage` renderiza el texto gratis. Verificación: test que fuerza el deadlock y afirma 409 + `X-Reintentable`; test de frontend que afirma que el botón "Reintentar" aparece sin depender del texto del mensaje.
- **Este plan lleva su propia sección "§ Copy de errores"**, siguiendo la convención que `client.ts:62-66` cita por nombre, con una fila por error nuevo: código, status, texto y acción de recuperación. Las seis filas mínimas: conflicto de concurrencia de A1; cursor inválido de E1; cursor que apunta a fila cuyo estado cambió (E1); timeout de test de A2 (mensaje que nombre las dos sesiones y la fila en disputa, no un `TimeoutError` pelado); valor inválido de `alcance` en B1 (hoy sería el 422 crudo sin traducir de FastAPI); y 403 de F1. Hoy el plan especifica copy para UNO solo de sus errores (el tercer empty state de B1, que además está bien: nombra causa y acción, "Pedí una asignación a un AdminGeneral"). Verificación: la sección existe y cada error nuevo aparece en ella antes de implementarse.
- Política de errores del plan, dicha una vez: la acción de recuperación va en el mensaje al usuario y el puntero de diagnóstico va en el docstring (como ya hace la línea de runbook de A1 con `pg_stat_activity`). No se agregan URLs de docs a los mensajes: cero errores del repo las llevan hoy y es una herramienta interna en español con acciones de recuperación in-app.
- El umbral de espera del `FOR UPDATE` y el conteo de reintentos de A1 salen de `Settings` (`backend/app/core/config.py`, que ya lee `.env` con pydantic-settings), no de literales en el código. El sink del log se nombra concreto: `logging.getLogger("app.concurrencia")` a stdout. Verificación: cambiar el umbral por variable de entorno cambia el comportamiento sin editar código.
- A1 deja registrado en el docstring de `BaseRepository.create` que `EventoPartidoService` maneja su propia transacción, para que el próximo que lea "create no commitea" no lo "arregle" de vuelta. Colapsar `create` a una sola transacción es correcto, pero cambia una expectativa que cualquier llamador futuro puede dar por sentada. Verificación: el docstring lo dice.
- El mensaje de 403 de F1 se testea por CONTENIDO, no solo por status. Como `RequireRole` ya esconde los botones, un 403 real significa token viejo o cambio de rol a mitad de sesión: el mensaje dice eso y manda a re-loguear. Hoy una llamada directa recibe `deps.py:132-134` ("Esta operación requiere rol X (tenés: Y)"), que tiene problema y causa pero no arreglo. Verificación: el test afirma el texto, no solo el código.
- **Toda fase que cambie el contrato de la API (B1, E1, F1) nombra como paso numerado "regenerar `frontend/src/api/schema.d.ts` con `npm run gen:api` (backend arriba) en el MISMO commit".** Verificado: `frontend/package.json:12` genera el cliente contra `http://127.0.0.1:8000/openapi.json`, o sea contra un backend VIVO, y `verificar.ps1` explícitamente no necesita el servidor levantado (cabecera, línea 22) — así que el drift de contrato no lo detecta nadie: o el typecheck pasa en verde contra un contrato viejo, o `tsc` tira un error que nunca dice "corré gen:api". Verificación: cada una de esas fases tiene el paso escrito, y el `schema.d.ts` regenerado entra en el mismo commit.
- Cada ruta nueva o modificada por este plan lleva una URL de ejemplo ejecutable en su docstring, siguiendo el precedente que ya existe en `backend/app/api/routes/partidos.py:92` (`Ejemplo: GET /api/v1/partidos/feed?disciplina_id=1&limit=20`). Verificación: la ruta tiene el ejemplo y la URL responde tal cual está escrita.
- **El plan gana una tabla de estado al principio** — fase, viva o diferida, y disparador de reapertura — y los encabezados de las fases diferidas se reescriben como `#### Fase E1 — DIFERIDA (ver umbral)`, conservando el cuerpo como diseño de referencia. Hoy los Tracks A-F se leen como nueve ítems comprometidos con instrucciones a nivel de archivo, y las correcciones del final revierten cuatro en silencio (B2 "ya está ejecutado", F1/E1/B1 pasan a "si se reabre"), mientras el orden serial de ejecución omite B1, B2, E1 y F1 sin decirlo y el grafo de dependencias los sigue presentando como en alcance. Quien lea "Track B" y arranque `EquipoRepository.list(torneo_ids_permitidos=...)` está haciendo trabajo diferido, y la frase que lo habría frenado está 380 líneas más abajo. Además se reescriben en el cuerpo A0, A1 y B2 para que digan lo que las revisiones 2 y 3 corrigieron, quedando las correcciones al final solo como changelog corto — hoy el cuerpo afirma que A1 se arregla cambiando `get_or_404` por `get_or_404_bloqueado` mientras la corrección dice que eso no cierra la carrera, y la sección Verificación sigue pidiendo "B2 cierra corriendo su consulta" cuando la consulta ya corrió y su archivo no se commitea. Verificación: leer el plan de arriba hacia abajo no lleva a empezar trabajo diferido.
- **El tratamiento de estado pending se decide UNA vez, global, no por fase.** SUPERSEDE de la obligación de Fase 2 que decía "cada fase reorganizada nombra su tratamiento de estado pending en una línea": eso devuelve la decisión al implementador, que es el modo de fallo exacto que las propias obligaciones de Fase 2 sobre zonas FIJADAS y sobre la secuencia del modal de C1 se agregaron para eliminar; cinco fases reinventándolo dan cinco tratamientos distintos. Queda así: control deshabilitado + spinner inline + la región `aria-live` que ya pide Fase 2 anunciando "Guardando…" y después la confirmación de éxito. Verificación: hay un solo patrón de pending en el diff.
- La guardia de tres lugares para columnas nuevas (`01_schema.sql` + script `NN_` idempotente + `SCRIPTS_VIGENTES` de `backend/tests/test_scripts_sql.py:36-48`) se escribe UNA vez en `database/README.md` y el plan apunta ahí en vez de restatearla. Hoy está en el plan dos veces y en el README de la base ninguna, y es la que produce el `UndefinedColumn` en ~40 archivos de test. Verificación: `database/README.md` la cubre y el plan la referencia sin repetirla.
- La trampa de casing de `AUDITORIA.Tabla` se preserva en el criterio de reapertura de B2 en `TODOS.md`, en una línea: "`Tabla` se filtra en minúscula (`usuarios`) — guarda `__tablename__`". Verificado: `backend/app/core/auditoria.py:111,119,137,163,178,193` usan `obj.__tablename__`, así que `Tabla='USUARIOS'` da cero por casing, no por falta de datos — es la trampa exacta que hizo mal la especificación original de B2. Esto NO contradice la obligación de Fase 1 de no commitear `docs/queries/metricas-revocacion-licencia.sql`: preserva el dato sin el archivo. Si además se commitea la consulta, es la decisión T-3 del Gate. Verificación: el criterio de reapertura de B2 en `TODOS.md` incluye esa línea.
- `docs/queries/` gana una fila en la tabla "Dónde está cada cosa" del `README.md` raíz y un `docs/queries/README.md` de 10 líneas (cómo correr una consulta, contra qué base, y que un resultado en cero es un hallazgo que vale registrar). Verificado: el directorio tiene un solo `.sql` y ningún README, y grepear "queries" en `README.md`, `database/README.md` y `backend/README.md` da CERO resultados — es indescubrible. Va independientemente de lo que se resuelva sobre T-3 y sobre B2.
- La regla de nombres de parámetros de query queda escrita en `backend/README.md`: sustantivos de dominio en español, primitivas de paginación y búsqueda en inglés. Hoy el repo mezcla (`skip`/`limit`/`q` contra `disciplina_id`/`estado`) y el plan suma `alcance` sin fijar la regla, así que el próximo parámetro la vuelve a litigar. Verificación: la regla está escrita y el parámetro siguiente la cumple.
- Los umbrales de reapertura ya escritos como números en `TODOS.md` llevan al lado el nombre de la consulta que los evalúa, para que revisarlos sea leer y correr en vez de reconstruir. Verificación: cada umbral tiene su consulta nombrada.
- **Si F1 se reabre: la autorización se resuelve partiendo rutas, no ampliando la que existe.** El plan pide ampliar `PATCH /disciplinas/{id}` más allá de `estado`, gatearlo `AdminGeneral`, y a la vez conservar el toggle de `TorneoAdmin` "como está". Eso no es expresable: `backend/app/api/routes/disciplinas.py:77-86` tiene UNA sola ruta PATCH, gateada `dependencies=[Depends(require_roles("TorneoAdmin"))]`, cuyo docstring dice que el único cambio permitido es activar/desactivar; y `require_roles` (`backend/app/api/deps.py:118-136`) es dependencia a NIVEL DE RUTA, no por campo. Tener `estado` en TorneoAdmin y el resto de los campos en AdminGeneral sobre la misma ruta obliga a mover la autorización al servicio, abandonando el patrón que el plan dice preservar (89 usos, cuatro combinaciones). Queda: `PATCH /disciplinas/{id}/estado` conserva `TorneoAdmin`; un `PUT /disciplinas/{id}` (edición completa del catálogo) y un `POST /disciplinas` toman `AdminGeneral`. La autorización se queda donde los otros 89 call sites la ponen, los dos poderes quedan visiblemente distintos, y `RequireRole` en `CatalogoDisciplinas.tsx` tiene dos cosas limpias sobre las que decidir. Confirmado de paso: `require_roles` ya hace bypass para `AdminGeneral` (`deps.py:130`), así que el razonamiento del plan sobre eso sí se sostiene. Verificación: ninguna ruta mezcla dos niveles de rol para campos distintos.
- Si F1 se reabre: el `limit=200` de `backend/app/services/disciplina.py:30` **se sube y se promueve a constante nombrada, o se pagina — NO se quita**. SUPERSEDE de la obligación de Fase 1 que decía "el `limit=200` hardcodeado de `services/disciplina.py:30` sale": está en `list_con_modalidades`, cuyo docstring explica que la cota es deliberada para un catálogo fijo de 28 disciplinas / 66 modalidades de solo lectura. La premisa entera de F1 es volver ese catálogo escribible por el usuario, así que la cota deja de ser cosmética exactamente cuando F1 la eliminaría.
- Si E1 se reabre: (a) se actualiza `RESPUESTA_LISTA_JUGADORES` (y `RESPUESTA_JUGADOR`/`RESPUESTA_PERFIL` si se tocan) al union envuelto, MÁS un test de backend que afirme que `app.openapi()["paths"]["/api/v1/jugadores"]["get"]["responses"]["200"]` contiene `siguiente_cursor`. `GET /jugadores` es la única ruta que se sale de la red de seguridad del codegen: usa `response_model=None` con el dict mantenido a mano de `backend/app/api/routes/jugadores.py:22-24,39` por la proyección de PII para callers anónimos. Sin esa actualización, `openapi.json` sigue anunciando la forma vieja, `npm run gen:api` regenera un cliente tipado a la forma vieja, `tsc -b` pasa verde, y la rotura aparece en runtime como `.map is not a function` — rompiendo la garantía que `README.md:68-69` vende como convención central. (b) `{items, siguiente_cursor}` es el envelope paginado genérico y la regla queda escrita en `backend/README.md`; `FeedResponseOut` (`backend/app/schemas/partido.py:290-303`, `{fecha_pedida, fecha_efectiva, total_disponible, partidos}`) se declara por escrito forma legacy de una sola vez que NO se migra. (c) se define el destino del banner `truncado` de `frontend/src/hooks/useResourceCrud.ts:40,131`, que hoy depende de `LIMITE_LISTA = 200` para saber que hay más. (d) el page size del cursor hereda el `le=200` que ya existe en `routes/equipos.py:21` y `routes/jugadores.py:42`. (e) cursor inválido: 400 con código estable en `CODIGOS_ERROR_TRADUCIDOS`, texto "El cursor no es válido o expiró; recargá el listado", nunca fallback silencioso a la página 1; un campo de versión distinto devuelve ese mismo error en vez de reinterpretar bytes viejos; y como estos recursos usan soft-delete por `Estado`, el caso real es "fila cuyo estado cambió y ya no matchea el filtro", que con un cursor de id opaco se resuelve continuando desde ese id igual.
- Si B1 se reabre: el alcance del listado NO se expresa como query param elegible por el cliente (`alcance=asignados|disciplina` con default ancho, como decía el plan). El techo de permisos se queda implícito y derivado del token vía `torneo_ids_permitidos`, con la semántica `None`/`[]` que el plan ya documenta bien, como ya hacen `routes/torneos.py` y `routes/partidos.py`. Dos motivos: invierte el default seguro, y `alcance=asignados|disciplina` mezcla una audiencia con un eje de datos, así que nadie va a adivinar cuál es cuál — es el problema de "uno y no tres" que el propio plan se niega a crear un párrafo antes. Si el camino de alta o de búsqueda necesita ver filas no inscritas, se expresa como flag de CAPACIDAD con nombre honesto (`incluir_no_inscritos=true`), y el servidor garantiza que nunca amplía más allá de lo que el rol del caller ya permite. Además: empty state y encabezado del listado dicen "mostrando solo equipos de tus torneos asignados" con un toggle "ver todos" — ese toggle es a la vez el escape hatch, la documentación y lo que evita el reporte de bug.
<!-- /autoplan-accepted:dx -->

#### Segunda pasada DX — contra el plan enmendado

La primera corrida de la voz DX se hizo contra un `Implementation plan` al que
todavía le faltaban las 15 obligaciones de Fase 2 (Diseño), que se habían
registrado pero nunca aplicado — la corrida del 2026-09-17 murió antes de su
`amend`, y su snapshot quedó byte-incompatible con el plan de hoy (se grabó
con LF; el plan usa CRLF, y el chequeo de integridad es byte-exacto a
propósito). Con el bloque de Diseño aplicado, el snapshot DX se recreó y la
voz se volvió a despachar. La segunda pasada encontró cuatro cosas que la
primera no podía ver, todas verificadas contra el código antes de aceptarse:

- **F-4 (ALTA) — el diseño de autorización de F1 no es expresable con el
  mecanismo que el propio plan nombra.** `backend/app/api/routes/disciplinas.py:77-86`
  tiene UNA sola ruta PATCH, gateada `dependencies=[Depends(require_roles("TorneoAdmin"))]`,
  y `require_roles` (`backend/app/api/deps.py:118-136`) es dependencia a nivel
  de RUTA, no por campo. El plan quiere `estado` en TorneoAdmin y el resto de
  campos en AdminGeneral sobre esa misma ruta: eso obliga a mover la
  autorización al servicio, abandonando el patrón de 89 usos que el plan dice
  preservar. Resuelto partiendo rutas.
- **F-7 (CRÍTICA) — existe un mecanismo de códigos de error estables que el
  plan ignora.** `frontend/src/api/client.ts:73-86` tiene
  `CODIGOS_ERROR_TRADUCIDOS`: códigos snake_case que viajan en `detail`,
  mapeados a copy en español con acción de recuperación, alimentados por
  secciones "§ Copy de errores" de planes anteriores. Eso cambia el arreglo
  del error de deadlock: no alcanza con 409 + header, el `detail` tiene que
  ser un código estable registrado en esa tabla. La obligación se reescribió.
- **F-10 (ALTA) — ninguna fase que cambia el contrato nombra `npm run gen:api`.**
  `frontend/package.json:12` genera `schema.d.ts` contra un backend VIVO, y
  `verificar.ps1` explícitamente no levanta el servidor (cabecera, línea 22).
  El drift de contrato no lo detecta nadie.
- **F-3 (CRÍTICA, más filosa que la primera pasada) — la contradicción del plan
  no es solo de contenido, es de alcance.** El orden serial de ejecución
  (`A0 → A1 → C1 → C2a → C2b → D1 → exp.1 → A2 → A3`) omite B1, B2, E1 y F1
  sin decirlo, mientras el grafo de dependencias y "Fuera de alcance" los
  siguen presentando como en alcance. Quien lea "Track B" y arranque
  `EquipoRepository.list(torneo_ids_permitidos=...)` está haciendo trabajo
  diferido.

Además resolvió sola una tensión que la primera pasada había mandado al Gate:
la trampa de casing de `AUDITORIA.Tabla` se puede preservar en el criterio de
reapertura de B2 en `TODOS.md` **sin** commitear la consulta, así que deja de
chocar con la obligación de Fase 1. **T-3 se reduce**: lo necesario ya está
auto-decidido; lo que queda en el Gate es solo si además se commitea el `.sql`.

Verificación independiente de esta fase (no se aceptó ninguna afirmación por
venir del subagente): `backend/pytest.ini`, `verificar.ps1:46`,
`backend/app/api/routes/jugadores.py:22-24,39`, `backend/app/api/routes/equipos.py:21`,
`backend/app/exceptions/handlers.py:45-100`, `backend/app/schemas/partido.py:290-303`,
`backend/app/services/disciplina.py:30`, `frontend/src/hooks/useResourceCrud.ts:40,131`,
`frontend/src/api/client.ts:4,73-86`, `frontend/src/auth/AuthContext.tsx:72`,
`frontend/package.json:9,12`, `backend/app/api/routes/disciplinas.py:77-86`,
`backend/app/api/deps.py:118-136`, `.gitignore:14-15`, `docs/queries/`,
`README.md:68-69`. Todas se sostuvieron.

#### Implementation Tasks — Fase 2.5 (DX)

Artefacto JSONL: `~/.gstack/projects/Score-App/tasks-devex-review-20260918-123422.jsonl`
(17 tareas: 4 P1, 7 P2, 6 P3).

- [ ] **T1 (P1, human: ~10 min / CC: ~2 min)** — frontend — Agregar `frontend/.env.example` con `VITE_API_BASE_URL`
- [ ] **T2 (P1, human: ~2 h / CC: ~20 min)** — plan — Tabla de estado por fase y reescritura de A0/A1/B2 en el cuerpo
- [ ] **T3 (P1, human: ~3 h / CC: ~25 min)** — backend — `ConcurrencyConflictError` → 409 + `X-Reintentable` + código en `CODIGOS_ERROR_TRADUCIDOS`
- [ ] **T4 (P1, human: ~1 h / CC: ~10 min)** — tests — Marca `concurrencia` en `pytest.ini` + `--strict-markers` + filtro en `verificar.ps1`
- [ ] **T5 (P2, human: ~4 h / CC: ~30 min)** — infra — Postgres en el compose y "Levantar todo" apuntando ahí
- [ ] **T6 (P2, human: ~2 h / CC: ~15 min)** — tests — Los dos harness en el docstring de `conftest.py` + ejemplo copiable
- [ ] **T7 (P2, human: ~1 h / CC: ~10 min)** — plan — Sección "§ Copy de errores" con una fila por error nuevo
- [ ] **T8 (P2, human: ~1 h / CC: ~8 min)** — backend — Umbral y reintentos de A1 a `Settings`, logger nombrado
- [ ] **T9 (P2, human: ~30 min / CC: ~5 min)** — docs — `docs/queries/README.md` + fila en la tabla del README raíz
- [ ] **T10 (P2, human: ~30 min / CC: ~5 min)** — docs — Guardia de tres lugares en `database/README.md`
- [ ] **T11 (P2, human: ~15 min / CC: ~3 min)** — docs — Regla de nombres de parámetros en `backend/README.md`
- [ ] **T12 (P3, human: ~30 min / CC: ~5 min)** — plan — Paso `gen:api` en B1, E1 y F1
- [ ] **T13 (P3, human: ~1 h / CC: ~10 min)** — frontend — Un único tratamiento de estado pending
- [ ] **T14 (P3, human: ~15 min / CC: ~3 min)** — backend — Docstring de `BaseRepository.create`
- [ ] **T15 (P3, human: ~10 min / CC: ~2 min)** — docs — Casing de `AUDITORIA.Tabla` en el criterio de reapertura de B2
- [ ] **T16 (P3, human: ~45 min / CC: ~8 min)** — backend — URL de ejemplo en el docstring de cada ruta nueva
- [ ] **T17 (P3, human: ~20 min / CC: ~5 min)** — backend — Test de contenido del 403 de F1

#### Decision Audit Trail — Fase 2.5 (DX)

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|-------|----------|----------------|-----------|-----------|----------|
| 51 | dx | Persona = contribuidor del repo (+ frontend como consumidor de la API) | Mechanical | P6 | Es el único tipo de desarrollador con demanda real; no hay usuario externo que instale esto | Fingir que es una herramienta para desarrolladores |
| 52 | dx | Modo DX POLISH | Mechanical | override | Mejora de producto existente, no producto nuevo orientado a devs | EXPANSION, TRIAGE |
| 53 | dx | Tier objetivo Competitive (2-5 min) | Mechanical | P1+P5 | Champion exigiría devcontainer = infraestructura nueva fuera del blast radius | Champion (<2 min) |
| 54 | dx | Momento mágico = compose + `verificar.ps1` en verde | Mechanical | P5+P4 | El compose ya existe; es el vehículo de menor esfuerzo que alcanza el tier | devcontainer, `setup.ps1` a mano |
| 55 | dx | DX-1 `.env.example` en vez de default en `client.ts` | Mechanical | P5 | Un default silencioso convierte un fallo de config en un fallo de red intermitente | Fallback en `client.ts` |
| 56 | dx | A1 usa código de error estable en `CODIGOS_ERROR_TRADUCIDOS` (SUPERSEDE de Fase 1) | Mechanical | P4 | `DomainRuleError`→400 dejaba como único discriminador el substring-match en español | `DomainRuleError` con prosa |
| 57 | dx | Desambiguación por header, no por status | Mechanical | P4 | 409 ya lo usa `IntegrityError`; el repo ya desambigua con `X-License-Revoked` sobre un 403 compartido | Status nuevo inventado |
| 58 | dx | Marca `concurrencia` registrada + `--strict-markers` + filtro en `verificar.ps1` | Mechanical | P1 | El escape hatch que el plan promete hoy no es alcanzable y un typo reporta verde | Confiar en `-m` sin registrar |
| 59 | dx | F1 parte rutas en vez de ampliar el PATCH único | Mechanical | P5 | `require_roles` es dependencia a nivel de ruta; lo que pide el plan no es expresable sin mover authz al servicio | Authz por campo en el servicio |
| 60 | dx | Paso `gen:api` obligatorio en toda fase que cambie el contrato | Mechanical | P1 | `verificar.ps1` no levanta el backend, así que nadie detecta el drift | Confiar en `tsc` |
| 61 | dx | Tabla de estado por fase al inicio del plan | Mechanical | P5 | El orden serial omite 4 fases sin decirlo y el grafo las presenta como vivas | Dejar las correcciones al final |
| 62 | dx | Tratamiento de pending decidido una vez, global (SUPERSEDE de Fase 2) | Mechanical | P5 | "Cada fase nombra el suyo" devuelve la decisión al implementador: 5 fases, 5 tratamientos | Una línea por fase |
| 63 | dx | `limit=200` de `disciplina.py` se sube, no se quita (SUPERSEDE de Fase 1) | Mechanical | P6 | La cota deja de ser cosmética justo cuando F1 vuelve escribible el catálogo | Quitarla como decía Fase 1 |
| 64 | dx | Casing de `AUDITORIA.Tabla` preservado en `TODOS.md` sin commitear el `.sql` | Mechanical | P3 | Preserva el dato sin chocar con la obligación de Fase 1; reduce T-3 a "además, ¿commiteamos?" | Perder el dato; forzar el conflicto |
| 65 | dx | Pass 7 (Community) con techo 6/10, sin proponer `CONTRIBUTING.md` | Mechanical | P2 | Repo privado de un autor: invertir en ecosistema sería trabajo para nadie | Recomendar CONTRIBUTING + licencia |
| 66 | dx | Sin instrumentación de TTHW (Pass 8 techo 7/10) | Mechanical | P2 | Alcance nuevo fuera del blast radius; el plan ya mide antes de construir | Agregar telemetría |
| 67 | dx | T-3 (commitear el `.sql`) y T-4 (partir A1 en 3 commits) al Gate | Taste | — | Ambas chocan con obligaciones ya aceptadas en Fase 1 | Auto-decidirlas |

### Fase 3 — Eng review (single-model, FULL_REVIEW)

Corre última, sobre el plan ya enmendado con las obligaciones de CEO, Diseño y
DX aplicadas al `Implementation plan`. Voz externa: **codex no disponible
(not_installed)**; cayó a subagente de Claude (contexto fresco, mismo harness,
identidad de modelo desconocida). Toda afirmación cargada se verificó contra el
código antes de aceptarse.

**El titular de esta fase:** cuatro bloqueantes, y **tres de los cuatro los
introdujeron las pasadas de corrección posteriores, no el cuerpo original del
plan** — incluido uno que introduje yo en la Fase 2.5. Las correcciones
mejoraron el razonamiento y a la vez especificaron cosas que el código no
soporta como están escritas. Eso es exactamente lo que una revisión de
ingeniería corriendo al final tiene que encontrar.

#### Step 0 — Scope challenge

**1. Qué código existente ya resuelve cada sub-problema.** Mapeado y
verificado, fase por fase:

| Sub-problema | Ya existe | ¿El plan lo reusa? |
|---|---|---|
| Lock de fila sobre partido | `PartidoRepository.get_or_404_bloqueado` (`repositories/partido.py:16`), `session.get(..., with_for_update=True)` | Sí. Un solo llamador hoy: `partido.py:198` |
| Transacción única multi-evento | `PartidoService.registrar_resultado_directo` (`partido.py:190-198`): `add()`+`flush()`, un `commit()` al final | Sí, A1 copia esa forma |
| Regla de doble amarilla | `services/reglas_tarjetas.py` `procesar_doble_amarilla`, devuelve sin persistir a propósito | Sí, no la reescribe |
| Errores tipados con header | `handlers.py:68-95` (`X-License-Revoked`, `Retry-After`) | Sí, pero mal aplicado — ver E3 |
| Códigos de error estables | `CODIGOS_ERROR_TRADUCIDOS` (`client.ts:73-86`) | Sí, vía Fase 2.5 |
| Derivaciones compartidas de UI | `components/eventos.ts` (`deriveHistorialElegibilidad`, `deriveTitularSuplente`, `deriveEnCancha`) | Sí, la expansión 1 va ahí |
| Selector de jugador | `SelectorJugadorBuscable` | Sí, C1 migra hacia él |
| Recreación de base de test | `conftest.py:67` `_recreate_test_database` | Parcial — ver E1 |
| Recuperación de evento pendiente | `MesaPanel.tsx:377` ("El evento pendiente no se pudo guardar") | **No.** El plan agrega una segunda — ver E8 |

**2. Mínimo conjunto de cambios.** El plan ya difiere B1, B2, E1 y F1. Lo que
queda vivo (A0, A1, A2, A3, C1, C2a, C2b, D1, exp.1) es el mínimo que cierra los
ítems que el usuario marcó como abiertos.

**3. Complexity check: DISPARA.** El plan toca más de 8 archivos e introduce
una excepción nueva (`ConcurrencyConflictError`) más una fixture nueva de test.
Por la metodología eso obliga a parar y ofrecer reducción. **Auto-decidido: NO
reducir** (override de /autoplan, P2 boil lakes). Es explícito, no un olvido: el
alcance ya se recortó dos veces en Fase 1 (cuatro fases diferidas con umbral
numérico), y volver a recortar acá sería re-litigar una decisión cerrada.

**4. Search check.** Aside no está instalado; corrió por WebSearch. Patrón
evaluado: `SELECT ... FOR UPDATE` bajo SQLAlchemy/asyncpg. Resultado
**[Layer 1]**: la espera indefinida es el footgun documentado del patrón, y las
mitigaciones estándar son `lock_timeout`, `nowait=True` o `skip_locked`. El
plan usa el patrón sin ninguna de las tres. Ver E2. No hay que inventar nada:
es tecnología aburrida bien conocida, mal configurada.

**5. TODOS cross-reference.** `TODOS.md` no bloquea este plan; el plan ES el
cierre de su sección `## Pendiente`. Crea trabajo nuevo que sí va a `TODOS.md`:
los umbrales de reapertura con su consulta al lado, y la nota de casing de
`AUDITORIA.Tabla`.

**6. Completeness check.** El plan elige la versión completa en los lugares que
importan (A1 reestructura en vez de parchear; C2 se parte en C2a/C2b en vez de
borrar y ver qué pasa). Los atajos que quedan son de verificación, no de
implementación, y esta fase los cierra: E6, E10, E13, E14, E15, E16, E17.

**7. Distribution check.** N/A: no introduce artefacto nuevo distribuible
(ni binario, ni paquete, ni imagen). El único cambio de empaquetado es
DX-2 (Postgres dentro del compose), que es desarrollo local, no distribución.

#### Step 0.5 — Voces duales (Eng)

**CODEX SAYS (eng):** no disponible — `CODEX_MODE: not_installed`. Sin
cobertura externa. `outside_status: unavailable`.

**OUTSIDE VOICE (subagente Claude, eng):** completado. INPUT
`eng a839ae300ffe6fd4843208c9e8339d2b7f55a18805cce0312026d17cea7e22df`
verificado. 4 bloqueantes, 6 medios, 7 menores.

```
ENG DUAL VOICES — CONSENSUS TABLE:
===============================================================
  Dimension                           Claude  Codex  Consensus
  ----------------------------------- ------- ------ ---------
  1. Architecture sound?               NO      N/A    N/A
  2. Test coverage sufficient?         NO      N/A    N/A
  3. Performance risks addressed?      NO      N/A    N/A
  4. Security threats covered?         PARCIAL N/A    N/A
  5. Error paths handled?              NO      N/A    N/A
  6. Deployment risk manageable?       SI      N/A    N/A
===============================================================
0/6 CONFIRMED. Codex ausente => N/A en las 6, nunca CONFIRMED.
Los 4 bloqueantes son hallazgos de UNA sola voz. Marcados como tales.
Se aceptan porque se verificaron contra el codigo, no por consenso.
```

#### Sección 1 — Arquitectura

```
ARQUITECTURA DE A1 (camino en vivo) — ANTES vs DESPUES

ANTES (hoy)
  POST /eventos-partido
    -> EventoPartidoService.create()
       |- partido_repo.get_or_404()            SIN LOCK
       |- verificar_arbitro_asignado()
       |- _verificar_partido_en_curso()
       |- _minuto_en_vivo()                    config_repo + hitos
       |- _validar_reglas_cambio()
       |- repo.create()  ---------------------> COMMIT #1 (base.py:43-48)
       `- _procesar_doble_amarilla_si_corresponde()
          |- evento_catalogo_repo.get_or_404()
          |- evento_catalogo_repo.list(nombre="Tarjeta Roja")
          |- procesar_doble_amarilla()         2 querys de conteo
          `- session.commit() ----------------> COMMIT #2 (linea 124-125)
                                               ^ la ventana de carrera vive
                                                 ENTRE los dos commits

DESPUES (A1 como lo especifica el plan enmendado)
  POST /eventos-partido
    -> EventoPartidoService.create()
       |- partido_repo.get_or_404_bloqueado()  FOR UPDATE  <-- lock tomado
       |- verificar_arbitro_asignado()             |
       |- _verificar_partido_en_curso()            |
       |- _minuto_en_vivo()                        | ~6 round trips
       |- _validar_reglas_cambio()                 | BAJO LOCK
       |- session.add() + flush()                  |
       |- _procesar_doble_amarilla_si_corresponde()|
       `- session.commit() ---------------------> lock liberado

  MISMA FILA, otro camino:
  PartidoService.registrar_resultado_directo()  (partido.py:198)
       `- get_or_404_bloqueado()  FOR UPDATE sobre el MISMO partido
          -> un batch retroactivo completo bajo el mismo lock

  CONSECUENCIA (E2/E5): los dos caminos toman el MISMO lock, sobre la MISMA
  fila, PRIMERO. Eso es CONTENCION, no deadlock. Y sin lock_timeout,
  la espera es infinita.
```

**E1 [P0] (confianza: 10/10) `backend/tests/conftest.py:89-91` + `database/05_seed.sql` — el teardown de A2 destruye datos sembrados a nivel de sesión y envenena la suite entera.**

Verificado línea por línea. `_test_db_ready` es `scope="session"` (`conftest.py:89`) y reconstruye la base UNA vez por corrida ejecutando `01_schema.sql`–`06_triggers.sql`. `05_seed.sql` inserta en **14 tablas**, entre ellas `EVENTOS` (el catálogo), `DISCIPLINA`, `MODALIDAD`, `PARTIDOS`, `EQUIPOS`, `JUGADORES`, `EVENTOS_PARTIDO`. Los ~520 tests dependen de esas filas y están protegidos únicamente por el rollback de savepoint de `db_session` (`conftest.py:112-125`).

A2 propone `TRUNCATE ... CASCADE` **con commits reales**. Un commit real no se revierte con el savepoint. `TRUNCATE PARTIDOS CASCADE` se propaga por el `ON DELETE CASCADE` de `EVENTOS_PARTIDO`, y no hay re-seed. A partir de ahí la suite falla según el orden en que pytest corra: verde local, rojo en CI, o al revés. Es la peor forma de fallo disponible porque no es determinista.

**Decisión (Mechanical, P1):** A2 recibe su **propia base**, `torneos_mvp_test_concurrencia`, construida por el mismo helper `_recreate_test_database`, con scope de módulo. Con eso el `TRUNCATE` sale gratis y los 520 tests quedan intocables por construcción. **Rechazado:** "DELETE acotado a las tablas tocadas" — las tablas que A3 toca *son* las sembradas, así que el peligro sigue vivo.

**E2 [P0] (confianza: 9/10) `services/partido.py:198` + ausencia de `lock_timeout` — el rescate de `DeadlockDetected` está especificado contra un fallo que no puede ocurrir, y el fallo real queda sin manejar.**

El plan pide "un test que fuerza el deadlock cruzado con `registrar_resultado_directo`". Los dos caminos adquieren `get_or_404_bloqueado(partido_id)` sobre la **misma fila única, primero**. Postgres levanta 40P01 solo ante adquisición cruzada de 2+ recursos; ordenamiento idéntico sobre un recurso produce contención. Ese test es inescribible tal como está, así que la obligación terminaría silenciosamente descartada o satisfecha con un test falso.

Y el fallo real queda descubierto: **`lock_timeout` no aparece en `backend/app` ni en `database/`** (verificado; los únicos hits están dentro de `.venv`). El default de Postgres es `lock_timeout = 0`, o sea esperar para siempre. Al árbitro se le corta el teléfono a mitad del request, esa transacción retiene el `FOR UPDATE`, y todo evento posterior de ese partido bloquea indefinidamente: un worker ASGI colgado por intento, y `verificar.ps1` en verde todo el tiempo.

**Decisión (Mechanical, P1 + P4 [Layer 1]):** `SET LOCAL lock_timeout` desde `Settings` — el plan ya rutea un umbral por `config.py`, que se use para el timeout real y no solo para el log. Mapear `LockNotAvailable`/`QueryCanceled` a `ConcurrencyConflictError`. El rescate de `DeadlockDetected` se conserva como defensa en profundidad, pero la obligación del "test de deadlock cruzado" se reemplaza por un **test de contención** (la sesión B bloquea, vence el timeout, devuelve 409). **Alternativa evaluada y rechazada:** `nowait=True`, que falla al instante — para un árbitro que toca dos veces, una espera acotada es mejor experiencia que un rechazo inmediato.

Corolario que cierra el mismo agujero: el plan pide loguear cuando la espera del `FOR UPDATE` supera un umbral. Un log solo puede dispararse *después* de que la espera termina, así que sin timeout la alerta para un cuelgue indefinido nunca se emite — justo el caso para el que la querés. Con `lock_timeout` el log se vuelve trivialmente correcto. Son un solo arreglo.

**E3 [P0] (confianza: 10/10) `frontend/src/api/client.ts:44-56` + `MesaPanel.tsx` (~40 call sites) — `X-Reintentable` es inalcanzable para el frontend. SUPERSEDE de una obligación que escribí yo en Fase 2.5.**

La Fase 2.5 especificó 409 + header `X-Reintentable: true` razonando por analogía con `X-License-Revoked`. La analogía se rompe, y lo verifiqué: `X-License-Revoked` lo consume el interceptor **global** `onResponse` (`client.ts:44-56`) como efecto de sesión (llama a `onLicenseRevoked()`). Un botón "Reintentar" por mutación necesita la señal **en el call site**, y todos los call sites la descartan: `MesaPanel.tsx:79-80, 91-94, 104-105, 114-115, 124-125, 137-140, 149-152` y siguientes hacen `const { data, error } = await api.GET(...)` seguido de `if (error) throw error`. `response` se desestructura afuera. `mutation.error` es el body parseado y nada más.

La ironía es que la otra mitad de mi propia obligación ya alcanza: `detail = "evento_conflicto_concurrente"` es un código estable en el body, y `CODIGOS_ERROR_TRADUCIDOS` es el mecanismo que ya existe.

**Decisión (Mechanical, P4):** se cae `X-Reintentable`. Queda 409 + el código estable. El componente discrimina con `error.detail === "evento_conflicto_concurrente"`. Salvedad que hay que dejar escrita: `apiErrorMessage` colapsa código a texto en español, así que el chequeo del reintento tiene que leer `error.detail` **antes** de traducir, nunca el string renderizado — que es precisamente la trampa de substring-matching que la obligación intentaba evitar, reintroducida una capa más arriba.

**E4 [P0] (confianza: 10/10) `services/evento_partido.py:189-192` + `services/reglas_tarjetas.py` — A1 exime a `anular` sobre una premisa que el código contradice.**

El plan dice que "`anular` opera sobre un evento ya existente por su propio ID, no sobre el estado compartido del partido". Es falso, y se ve en dos archivos: `procesar_doble_amarilla` cuenta las amarillas con `estado="Registrado"`, y `anular` hace exactamente `save_changes(evento, estado="Anulado")` (`evento_partido.py:192`) sobre esa misma columna, tomando el partido con `get_or_404` **sin lock** (línea 190).

Anular la amarilla #1 concurrentemente con la inserción de la amarilla #2 corre la carrera en las dos direcciones: una roja para un jugador que tiene una sola amarilla válida, o la roja que A1 busca garantizar que no aparece. Es el mismo resultado silencioso e irreparable-tras-el-cierre que justifica Track A entero.

**Decisión (Mechanical, P1):** `anular` toma el mismo lock del partido cuando el evento objetivo es una tarjeta. `corregir_minuto` sí es genuinamente seguro (el minuto no lo lee la regla) — se dice explícitamente en vez de agrupar los dos bajo una exención común.

**Failure scenario de producción por codepath nuevo** (lo pide la sección): árbitro con señal intermitente carga una amarilla; el request queda a medio camino reteniendo el `FOR UPDATE`; el segundo árbitro del mismo partido intenta cargar un gol y su request queda colgado sin timeout hasta que el worker muere. El plan no lo cubría; E2 lo cubre.

#### Sección 2 — Calidad de código

**E5 [P2] (confianza: 8/10) `evento_partido.py:72-125` — tiempo de retención del lock.**

A1 pasa a sostener el `FOR UPDATE` a través de `_minuto_en_vivo` (lookup de config + hitos), `_validar_reglas_cambio`, el insert, y `_procesar_doble_amarilla_si_corresponde` (get del catálogo + `list(nombre=...)` + dos querys de conteo): unos **6 round trips bajo lock**, donde hoy hay cero. Y `registrar_resultado_directo` sostiene el *mismo* lock durante un batch retroactivo entero, así que una carga en vivo puede quedar encolada detrás de un batch completo. Es correcto, pero es un cambio de latencia real y el plan factura A1 como "Effort M, sin cambio de contrato".

**Decisión (Mechanical, P3):** izar los lookups de solo lectura que no dependen de la fila bloqueada (los del catálogo de eventos para "Tarjeta Amarilla"/"Tarjeta Roja" son lecturas de catálogo) por encima del lock, y sumar el p95 de `POST /eventos-partido` al resultado observable declarado de A1 — el plan ya exige uno por track, y "tests verdes" no atrapa esto. **Va al Gate como T-5**: aceptar la retención más larga es defendible dado que la frecuencia medida de concurrencia es cero.

**E6 [P2] (confianza: 9/10) `conftest.py:127-145` — A3 no puede usar la fixture `client`.**

Verificado: `client` sobreescribe `get_db` con la `db_session` única y compartida. Dos sesiones genuinamente independientes significa que **A3 llama a los servicios directo, salteando las rutas**. Entonces A3 prueba el invariante del servicio pero no el camino HTTP: `verificar_arbitro_asignado`, `require_roles` y el mapeo del handler a 409 quedan sin cubrir por él.

**Decisión (Mechanical, P1):** está bien que sea así, pero se escribe en el bosquejo de una página que A2 ya tiene como precondición, porque descubrirlo a mitad de A2 es exactamente el riesgo de cronograma que el plan ya señala. Y el camino HTTP del 409 lleva su propio test con la fixture `client`.

**E7 [P2] (confianza: 8/10) — semántica del reintento subespecificada de una forma que corrompe datos.**

Dos mecánicas faltan y las dos cargan peso:
- Tras cualquier error DBAPI, SQLAlchemy deja la sesión en pending-rollback. El reintento tiene que hacer `await session.rollback()` primero o falla con un `PendingRollbackError` confuso en vez de reintentar.
- El reintento tiene que re-correr el **read-validate-insert completo**, no solo el insert. El `minuto` sale de `calcular_minuto_actual(..., datetime.now())`: reusar el valor previo al fallo escribe un minuto viejo, y `chk_eventos_partido_minuto` no lo atrapa porque sigue estando entre 0 y 130.

Contexto que refuerza: verificado que **no hay UNIQUE sobre `EVENTOS_PARTIDO`** (`02_constraints.sql:374-386` solo tiene FKs y checks), así que la base no es red de seguridad contra un doble insert.

**E8 [P2] (confianza: 9/10) `MesaPanel.tsx:377` — ya existe un camino de reintento sobre esta misma mutación.**

Hay una recuperación de "evento pendiente" con el mensaje "El evento pendiente no se pudo guardar — cargalo de nuevo." El plan agrega una segunda afordancia de reintento distinta para el 409, sin decir cómo componen. Un 409 sobre un evento *pendiente* dispara las dos.

**Decisión (Mechanical, P4 DRY):** el 409 se rutea por el mecanismo de pendiente que ya existe, en vez de sumar un segundo.

**E9 [P1] (confianza: 10/10) — la separación cuerpo/correcciones es un peligro vivo, no un tema de formato.**

Refuerza el hallazgo F-3 de la Fase 2.5, y la segunda voz lo encontró por su cuenta. Hoy el plan le dice al lector: A1 = cambiar a `get_or_404_bloqueado` (cuerpo) contra "ese cambio no cierra la carrera" (corrección); B2 = escribir y commitear el `.sql` (cuerpo) contra "ya corrió, no se commitea" (corrección); orden serial `A0→A1→A2→A3→C1…` (cuerpo) contra `A0→A1→C1→C2a→C2b→D1→exp.1→A2→A3` (corrección); el gate de merge de C2 (Fase 1) contra "ese gate es inaplicable" (Fase 2). **Se aplica al cuerpo ANTES de que arranque la ejecución.** Es el ítem más barato del plan y hoy el grafo de dependencias instruye activamente a empezar trabajo diferido.

**E10 [P2] (confianza: 8/10) — C2 pasó de ser un borrado a ser una feature con gate solo manual.**

La corrección de Fase 2 acierta en que no existe camino `sinConvocatoria` hacia `ModalSustitucion`. Pero el reemplazo (C2a construye la lista con fallback a plantilla, gateado en "un árbitro completa un cambio de punta a punta") no tiene verificación automatizada. Y entonces el invariante de "la cuenta de tests de Cambio no baja" no tiene contra qué contar, porque los tests viejos de `CargaEvento` se mudan a un camino que no existía cuando se tomó la cuenta.

**Decisión (Mechanical, P1):** el gate de C2a suma un test automatizado compañero (la lista de fallback renderiza con su caption, y un Cambio enviado desde ella produce el mismo body de POST que el camino con convocatoria). El recorrido humano queda encima, no en lugar de.

#### Sección 3 — Test review

**Detección de framework:** `RUNTIME:python` (`pytest.ini`, `requirements.txt`), `RUNTIME:node` (`package.json`), pytest + vitest. 486 funciones `def test_` en 49 archivos de `backend/tests/`, 37 archivos de test en frontend. Gate único: `verificar.ps1`.

```
DIAGRAMA DE COBERTURA — codepaths nuevos de este plan

CODE PATHS                                          USER FLOWS
[+] EventoPartidoService.create (A1)                [+] Arbitro carga 2a amarilla
  |- get_or_404_bloqueado                             |- [GAP] [->E2E] doble tap
  |  |- [GAP] contencion: B espera y vence timeout    |         antes del re-render
  |  `- [GAP] lock sostenido: p95 medido              |- [GAP] roja auto visible
  |- flush (sin commit intermedio)                    |         antes de confirmar
  |  `- [GAP][REGRESION] nada persiste a mitad        `- [GAP] mensaje de reintento
  |- _procesar_doble_amarilla_si_corresponde                   distinto del rechazo
  |  `- [GAP] roja auto en la MISMA transaccion
  `- rescate ConcurrencyConflictError               [+] Arbitro anula tarjeta
     |- [GAP] rollback antes del reintento            `- [GAP] anular vs insertar
     `- [GAP] reintento recalcula minuto                       en paralelo (E4)

[+] anular (E4)                                     [+] Cambio sin convocatoria
  `- [GAP] toma lock si el evento es tarjeta           |- [GAP] lista cae a plantilla
[+] corregir_minuto                                   |         con su caption
  `- [OK] no lo lee la regla; sin lock, dicho          `- [GAP] mismo POST body que
[+] Fixture de concurrencia (A2)                              el camino con convocatoria
  |- [GAP] base propia, no la compartida
  `- [GAP] guard de nombre ANTES del terminate      [+] Estados de error
[+] handlers: ConcurrencyConflictError -> 409        |- [GAP] 409 no comparte clase
  `- [GAP] camino HTTP (A3 no lo cubre, E6)          |         con 4xx de validacion
[+] D1 3 zonas + sticky 375px                        `- [GAP] 403 de F1 por contenido
  `- [MANUAL] JSDOM no prueba sticky/grid/44px

COBERTURA: 1/18 rutas con cobertura definida (6%)
GAPS: 17  |  1 REGRESION (mandatoria, sin pregunta)  |  1 solo-manual
```

**REGRESIÓN (regla de hierro, se agrega sin preguntar):** A1 cambia
comportamiento existente — de commit-por-evento a transacción única. Un test de
regresión es obligatorio: **nada persiste a mitad de camino si el request falla
después del insert y antes del commit**. Hoy, con `repo.create()` commiteando
(`base.py:43-48`), un fallo posterior deja el evento escrito. Después de A1 no
debe quedar nada. Además: grepear los tests que crean dos eventos en secuencia y
afirman persistencia intermedia — esos son los que el commit-por-evento venía
sosteniendo en silencio.

**Test que falta y que es el invariante real de A1:** que la roja automática
caiga en la **misma transacción** que la segunda amarilla. "Dos amarillas
producen una roja" ya pasa hoy en el caso secuencial, así que no prueba lo que
A1 compra.

**E11 [P3] (confianza: 8/10) `--strict-markers`** convierte un aviso en fallo
duro sobre 49 archivos que nunca se chequearon. Se corre
`pytest --collect-only -W error::pytest.PytestUnknownMarkWarning` antes de
comprometerse. Y `addopts` en `pytest.ini` compone con el `-q` de
`verificar.ps1:46`.

**E12 [P1] (confianza: 10/10) `conftest.py:67-75` — el guard de nombre de base
está en el lugar equivocado.** SUPERSEDE parcial de la obligación de Fase 1, que
lo ata al `DROP DATABASE`. Verificado: dentro de `_recreate_test_database`, el
`pg_terminate_backend(pid) ... WHERE datname = $1` corre en la **línea 71** y el
`DROP DATABASE` en la **75**. Un nombre mal apuntado mata todas las conexiones
vivas a `torneos_mvp` antes de llegar al DROP guardado. **El guard va al
principio de la función, no delante del DROP.**

**E15 [P2]** `incluir_no_inscritos=true` (si B1 se reabre) necesita un test que
afirme que `torneo_ids_permitidos` sigue aplicando con el flag puesto.
Implementado de forma ingenua como "saltear el filtro", es un bypass de
autorización alcanzable por query string.

**E16 [P2]** El test del 403 de F1 tiene que manejar un token real de
`TorneoAdmin` por la ruta: `require_roles` hace bypass para `AdminGeneral`
(`deps.py:130`), así que una aserción sobre el string del rol no prueba nada.

**E17 [P2]** La verificación de D1 es **visual y manual**, y así hay que
escribirlo. JSDOM no prueba grid areas, ni `position: sticky`, ni targets de
44px. Y `sticky` falla en silencio bajo cualquier ancestro con `overflow`
scrollable, probable en una hoja de estilos que mezcla `min-width` (800/1000) y
`max-width` (480/640). Dejar que "`MesaPanel.test.tsx` no se mueve" se lea como
prueba sería falso.

Artefacto de test plan escrito a disco (ver ruta en el resumen de finalización).

#### Sección 4 — Performance

**N+1:** ninguno nuevo. `_procesar_doble_amarilla_si_corresponde` hace 4
consultas por evento de tarjeta, pero son por-request, no por-fila.

**El riesgo real es de latencia, no de consulta** (E5): ~6 round trips bajo un
lock exclusivo donde hoy hay cero, más la posibilidad de encolarse detrás de un
batch retroactivo entero de `registrar_resultado_directo`. Mitigado izando los
lookups de catálogo y midiendo el p95.

**Memoria y caché:** sin cambios. El catálogo de eventos se releé por request;
es una tabla chica y cachearla sería optimización prematura (P5).

**Riesgo de despliegue:** bajo. A1 no cambia esquema ni contrato de API. E1
(base propia para A2) es solo de tests. Nada requiere migración.

#### "NOT in scope" — Fase 3

- Reescribir `registrar_resultado_directo` para acortar su retención de lock — es código existente que ya funciona; solo se mide.
- Cachear el catálogo de eventos — optimización prematura, tabla chica.
- Unique constraint sobre `EVENTOS_PARTIDO` — cambio de esquema con riesgo sobre datos existentes; el rescate de E7 lo cubre sin tocar la base.
- Cubrir el camino HTTP dentro de A3 — imposible con la fixture `client`; va como test propio (E6).
- Mover `verificar.ps1` a CI — ya está en "Descartado a propósito" de `TODOS.md`.
- Reescribir `handlers.py` para dejar de mapear `DBAPIError` a 400 — código existente, nombrado en Fase 2.5 como contexto.

#### "What already exists" — Fase 3

Ver la tabla del Step 0. Lo que el plan **reusa bien**: el helper de lock, la
forma transaccional de `registrar_resultado_directo`, `reglas_tarjetas`,
`eventos.ts`, `SelectorJugadorBuscable`, `_recreate_test_database`. Lo que
**reconstruye sin necesidad**: una segunda afordancia de reintento cuando
`MesaPanel.tsx:377` ya tiene una (E8).

Dos cosas que este repo tiene y que evitan trampas conocidas, verificadas:
`expire_on_commit=False` en la factory de producción (`db/database.py:24`) y en
la de tests, así que la reestructuración de A1 **no** va a chocar contra
`MissingGreenlet` al serializar la respuesta — un peligro real en esta forma de
cambio, al que este repo resulta inmune. Y no hay UNIQUE en `EVENTOS_PARTIDO`
(`02_constraints.sql:374-386`), que es exactamente la premisa sobre la que el
plan prohíbe el reintento antes de la atomicidad.

#### Registro de modos de fallo

| # | Codepath | Modo de fallo realista | ¿Test? | ¿Manejo de error? | ¿Lo ve el usuario? | Gap crítico |
|---|---|---|---|---|---|---|
| 1 | `create` con `FOR UPDATE` | Cliente muere reteniendo el lock; todo el partido bloquea | NO | **NO** (sin `lock_timeout`) | NO, cuelga | **SÍ — E2** |
| 2 | A2 `TRUNCATE` | Borra seed de sesión; falla no determinista por orden | NO | NO | No aplica (tests) | **SÍ — E1** |
| 3 | 409 en el frontend | El call site no ve el header; no hay reintento | NO | NO | Error genérico | **SÍ — E3** |
| 4 | `anular` concurrente | Roja espuria o roja faltante | NO | NO | NO, silencioso | **SÍ — E4** |
| 5 | Reintento sin rollback | `PendingRollbackError` en vez de reintentar | NO | NO | Error confuso | SÍ — E7 |
| 6 | Reintento con minuto viejo | Evento con minuto incorrecto; el check no lo atrapa | NO | NO | NO, silencioso | SÍ — E7 |
| 7 | Doble afordancia de reintento | Dos UIs de recuperación compiten | NO | Parcial | Confuso | NO — E8 |
| 8 | C2a sin test | La lista de fallback se rompe sin aviso | NO | NO | Lista vacía | SÍ — E10 |
| 9 | Guard mal ubicado | Mata conexiones a `torneos_mvp` antes del DROP | NO | NO | Pérdida de sesiones dev | SÍ — E12 |
| 10 | `sticky` bajo `overflow` | El marcador no queda fijo a 375px | NO (JSDOM no puede) | N/A | Sí, visible | NO — E17 |
| 11 | `--strict-markers` | Colección falla en 49 archivos | NO | NO | Suite roja | NO — E11 |
| 12 | B1 flag de capacidad | Bypass de autorización por query string | NO | NO | NO, silencioso | SÍ — E15 |

**9 gaps críticos**, 4 de ellos P0.

#### Estrategia de paralelización por worktree

| Paso | Módulos tocados | Depende de |
|---|---|---|
| A0 | (baseline, commit) | — |
| A1 | `backend/app/services/`, `backend/app/exceptions/`, `backend/app/core/`, `frontend/src/api/`, `frontend/src/components/` | A0 |
| C1 | `frontend/src/components/` | A0 |
| C2a/C2b | `frontend/src/components/` | C1 |
| D1 + exp.1 | `frontend/src/components/`, `frontend/src/index.css` | C2b |
| A2/A3 | `backend/tests/`, `backend/pytest.ini`, `verificar.ps1` | A1 |
| DX-1/DX-2 | `frontend/.env.example`, `infrastructure/`, `README.md` | — |

```
Lane A: A0 -> A1 -> A2 -> A3        (secuencial, comparten backend/app + tests)
Lane B: A0 -> C1 -> C2a -> C2b -> D1 -> exp.1   (secuencial, comparten components/)
Lane C: DX-1 -> DX-2               (independiente, no toca ni app ni components)
```

**Orden de ejecución:** A0 primero y solo. Después A + B + C en paralelo.
**Bandera de conflicto:** A1 toca `frontend/src/api/client.ts` y
`frontend/src/components/MesaPanel.tsx` (el 409 y su botón de reintento), y el
Lane B reorganiza `MesaPanel.tsx` entero en D1. **Lanes A y B chocan en
`MesaPanel.tsx`.** Mitigación: la parte frontend de A1 (leer `error.detail`,
mostrar el reintento) se hace DESPUÉS de D1, dentro del Lane B, y el Lane A
queda backend puro. Eso también respeta la obligación de Fase 1 de mantener
`MesaPanel.tsx` fuera del commit del baseline.

#### Decisión de taste al Gate — Fase 3

- **T-5** Izar los lookups de catálogo por encima del lock y medir el p95 de
  `POST /eventos-partido` (recomendado — el lock pasa de 0 a ~6 round trips y el
  plan factura A1 como "sin cambio de contrato") vs aceptar la retención más
  larga tal cual, dado que la frecuencia medida de concurrencia es CERO casos y
  el volumen orgánico es de 15 torneos.

<!-- autoplan-accepted:eng -->
- **A2 corre contra su PROPIA base de datos, `torneos_mvp_test_concurrencia`, construida por el mismo helper `_recreate_test_database`, con scope de módulo.** Verificado: `backend/tests/conftest.py:89-91` declara `_test_db_ready` con `scope="session"` y reconstruye la base UNA vez por corrida ejecutando `01_schema.sql`–`06_triggers.sql`; `database/05_seed.sql` inserta en 14 tablas, entre ellas `EVENTOS` (el catálogo), `DISCIPLINA`, `MODALIDAD`, `PARTIDOS`, `EQUIPOS`, `JUGADORES` y `EVENTOS_PARTIDO`, y los ~520 tests dependen de esas filas protegidos solo por el rollback de savepoint de `db_session` (`conftest.py:112-125`). El `TRUNCATE ... CASCADE` con commits reales que A2 propone NO se revierte con ese savepoint y se propaga por el `ON DELETE CASCADE` de `EVENTOS_PARTIDO`, sin re-seed: la suite pasa a fallar según el orden en que pytest corra, o sea verde local y rojo en CI. Con base propia el TRUNCATE sale gratis y los 520 tests quedan intocables por construcción. RECHAZADO: "DELETE acotado a las tablas tocadas" — las tablas que A3 toca son justamente las sembradas. Verificación: correr la suite completa dos veces seguidas en la misma sesión, con los tests de A3 incluidos, da el mismo resultado.
- **A1 fija `lock_timeout` y reemplaza el test de deadlock por un test de contención.** Verificado: `get_or_404_bloqueado` tiene un solo llamador hoy, `PartidoService.registrar_resultado_directo` (`backend/app/services/partido.py:198`), y A1 haría que los dos caminos adquieran el `FOR UPDATE` sobre la MISMA fila de partido, PRIMERO. Ordenamiento idéntico sobre un único recurso produce CONTENCIÓN, no `DeadlockDetected`: Postgres levanta 40P01 solo ante adquisición cruzada de 2+ recursos, así que el "test que fuerza el deadlock cruzado con `registrar_resultado_directo`" que pide Fase 1 es inescribible y terminaría descartado o satisfecho con un test falso. Y el fallo real queda descubierto: `lock_timeout` no aparece en `backend/app` ni en `database/` (verificado; los únicos hits están dentro de `.venv`), y el default de Postgres es 0 = esperar para siempre, así que un cliente que muere reteniendo el lock cuelga indefinidamente todo evento posterior de ese partido, con `verificar.ps1` en verde. Queda: `SET LOCAL lock_timeout` leído desde `Settings` (el mismo `config.py` por el que ya se rutea el umbral del log — se usa para el timeout REAL, no solo para loguear); `LockNotAvailable`/`QueryCanceled` mapeadas a `ConcurrencyConflictError`; el rescate de `DeadlockDetected` se conserva como defensa en profundidad. SUPERSEDE de la obligación de Fase 1 en la parte del test: en vez del deadlock cruzado, un test de CONTENCIÓN (la sesión B espera, vence el timeout y recibe 409). RECHAZADO: `nowait=True`, que falla al instante — para un árbitro que toca dos veces, una espera acotada es mejor experiencia que un rechazo inmediato. Corolario incluido: el log de "espera del `FOR UPDATE` por encima del umbral" solo puede dispararse DESPUÉS de que la espera termina, así que sin timeout la alerta para un cuelgue indefinido nunca se emite; con `lock_timeout` el log se vuelve trivialmente correcto. Son un solo arreglo. Verificación: test de dos sesiones donde la B vence el timeout y recibe 409 con el código estable, y assert sobre el log de contención.
- **Se elimina el header `X-Reintentable`. El 409 lleva solo el código estable en `detail`.** SUPERSEDE de la obligación de Fase 2.5 que especificaba `409 + X-Reintentable: true` razonando por analogía con `X-License-Revoked`. La analogía se rompe y está verificado: `X-License-Revoked` lo consume el interceptor GLOBAL `onResponse` (`frontend/src/api/client.ts:44-56`) como efecto de sesión, llamando a `onLicenseRevoked()`, mientras que un botón "Reintentar" por mutación necesita la señal EN el call site — y todos los call sites la descartan: `frontend/src/components/MesaPanel.tsx:79-80, 91-94, 104-105, 114-115, 124-125, 137-140, 149-152` y siguientes hacen `const { data, error } = await api.GET(...)` seguido de `if (error) throw error`, con `response` desestructurado afuera; `mutation.error` es el body parseado y nada más, en ~40 sitios. La otra mitad de la obligación ya alcanza: `detail = "evento_conflicto_concurrente"` es un código estable y `CODIGOS_ERROR_TRADUCIDOS` (`client.ts:73-86`) es el mecanismo existente. El componente discrimina con `error.detail === "evento_conflicto_concurrente"`. SALVEDAD obligatoria: `apiErrorMessage` colapsa código a texto en español, así que el chequeo del reintento lee `error.detail` ANTES de traducir, nunca el string renderizado — si no, se reintroduce una capa más arriba el substring-matching que la obligación buscaba evitar. Verificación: test de frontend que afirma el botón de reintento a partir de `error.detail`, sin leer texto renderizado y sin plomería nueva en los call sites.
- **`anular` toma el mismo lock del partido cuando el evento objetivo es una tarjeta.** SUPERSEDE de la exención de Fase 1 que afirmaba que "`anular` opera sobre un evento ya existente por su propio ID, no sobre el estado compartido del partido". Es falso y se verifica en dos archivos: `procesar_doble_amarilla` (`backend/app/services/reglas_tarjetas.py`) cuenta las amarillas filtrando `estado="Registrado"`, y `anular` hace exactamente `save_changes(evento, estado="Anulado")` (`backend/app/services/evento_partido.py:192`) sobre esa misma columna, tomando el partido con `get_or_404` SIN lock (línea 190). Anular la amarilla #1 en paralelo con el insert de la amarilla #2 corre la carrera en las dos direcciones: una roja para un jugador con una sola amarilla válida, o la desaparición de la roja que A1 busca garantizar — el mismo resultado silencioso e irreparable tras el cierre que justifica Track A entero. `corregir_minuto` SÍ es genuinamente seguro porque la regla no lee el minuto: se dice explícitamente en vez de agrupar los dos bajo una exención común. Verificación: test de dos sesiones que anula la amarilla #1 mientras se inserta la #2 y afirma el conteo final correcto.
- **El reintento de A1 hace `await session.rollback()` antes de reintentar y re-corre el read-validate-insert COMPLETO, no solo el insert.** Tras cualquier error DBAPI, SQLAlchemy deja la sesión en pending-rollback, así que sin el rollback previo el reintento falla con un `PendingRollbackError` confuso en vez de reintentar. Y el `minuto` sale de `calcular_minuto_actual(..., datetime.now())`: reusar el valor previo al fallo escribe un minuto viejo, y `chk_eventos_partido_minuto` no lo atrapa porque sigue estando entre 0 y 130. Refuerzo verificado: NO hay UNIQUE sobre `EVENTOS_PARTIDO` (`database/02_constraints.sql:374-386` solo tiene FKs y checks), así que la base no es red de seguridad contra un doble insert. Verificación: test que fuerza el fallo, afirma que el reintento recalcula el minuto y que queda exactamente un evento persistido.
- **El 409 se rutea por el mecanismo de recuperación de "evento pendiente" que ya existe en `frontend/src/components/MesaPanel.tsx:377`** ("El evento pendiente no se pudo guardar — cargalo de nuevo."), en vez de agregar una segunda afordancia de reintento. Hoy el plan sumaría una segunda y no dice cómo componen; un 409 sobre un evento pendiente dispararía las dos. Verificación: hay un solo camino de recuperación en la UI de mesa y el 409 entra por él.
- **A3 llama a los servicios directo, no por las rutas, y eso se escribe en el bosquejo de una página que A2 ya tiene como precondición.** Verificado: la fixture `client` (`backend/tests/conftest.py:127-145`) sobreescribe `get_db` con la `db_session` única y compartida, así que dos sesiones genuinamente independientes no pueden pasar por ella. Consecuencia que hay que nombrar antes de empezar: A3 prueba el invariante del servicio pero NO el camino HTTP, así que `verificar_arbitro_asignado`, `require_roles` y el mapeo del handler a 409 quedan sin cubrir por A3 y llevan su propio test con la fixture `client`. Descubrir esto a mitad de A2 es exactamente el riesgo de cronograma que el plan ya señala. Verificación: el bosquejo lo dice y existe el test HTTP del 409 aparte.
- **REGRESIÓN (obligatoria, sin pregunta): test que afirma que NADA persiste a mitad de camino si el request falla después del insert y antes del commit.** A1 cambia comportamiento existente: hoy `repo.create()` commitea (`backend/app/repositories/base.py:43-48`) y un fallo posterior deja el evento escrito; después de A1 no debe quedar nada. Se suma el barrido: grepear los tests existentes que crean dos eventos en secuencia y afirman persistencia intermedia, porque son los que el commit-por-evento venía sosteniendo en silencio. Verificación: ese test falla contra el código de hoy y pasa después de A1, más los 486 tests existentes en verde.
- **Test del invariante real de A1: la roja automática cae en la MISMA transacción que la segunda amarilla.** "Dos amarillas producen una roja" ya pasa hoy en el caso secuencial, así que no prueba lo que A1 compra. Verificación: el test afirma atomicidad, no solo el resultado final.
- **El guard de nombre de base va al PRINCIPIO de `_recreate_test_database`, no delante del `DROP DATABASE`.** SUPERSEDE parcial de la obligación de Fase 1, que lo ata al DROP. Verificado: dentro de `backend/tests/conftest.py:67-75`, el `pg_terminate_backend(pid) ... WHERE datname = $1` corre en la línea 71 y el `DROP DATABASE IF EXISTS` en la 75 — un nombre mal apuntado mata todas las conexiones vivas a `torneos_mvp` antes de llegar al DROP guardado. Verificación: el test unitario que apunta el helper a `torneos_mvp` afirma que levanta ANTES de ejecutar el terminate, no solo antes del DROP.
- **C2a lleva un test automatizado compañero además del recorrido humano.** La corrección de Fase 2 acierta en que no existe camino `sinConvocatoria` hacia `ModalSustitucion`, pero su reemplazo (C2a construye la lista con fallback a plantilla, gateado en "un árbitro completa un cambio de punta a punta") quedó sin verificación automatizada, y entonces el invariante de Fase 1 de "la cuenta de tests de Cambio no baja" no tiene contra qué contar, porque los tests viejos de `CargaEvento` se mudan a un camino que no existía cuando se tomó la cuenta. El test compañero afirma dos cosas: que la lista de fallback renderiza con su caption, y que un Cambio enviado desde ella produce el mismo body de POST que el camino con convocatoria. El recorrido humano queda encima, no en lugar de. Verificación: ese test existe y pasa antes del retiro de C2b.
- Antes de comprometerse con `addopts = --strict-markers` se corre `pytest --collect-only -W error::pytest.PytestUnknownMarkWarning`: convierte un aviso en fallo duro sobre 49 archivos de test que nunca se chequearon. Y se deja escrito que `addopts` en `pytest.ini` compone con el `-q` de `verificar.ps1:46`. Verificación: la corrida de colección pasa limpia antes del commit que agrega el flag.
- Si B1 se reabre, `incluir_no_inscritos=true` lleva un test que afirma que `torneo_ids_permitidos` SIGUE aplicando con el flag puesto. Implementado de forma ingenua como "saltear el filtro", es un bypass de autorización alcanzable por query string. Verificación: el test afirma que un TorneoAdmin con el flag no ve filas fuera de sus torneos asignados.
- El test del 403 de F1 maneja un token real de `TorneoAdmin` a través de la ruta, no una aserción sobre el string del rol: `require_roles` hace bypass para `AdminGeneral` (`backend/app/api/deps.py:130`), así que un test mal armado pasa sin probar nada. Verificación: el test usa la fixture `client` con un token de TorneoAdmin.
- **La verificación de D1 se declara VISUAL Y MANUAL en el plan.** JSDOM no prueba grid areas, ni `position: sticky`, ni targets de 44px, así que dejar que "`MesaPanel.test.tsx` no se mueve" se lea como prueba sería falso. Se agrega la advertencia concreta: `position: sticky` falla en silencio bajo cualquier ancestro con `overflow` scrollable, y `frontend/src/index.css` mezcla `min-width` (800/1000) con `max-width` (480/640), así que hay que inspeccionar la cadena de ancestros a 375px. Verificación: el plan dice que D1 se verifica a ojo, en un dispositivo, y lista los tres puntos a mirar.
- **El cuerpo del plan se corrige ANTES de que arranque la ejecución, no como tarea al final.** Refuerza la obligación de Fase 2.5 y sube su prioridad a bloqueante de arranque. Las cuatro contradicciones vivas hoy: A1 = cambiar a `get_or_404_bloqueado` (cuerpo) contra "ese cambio no cierra la carrera" (corrección); B2 = escribir y commitear el `.sql` (cuerpo) contra "ya corrió, no se commitea" (corrección); orden serial `A0→A1→A2→A3→C1…` (cuerpo) contra `A0→A1→C1→C2a→C2b→D1→exp.1→A2→A3` (corrección); el gate de merge de C2 de Fase 1 contra "ese gate es inaplicable" de Fase 2. Mientras no se aplique, el grafo de dependencias del cuerpo instruye activamente a empezar trabajo diferido. Verificación: `git status` limpio y el cuerpo corregido en el commit anterior al arranque de A1.
- **La parte frontend de A1 (leer `error.detail`, mostrar el reintento) se hace DESPUÉS de D1, dentro del mismo lane que reorganiza `MesaPanel.tsx`; el lane de A1 queda backend puro.** A1 tocaría `frontend/src/api/client.ts` y `frontend/src/components/MesaPanel.tsx`, y D1 reorganiza `MesaPanel.tsx` entero: correr los dos lanes en paralelo choca en ese archivo. Esto además respeta la obligación de Fase 1 de mantener `MesaPanel.tsx` fuera del commit del baseline. Verificación: ningún commit toca `MesaPanel.tsx` desde dos tracks a la vez.
- A1 declara su resultado observable en términos medibles, no solo "tests verdes": el p95 de `POST /eventos-partido` antes y después. El plan ya exige un resultado observable por track (obligación de Fase 1) y este es el de A1. Verificación: los dos números escritos en el track antes de cerrarlo.
<!-- /autoplan-accepted:eng -->

#### Resumen de finalización — Fase 3 (Eng)

- **Step 0 — Scope Challenge:** alcance ACEPTADO tal cual. El complexity check
  dispara (más de 8 archivos, excepción nueva, fixture nueva) y se resuelve
  explícitamente en "no reducir" (override de /autoplan, P2): el alcance ya se
  recortó en Fase 1 con cuatro fases diferidas y umbral numérico, y volver a
  recortarlo sería re-litigar una decisión cerrada.
- **Architecture Review:** 4 issues (4 P0).
- **Code Quality Review:** 6 issues (1 P1, 5 P2).
- **Test Review:** diagrama producido, **17 gaps**, 1 REGRESIÓN obligatoria,
  1 camino solo verificable a mano.
- **Performance Review:** 1 issue (retención de lock, P2 → taste T-5).
- **NOT in scope:** escrito (6 ítems).
- **What already exists:** escrito (9 mapeos + 2 trampas que este repo ya evita).
- **TODOS.md updates:** 2 ítems (umbrales con su consulta al lado; casing de
  `AUDITORIA.Tabla`), ambos ya cubiertos por obligaciones de Fase 2.5.
- **Failure modes:** 12 modos mapeados, **9 gaps críticos** (4 P0).
- **Outside voice:** codex unavailable (`not_installed`); subagente Claude
  completado, INPUT verificado.
- **Parallelization:** 3 lanes (A backend, B frontend, C DX), 1 bandera de
  conflicto resuelta moviendo la parte frontend de A1 detrás de D1.
- **Lake Score:** 6/6 — las seis decisiones que comparaban opción completa
  contra atajo eligieron la completa (E1 base propia, E2 lock_timeout, E4 lock
  en `anular`, E5 regresión, E10 test compañero, E12 test HTTP aparte).
- **Unresolved decisions:** 0 de esta fase. 3 van al Gate (T-3, T-4, T-5).

#### Temas cross-phase

**Tema 1: el plan se contradice a sí mismo, y lo encontraron dos fases
independientes.** La Fase 2.5 lo marcó como C1/F-3 (documentación) y la Fase 3
lo marcó como E9 (peligro de ejecución). Ninguna vio el hallazgo de la otra.
Señal de alta confianza: **es el ítem más barato del plan y el de mayor daño si
no se hace**, porque hoy el grafo de dependencias del cuerpo instruye
activamente a empezar trabajo diferido.

**Tema 2: las correcciones tardías introdujeron defectos que el cuerpo original
no tenía.** Tres de los cuatro bloqueantes de Fase 3 nacieron en pasadas de
corrección posteriores: el test de deadlock (Fase 1), `X-Reintentable`
(Fase 2.5) y el gate solo-manual de C2a (Fase 2). Es un patrón, no tres
accidentes: cada ronda de corrección mejoró el razonamiento y a la vez
especificó mecanismos sin volver a verificarlos contra el código. La lección
operativa está registrada como learning.

**Tema 3: la verificación se quedaba en "tests verdes" mientras los riesgos
reales eran invisibles a los tests.** Fase 2.5 lo vio en el gate por defecto
(`verificar.ps1` sin filtro de marcas) y Fase 3 lo vio en tres lugares
distintos: el p95 bajo lock, la verificación de D1 (JSDOM no puede probar
sticky ni 44px) y el teardown de A2 (que falla según el orden de pytest).

**Tema 4 (convergencia sobre B1).** Fase 1 lo mandó al Gate como UC-3 ("matar
B1, premisa falsa por modelo de datos"). Fase 2.5 llegó por otro camino — el
`alcance` elegible por el cliente invierte el default seguro y mezcla una
audiencia con un eje de datos. Dos fases, dos razonamientos, misma conclusión.

#### Decision Audit Trail — Fase 3 (Eng)

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|-------|----------|----------------|-----------|-----------|----------|
| 68 | eng | No reducir alcance pese a que el complexity check dispara | Mechanical | P2 | Ya se recortó en Fase 1 con umbral numérico; recortar de nuevo re-litiga una decisión cerrada | Reducir a un subconjunto |
| 69 | eng | A2 recibe su propia base `torneos_mvp_test_concurrencia` | Mechanical | P1 | `scope="session"` + 14 tablas sembradas: un TRUNCATE con commits reales deja la suite fallando por orden | DELETE acotado (el peligro sigue vivo) |
| 70 | eng | `lock_timeout` desde `Settings`, test de contención en vez de deadlock | Mechanical | P1+P4 | Mismo lock, misma fila, primero = contención; y sin timeout la espera es infinita | `nowait=True` (peor UX para doble tap) |
| 71 | eng | Se elimina `X-Reintentable`; queda el código estable en `detail` | Mechanical | P4 | El interceptor es global y los ~40 call sites descartan `response` | Plomear `response` en 40 sitios |
| 72 | eng | `anular` toma el lock si el evento es tarjeta; `corregir_minuto` no | Mechanical | P1 | `procesar_doble_amarilla` filtra por la columna que `anular` muta | Mantener la exención de Fase 1 |
| 73 | eng | Regresión obligatoria: nada persiste a mitad | Mechanical | regla de hierro | A1 cambia comportamiento existente; hoy `repo.create()` commitea | Preguntar (la regla lo prohíbe) |
| 74 | eng | Rollback antes del reintento + recálculo del minuto | Mechanical | P1 | pending-rollback da `PendingRollbackError`; el minuto viejo pasa el CHECK | Reintentar solo el insert |
| 75 | eng | El 409 entra por el mecanismo de evento pendiente que ya existe | Mechanical | P4 | `MesaPanel.tsx:377` ya lo tiene; dos caminos compiten en el mismo caso | Segunda afordancia |
| 76 | eng | El guard de base va al inicio de la función, no antes del DROP | Mechanical | P1 | `pg_terminate_backend` corre en :71 y el DROP en :75 | Dejarlo delante del DROP |
| 77 | eng | C2a suma test automatizado además del recorrido humano | Mechanical | P1 | El invariante de cuenta de tests se queda sin contra qué contar | Solo gate manual |
| 78 | eng | Verificación de D1 declarada visual y manual | Mechanical | P5 | JSDOM no prueba sticky, grid ni 44px | Dejar que el test se lea como prueba |
| 79 | eng | Parte frontend de A1 detrás de D1; lane A queda backend puro | Mechanical | P3 | Los dos lanes tocan `MesaPanel.tsx` | Paralelizar y resolver conflictos |
| 80 | eng | A1 declara p95 antes/después como resultado observable | Mechanical | P1 | El plan exige resultado observable por track y "tests verdes" no lo cubre | Solo tests verdes |
| 81 | eng | T-5 (izar lookups fuera del lock) al Gate | Taste | — | Ambas viables: la frecuencia medida de concurrencia es cero | Auto-decidirla |


#### Implementation Tasks — Fase 3 (Eng)

Artefacto JSONL: `~/.gstack/projects/Score-App/tasks-eng-review-20260918-143619.jsonl`
(16 tareas: 5 P1, 8 P2, 3 P3).

- [ ] **E1 (P1, human: ~4 h / CC: ~30 min)** — tests — Dar a A2 su propia base torneos_mvp_test_concurrencia con scope de modulo
  - Surfaced by: Seccion 1 / E1 — _test_db_ready es scope=session (conftest.py:89) y 05_seed.sql siembra 14 tablas; un TRUNCATE CASCADE con commits reales no lo revierte el savepoint y deja la suite fallando segun el orden de pytest.
  - Files: backend/tests/conftest.py
- [ ] **E2 (P1, human: ~3 h / CC: ~25 min)** — backend — Fijar lock_timeout desde Settings y reemplazar el test de deadlock por uno de contencion
  - Surfaced by: Seccion 1 / E2 — los dos caminos toman el FOR UPDATE sobre la misma fila primero, o sea contencion y no deadlock; y lock_timeout no existe en backend/app ni database/, con default 0 = esperar para siempre.
  - Files: backend/app/core/config.py, backend/app/services/evento_partido.py, backend/app/exceptions/handlers.py, backend/tests/
- [ ] **E3 (P1, human: ~1 h / CC: ~10 min)** — frontend — Eliminar X-Reintentable y discriminar el 409 por error.detail antes de traducir
  - Surfaced by: Seccion 1 / E3 — el interceptor onResponse (client.ts:44-56) es global y los ~40 call sites de MesaPanel desestructuran {data,error} descartando response, asi que un header por call site es inalcanzable.
  - Files: backend/app/exceptions/handlers.py, frontend/src/components/MesaPanel.tsx
- [ ] **E4 (P1, human: ~2 h / CC: ~15 min)** — backend — anular toma el lock del partido cuando el evento objetivo es una tarjeta
  - Surfaced by: Seccion 1 / E4 — procesar_doble_amarilla cuenta con estado=Registrado y anular hace save_changes(evento, estado=Anulado) sobre esa misma columna con get_or_404 sin lock (evento_partido.py:190-192).
  - Files: backend/app/services/evento_partido.py
- [ ] **E5 (P1, human: ~2 h / CC: ~15 min)** — tests — Test de regresion: nada persiste a mitad si el request falla despues del insert
  - Surfaced by: Seccion 3 / REGLA DE HIERRO — A1 cambia comportamiento existente: hoy repo.create() commitea (base.py:43-48) y un fallo posterior deja el evento escrito.
  - Files: backend/tests/test_eventos_partido.py
- [ ] **E6 (P2, human: ~1 h / CC: ~10 min)** — backend — Rollback previo al reintento y recalculo completo del read-validate-insert
  - Surfaced by: Seccion 2 / E7 — SQLAlchemy deja la sesion en pending-rollback tras un error DBAPI, y el minuto sale de calcular_minuto_actual(datetime.now()) asi que reusarlo escribe un minuto viejo que chk_eventos_partido_minuto no atrapa.
  - Files: backend/app/services/evento_partido.py
- [ ] **E7 (P2, human: ~1 h / CC: ~10 min)** — tests — Test del invariante real: la roja automatica cae en la misma transaccion que la 2a amarilla
  - Surfaced by: Seccion 3 — dos amarillas producen una roja ya pasa hoy en el caso secuencial, asi que no prueba lo que A1 compra.
  - Files: backend/tests/test_eventos_partido.py
- [ ] **E8 (P2, human: ~30 min / CC: ~5 min)** — tests — Mover el guard de nombre de base al principio de _recreate_test_database
  - Surfaced by: Seccion 3 / E12 — pg_terminate_backend corre en conftest.py:71 y el DROP en la 75, asi que un nombre mal apuntado mata las conexiones a torneos_mvp antes de llegar al DROP guardado.
  - Files: backend/tests/conftest.py
- [ ] **E9 (P2, human: ~1 h / CC: ~10 min)** — frontend — Rutear el 409 por el mecanismo de evento pendiente que ya existe
  - Surfaced by: Seccion 2 / E8 — MesaPanel.tsx:377 ya tiene una recuperacion de evento pendiente; el plan agregaba una segunda sin decir como componen.
  - Files: frontend/src/components/MesaPanel.tsx
- [ ] **E10 (P2, human: ~2 h / CC: ~15 min)** — tests — Test automatizado companero del gate de C2a
  - Surfaced by: Seccion 2 / E10 — el gate de C2a es solo manual y el invariante de cuenta de tests de Fase 1 se queda sin contra que contar.
  - Files: frontend/src/components/MesaPanel.test.tsx
- [ ] **E11 (P2, human: ~1 h / CC: ~10 min)** — backend — Izar los lookups de catalogo por encima del lock y medir el p95 de POST /eventos-partido
  - Surfaced by: Seccion 4 / E5 — A1 sostiene ~6 round trips bajo un lock donde hoy hay cero, y puede encolarse detras de un batch completo de registrar_resultado_directo. Decision de taste T-5.
  - Files: backend/app/services/evento_partido.py
- [ ] **E12 (P2, human: ~30 min / CC: ~5 min)** — tests — Test HTTP del 409 con la fixture client, que A3 no puede cubrir
  - Surfaced by: Seccion 2 / E6 — la fixture client (conftest.py:127-145) sobreescribe get_db con la db_session compartida, asi que A3 llama servicios directo y no cubre verificar_arbitro_asignado, require_roles ni el mapeo a 409.
  - Files: backend/tests/test_eventos_partido.py
- [ ] **E13 (P2, human: ~2 h / CC: ~20 min)** — plan — Aplicar las correcciones al cuerpo del plan antes de arrancar la ejecucion
  - Surfaced by: Seccion 2 / E9 — cuatro contradicciones vivas entre cuerpo y correcciones; el grafo de dependencias del cuerpo instruye a empezar trabajo diferido.
  - Files: docs/plans/cierre-pendientes-todos-plan.md
- [ ] **E14 (P3, human: ~30 min / CC: ~5 min)** — tests — Probar --strict-markers con collect-only antes de comprometerse
  - Surfaced by: Seccion 3 / E11 — convierte un aviso en fallo duro sobre 49 archivos de test que nunca se chequearon.
  - Files: backend/pytest.ini
- [ ] **E15 (P3, human: ~15 min / CC: ~3 min)** — plan — Declarar la verificacion de D1 como visual y manual, con los tres puntos a mirar
  - Surfaced by: Seccion 3 / E17 — JSDOM no prueba grid areas, sticky ni 44px, y sticky falla en silencio bajo un ancestro con overflow.
  - Files: docs/plans/cierre-pendientes-todos-plan.md
- [ ] **E16 (P3, human: ~15 min / CC: ~3 min)** — plan — Separar el lane backend de A1 del lane que reorganiza MesaPanel
  - Surfaced by: Paralelizacion — A1 tocaria client.ts y MesaPanel.tsx, y D1 reorganiza MesaPanel entero: los lanes A y B chocan en ese archivo.
  - Files: docs/plans/cierre-pendientes-todos-plan.md

### Tareas de implementación — agregadas de las 4 fases

Generadas el 2026-09-18 a partir de los JSONL por fase. **59 tareas: 18 P1, 27 P2,
14 P3.** Copia suelta en `~/.gstack/projects/Score-App/aggregated-tasks-latest.md`.

**Advertencia:** cuatro tareas P1 de fases tempranas quedaron obsoletas porque fases
posteriores las supersedieron, y sus JSONL no lo saben. `T2` y `T3` de ceo-review (el
row-lock simple y el test de deadlock) los reemplaza `E2`; `T3` de devex-review
(`X-Reintentable`) lo reemplaza `E3`; `T5` de ceo-review (guard antes del TRUNCATE) lo
refina `E8`; `T8` de ceo-review (test de `sinConvocatoria`) lo reemplaza `D1`. **Manda el
bloque de obligaciones del `Implementation plan`, no esta lista.**

- [ ] **T1 (P1, human: ~10min / CC: ~2min) — baseline** — Commitear el baseline ReglamentoTorneo antes de tocar nada
  - Surfaced by: ceo-review — Step 0 / subagente hallazgo 1 - motor de reglas untracked con 520 tests verdes, un git clean lo borra
  - Files: backend/app/services/reglamento_torneo.py, backend/tests/test_reglamento_torneo.py
- [ ] **T2 (P1, human: ~15min / CC: ~3min) — backend** — Row-lock en EventoPartidoService.create via get_or_404_bloqueado
  - Surfaced by: ceo-review — Seccion 4 - dos amarillas concurrentes dejan al jugador sin roja automatica
  - Files: backend/app/services/evento_partido.py
- [ ] **T3 (P1, human: ~1h / CC: ~10min) — backend** — Rescatar DeadlockDetected con reintento unico y mensaje accionable
  - Surfaced by: ceo-review — Seccion 2 hallazgo 2.1 - segundo locker sobre PARTIDOS, hoy el deadlock sale 500
  - Files: backend/app/services/evento_partido.py, backend/app/exceptions/handlers.py
- [ ] **T5 (P1, human: ~30min / CC: ~5min) — tests** — Guard de current_database contra patron test-only antes de cualquier TRUNCATE
  - Surfaced by: ceo-review — Seccion 3 hallazgo 3.1 - torneos_mvp y torneos_mvp_test a una letra de distancia
  - Files: backend/tests/conftest.py
- [ ] **T8 (P1, human: ~1h / CC: ~10min) — frontend** — Test de ModalSustitucion con sinConvocatoria=true ANTES de retirar el camino viejo
  - Surfaced by: ceo-review — Seccion 4 hallazgo 4.1 - sin el, un partido sin convocatoria queda sin camino para Cambio
  - Files: frontend/src/components/ModalSustitucion.tsx, frontend/src/components/MesaPanel.test.tsx
- [ ] **D1 (P1, human: ~4h / CC: ~30min) — frontend** — C2a: punto de entrada de sustitucion sin convocatoria (lista cae a plantilla completa con caption)
  - Surfaced by: design-review — Pass 2 hallazgo 2.3 CRITICO - ModalSustitucion es inalcanzable sin convocatoria; C2 borraria la unica via
  - Files: frontend/src/components/MesaPanel.tsx
- [ ] **D2 (P1, human: ~1h / CC: ~10min) — frontend** — Accion primaria en el empty state de ModalSustitucion hacia Convocatoria
  - Surfaced by: design-review — Pass 2 hallazgo 2.2 CRITICO - instruccion sin navegacion; terminal despues de C2b
  - Files: frontend/src/components/ModalSustitucion.tsx
- [ ] **D3 (P1, human: ~2h / CC: ~15min) — frontend** — Confirmacion aria-live del evento cargado, anclada en la zona del gesto
  - Surfaced by: design-review — Pass 2 hallazgo 2.1 CRITICO - 0 aria-live en MesaPanel; sin acuse el mesero toca de nuevo y genera el doble-submit
  - Files: frontend/src/components/MesaPanel.tsx
- [ ] **D4 (P1, human: ~1h / CC: ~10min) — frontend** — Zona primaria sticky a 375px
  - Surfaced by: design-review — Pass 1 hallazgo 1.3 CRITICO - 3 zonas que colapsan a 1 columna no cambian nada para el caso principal
  - Files: frontend/src/index.css, frontend/src/components/MesaPanel.tsx
- [ ] **E1 (P1, human: ~4 h / CC: ~30 min) — tests** — Dar a A2 su propia base torneos_mvp_test_concurrencia con scope de modulo
  - Surfaced by: eng-review — Seccion 1 / E1 — _test_db_ready es scope=session (conftest.py:89) y 05_seed.sql siembra 14 tablas; un TRUNCATE CASCADE con commits reales no lo revierte el savepoint y deja la suite fallando segun el orden de pytest.
  - Files: backend/tests/conftest.py
- [ ] **E2 (P1, human: ~3 h / CC: ~25 min) — backend** — Fijar lock_timeout desde Settings y reemplazar el test de deadlock por uno de contencion
  - Surfaced by: eng-review — Seccion 1 / E2 — los dos caminos toman el FOR UPDATE sobre la misma fila primero, o sea contencion y no deadlock; y lock_timeout no existe en backend/app ni database/, con default 0 = esperar para siempre.
  - Files: backend/app/core/config.py, backend/app/services/evento_partido.py, backend/app/exceptions/handlers.py, backend/tests/
- [ ] **E3 (P1, human: ~1 h / CC: ~10 min) — frontend** — Eliminar X-Reintentable y discriminar el 409 por error.detail antes de traducir
  - Surfaced by: eng-review — Seccion 1 / E3 — el interceptor onResponse (client.ts:44-56) es global y los ~40 call sites de MesaPanel desestructuran {data,error} descartando response, asi que un header por call site es inalcanzable.
  - Files: backend/app/exceptions/handlers.py, frontend/src/components/MesaPanel.tsx
- [ ] **E4 (P1, human: ~2 h / CC: ~15 min) — backend** — anular toma el lock del partido cuando el evento objetivo es una tarjeta
  - Surfaced by: eng-review — Seccion 1 / E4 — procesar_doble_amarilla cuenta con estado=Registrado y anular hace save_changes(evento, estado=Anulado) sobre esa misma columna con get_or_404 sin lock (evento_partido.py:190-192).
  - Files: backend/app/services/evento_partido.py
- [ ] **E5 (P1, human: ~2 h / CC: ~15 min) — tests** — Test de regresion: nada persiste a mitad si el request falla despues del insert
  - Surfaced by: eng-review — Seccion 3 / REGLA DE HIERRO — A1 cambia comportamiento existente: hoy repo.create() commitea (base.py:43-48) y un fallo posterior deja el evento escrito.
  - Files: backend/tests/test_eventos_partido.py
- [ ] **T1 (P1, human: ~10 min / CC: ~2 min) — frontend** — Agregar frontend/.env.example con VITE_API_BASE_URL
  - Surfaced by: devex-review — Pass 1 / DX-1 — client.ts:4 lee VITE_API_BASE_URL sin default y AuthContext.tsx:72 la interpola en el fetch del login; .gitignore:14-15 ignora .env. En un clon limpio el login POSTea a undefined/api/v1/auth/login.
  - Files: frontend/.env.example
- [ ] **T2 (P1, human: ~2 h / CC: ~20 min) — plan** — Tabla de estado por fase al inicio del plan y reescritura de A0/A1/B2 en el cuerpo
  - Surfaced by: devex-review — Pass 4 / F-3 — el orden serial omite B1, B2, E1 y F1 sin decirlo mientras el grafo de dependencias los presenta como en alcance; el cuerpo de A1 dice que el swap a get_or_404_bloqueado alcanza, y la corrección 380 lineas despues dice que no cierra la carrera.
  - Files: docs/plans/cierre-pendientes-todos-plan.md
- [ ] **T3 (P1, human: ~3 h / CC: ~25 min) — backend** — ConcurrencyConflictError a 409 con header X-Reintentable y codigo estable en CODIGOS_ERROR_TRADUCIDOS
  - Surfaced by: devex-review — Pass 3 / F-7 — DomainRuleError mapea a 400 (handlers.py:50-52), misma forma y clase que un rechazo de validacion permanente; el unico discriminador seria substring-match sobre prosa en espanol, que es lo que CODIGOS_ERROR_TRADUCIDOS (client.ts:73-86) existe para evitar.
  - Files: backend/app/exceptions/errors.py, backend/app/exceptions/handlers.py, frontend/src/api/client.ts
- [ ] **T4 (P1, human: ~1 h / CC: ~10 min) — tests** — Registrar marca concurrencia en pytest.ini con --strict-markers y filtrarla en verificar.ps1
  - Surfaced by: devex-review — Pass 6 / F-1 — pytest.ini no tiene bloque markers ni addopts, y verificar.ps1:46 corre pytest -q sin filtro, asi que los tests de A3 con commits reales y TRUNCATE entran en la corrida por defecto del unico gate del repo.
  - Files: backend/pytest.ini, verificar.ps1, backend/README.md
- [ ] **T4 (P2, human: ~20min / CC: ~5min) — backend** — Log estructurado cuando la espera del FOR UPDATE supera umbral
  - Surfaced by: ceo-review — Seccion 8 hallazgo 8.1 - un lock que espera no deja rastro
  - Files: backend/app/services/evento_partido.py
- [ ] **T6 (P2, human: ~4h / CC: ~30min) — tests** — Fixture sesiones_paralelas con dos AsyncSession y commit real
  - Surfaced by: ceo-review — Seccion 6 hallazgo 6.2 - el modelo de savepoints impide tests de 2 conexiones
  - Files: backend/tests/conftest.py
- [ ] **T7 (P2, human: ~3h / CC: ~25min) — tests** — Tests de concurrencia T23/T24 + doble amarilla
  - Surfaced by: ceo-review — Seccion 6 - T23/T24 anotados como pendientes de infraestructura en test_fin_forzado.py:7-8
  - Files: backend/tests/test_fin_forzado.py, backend/tests/test_convocados.py
- [ ] **T9 (P2, human: ~2h / CC: ~15min) — frontend** — Retirar la rama Cambio de CargaEvento y migrar sus tests
  - Surfaced by: ceo-review — Seccion 6 hallazgo 6.1 - la cuenta de tests de Cambio no puede bajar
  - Files: frontend/src/components/MesaPanel.tsx, frontend/src/components/MesaPanel.test.tsx
- [ ] **T10 (P2, human: ~1h30 / CC: ~12min) — frontend** — Crear DetalleEquipo.test.tsx antes de refactorizar
  - Surfaced by: ceo-review — Seccion 6 - DetalleEquipo no tiene test propio hoy
  - Files: frontend/src/pages/torneo-admin/DetalleEquipo.test.tsx
- [ ] **T11 (P2, human: ~2h / CC: ~15min) — frontend** — Migrar el modal inline de DetalleEquipo a SelectorJugadorBuscable sin absorber conflicto ni alta
  - Surfaced by: ceo-review — Seccion 5 hallazgo 5.3 - 6 props opcionales convierten compartido en configurable
  - Files: frontend/src/pages/torneo-admin/DetalleEquipo.tsx, frontend/src/components/admin/SelectorJugadorBuscable.tsx
- [ ] **T12 (P2, human: ~3h / CC: ~25min) — frontend** — Panel en 3 zonas con grid-template-areas reusando los breakpoints existentes
  - Surfaced by: ceo-review — Seccion 11 - el marcador queda fuera de pantalla en 375px
  - Files: frontend/src/index.css, frontend/src/components/MesaPanel.tsx
- [ ] **D5 (P2, human: ~1h30 / CC: ~12min) — frontend** — Error de deadlock con tratamiento distinto y boton Reintentar
  - Surfaced by: design-review — Pass 2 hallazgo 2.4 - el unico error transitorio se veria igual que un rechazo permanente
  - Files: frontend/src/components/MesaPanel.tsx, frontend/src/components/ModalSustitucion.tsx
- [ ] **D6 (P2, human: ~1h / CC: ~10min) — frontend** — Badge de tarjetas con texto y forma (1A/2A/R), no solo color
  - Surfaced by: design-review — Pass 6 hallazgo 6.3 - color solo falla para daltonismo bajo sol directo
  - Files: frontend/src/components/eventos.ts, frontend/src/components/MesaPanel.tsx
- [ ] **D7 (P2, human: ~30min / CC: ~5min) — frontend** — Fijar 1000px como unico breakpoint de activacion, mobile-first, y verificar 640-799px
  - Surfaced by: design-review — Pass 5 hallazgo 5.1 - index.css mezcla min/max-width; la verificacion de Fase 1 pasaba rompiendo ese rango
  - Files: frontend/src/index.css
- [ ] **D8 (P2, human: ~1h / CC: ~10min) — frontend** — Targets de 44px en zonas 1 y 2, incluido Sacar; contraste de cuerpo 4.5:1
  - Surfaced by: design-review — Pass 6 hallazgo 6.2 - Sacar es .link-button, un link de texto como target tactil a 375px
  - Files: frontend/src/index.css, frontend/src/components/MesaPanel.tsx
- [ ] **D9 (P2, human: ~30min / CC: ~5min) — frontend** — Especificar la secuencia buscar-conflicto-confirmar de C1 (dos paneles en un modal)
  - Surfaced by: design-review — Pass 7 hallazgo 7.1 - tres secuencias posibles, ninguna elegida
  - Files: frontend/src/pages/torneo-admin/DetalleEquipo.tsx
- [ ] **E6 (P2, human: ~1 h / CC: ~10 min) — backend** — Rollback previo al reintento y recalculo completo del read-validate-insert
  - Surfaced by: eng-review — Seccion 2 / E7 — SQLAlchemy deja la sesion en pending-rollback tras un error DBAPI, y el minuto sale de calcular_minuto_actual(datetime.now()) asi que reusarlo escribe un minuto viejo que chk_eventos_partido_minuto no atrapa.
  - Files: backend/app/services/evento_partido.py
- [ ] **E7 (P2, human: ~1 h / CC: ~10 min) — tests** — Test del invariante real: la roja automatica cae en la misma transaccion que la 2a amarilla
  - Surfaced by: eng-review — Seccion 3 — dos amarillas producen una roja ya pasa hoy en el caso secuencial, asi que no prueba lo que A1 compra.
  - Files: backend/tests/test_eventos_partido.py
- [ ] **E8 (P2, human: ~30 min / CC: ~5 min) — tests** — Mover el guard de nombre de base al principio de _recreate_test_database
  - Surfaced by: eng-review — Seccion 3 / E12 — pg_terminate_backend corre en conftest.py:71 y el DROP en la 75, asi que un nombre mal apuntado mata las conexiones a torneos_mvp antes de llegar al DROP guardado.
  - Files: backend/tests/conftest.py
- [ ] **E9 (P2, human: ~1 h / CC: ~10 min) — frontend** — Rutear el 409 por el mecanismo de evento pendiente que ya existe
  - Surfaced by: eng-review — Seccion 2 / E8 — MesaPanel.tsx:377 ya tiene una recuperacion de evento pendiente; el plan agregaba una segunda sin decir como componen.
  - Files: frontend/src/components/MesaPanel.tsx
- [ ] **E10 (P2, human: ~2 h / CC: ~15 min) — tests** — Test automatizado companero del gate de C2a
  - Surfaced by: eng-review — Seccion 2 / E10 — el gate de C2a es solo manual y el invariante de cuenta de tests de Fase 1 se queda sin contra que contar.
  - Files: frontend/src/components/MesaPanel.test.tsx
- [ ] **E11 (P2, human: ~1 h / CC: ~10 min) — backend** — Izar los lookups de catalogo por encima del lock y medir el p95 de POST /eventos-partido
  - Surfaced by: eng-review — Seccion 4 / E5 — A1 sostiene ~6 round trips bajo un lock donde hoy hay cero, y puede encolarse detras de un batch completo de registrar_resultado_directo. Decision de taste T-5.
  - Files: backend/app/services/evento_partido.py
- [ ] **E12 (P2, human: ~30 min / CC: ~5 min) — tests** — Test HTTP del 409 con la fixture client, que A3 no puede cubrir
  - Surfaced by: eng-review — Seccion 2 / E6 — la fixture client (conftest.py:127-145) sobreescribe get_db con la db_session compartida, asi que A3 llama servicios directo y no cubre verificar_arbitro_asignado, require_roles ni el mapeo a 409.
  - Files: backend/tests/test_eventos_partido.py
- [ ] **E13 (P2, human: ~2 h / CC: ~20 min) — plan** — Aplicar las correcciones al cuerpo del plan antes de arrancar la ejecucion
  - Surfaced by: eng-review — Seccion 2 / E9 — cuatro contradicciones vivas entre cuerpo y correcciones; el grafo de dependencias del cuerpo instruye a empezar trabajo diferido.
  - Files: docs/plans/cierre-pendientes-todos-plan.md
- [ ] **T5 (P2, human: ~4 h / CC: ~30 min) — infra** — Extender docker-compose con Postgres y carga de database/01-06, y nombrarlo en Levantar todo
  - Surfaced by: devex-review — Pass 1 / DX-2 — el compose ya levanta la API pero asume Postgres en el host con torneos_mvp cargado, que es la suposicion que rompe a la segunda persona que clone. TTHW medido ~25 min contra un tier objetivo de 2-5.
  - Files: infrastructure/docker-compose.yml, README.md
- [ ] **T6 (P2, human: ~2 h / CC: ~15 min) — tests** — Documentar los dos harness de test en conftest.py y agregar un test de concurrencia copiable a backend/README
  - Surfaced by: devex-review — Pass 4 / H2 — el docstring de conftest.py ensena que un session.commit() de repositorio no persiste nada, y la fixture de A2 invierte exactamente eso.
  - Files: backend/tests/conftest.py, backend/README.md
- [ ] **T7 (P2, human: ~1 h / CC: ~10 min) — plan** — Escribir la seccion Copy de errores del plan con una fila por error nuevo
  - Surfaced by: devex-review — Pass 3 / F-8 — el plan especifica copy para uno solo de sus errores; quedan sin definir cursor invalido, fila con estado cambiado, timeout de test de A2, alcance invalido y el 403 de F1.
  - Files: docs/plans/cierre-pendientes-todos-plan.md
- [ ] **T8 (P2, human: ~1 h / CC: ~8 min) — backend** — Mover umbral de espera y conteo de reintentos de A1 a Settings y nombrar el logger
  - Surfaced by: devex-review — Pass 3 / F-6 — reintento unico y umbral de log especificados como literales; config.py ya lee .env con pydantic-settings.
  - Files: backend/app/core/config.py, backend/app/services/evento_partido.py
- [ ] **T9 (P2, human: ~30 min / CC: ~5 min) — docs** — Crear docs/queries/README.md y agregar la fila en la tabla del README raiz
  - Surfaced by: devex-review — Pass 4 / F-12 — docs/queries tiene un solo .sql, ningun README, y grepear queries en los tres README da cero resultados: es indescubrible.
  - Files: docs/queries/README.md, README.md
- [ ] **T10 (P2, human: ~30 min / CC: ~5 min) — docs** — Escribir la guardia de tres lugares para columnas nuevas en database/README.md
  - Surfaced by: devex-review — Pass 4 / M7 — la guardia esta en el plan dos veces y en database/README.md ninguna, y es la que produce el UndefinedColumn en ~40 archivos de test.
  - Files: database/README.md
- [ ] **T11 (P2, human: ~15 min / CC: ~3 min) — docs** — Fijar por escrito la regla de nombres de parametros de query
  - Surfaced by: devex-review — Pass 2 / M5 — alcance en espanol junto a skip/limit/q en ingles; el plan suma sin fijar la regla y el proximo parametro la vuelve a litigar.
  - Files: backend/README.md
- [ ] **T13 (P3, human: ~30min / CC: ~5min) — backend** — Correr la consulta de revocacion de licencia ad hoc y registrar el numero
  - Surfaced by: ceo-review — Seccion 8 hallazgo 8.2 - AUDITORIA tiene 287 filas y CERO de usuarios
  - Files: docs/queries/metricas-revocacion-licencia.sql
- [ ] **T14 (P3, human: ~20min / CC: ~5min) — docs** — Escribir en TODOS.md el umbral numerico que desbloquea E1 y F1
  - Surfaced by: ceo-review — 0D expansion 5 - convierte diferimiento vago en disparador accionable
  - Files: TODOS.md
- [ ] **T15 (P3, human: ~15min / CC: ~3min) — docs** — Cerrar B1 en TODOS.md como no-aplica-por-modelo-de-datos con su motivo
  - Surfaced by: ceo-review — Seccion 3 hallazgo 3.2 - alcance con default permisivo no es autorizacion
  - Files: TODOS.md
- [ ] **D10 (P3, human: ~20min / CC: ~5min) — docs** — Registrar en TODOS.md las restricciones de reapertura de UI para E1, F1 y B1
  - Surfaced by: design-review — Pass 7 hallazgos 7.2 y 7.4 - diferir sin registrar la UI faltante pierde el hallazgo
  - Files: TODOS.md
- [ ] **D11 (P3, human: ~10min / CC: ~2min) — docs** — Agendar o descartar a proposito DESIGN.md formal (6a recomendacion)
  - Surfaced by: design-review — Pass 5 - 5 recomendaciones previas no movieron nada
  - Files: TODOS.md
- [ ] **E14 (P3, human: ~30 min / CC: ~5 min) — tests** — Probar --strict-markers con collect-only antes de comprometerse
  - Surfaced by: eng-review — Seccion 3 / E11 — convierte un aviso en fallo duro sobre 49 archivos de test que nunca se chequearon.
  - Files: backend/pytest.ini
- [ ] **E15 (P3, human: ~15 min / CC: ~3 min) — plan** — Declarar la verificacion de D1 como visual y manual, con los tres puntos a mirar
  - Surfaced by: eng-review — Seccion 3 / E17 — JSDOM no prueba grid areas, sticky ni 44px, y sticky falla en silencio bajo un ancestro con overflow.
  - Files: docs/plans/cierre-pendientes-todos-plan.md
- [ ] **E16 (P3, human: ~15 min / CC: ~3 min) — plan** — Separar el lane backend de A1 del lane que reorganiza MesaPanel
  - Surfaced by: eng-review — Paralelizacion — A1 tocaria client.ts y MesaPanel.tsx, y D1 reorganiza MesaPanel entero: los lanes A y B chocan en ese archivo.
  - Files: docs/plans/cierre-pendientes-todos-plan.md
- [ ] **T12 (P3, human: ~30 min / CC: ~5 min) — plan** — Agregar el paso de regenerar schema.d.ts con gen:api a B1, E1 y F1
  - Surfaced by: devex-review — Pass 4 / F-10 — package.json:12 genera el cliente contra un backend vivo y verificar.ps1 no lo levanta, asi que el drift de contrato no lo detecta nadie.
  - Files: docs/plans/cierre-pendientes-todos-plan.md
- [ ] **T13 (P3, human: ~1 h / CC: ~10 min) — frontend** — Decidir un unico tratamiento de estado pending para todas las fases reorganizadas
  - Surfaced by: devex-review — Pass 5 / F-13 — la obligacion de Fase 2 devolvia la decision al implementador, que es el modo de fallo que las zonas FIJADAS y la secuencia del modal de C1 se agregaron para eliminar.
  - Files: frontend/src/components/MesaPanel.tsx
- [ ] **T14 (P3, human: ~15 min / CC: ~3 min) — backend** — Registrar en el docstring de BaseRepository.create que EventoPartidoService maneja su propia transaccion
  - Surfaced by: devex-review — Pass 5 / F-14 — colapsar create a una sola transaccion cambia una expectativa que cualquier llamador futuro puede dar por sentada.
  - Files: backend/app/repositories/base.py
- [ ] **T15 (P3, human: ~10 min / CC: ~2 min) — docs** — Preservar la trampa de casing de AUDITORIA.Tabla en el criterio de reapertura de B2
  - Surfaced by: devex-review — Pass 4 / F-11 — auditoria.py:111,119,137,163,178,193 usan obj.__tablename__, asi que Tabla='USUARIOS' da cero por casing y no por falta de datos.
  - Files: TODOS.md
- [ ] **T16 (P3, human: ~45 min / CC: ~8 min) — backend** — Agregar URL de ejemplo ejecutable al docstring de cada ruta nueva o modificada
  - Surfaced by: devex-review — Pass 4 / M4 — cero ejemplos copiables para la superficie nueva; el precedente del repo es routes/partidos.py:92.
  - Files: backend/app/api/routes/
- [ ] **T17 (P3, human: ~20 min / CC: ~5 min) — backend** — Testear por contenido el mensaje del 403 de F1
  - Surfaced by: devex-review — Pass 3 / M8 — RequireRole ya esconde los botones, asi que un 403 real significa token viejo o cambio de rol; deps.py:132-134 da problema y causa pero no arreglo.
  - Files: backend/tests/

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` (via /autoplan) | Scope & strategy | 1 | issues_open | SELECTIVE EXPANSION, 2 iteraciones de spec review (6/10 → 8/10), 7 gaps críticos activos, 20 obligaciones |
| Outside Review | codex (no ejecutado) | Independent 2nd opinion | 0 | unavailable | `CODEX_MODE: not_installed` en las 4 fases; sin cobertura externa |
| Eng Review | `/plan-eng-review` (via /autoplan) | Architecture & tests (required) | 1 | issues_open | 28 issues, 9 gaps críticos (4 P0), 1 regresión obligatoria, Lake Score 6/6 |
| Design Review | `/plan-design-review` (via /autoplan) | UI/UX gaps | 1 | clean | score: 2/10 → 7/10, 13 decisiones, 15 obligaciones |
| DX Review | `/plan-devex-review` (via /autoplan) | Developer experience gaps | 1 | issues_open | score: 2/10 → 6/10, TTHW: ~25 min → ≤5 min |

- **OUTSIDE COVERAGE:** codex `unavailable` (`not_installed`) en las cuatro fases — ceo, design, dx y eng. Ninguna fase tuvo cobertura externa completada. El fallback fue un subagente de Claude: contexto fresco, mismo harness, identidad de modelo desconocida. Consenso 0/6 en ceo, 0/7 en design, 0/6 en dx y 0/6 en eng: todo hallazgo de esta corrida es de una sola voz. Se aceptaron por verificación directa contra el código, no por acuerdo entre modelos. Un fallback nativo NO constituye cobertura externa.
- **VERDICT:** CEO + DESIGN + DX + ENG revisados y aprobados por el usuario en el Gate Final del 2026-09-18. Las obligaciones de las cuatro fases están aplicadas al `Implementation plan` (líneas 522-613). Los 4 bloqueantes P0 de Eng tienen arreglo escrito y verificado, pero **no implementado**: el plan está listo para ejecutar, no ejecutado. Los 3 desafíos a la dirección del usuario (diferir E1, diferir F1, matar B1) fueron RECHAZADOS: E1, F1 y B1 siguen en alcance tal como el usuario los tenía.

NO UNRESOLVED DECISIONS
