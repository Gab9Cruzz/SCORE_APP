# Plan: Roles y 3 módulos (Admin General / Torneo Admin / Árbitro)

Generado por /office-hours (dentro de /gstack-autoplan) el 2026-08-26
Branch: main | Repo: Gab9Cruzz/SCORE_APP
Estado: DRAFT — fases para revisar y construir una por una. Este documento
todavía no pasó por el pipeline completo de revisión (/autoplan CEO+Design+
Eng+DX); eso se corre fase por fase cuando se retome cada una.

## Por qué existe este documento

Hoy el sistema tiene 3 roles planos (`Admin`, `Arbitro`, `Publico`, ver
`chk_usuarios_rol` en `database/02_constraints.sql`). El pedido es
reestructurarlo en 3 módulos con permisos reales:

1. **Torneo Admin** — crea y administra torneos, partidos, equipos, etc.
2. **Árbitro** — solo ve los partidos que tiene asignados; carga goles,
   tarjetas y cambios de esos partidos.
3. **Admin General** — todo lo anterior, más crear/eliminar usuarios.

Esto es un cambio de modelo de datos (roles + asignación árbitro↔partido),
no solo de frontend. Por eso se fasea en vez de construirse de una vez.

**Diseño visual queda fuera de estas fases** (confirmado por el usuario) —
cuando llegue el momento de pulir cada pantalla, eso es un pase de
`/design-review` aparte, no parte de este plan.

## Estado actual del frontend (confirmado en esta sesión, sin cambios de código)

- `App.tsx`: `/` redirige siempre a `/dashboard`, para cualquiera —
  autenticado o no. `/dashboard` y `/partido/:id/en-vivo` son públicos.
  `/control-de-mesa` exige rol `Admin` o `Arbitro` (`RequireRole`).
- `NavBar.tsx` ya muestra usuario + rol + logout cuando hay sesión, y
  "Iniciar sesión" cuando no la hay.
- **Decisión D1 (esta sesión):** para esta fase, Admin y Arbitro comparten
  el mismo `/dashboard` post-login — no se construye una landing distinta
  por rol todavía. El frontend actual ya cumple esto tal cual está. No hay
  trabajo pendiente de "vista al ingresar" hasta que empiece la Fase 2/3 de
  abajo (ahí sí cada módulo tiene su propia landing).

## Decisión registrada: alcance de Torneo Admin

**Decisión D2 (esta sesión):** Torneo Admin es un pool compartido — cualquier
usuario con ese rol administra cualquier torneo, no solo los que creó. Se
evaluó y se rechazó explícitamente el modelo con dueño (`creado_por` en
`TORNEO`, aislamiento entre organizadores) por ahora: cero cambio de esquema
para arrancar, más rápido de construir. Costo aceptado: si en el futuro dos
organizadores de ligas distintas comparten el mismo sistema, uno puede
modificar el torneo del otro. Revisar si eso se vuelve un problema real de
uso (candidato a `TODOS.md` si aparece).

## Fases

Cada fase se ejecuta y se revisa por separado — con `/plan-eng-review` (o
`/autoplan` si en ese momento se quiere el pipeline completo con revisión
CEO+Design+Eng+DX) apuntando a la sección correspondiente de este archivo.
No arrancar la Fase N+1 sin haber cerrado la Fase N.

### Fase 1 — Backend: modelo de roles + asignación árbitro↔partido

Es la única fase que **tiene que** ir primero: las fases 2-4 dependen de que
estos datos existan.

- Migrar `chk_usuarios_rol` de `('Admin', 'Arbitro', 'Publico')` a los 3
  roles reales (definir nombres exactos de rol en esa revisión: p. ej.
  `AdminGeneral`, `TorneoAdmin`, `Arbitro`, `Publico`). Decidir ahí si
  `Admin` existente se migra a `TorneoAdmin` o a `AdminGeneral` (dato real:
  hoy no hay forma de distinguir cuál de los dos es cada usuario `Admin`
  actual — hay que mirar los datos antes de escribir la migración).
- Nueva tabla o columna para asignación árbitro↔partido (`PARTIDOS` hoy no
  tiene ninguna columna de árbitro). Sin esto, "el árbitro solo ve sus
  partidos asignados" no es construible — es la pieza que bloquea la Fase 3.
- Endpoints de gestión de usuarios para Admin General: crear, eliminar,
  cambiar rol. Hoy `backend/app/api` no tiene un router de administración de
  usuarios (confirmar en esa revisión si existe algo parcial en
  `usuarios.py` que se pueda extender).
- `require_roles` (backend/app/core) hoy filtra por rol plano — revisar si
  alcanza con agregar los nuevos valores de rol o si Árbitro necesita un
  chequeo adicional de "¿este partido es tuyo?" a nivel de endpoint.

#### Fase 1 — Resultado de /plan-eng-review (2026-08-26)

**Corrección al punto de arriba:** `usuarios.py` YA tiene CRUD completo
(list/get/create/update/soft-delete), gateado en `require_roles("Admin")`.
No hay que construir nada nuevo ahí, solo re-gatearlo.

**Dato real de la base (`torneos_mvp`, host local, consultado en esta
revisión):** solo 2 usuarios — `admin` (Rol=`Admin`, el bootstrap del
sistema) y `arbitro1` (Rol=`Arbitro`, dato de prueba). Sin ambigüedad:
`admin` migra a `AdminGeneral`.

##### Decisiones de arquitectura (D2-D6, en orden de la revisión)

- **D2 — Alcance del cambio:** completo en un solo pase (roles + columna +
  ownership-check + tests), no partido en sub-fases. Partirlo exigiría un
  shim de compatibilidad temporal (aceptar `Admin` y los roles nuevos a la
  vez) que después hay que sacar — más trabajo total que hacerlo atómico.
- **D3 (Architecture-1) — Acceso de AdminGeneral:** bypass centralizado
  dentro de `require_roles()` (`backend/app/api/deps.py`) — si
  `usuario.rol == "AdminGeneral"`, pasa sin mirar la lista de roles pedida.
  8 de los 9 routers hacen un swap mecánico `Admin` → `TorneoAdmin`. **Una
  sola excepción, confirmada tras el hallazgo de la voz externa:**
  `usuarios.py` va a `require_roles("AdminGeneral")` literal, no al swap
  uniforme — si se le aplicara el swap, TorneoAdmin heredaría gestión de
  usuarios, incluyendo auto-escalarse a AdminGeneral vía
  `PATCH /usuarios/{id}`. Esto rompía el límite de módulos que el plan
  existe para construir; ver "Bugs encontrados" abajo.
- **D4 (Architecture-2) — Alcance de escritura de Árbitro:** se le saca
  `POST /partidos` (crear) — pasa a ser solo TorneoAdmin/AdminGeneral.
  Árbitro conserva `PATCH /partidos/{id}` (para avanzar el estado de SU
  partido) y `POST` / `.../anular` en `/eventos-partido`, los tres con el
  ownership-check nuevo. Verificado: el frontend (`ControlDeMesa.tsx`)
  nunca llama `POST /partidos`, así que no rompe nada existente.
- **D5 (Architecture-3) — Dónde vive el ownership-check:** en el Service
  (`PartidoService.update`, `EventoPartidoService.create`/`anular`), que
  recibe el `Usuario` autenticado. Corrección de la voz externa a la
  justificación original: solo `anular()` reusa una carga que ya existe;
  `create()` y `update()` necesitan una consulta nueva igual. No cambia la
  decisión, pero como es el único chequeo de permiso imperativo del código
  (el resto es declarativo vía `dependencies=[Depends(require_roles(...))]`
  en el router), cada endpoint que dependa de esto lleva un comentario en
  la ruta señalando dónde vive el chequeo real (ver Implementation Tasks).
- **D6 (Architecture-4) — Forma del dato de asignación:** columna
  `arbitro_id` nullable en `PARTIDOS` (FK a `usuarios.id`), mismo patrón que
  `equipos_id_local`/`equipos_id_visitante`. Un árbitro por partido — sin
  evidencia de que haga falta más de uno (fútbol amateur chico). Se agrega
  a `PartidoUpdate`/`PartidoOut`, no a `PartidoCreate`: la asignación es un
  paso separado de la creación del partido.
- **D7 (Architecture-5) — Estrategia de migración:** no hay Alembic, son
  archivos SQL numerados, y `torneos_mvp` ya tiene datos reales (no se
  recrea desde cero). `database/07_migracion_roles_arbitro.sql` nuevo con
  los `ALTER TABLE` reales, corre una vez contra la base viva. En paralelo,
  `01_schema.sql`/`02_constraints.sql` se actualizan para que un entorno
  nuevo nazca correcto. Riesgo de drift entre ambos caminos (correctamente
  flageado por la voz externa): `backend/tests/conftest.py` reconstruye la
  base de test solo con `01`-`06` (nunca corre `07`), así que nada prueba
  automáticamente que `07` produce el mismo estado final que `01`/`02` —
  mitigación: verificación manual de una sola vez con
  `pg_dump --schema-only` (ver Implementation Tasks T17).
- **TODO decidido — auto-lockout de AdminGeneral:** `UsuarioService` hoy no
  impide que un AdminGeneral se desactive o se cambie el rol a sí mismo.
  Bug preexistente, no introducido por esta fase, pero se construye AHORA
  (dentro de Fase 1) porque `usuarios.py`/`UsuarioService` ya se están
  tocando — evita una segunda vuelta al mismo archivo (T6).
- **Frontend — hallazgo propio, fuera de lo que cubrió Arquitectura o la
  voz externa:** `RequireRole` (`frontend/src/components/RequireRole.tsx`)
  hace match literal de string contra `session.rol`, y
  `App.tsx:21` tiene `roles={["Admin", "Arbitro"]}`. Después del rename,
  el login devuelve `rol: "TorneoAdmin"` (o `"AdminGeneral"`) en vez de
  `"Admin"` — el usuario que hoy es Admin queda bloqueado de
  `/control-de-mesa` aunque el backend lo siga autorizando. Aunque el
  título de la fase dice "Backend", se corrige ahora (T19): son 2 líneas
  (el `Rol` type + el array de `roles`), cero trabajo de diseño/UI nueva,
  evita dejar el sistema inutilizable entre el deploy de Fase 1 y Fase 2/3.

##### Bugs encontrados por la voz externa (Claude subagente — Codex no
estaba instalado en esta sesión)

1. **Crítico, ya corregido en D3 arriba:** el swap uniforme `Admin` →
   `TorneoAdmin` aplicado sin excepción a `usuarios.py` habría permitido
   auto-escalación de privilegios (TorneoAdmin → AdminGeneral).
2. `UsuarioService.bootstrap_admin_si_no_existe`
   (`backend/app/services/usuario.py:50`) hardcodea `rol="Admin"` — sin
   fix, rompe el CHECK constraint nuevo en el primer arranque de cualquier
   entorno limpio (T6).
3. `RolUsuario` (`backend/app/schemas/usuario.py:6`) sigue en 3 valores —
   sin actualizar, cualquier respuesta con un usuario de rol nuevo falla
   la validación de Pydantic (500 en vez de funcionar) (T4).
4. Conteo real de call sites de `require_roles("Admin"...)`: 23, no 24
   (dato menor, no cambia el plan).

Todo lo demás (ownership-check en el Service, columna vs tabla, sacarle
`POST /partidos` a Árbitro, D2 pool compartido) lo validó sin objeciones —
"no fundamentally simpler architecture is being missed."

##### Diagrama — flujo de permisos (nuevo, post Fase 1)

```
Request
  │
  ▼
get_current_user            (JWT → sub → lookup DB, rol SIEMPRE fresco,
  │                           nunca del claim del token)
  ▼
require_roles("X","Y")      (FastAPI dependency, declarativo, visible en
  │                           el decorator de la ruta)
  │
  ├─ usuario.rol == "AdminGeneral"? ──── sí ──▶ PASS (bypass, D3)
  │
  ├─ usuario.rol in ("X","Y")? ────────── sí ──▶ PASS
  │
  └─ no ──▶ 403 ForbiddenError (mensaje: "requiere rol X o Y")

  ▼ (si pasó)
Route handler ──▶ Service method
                     │
                     ├─ usuario.rol == "Arbitro"?
                     │     │
                     │     ├─ sí ─▶ carga Partido, compara
                     │     │        partido.arbitro_id == usuario.id
                     │     │           │
                     │     │           ├─ match ────▶ PASS
                     │     │           └─ mismatch ─▶ 403 ForbiddenError
                     │     │              ("este partido no está asignado
                     │     │               a vos")
                     │     │
                     │     └─ no (TorneoAdmin/AdminGeneral) ─▶ PASS, sin
                     │                                          chequeo
                     ▼
                  mutación real (repo.create / repo.update)
```

Este es el único chequeo de permiso **imperativo** del código — todo lo
demás es declarativo vía `Depends(require_roles(...))` en el router. Cada
endpoint que lo dispare (`PATCH /partidos/{id}`,
`POST /eventos-partido`, `POST /eventos-partido/{id}/anular`) lleva un
comentario en la ruta señalándolo, para que quede visible sin tener que
abrir el Service (hallazgo de la voz externa).

##### NOT in scope (Fase 1)

- Landing/UI por rol (Fase 2/3), selector "entrar como" de AdminGeneral
  (Fase 4, todavía sin decidir cómo resuelve el routing) — confirmado
  fuera desde el plan original.
- Tabla de unión para múltiples árbitros por partido (asistentes) —
  rechazada en D6 por falta de evidencia; si aparece la necesidad, es
  candidato a TODOS.md igual que D2.
- Auditoría de qué endpoints deberían requerir autenticación en GET (hoy
  `GET /partidos` y `GET /eventos-partido` son públicos a propósito, sin
  cambios — corresponde a Fase 3 cuando exista "Mis partidos").
- Verificar si existe una base de datos de producción/staging separada de
  `torneos_mvp` con más filas `Admin` que la muestra de 2 usuarios vista
  acá — no hay evidencia de que exista, pero si aparece, la migración de
  datos (`UPDATE ... SET Rol='AdminGeneral'`) necesita revisarse fila por
  fila, no asumir que generaliza.

##### What already exists (reusado, no reconstruido)

- CRUD completo de usuarios (`usuarios.py` + `UsuarioService` +
  `UsuarioRepository`) — reutilizado tal cual, solo cambia el gate.
- `require_roles` genérico (`deps.py`) — extendido con el bypass, no
  reescrito.
- Patrón de columnas FK directas en `PARTIDOS`
  (`equipos_id_local`/`equipos_id_visitante`) — `arbitro_id` sigue el
  mismo patrón en vez de inventar uno nuevo.
- Patrón de borrado lógico (`Estado='Inactivo'`) ya usado en toda la app —
  el guard de auto-lockout no inventa un mecanismo nuevo, solo agrega una
  condición antes del soft-delete/update existente.

##### Failure modes

| Codepath | Falla realista | Test | Manejo de error | Visible o silenciosa |
|---|---|---|---|---|
| Ownership-check, `arbitro_id` NULL (partido nunca asignado) | Árbitro intenta cargar un evento en un partido sin asignar | Nueva (fixture "no asignado") | `ForbiddenError` 403 | Visible, mensaje claro |
| `07_migracion_roles_arbitro.sql` corrido dos veces | `ADD COLUMN arbitro_id` falla la segunda vez (no idempotente) | N/A (script, no código) | Error SQL visible, detiene el script | Visible — usar `ADD COLUMN IF NOT EXISTS` |
| `bootstrap_admin_si_no_existe` en entorno limpio sin T6 | CHECK constraint rechaza `rol="Admin"` | Nueva, unitaria (T18) — no existía ninguna hoy | Excepción atrapada por el retry loop de `main.py`, solo logueada a consola | **Silenciosa para el usuario** — `/health` sigue en OK, nadie ve que no hay AdminGeneral. Crítico: cubierto por T6 + T18. |
| AdminGeneral único se auto-desactiva o se auto-cambia el rol | Pierde acceso sin nadie que revierta (no hay superadmin de respaldo) | Nueva (T14) | Guard nuevo (T6) rechaza la operación | Visible, mensaje claro |
| Drift entre `07_migracion...sql` y `01`/`02` hand-edited | Una base recreada desde cero y una migrada a mano terminan con esquemas distintos | Sin test automático — verificación manual única (T17) | N/A | Silenciosa si no se corre T17 — flageado como riesgo conocido, no cerrado con test |

##### Worktree parallelization strategy

Secuencial, no vale la pena partir en worktrees: T1-T2 (migración +
schema) y T3-T4 (deps.py + Literal) son prerequisito de todo lo demás —
sin eso, los 8 routers (T8) y el Service layer (T11-T12) no tienen contra
qué compilar. Los 8 routers sí son technically independientes entre sí
después de T1-T4, pero cada edit es un swap de una palabra en un
decorator — el overhead de coordinar 3 worktrees para diffs de una línea
cada uno supera el beneficio en una sesión de un solo desarrollador.

##### Implementation Tasks

- [x] **T1 (P1, human: ~30min / CC: ~5min)** — database — Crear
  `database/07_migracion_roles_arbitro.sql`: `ALTER TABLE` de
  `chk_usuarios_rol` (4 roles), `UPDATE usuarios SET Rol='AdminGeneral'
  WHERE Rol='Admin'`, `ALTER TABLE PARTIDOS ADD COLUMN IF NOT EXISTS
  arbitro_id INT`, FK a `usuarios(id)`.
  - Surfaced by: D7
  - Verify: correr contra un clone de `torneos_mvp`, confirmar 2 filas de
    usuarios con roles correctos y la columna nueva
- [x] **T2 (P1, human: ~20min / CC: ~5min)** — database — Actualizar
  `01_schema.sql` (columna `arbitro_id`) y `02_constraints.sql` (CHECK de
  4 roles + FK) para que un entorno nuevo nazca correcto.
  - Surfaced by: D7
  - Verify: `backend/tests/conftest.py` reconstruye la base de test desde
    estos archivos — la suite completa debe seguir corriendo
- [x] **T3 (P1, human: ~15min / CC: ~5min)** — backend/app/api — Bypass de
  AdminGeneral en `require_roles()` (`deps.py`).
  - Surfaced by: D3
  - Verify: test nuevo, AdminGeneral pasa cualquier `require_roles(...)`
    sin estar en la lista
- [x] **T4 (P1, human: ~5min / CC: ~2min)** — backend/app/schemas —
  `RolUsuario` Literal a los 4 valores.
  - Surfaced by: bug #3 de la voz externa
  - Verify: `UsuarioOut` valida una respuesta con rol `TorneoAdmin`
- [x] **T5 (P2, human: ~5min / CC: ~2min)** — backend/app/models —
  Actualizar comentario de valores válidos en `usuario.py`.
  - Surfaced by: consistencia de código
  - Verify: revisión visual
- [x] **T6 (P1, human: ~30min / CC: ~10min)** — backend/app/services —
  `bootstrap_admin_si_no_existe` → `rol="AdminGeneral"`; guard nuevo en
  `update()`/`soft_delete()` que rechaza que un usuario se modifique su
  propio rol o se desactive a sí mismo.
  - Surfaced by: bug #2 de la voz externa + TODO decidido (self-lockout)
  - Verify: T14, T18
- [x] **T7 (P1, human: ~5min / CC: ~2min)** — backend/app/api/routes —
  `usuarios.py`: `require_roles("Admin")` → `require_roles("AdminGeneral")`
  literal (NO el swap uniforme de T8).
  - Surfaced by: bug #1 de la voz externa (crítico)
  - Verify: test nuevo, TorneoAdmin recibe 403 en `/usuarios`
- [x] **T8 (P1, human: ~20min / CC: ~10min)** — backend/app/api/routes —
  Swap `Admin` → `TorneoAdmin` en los 8 routers restantes: torneos,
  equipos, jugadores, inscripciones, plantillas, eventos, partidos,
  eventos_partido (23 call sites totales menos el de T7).
  - Surfaced by: D3
  - Verify: suite completa de tests por router
- [x] **T9 (P1, human: ~10min / CC: ~5min)** — backend/app/api/routes —
  `partidos.py`: sacar `Arbitro` de `POST /partidos`.
  - Surfaced by: D4
  - Verify: T15
- [x] **T10 (P1, human: ~15min / CC: ~5min)** — backend/app/models,
  backend/app/schemas — `arbitro_id` en `Partido` model, `PartidoUpdate` y
  `PartidoOut` (no en `PartidoCreate`).
  - Surfaced by: D6
  - Verify: `PATCH /partidos/{id}` con `arbitro_id` devuelve el campo en
    `PartidoOut`
- [x] **T11 (P1, human: ~30min / CC: ~10min)** — backend/app/services —
  `PartidoService.update()`: ownership-check para rol Árbitro (carga el
  partido, compara `arbitro_id`).
  - Surfaced by: D5
  - Verify: T15
- [x] **T12 (P1, human: ~30min / CC: ~10min)** — backend/app/services —
  `EventoPartidoService.create()` y `.anular()`: mismo ownership-check.
  - Surfaced by: D5
  - Verify: T16
- [x] **T13 (P1, human: ~30min / CC: ~10min)** — backend/tests —
  `conftest.py`: renombrar `admin_headers` → `admin_general_headers`,
  agregar `torneo_admin_headers`, y una forma de crear un Árbitro asignado
  a un partido específico (fixture o helper).
  - Surfaced by: regresión detectada en Test Review
  - Verify: los tests existentes que dependían de `admin_headers` siguen
    pasando con el nombre nuevo
- [x] **T14 (P1, human: ~20min / CC: ~10min)** — backend/tests —
  `test_usuarios.py`: actualizar referencias de rol, agregar test
  "TorneoAdmin recibe 403 en /usuarios" y test de auto-lockout (T6).
  - Surfaced by: T7, T6
  - Verify: `pytest backend/tests/test_usuarios.py`
- [x] **T15 (P1, human: ~20min / CC: ~10min)** — backend/tests —
  `test_partidos.py`: reescribir `test_arbitro_puede_programar_partido...`
  a esperar 403; agregar test de TorneoAdmin creando partido; agregar
  tests de ownership en `PATCH /partidos/{id}` (asignado vs no asignado).
  - Surfaced by: regresión detectada en Test Review (mandatorio, IRON RULE)
  - Verify: `pytest backend/tests/test_partidos.py`
- [x] **T16 (P1, human: ~20min / CC: ~10min)** — backend/tests —
  `test_eventos_partido.py`: reescribir los 4 tests existentes para usar
  un Árbitro asignado; agregar test de Árbitro NO asignado → 403.
  - Surfaced by: regresión detectada en Test Review (mandatorio, IRON RULE)
  - Verify: `pytest backend/tests/test_eventos_partido.py`
- [x] **T17 (P2, human: ~20min / CC: ~10min)** — database — Verificación
  única: correr `07_migracion_roles_arbitro.sql` contra un clone de
  `torneos_mvp`, comparar `pg_dump --schema-only` contra una base recreada
  desde `01`-`06`, confirmar que coinciden.
  - Surfaced by: riesgo de drift (voz externa)
  - Verify: diff vacío entre ambos schema dumps
- [x] **T18 (P2, human: ~15min / CC: ~5min)** — backend/tests — Test
  unitario nuevo para `bootstrap_admin_si_no_existe` (no existía ninguno
  hoy — el flujo de bootstrap no se ejercita vía HTTP en la suite actual).
  - Surfaced by: failure mode "silenciosa" en bootstrap
  - Verify: `UsuarioService(db_session).bootstrap_admin_si_no_existe(...)`
    devuelve `usuario.rol == "AdminGeneral"`
- [x] **T19 (P1, human: ~10min / CC: ~5min)** — frontend/src/auth,
  frontend/src — `Rol` type (`AuthContext.tsx`) a los 4 valores; `App.tsx`
  `roles={["TorneoAdmin", "AdminGeneral", "Arbitro"]}` en el
  `RequireRole` de `/control-de-mesa`.
  - Surfaced by: hallazgo propio (frontend RequireRole)
  - Verify: manual — login con el usuario admin migrado, confirmar acceso
    a `/control-de-mesa`
- [x] **T20 (P2, human: ~5min / CC: ~2min)** — frontend/src/api —
  Regenerar `schema.d.ts` con `npm run gen:api` contra el backend ya
  actualizado (no editar a mano, es generado).
  - Surfaced by: consistencia con backend
  - Verify: `schema.d.ts` incluye los 4 roles nuevos

### Fase 2 — Frontend: módulo Torneo Admin

- Landing propia para `TorneoAdmin` (reemplaza el `/dashboard` compartido de
  hoy para ese rol): crear torneo, listar/editar/eliminar torneos,
  gestionar equipos, partidos, inscripciones, jugadores.
- Pool compartido (D2) — sin filtro de dueño en las listas.
- Reutiliza el patrón ya existente de `ControlDeMesa.tsx` (formularios
  densos, feedback inline de errores 400) en vez de inventar uno nuevo.

#### Fase 2 — Resultado de /plan-eng-review (2026-08-26)

**Corrección al punto de arriba:** de los 6 recursos que Fase 2 gestiona,
solo Torneo/Equipo/Jugador tienen forma CRUD realmente uniforme. Ver D1.

##### Decisiones de arquitectura

- **D1 — Scaffold genérico vs 6 páginas a mano:** scaffold genérico (un hook
  `useResourceCrud` + `ResourceTable` + `ResourceForm`, configurados por
  recurso) para Torneo/Equipo/Jugador — los 3 que de verdad comparten forma
  (`id + estado + fecha_registro + fecha_modificacion`, `GET` con
  `skip/limit/estado`, `DELETE` = soft-delete). **Corrección de la voz
  externa:** InscripcionTorneo y JugadorEquipo se desvían más de lo que
  asumí — InscripcionTorneo no tiene `DELETE`, el borrado lógico es un
  `PATCH {estado: "Cancelado"}` directo, y tiene un campo `fecha` extra;
  JugadorEquipo no tiene `skip/limit/estado` en su `GET` (solo
  `equipo_id`/`jugador_id`) y no tiene ningún soft-delete plano — `POST
  /{id}/baja?fecha_fin=X` es el único camino de baja. Las dos usan el
  `ResourceTable` genérico para listar, pero con overrides reales en la
  acción de borrado y el filtro de estado, no un "wrinkle" chico como
  pensé — más parecidas al tratamiento semi-custom de Partido (D4) que al
  de Torneo/Equipo/Jugador.
- **D2 — Ruteo:** ruta nueva anidada `/torneo-admin/{recurso}` (torneos,
  equipos, jugadores, plantillas, inscripciones, partidos) con un
  `TorneoAdminLayout` compartido (nav + `<Outlet/>`), gateado con
  `RequireRole roles={["TorneoAdmin", "AdminGeneral"]}`. Redirect
  post-login a `/torneo-admin` para esos roles. **Hallazgo de la voz
  externa, no cerrado por el ruteo solo:** `Login.tsx` calcula
  `redirectTo` ANTES de loguear y `AuthContext.login()` nunca devuelve el
  `rol` a quien llama — hoy no hay forma de redirigir por rol en el punto
  donde se hace la navegación. Necesita: `login()` devuelve el `rol` (o
  `handleSubmit` lee `session.rol` recién actualizado), y ahí sí decide
  `/torneo-admin` vs el default. `/dashboard` sigue alcanzable
  navegando directo por URL — decisión: dejarlo así, es información
  pública (nunca tuvo `RequireRole`), no hay un límite de seguridad que
  cerrar, solo cambia el destino por default.
- **D3 — Alcance Plantillas (JugadorEquipo):** incluida en esta fase — sin
  esto, armar un equipo real desde la UI queda incompleto.
- **D4 — Form de Partido:** semi-custom, reusa el `ResourceTable` genérico
  para lista/baja pero tiene su propio form de creación/edición.
  **Hallazgos de la voz externa que agregan precisión, sin cambiar la
  decisión:**
  - El picker de equipos NO es "todos los equipos" — tiene que ser
    equipos inscritos (`Estado IN ('Inscrito','Confirmado')`) en el
    torneo elegido, porque `trg_partidos_validar_inscripcion`
    (`06_triggers.sql`) rechaza si no. No hay un endpoint que devuelva
    "equipos inscritos en el torneo X" directo — el form hace `GET
    /inscripciones?torneo_id=X`, filtra por estado en el cliente, y
    cruza con `GET /equipos` para los nombres. Join en el cliente sobre
    2 endpoints que ya existen, no un endpoint de backend nuevo (diff
    más chico).
  - Dependencia de orden: el torneo se elige PRIMERO, recién ahí se
    puebla el picker de equipos (a diferencia de InscripcionTorneo, cuyo
    picker de equipo no está acotado a nada). Si el form tratara ambos
    pickers igual, dejaría elegir cualquier equipo y recién el trigger
    lo rechazaría con un 400 — mala UX, evitable haciendo la dependencia
    explícita en el diseño del form.
  - `arbitro_id` renderiza SOLO en modo edición, nunca en el form de
    creación — `PartidoCreate` (backend) no lo acepta a propósito (Fase
    1, D6: "la asignación es un paso separado de crear el partido"). Si
    el form de crear/editar comparte componente, el campo se oculta
    condicionalmente, no se manda vacío.
- **D5 — Acceso de lectura a la lista de árbitros (reabre Fase 1):**
  TorneoAdmin necesita ver qué usuarios son Árbitro para asignarlos a un
  partido, pero `GET /usuarios` es `require_roles("AdminGeneral")`
  literal desde Fase 1 (T7, a propósito). **Corrección de la voz externa
  a mi propuesta original** (abrir el endpoint completo a TorneoAdmin):
  el filtro `?rol=` ya existe server-side — en vez de exponer el roster
  completo, el service fuerza `rol="Arbitro"` cuando quien llama es
  TorneoAdmin (ignora/rechaza cualquier otro valor que mande). Mismo
  endpoint, sin código nuevo más allá del chequeo, TorneoAdmin nunca ve
  el username de otro TorneoAdmin/AdminGeneral.
- **D6 — Infra de tests frontend:** cero infraestructura existe hoy (sin
  vitest/jest, sin un solo `.test.tsx`). Se monta vitest + Testing
  Library + MSW (mockea a nivel de red, más robusto que mockear el
  cliente `openapi-fetch` a mano) en esta fase, con tests para el
  scaffold genérico, `PartidosAdmin`, y el redirect/gate de rutas.

##### Sizing — considerado y rechazado

La voz externa argumentó partir Fase 2 en 3 sub-fases independientes (a:
scaffold + 3 recursos limpios, b: infra de tests, c: Partido + D5 +
excepciones) porque, a diferencia de Fase 1, no hay una razón técnica que
fuerce ir atómico acá (Fase 1 sí la tenía: el shim de compatibilidad que
se evitaba yendo todo junto). **Decisión del usuario: completo en un solo
pase, igual que Fase 1.** Registrado para que quede explícito que se
consideró y se rechazó conscientemente, no por default.

##### Diagrama — dependencia de datos en el form de Partido

```
PartidosAdmin.tsx
  │
  ▼
1. Elegir Torneo ──────────────▶ GET /torneos (lista, sin acotar)
  │
  ▼ (torneo_id conocido)
2. GET /inscripciones?torneo_id=X
  │  filtrar cliente: Estado IN ('Inscrito','Confirmado')
  ▼
3. Cruzar con GET /equipos ──▶ nombres para mostrar en el picker
  │
  ▼ (lista de equipos INSCRITOS en ESE torneo)
4. Elegir equipo local / visitante ──▶ deben ser distintos (chequeo cliente,
  │                                     espejo de chk_partidos_equipos_distintos)
  ▼
5. POST /partidos { torneo_id, equipos_id_local, equipos_id_visitante, ... }
   (sin arbitro_id — no existe en PartidoCreate)
   trg_partidos_validar_inscripcion revalida server-side (defensa en
   profundidad: el filtro del paso 2 es UX, no la única validación)

--- Modo edición (partido ya existe) ---
GET /usuarios?rol=Arbitro (forzado server-side si quien llama es
TorneoAdmin, D5) ──▶ picker de árbitro, solo visible acá
PATCH /partidos/{id} { arbitro_id, estado, ... }
```

##### NOT in scope (Fase 2)

- E2E real (Playwright/Cypress) del flujo completo — evaluado como TODO,
  descartado por el usuario: sin liga real usando el sistema todavía, es
  infraestructura para un flujo que nadie corrió en producción.
- Partir Fase 2 en sub-fases — considerado (voz externa) y rechazado
  explícitamente por el usuario, ver "Sizing" arriba.
- Endpoint de backend que devuelva "equipos inscritos en un torneo" ya
  unido — se resuelve con un join en el cliente sobre 2 endpoints
  existentes, diff más chico que agregar backend nuevo.
- Bloquear `/dashboard` para TorneoAdmin — sigue siendo información
  pública sin `RequireRole`, no hay razón de seguridad para cerrarlo.
- Soporte de múltiples árbitros por partido — ya rechazado en Fase 1 (D6),
  no se revisita acá.
- Diseño visual/branding — fuera de alcance de todo este plan desde el
  inicio.

##### What already exists (reusado, no reconstruido)

- Patrón de `ControlDeMesa.tsx` (TanStack Query, `apiErrorMessage` para
  errores inline, sin actualizaciones optimistas) — el scaffold genérico
  sigue el mismo estilo, no inventa uno nuevo.
- `AuthContext`/`RequireRole` — extendidos con la lista de roles nueva,
  no reescritos.
- Cliente tipado `openapi-fetch` + `schema.d.ts` — ya cubre los 6
  endpoints (regenerado en Fase 1 T20).
- Filtro `?rol=` de `GET /usuarios` — ya existía, D5 lo reusa en vez de
  agregar un endpoint nuevo.
- Patrón `BaseRepository` del backend — el scaffold genérico del frontend
  es el mismo concepto del lado del cliente.

##### Failure modes

| Codepath | Falla realista | Test | Manejo de error | Visible o silenciosa |
|---|---|---|---|---|
| Redirect post-login por rol | `login()` no devuelve `rol` hoy — sin el fix, el redirect a `/torneo-admin` nunca dispara | Nueva (T15/T17) | N/A hasta implementar el fix | Silenciosa si se omite: el usuario simplemente cae en `/dashboard` igual que antes, sin error visible |
| Form de Partido, equipo elegido antes que torneo (si no se fuerza el orden) | Trigger rechaza con 400 recién al confirmar, no al elegir | Nueva (T13) | `apiErrorMessage` ya muestra el 400 inline | Visible, pero mala UX evitable con el orden correcto en el form |
| `ResourceTable` genérico aplicado a JugadorEquipo sin el override de baja | Botón de "borrar" genérico llama a un endpoint que no existe (no hay `DELETE`/soft-delete plano) | Nueva (T11/T13) | 404/405 crudo si no se overridea | Confuso para el usuario si no se construye el override — cubierto por T11 |
| D5, force-filter con bug (TorneoAdmin manda `rol=AdminGeneral` y el filtro no lo pisa) | TorneoAdmin ve el roster completo, el leak que D5 existe para evitar | Nueva (T3) | Depende de la implementación — por eso el test es obligatorio | Silenciosa si no hay test: nadie lo nota hasta que importa |

##### Worktree parallelization strategy

Una sola oportunidad real: **T2-T3 (el fix de D5 en backend) no depende de
nada del frontend** — podría ir en paralelo al resto. El resto (T1 infra
de tests → T4-T6 scaffold → T8 layout → T9-T12 páginas → T14-T17 ruteo) es
una cadena secuencial genuina, cada capa depende de la anterior. Con una
sola pieza paralelizable, no vale la pena un worktree aparte — se hace
T2-T3 primero (rápido, desbloquea el picker de árbitro) y el resto en
secuencia.

##### Implementation Tasks

- [x] **T1 (P1, human: ~30min / CC: ~10min)** — frontend — Instalar
  `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `msw`
  como devDependencies; config de vitest (extiende `vite.config.ts`) +
  archivo de setup (matchers de jest-dom).
  - Surfaced by: D6
  - Verify: `npm run test` corre y encuentra 0 tests sin error
- [x] **T2 (P1, human: ~15min / CC: ~5min)** — backend/app/services,
  backend/app/api/routes — `UsuarioService.list()`: si quien llama tiene
  rol TorneoAdmin, fuerza `rol="Arbitro"` sin importar qué mande el query
  param. Router sigue en `require_roles("AdminGeneral")` para
  POST/PATCH/DELETE; el GET necesita `require_roles("AdminGeneral",
  "TorneoAdmin")`.
  - Surfaced by: D5
  - Verify: T3
- [x] **T3 (P1, human: ~15min / CC: ~5min)** — backend/tests — Test:
  TorneoAdmin en `GET /usuarios` recibe solo filas `rol=Arbitro` aunque
  mande `?rol=AdminGeneral`; AdminGeneral sigue viendo la lista completa
  sin forzar nada.
  - Surfaced by: D5 (failure mode de la tabla de arriba)
  - Verify: `pytest backend/tests/test_usuarios.py`
- [x] **T4 (P1, human: ~45min / CC: ~15min)** — frontend/src/hooks —
  `useResourceCrud.ts`: hook genérico list/create/update/softDelete sobre
  TanStack Query, parametrizado por endpoint base.
  - Surfaced by: D1
  - Verify: T7
- [x] **T5 (P1, human: ~45min / CC: ~15min)** — frontend/src/components/admin —
  `ResourceTable.tsx`: tabla genérica con estado de carga/error/vacío,
  click en fila para editar, acción de borrado configurable (para poder
  overridear en Inscripciones/Plantillas).
  - Surfaced by: D1
  - Verify: T7
- [x] **T6 (P1, human: ~45min / CC: ~15min)** — frontend/src/components/admin —
  `ResourceForm.tsx`: form genérico con tipos de campo texto/número/fecha/
  referencia (select poblado desde otro recurso).
  - Surfaced by: D1
  - Verify: T7
- [x] **T7 (P1, human: ~30min / CC: ~10min)** — frontend/src — Tests
  (vitest+RTL+MSW) para T4-T6: list success/error/vacío, create
  success/422/400/409, update, softDelete, picker de referencia
  cargando/vacío.
  - Surfaced by: D6, diagrama de cobertura
  - Verify: `npm run test`
- [x] **T8 (P1, human: ~20min / CC: ~10min)** — frontend/src/pages/torneo-admin —
  `TorneoAdminLayout.tsx`: nav de pestañas + `<Outlet/>`, envuelto en
  `RequireRole roles={["TorneoAdmin", "AdminGeneral"]}`.
  - Surfaced by: D2
  - Verify: T17
- [x] **T9 (P1, human: ~30min / CC: ~10min)** — frontend/src/pages/torneo-admin —
  `TorneosAdmin.tsx`, `EquiposAdmin.tsx`, `JugadoresAdmin.tsx`: config +
  scaffold genérico directo, sin overrides.
  - Surfaced by: D1
  - Verify: T13
- [x] **T10 (P1, human: ~20min / CC: ~10min)** — frontend/src/pages/torneo-admin —
  `InscripcionesAdmin.tsx`: scaffold genérico con override de baja
  (`PATCH {estado: "Cancelado"}` en vez de `DELETE`, que no existe).
  - Surfaced by: D1 (corrección de la voz externa)
  - Verify: T13
- [x] **T11 (P1, human: ~40min / CC: ~15min)** — frontend/src/pages/torneo-admin —
  `PlantillasAdmin.tsx`: usa `ResourceTable` para listar pero sin
  `skip/limit/estado` (el GET no los soporta) y con acción de baja
  custom apuntando a `POST /{id}/baja?fecha_fin=X` (no hay soft-delete
  plano).
  - Surfaced by: D1 (corrección de la voz externa — más custom de lo
    asumido originalmente)
  - Verify: T13
- [x] **T12 (P1, human: ~1h / CC: ~20min)** — frontend/src/pages/torneo-admin —
  `PartidosAdmin.tsx`: form semi-custom, torneo primero → equipos
  filtrados por inscripción (join cliente, ver diagrama), `arbitro_id`
  solo en modo edición, usando el endpoint de T2.
  - Surfaced by: D4
  - Verify: T13
- [x] **T13 (P1, human: ~30min / CC: ~15min)** — frontend/src — Tests
  para T9-T12: cada config renderiza y puede crear; `PartidosAdmin`
  cubre la dependencia torneo→equipos y que `arbitro_id` no aparece en
  modo creación.
  - Surfaced by: diagrama de cobertura
  - Verify: `npm run test`
- [x] **T14 (P1, human: ~15min / CC: ~5min)** — frontend/src — `App.tsx`:
  rutas anidadas `/torneo-admin/*` envueltas en `RequireRole` +
  `TorneoAdminLayout`.
  - Surfaced by: D2
  - Verify: T17
- [x] **T15 (P1, human: ~30min / CC: ~10min)** — frontend/src/auth,
  frontend/src/pages — `AuthContext.login()` devuelve el `rol` (o
  `LoginPage` lee `session.rol` post-login); redirect a `/torneo-admin`
  para TorneoAdmin/AdminGeneral, default sin cambios para el resto.
  - Surfaced by: D2 (hallazgo de la voz externa — el redirect por rol no
    estaba realmente cableado)
  - Verify: T17
- [x] **T16 (P1, human: ~10min / CC: ~5min)** — frontend/src/components —
  `NavBar.tsx`: link a `/torneo-admin`, visible solo para
  TorneoAdmin/AdminGeneral.
  - Surfaced by: D2
  - Verify: manual
- [x] **T17 (P1, human: ~20min / CC: ~10min)** — frontend/src — Test de
  ruteo: TorneoAdmin logueado termina en `/torneo-admin`; Arbitro/sin
  sesión sigue en `/dashboard`; navegar directo a `/torneo-admin` sin
  rol adecuado muestra el prompt de `RequireRole`, no un crash.
  - Surfaced by: D2, failure mode de la tabla de arriba
  - Verify: `npm run test`
- [x] **T18 (P2, human: ~5min / CC: ~2min)** — frontend/src/api —
  Regenerar `schema.d.ts` (levantar backend, `npm run gen:api`) por si
  D5 cambia algo visible en el OpenAPI — chequeo rápido, probablemente
  sin cambios de forma (solo permisos).
  - Surfaced by: consistencia con backend
  - Verify: diff de `schema.d.ts` es vacío o mínimo

### Fase 3 — Frontend: módulo Árbitro (partidos asignados)

- Bloqueada por la Fase 1 (necesita la asignación árbitro↔partido real).
- Landing "Mis partidos" filtrada por el usuario logueado — hoy
  `ControlDeMesa.tsx` no filtra, muestra el flujo de carga de eventos para
  cualquier partido al que se navegue. Decidir en esa revisión si
  `ControlDeMesa.tsx` se adapta con un filtro previo, o si el módulo
  Árbitro es una pantalla nueva que reusa los mismos componentes de carga
  de eventos.

#### Fase 3 — Resultado de /plan-eng-review (2026-08-26)

**Step 0:** fase chica a propósito — una sola pantalla nueva. Toca ~10
archivos pero cada edit es trivial (agregar un query param que
`BaseRepository` ya soporta genérico, exportar un componente existente,
una rama nueva en un helper de redirect). No se activó el gate de
reducción de alcance: no hay una versión "más chica" real que siga
entregando "Mis partidos" — sacar cualquier pieza (el filtro server-side,
el link de NavBar, el redirect post-login) deja el módulo roto o
inalcanzable, no lo simplifica.

##### Decisiones de arquitectura (D1-D6)

- **D1 — Filtro de "mis partidos":** `arbitro_id` nuevo como query param
  opcional en `GET /partidos` (route + `PartidoService.list()`
  pass-through). `BaseRepository.list(**filtros)` ya arma el `WHERE`
  genérico para cualquier columna no-nula — cero cambios en el repositorio.
  Server-side, no filtro en el cliente: reusa el mismo patrón que
  `torneo_id`/`estado`, y no trae partidos ajenos que después se
  descartan en el navegador.
- **D2 — De dónde sale el `id` del árbitro logueado:** `AuthContext` llama
  `GET /auth/me` una vez después de loguearse (endpoint que ya existe
  desde Fase 1, nunca usado hasta ahora) y guarda `id` en la sesión. Cero
  cambios al contrato de `POST /auth/login` — no hace falta tocarlo.
- **D3 — Forma de la ruta:** `/arbitro` es una ruta única que ES
  directamente "Mis partidos" — sin capa de layout/`<Outlet/>` como
  Torneo Admin, porque hoy hay una sola pantalla real. Si Fase 4 agrega
  más pantallas al módulo Árbitro, migrar a layout+Outlet en ese momento
  es un refactor chico, no una reescritura. `RequireRole roles={["Arbitro"]}`
  — sin AdminGeneral (a diferencia de `/torneo-admin`): el "entrar como"
  de un AdminGeneral en el módulo Árbitro es exactamente la pregunta que
  Fase 4 todavía no decidió (ver esa sección), no se preempta acá.
- **D4 — Reuso del panel de carga de eventos:** se exporta el `MesaPanel`
  existente de `ControlDeMesa.tsx` y se reusa tal cual dentro de
  `MisPartidos.tsx`, en vez de duplicar la lógica de forms/mutaciones de
  goles/tarjetas/cambios. Confirmado por la voz externa: `MesaPanel` no
  tiene ninguna afordancia exclusiva de TorneoAdmin/AdminGeneral (nada de
  editar/eliminar partido) — seguro de embeber para un Árbitro sin
  filtrar nada adicional.
- **D5 — Acceso a `/control-de-mesa` para Árbitro:** se deja alcanzable
  sin restringir (mismo `RequireRole` de hoy, sin sacar `"Arbitro"`).
  Mismo precedente que Fase 2 D2 con `/dashboard`: no hay límite de
  seguridad que cerrar (el ownership-check en el Service ya rechaza
  cualquier mutación sobre un partido ajeno), solo cambia cuál es la
  pantalla default después del login.
- **D6 — Alcance de la lista + guard de estado (decisión del usuario,
  no la recomendación de la revisión):** la voz externa encontró que
  `MesaPanel` no chequea `partido.estado` en ningún lado — el form de
  carga de eventos se renderiza siempre, sin gate ni de frontend ni de
  backend, sea cual sea el estado del partido. Hoy eso no se nota porque
  `ControlDeMesaPage` solo deja *elegir* partidos Programado/En curso (el
  filtro vive en la lista, no en el panel). La revisión recomendó agregar
  ADEMÁS un guard real dentro de `MesaPanel` (defensa en profundidad,
  cierra el mismo gap latente que ya existe hoy en `/control-de-mesa`).
  **El usuario decidió explícitamente solo el filtro de lista, sin el
  guard extra** — mismo patrón que Control de Mesa ya usa, sin tocar
  `MesaPanel`. `MisPartidos.tsx` muestra únicamente partidos
  Programado/En curso, igual que `ControlDeMesaPage`. Riesgo aceptado,
  documentado en Failure modes abajo: si en el futuro algún código llega
  a `MesaPanel` con un partido ya cerrado (deep link, cambio de filtro),
  no hay ningún gate que lo impida.

##### Hallazgos de la voz externa (Claude subagente — Codex no estaba
instalado en esta sesión)

1. **El gap de estado en `MesaPanel`** (crítico como hallazgo, resuelto
   como riesgo aceptado en D6 — ver arriba).
2. `MesaPanel`/`ControlDeMesa.tsx` no tiene NINGÚN botón de "anular
   evento" en el frontend hoy — el timeline de eventos cargados es
   solo-lectura, aunque el backend ya soporta
   `POST /eventos-partido/{id}/anular` desde Fase 1. Gap preexistente,
   no introducido ni resuelto por esta fase — más sentido en "Mis
   partidos" (uso diario del árbitro) que en Control de Mesa, pero fuera
   de alcance acá (ver NOT in scope).
3. El empty-state de "Mis partidos" necesita copy propia — la de
   `ControlDeMesaPage` ("No hay partidos programados ni en curso ahora
   mismo") es una afirmación de sistema completo, no tiene sentido para
   un árbitro sin asignaciones (T5).
4. NavBar no tenía rama para Árbitro (solo TorneoAdmin/AdminGeneral) —
   agregado a Implementation Tasks (T8).
5. `landingPorRol()` necesita la rama `Arbitro` → `/arbitro` — fácil de
   olvidar porque la pantalla puede quedar construida y alcanzable solo
   navegando la URL a mano si se omite (T7).
6. Confirmado sin objeciones: D1 no agrega ninguna fuga de datos nueva —
   `PartidoOut` ya incluye `arbitro_id` en la respuesta pública hoy
   existente de `GET /partidos`; cualquiera podía ya calcular "qué
   partidos son de tal árbitro" del lado del cliente. El query param
   nuevo es conveniencia server-side, no una capacidad nueva.

##### Diagrama — flujo de "Mis partidos"

```
Login
  │
  ▼
POST /auth/login ──▶ { access_token, rol }
  │
  ▼
GET /auth/me (D2, ya existía) ──▶ { id, username, rol, ... }
  │                                 session = { token, username, rol, id }
  ▼
landingPorRol(rol)
  │
  ├─ "Arbitro" ─────────────────▶ /arbitro (D3, ruta única, sin layout)
  ├─ "TorneoAdmin"/"AdminGeneral" ▶ /torneo-admin (Fase 2)
  └─ otro ──────────────────────▶ /dashboard

/arbitro (MisPartidos.tsx)
  │
  ▼
GET /partidos?arbitro_id=session.id   (D1, filtro server-side vía
  │                                     BaseRepository genérico)
  ▼
filtrar: estado IN (Programado, En curso)   (D6, mismo patrón que
  │                                           ControlDeMesaPage — SIN
  │                                           guard extra en MesaPanel)
  ▼
lista de partidos asignados activos (o empty-state árbitro-específico)
  │
  ▼ (click en un partido)
<MesaPanel partidoId=X />   (D4, componente EXPORTADO y REUSADO de
                              ControlDeMesa.tsx — cero lógica duplicada)
  │
  ▼
POST /eventos-partido, PATCH /partidos/{id}
  ownership ya enforced server-side (Fase 1 D5, verificar_arbitro_asignado)
```

##### NOT in scope (Fase 3)

- Guard de `estado` dentro de `MesaPanel` — considerado (voz externa) y
  rechazado explícitamente por el usuario en D6, ver riesgo aceptado en
  Failure modes.
- Botón de "anular evento" en el frontend — gap preexistente de Control
  de Mesa (hallazgo #2), ni introducido ni resuelto acá.
- Historial de partidos Finalizado/Cancelado del árbitro — "Mis
  partidos" solo muestra los activos (D6), no hay pantalla de histórico.
- Selector "entrar como" de AdminGeneral / acceso de AdminGeneral al
  módulo Árbitro — deferred a Fase 4, como ya decía el plan original.
- Restringir `/control-de-mesa` para Árbitro — considerado y rechazado
  en D5, mismo precedente que Fase 2 D2.

##### What already exists (reusado, no reconstruido)

- `BaseRepository.list(**filtros)` genérico — `arbitro_id` no toca el
  repositorio, solo route + service.
- `GET /auth/me` — construido en Fase 1, nunca llamado desde el frontend
  hasta esta fase.
- `verificar_arbitro_asignado` (Fase 1 D5) — ya protege las mutaciones
  reales, sin cambios.
- `MesaPanel` — reusado tal cual, sin duplicar (D4).
- Patrón `landingPorRol` + link condicional en NavBar — mismo patrón que
  Fase 2 D2 usó para Torneo Admin, aplicado ahora a Árbitro.

##### Failure modes

| Codepath | Falla realista | Test | Manejo de error | Visible o silenciosa |
|---|---|---|---|---|
| Árbitro sin partidos asignados activos | Lista vacía en "Mis partidos" | Nueva (T9) | Empty-state árbitro-específico (hallazgo #3) | Visible, mensaje claro |
| `GET /auth/me` falla justo después de un login exitoso | `session.id` queda `undefined`, `/arbitro` no puede armar el filtro | Nueva (T9) | A definir en implementación — no debería tumbar el login ya exitoso | Cubrir con al menos un test explícito, no asumir que siempre responde |
| Deep link futuro (o cambio de filtro) que llega a `MesaPanel` con un partido Finalizado/Cancelado | Formulario de carga de eventos activo sobre un partido cerrado | Ninguno — riesgo aceptado en D6, no cerrado con test | N/A, no hay gate | **Silenciosa** — documentado como deuda conocida, candidato a TODOS.md si aparece un caso real |
| `arbitro_id` + `estado` combinados en `GET /partidos` | Filtro compuesto no combina bien | Nueva (T2) | `BaseRepository` ya los combina con AND | Visible si el test falla |

##### Worktree parallelization strategy

Secuencial, fase demasiado chica para partir en worktrees: T1-T2 (filtro
backend) y T3 (session.id vía `/auth/me`) son prerequisito de T5
(`MisPartidos.tsx`). T4 (exportar `MesaPanel`) es técnicamente
independiente pero es literalmente agregar la palabra `export` — no
amerita coordinar un worktree aparte para eso.

##### Implementation Tasks

- [x] **T1 (P1, human: ~15min / CC: ~5min)** — backend/app/api/routes,
  backend/app/services — `GET /partidos`: agregar `arbitro_id: int | None`
  como query param opcional, pasarlo a `PartidoService.list()` →
  `self.repo.list(..., arbitro_id=arbitro_id)`.
  - Surfaced by: D1
  - Verify: T2
- [x] **T2 (P1, human: ~15min / CC: ~5min)** — backend/tests — Tests
  nuevos: `GET /partidos?arbitro_id=X` devuelve solo esos partidos;
  combinado con `?estado=` (hallazgo #6 de la sección de tests).
  - Surfaced by: D1, voz externa
  - Verify: `pytest backend/tests/test_partidos.py`
- [x] **T3 (P1, human: ~20min / CC: ~10min)** — frontend/src/auth —
  `AuthContext.tsx`: extender `Session` con `id: number`; tras un login
  exitoso, llamar `GET /auth/me` y guardar el `id` en la sesión.
  - Surfaced by: D2
  - Verify: T9 (test de error si `/auth/me` falla)
- [x] **T4 (P1, human: ~5min / CC: ~2min)** — frontend/src/pages —
  `ControlDeMesa.tsx`: exportar `MesaPanel`.
  - Surfaced by: D4
  - Verify: compila, `ControlDeMesaPage` sigue funcionando igual
- [x] **T5 (P1, human: ~45min / CC: ~15min)** — frontend/src/pages/arbitro —
  `MisPartidos.tsx` (nuevo): fetch `GET /partidos?arbitro_id=session.id`,
  filtra Programado/En curso (D6), lista con empty-state árbitro-específico
  (hallazgo #3), embebe `MesaPanel` reusado (D4) al seleccionar un partido.
  - Surfaced by: D1, D2, D3, D4, D6
  - Verify: T9
- [x] **T6 (P1, human: ~10min / CC: ~5min)** — frontend/src —
  `App.tsx`: ruta `/arbitro` con `RequireRole roles={["Arbitro"]}` (D3,
  sin layout/Outlet).
  - Surfaced by: D3
  - Verify: T9
- [x] **T7 (P1, human: ~5min / CC: ~2min)** — frontend/src/pages —
  `Login.tsx`: `landingPorRol()` — rama `"Arbitro"` → `/arbitro`
  (hallazgo #5 de la voz externa).
  - Surfaced by: voz externa
  - Verify: T9
- [x] **T8 (P2, human: ~10min / CC: ~5min)** — frontend/src/components —
  `NavBar.tsx`: link condicional "Mis partidos" → `/arbitro`, visible
  solo para rol `Arbitro` (hallazgo #4 de la voz externa).
  - Surfaced by: voz externa
  - Verify: manual
- [x] **T9 (P1, human: ~30min / CC: ~15min)** — frontend/src — Tests
  (vitest+RTL+MSW): `MisPartidos.tsx` pide `arbitro_id` propio, filtra a
  Programado/En curso, empty-state árbitro-específico, error de
  `/auth/me` no rompe el login; ruteo: redirect post-login Arbitro→
  `/arbitro`, `RequireRole` rechaza TorneoAdmin/AdminGeneral/Publico en
  `/arbitro`.
  - Surfaced by: D1-D6, hallazgos de tests de la voz externa
  - Verify: `npm run test`
- [x] **T10 (P2, human: ~5min / CC: ~2min)** — frontend/src/api —
  Regenerar `schema.d.ts` (`npm run gen:api`) — chequeo rápido, D1 es el
  único cambio de forma esperado (query param nuevo y opcional).
  - Surfaced by: consistencia con backend
  - Verify: diff de `schema.d.ts` es mínimo (solo el nuevo param)

### Fase 4 — Backend + Frontend: módulo Admin General

- Gestión de usuarios (crear, eliminar, asignar rol) — pantalla nueva, sin
  equivalente hoy en el frontend.
- Acceso total: puede entrar a los módulos de Torneo Admin y Árbitro sin
  restricción — confirmar en esa revisión cómo se resuelve el routing
  (¿un selector de "entrar como", o simplemente ve todo junto en su propia
  vista?). No decidido todavía — abrir como pregunta en esa fase.

#### Fase 4 — Resultado de /plan-eng-review (2026-08-26)

**Step 0:** el backend de esta fase ya está construido de punta a punta
desde Fase 1/2 — CRUD completo de usuarios (`usuarios.py` +
`UsuarioService`), guard de auto-lockout, filtro `?rol=`. Fase 4 es casi
puramente frontend: una pantalla que encaja exacto en el scaffold
genérico ya existente (`SimpleResourceAdminPage`, el mismo patrón de
`TorneosAdmin.tsx`) — mismo `id+estado+fechas`, `DELETE`=soft-delete. No
se activó el gate de reducción de alcance: no hay una versión más chica
que siga entregando "gestión de usuarios + acceso cruzado", que es
literalmente lo que pide el texto original de esta fase.

##### Decisiones de arquitectura (D1-D4)

- **D1 — Acceso cruzado de AdminGeneral a `/arbitro`:** se amplía
  `RequireRole` de `/arbitro` para incluir `AdminGeneral` (además de
  `Arbitro`), más el link condicional de NavBar. Sin selector "entrar
  como" — dos listas de roles ampliadas, sin UI nueva. Confirmado por la
  voz externa: backend-safe sin cambios — `require_roles()` ya tiene un
  bypass global de AdminGeneral (`deps.py`) para TODO excepto
  `usuarios.py` (a propósito), y `verificar_arbitro_asignado` ya es
  no-op para cualquier rol que no sea Árbitro — AdminGeneral ya tenía
  acceso de backend a `/partidos`/`/eventos-partido` desde antes; esto
  solo expone la ruta de frontend a una capacidad que ya era legal.
- **D2 — Self-lockout en la lista de Usuarios:** dos arreglos juntos,
  mismo costo marginal por tocar el mismo archivo:
  (a) `ResourceTable` gana un prop opcional `isSelf?: (row) => boolean`
  que oculta el botón "Dar de baja" para la fila del usuario logueado —
  cierra preventivamente el click más probable de auto-lockout.
  (b) `SimpleResourceAdminPage` gana un mensaje de error visible cuando
  falla un softDelete — gap preexistente confirmado por la voz externa
  (`crud.softDelete.isError`/`.error` nunca se leían), que beneficia a
  los 4 recursos que ya usan este componente compartido (Torneos,
  Equipos, Jugadores, y el nuevo Usuarios), no solo a esta pantalla.
  La voz externa confirmó que el otro camino de auto-lockout (editar tu
  propia fila y cambiarte el rol/estado desde el form) YA no es
  silencioso — `SimpleResourceAdminPage` ya cablea `submitError` al
  form de edición, sin trabajo extra.
- **D3 (hallazgo de la voz externa, no discutido — se corrige directo):**
  `UsuarioUpdate.password` (`schemas/usuario.py`) no tenía el mismo
  validador de mínimo 8 caracteres que `UsuarioCreate` — agujero
  preexistente que antes solo era alcanzable llamando la API cruda,
  ahora queda un click de distancia con el form de edición nuevo. Se
  agrega el mismo `field_validator`.
- **D4 (ruteo, confirmado explícito — no había otra opción real):**
  ruta standalone `/admin/usuarios`, sin anidar bajo `/torneo-admin`.
  La voz externa señaló por qué anidar sería un error: el nav de
  `TorneoAdminLayout` no está gateado por pestaña (`RequireRole` envuelve
  todo el layout), así que un tab "Usuarios" ahí le mostraría un link
  muerto a TorneoAdmin (siempre cae en el prompt de login) — confuso,
  aunque no un agujero de seguridad (el backend sigue literal-gateado).
  `RequireRole roles={["AdminGeneral"]}` — sin TorneoAdmin, coincide
  exacto con el gate literal de escritura del backend (los 4 endpoints
  de escritura en `usuarios.py` son `require_roles("AdminGeneral")`
  literal); TorneoAdmin puede seguir llamando `GET /usuarios` en otro
  lado (picker de árbitro, Fase 2 D5) sin llegar nunca a esta pantalla.

##### Hallazgos de la voz externa (Claude subagente — Codex no estaba
instalado en esta sesión)

1. **El gap de D3** (crítico como hallazgo, resuelto directo arriba).
2. **El gap de ruteo de D4** (resuelto directo arriba).
3. Confirmado sin objeciones: el tipo de campo `"password"` nuevo en
   `ResourceForm` es casi un no-op en runtime — la rama genérica ya pasa
   cualquier `type` no-`reference`/`select` directo al `<input type=...>`
   (`ResourceForm.tsx`); lo único que hace falta es ensanchar el union
   de TypeScript. Nada que sobre-construir acá.
4. Confirmado sin objeciones: `initialValues.password` en modo edición
   arranca en `null` (no viene en `UsuarioOut`), así que si el admin no
   toca el campo, `password` nunca se manda — no hay riesgo de que un
   password vacío pise el validador de 8 caracteres por accidente.
5. Confirmado sin objeciones: dejar `"Publico"` como opción del select
   de rol en el form de creación tiene sentido — `landingPorRol` ya
   manda cualquier rol no reconocido a `/dashboard` (público, sin
   `RequireRole`), no es una cuenta "sin adónde ir".
6. Gap transitorio menor, no bloqueante: `session.id` puede estar
   `undefined` justo después del login (mientras `GET /auth/me` no
   resolvió) — durante esa ventana, `isSelf` compara contra `undefined`
   y el botón de tu propia fila queda visible. Se autocorrige solo: si
   se lo clickeás en ese instante, D2(b) ya muestra el error en vez de
   fallar en silencio. No amerita un guard extra.

##### Diagrama — acceso por rol después de Fase 4

```
                    /torneo-admin    /arbitro       /admin/usuarios
AdminGeneral            ✅               ✅ (D1)          ✅
TorneoAdmin              ✅               ❌               ❌
Arbitro                  ❌               ✅               ❌
Publico / sin sesión     ❌               ❌               ❌

GET /usuarios (lectura): AdminGeneral ve todo | TorneoAdmin ve solo
rol=Arbitro (Fase 2, D5, sin cambios) | el resto, 403.
POST/PATCH/DELETE /usuarios: AdminGeneral únicamente, literal, sin
cambios (Fase 1, D3/T7).
```

##### NOT in scope (Fase 4)

- Selector "entrar como" — considerado (C en la revisión) y rechazado:
  sin evidencia de demanda, dos links en el nav alcanzan.
- Deshabilitar (en vez de solo ocultar) los campos rol/estado en el form
  de edición cuando editás tu propia fila — la voz externa confirmó que
  el camino ya no es silencioso (submitError existente), así que es una
  mejora de UX opcional, no un gap a cerrar.
- Auditoría más amplia de otros gaps de UX silenciosos en el scaffold
  genérico fuera de softDelete (create/update de los otros 3 recursos ya
  tienen su propio `submitError` cableado — no se encontró ningún otro
  camino silencioso).

##### What already exists (reusado, no reconstruido)

- CRUD completo de usuarios + guard de auto-lockout + filtro `?rol=` —
  el backend entero de esta fase, construido en Fase 1/2.
- `SimpleResourceAdminPage` + `ResourceTable` + `ResourceForm` — mismo
  patrón exacto que `TorneosAdmin.tsx`, sin inventar una página custom.
- Bypass de AdminGeneral en `require_roles()` (Fase 1, D3) — D1 no
  necesita tocar el backend en absoluto.
- Empty-state árbitro-específico de "Mis partidos" (Fase 3) — cubre
  gratis el caso común de un AdminGeneral sin partidos asignados.

##### Failure modes

| Codepath | Falla realista | Test | Manejo de error | Visible o silenciosa |
|---|---|---|---|---|
| PATCH `/usuarios/{id}` con password de 1-7 caracteres | Antes de D3: se acepta y hashea igual | Nueva (T2) | 422 de Pydantic tras D3 | Visible tras el fix, silenciosa (aceptaba cualquier cosa) antes |
| AdminGeneral hace click en "Dar de baja" de su propia fila | Antes de D2: 403 sin ningún mensaje en la lista | Nueva (T9) | Guard D2(a) lo oculta; si igual se dispara (ventana de `session.id` undefined), D2(b) lo muestra | Visible tras el fix |
| softDelete falla por cualquier otra razón (network, 500) en Torneos/Equipos/Jugadores/Usuarios | Antes de D2(b): sin ningún feedback en la lista | Nueva (T9) | Mensaje de error visible tras D2(b) | Visible tras el fix, silenciosa antes (afecta 4 recursos, no solo Usuarios) |
| TorneoAdmin navega directo a `/admin/usuarios` por URL | Bloqueado por `RequireRole` — nunca llega al backend | Nueva (T9) | `LoginPrompt` | Visible, mensaje claro |

##### Worktree parallelization strategy

Secuencial, fase chica: T1 (validador backend) y T3-T5 (prop nuevo en
`ResourceForm`/`ResourceTable`/`SimpleResourceAdminPage`) son
prerequisito de T6 (`UsuariosAdmin.tsx`). T7-T8 (rutas + nav) dependen de
T6. Un solo desarrollador, sin beneficio real de partir en worktrees.

##### Implementation Tasks

- [x] **T1 (P1, human: ~10min / CC: ~5min)** — backend/app/schemas —
  `UsuarioUpdate.password`: mismo `field_validator` de mínimo 8
  caracteres que `UsuarioCreate` (D3, hallazgo de la voz externa).
  - Surfaced by: D3
  - Verify: T2
- [x] **T2 (P1, human: ~10min / CC: ~5min)** — backend/tests — Test
  nuevo: `PATCH /usuarios/{id}` con password corta devuelve 422.
  - Surfaced by: D3
  - Verify: `pytest backend/tests/test_usuarios.py`
- [x] **T3 (P2, human: ~5min / CC: ~2min)** — frontend/src/components/admin —
  `ResourceForm.tsx`: ensanchar `ResourceFormField.type` para incluir
  `"password"` (la rama genérica ya renderiza el `<input>` correcto,
  solo hace falta el tipo).
  - Surfaced by: hallazgo #3 de la voz externa
  - Verify: T9
- [x] **T4 (P1, human: ~15min / CC: ~5min)** — frontend/src/components/admin —
  `ResourceTable.tsx`: prop opcional `isSelf?: (row: T) => boolean` —
  oculta el botón "Dar de baja" cuando es `true` (D2a).
  - Surfaced by: D2
  - Verify: T9
- [x] **T5 (P1, human: ~15min / CC: ~5min)** — frontend/src/pages/torneo-admin —
  `SimpleResourceAdminPage.tsx`: pasar `isSelf` a `ResourceTable`;
  agregar mensaje de error visible cuando falla `crud.softDelete` (D2b,
  beneficia a los 4 recursos que ya usan este componente).
  - Surfaced by: D2
  - Verify: T9
- [x] **T6 (P1, human: ~40min / CC: ~15min)** — frontend/src/pages/admin —
  `UsuariosAdmin.tsx` (nuevo): config vía `SimpleResourceAdminPage`,
  mismo patrón que `TorneosAdmin.tsx` — `createFields`
  (username/nombre/password requerido/rol),
  `editFields` (nombre/rol/estado/password opcional — "dejar en blanco
  para no cambiar"), `isSelf={(row) => row.id === session?.id}`.
  - Surfaced by: D1, D2, D3
  - Verify: T9
- [x] **T7 (P1, human: ~10min / CC: ~5min)** — frontend/src —
  `App.tsx`: ruta nueva `/admin/usuarios`, `RequireRole
  roles={["AdminGeneral"]}` (D4, standalone, sin anidar bajo
  `/torneo-admin`); ampliar `/arbitro` a `RequireRole
  roles={["Arbitro", "AdminGeneral"]}` (D1).
  - Surfaced by: D1, D4
  - Verify: T9
- [x] **T8 (P1, human: ~10min / CC: ~5min)** — frontend/src/components —
  `NavBar.tsx`: link condicional "Usuarios" → `/admin/usuarios`
  (AdminGeneral únicamente); ampliar la condición del link "Mis
  partidos" para incluir AdminGeneral (D1).
  - Surfaced by: D1
  - Verify: manual
- [x] **T9 (P1, human: ~40min / CC: ~15min)** — frontend/src — Tests
  (vitest+RTL+MSW): tipo `"password"` en `ResourceForm.test.tsx`;
  `isSelf` oculta el botón en `ResourceTable.test.tsx`; mensaje de error
  de softDelete en `SimpleResourceAdminPage.test.tsx`;
  `UsuariosAdmin.test.tsx` (crear/editar/listar, password opcional en
  edición); ruteo: AdminGeneral llega a `/arbitro` y a
  `/admin/usuarios`, TorneoAdmin rechazado en `/admin/usuarios`.
  - Surfaced by: D1-D4, hallazgos de tests de la voz externa
  - Verify: `npm run test`
- [x] **T10 (P2, human: ~5min / CC: ~2min)** — frontend/src/api —
  Regenerar `schema.d.ts` — corrido, diff vacío: el validador de D3 es un
  `field_validator` custom, no un `Field(min_length=...)`, así que no se
  refleja en el JSON Schema de OpenAPI. Resultado esperado, no un error.
  - Surfaced by: consistencia con backend
  - Verify: diff de `schema.d.ts` es vacío (confirmado)

## Fuera de alcance en este plan

- Diseño visual / branding / pulido de UI (confirmado por el usuario en
  esta sesión — "la parte de diseño no entra en esta fase").
- Deploy y hosting de producción.
- Offline-first en Control de Mesa (ya listado en `TODOS.md`, sigue
  diferido, es ortogonal a este plan).

## Próximo paso

Fase 1 (20/20 tasks, 52 tests backend) y Fase 2 (20/20 tasks, 54 tests
backend + 47 tests frontend) están implementadas y verificadas de punta a
punta — módulo Torneo Admin funcional en `/torneo-admin/*` con las 6
pantallas de gestión. Nada de esto está commiteado todavía (todo sigue
sobre el working tree del commit `04e07c3`) — evaluar si conviene
commitear/pushear antes de seguir.

Fase 3 (frontend Árbitro — "Mis partidos") — 10/10 tasks implementadas y
verificadas de punta a punta: 58 tests backend (56 + 2 nuevos de T2) + 55
tests frontend (47 + 8 nuevos), `tsc -b` limpio, `vite build` OK (90
módulos), `oxlint` limpio (mismo warning preexistente de siempre en
AuthContext.tsx). Módulo Árbitro funcional en `/arbitro` — "Mis partidos"
filtrado server-side por `arbitro_id`, reusa `MesaPanel` de Control de
Mesa. Riesgo aceptado documentado (D6): sin guard de `estado` dentro de
`MesaPanel`, solo el filtro de lista. Nada de esto está commiteado
todavía — Fase 1, Fase 2 y Fase 3 completas siguen sobre el working tree
del commit `04e07c3`.

Fase 4 (Admin General — gestión de usuarios + acceso cruzado) — 10/10
tasks implementadas y verificadas: 57 tests backend (56 + 1 nuevo de T2)
+ 67 tests frontend (55 + 12 nuevos), `tsc -b` limpio, `vite build` OK
(91 módulos), `oxlint` limpio. Pantalla de gestión de usuarios en
`/admin/usuarios`, acceso cruzado de AdminGeneral a `/arbitro` sin
selector. **Las 4 fases del plan original están completas.**

Nada de esto está commiteado — Fase 1, 2, 3 y 4 completas siguen sobre
el working tree del commit `04e07c3`. No hay una Fase 5 planeada; el
próximo paso natural es evaluar/armar los commits antes de seguir con
cualquier otro trabajo.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | not run |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | not run |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 4 | CLEAR (Fase 2), ISSUES_OPEN (Fase 3 accepted risk, Fase 4 fixes pending implementation) | Fase 4: 4 issues resolved via AskUserQuestion (D1-D2) + 2 hallazgos aplicados directo (D3 backend validator gap, D4 routing). Fase 3: 6 issues resolved (D1-D6), 1 real gap accepted as risk. Fase 2: 8 issues resolved, 0 critical gaps. Fase 1 (prior run, implemented): 9 issues resolved, 1 known gap (T17 drift check is manual-only by design) |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | not run (diseño fuera de alcance por decisión del usuario) |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | not run |

- **CODEX:** not installed this session — outside voice ran via Claude subagent instead (Fase 1 through Fase 4 runs).
- **CROSS-MODEL (Fase 4):** subagent verified D1/D2 are backend-safe (AdminGeneral's `require_roles()` bypass already covers `/partidos`/`/eventos-partido`; `verificar_arbitro_asignado` is a no-op for non-Arbitro roles) and confirmed the reuse plan for `SimpleResourceAdminPage`/`ResourceTable`/`ResourceForm` drops in cleanly. Found 2 real gaps applied directly rather than debated: `UsuarioUpdate.password` was missing the same 8-char minimum validator `UsuarioCreate` has (D3 — a preexisting hole made UI-reachable by the new edit form) and nesting the new screen as a `TorneoAdminLayout` tab would show TorneoAdmin a dead-end nav link since that layout's `RequireRole` isn't per-tab (D4 — settled on a standalone `/admin/usuarios` route instead). Confirmed several non-issues: the edit-form self-role-change path was already non-silent (`submitError` already wired), the `"password"` field type is a near no-op at the render layer, and empty-string-password-on-edit can't accidentally trip the validator (`initialValues.password` starts `null`).
- **CROSS-MODEL (Fase 3):** subagent found `MesaPanel` (reused by D4) has no `partido.estado` guard anywhere — the event-entry form renders unconditionally regardless of match state, and neither the frontend nor `EventoPartidoService` checks state, only ownership. Today this is masked because `ControlDeMesaPage`'s list only lets you *select* Programado/En curso matches — the protection lives in the list, not the panel. Subagent recommended adding a real guard in `MesaPanel` as defense-in-depth (D6, option C) since "Mis partidos" is a second, independent path into the same component. **User explicitly chose the list-filter-only option (D6-A) instead**, accepting the gap as documented risk (see Failure modes in the Fase 3 section) rather than following the recommendation — logged, not silently overridden. Subagent also confirmed D1 introduces no new data exposure (`PartidoOut` already includes `arbitro_id` in the existing public `GET /partidos` response) and that `MesaPanel` has no TorneoAdmin/AdminGeneral-only affordances, so D4's reuse is safe. Minor findings (no anular-event UI exists yet — preexisting gap, not this phase's; NavBar/Login redirect branches easy to forget) folded into T7/T8/T9.
- **CROSS-MODEL (Fase 2):** subagent narrowed D5 (giving TorneoAdmin read access to the árbitro list) — instead of opening `GET /usuarios` fully, the service now force-filters to `rol="Arbitro"` for TorneoAdmin callers, reusing the existing `?rol=` param instead of exposing the full user roster. Subagent also argued for splitting Fase 2 into 3 independent sub-phases (no technical coupling forces atomicity here, unlike Fase 1); user explicitly considered and rejected the split, keeping Fase 2 complete in one pass. Subagent confirmed the trigger-validation join, the torneo→equipo sequencing gap, and that `arbitro_id` must render edit-only — all folded into D4's implementation tasks.
- **VERDICT:** Eng Review CLEAR for Fase 4 (implemented, 10/10 tasks, 57 backend + 67 frontend tests — every issue the outside voice found, fixed) — no open critical gaps. ISSUES_OPEN for Fase 3 (implemented, 10/10 tasks, 58 backend + 55 frontend tests) — one gap (MesaPanel estado guard) knowingly left open by explicit user decision (D6), not an oversight; documented as accepted risk in Failure modes, candidate for TODOS.md if it becomes a real incident. CLEAR for Fase 2 (all issues resolved, no open critical gaps). Fase 1 remains ISSUES_OPEN by design (T17's drift check has no automated test, documented risk, already implemented and shipped). Eng review required before /ship — all 4 phases of this plan are now implemented; the working tree still has nothing committed.

NO UNRESOLVED DECISIONS
