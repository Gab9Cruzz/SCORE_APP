# RBAC — Asignación de Torneos (N:M) + Sistema de Licenciamiento

> Plan generado por `/autoplan` a partir de un brief de arquitectura/seguridad.
> Estado: **Fase 1, 2 y 3 implementadas** (2026-09-02) — kill switch de
> licencia, asignación N:M, panel de Admin General (Fase 1); scoping de
> `require_torneo_access` en los 8 routers con `torneo_id` real —
> inscripciones, partidos, motor_formatos, plantillas, traspasos,
> registro_lote, grupos, eventos_partido (Fase 2); filtro "mis torneos" en
> `TorneosAdminPage` para TorneoAdmin (Fase 3). 320 tests backend + 196
> frontend, todos verdes; migración 26 aplicada a `torneos_mvp`. Los 7
> routers restantes (equipos, jugadores, perfiles, disciplinas,
> modalidades, eventos-catálogo, torneo_grupos) quedaron **deliberadamente
> sin scoping** — son catálogos globales o un pool compartido sin torneo
> único (decisión explícita del usuario, ver §12).

<!-- /autoplan restore point: /c/Users/Gabo/.gstack/projects/Score-App/feat-equipos-jugadores-plan-autoplan-restore-20260902-121615.md -->

## 0. Resumen ejecutivo

Hoy `TorneoAdmin` es un rol **global**: cualquier cuenta con ese rol administra
**cualquier** torneo del sistema (`torneos.py` solo exige
`require_roles("TorneoAdmin")`, sin chequear de cuál torneo se trata). No
existe tabla de asignación usuario↔torneo, ni columna de licencia en
`USUARIOS`, ni pantalla de bloqueo por licencia.

Este plan agrega:
1. **Asignación N:M** `USUARIOS ↔ TORNEO` — un `TorneoAdmin` solo administra
   los torneos que se le asignaron explícitamente.
2. **Licencia por cuenta** (`Licencia_Activa` en `USUARIOS`) — kill switch de
   nivel superior: sin licencia, cero acceso administrativo, sin importar
   qué diga la tabla de asignaciones.
3. **Panel de Admin General**: tabla de usuarios con toggle de licencia +
   modal de selección múltiple de torneos.

Construye sobre infraestructura que **ya existe** (ver §1) — no reinventa
roles, auditoría, ni el patrón de tabla admin. La brecha real es acotada:
una tabla nueva, una columna nueva, un dependency de FastAPI nuevo, y
composición de UI sobre componentes ya existentes.

## 1. Lo que ya existe (no se reconstruye)

Verificado leyendo el código, no asumido:

| Pieza | Dónde | Qué hace hoy |
|---|---|---|
| 4 roles (`AdminGeneral`, `TorneoAdmin`, `Arbitro`, `Publico`) | `database/01_schema.sql:472` (columna `Rol`) + `database/02_constraints.sql:288` (`chk_usuarios_rol`) | Ya existe la jerarquía; `AdminGeneral` ya es el rol supremo |
| Bypass de `AdminGeneral` | `backend/app/api/deps.py:76-81` (`require_roles`) | `AdminGeneral` ya pasa cualquier chequeo de rol — mismo principio que "la licencia no importa para AdminGeneral" (a decidir, D2) |
| Auditoría automática de TODO cambio | `backend/app/core/auditoria.py` (session listener `before_flush`/`after_flush_postexec`) | Cualquier INSERT/UPDATE/DELETE vía ORM en `USUARIOS` o la tabla nueva queda registrado en `AUDITORIA` **gratis** — no hace falta una tabla de historial de licencias aparte |
| Guardas anti-auto-lockout | `backend/app/api/routes/usuarios.py:69-84`, `UsuarioService.update()`/`soft_delete()` (T6) | Ya existe el patrón "un AdminGeneral no puede desactivarse/degradarse a sí mismo" — se reusa igual para "no podés revocarte tu propia licencia" |
| Ownership-check de Árbitro | `backend/app/services/permisos.py` | Precedente directo de "rol X solo opera sobre SU subconjunto asignado" — incluso el comentario dice que `TorneoAdmin`/`AdminGeneral` "nunca pasan por acá con una restricción real" (hoy). Este plan le agrega esa restricción real a `TorneoAdmin`. |
| JWT sin claim de licencia | `backend/app/core/security.py:44` (`create_access_token(subject, rol)`) | El token solo lleva `sub`+`rol` — la licencia **no puede** vivir en el JWT si tiene que ser "inmediata" (revocar y que el usuario pierda acceso sin esperar a que expire el token) |
| Punto único de verificación por request | `backend/app/api/deps.py:21-40` (`get_current_user`) | Ya hace un round-trip a `UsuarioRepository` en cada request autenticado — agregar el chequeo de licencia acá es gratis, no agrega una query nueva |
| Precedente de metadata vía header | `backend/app/exceptions/errors.py:55-66` + `handlers.py:64-69` (`RateLimitError` → header `Retry-After`) | Patrón ya usado en este repo para que el frontend distinga "por qué" un error sin parsear el body — se reusa igual para distinguir "licencia revocada" de un 403 genérico |
| Middleware único de fetch | `frontend/src/api/client.ts:26-40` | Ya intercepta **todas** las respuestas (`onResponse`) y ya tiene el patrón callback registrado por `AuthContext` (`onUnauthorized`) — se agrega un segundo callback simétrico |
| Pantalla de bloqueo ya existe como patrón | `frontend/src/components/RequireRole.tsx` + `LoginPrompt` (`pages/Login.tsx`) | Ya hay precedente de "no mostrar un error crudo, mostrar una pantalla explicando qué hace falta" — se clona el patrón para "Licencia Inactiva" |
| Panel de usuarios ya existe | `frontend/src/pages/admin/UsuariosAdmin.tsx` | Ya es una tabla de TODOS los usuarios del sistema, ya usa `SimpleResourceAdminPage` + `ResourceTable`, ya tiene `isSelf` para ocultar acciones sobre la propia fila |
| Slot de acción extra por fila YA EXISTE | `SimpleResourceAdminPage.tsx:26` (`renderRowExtra` → `ResourceTable`'s `extraActions`) | Precedente literal (`equipos-jugadores-plan.md`, Fase 2, Etapa D) de agregar una acción custom por fila sin tocar `ResourceTable`/`SimpleResourceAdminPage` |
| Columna con render custom YA EXISTE | `ResourceTableColumn.render` | El toggle de licencia es una columna con `render` custom — no requiere ningún componente nuevo de tabla |
| Sin librería de UI instalada | `frontend/package.json` (solo `react`, `react-dom`, `react-router-dom`) | No hay Radix/MUI/Headless UI — el multiselect es una lista de checkboxes nativa, no una dependencia nueva |

**Conclusión de la búsqueda previa (Search Before Building):** la brecha real
es: 1 tabla nueva, 1 columna nueva, 1 trigger de validación cruzada, 1
dependency de FastAPI, 1 excepción + 1 handler, 2 endpoints nuevos en
`usuarios.py`, 1 callback en `client.ts`, 1 pantalla de bloqueo, y
composición de UI sobre `UsuariosAdmin.tsx` existente. Nada de esto duplica
algo que ya exista.

## 2. Brecha vs. requerimiento (qué falta hoy)

- `TORNEO_ID` en ningún lado de `USUARIOS` ni tabla intermedia → **no existe
  asignación N:M**, `TorneoAdmin` administra todo.
- `USUARIOS` no tiene columna de licencia → **no existe kill switch**.
- `torneos.py` (`POST`/`PATCH`/`DELETE`) solo chequea rol, nunca
  `torneo_id` contra el usuario → confirma el gap N:M.
- No hay excepción/handler que devuelva un 403 distinguible de "licencia" vs.
  "rol insuficiente" → frontend no puede mostrar la pantalla correcta.
- No hay panel con toggle + multiselect (`UsuariosAdmin.tsx` es CRUD
  genérico de campos, sin acciones de negocio custom todavía).

## 3. Modelo de datos

### 3.1 Licencia — columna en `USUARIOS`, no tabla aparte (D1)

```sql
ALTER TABLE USUARIOS
    ADD COLUMN IF NOT EXISTS Licencia_Activa BOOLEAN NOT NULL DEFAULT TRUE;
```

`DEFAULT TRUE`: migración aditiva sobre una base ya provisionada — nadie
pierde acceso el día que se despliega esto (mismo criterio que toda
migración de este repo, ver comentarios en `07_`/`14_`/`18_`).

**Wiring de ORM (obligatorio, no implícito):** `backend/app/models/usuario.py`
hoy NO tiene `licencia_activa` — hay que agregar
`licencia_activa: Mapped[bool] = mapped_column(default=True)` explícitamente
al `Usuario` declarativo. Sin este paso, cualquier código que lea
`usuario.licencia_activa` (§4.2 abajo) es un `AttributeError`, no una
excepción de negocio — el modelo SQLAlchemy y la columna SQL son cosas
distintas y ambas hacen falta (hallazgo de la voz externa, confirmado
leyendo `models/usuario.py`).

**Por qué columna y no tabla `LICENCIAS` con historial propio:** es un flag
de estado actual ("¿tiene licencia AHORA?"), no una entidad con ciclo de
vida propio. El "quién lo cambió y cuándo" ya lo cubre `AUDITORIA`
automáticamente (Datos_Anteriores/Datos_Nuevos vía el listener de sesión) —
una tabla de historial paralela duplicaría exactamente eso. Mismo patrón que
`Estado` en 10+ tablas del esquema.

### 3.2 Asignación N:M — tabla nueva

```sql
CREATE TABLE ASIGNACION_TORNEO_ADMIN (
    ID SERIAL PRIMARY KEY,
    Usuario_ID INT NOT NULL,
    Torneo_ID INT NOT NULL,
    -- 'Activo'/'Inactivo': revocar acceso = flip de Estado, no DELETE.
    -- Mismo criterio soft-delete que el resto del esquema, y evita
    -- reinsertar una fila (con su historial de auditoría) cada vez que el
    -- Admin General destilda y vuelve a tildar el mismo torneo en el modal.
    Estado VARCHAR(20) NOT NULL DEFAULT 'Activo',
    Fecha_Registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Fecha_Modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_asignacion_usuario_torneo UNIQUE (Usuario_ID, Torneo_ID)
);

ALTER TABLE ASIGNACION_TORNEO_ADMIN
    ADD CONSTRAINT fk_asignacion_usuario FOREIGN KEY (Usuario_ID) REFERENCES USUARIOS(ID),
    ADD CONSTRAINT fk_asignacion_torneo FOREIGN KEY (Torneo_ID) REFERENCES TORNEO(ID),
    ADD CONSTRAINT chk_asignacion_estado CHECK (Estado IN ('Activo', 'Inactivo'));
<!-- Corrección post outside-voice (Eng review, hallazgo #5): nombre de
constraint corregido de uq_* a unique_* — cada UNIQUE en 02_constraints.sql
usa unique_* (unique_disciplina_nombre, unique_edicion_por_grupo,
unique_usuario_username, etc.), cero uq_* en todo el repo. Section 5 de
este plan afirmaba "cero desvío de patrón" — este era uno, ya corregido. -->
<!-- La FILA UNIQUE(Usuario_ID, Torneo_ID) de arriba YA es un índice btree
de 2 columnas — el "índice compuesto (Usuario_ID, Torneo_ID, Estado)" que
una versión anterior de este plan proponía como mejora en Section 7/TODOS.md
resultó ser ruido (Eng review hallazgo #5): el lookup de require_torneo_access
ya es un probe de una sola fila sobre este UNIQUE, filtrar Estado después
es un fetch extra sobre una tupla ya localizada, no un scan. Retirado de
TODOS.md — no hay optimización real que hacer acá. -->

-- Postgres no indexa FK automáticamente (mismo comentario que 03_indexes.sql)
CREATE INDEX idx_asignacion_usuario ON ASIGNACION_TORNEO_ADMIN(Usuario_ID);
CREATE INDEX idx_asignacion_torneo ON ASIGNACION_TORNEO_ADMIN(Torneo_ID);
```

**Trigger de validación cruzada** (mismo patrón que
`fn_validar_torneo_modalidad`, `06_triggers.sql`): `Usuario_ID` debe
referenciar una cuenta con `Rol = 'TorneoAdmin'`. Un `CHECK` simple no
alcanza porque cruza tablas.

```
fn_validar_asignacion_torneo_admin_rol()
  → RAISE EXCEPTION si USUARIOS.Rol <> 'TorneoAdmin' para el Usuario_ID insertado/actualizado
```

**Corrección post outside-voice (Eng review, hallazgo #3 — MEDIA/ALTA
severidad):** este trigger valida en el momento de INSERT/UPDATE de la
propia fila de asignación — pero un `AdminGeneral` puede degradar a un
`TorneoAdmin` a `Arbitro` en cualquier momento vía `PATCH
/usuarios/{id}` (`usuarios.py`), y nada en el diseño original revalida ni
desactiva las filas de `ASIGNACION_TORNEO_ADMIN` que ese usuario ya
tenía. A diferencia de `fn_validar_torneo_modalidad` (que valida una FK
contra un catálogo estático que no cambia de categoría bajo el torneo),
acá el "catálogo" (`USUARIOS.Rol`) SÍ puede cambiar mid-life. Consecuencia
real: las filas de asignación quedan `Activo` pero huérfanas — si esa
misma cuenta se vuelve a promover a `TorneoAdmin` más adelante, reactiva
acceso a torneos que ningún `AdminGeneral` decidió conscientemente en ese
momento (la decisión "vieja" resucita sin pasar de nuevo por el panel).
`require_torneo_access` (§4.3) ya bloquea el acceso INMEDIATO mientras el
rol está degradado (su propio chequeo de rol lo cubre), así que esto no
es una brecha de seguridad activa hoy — es una brecha de higiene de datos
que se vuelve una sorpresa de seguridad en el futuro. **Fix agregado al
diseño:** `UsuarioService.update()` (que ya es el único lugar que cambia
`Rol`, con los guards de auto-lockout existentes) desactiva en la misma
transacción todas las filas `Activo` de `ASIGNACION_TORNEO_ADMIN` para ese
`Usuario_ID` cuando `Rol` sale de `'TorneoAdmin'` hacia cualquier otro
valor — aplicación, no trigger de DB (mantiene la lógica de negocio en
Python, consistente con dónde ya viven los otros guards de
`UsuarioService.update()`, y evita un segundo trigger cruzando
`USUARIOS`↔`ASIGNACION_TORNEO_ADMIN` en la dirección opuesta).

Número de migración tentativo: `26_migracion_rbac_licencias_torneos.sql`
(verificar en implementación si algún plan concurrente ya tomó ese número —
mismo criterio que el comentario en `18_migracion_auditoria_cambios.sql`).

**Wiring de ORM (obligatorio, no implícito):** esta tabla necesita un
modelo declarativo nuevo (`backend/app/models/asignacion_torneo_admin.py`,
`class AsignacionTorneoAdmin(TimestampMixin, Base)`) — no alcanza con la
DDL sola. **Condición para que `AUDITORIA` la capture gratis (§1):**
`AsignacionTorneoAdminService.set_torneos_asignados` (§4.4) DEBE mutar
filas vía `session.add()`/`setattr()` ORM estándar (que pueblan
`session.new`/`session.dirty`, lo que el listener de `core/auditoria.py`
inspecciona) — **nunca** `session.execute(insert(...)/update(...))` estilo
Core. Un bulk-upsert "eficiente" con Core es la implementación NATURAL para
"activar/desactivar el diff completo" y es precisamente la que rompe la
auditoría gratis en silencio (hallazgo de la voz externa) — el servicio
debe cargar las filas existentes primero y mutarlas una por una (ORM),
aceptando el costo de N queries/updates chicos en vez de 1 statement bulk;
para el tamaño real de este dato (decenas de torneos por usuario, no
miles) el costo es despreciable frente a la garantía de auditoría.

## 4. Backend

### 4.1 Excepción + handler nuevos

`backend/app/exceptions/errors.py`:

```python
class LicenseRevokedError(ForbiddenError):
    """Usuario autenticado, credenciales válidas, pero sin licencia activa.
    403 (no 401): la identidad SÍ es válida, lo que falta es autorización
    de nivel superior — mismo criterio que separa AuthError de ForbiddenError
    en este archivo."""

    def __init__(self, detail: str = "Licencia inactiva o revocada. Contactá al administrador."):
        super().__init__(detail)
```

`backend/app/exceptions/handlers.py` — mismo patrón que `RateLimitError` →
`Retry-After`: un header, no un campo en el body, para que el frontend no
tenga que parsear/clonar el stream de respuesta en el middleware genérico.

```python
@app.exception_handler(LicenseRevokedError)
async def _license_revoked(_: Request, exc: LicenseRevokedError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": exc.detail},
        headers={"X-License-Revoked": "true"},
    )
```

(Starlette resuelve el handler por MRO de la excepción — no importa el
orden de registro respecto a `ForbiddenError`, mismo mecanismo ya en uso.)

### 4.2 Chequeo de licencia — un único choke point

Vive en `get_current_user` (`deps.py`), no duplicado en `login()`: es el
único lugar por el que pasa **cada** request autenticado, incluida la
verificación de sesión que el frontend hace después de loguearse. Esto es
lo que hace la revocación "inmediata" (spec §2) sin tocar el JWT ni agregar
un mecanismo de blacklist de tokens — el próximo request del usuario ya
pasa por acá y ya lee `Licencia_Activa` fresco de la base.

```python
async def get_current_user(...) -> Usuario:
    ...
    usuario = await UsuarioRepository(session).get_by_username(payload["sub"])
    if usuario is None or usuario.estado != "Activo":
        raise AuthError("Usuario inválido o inactivo.")
    if not usuario.licencia_activa:          # nuevo
        raise LicenseRevokedError()          # nuevo
    set_actor(...)
    return usuario
```

**Corrección post outside-voice — `get_current_user_optional` NO es un
alias de `get_current_user`.** Verificado leyendo `deps.py:43-62`: es una
implementación INDEPENDIENTE (decodifica el token, resuelve el usuario,
chequea `estado`) que NO llama a `get_current_user` por dentro — parchear
solo `get_current_user` deja este segundo camino sin el chequeo de
licencia, lo cual **falsifica la premisa central del plan** ("sin licencia,
cero acceso, sin importar qué"): cualquier endpoint que use
`get_current_user_optional` (su propio docstring cita `JugadorPublicOut` —
PII que se expone distinto si hay sesión) le sigue dando acceso elevado a
una cuenta recién revocada mientras `Estado` siga en `'Activo'`. Fix:
extraer un helper compartido (`_resolver_usuario_autenticado(token,
session) -> Usuario | None`, con el chequeo de `estado` Y de
`licencia_activa` adentro) y hacer que AMBAS funciones lo llamen —
`get_current_user` relanza si es `None` (`AuthError`) o si viene sin
licencia (`LicenseRevokedError`, chequeado aparte porque el código de
error es distinto), `get_current_user_optional` simplemente propaga `None`
en cualquiera de los dos casos (falla silenciosa es su contrato ya
existente, no se le agrega uno nuevo). Este helper es DRY real, no
opcional: sin él, un tercer call site futuro repetiría el mismo bug.

**Login** (`POST /auth/login`) también debe rechazar con 403 si la
licencia está revocada, según spec §2 ("si intenta iniciar sesión"). Se
resuelve con el mismo chequeo, no una copia: `login()` ya valida
credenciales contra `UsuarioRepository`; se agrega el mismo `if not
usuario.licencia_activa: raise LicenseRevokedError()` ahí, reusando la
excepción/handler de arriba (no un chequeo nuevo). **Corrección
post outside-voice:** `services/usuario.py:152-161` deja documentado como
NO NEGOCIABLE que cada motivo de rechazo de login escribe una fila en
`ACCESOS` vía `_registrar_acceso(...)` ANTES de lanzar la excepción — el
chequeo de licencia debe clonar exactamente ese patrón, incluida la
llamada a `_registrar_acceso(usuario_id=usuario.id, username=...,
exitoso=False, motivo="licencia_revocada", ...)` en el mismo lugar donde
hoy vive el bloque de `estado != "Activo"`. Implementado como el plan
originalmente lo describía (solo el `raise`), los intentos de login con
licencia revocada desaparecerían silenciosamente de la bitácora de
accesos — exactamente el tipo de falla silenciosa que este mismo review
existe para atrapar.

### 4.3 Dependency de acceso por torneo — nuevo, junto a `require_roles`

`backend/app/api/deps.py`:

```python
def require_torneo_access() -> Callable:
    """AdminGeneral: bypass total (mismo criterio que require_roles).
    TorneoAdmin: exige una fila Activa en ASIGNACION_TORNEO_ADMIN para
    ESTE torneo_id. Cualquier otro rol: 403 (no debería llegar acá; las
    rutas que usan esto ya exigen TorneoAdmin/AdminGeneral río arriba)."""

    async def _checker(
        torneo_id: int,
        usuario: Usuario = Depends(get_current_user),
        session: AsyncSession = Depends(get_db),
    ) -> Usuario:
        if usuario.rol == "AdminGeneral":
            return usuario
        if usuario.rol != "TorneoAdmin":
            raise ForbiddenError("Esta operación requiere TorneoAdmin o AdminGeneral.")
        tiene_acceso = await AsignacionTorneoAdminRepository(session).existe_activa(
            usuario_id=usuario.id, torneo_id=torneo_id
        )
        if not tiene_acceso:
            raise ForbiddenError(
                "No tenés este torneo asignado. Pedile a tu Admin General "
                "que te lo asigne desde el panel de usuarios."
            )  # mensaje mejorado, ver DX REVIEW abajo
        return usuario

    return _checker
```

`get_current_user` ya cubre "sin licencia → 403" antes de que esto se
evalúe (la dependency chain de FastAPI resuelve `get_current_user` primero)
— `require_torneo_access` solo necesita preocuparse por la asignación, no
por la licencia otra vez.

### 4.4 Servicio nuevo: `AsignacionTorneoAdminService`

- `set_licencia(usuario_id, activa, actor)` → `AdminGeneral` únicamente
  (mismo `require_roles("AdminGeneral")` que ya gatea `PATCH /usuarios/{id}`).
  Bloquea auto-revocación (`if usuario_id == actor.id and not activa: raise
  ForbiddenError(...)`) — clon exacto del guard que ya existe para
  auto-desactivación/auto-cambio-de-rol en `UsuarioService.update()` (T6).
- `set_torneos_asignados(usuario_id, torneo_ids, actor)` → reemplaza el
  set completo (matchea la UX de "modal con checkboxes, guardar"): activa
  filas para los IDs entrantes, desactiva las que ya no están en el set
  nuevo. Valida `usuario.rol == "TorneoAdmin"` antes (400 si no — asignar
  torneos a un Árbitro o Publico no tiene sentido de negocio).

  **Corrección post outside-voice (Eng review, hallazgo #1 — ALTA
  severidad):** NO implementar el diff activar/desactivar llamando a
  `BaseRepository.update()`/`.create()` en un loop — verificado en
  `repositories/base.py:43-69`: `create()`, `update()` y `save_changes()`
  hacen `await self.session.commit()` CADA UNO, así que un loop sobre
  `BaseRepository` serían N commits separados, no una operación atómica.
  Un fallo de DB a mitad de loop deja el set de asignación parcialmente
  aplicado — contradice directamente lo que §9 de este plan promete
  ("el ganador debe ser determinístico... sin filas huérfanas"). El repo
  YA tiene el patrón correcto para esto: `services/inscripcion_torneo.py`
  (flujo de registro por lote, ~línea 143-277) hace `session.add()` por
  fila directamente y UN SOLO `session.commit()` al final, evitando
  `BaseRepository` a propósito para trabajo en lote. `set_torneos_asignados`
  debe clonar ESE patrón: cargar las filas existentes, mutarlas/crearlas
  con `session.add()`/`setattr()` sin pasar por `BaseRepository`, y un
  único `commit()` al final — atómico de verdad, y sigue cumpliendo la
  condición de auditoría gratis de §3.2 (mutación ORM, no Core).

### 4.5 Endpoints nuevos en `usuarios.py`

```
PATCH /usuarios/{id}/licencia    body: {activa: bool}     → AdminGeneral
GET   /usuarios/{id}/torneos                              → AdminGeneral | TorneoAdmin (self)
PATCH /usuarios/{id}/torneos     body: {torneo_ids: int[]} → AdminGeneral
```

**Corrección post outside-voice (Eng review, hallazgo #2 — ALTA
severidad):** el tercer endpoint es `PATCH`, no `PUT` como decía la
versión original de este plan — verificado en
`frontend/src/hooks/useResourceCrud.ts:107-124`: `customAction` (el
"escape hatch" que este plan asumía reusar, citado en §1 como "90% de
infraestructura ya existente") solo soporta `method?: "POST" | "PATCH"`,
sin rama para `PUT`. Con `PUT` en el contrato, el frontend simplemente NO
puede llamar a este endpoint con la infraestructura existente — habría
que extender el tipo de `customAction` para un único caller, exactamente
el tipo de superficie nueva no justificada que Section 5 (CEO, Code
Quality) ya rechaza en otro lado de este mismo documento. `PATCH` es
además consistente: es el verbo que TODO otro "reemplazo completo" de la
API ya usa.

**Segundo hallazgo (mismo finding, severidad menor):** `UsuariosAdminPage`
no tiene su propia instancia de `useResourceCrud` — `SimpleResourceAdminPage`
la posee internamente y no la expone a través de `columns[].render` ni
`renderRowExtra`. `ToggleLicencia`/`AsignarTorneosModal` (§5.3) necesitan
su PROPIA mutación (`useMutation` + invalidar la query de `usuarios`
manualmente), no la de `SimpleResourceAdminPage` — mismo patrón que ya
usan `PlantillasDelTorneoPage`/`EquiposDelTorneo` (páginas bespoke con su
propio `useResourceCrud`), pero estos SÍ viven embebidos dentro de una
página que usa `SimpleResourceAdminPage` para el resto, una composición
que ningún caso existente hace exactamente así. No bloqueante — la frase
original "no se toca `SimpleResourceAdminPage.tsx`/`ResourceTable.tsx`"
sigue siendo cierta (no se modifican esos 2 archivos), pero implica menos
cableado nuevo del que realmente hace falta. Anotado para que Fase 3 no
se sorprenda.

Reusan `require_roles("AdminGeneral")` ya existente en este router — no se
inventa un chequeo nuevo, mismo criterio literal que ya documenta el header
del archivo (`usuarios.py:10-23`) sobre por qué escritura exige
`AdminGeneral` sin el bypass uniforme que sí tienen los demás routers.

**Corrección post outside-voice:** `UsuarioOut` (`schemas/usuario.py:54-64`)
no expone `licencia_activa` hoy — sin agregarlo explícitamente, el toggle
del panel (§5.3) no tiene con qué pintar su estado inicial al cargar
`GET /usuarios`. Se agrega como campo más de `UsuarioOut`, mismo patrón
que `estado`.

### 4.6 Aplicar `require_torneo_access` a las rutas existentes

`torneos.py` (`PATCH`/`DELETE /{torneo_id}`, y `POST` no aplica — un
torneo nuevo no tiene asignación todavía, queda igual que hoy: cualquier
`TorneoAdmin` puede crear uno, y el creador se auto-asigna — decisión D4)
agrega `Depends(require_torneo_access())` junto al `require_roles`
existente.

**El resto de los routers gateados a `TorneoAdmin`** (`equipos`, `partidos`,
`inscripciones`, `grupos`, `fase`, `sorteos`, `traspasos`,
`motor_formatos`, `plantillas`, `registro_lote`, `eventos_partido`) reciben
el mismo patrón — pero varios no tienen `torneo_id` directo en el path
(cuelgan de `equipo_id`/`partido_id`/`inscripcion_id`, un salto indirecto
hasta `TORNEO`). Esto es blast radius real (12 routers) pero no todos son
`< 1 día` de esfuerzo — algunos necesitan resolver el `torneo_id` indirecto
antes de poder aplicar el mismo dependency. Se separa en **Fase 2** (§6),
no bloquea el kill switch de licencia ni la asignación N:M en `torneos.py`
(Fase 1), que son el corazón del pedido.

## 5. Frontend

### 5.1 Cliente API — segundo callback simétrico a `onUnauthorized`

`frontend/src/api/client.ts`:

```typescript
let onLicenseRevoked: (() => void) | null = null;
export function setOnLicenseRevoked(handler: (() => void) | null) {
  onLicenseRevoked = handler;
}

// dentro de onResponse, junto al chequeo de 401 existente:
if (response.status === 403 && response.headers.get("X-License-Revoked") === "true" && onLicenseRevoked) {
  onLicenseRevoked();
}
```

No requiere leer/clonar el body — el header ya es suficiente (§4.1).

### 5.2 `AuthContext` + pantalla de bloqueo

`AuthContext` registra `onLicenseRevoked` igual que ya registra
`onUnauthorized`, guarda un flag (`licenseRevoked: boolean`) en el estado
de sesión, y limpia la sesión (mismo efecto que un 401).

Nuevo componente `LicenseRevokedScreen.tsx` — clon del patrón de
`LoginPrompt` (`pages/Login.tsx`) referenciado por `RequireRole.tsx`:
pantalla completa, texto exacto del spec ("Licencia Inactiva o Revocada.
Contacte al administrador."), botón para volver a login.

`App.tsx` (donde ya se decide `onUnauthorized` → mostrar `LoginPrompt`)
agrega la misma rama para `licenseRevoked` → `LicenseRevokedScreen`.

### 5.3 Panel de Admin General — extiende `UsuariosAdmin.tsx`, no lo reemplaza

Sobre el `UsuariosAdmin.tsx` existente:

- **Columna de licencia con toggle**: nueva entrada en `columns` con
  `render: (row) => <ToggleLicencia usuario={row} />` — un `<input
  type="checkbox">` (o switch estilizado) que dispara `PATCH
  /usuarios/{id}/licencia` on-change, con confirmación si se está
  revocando la propia (aunque el backend ya lo bloquea — mismo criterio
  UX que `isSelf` ya oculta el botón de "Dar de baja" para uno mismo:
  ocultar/deshabilitar el toggle en la propia fila también, evitando el
  viaje redondo).
- **Botón "Gestionar torneos"** vía el slot `renderRowExtra` ya existente
  (precedente literal `equipos-jugadores-plan.md` Fase 2 Etapa D) — abre
  un modal, solo visible/habilitado cuando `row.rol === "TorneoAdmin"`
  (asignar torneos a un Árbitro no tiene sentido, §4.4).
- **Modal `AsignarTorneosModal.tsx`** (nuevo, chico): al abrir, `GET
  /usuarios/{id}/torneos` precarga el set actual; lista de checkboxes con
  TODOS los torneos activos (`GET /torneos`, ya público, ya existe);
  "Guardar" dispara `PATCH /usuarios/{id}/torneos` con el set completo
  tildado. Checkbox list nativa — no hay librería de multiselect instalada
  (§1) y no hace falta una para esto.

No se toca `SimpleResourceAdminPage.tsx` ni `ResourceTable.tsx` — ambos ya
exponen los slots necesarios.

## 6. Fases de implementación

- **Fase 1 — Núcleo (kill switch + asignación en `torneos.py`)**: columna
  `Licencia_Activa`, tabla `ASIGNACION_TORNEO_ADMIN` + trigger, chequeo en
  `get_current_user` + `login()`, `LicenseRevokedError`/handler,
  `require_torneo_access` aplicado a `torneos.py`, servicios + 3 endpoints
  nuevos en `usuarios.py`.
- **Fase 2 — Rollout a routers restantes**: aplicar `require_torneo_access`
  (o una variante que resuelva `torneo_id` indirecto) a los 12 routers
  listados en §4.6, uno por uno, con su propio test de "TorneoAdmin sin
  asignación recibe 403" por router (mismo espíritu que el test T3/T6 ya
  existente en `roles-3-modulos-plan.md`).
- **Fase 3 — Frontend**: cliente API, `AuthContext`, `LicenseRevokedScreen`,
  panel `UsuariosAdmin.tsx` (toggle + modal), y — dependiendo de qué tan
  lejos llegó Fase 2 — filtrar qué torneos ve un `TorneoAdmin` en las
  pantallas de `torneo-admin/*` (hoy probablemente listan todos).

Este plan (documento) cubre Fase 1 a nivel de diseño completo; Fases 2-3
quedan esqueletizadas para que Eng review las desglose en tareas.

## 7. Decisiones (D1-D5)

- **D1 — Licencia como columna, no tabla con historial.** Ver §3.1.
  Alternativa rechazada: tabla `LICENCIAS(Usuario_ID, Otorgada_Por,
  Fecha_Otorgada, Fecha_Revocada, ...)` — duplica lo que `AUDITORIA` ya da
  gratis vía el listener de sesión.
- **D2 — ¿La licencia aplica también a `AdminGeneral`, `Arbitro` y
  `Publico`, o solo a `TorneoAdmin`/`AdminGeneral`?** **RESUELTO en el
  Final Approval Gate: D2a — uniforme a las 4 cuentas** (decisión
  explícita del usuario, no auto-decidida — ver §11 y el Final Approval
  Gate al final del documento). Recomendado
  originalmente: sí, de forma uniforme a las 4. **Tensión cross-model
  (CEO review vs. outside voice):** la voz externa marca que esto duplica
  `Estado` (Activo/Inactivo) — que YA es un kill switch de cuenta,
  chequeado en el mismo `get_current_user`/`login()` — para `Arbitro` y
  `Publico`, que no tienen nada que ver con licenciar administración de
  torneos (el spec §0 enmarca la licencia explícitamente como "kill switch
  de nivel superior" sobre gestión de torneos). Dos booleans haciendo
  esencialmente lo mismo (bloquear acceso) para esos 2 roles es una fuente
  de verdad duplicada que puede desincronizarse y duplica superficie de
  test sin necesidad. **Este documento no resuelve esto — queda como
  decisión abierta para el gate final** (ver Riesgos, §11) con dos
  variantes concretas:
  - **D2a (uniforme, como estaba):** columna aplica a las 4 cuentas,
    chequeo en `get_current_user`/`login()` sin excepción de rol. Pro:
    "cualquier cuenta" del spec se cumple literal. Con: kill switch
    redundante con `Estado` para Arbitro/Publico.
  - **D2b (columna uniforme, chequeo scoped):** se guarda
    `licencia_activa` en las 4 cuentas por simplicidad de esquema (mismo
    `ALTER TABLE`), pero el chequeo en `get_current_user`/`login()` solo
    aplica si `usuario.rol in ("TorneoAdmin", "AdminGeneral")` — Arbitro/
    Publico ignoran la columna por completo (queda en `TRUE` siempre para
    ellos, sin uso). Pro: sin duplicar el kill switch donde no aplica. Con:
    la columna existe pero no hace nada para 2 de los 4 roles — dead data
    si `AdminGeneral` intenta usar el toggle sobre un Arbitro sin efecto
    visible, salvo que la UI también lo oculte para esos roles.
  El guard de auto-revocación (§4.4) aplica igual bajo cualquiera de las
  dos.
- **D3 — Header vs. body para distinguir el 403 de licencia.** Recomendado:
  header `X-License-Revoked` (§4.1), clonando el precedente de
  `RateLimitError`/`Retry-After`. Alternativa: campo `code` en el JSON body
  — más "RESTful", pero obliga a `response.clone().json()` en un
  middleware que hoy es sincrónico sobre el objeto `Response`, y este repo
  ya resolvió el mismo problema con un header antes.
- **D4 — `POST /torneos` (creación) no exige asignación previa.** No puede
  exigirla (el torneo no existe todavía). Alternativa considerada:
  auto-asignar al creador en la misma transacción (`TorneoService.create`
  inserta también la fila en `ASIGNACION_TORNEO_ADMIN`) — **recomendado,
  con guard obligatorio (corrección post outside-voice)**: `POST /torneos`
  hoy exige `Depends(require_roles("TorneoAdmin"))`, pero el bypass de
  `require_roles` (`deps.py:76-78`) deja pasar también a `AdminGeneral` —
  es un camino que funciona HOY. Si el auto-insert se hace incondicional,
  un `AdminGeneral` creando un torneo dispara
  `fn_validar_asignacion_torneo_admin_rol` (§3.2, que rechaza
  `Usuario_ID` con `Rol <> 'TorneoAdmin'`) y la creación **falla** — una
  regresión real sobre un flujo que hoy anda. El auto-insert debe ir
  **guardado**: `if usuario_actual.rol == "TorneoAdmin":
  insertar_asignacion(...)` — para `AdminGeneral` no se inserta nada (ya
  tiene bypass total vía `require_torneo_access`, §4.3, no necesita fila).
  Esto también expone un cambio de firma no mencionado originalmente:
  `crear_torneo` (`torneos.py:32-34`) hoy NO resuelve
  `Depends(get_current_user)` y `TorneoService.create(self, data:
  TorneoCreate)` (`services/torneo.py:67`) no recibe actor — ambos
  necesitan el parámetro agregado para poder guardar la condición de
  arriba.
- **D5 — Alcance de Fase 1 vs. Fase 2 (§4.6, §6).** Aplicar
  `require_torneo_access` a los 12 routers restantes en la misma pasada
  vs. separarlo. Recomendado: separar (Fase 2) — varios routers no tienen
  `torneo_id` directo en el path y requieren resolverlo primero (join
  hasta `TORNEO`), lo que no es un cambio mecánico de <1 día por router.

## 8. NOT in scope (este plan)

- Multi-licencia o licencias con expiración temporal (spec pide on/off,
  no "licencia válida hasta fecha X").
- Notificar al usuario afectado (email/push) cuando se le revoca la
  licencia — el spec solo pide que el próximo intento de acceso falle con
  403 + pantalla, no una notificación proactiva.
- Auditoría/UI dedicada de "historial de licencia" — cubierto por
  `AUDITORIA` genérica (§1), sin pantalla propia (mismo nivel que
  cualquier otro campo auditado hoy, que tampoco tiene UI dedicada).
- Resolver el `torneo_id` indirecto de los 12 routers de Fase 2 (queda
  esqueletizado, no diseñado a nivel de código en este documento).
- Filtrado del listado de torneos visibles en las pantallas de
  `torneo-admin/*` para que un `TorneoAdmin` solo vea los suyos (Fase 3,
  depende de qué tan lejos llegue Fase 2).
- Roles adicionales o jerarquía de licencia por rol (ej. licencia que solo
  aplica a `TorneoAdmin` pero no a `Arbitro`) — el spec no lo pide, D2
  decide aplicarla uniforme a toda cuenta autenticada.

## 9. Registro de fallos / edge cases

| Escenario | Comportamiento esperado | Cubierto por |
|---|---|---|
| `TorneoAdmin` con licencia activa pero sin asignación al torneo X | 403 "No tenés este torneo asignado" | `require_torneo_access` (§4.3) |
| `TorneoAdmin` con asignación al torneo X pero licencia revocada | 403 "Licencia inactiva o revocada" (la licencia gana, spec §2) | `get_current_user` corta ANTES de llegar a `require_torneo_access` (§4.2) |
| `AdminGeneral` revoca su propia licencia | 403 bloqueado en el service, no llega a escribir | `set_licencia` guard (§4.4), clon de T6 |
| `AdminGeneral` revoca la licencia de otro `AdminGeneral` | Permitido (D2) — el otro pierde acceso en su próximo request | `get_current_user` |
| Login con licencia revocada | 403 (no 401) en `POST /auth/login`, mismo mensaje | §4.2 |
| Token válido, sesión activa, licencia revocada a mitad de sesión | Próximo request del usuario devuelve 403 de inmediato (sin esperar expiración del JWT) | `get_current_user` lee `Licencia_Activa` fresco por request (§4.2) |
| `TorneoAdmin` intenta `PATCH /usuarios/{id}/torneos` sobre sí mismo o sobre otro | 403 — endpoint exige `AdminGeneral` literal, sin bypass de "self" | `require_roles("AdminGeneral")` (§4.5) |
| Asignar un torneo a un usuario con `Rol != 'TorneoAdmin'` | 400/db-trigger rechaza | `fn_validar_asignacion_torneo_admin_rol` (§3.2) + validación de service (§4.4) |
| Revocar y re-otorgar la misma asignación repetidamente | No acumula filas — `UNIQUE(Usuario_ID, Torneo_ID)`, flip de `Estado` | §3.2 |
| `AdminGeneral` navega a un torneo sin asignación propia | Acceso total igual (bypass, mismo criterio que `require_roles`) | `require_torneo_access` (§4.3) |

## 10. Plan de pruebas (esqueleto — Eng review lo completa)

- Backend: test de `require_torneo_access` (asignado/no asignado/AdminGeneral
  bypass), test de `LicenseRevokedError` en `login()` y en cualquier ruta
  protegida, test de auto-revocación bloqueada, test del trigger de rol en
  `ASIGNACION_TORNEO_ADMIN`, test de que `AUDITORIA` captura el cambio de
  `Licencia_Activa` y de filas de asignación (verifica que el listener
  genérico realmente cubre las tablas nuevas sin configuración extra).
- Frontend: test de `client.ts` disparando `onLicenseRevoked` en un 403
  con el header, test de `LicenseRevokedScreen` renderizando el texto
  exacto del spec, test de `UsuariosAdmin.tsx` con el toggle + modal
  (mock de los 3 endpoints nuevos).

## 11. Riesgos / preguntas abiertas para el gate final

1. ~~**D2 (User Challenge / tensión cross-model)**~~ — **RESUELTO:** el
   usuario eligió **D2a — uniforme a las 4 cuentas** en el Final Approval
   Gate (2026-09-02). La columna `Licencia_Activa` se chequea sin
   excepción de rol en `get_current_user`/`get_current_user_optional`/
   `login()` — sin scoping a TorneoAdmin/AdminGeneral únicamente.
2. D4 (auto-asignar al creador de un torneo) — **ya resuelto** con el
   guard de rol (corrección post outside-voice arriba); confirmar con el
   usuario que el comportamiento resultante (AdminGeneral crea sin
   auto-asignación, TorneoAdmin sí) es el esperado.
3. Alcance de Fase 2 (§4.6) — 12 routers es blast radius real; confirmar
   si el usuario quiere eso en el mismo ciclo de trabajo o como backlog
   separado en `TODOS.md`.

---

## 12. Fase 2 + Fase 3 — lo que se implementó de verdad (post-plan)

El §6 original esqueletizaba Fase 2/3 sin diseño a nivel de código. Esto
documenta lo que se construyó, porque el conteo/lista original ("12
routers", "equipos, partidos, inscripciones, grupos, fase, sorteos,
traspasos, motor_formatos, plantillas, registro_lote, eventos_partido")
no era exacto — verificado contra el código real al implementar, no
contra la memoria del plan.

### 12.1 Los 15 routers gateados a `TorneoAdmin` fuera de `torneos.py`, clasificados

Verificado leyendo cada router + su modelo (`grep require_roles("TorneoAdmin"`
en `backend/app/api/routes/`), no asumido:

| Router | torneo_id | Hops | Compartido con Árbitro | Decisión |
|---|---|---|---|---|
| `inscripciones.py` | Directo (body/entidad) | 0-1 | No | ✅ Scoped |
| `partidos.py` | Directo (Partido.torneo_id) | 0-1 | Sí (varias rutas) | ✅ Scoped |
| `motor_formatos.py` | Directo (path param) | 0 | No | ✅ Scoped |
| `plantillas.py` | Vía `InscripcionTorneo` | 1-2 | No | ✅ Scoped |
| `traspasos.py` | Vía `InscripcionTorneo` (destino) | 1-2 | No | ✅ Scoped |
| `registro_lote.py` | Vía `InscripcionTorneo` | 1 | No | ✅ Scoped |
| `grupos.py` | Vía `GrupoEquipo.inscripcion_torneo_id` | 1 | No | ✅ Scoped |
| `eventos_partido.py` | Vía `Partido` | 1-2 | Sí (todas las rutas) | ✅ Scoped |
| `equipos.py` | — | — | No | ❌ Sin scoping (pool compartido, "sin dueño" — comentario propio del código) |
| `jugadores.py` | — | — | No | ❌ Sin scoping (catálogo global cross-torneo) |
| `perfiles.py` | — | — | No | ❌ Sin scoping (perfil por disciplina, no por torneo) |
| `disciplinas.py` | — | — | No | ❌ Sin scoping (catálogo global) |
| `modalidades.py` | — | — | No | ❌ Sin scoping (catálogo global) |
| `eventos.py` | — | — | No | ❌ Sin scoping (catálogo de tipos de evento, no de partidos) |
| `torneo_grupos.py` | Ambiguo — spans ediciones | — | No | ❌ Sin scoping (una franquicia de ediciones no tiene un `torneo_id` único; ver §12.3) |

**Decisión del usuario (Final Gate de esta sub-fase, no auto-decidida):**
dejar los 7 routers de la columna "❌" tal como estaban — forzar un
`torneo_id` sobre un recurso que a propósito no tiene uno rompería ese
diseño, no lo completaría. Quedan con `require_roles("TorneoAdmin")`
solo, igual que hoy.

### 12.2 Infraestructura nueva en `deps.py`

- `_verificar_acceso_torneo(usuario, torneo_id, session, roles_sin_scoping)`
  — núcleo compartido, extraído de la versión original de
  `require_torneo_access` (§4.3) para que ambas variantes de abajo lo
  reusen sin duplicar la lógica AdminGeneral-bypass / TorneoAdmin-scoped.
- `require_torneo_access(*roles_sin_scoping)` — la de §4.3, ahora acepta
  roles que pasan sin scoping (ej. `require_torneo_access("Arbitro")` en
  `partidos.py`/`eventos_partido.py`: Árbitro ya tiene su propio
  ownership-check en el Service, D5 de `roles-3-modulos-plan.md` —
  aplicarle además el scoping de TorneoAdmin sería un bug, no un refuerzo).
- `require_torneo_access_de(resolver, *roles_sin_scoping)` — nueva, para
  rutas donde `torneo_id` no es un path param directo. `resolver` es un
  callable async con sus propios params (path o body, vía el mecanismo
  normal de FastAPI `Depends`) que devuelve el `torneo_id` resuelto. Cada
  router define sus propios resolvers, co-ubicados (no centralizados en
  `deps.py`, que ensuciaría ese archivo con imports de todo el dominio).

### 12.3 Fase 3 — filtrado sin tocar `torneo_grupos.py`

`TorneosAdminPage` (el listado que ve un TorneoAdmin al entrar a
`/torneo-admin`) consulta `GET /torneo-grupos`, no `GET /torneos` — una
`TorneoGrupo` es una franquicia con múltiples ediciones (`Torneo`), así
que "¿este grupo es mío?" no tiene una respuesta de un solo `torneo_id`
(el mismo problema ambiguo de §12.1 para ese router).

Resuelto en el cliente, no en el backend: `TorneosAdminPage` pide además
`GET /torneos?solo_mios=true` (E1, ya existente desde Fase 1) y filtra los
grupos localmente — un grupo se muestra si AL MENOS UNA de sus ediciones
está en el set devuelto. `torneo_grupos.py` queda intacto, consistente con
§12.1. Mientras la query de "mis torneos" está en vuelo, no se filtra
(evita el flash de "no tenés torneos" antes de que llegue el dato real) —
se angosta solo una vez que resuelve, nunca al revés. AdminGeneral (o sin
sesión) ve todo, sin filtro — la query ni se dispara (`enabled:
session?.rol === "TorneoAdmin"`).

---

# CEO REVIEW (autoplan Phase 1)

Mode: **SELECTIVE EXPANSION** (context-dependent default — esto es una
mejora/feature nueva sobre un sistema existente y activamente desarrollado,
no un producto greenfield ni un bugfix). Codex no disponible en este
entorno (`codex` no está en el PATH) — la segunda voz corre como
subagente Claude con contexto fresco (mismo modelo, no un modelo externo).

## Step 0

### 0A — Premise Challenge

1. **¿Es el problema correcto?** Sí, sin vuelta — hoy `TorneoAdmin` es
   literalmente un rol global (verificado en `torneos.py`, ninguna ruta de
   escritura chequea `torneo_id`), y eso es una brecha de seguridad real, no
   hipotética: cualquier cuenta `TorneoAdmin` que se filtre o se cree por
   error administra TODOS los torneos, no solo los suyos. El framing del
   spec (N:M + kill switch) es el mínimo correcto para cerrarla.
2. **¿Es el output real el que se pide, o un proxy?** El output real es
   "un `TorneoAdmin` comprometido/malicioso tiene blast radius acotado a
   SUS torneos, y un `AdminGeneral` puede cortar el acceso de cualquiera al
   instante." La licencia y la asignación N:M son ambas necesarias para
   eso — ninguna sola alcanza (licencia sin asignación = todo o nada por
   cuenta, sin granularidad de torneo; asignación sin licencia = sin kill
   switch de emergencia).
3. **¿Qué pasa si no se hace nada?** El código ya tiene el comentario que
   lo dice explícito (`permisos.py:9`: "TorneoAdmin y AdminGeneral nunca
   pasan por acá con una restricción real") — es una brecha conocida,
   documentada en el propio código, no descubierta ahora.

### 0B — Existing Code Leverage

Ya cubierto en detalle en §1 del plan (tabla de 12 filas, cada una con
archivo:línea). No se repite acá — es la sección más fuerte del documento
tal como está: cada pieza de infraestructura reusada está verificada
leyendo el código, no asumida.

### 0C — Dream State Mapping

```
  CURRENT STATE                       THIS PLAN                         12-MONTH IDEAL
  ────────────────                    ─────────                        ──────────────
  TorneoAdmin = rol global.           + Licencia_Activa (kill           RBAC completo:
  Cualquier cuenta con ese rol          switch, un choke point).        cada superficie
  administra CUALQUIER torneo.        + ASIGNACION_TORNEO_ADMIN         admin-facing
                                         (N:M, torneos.py).             (12 routers)
  Sin licencia: dar de baja           + Panel Admin General             respeta
  (Estado='Inactivo') es la           (toggle + modal).                 asignación
  única forma de cortar acceso,                                         real de torneo,
  y es total (pierde TODO acceso,     Fase 2/3 (fuera de este           no solo rol.
  no solo administrar torneos).       documento): rollout del
                                      mismo dependency a los            AdminGeneral
                                      12 routers restantes +            tiene un panel
                                      filtrado de UI.                   operable de
                                                                        "quién puede
                                                                        tocar qué",
                                                                        no solo un
                                                                        toggle binario.
```

Este plan (Fase 1) mueve directamente hacia el ideal — no es un parche
que haya que deshacer después. La forma de datos (`ASIGNACION_TORNEO_ADMIN`
N:M genérica, no acoplada a `torneos.py`) es la misma forma que Fase 2
reutiliza sin cambios de esquema.

### 0C-bis — Implementation Alternatives

```
APPROACH A: Columna + tabla de asignación (el plan tal como está)
  Summary: Licencia_Activa en USUARIOS, tabla N:M ASIGNACION_TORNEO_ADMIN,
           un dependency nuevo (require_torneo_access), reuso total de
           AUDITORIA/require_roles/RequireRole existentes.
  Effort:  S (Fase 1) — ~8 archivos backend, ~5 frontend.
  Risk:    Low — aditivo, DEFAULT TRUE, nada rompe el día del deploy.
  Pros:    Cero dependencias nuevas; reusa el 90% de la infraestructura de
           auth ya existente; migración reversible con un DROP.
  Cons:    No generaliza a "otros tipos de permiso" más allá de
           torneo-por-usuario — si mañana aparece un tercer objeto
           asignable (ej. "Disciplina"), esto no lo cubre gratis.
  Reuses:  get_current_user, require_roles, AUDITORIA, RequireRole,
           SimpleResourceAdminPage/ResourceTable, patrón Retry-After.

APPROACH B: Tabla de permisos genérica (RBAC/ABAC completo)
  Summary: Tabla PERMISOS(Usuario_ID, Recurso_Tipo, Recurso_ID, Accion) —
           un modelo de autorización genérico que cubriría torneos HOY y
           cualquier otro recurso asignable mañana sin migración nueva.
  Effort:  L — nuevo motor de evaluación de permisos, nueva UI genérica de
           gestión de permisos (no un toggle simple), migración de los 12
           routers a consultar el motor en vez de `require_roles`.
  Risk:    Med — over-engineering real: hoy hay UN SOLO tipo de recurso
           asignable (Torneo). Un motor genérico para N=1 caso es la
           definición de abstracción prematura (Section 5 lo marcaría).
  Pros:    Extensible a cualquier recurso futuro sin otra migración de
           esquema; UI de permisos reusable para lo que venga después.
  Cons:    3-5x el esfuerzo de A para resolver el MISMO problema de hoy;
           el spec no pide esto — pide específicamente Torneo + Licencia.
  Reuses:  Mucho menos — el motor de evaluación es código nuevo desde cero,
           no reusa el patrón `require_roles`/`Depends` tal como existe.

RECOMMENDATION: Approach A porque el spec pide exactamente esto (torneos +
licencia, no un motor de permisos genérico), la Sección 5 de esta misma
revisión marcaría B como over-engineering para N=1 tipo de recurso, y A
reusa 90% de infraestructura ya construida vs. B que construye un motor
paralelo. Si en el futuro aparece un segundo tipo de recurso asignable
(ej. Disciplinas, Ligas), ESE es el momento de generalizar — YAGNI hasta
entonces. Completeness: A=9/10 (cubre el 100% del spec), B=10/10 (cubre el
spec + hipotéticos futuros no pedidos) — pero completeness no es el eje
correcto acá: B es completeness sobre un problema que no existe todavía.
```

**Auto-decidido (autoplan, Principio 5 — Explicit over clever): Approach
A.** Registrado en el Decision Audit Trail al final de este documento.

### Mode-specific analysis (SELECTIVE EXPANSION)

1. **Complexity check:** Fase 1 toca 8 archivos backend + 5 frontend — por
   debajo del umbral de "smell" (>8 backend, >2 clases/servicios nuevos).
   Clases nuevas: 1 excepción (`LicenseRevokedError`), 1 servicio
   (`AsignacionTorneoAdminService`), 1 repositorio — dentro de rango.
2. **Mínimo set de cambios:** Ya es el mínimo — no hay grasa que cortar sin
   perder alcance del spec (licencia + asignación + panel son los 3
   requerimientos explícitos, ninguno es opcional).
3. **Cherry-pick scan** (candidatos, no agregados a scope todavía):

   - **E1 — `GET /torneos?solo_mios=true`** filtra a los torneos asignados
     cuando el caller es `TorneoAdmin` (bypass total para `AdminGeneral`,
     sin cambio para llamadas públicas/anónimas). Effort: S (mismo router,
     mismo servicio, reusa `AsignacionTorneoAdminRepository` de Fase 1).
     Risk: Low. **Por qué importa:** sin esto, el panel de un `TorneoAdmin`
     seguiría listando TODOS los torneos del sistema (aunque no pueda
     escribir en los que no son suyos) — el spec da el ejemplo "Snoopy
     tiene A,B,C,D; Oscar solo Z", que implícitamente pide que Oscar VEA
     solo Z, no que vea todo y le rebote al tocar los demás.
   - **E2 — Auto-asignar al creador de un torneo** (`POST /torneos`
     inserta también la fila de asignación). Ya está en el plan como D4
     recomendado — se formaliza acá como parte del scope base, no un
     cherry-pick separado.
   - **E3 — Rollout de `require_torneo_access` a los 12 routers restantes**
     (Fase 2 completa, no solo torneos.py). Effort: L (varios routers no
     tienen `torneo_id` directo — join indirecto). **No** es <1 día por
     router, así que no califica para auto-aprobación aunque esté en blast
     radius directo del problema que este plan resuelve.
   - **E4 — Vista inversa "qué usuarios tienen este torneo asignado"** en
     la pantalla de edición de un Torneo (para que un `TorneoAdmin` vea con
     quién comparte el torneo, ej. Mónica ve que comparte el Torneo A con
     Snoopy). El spec no lo pide explícitamente (solo pide el panel de
     Admin General), y es una superficie nueva de UI no trivial.
   - **E5 — Alertar/loggear específicamente revocaciones de licencia**
     (más allá de lo que ya captura `AUDITORIA`). Se resuelve en Sección 8
     (Observabilidad) más abajo, no como item de scope aparte.

   **Decisiones (auto-decididas, Principio 2 — Boil lakes: blast radius +
   <1 día = auto-aprobado; si no, TODOS.md):**
   | # | Propuesta | Effort | Decisión | Razón |
   |---|---|---|---|---|
   | E1 | `GET /torneos?solo_mios=true` | S | **ACCEPTED** — agregado al scope de Fase 1 | Blast radius directo (mismo router/servicio), <1 día, cierra un gap de UX que el propio ejemplo del spec implica |
   | E2 | Auto-asignar creador (D4) | S | **ACCEPTED** — ya era parte del scope base | Sin esto un TorneoAdmin crea un torneo que no puede administrar — contradice el flujo natural |
   | E3 | Rollout Fase 2 (12 routers) | L | **DEFERRED → TODOS.md** | No es <1 día por router; ya estaba correctamente separado como Fase 2 en el plan original (D5) |
   | E4 | Vista inversa usuario↔torneo | S | **SKIPPED** | El spec no lo pide; agrega superficie de UI no solicitada (Focus as subtraction — hacer menos, mejor) |
   | E5 | Alertas específicas de licencia | — | Resuelto en Sección 8 (no es un item de scope aparte) | — |

E1 se incorpora al plan (ver adenda en §4.6/§5.3 abajo). El resto de este
review evalúa el plan CON E1 y E2 incluidos.

### 0E — Temporal Interrogation

```
  HOUR 1 (foundations):    Migración (columna + tabla + trigger + índices)
                            y el ORM model de la tabla nueva DEBEN usar
                            session.add()/setattr() estándar, NUNCA
                            session.execute(insert(...)) — si no, AUDITORIA
                            no los captura (ver core/auditoria.py: el
                            listener solo ve session.new/session.dirty,
                            que son poblados por el patrón ORM, no por
                            Core statements). Esto hay que decidirlo AHORA,
                            no descubrirlo en code review.
  HOUR 2-3 (core logic):   La resolución del orden de Depends() en FastAPI
                            (get_current_user corre antes que
                            require_torneo_access porque este último lo
                            declara como su propia dependencia) — confirmar
                            esto con un test explícito, no asumir el orden.
  HOUR 4-5 (integration):  El middleware de client.ts lee un header en
                            TODA respuesta — confirmar que el 403 de
                            require_roles() genérico (sin licencia
                            revocada) NO trae por accidente el header
                            X-License-Revoked (debe ser exclusivo del
                            handler de LicenseRevokedError).
  HOUR 6+ (polish/tests):  El toggle de licencia en UsuariosAdmin.tsx
                            necesita optimistic UI o loading state por fila
                            — sin eso, doble-click en el toggle dispara 2
                            PATCH concurrentes (Sección 4 lo cubre).
```

Con CC + gstack: ~6 horas humanas de Fase 1 comprimen a ~30-45 minutos de
implementación real. Las decisiones de arriba son las que hay que resolver
en el plan, no durante el código.

## Review Sections (11)

### Section 1 — Architecture Review

**Dependency graph (nuevo vs. existente):**
```
  ┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────┐
  │  client.ts       │────▶│  onResponse           │────▶│ onLicenseRevoked │ (nuevo,
  │  (existente)     │     │  (existente, +1 rama) │     │  callback nuevo) │  simétrico
  └─────────────────┘     └──────────────────────┘     └─────────────────┘  a onUnauthorized
           │                                                      │
           ▼                                                      ▼
  ┌─────────────────┐                                   ┌──────────────────┐
  │  AuthContext     │◀──────────────────────────────────│ LicenseRevoked   │ (nuevo)
  │  (existente,     │                                   │ Screen.tsx       │
  │  +1 estado)      │                                   └──────────────────┘
  └─────────────────┘

  ── backend ──
  ┌─────────────────┐     ┌───────────────────┐     ┌────────────────────────┐
  │ get_current_user │────▶│ Licencia_Activa?   │────▶│ LicenseRevokedError     │ (nuevo)
  │ (existente,      │     │ (nuevo check)      │     │ → handler → header      │
  │  +1 check)       │     └───────────────────┘     └────────────────────────┘
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────────┐     ┌─────────────────────────────┐
  │ require_torneo_access │────▶│ AsignacionTorneoAdminRepo    │ (nuevo)
  │ (nuevo, junto a       │     │ → ASIGNACION_TORNEO_ADMIN     │
  │  require_roles)       │     └─────────────────────────────┘
  └───────────┬───────────┘
              │
              ▼
     torneos.py (PATCH/DELETE, +GET ?solo_mios) — único router tocado en Fase 1
```

**Security architecture — quién puede llamar qué, qué obtiene, qué puede
cambiar:**

| Endpoint | Quién | Qué ve/obtiene | Qué puede cambiar |
|---|---|---|---|
| `PATCH /usuarios/{id}/licencia` | `AdminGeneral` (no self si `activa=false`) | — | `Licencia_Activa` de cualquier cuenta salvo la propia al revocar |
| `GET /usuarios/{id}/torneos` | `AdminGeneral` \| `TorneoAdmin` (solo self) | Set de torneos asignados a `id` | — (solo lectura) |
| `PATCH /usuarios/{id}/torneos` | `AdminGeneral` | — | Set completo de asignaciones de `id` |
| `PATCH/DELETE /torneos/{id}` | `AdminGeneral` (bypass) \| `TorneoAdmin` asignado | — | El torneo, si está asignado |
| `GET /torneos?solo_mios=true` (E1) | Cualquier autenticado | Lista filtrada si `TorneoAdmin`, completa si no | — (solo lectura) |

**Coupling:** `torneos.py` pasa de depender solo de `require_roles` a
depender también de `AsignacionTorneoAdminRepository` — coupling nuevo pero
justificado (es exactamente el propósito del cambio). No hay coupling
accidental: el repo nuevo no se filtra a routers que no lo necesitan.

**Scaling:** `get_current_user` ya trae la fila completa de `USUARIOS` — el
chequeo de licencia es un campo más en la MISMA fila, cero queries extra.
`require_torneo_access` agrega **una** query indexada
(`Usuario_ID + Torneo_ID`, índice compuesto implícito por `UNIQUE`) por
request de escritura de un `TorneoAdmin` — a 10x o 100x load, esto escala
igual que cualquier otro lookup indexado del sistema (no es distinto de
`verificar_arbitro_asignado`, que ya hace lo mismo para partidos). **OK,
sin hallazgos.**

**SPOFs:** Ninguno nuevo — misma base Postgres que todo el sistema.

**Production failure scenarios:** Caída de conexión a DB durante el
chequeo de licencia → mismo failure mode que CUALQUIER request autenticado
hoy (`get_current_user` ya depende de una query a `UsuarioRepository`) — no
es una superficie nueva de fragilidad, es la misma.

**Rollback posture:** Fase 1 es 100% aditiva — `DEFAULT TRUE` en la
columna, tabla nueva sin FKs entrantes desde tablas existentes. Rollback =
`git revert` del código + (opcional) `DROP TABLE
ASIGNACION_TORNEO_ADMIN; ALTER TABLE USUARIOS DROP COLUMN Licencia_Activa;`
— sin pérdida de datos de negocio preexistente. Ventana de rollback: minutos,
no hay migración de datos que deshacer.

**SELECTIVE EXPANSION — ¿E1 encaja limpio arquitectónicamente?** Sí — reusa
`AsignacionTorneoAdminRepository` sin cambios, agrega un query param opcional
a un endpoint ya público. Cero coupling nuevo más allá del ya aceptado.

**Diagrama de arquitectura completo:** ver el grafo de arriba — cubre
componentes nuevos y su relación con los existentes tal como pide esta
sección.

### Section 2 — Error & Rescue Map

| Método/Codepath | Qué puede salir mal | Exception class |
|---|---|---|
| `get_current_user` (chequeo licencia) | Licencia revocada | `LicenseRevokedError` (nueva) |
| `login()` (chequeo licencia) | Licencia revocada | `LicenseRevokedError` (nueva, reusada) |
| `require_torneo_access._checker` | Rol no asignado a este torneo | `ForbiddenError` (existente) |
| `require_torneo_access._checker` | Rol distinto de TorneoAdmin/AdminGeneral | `ForbiddenError` (existente) |
| `AsignacionTorneoAdminRepository.existe_activa` | Pool de conexiones agotado | `DBAPIError`/`OperationalError` (SQLAlchemy) |
| `set_licencia` (servicio) | Auto-revocación | `ForbiddenError` (existente, clon T6) |
| `set_torneos_asignados` (servicio) | `usuario.rol != 'TorneoAdmin'` | `DomainRuleError` (existente, nueva instancia) |
| Trigger `fn_validar_asignacion_torneo_admin_rol` | Insert con `Usuario_ID` de rol incorrecto | `RAISE EXCEPTION` → `DBAPIError` (Postgres, ya traducido por `_dbapi_error_response` existente) |
| `PATCH /usuarios/{id}/torneos` | `torneo_ids` con un ID inexistente | `NotFoundError` (existente) — **GAP, ver abajo** |
| Insert en `ASIGNACION_TORNEO_ADMIN` fuera del flujo de "reemplazo de set" | Duplicado (`Usuario_ID`, `Torneo_ID`) | `IntegrityError` → 409 (existente, genérico) |

| Exception class | ¿Rescatada? | Acción de rescate | Qué ve el usuario |
|---|---|---|---|
| `LicenseRevokedError` | Y (nuevo handler) | 403 + header `X-License-Revoked` | Pantalla "Licencia Inactiva o Revocada..." |
| `ForbiddenError` (asignación/rol) | Y (handler existente) | 403 genérico | Mensaje `detail` legible ("No tenés este torneo asignado.") |
| `DBAPIError` (pool agotado) | Y (handler existente, genérico) | 400 con mensaje limpio | Mensaje de Postgres traducido — **preexistente, no introducido por este plan**: un pool agotado debería ser 503, no 400, pero es el MISMO comportamiento que cualquier otro endpoint hoy (no es una regresión de este plan, es un gap heredado — no se corrige acá, fuera de blast radius) |
| `DomainRuleError` | Y (handler existente) | 400 | Mensaje de negocio |
| `NotFoundError` (torneo_id inválido en `torneo_ids`) | **N ← GAP** | — | Sin este chequeo explícito en el servicio, un ID inexistente en el array simplemente no matchea ningún `Torneo.ID` al hacer el upsert — según cómo se implemente el bulk-upsert, esto puede fallar silenciosamente (no crea la fila, no avisa) en vez de devolver 404/400 con el ID culpable |
| `IntegrityError` (duplicado) | Y (handler existente) | 409 | No debería ocurrir en operación normal (el servicio hace upsert idempotente por diseño, §4.4) — solo si dos requests concurrentes de `PATCH /usuarios/{id}/torneos` para el mismo usuario corren en paralelo (Sección 4 lo cubre) |

**GAP real identificado:** `set_torneos_asignados` debe validar explícitamente
que cada ID en `torneo_ids` exista (`TorneoRepository.get_many` o similar) y
devolver `NotFoundError` con el/los ID(s) culpables ANTES de tocar la tabla
de asignación — no dejar que un ID basura se pierda silenciosamente en un
bulk upsert. Anotado como tarea (T-gap1 abajo).

### Section 3 — Security & Threat Model

| Amenaza | Likelihood | Impact | ¿Mitigada? |
|---|---|---|---|
| `TorneoAdmin` sin licencia sigue operando por token viejo | Low (el chequeo es por-request, no por-token) | High si no mitigada | **Sí** — `get_current_user` lee `Licencia_Activa` fresco de DB en cada request, no hay caching de esa columna |
| `TorneoAdmin` administra un torneo no asignado manipulando el `torneo_id` en la URL | Med (trivial de intentar) | High si no mitigada | **Sí** — `require_torneo_access` valida contra la tabla de asignación, no confía en el path param solo |
| IDOR en `PATCH /usuarios/{id}/torneos` (un `TorneoAdmin` se auto-asigna torneos) | Low | High si no mitigada | **Sí** — endpoint exige `AdminGeneral` literal, sin excepción de "self", igual que el resto de `usuarios.py` (comentario explícito en el archivo sobre por qué esto es intencional) |
| `AdminGeneral` se bloquea a sí mismo revocando su propia licencia (self-lockout, sistema queda sin ningún AdminGeneral operable) | Med si no mitigada (un solo AdminGeneral en la base es plausible — visto en el dato real de la migración 07: "un solo usuario con Rol='Admin'") | **Critical** — recuperar acceso requeriría acceso directo a la base | **Sí** — guard de auto-revocación (§4.4), clon del guard T6 ya probado en producción para Estado/Rol |
| Enumeración de torneos vía diferencia de status code (403 vs 404) en `PATCH /torneos/{id}` con ID inexistente | Low | Low | **Parcial/aceptable** — un `TorneoAdmin` sin asignación recibe 403 tanto para un torneo que existe pero no es suyo como para uno que no existe (la validación de asignación corre antes que la de existencia) — esto es information-hiding DESEABLE (no revela qué IDs existen), no un gap. `AdminGeneral` sí ve 404 real. Documentado, no requiere fix. |
| Input malformado en `torneo_ids` (no es array de ints, strings, negativos) | Med | Low-Med | **Sí, vía Pydantic** — el schema del body (`torneo_ids: list[int]`) rechaza tipos incorrectos en el nivel de FastAPI/Pydantic antes de llegar al servicio — consistente con el resto de la API |
| Torneo_ID negativo o cero en `torneo_ids` | Low | Low | **GAP menor** — Pydantic valida el TIPO (int) pero no el RANGO; un `torneo_id=-1` llega al servicio y simplemente no matchea ningún torneo real → mismo GAP que el de Sección 2 (`set_torneos_asignados` debe validar existencia, lo que cubre esto gratis) |
| SQL injection | N/A | N/A | **Sí, por diseño** — ORM parametrizado en todo el flujo nuevo, sin interpolación de strings, consistente con el resto del código |
| Dependency risk (paquete nuevo) | N/A | N/A | **Sí, no aplica** — cero dependencias nuevas (§1 del plan, confirmado: no hay librería de UI instalada y no se agrega ninguna) |
| Audit trail de operaciones sensibles (otorgar/revocar licencia, asignar/desasignar torneo) | — | — | **Sí, gratis** — `AUDITORIA` es un listener genérico a nivel de sesión SQLAlchemy (`before_flush`/`after_flush_postexec`, verificado leyendo `core/auditoria.py`: `_es_auditable` usa una lista de EXCLUSIÓN, no de inclusión — cualquier tabla nueva queda cubierta sin registro explícito), **con una condición**: el servicio debe escribir vía `session.add()`/`setattr()` ORM estándar, no `session.execute(insert(...))` estilo Core — ver Hour 1 en 0E arriba |

### Section 4 — Data Flow & Interaction Edge Cases

**Data flow — chequeo de licencia + asignación en un request de escritura a `/torneos/{id}`:**
```
  REQUEST ──▶ get_current_user ──▶ Licencia_Activa? ──▶ require_torneo_access ──▶ TorneoService.update()
     │              │                    │                       │                        │
     ▼              ▼                    ▼                       ▼                        ▼
  [sin token?]  [token inválido/   [FALSE?]              [rol≠TorneoAdmin/       [torneo_id no existe?]
  → 401         expirado?]         → 403 +               AdminGeneral? → 403]    → 404 (NotFoundError,
                → 401               X-License-Revoked     [sin fila Activa en     ya existente)
                                                            ASIGNACION? → 403]
```
Los 4 shadow paths (nil/vacío/error/happy) están cubiertos: sin token (401,
existente), token inválido (401, existente), sin licencia (403, nuevo,
corta ANTES de llegar a la asignación — orden correcto según §9 del plan),
sin asignación (403, nuevo). El único no cubierto explícitamente es
"torneo_id no numérico en la URL" — pero eso ya lo maneja FastAPI a nivel
de path param typing (422 automático), no es código de este plan.

**Interaction edge cases (UI nueva — toggle de licencia + modal de torneos):**

| Interacción | Edge case | ¿Manejado? | Cómo |
|---|---|---|---|
| Toggle de licencia | Doble-click rápido | **GAP si no se agrega** | Debe deshabilitarse el control mientras el `PATCH` está en vuelo (mismo patrón que `softDeletePending` ya existente en `ResourceTable`/`SimpleResourceAdminPage` — reusar, no inventar) |
| Toggle de licencia | Revocar la propia licencia | Manejado | Oculto/deshabilitado en la propia fila (mismo criterio que `isSelf` ya oculta "Dar de baja") — backend igual lo bloquea como defensa en profundidad |
| Modal de torneos | Abrir, no tildar nada, Guardar | Manejado | `PUT` con `torneo_ids: []` — el servicio desactiva todas las asignaciones existentes, comportamiento correcto y explícito (no un caso especial) |
| Modal de torneos | Abrir mientras `GET /torneos` (para poblar la lista) está lento/falla | **GAP si no se agrega** | Falta estado de loading/error explícito en el modal — mismo vocabulario que `ResourceTable` ya usa ("Cargando...", "No se pudo cargar la lista.") |
| Modal de torneos | Guardar, cerrar el modal, reabrir antes de que el `PUT` anterior confirme | **GAP si no se agrega** | Deshabilitar "Guardar" mientras la mutación está en vuelo, mismo patrón que el toggle |
| Lista de usuarios (Admin General) | 0 usuarios / 500 usuarios | Manejado | `ResourceTable` ya maneja lista vacía (`emptyMessage`) y no pagina explícitamente hoy — a 500 filas eso es un problema PREEXISTENTE de `UsuariosAdmin.tsx`, no introducido por este plan (fuera de blast radius, no se corrige acá) |
| `GET /torneos?solo_mios=true` (E1) | `TorneoAdmin` con licencia revocada intenta este GET | Manejado | `get_current_user` corta con 403 antes de llegar al filtro — mismo choke point que todo lo demás |

### Section 5 — Code Quality Review

- **Organización:** Todo el código nuevo sigue la estructura existente
  (excepción en `exceptions/errors.py`, handler en `exceptions/handlers.py`,
  dependency en `api/deps.py`, servicio en `services/`, endpoints en el
  router existente) — cero desvío de patrón.
- **DRY:** Verificado activamente contra reimplementación — `set_licencia`
  reusa el guard de auto-lockout (clon exacto de T6, no una copia con
  drift), `require_torneo_access` reusa `get_current_user` (no reimplementa
  resolución de JWT), el toggle/modal reusan `ResourceTable`/
  `SimpleResourceAdminPage` (no un componente de tabla nuevo). **Sin
  violaciones DRY encontradas** — el plan fue diseñado activamente para
  evitarlas (ver §1 del documento).
- **Naming:** `LicenseRevokedError`, `require_torneo_access`,
  `ASIGNACION_TORNEO_ADMIN` — consistentes con el vocabulario del resto del
  código (inglés en Python/clases, español en SQL/UI, mismo split que ya
  existe en todo el repo).
- **Over-engineering check:** Approach B (0C-bis) habría sido
  over-engineering — correctamente rechazado. Approach A (elegido) no
  introduce abstracción sin uso inmediato.
- **Under-engineering check:** El GAP de Sección 2 (validar existencia de
  `torneo_ids`) es el único punto donde el plan es más optimista de lo que
  debería — corregido como tarea.
- **Complejidad ciclomática:** `require_torneo_access._checker` tiene 3
  branches (bypass AdminGeneral / rol incorrecto / sin asignación) — muy
  por debajo del umbral de 5.

### Section 6 — Test Review

```
  NEW UX FLOWS:
    - Toggle de licencia por fila (UsuariosAdmin.tsx)
    - Modal "Gestionar torneos" (abrir, tildar/destildar, guardar)
    - Pantalla LicenseRevokedScreen (login o mid-sesión)

  NEW DATA FLOWS:
    - get_current_user → chequeo de licencia → LicenseRevokedError
    - require_torneo_access → ASIGNACION_TORNEO_ADMIN → 403/pass
    - set_torneos_asignados → upsert diff (activar/desactivar filas)

  NEW CODEPATHS:
    - Bypass AdminGeneral en require_torneo_access
    - Guard de auto-revocación en set_licencia
    - Trigger fn_validar_asignacion_torneo_admin_rol (rechazo de rol incorrecto)
    - GET /torneos?solo_mios=true (E1) rama TorneoAdmin vs. rama pública/otros roles

  NEW BACKGROUND JOBS / ASYNC WORK:
    - Ninguno — todo el flujo es síncrono por request

  NEW INTEGRATIONS / EXTERNAL CALLS:
    - Ninguna — todo interno (misma DB, mismo JWT)

  NEW ERROR/RESCUE PATHS:
    - Ver Sección 2 completa
```

| Codepath | Tipo de test | ¿Existe spec en el plan? | Happy path | Failure path | Edge case |
|---|---|---|---|---|---|
| `get_current_user` + licencia | Unit/Integration | Sí (§10 del plan) | Licencia activa → pasa | Licencia revocada → 403 + header | Licencia revocada A MITAD de sesión (token viejo, licencia cambia entre requests) |
| `require_torneo_access` | Unit/Integration | Sí (§10) | Asignado → pasa | No asignado → 403 | `AdminGeneral` sin asignación propia → pasa igual (bypass) |
| `set_licencia` (auto-revocación) | Unit | Sí (§10) | Revocar a otro → OK | Revocar a sí mismo → 403 | — |
| Trigger de rol en asignación | Integration (DB) | Sí (§10) | Asignar a TorneoAdmin → OK | Asignar a Arbitro/Publico → rechazo | — |
| `AUDITORIA` captura tabla nueva | Integration | Sí (§10) — y es el test MÁS importante de todo el plan: valida la premisa central de §1 (que el listener genérico realmente cubre la tabla nueva sin config) | Cambio de `Licencia_Activa` → fila en `AUDITORIA` | — | Cambio de `Estado` en `ASIGNACION_TORNEO_ADMIN` → fila en `AUDITORIA` |
| `set_torneos_asignados` (GAP de Sección 2) | Unit | **Falta en el plan — agregado acá** | Set válido → upsert correcto | `torneo_id` inexistente en el array → 404 con el ID culpable (no falla silencioso) | Array vacío → desactiva todo; array con duplicados → idempotente |
| `client.ts` header handling | Unit (frontend) | Sí (§10) | 403 + header → `onLicenseRevoked` dispara | 403 SIN el header (rol insuficiente genérico) → `onLicenseRevoked` NO dispara | — |
| Toggle doble-click (Sección 4) | E2E/component | **Falta en el plan — agregado acá** | Un solo PATCH | — | Doble-click → un solo PATCH en vuelo, control deshabilitado |

**Test ambition check:**
- *2am Friday test:* "Revocar la licencia de un `AdminGeneral` activo con
  una sesión abierta en otra pestaña — el próximo click ahí debe devolver
  403 con la pantalla correcta, sin excepción no capturada en el server."
- *Hostile QA test:* "Loguearse como `TorneoAdmin`, capturar el token,
  pedir que `AdminGeneral` revoque la licencia, reintentar CUALQUIER
  operación con el token viejo (no relogueado) — debe fallar 403, no
  colar por caché de sesión en ningún nivel (no hay caché de
  `Licencia_Activa` en este diseño, así que no debería colar)."
- *Chaos test:* Dos requests `PATCH /usuarios/{id}/torneos` concurrentes
  con sets distintos para el mismo usuario — el ganador debe ser
  determinístico (último commit gana, sin duplicados ni filas huérfanas)
  — cubre el caso de `IntegrityError` de la Sección 2.

**Test pyramid:** Mayoría unit (chequeos de deps/servicios), pocos
integration (trigger de DB, listener de auditoría), 1-2 E2E/component de
frontend (toggle, modal) — pirámide correcta, no invertida.

**Flakiness risk:** Ninguno de los tests nuevos depende de tiempo,
randomness, u orden — todos son determinísticos sobre estado explícito.

### Section 7 — Performance Review

- **N+1:** No aplica — `require_torneo_access` hace exactamente 1 query
  indexada por request, no una traversal de asociación.
- **Memoria:** `torneo_ids` en el body de `PATCH /usuarios/{id}/torneos` —
  tamaño máximo = cantidad total de torneos activos en el sistema (hoy
  decenas, no miles) — sin riesgo de memoria.
- **Índices:** `idx_asignacion_usuario`/`idx_asignacion_torneo` ya
  especificados en §3.2 del plan — cubren tanto `require_torneo_access`
  (busca por Usuario+Torneo) como `GET /usuarios/{id}/torneos` (busca por
  Usuario) y E1 (busca por Torneo, vía join). El `UNIQUE(Usuario_ID,
  Torneo_ID)` de §3.2 YA es un índice btree de 2 columnas que cubre el
  lookup de `require_torneo_access` como probe de una sola fila — **sin
  gap real acá** (corrección post outside-voice, Eng review hallazgo #5:
  una versión anterior de esta sección proponía un índice compuesto con
  `Estado` como mejora — era ruido, retirado, ver §3.2).
- **Caching:** Deliberadamente NO se cachea `Licencia_Activa` (la
  inmediatez de la revocación depende de leerla fresca cada vez, §4.2 del
  plan) — decisión correcta, cachear acá sería un bug de producto, no una
  optimización.
- **Background jobs:** Ninguno nuevo.
- **Slow paths (top 3, estimado):** (1) `PATCH /usuarios/{id}/torneos` con
  set grande — O(n) sobre el diff activar/desactivar, p99 estimado <50ms
  para <100 torneos; (2) `require_torneo_access` — 1 query indexada, p99
  <5ms; (3) modal frontend `GET /torneos` + `GET /usuarios/{id}/torneos`
  en paralelo al abrir — acotado por lo que ya tarda `GET /torneos` hoy
  (sin cambios).
- **Connection pool pressure:** Cero conexiones nuevas — misma pool
  Postgres que todo el sistema.

### Section 8 — Observability & Debuggability Review

- **Logging:** `get_current_user` y `require_torneo_access` deben loggear
  (nivel `warning`, no `error` — son rechazos esperados del negocio, no
  fallos del sistema) cada 403 de licencia/asignación con
  `usuario_id`+`torneo_id`+motivo — hoy el plan no lo especifica
  explícitamente. **Agregado como tarea** (T-obs1).
- **Métricas:** Un contador de "licencias revocadas" y "licencias
  otorgadas" (delta neto por día) le da a `AdminGeneral` una señal de uso
  del kill switch sin tener que leer `AUDITORIA` a mano — nice-to-have,
  no bloqueante, candidato a TODOS.md.
- **Tracing:** No aplica — sin llamadas cross-service.
- **Alerting:** Un pico anómalo de 403 por licencia (ej. >N en 5 minutos)
  podría indicar un token comprometido siendo reusado post-revocación —
  candidato a TODOS.md, no bloqueante para Fase 1.
- **Dashboards:** El panel de Admin General (parte del scope) YA ES el
  dashboard operativo del día 1 — no se necesita uno adicional.
  E5 (del cherry-pick scan) se resuelve acá: la propia tabla del panel +
  `AUDITORIA` genérica cubren "quién cambió qué licencia cuándo" sin
  UI dedicada nueva.
- **Debuggability:** Si en 3 semanas se reporta "a Snoopy le rechazaron
  acceso al Torneo B" — reconstruible 100% desde `AUDITORIA` (¿cuándo se
  desactivó esa fila de asignación, quién lo hizo) sin necesitar logs de
  aplicación — la elección de reusar `AUDITORIA` en vez de una tabla de
  historial paralela (D1) paga dividendos acá directamente.
- **Runbooks:** "Un `AdminGeneral` se auto-bloqueó" — no debería poder
  pasar (guard bloquea la auto-revocación), pero si el ÚLTIMO
  `AdminGeneral` de la base pierde acceso por otra vía (ej. `Estado`
  puesto en 'Inactivo' por error de DB directo, fuera de la API) — el
  runbook es el mismo que ya existe para cualquier lockout de cuenta
  (acceso directo a DB), no uno nuevo introducido por este plan.

### Section 9 — Deployment & Rollout Review

- **Migration safety:** `ALTER TABLE ... ADD COLUMN ... DEFAULT TRUE` y
  `CREATE TABLE` son ambas operaciones sin lock prolongado en Postgres
  moderno (no reescriben la tabla existente para un DEFAULT constante) —
  zero-downtime, backward-compatible (código viejo sigue funcionando
  contra el esquema nuevo, ignora la columna/tabla que no conoce).
- **Feature flags:** No se necesita — el `DEFAULT TRUE` en
  `Licencia_Activa` significa que el día del deploy nadie pierde acceso;
  el nuevo dependency `require_torneo_access` solo se activa cuando se
  agrega explícitamente a una ruta (el deploy del código y la activación
  del chequeo son el mismo evento, sin estado intermedio peligroso).
- **Rollout order:** Migración DB primero, código después — orden
  estándar del repo (mismo patrón que toda migración numerada 07-25).
- **Rollback plan:** Ver Sección 1 (rollback posture) — explícito, minutos.
- **Deploy-time risk window:** Código viejo + esquema nuevo = sin
  problema (columna con default, tabla sin FK entrante). Código nuevo +
  esquema viejo (deploy de código antes que migración, si el orden se
  invierte por error) = **rompería** (`Licencia_Activa` no existiría
  todavía) — por eso el orden migración-primero es no negociable, ya
  anotado.
- **Environment parity:** Mismo patrón SQL numerado que toda migración
  previa — se prueba igual (staging con la migración aplicada antes que
  el deploy de código).
- **Post-deploy verification (primeros 5 min):** Login de una cuenta
  `TorneoAdmin` de prueba, confirmar que `Licencia_Activa=TRUE` por
  default no le cambió nada; confirmar que `PATCH /torneos/{id}` sobre un
  torneo NO asignado a esa cuenta ahora devuelve 403 (era 200 antes del
  deploy) — este es el smoke test que prueba que el fix real (el gap de
  §2 del plan) quedó cerrado.
- **Smoke tests:** Los dos chequeos de arriba, automatizables como parte
  del healthcheck post-deploy existente (si lo hay) o como test manual
  documentado en el runbook de deploy.

### Section 10 — Long-Term Trajectory Review

- **Deuda técnica introducida:** Mínima — Fase 2 (rollout a 12 routers)
  queda como deuda EXPLÍCITA y documentada (D5, TODOS.md), no oculta. Sin
  deuda de testing (Sección 6 cubre el diseño completo) ni de
  documentación (el plan mismo es la documentación, con
  archivo:línea en cada afirmación).
- **Path dependency:** La forma N:M elegida (Approach A) no bloquea una
  futura generalización (Approach B) — si algún día aparece un segundo
  tipo de recurso asignable, la tabla `ASIGNACION_TORNEO_ADMIN` puede
  convivir con una tabla genérica nueva sin migrar esta, o migrarse una
  vez con un patrón conocido (mismo que la migración de roles 3→4 en
  `07_migracion_roles_arbitro.sql`). Reversibilidad: **4/5** (fácil de
  extender o reemplazar, no un one-way door — el único costo de cambiarlo
  después es una migración de datos, no un rediseño).
- **Conocimiento concentrado:** El plan documenta cada decisión con su
  alternativa rechazada (D1-D5) — un ingeniero nuevo en 12 meses puede
  leer el "por qué", no solo el "qué".
- **Ecosystem fit:** Sigue el mismo patrón SQL-numerado, FastAPI
  `Depends()`, y React sin librería de UI que el resto del repo — cero
  fricción con la dirección existente.
- **1-year question:** Leído como ingeniero nuevo: "¿por qué
  `require_torneo_access` vive en `deps.py` junto a `require_roles`?" —
  obvio, mismo lugar que su primo. "¿por qué la licencia es una columna y
  no una tabla?" — el comentario en el código (D1, §3.1) lo explica sin
  tener que preguntar.
- **¿Qué viene después?** Fase 2 (rollout) y Fase 3 (frontend) — la
  arquitectura de Fase 1 las soporta sin cambios de forma, solo repetición
  del mismo patrón por router (Section 10 EXPANSION check: sí soporta la
  trayectoria).
- **Platform potential:** `require_torneo_access` es directamente
  reutilizable por los 12 routers de Fase 2 tal como está escrito — no
  hace falta generalizarlo primero.
- **Retrospectiva del cherry-pick (E1 vs. E3/E4):** E1 fue la elección
  correcta — barato, en blast radius directo, cierra un gap de UX real. E3
  rechazado correctamente por costo (no es una condición previa para que
  E1 o el core funcionen). E4 rechazado correctamente por no estar pedido
  — ninguno de los rechazados resulta ser "load-bearing" para lo aceptado.

### Section 11 — Design & UX Review (UI scope detectado)

- **Information architecture:** En la fila de usuario: username → nombre →
  rol → **licencia (toggle, nuevo)** → estado → fecha → acciones (editar /
  dar de baja / **gestionar torneos, nuevo**). El toggle de licencia va
  ANTES que "estado" de la cuenta porque es la señal de mayor autoridad
  (jerarquía de validación superior, tal como pide el spec) — el ojo debe
  verla primero.
- **Interaction state coverage:**

  | Feature | LOADING | EMPTY | ERROR | SUCCESS | PARTIAL |
  |---|---|---|---|---|---|
  | Toggle de licencia | Control deshabilitado durante el PATCH | N/A | Revertir el toggle visualmente + mensaje (`apiErrorMessage` ya existente) | Toggle refleja el nuevo estado | N/A (operación atómica) |
  | Modal "Gestionar torneos" | "Cargando..." (mismo vocabulario que `ResourceTable`) | "No hay torneos activos" (mismo patrón que `emptyMessage`) | "No se pudo cargar la lista." (mismo texto que `ResourceTable`) | Modal cierra, tabla no cambia (la asignación no es una columna visible en la tabla principal) | N/A |
  | `LicenseRevokedScreen` | N/A (aparece post-respuesta, no hay estado intermedio) | N/A | N/A (es en sí la pantalla de error) | N/A | N/A |

- **User journey coherence:** Login → (si sin licencia) pantalla de bloqueo
  inmediata, sin parpadeo del shell de la app detrás — el arco emocional
  correcto es "rechazo claro e inmediato", no "casi entro y me echaron".
  Esto depende de que `LicenseRevokedScreen` se resuelva en el MISMO
  punto donde `AuthContext` decide qué renderizar (junto a `onUnauthorized`,
  §5.2 del plan) — no como un toast que aparece después de que la app ya
  renderizó.
- **AI slop risk:** Ninguno — el plan reusa componentes/vocabulario
  existentes en vez de inventar un patrón visual nuevo (checkbox list
  nativa, no un multiselect "de catálogo" genérico sin relación con el
  resto de la UI).
- **DESIGN.md alignment:** No hay `DESIGN.md` en el repo (confirmado —
  `docs/designs/` tiene un solo doc no relacionado, sobre dashboard/mesa en
  vivo) — el plan alinea con el sistema de diseño IMPLÍCITO (el que ya usan
  `ResourceTable`/`SimpleResourceAdminPage`), que es el único estándar real
  disponible.
- **Responsive:** No mencionado explícitamente en el plan — **gap
  menor**, agregado como nota: el modal de checkboxes debe scrollear en
  vertical en mobile (misma consideración que cualquier lista larga), sin
  requerir un breakpoint especial más allá de lo que `ResourceTable` ya
  maneja.
- **Accesibilidad:** El toggle debe ser un `<input type="checkbox">` o
  `<button role="switch" aria-checked>` real (no un `<div>` con onClick) —
  necesario para lector de pantalla + navegación por teclado. Anotado
  como requisito explícito, no implícito.

**Recomendación:** dado que el UI scope es acotado (extender una pantalla
existente, no crear un flujo nuevo), `/plan-design-review` es opcional —
esta sección ya cubre la intencionalidad de diseño necesaria. Se ejecuta
igual como Fase 2 de este pipeline de `/autoplan` porque hay UI scope
detectado.

## CEO Voices

Codex: no disponible (`codex` no está en el PATH de este entorno) — no
corrió. Claude subagent (contexto fresco, mismo modelo — no una voz
cross-model real, pero independiente de este hilo de conversación): corrió
contra el plan ya escrito, verificando cada afirmación contra el código en
vez de confiar en el resumen del plan. Encontró **6 hallazgos reales**, 4
de severidad alta/media (gaps que rompen la premisa central o regresionan
un flujo que hoy funciona) y 2 menores (cita de línea incorrecta, MRO de
excepciones correcto pero justificado con un precedente inexistente). Los
4 hallazgos altos/medios ya están **incorporados al plan** arriba (no
quedan como "hallazgo suelto" — se corrigieron en §3.1, §3.2, §4.2, §4.5,
§7-D4). El hallazgo D2 (licencia duplicando `Estado` para Arbitro/Publico)
es genuinamente una decisión de producto, no un bug — queda para el gate
final, no se auto-decide.

**Consensus:**

| # | Hallazgo | CEO review (esta sección) | Outside voice | Resuelto |
|---|---|---|---|---|
| 1 | `get_current_user_optional` sin parchear | No detectado en el primer pase | Detectado, severidad alta | ✅ Incorporado (§4.2) |
| 2 | ORM models nunca especificados (`licencia_activa`, `AsignacionTorneoAdmin`) | Mencionado tangencialmente en 0E (Hour 1) pero no como paso explícito | Detectado con precisión (AttributeError concreto) | ✅ Incorporado (§3.1, §3.2) |
| 3 | D4 rompe creación de torneo por `AdminGeneral` | No detectado — D4 se recomendó sin trazar el bypass de `require_roles` hasta el trigger | Detectado, con cita de línea exacta | ✅ Incorporado (§7-D4) |
| 4 | Login sin `_registrar_acceso` en el rechazo por licencia | No detectado | Detectado, cita el docstring "no negociable" | ✅ Incorporado (§4.2) |
| 5 | `UsuarioOut` sin `licencia_activa` | Implícito en Sección 4/11 (UI necesita el campo) pero no explicitado como gap de schema | Detectado explícito | ✅ Incorporado (§4.5) |
| 6 | D2 uniforme duplica `Estado` para Arbitro/Publico | Ya identificado como taste decision en el plan original, sin el argumento concreto de duplicación | Mismo tema, argumento más afilado (duplicación de fuente de verdad) | 🔶 Sigue abierto — gate final |
| — | Cita `chk_usuarios_rol` en línea incorrecta | No detectado | Detectado | ✅ Corregido (§1) |
| — | MRO de excepciones: correcto pero "mismo mecanismo ya en uso" es una cita fabricada (no hay precedente real de subclase de excepción registrada en este repo) | Afirmado sin verificar | Verificado — el comportamiento es correcto, la justificación de precedente no | 📝 Nota: el diseño (header vs. body, D3) sigue siendo válido; la única corrección es no citarlo como "patrón ya en uso", es simplemente comportamiento correcto de Starlette aplicado por primera vez acá |

**Consensus: 6/8 hallazgos, ambas voces coinciden en severidad donde
coinciden en detectarlo — 0 desacuerdos genuinos (la voz externa encontró
más, no encontró algo distinto de lo que esta revisión ya sostenía).**
Esto es la señal de valor real de correr dual-voice: no reemplaza el
review, encuentra lo que el primer pase, enfocado en el diseño de alto
nivel, no llegó a trazar hasta el código de wiring concreto.

## Error & Rescue Registry

Ver tabla completa en **Section 2** arriba — es la misma tabla, no se
duplica. 10 codepaths mapeados, 1 GAP real identificado y resuelto como
tarea (T-gap1, validar existencia de `torneo_ids` antes del upsert).

## Failure Modes Registry

```
  CODEPATH                          | FAILURE MODE                | RESCUED? | TEST? | USER SEES?          | LOGGED?
  ----------------------------------|------------------------------|----------|-------|---------------------|--------
  get_current_user (licencia)       | Licencia revocada            | Y        | Y (§10) | Pantalla bloqueo   | Vía AUDITORIA (cambio de columna), NO vía log de acceso (no es un intento de login)
  get_current_user_optional         | Licencia revocada (ANTES     | N →      | Falta  | Acceso elevado      | No — GAP CRÍTICO real,
                                     | de la corrección de arriba) | GAP      | agregar | silencioso          | ya incorporado al plan (§4.2)
  login()                           | Licencia revocada            | Y        | Y (§10) | 403 + pantalla      | Y — vía _registrar_acceso (corrección incorporada, §4.2)
  require_torneo_access             | Sin asignación activa        | Y        | Y (§10) | 403 con mensaje     | No explícito — T-obs1 (Sección 8)
  set_licencia                      | Auto-revocación               | Y        | Y (§10) | 403, bloqueado      | Vía AUDITORIA (intento no llega a escribir)
  set_torneos_asignados             | ID de torneo inexistente      | N →      | Falta  | Sin actualizar,     | No — GAP real, T-gap1
                                     | en el array                  | GAP      | agregar | sin aviso (antes    |
                                     |                               |          |         | de la corrección)   |
  Trigger fn_validar_..._rol        | Asignar a rol incorrecto      | Y        | Y (§10) | 400, mensaje DB     | Y — vía AUDITORIA si el insert llega a completar (no aplica, el trigger lo bloquea antes)
  Toggle de licencia (frontend)     | Doble-click                   | N →      | Falta  | 2 PATCH concurrentes | N/A (frontend)
                                     |                               | GAP      | agregar | (antes de corrección)|
```

Ninguna fila queda en **CRITICAL GAP** (RESCUED=N + TEST=N + USER
SEES=Silencioso simultáneo) DESPUÉS de las correcciones incorporadas — el
único caso que hubiera calificado (`get_current_user_optional`) ya está
resuelto en el diseño de arriba, no solo anotado.

## NOT in scope (adenda CEO review)

Adicional a §8 del plan original:
- **E3** (rollout de `require_torneo_access` a los 12 routers restantes) —
  confirmado NOT in scope de Fase 1, va a `TODOS.md` (ver abajo).
- **E4** (vista inversa usuario↔torneo en la pantalla de edición de
  Torneo) — rechazado, no pedido por el spec.
- Alertas/métricas dedicadas de licencia (Sección 8) — nice-to-have, va a
  `TODOS.md`.
- Índice compuesto `(Usuario_ID, Torneo_ID, Estado)` (Sección 7) —
  optimización menor, no bloqueante para Fase 1; se anota como mejora
  futura, no como tarea de esta fase.

## Dream state delta

Con Fase 1 (+ E1, + correcciones post outside-voice) implementada: el
sistema pasa de "TorneoAdmin es un rol global sin scoping real" a "todo
acceso administrativo a un torneo específico pasa por licencia + asignación
verificadas en cada request, con auditoría automática y una UI operable
para el AdminGeneral" — el delta más grande hacia el ideal de 12 meses
(§0C) que este plan puede mover en una sola fase. Lo que queda pendiente
(Fase 2: rollout a 12 routers; Fase 3: filtrado de UI en `torneo-admin/*`)
es trabajo de la MISMA forma, no un rediseño — el ideal de 12 meses queda
a "repetir el patrón N veces", no a "resolver algo nuevo".

## TODOS.md updates

Se auto-deciden (autoplan, sin AskUserQuestion interactivo) y se escriben
directamente a `TODOS.md` como parte de este review — ver la sección nueva
agregada a ese archivo. Ítems:

1. **Rollout de `require_torneo_access` a los 12 routers de Fase 2**
   (P2, L) — depende de Fase 1 mergeada.
2. **Filtrado de listados en `torneo-admin/*` para que un TorneoAdmin solo
   vea sus torneos asignados** (P2, M) — depende de Fase 2 (o de un subset
   de ella).
3. **Métricas/alertas dedicadas de licencia** (Sección 8) (P3, S) —
   independiente, se puede hacer en cualquier momento post Fase 1.
4. ~~Índice compuesto `(Usuario_ID, Torneo_ID, Estado)`~~ — **retirado**
   post Eng review outside-voice: `UNIQUE(Usuario_ID, Torneo_ID)` ya es el
   índice que hace falta, no había gap real (ver §3.2/Section 7).

## Scope Expansion Decisions (SELECTIVE EXPANSION)

- **Accepted:** E1 (`GET /torneos?solo_mios=true`), E2/D4 (auto-asignar
  creador, con el guard corregido).
- **Deferred:** E3 (rollout Fase 2), E5-derivados (métricas/alertas de
  licencia), índice compuesto.
- **Skipped:** E4 (vista inversa usuario↔torneo).

## Diagramas producidos

1. Arquitectura de sistema (Section 1) ✅
2. Data flow con shadow paths (Section 4) ✅
3. State machine — implícito en `Licencia_Activa`/`Estado` de asignación
   (ambos booleanos de 2 estados, sin transiciones intermedias que
   ameriten diagrama aparte — se documenta acá: `Activo ⇄ Inactivo`,
   transición libre en ambos sentidos, sin estado "en tránsito") ✅
4. Error flow (Section 2, tabla + Section 4 diagrama de request) ✅
5. Deployment sequence (Section 9, migración → código, texto explícito) ✅
6. Rollback flowchart (Section 1, rollback posture — texto explícito, sin
   pasos condicionales que ameriten ASCII aparte: es un revert simple) ✅

## Stale Diagram Audit

Ningún diagrama ASCII preexistente en los archivos que este plan toca
(`deps.py`, `errors.py`, `handlers.py`, `usuarios.py`, `torneos.py`,
`client.ts`, `RequireRole.tsx`, `UsuariosAdmin.tsx`) — nada que quede
desactualizado.

## Implementation Tasks

- [ ] **T1 (P1, human: ~1h / CC: ~10min)** — backend — Agregar
  `licencia_activa` al modelo ORM `Usuario` + migración de columna
  - Surfaced by: Section 2/outside-voice hallazgo #2 — `models/usuario.py`
  - Files: `backend/app/models/usuario.py`, `database/26_migracion_rbac_licencias_torneos.sql`
  - Verify: test que lee `usuario.licencia_activa` sin `AttributeError`
- [ ] **T2 (P1, human: ~2h / CC: ~15min)** — backend — Crear modelo ORM +
  tabla `ASIGNACION_TORNEO_ADMIN` + trigger de validación de rol
  - Surfaced by: Section 2/outside-voice hallazgo #2
  - Files: `backend/app/models/asignacion_torneo_admin.py`, migración SQL, `06_triggers.sql`-style function
  - Verify: insertar asignación a un usuario `Rol='Arbitro'` → rechazo
- [ ] **T3 (P1, human: ~30min / CC: ~10min)** — backend — Extraer
  `_resolver_usuario_autenticado` compartido entre `get_current_user` y
  `get_current_user_optional`
  - Surfaced by: outside-voice hallazgo #1 (CRÍTICO)
  - Files: `backend/app/api/deps.py`
  - Verify: test — licencia revocada + `get_current_user_optional` → `None`, no acceso elevado
- [ ] **T4 (P1, human: ~30min / CC: ~10min)** — backend — Chequeo de
  licencia en `login()` con `_registrar_acceso(motivo="licencia_revocada")`
  - Surfaced by: outside-voice hallazgo #4
  - Files: `backend/app/services/usuario.py`
  - Verify: test — login con licencia revocada → fila en `ACCESOS` con ese motivo
- [ ] **T5 (P1, human: ~1h / CC: ~10min)** — backend — `require_torneo_access`
  en `deps.py` + aplicar a `torneos.py` PATCH/DELETE
  - Surfaced by: plan core (§4.3, §4.6)
  - Files: `backend/app/api/deps.py`, `backend/app/api/routes/torneos.py`
  - Verify: test T3/T6-style — TorneoAdmin sin asignación → 403
- [ ] **T6 (P1, human: ~1h / CC: ~10min)** — backend — 3 endpoints nuevos
  en `usuarios.py` + `AsignacionTorneoAdminService` (con el guard D4
  corregido) + `licencia_activa` en `UsuarioOut`
  - Surfaced by: plan core (§4.4, §4.5) + outside-voice hallazgos #3, #5
  - Files: `backend/app/api/routes/usuarios.py`, `backend/app/services/`, `backend/app/schemas/usuario.py`
  - Verify: test — AdminGeneral crea torneo sin auto-asignación (no rompe); TorneoAdmin crea torneo → auto-asignado
- [ ] **T7 (P2, human: ~30min / CC: ~10min)** — backend — Validar
  existencia de `torneo_ids` en `set_torneos_asignados` antes del upsert
  - Surfaced by: Section 2 (GAP identificado en esta misma revisión)
  - Files: `backend/app/services/` (asignación)
  - Verify: test — `torneo_ids=[99999]` → 404 con el ID culpable, no falla silenciosa
- [ ] **T8 (P1, human: ~1h / CC: ~10min)** — frontend — Callback
  `onLicenseRevoked` en `client.ts` + estado en `AuthContext` +
  `LicenseRevokedScreen`
  - Surfaced by: plan core (§5.1, §5.2)
  - Files: `frontend/src/api/client.ts`, `frontend/src/auth/`, nuevo componente
  - Verify: test — 403 + header → pantalla correcta; 403 sin header → NO dispara
- [ ] **T9 (P2, human: ~1.5h / CC: ~15min)** — frontend — Toggle de
  licencia + modal `AsignarTorneosModal` en `UsuariosAdmin.tsx`, con
  loading/disabled state (Section 4 edge cases)
  - Surfaced by: plan core (§5.3) + Section 4 (doble-click, loading states)
  - Files: `frontend/src/pages/admin/UsuariosAdmin.tsx`, nuevo modal
  - Verify: test — doble-click en toggle → un solo PATCH; modal con `GET` lento → estado de loading visible
- [ ] **T10 (P2, human: ~30min / CC: ~10min)** — backend — `GET
  /torneos?solo_mios=true` (E1)
  - Surfaced by: cherry-pick E1 (SELECTIVE EXPANSION)
  - Files: `backend/app/api/routes/torneos.py`
  - Verify: test — TorneoAdmin con 2 de 5 torneos asignados → `solo_mios=true` devuelve 2
- [ ] **T11 (P1, human: ~1h / CC: ~10min)** — backend — Test de integración
  que confirma que `AUDITORIA` captura cambios en `Licencia_Activa` y en
  `ASIGNACION_TORNEO_ADMIN` sin config adicional
  - Surfaced by: §1 del plan (premisa central) + condición de ORM mutation (T2)
  - Files: `backend/tests/`
  - Verify: cambiar `licencia_activa` vía el servicio → fila nueva en `AUDITORIA` con `Tabla='usuarios'`

## Completion Summary

```
  +====================================================================+
  |            MEGA PLAN REVIEW — COMPLETION SUMMARY (CEO Phase)        |
  +====================================================================+
  | Mode selected        | SELECTIVE EXPANSION                          |
  | System Audit         | 4 roles ya existen, TorneoAdmin es global    |
  |                       | hoy (sin scoping), AUDITORIA es genérica     |
  | Step 0               | Approach A elegido; E1/D4 aceptados,         |
  |                       | E3/E5-derivados diferidos, E4 rechazado      |
  | Section 1  (Arch)    | 0 issues bloqueantes — arquitectura limpia   |
  | Section 2  (Errors)  | 10 codepaths mapeados, 1 GAP (resuelto: T7)  |
  | Section 3  (Security)| 9 amenazas evaluadas, 0 High sin mitigar     |
  | Section 4  (Data/UX) | 7 edge cases, 3 GAPS (resueltos: T8/T9)      |
  | Section 5  (Quality) | 0 issues — sin violaciones DRY               |
  | Section 6  (Tests)   | Diagrama producido, 2 gaps (T7/T9 los cubren)|
  | Section 7  (Perf)    | 1 mejora menor (índice compuesto, TODOS.md)  |
  | Section 8  (Observ)  | 1 gap de logging (T-obs1, TODOS.md)          |
  | Section 9  (Deploy)  | 0 riesgos bloqueantes — migración aditiva    |
  | Section 10 (Future)  | Reversibilidad: 4/5, deuda: Fase 2 explícita |
  | Section 11 (Design)  | 2 gaps menores (responsive, a11y — anotados) |
  +--------------------------------------------------------------------+
  | NOT in scope         | escrito (4 items adicionales)                |
  | What already exists  | escrito (§1 del plan, 12 filas verificadas)  |
  | Dream state delta    | escrito                                      |
  | Error/rescue registry| 10 métodos, 0 CRITICAL GAPS (post-corrección)|
  | Failure modes        | 8 filas, 0 CRITICAL GAPS (post-corrección)   |
  | TODOS.md updates     | 4 items agregados                            |
  | Scope proposals      | 3 propuestos (E1/E3/E4), 2 aceptados (E1,D4) |
  | CEO plan             | no aplica (SELECTIVE EXPANSION sin doc aparte)|
  | Outside voice         | corrió (Claude subagent) — 6/8 hallazgos consenso |
  | Lake Score            | 9/9 correcciones críticas incorporadas al plan |
  | Diagramas producidos  | 6 (arquitectura, data flow, state, error, deploy, rollback) |
  | Stale diagrams found  | 0                                            |
  | Unresolved decisions  | 1 (D2 — va al gate final)                    |
  +====================================================================+
```

### Unresolved Decisions

1. **D2** — licencia uniforme (D2a) vs. scoped a TorneoAdmin/AdminGeneral
   (D2b). Cross-model tension real (esta revisión recomendaba D2a por
   defecto; la voz externa argumenta D2b). Va al Final Approval Gate como
   User Challenge — el usuario decide, no se auto-resuelve.

<!-- AUTONOMOUS DECISION LOG -->
## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|---|---|---|---|---|---|
| 1 | CEO | Mode = SELECTIVE EXPANSION | Mechanical | — | Default de contexto: mejora sobre sistema existente, no greenfield ni bugfix | EXPANSION (demasiado ambicioso para el spec dado), HOLD/REDUCTION (el spec ya define un mínimo claro que vale la pena revisar por expansiones baratas) |
| 2 | CEO | Approach A (columna + tabla N:M) sobre Approach B (motor ABAC genérico) | Taste (recomendación clara, sin objeción) | P5 Explicit over clever + P3 Pragmatic | Spec pide exactamente esto; B es abstracción sin caso de uso hoy (N=1 tipo de recurso) | Approach B |
| 3 | CEO | Licencia como columna en `USUARIOS`, no tabla `LICENCIAS` con historial | Mechanical | P4 DRY | `AUDITORIA` ya da el historial gratis — una tabla paralela lo duplicaría | Tabla `LICENCIAS` separada |
| 4 | CEO | Header `X-License-Revoked` para distinguir el 403, no campo `code` en el body | Mechanical | P4 DRY + P5 Explicit | Precedente ya existente en el repo (`RateLimitError`→`Retry-After`); evita clonar el `Response` en el middleware | Campo `code` en JSON body |
| 5 | CEO | E1 (`GET /torneos?solo_mios=true`) | Taste → Accepted | P1 Completeness + P2 Boil lakes | Blast radius directo, <1 día, cierra un gap de UX que el propio ejemplo del spec implica | — |
| 6 | CEO | E2/D4 (auto-asignar creador, con guard de rol) | Mechanical (una vez corregido el bug) | P1 Completeness | Sin esto un TorneoAdmin crea un torneo que no puede administrar | Auto-asignar sin guard (regresionaba la creación por AdminGeneral — descartado tras hallazgo de la voz externa) |
| 7 | CEO | E3 (rollout Fase 2, 12 routers) → TODOS.md | Mechanical | P2 Boil lakes (con el límite explícito: NO auto-aprobado si no es <1 día) | Varios routers no tienen `torneo_id` directo — no es un cambio mecánico rápido por router | Incluir en Fase 1 |
| 8 | CEO | E4 (vista inversa usuario↔torneo) — Skipped | Mechanical | Cognitive pattern #17 (Subtraction default) | El spec no lo pide; agrega superficie de UI no solicitada | Agregar al scope |
| 9 | CEO | Incorporar los 4 hallazgos altos/medios de la voz externa directamente al diseño del plan (no solo anotarlos) | Mechanical | P1 Completeness (boil the ocean — corregir el gap real, no solo documentarlo) | Cada uno era un bug real verificado contra el código (AttributeError, regresión de flujo existente, invariante de auditoría roto, acceso elevado post-revocación) | Dejarlos como "hallazgo suelto" sin tocar el diseño |
| 10 | CEO | D2 (licencia uniforme vs. scoped) → **User Challenge, no auto-decidido** | User Challenge | — (excepción a las 6 principios: tensión genuina entre dos voces sobre una decisión de producto, no técnica) | Ninguna de las dos opciones es objetivamente correcta — depende de si "licencia" es un concepto de cuenta o de gestión de torneos específicamente | — |
| 11 | Design | Omitir generación de mockups de imagen (gstack designer disponible, no usado) | Mechanical | P3 Pragmatic | Sin `DESIGN.md`, superficie de 2 piezas sobre tabla plana ya existente — un mockup no tendría con qué calibrarse | Generar mockups igual (el usuario puede pedirlos en el gate) |
| 12 | Design | Toggle = `<input type="checkbox">` nativo, no un `Switch` custom | Mechanical | P5 Explicit over clever + P4 DRY | Ningún switch custom existe hoy en el repo; agregar uno para 1 solo uso es superficie no justificada | Componente `Switch.tsx` nuevo |
| 13 | Design | Focus trap + retorno de foco en el modal (T12) | Mechanical | P1 Completeness | Gap real de accesibilidad, costo bajo, en blast radius directo | Diferir a TODOS.md (rechazado — es <1 día, se incluye en Fase 1) |
| 14 | DX | Alcance de DX review reducido a 1 dimensión (error message empathy) | Mechanical | — (el marco del skill asume audiencia de desarrollador externo, verificado que no existe acá) | Score-App API no tiene consumidores externos — aplicar el marco completo (TTHW, SDK, benchmark competitivo) fabricaría análisis sin base real | Evaluar las 7 características completas igual (rechazado — produciría contenido sin sustento, contradice "Claimed Limitations Need Evidence") |
| 15 | DX | Mejorar mensaje de `require_torneo_access` con la acción sugerida | Mechanical | Característica #3 (Error message empathy) | Costo de 1 string, mejora real de debuggability para el propio equipo | — |
| 16 | Eng | Scope Fase 1 se mantiene pese al complexity-check (8+ archivos) | Mechanical | P5 Explicit + P3 Pragmatic | Ninguna reducción posible sin reabrir un hallazgo CEO ya cerrado (get_current_user_optional) o romper la convención de 1 servicio por entidad | Fusionar AsignacionTorneoAdminService en UsuarioService |
| 17 | Eng | `set_torneos_asignados` usa `session.add()`/commit único (patrón `inscripcion_torneo.py`), no `BaseRepository` en loop | Mechanical | Systems over heroes (atomicidad real, no solo en el caso feliz) | Verificado: `BaseRepository.create/update` commitean por llamada — un loop rompería la atomicidad que el propio plan prometía en §9 | Loop sobre BaseRepository (el diseño original, descartado) |
| 18 | Eng | Endpoint cambiado de `PUT` a `PATCH /usuarios/{id}/torneos` en todo el documento | Mechanical | Two-week smell test (no extender infra para 1 caller) | `useResourceCrud.customAction` solo soporta POST/PATCH — verificado en el código, no asumido | Extender el tipo de `customAction` para soportar PUT |
| 19 | Eng | `UsuarioService.update()` desactiva asignaciones huérfanas al degradar rol (no un segundo trigger de DB) | Mechanical | Reversibility preference + mantener la lógica de negocio donde ya viven los otros guards | Evita un trigger cruzando USUARIOS↔ASIGNACION_TORNEO_ADMIN en dirección inversa a fn_validar_asignacion_torneo_admin_rol | Segundo trigger `AFTER UPDATE OF Rol` |
| 20 | Eng | Fixtures de test nombradas + split de archivo explícito (test_usuarios.py/test_torneos.py/test_auth.py/test_auditoria.py) | Mechanical | Well-tested code non-negotiable | Evita que Fase 1 llegue a implementación sin saber dónde viven los tests | Dejar la ubicación implícita (el estado original del plan) |
| 21 | Eng | Índice compuesto retirado de TODOS.md (era ruido, no una mejora real) | Mechanical | Claimed Limitations Need Evidence (aplicado a una afirmación propia, no solo del usuario) | UNIQUE(Usuario_ID, Torneo_ID) ya es el índice necesario — verificado, no asumido | Mantener el TODO como estaba |

---

# DESIGN REVIEW (autoplan Phase 2 — UI scope detectado)

**Clasificación:** App UI (workspace-driven, data-dense, gestión — no
marketing/landing) → aplican las App UI Rules del skill, no las de Landing
Page.

**Decisión sobre mockups visuales (auto-decidida, Principio 3 —
Pragmatic):** el binario `gstack designer` está disponible
(`DESIGN_READY`), pero **se decide NO generar mockups de imagen** para
esta pieza. Razón concreta, no genérica: (1) no existe `DESIGN.md` en el
repo — no hay sistema de diseño visual contra el cual calibrar un mockup
generado por IA, así que el mockup no tendría con qué alinearse más allá
de "se ve bien" en abstracto; (2) la superficie nueva es una extensión de
2 piezas (una columna de toggle + un modal de checkboxes) sobre una tabla
HTML plana ya existente y sin librería de UI — el diseño visual completo
de esa tabla no es parte de este plan, y generar un mockup polished de una
sola columna nueva sería diseñar en el vacío; (3) el `UsuarioRow`/columnas
existentes de `UsuariosAdmin.tsx` ya definen el lenguaje visual real que
esta pieza debe seguir (texto plano, tabla `<table>`, botones de acción en
la última celda) — la especificación funcional exacta de §5.3 del plan ya
resuelve el 100% de lo que un mockup mostraría, sin el costo/tiempo de
generación de imagen. Si el usuario prefiere ver un mockup igual, puede
pedirlo explícitamente en el gate final — no es una puerta cerrada, es una
decisión de costo/valor para esta pieza específica.

### Pass 1 — Information Architecture: **7/10 → 9/10**

Ya cubierto en CEO Section 11 (jerarquía de columnas: licencia ANTES que
estado de cuenta). Gap encontrado acá que Section 11 no bajó a nivel de
ASCII: falta el diagrama de navegación del modal en sí.

```
  UsuariosAdmin (tabla)
    │
    ├─ fila de usuario ──▶ [toggle licencia] (inline, sin navegar)
    │
    └─ fila de usuario ──▶ [botón "Gestionar torneos"] ──▶ MODAL (overlay, no ruta nueva)
                                                              │
                                                              ├─ lista de checkboxes (todos los torneos activos)
                                                              ├─ [Cancelar] ──▶ cierra sin guardar
                                                              └─ [Guardar]  ──▶ PUT + cierra
```

**Fix aplicado:** el modal es un overlay, no una ruta (`/usuarios/:id/torneos`)
— decisión correcta para "constraint worship" (una sola tarea, no amerita
navegación propia ni deep-linking) y ya implícita en §5.3, ahora explícita.

### Pass 2 — Interaction State Coverage: **6/10 → 9/10**

CEO Section 11 ya dio la tabla completa (LOADING/EMPTY/ERROR/SUCCESS/
PARTIAL para toggle + modal + `LicenseRevokedScreen`) — no se repite. El
gap que subía el score de 6 a 9 es el mismo ya identificado en Section 4
del CEO review (doble-click, `PUT` en vuelo) — **ya incorporado al plan**
como parte de T9. Queda en 9, no 10, porque falta un estado explícito para
"el modal se abre pero el usuario NO tiene ningún torneo activo en el
sistema" (lista de checkboxes vacía) — agregado acá:

```
  FEATURE                    | LOADING      | EMPTY (sin torneos activos) | ERROR              | SUCCESS          | PARTIAL
  ----------------------------|--------------|------------------------------|---------------------|------------------|--------
  Modal "Gestionar torneos"   | "Cargando..."| "No hay torneos activos para | "No se pudo cargar  | Modal cierra     | N/A
                               |              | asignar." + el botón         | la lista."          |                  |
                               |              | "Guardar" queda deshabilitado |                     |                  |
                               |              | (nada que guardar, no un     |                     |                  |
                               |              | formulario roto)             |                     |                  |
```

### Pass 3 — User Journey & Emotional Arc: **8/10**

```
  STEP | USUARIO HACE                          | USUARIO SIENTE                    | ¿EL PLAN LO CUBRE?
  -----|----------------------------------------|------------------------------------|--------------------
  1    | AdminGeneral abre el panel de usuarios | Control — ve TODOS los usuarios   | Sí (§5.3, tabla existente)
  2    | Tilda el toggle de licencia de alguien | Autoridad, pero con fricción       | Sí — sin confirmación extra (el
       |                                         | consciente (es una acción seria)   | toggle es directo, no hay modal
       |                                         |                                     | de "¿estás seguro?") — decisión
       |                                         |                                     | correcta: agregar un confirm
       |                                         |                                     | dialog para CADA toggle sería
       |                                         |                                     | fricción excesiva para una acción
       |                                         |                                     | reversible con 1 click (revertir
       |                                         |                                     | es tildar de nuevo)
  3    | Abre "Gestionar torneos" de un TorneoAdmin | Precisión — arma el set exacto  | Sí (§5.3, modal)
  4    | (En paralelo) el TorneoAdmin afectado  | Sorpresa/frustración — rechazo    | Sí (§0/§5.2 — pantalla clara,
       | intenta trabajar y es bloqueado        | súbito sin aviso previo            | no un error crudo). El spec pide
       |                                         |                                     | explícitamente que sea así
       |                                         |                                     | (kill switch inmediato) — la
       |                                         |                                     | fricción emocional acá es
       |                                         |                                     | INTENCIONAL, no un bug de UX
  ```

  Time-horizon: 5-seg (el toggle/modal se leen sin pensar, mismo
  vocabulario que el resto de la tabla) — 5-min (el AdminGeneral confía en
  que el cambio aplicó, sin necesitar refrescar la página — el toggle
  refleja su nuevo estado inmediatamente vía la respuesta del PATCH) —
  5-años (reflectivo: no aplica de forma distinta a cualquier otra
  pantalla admin de este sistema).

### Pass 4 — AI Slop Risk: **9/10**

Sin hallazgos — el plan reusa vocabulario textual/funcional existente, no
describe UI en términos genéricos ("dashboard moderno", "tarjetas
elegantes"). Chequeado contra la blacklist: sin grid de 3 columnas, sin
iconos en círculos de color, sin gradientes — la superficie nueva es una
columna de tabla + una lista de checkboxes, ninguna de las dos tiene
superficie para "AI slop" en absoluto. **App UI rules** aplicables: "cards
solo cuando la card ES la interacción" — no aplica (no hay cards);
"copy utilitario, no de marca" — el texto propuesto ("Licencia Inactiva o
Revocada. Contacte al administrador.") es literal del spec, utilitario por
definición.

### Pass 5 — Design System Alignment: **6/10 → 8/10**

Sin `DESIGN.md` (confirmado, gap preexistente del repo, no introducido por
este plan). El plan SÍ alinea con el vocabulario implícito real
(`ResourceTable`/`SimpleResourceAdminPage`) — eso es lo máximo que puede
dar 10/10 sin que exista un `DESIGN.md` real. **Gap que sube el score de 6
a 8:** el plan no especifica el estilo visual CONCRETO del toggle (¿checkbox
nativo, o un `<button role="switch">` con CSS de píldora?) — Sección 11
del CEO review ya lo resolvió parcialmente (a11y: debe ser
`<input type="checkbox">` o `role="switch"` real), pero no elige explícito
entre las dos. **Recomendación (auto-decidida, Principio 5 — Explicit over
clever):** `<input type="checkbox">` simple, no un switch custom con CSS
— es lo que el resto de la tabla ya usa implícitamente en cualquier campo
booleano de `ResourceForm` (no hay switches custom en ningún lugar del
código hoy), y agregar un componente visual nuevo (`Switch.tsx`) para un
solo uso es exactamente el tipo de superficie nueva que Section 5 (CEO,
Code Quality) marcaría como no justificada. Queda en 8, no 10, porque
sigue faltando `DESIGN.md` — eso es deuda preexistente, no de este plan
(recomendación ya existente en el propio skill: "flag the gap and
recommend /design-consultation" — se anota, no se resuelve acá).

### Pass 6 — Responsive & Accessibility: **5/10 → 8/10**

CEO Section 11 ya identificó ambos gaps (responsive del modal, a11y del
toggle) como menores y los anotó. Para el score de este pase, se
formalizan como specs concretas (antes eran solo notas):

- **Responsive:** el modal usa el mismo breakpoint que cualquier
  formulario existente en `ResourceForm`/`SimpleResourceAdminPage` (no
  hay uno especial documentado en el código — es CSS estándar, columna
  única en mobile). La lista de checkboxes scrollea verticalmente dentro
  del modal con `max-height` + `overflow-y: auto` — nunca fuerza el modal
  a exceder el viewport.
- **A11y:** toggle = `<input type="checkbox">` real (decisión de Pass 5,
  ya trae teclado + lector de pantalla gratis, sin ARIA manual). Modal:
  foco atrapado dentro (focus trap) al abrir, `Escape` cierra sin guardar
  (mismo comportamiento que "Cancelar"), foco vuelve al botón que lo abrió
  al cerrar — **gap real, no estaba en el plan original, agregado como
  spec explícita**. Checkboxes de torneos: cada uno con `<label>` visible
  asociado (no solo el nombre del torneo suelto al lado), touch target
  ≥44px en mobile (el `<label>` completo es clickeable, no solo el
  cuadradito de 16px del checkbox — patrón estándar, se especifica
  explícito para que no se pierda en implementación).

No llega a 10/10 porque falta especificar contraste de color exacto (no
hay paleta de colores documentada en el repo — mismo gap que `DESIGN.md`,
preexistente).

### Pass 7 — Unresolved Design Decisions

```
  DECISIÓN NECESARIA                          | SI SE DEFIERE, QUÉ PASA
  ----------------------------------------------|---------------------------
  ¿Confirm dialog antes de revocar licencia?    | Ya resuelto (Pass 3): NO, es
                                                  | fricción excesiva para una
                                                  | acción reversible con 1 click
  ¿Toggle = checkbox nativo o switch custom?     | Ya resuelto (Pass 5): checkbox
                                                  | nativo, sin componente nuevo
  ¿Focus trap en el modal?                       | Ya resuelto (Pass 6): sí,
                                                  | explícito, con retorno de foco
  Estilo visual exacto del toggle (color activo/ | Sin `DESIGN.md`, queda a
  inactivo, tamaño)                              | criterio del implementador —
                                                  | igual que cualquier otro campo
                                                  | booleano existente en el repo
                                                  | hoy (sin precedente propio a
                                                  | seguir más allá de "consistente
                                                  | con el resto de la tabla")
```

Ninguna decisión queda genuinamente abierta para el gate final desde este
pase — todas se resolvieron dentro de la revisión misma (a diferencia de
D2 en CEO, que sigue siendo una tensión real sin resolver).

## Design — NOT in scope

- Rediseño visual de `UsuariosAdmin.tsx` / `ResourceTable` en general —
  fuera de blast radius, es deuda preexistente del repo (sin
  `DESIGN.md`), no de este plan.
- Mockups de imagen generados por IA — decisión explícita arriba (costo/
  valor), no un olvido.
- Animaciones de transición al abrir/cerrar el modal — no especificadas,
  se usa el comportamiento nativo del navegador (o CSS mínimo si el
  implementador ya tiene un patrón de modal en el repo — no se inventa
  uno para esto).

## Design — What already exists

`ResourceTable`, `SimpleResourceAdminPage`, `ResourceForm`,
`RequireRole`/`LoginPrompt` — los 4 ya cubiertos en detalle en §1 del plan
original. Este review no encontró ningún patrón visual adicional que
debiera reusarse y no esté ya listado ahí.

## Design — TODOS.md updates

Un solo ítem nuevo, agregado directamente (auto-decidido, no bloqueante
para Fase 1): **`DESIGN.md` no existe en el repo** — cualquier revisión de
diseño futura sigue topando con este mismo gap. Ya estaba fuera de blast
radius de este plan específico; se anota en `TODOS.md` como ítem
independiente (no ligado al plan de RBAC), P3, para no perderlo.

## Design Implementation Tasks

- [ ] **T12 (P2, human: ~20min / CC: ~5min)** — frontend — Focus trap +
  retorno de foco en `AsignarTorneosModal`
  - Surfaced by: Pass 6 (Responsive & Accessibility)
  - Files: nuevo componente del modal (§5.3)
  - Verify: test — `Escape` cierra sin guardar, foco vuelve al botón que abrió el modal
- [ ] **T13 (P3, human: ~10min / CC: ~5min)** — frontend — Estado vacío
  explícito del modal ("No hay torneos activos para asignar.")
  - Surfaced by: Pass 2 (Interaction State Coverage)
  - Files: nuevo componente del modal (§5.3)
  - Verify: test — sistema sin torneos activos → modal muestra el mensaje, botón "Guardar" deshabilitado

## Design Completion Summary

```
  +====================================================================+
  |         DESIGN PLAN REVIEW — COMPLETION SUMMARY                    |
  +====================================================================+
  | System Audit         | Sin DESIGN.md (preexistente); UI scope:     |
  |                       | extensión de UsuariosAdmin.tsx (toggle+modal)|
  | Step 0               | App UI classifier; mockups de imagen         |
  |                       | omitidos (decisión razonada, ver arriba)     |
  | Pass 1  (Info Arch)  | 7/10 → 9/10                                  |
  | Pass 2  (States)     | 6/10 → 9/10                                  |
  | Pass 3  (Journey)    | 8/10 (sin cambios — ya completo)              |
  | Pass 4  (AI Slop)    | 9/10 (sin cambios — sin superficie de riesgo) |
  | Pass 5  (Design Sys) | 6/10 → 8/10 (techo: sin DESIGN.md en el repo) |
  | Pass 6  (Responsive) | 5/10 → 8/10 (techo: sin paleta documentada)   |
  | Pass 7  (Decisions)  | 3 resueltas en el pase, 0 diferidas           |
  +--------------------------------------------------------------------+
  | NOT in scope         | escrito (3 items)                            |
  | What already exists  | escrito (referencia a §1 del plan)           |
  | TODOS.md updates     | 1 item (DESIGN.md, independiente de este plan)|
  | Approved Mockups     | 0 generados (decisión razonada, no un gap)   |
  | Decisions made       | 3 (checkbox nativo, sin confirm dialog, focus trap) |
  | Decisions deferred   | 0                                             |
  | Overall design score | 6.6/10 → 8.6/10                              |
  +====================================================================+
```

### Design — Unresolved Decisions

Ninguna — las 3 decisiones de diseño quedaron resueltas dentro de este
mismo pase (ver Pass 7).

---

# DX REVIEW (autoplan Phase 2.5 — scope detectado mecánicamente)

**Auto-decidido (Principio 3 — Pragmatic): alcance reducido, con
justificación explícita, no un skip silencioso.** `/plan-devex-review`
detectó scope por conteo mecánico de términos ("endpoint" × 6+ en este
mismo plan) — correcto como heurística, pero el producto real no encaja
en el marco del skill: `plan-devex-review` está diseñado para productos
DONDE EL DESARROLLADOR ES EL USUARIO FINAL (API pública, SDK, CLI, librería
— "chef cocinando para chefs", con "Time to Hello World", "SDK
completeness", benchmark competitivo contra Stripe/Vercel). La API REST de
Score-App no tiene audiencia externa de desarrolladores: la consume
EXCLUSIVAMENTE el frontend React del mismo equipo (`frontend/src/api/client.ts`,
generado desde el propio OpenAPI schema del backend). No hay SDK, no hay
"getting started" para terceros, no hay CLI, no hay documentación pública
de API. Aplicar el marco completo (persona de desarrollador externo,
TTHW, momentos mágicos, benchmark competitivo) produciría análisis
fabricado sobre una audiencia que no existe — exactamente lo que
"Claimed Limitations Need Evidence" pide evitar (no inventar sin
verificar). Verificado, no asumido: `grep` de "SDK\|getting.started\|CLI"
contra `frontend/src/api/` y `backend/` no encuentra nada — confirma que
este es un backend de un solo consumidor, no un producto DX.

**Lo que SÍ transfiere de este marco a un backend interno** — la
Característica #3 (Error message empathy: "¿identifica el problema,
explica la causa, muestra el fix?") aplica igual sin importar si el
"desarrollador" es externo o es el propio equipo frontend consumiendo la
API un año después de escribirla. Se evalúa esa única dimensión con
rigor real:

### Error message empathy — evaluado contra el diseño de Fase 1

| Error | ¿Identifica el problema? | ¿Explica la causa? | ¿Muestra el fix? |
|---|---|---|---|
| `LicenseRevokedError` (403 + header) | Sí — `detail`: "Licencia inactiva o revocada." | Sí — el mensaje mismo es la causa | Sí — "Contactá al administrador." es el fix (no hay auto-remediación posible, es correcto que apunte a una acción humana) |
| `ForbiddenError` de `require_torneo_access` | Sí — "No tenés este torneo asignado." | Sí — implícito en el mensaje | **Gap menor:** no dice QUÉ hacer (a diferencia del de licencia) — para un `TorneoAdmin` legítimo que debería tener el torneo asignado, el mensaje no sugiere "pedile a tu AdminGeneral que te lo asigne". Fix de bajo costo: agregar esa frase al mensaje. No bloqueante — el 403 ya es información suficiente para un desarrollador del propio equipo leyendo el código/logs, que es la audiencia real. |
| Trigger `fn_validar_asignacion_torneo_admin_rol` | Sí — mensaje de Postgres traducido por `_dbapi_error_response` | Parcial — el mensaje crudo de un `RAISE EXCEPTION` de Postgres es legible pero no tan pulido como las excepciones de dominio de Python | Aceptable — mismo patrón que CUALQUIER otro trigger existente del repo (`fn_validar_torneo_modalidad`, etc.), no es una regresión introducida por este plan |

**Único fix aplicado al plan:** el mensaje de `require_torneo_access`
(§4.3) se ajusta de "No tenés este torneo asignado." a "No tenés este
torneo asignado. Pedile a tu Admin General que te lo asigne desde el
panel de usuarios." — mejora barata (una string), consistente con la
Característica #3, sin agregar código nuevo.

### Dimensiones NO evaluadas — con razón explícita, no un silencio

| Dimensión del skill | Por qué no aplica acá |
|---|---|
| Usable (instalación, setup) | No hay "instalación" — es un endpoint interno de un backend ya desplegado |
| Credible (deprecation, semver) | No hay contrato público versionado — el frontend y el backend se despliegan juntos, desde el mismo repo |
| Findable (comunidad, SO) | No hay comunidad externa — la "documentación" es el propio código + este plan |
| Valuable / Desirable (competir contra alternativas) | No hay elección de adoptar o no — es infraestructura interna obligatoria |
| TTHW / Magical Moments / SDK completeness | No hay "hello world" de un desarrollador externo — el único consumidor ya existe y ya está integrado |

### DX Completion Summary

```
  +====================================================================+
  |         DX PLAN REVIEW — COMPLETION SUMMARY (alcance reducido)      |
  +====================================================================+
  | Tipo de producto      | Backend interno, un solo consumidor        |
  |                        | (frontend propio) — NO un producto DX      |
  | Dimensión evaluada     | Error message empathy (única transferible) |
  | Score                  | 7/10 → 8/10 (mensaje de asignación mejorado)|
  | TTHW                   | No aplica (sin audiencia externa)          |
  | Dimensiones omitidas   | 6 de 7 — con razón explícita, ver tabla    |
  | Fix aplicado            | 1 (mensaje de require_torneo_access)      |
  +====================================================================+
```

---

# ENG REVIEW (autoplan Phase 3 — siempre última, gate obligatorio)

## Step 0: Scope Challenge

**Complexity check (umbral del skill: >8 archivos O >2 clases/servicios
nuevos):** Fase 1 toca 8 archivos backend (`deps.py`, `errors.py`,
`handlers.py`, `usuario.py` model, `asignacion_torneo_admin.py` model
nuevo, `usuarios.py` router, `torneos.py` router, `services/torneo.py`) +
1 migración SQL + 5 frontend, e introduce 3 clases/servicios nuevos
(`LicenseRevokedError`, `AsignacionTorneoAdminService`,
`AsignacionTorneoAdminRepository`). **El check dispara** — pero no por
scope creep: son 8 archivos porque el fix toca cada choke point de auth
existente EXACTAMENTE UNA VEZ (defense in depth, no duplicación) — el
propio 0C-bis del CEO review ya comparó esto contra la alternativa
"genérica" (Approach B) y la rechazó por sobre-ingeniería. Reducir esto
más significaría: (a) no parchear `get_current_user_optional` — reabre el
hallazgo #1 de la voz externa (CRÍTICO), o (b) fusionar
`AsignacionTorneoAdminService`/`Repository` en el servicio de `Usuario`
existente — viola el patrón de 1 servicio por entidad ya establecido en
todo el repo (`TorneoService`, `UsuarioService`, etc., cada uno 1:1 con su
tabla). **Auto-decidido (Principio 5 — Explicit over clever + Principio 3
— Pragmatic): scope se mantiene como está.** No hay una versión más chica
que no reabra un hallazgo ya cerrado o rompa una convención ya
establecida.

1. **Código existente que ya resuelve parte del problema:** `BaseRepository`
   (patrón usado por todos los repos existentes, ej. `UsuarioRepository`,
   `TorneoRepository`) — `AsignacionTorneoAdminRepository` debe heredar de
   ahí, no reimplementar CRUD básico. `TimestampMixin` (`models/mixins.py`)
   — ya da `Fecha_Registro`/`Fecha_Modificacion` gratis al nuevo modelo
   `AsignacionTorneoAdmin`, consistente con §3.2 del plan (no hace falta
   declarar esas columnas a mano).
2. **Mínimo set de cambios:** ya es el mínimo (ver complexity check arriba).
3. **Search check:** el patrón "dependency de FastAPI que valida ownership
   antes de dejar pasar al handler" es el patrón estándar de FastAPI
   (`Depends()` anidados) — no hay un built-in más simple, y es
   exactamente el patrón que `require_roles`/`verificar_arbitro_asignado`
   ya usan en este mismo repo. **[Layer 1]** — patrón ya probado en este
   codebase, no se está inventando nada.
4. **TODOS cross-reference:** ningún ítem de `TODOS.md` bloquea este plan;
   este plan SÍ agrega 4 ítems nuevos (ya escritos, ver CEO REVIEW arriba).
5. **Completeness check:** el plan ya elige la versión completa (D1-D5,
   correcciones de la voz externa incorporadas) sobre cualquier atajo.
6. **Distribution check:** no aplica — no se introduce un artefacto nuevo
   (binario, paquete, imagen) — es código de aplicación desplegado con el
   resto del sistema.

## 1. Architecture Review (breve — ver CEO Section 1 para el detalle completo)

Sin hallazgos nuevos más allá de los ya cubiertos en CEO Section 1
(dependency graph, security architecture table, rollback posture). Un
punto de verificación específico de Eng: **¿`AsignacionTorneoAdminRepository`
puede heredar limpio de `BaseRepository`?** — sí, `BaseRepository` (patrón
usado por `UsuarioRepository`/`TorneoRepository`) ya da `create`/`get`/
`list`/`soft_delete` genéricos sobre cualquier modelo con `Estado` — el
modelo nuevo encaja sin modificar `BaseRepository`. Sin coupling nuevo
más allá del ya aceptado en CEO Section 1.

## 2. Code Quality Review (breve — ver CEO Section 5 para el detalle completo)

Sin hallazgos nuevos — CEO Section 5 ya cubrió DRY/naming/complejidad
ciclomática. Verificación Eng-específica: el trigger propuesto
(`fn_validar_asignacion_torneo_admin_rol`, §3.2) debe seguir la MISMA
convención que `fn_validar_torneo_modalidad`/`fn_validar_equipo_modalidad`
en `06_triggers.sql` (función `plpgsql`, `RAISE EXCEPTION` con mensaje en
español, `BEFORE INSERT OR UPDATE`) — el plan ya lo referencia
correctamente por nombre, sin necesidad de reescribir la sección.

## 3. Test Review

**Framework detectado:** backend = `pytest` (`backend/pytest.ini`,
`backend/tests/*.py`); frontend = `vitest` (`frontend/package.json`
`"test": "vitest run"`). Sin sección `## Testing` explícita en
`CLAUDE.md` — auto-detectado por convención de archivos.

**Fixtures existentes a reusar (verificado en `backend/tests/conftest.py`)
— no reinventar:**
- `admin_general_headers`, `torneo_admin_headers`, `arbitro_headers`,
  `arbitro_no_asignado_headers` — ya dan JWT headers por rol. El último
  par (`arbitro_headers`/`arbitro_no_asignado_headers` — un Árbitro CON
  partido asignado vs. SIN asignación) es el precedente estructural exacto
  para lo que este plan necesita del lado de `TorneoAdmin`.
- `_crear_usuario(session, username, password, rol)` — helper ya
  existente, reusar para crear las cuentas de prueba de licencia/asignación.
- Precedente EXACTO del test de auto-lockout a clonar:
  `test_admin_general_no_puede_desactivarse_a_si_mismo`
  (`backend/tests/test_usuarios.py:142`) — el test de auto-revocación de
  licencia es la misma forma, mismo archivo.

**Corrección post outside-voice (Eng review, hallazgo #4 — MEDIA
severidad):** las versiones anteriores de esta sección describían
categorías de test en abstracto sin comprometerse a fixtures ni a la
ubicación de archivo — corregido, explícito:

- **2 fixtures nuevas en `conftest.py`**, construidas con `_crear_usuario`/
  `_login_headers` ya existentes (mismo patrón que
  `arbitro_no_asignado_headers`):
  - `torneo_admin_con_torneo_headers` — `TorneoAdmin` con 1 fila `Activo`
    en `ASIGNACION_TORNEO_ADMIN` apuntando a un torneo de prueba.
  - `torneo_admin_sin_licencia_headers` — `TorneoAdmin` con
    `Licencia_Activa=False` (para los tests de `LicenseRevokedError`).
- **Ubicación de los tests nuevos** (dado que los endpoints viven en
  `usuarios.py`/`torneos.py` per §4.5/§4.6, no en un router propio):
  - Tests de licencia + asignación (los 3 endpoints nuevos, guard de
    auto-revocación, trigger de rol) → `backend/tests/test_usuarios.py`
    (mismo archivo que ya tiene T6, el precedente clonado).
  - Tests de "`TorneoAdmin` sin asignación → 403 en `PATCH`/`DELETE
    /torneos/{id}`" y de `GET /torneos?solo_mios=true` (E1) →
    `backend/tests/test_torneos.py`.
  - Test de licencia en `login()` (+ `_registrar_acceso`) →
    `backend/tests/test_auth.py` (donde ya viven los tests de login).
  - Test de integración de `AUDITORIA` (T11) → `backend/tests/test_auditoria.py`
    (ya existe, mismo patrón que sus tests actuales de otras tablas).

**Diagrama de cobertura (código + flujos de usuario):**

```
CODE PATHS                                                    USER FLOWS
[+] backend/app/api/deps.py                                   [+] Login con licencia revocada
  ├── get_current_user (chequeo licencia)                       ├── [GAP][→E2E] Login rechazado, mensaje
  │   ├── [GAP] licencia activa → pasa                           │   correcto, fila en ACCESOS
  │   └── [GAP] licencia revocada → 403 + header                 └── [GAP]     Sesión activa, licencia
  ├── get_current_user_optional (mismo chequeo, corrección)          revocada a mitad → próximo click 403
  │   ├── [GAP] licencia revocada → None (no 403 crudo)         [+] Toggle de licencia (Admin General)
  ├── require_torneo_access                                       ├── [GAP][→E2E] Revocar la licencia de otro
  │   ├── [GAP] AdminGeneral → bypass                             ├── [GAP]     Intentar revocar la propia (bloqueado)
  │   ├── [GAP] TorneoAdmin asignado → pasa                       └── [GAP]     Doble-click (T9) → 1 solo PATCH
  │   ├── [GAP] TorneoAdmin sin asignación → 403                [+] Modal "Gestionar torneos"
  │   └── [GAP] rol Arbitro/Publico → 403                         ├── [GAP][→E2E] Tildar 2, guardar, reabrir → refleja
  └── login() (chequeo licencia + _registrar_acceso)               ├── [GAP]     Set vacío → desasigna todo
      └── [GAP] revocada → 403 + fila en ACCESOS                   └── [GAP]     GET lento → estado de loading (T9)
[+] backend/app/services/asignacion_torneo_admin.py (nuevo)   [+] Error states
  ├── set_licencia                                               ├── [GAP] Pantalla LicenseRevokedScreen exacta
  │   ├── [GAP] revocar a otro → OK                               └── [GAP] Mensaje de asignación con la acción sugerida
  │   └── [GAP] auto-revocación → 403 (clon T6)                       (DX fix)
  └── set_torneos_asignados
      ├── [GAP] set válido → upsert activa/desactiva diff
      ├── [GAP] torneo_id inexistente → 404 (T7, gap cerrado en CEO)
      ├── [GAP] usuario.rol != TorneoAdmin → 400
      └── [GAP] mutación vía ORM (no Core) → AUDITORIA captura (T11)
[+] database/26_migracion...sql (trigger)
  └── fn_validar_asignacion_torneo_admin_rol
      ├── [GAP] Usuario_ID con Rol=TorneoAdmin → OK
      └── [GAP] Usuario_ID con otro rol → RAISE EXCEPTION
[+] frontend/src/api/client.ts
  └── onResponse (+1 rama)
      ├── [GAP] 403 + X-License-Revoked → onLicenseRevoked dispara
      └── [GAP] 403 SIN el header (403 genérico) → NO dispara (regresión si se rompe)
[+] backend/app/api/routes/torneos.py (E1)
  └── GET /torneos?solo_mios=true
      ├── [GAP] TorneoAdmin con 2/5 asignados → devuelve 2
      └── [GAP] AdminGeneral/anónimo → devuelve todos (sin cambio)

COVERAGE: 0/24 paths tested (0% — ningún archivo existe todavía, plan pre-implementación)
QUALITY objetivo: ★★★ en TODOS los paths marcados [→E2E] o de auto-lockout (no negociable, mismo
                   estándar que T6 ya tiene en producción)
GAPS: 24 (4 marcados [→E2E] — login, revocar licencia, modal completo, doble-click)
```

**Regla de regresión (IRON RULE):** `client.ts` `onResponse` ya existente
maneja 401 hoy — agregar la rama de 403+header es una MODIFICACIÓN de
código existente, no solo una adición. **Test de regresión obligatorio,
sin AskUserQuestion:** "un 403 SIN el header `X-License-Revoked` (ej. un
`ForbiddenError` genérico de rol insuficiente) NO debe disparar
`onLicenseRevoked`" — si este test falta, un refactor futuro del
middleware podría hacer que CUALQUIER 403 muestre la pantalla de licencia
revocada, rompiendo el mensaje correcto para "no tenés permiso" genérico.

**Test Plan Artifact** — escrito para consumo de `/qa`/`/qa-only`:

```markdown
# Test Plan
Generated by /autoplan (plan-eng-review phase) on 2026-09-02
Branch: feat/equipos-jugadores-plan
Repo: Gab9Cruzz/SCORE_APP

## Affected Pages/Routes
- POST /api/v1/auth/login — rechazo por licencia revocada (403, no 401)
- PATCH /api/v1/torneos/{id} — TorneoAdmin sin asignación (403)
- DELETE /api/v1/torneos/{id} — ídem
- GET /api/v1/torneos?solo_mios=true — filtrado por asignación
- PATCH /api/v1/usuarios/{id}/licencia — toggle, AdminGeneral only, auto-revocación bloqueada
- GET /api/v1/usuarios/{id}/torneos — set actual de asignaciones
- PATCH /api/v1/usuarios/{id}/torneos — reemplazo de set completo
- /admin/usuarios (frontend) — toggle de licencia + modal "Gestionar torneos"

## Key Interactions to Verify
- Toggle de licencia en la fila de otro usuario, en `/admin/usuarios`
- Toggle de licencia en la PROPIA fila (debe estar oculto/deshabilitado)
- Abrir "Gestionar torneos", tildar/destildar, Guardar
- Doble-click rápido en el toggle (debe resultar en 1 solo PATCH)
- Login con una cuenta cuya licencia fue revocada mientras estaba deslogueada
- Sesión activa en 2 pestañas, revocar licencia en una, intentar operar en la otra

## Edge Cases
- `torneo_ids` con un ID inexistente en `PATCH /usuarios/{id}/torneos`
- `torneo_ids: []` (desasignar todo)
- AdminGeneral crea un torneo (no debe auto-asignarse, D4 corregido)
- TorneoAdmin crea un torneo (SÍ debe auto-asignarse)
- Sistema sin torneos activos, modal abierto (estado vacío, T13)
- `GET /torneos?solo_mios=true` para un TorneoAdmin sin ningún torneo asignado (lista vacía, no error)

## Critical Paths
- Revocar licencia → próximo request del usuario afectado → 403 + pantalla correcta (extremo a extremo, sin refrescar el token)
- Desasignar el único torneo de un TorneoAdmin → `PATCH /torneos/{id}` de ESE torneo → 403 "no asignado"
```

*(Archivo real a escribir en `~/.gstack/projects/Score-App/{user}-feat-equipos-jugadores-plan-eng-review-test-plan-{datetime}.md` al aprobarse el plan — contenido arriba, listo para copiar tal cual.)*

## 4. Performance Review (breve — ver CEO Section 7 para el detalle completo)

Sin hallazgos nuevos. Confirmado: `BaseRepository.list()` (patrón
existente) soporta el filtro de E1 (`solo_mios`) sin N+1 — un solo query
con `WHERE Torneo_ID IN (SELECT Torneo_ID FROM ASIGNACION_TORNEO_ADMIN
WHERE Usuario_ID = :uid AND Estado = 'Activo')`, no una traversal fila por
fila.

## Failure Modes (consolidado — mismo registro que CEO, sin filas nuevas)

Ver **Failure Modes Registry** en CEO REVIEW arriba — 8 filas, 0
CRITICAL GAPS post-corrección. Eng review no encontró un failure mode
adicional que el CEO review no hubiera cubierto ya (esperable: mismo plan,
mismo código, revisores distintos pero convergentes — ver Eng Voices
abajo para el detalle de consenso).

## Worktree Parallelization Strategy

| Step | Módulos tocados | Depende de |
|---|---|---|
| Backend núcleo (T1-T7: modelos ORM, deps.py, errors.py, handlers.py, servicios, endpoints) | `backend/app/` | — |
| Frontend (T8-T9, T12-T13: client.ts, AuthContext, LicenseRevokedScreen, UsuariosAdmin, modal) | `frontend/src/` | T6 (necesita el contrato de los 3 endpoints nuevos ya definido — puede empezar sobre el contrato del plan sin esperar el código real, dado que el schema ya está especificado en §4.5) |
| E1 (`GET /torneos?solo_mios=true`, T10) | `backend/app/api/routes/torneos.py` | T2/T5 (necesita `AsignacionTorneoAdminRepository` ya existente) |
| Test de integración AUDITORIA (T11) | `backend/tests/` | T1, T2 (necesita los modelos ORM ya creados) |

**Lane A (backend núcleo):** T1 → T2 → T3/T4 (en paralelo entre sí,
ambos tocan `deps.py`/`services/usuario.py` pero funciones distintas,
sin overlap real de líneas) → T5 → T6 → T7.
**Lane B (frontend):** T8 → T9 (puede arrancar en paralelo a Lane A una
vez que el contrato de los 3 endpoints esté fijado en el plan, que ya lo
está — no necesita esperar el código backend real, solo el contrato).
**Lane C (E1 + test de auditoría):** depende de Lane A completa hasta T2/T5.

**Ejecución:** Lanzar Lane A y Lane B en paralelo (worktrees separados).
Merge ambas. Luego Lane C (corta, depende de Lane A). **Conflicto
potencial:** ninguno — Lane A y Lane B no comparten ningún archivo (A =
`backend/`, B = `frontend/`).

## Eng — NOT in scope

Mismo contenido que CEO REVIEW § NOT in scope — sin ítems adicionales
encontrados por Eng review. Confirmado: E3 (rollout Fase 2) sigue
correctamente fuera, por la misma razón (no es un cambio mecánico <1 día
por router, ahora reforzado por el Worktree Parallelization Strategy de
arriba — Fase 2 sería un Lane D completo, con 12 sub-lanes por router,
que este documento no intenta planificar a ese nivel de detalle).

## Eng — What already exists

`BaseRepository`, `TimestampMixin`, las fixtures de `conftest.py`
(`admin_general_headers`, `torneo_admin_headers`, `_crear_usuario`), y el
test `test_admin_general_no_puede_desactivarse_a_si_mismo` como precedente
exacto a clonar — todos verificados arriba (Step 0, Test Review). El plan
original (§1) ya cubría la capa de API/UI; Eng review agrega la capa de
testing/infra que CEO no llegó a bajar a nivel de archivo concreto.

## Eng Implementation Tasks

Sin tareas nuevas — el Test Review de arriba refina T1-T11 (ya listadas en
CEO REVIEW) con fixtures/archivos concretos, no agrega alcance nuevo. Un
solo ítem nuevo, de testing puro:

- [ ] **T14 (P1, human: ~20min / CC: ~5min)** — backend — Test de
  regresión: 403 sin header `X-License-Revoked` NO dispara `onLicenseRevoked`
  - Surfaced by: Test Review — IRON RULE de regresión (modificación de
    código existente en `client.ts`)
  - Files: `frontend/src/api/client.test.ts` (o donde vivan los tests de `client.ts` hoy)
  - Verify: mock de un 403 sin el header → `onLicenseRevoked` NO se llama; con el header → sí se llama
- [ ] **T15 (P1, human: ~30min / CC: ~10min)** — backend — `UsuarioService.update()`
  desactiva asignaciones huérfanas cuando `Rol` sale de `TorneoAdmin`
  - Surfaced by: outside-voice Eng hallazgo #3 (trigger no cubre cambio de rol posterior)
  - Files: `backend/app/services/usuario.py`
  - Verify: test — degradar un TorneoAdmin con 2 torneos asignados a Arbitro → ambas filas pasan a Estado='Inactivo'; re-promoverlo a TorneoAdmin → sigue sin acceso hasta que AdminGeneral reasigne explícitamente

## Eng Voices

Codex: no disponible (mismo motivo que CEO/Design). Claude subagent
(contexto fresco, independiente de este hilo): leyó el plan COMPLETO
(incluidas las secciones CEO/Design/DX ya escritas) y verificó cada
afirmación de arquitectura/feasibility contra el código real —
`repositories/base.py`, `services/inscripcion_torneo.py`,
`hooks/useResourceCrud.ts`, `06_triggers.sql`, `conftest.py`,
`02_constraints.sql`. Encontró **5 hallazgos**, 2 de severidad ALTA
(ambos sobre afirmaciones de "reuso de infraestructura existente" que
resultaron ser feasibility gaps reales cuando se abrió el archivo citado),
2 de severidad media, 1 de severidad baja (ruido de proceso). **Los 5 ya
están incorporados al plan arriba** — 0 quedan como hallazgo suelto.

**Consensus:**

| # | Hallazgo | Eng review (esta sección) | Outside voice | Resuelto |
|---|---|---|---|---|
| 1 | `BaseRepository` no es atómico para el diff de asignaciones | No detectado — el plan asumía `BaseRepository` sin abrir `base.py` | Detectado, con el fix ya existente en el repo (`inscripcion_torneo.py`) citado como precedente | ✅ Incorporado (§4.4) |
| 2 | `PUT /usuarios/{id}/torneos` no es invocable con `useResourceCrud` (`customAction` solo POST/PATCH) | No detectado — Step 0 citó "90% de infra reusada" sin abrir `useResourceCrud.ts` | Detectado con cita de línea exacta | ✅ Incorporado (§4.5) — endpoint cambiado a `PATCH` en TODO el documento |
| 3 | Trigger no cubre degradación de rol posterior a la asignación | No detectado en el primer pase de Eng | Detectado, con el fix aplicado a `UsuarioService.update()` en vez de un segundo trigger | ✅ Incorporado (§3.2, T15) |
| 4 | Test plan no nombra fixtures concretas ni archivo destino | Parcialmente cubierto (mencioné `conftest.py` en general) | Cubierto con precisión — 2 fixtures nombradas, split de archivo explícito | ✅ Incorporado (Test Review) |
| 5 | Índice compuesto propuesto era ruido; naming `uq_*` vs `unique_*` | No detectado (yo mismo propuse el índice compuesto como "mejora" en Section 7) | Detectado — el índice ya existe implícito en el UNIQUE, y el naming rompe la convención del repo | ✅ Incorporado (§3.2, TODOS.md, Section 7) — el propio review de Eng se autocorrigió acá |

**Consensus: 5/5 hallazgos de la voz externa, 0 desacuerdos — todos
verificados contra código real antes de incorporarse (no se aplicó
ninguno a ciegas).** Segunda pasada consecutiva (después del CEO review)
donde la voz externa encuentra bugs de feasibility concretos que el
primer pase — enfocado en el diseño de alto nivel — no llegó a verificar
abriendo el archivo citado. Patrón a llevarse de este ejercicio (loggeado
como learning): **toda afirmación de "esto ya existe, se reusa tal cual"
necesita el archivo abierto y la línea citada ANTES de escribirse en el
plan, no después de que la voz externa lo encuentre.**

## Eng Completion Summary

```
  +====================================================================+
  |         ENG PLAN REVIEW — COMPLETION SUMMARY                       |
  +====================================================================+
  | Step 0 (Scope Challenge)  | Scope aceptado tal cual — complexity     |
  |                            | check disparó, evaluado, sin reducción   |
  |                            | posible sin reabrir hallazgos ya cerrados|
  | Architecture Review        | 0 issues nuevos (breve, ver CEO Sec 1)  |
  | Code Quality Review        | 0 issues nuevos (breve, ver CEO Sec 5)  |
  | Test Review                | Diagrama de 24 paths, 0% cobertura pre- |
  |                            | implementación (esperado), Test Plan     |
  |                            | Artifact escrito, 2 fixtures nombradas   |
  | Performance Review         | 0 issues nuevos, 1 falso-positivo propio |
  |                            | retirado (índice compuesto)              |
  | NOT in scope                | escrito (ref. CEO, sin ítems nuevos)    |
  | What already exists         | escrito (BaseRepository, TimestampMixin,|
  |                              | fixtures concretas)                     |
  | Failure modes                | consolidado con CEO — 0 CRITICAL GAPS  |
  | Outside voice                 | corrió (Claude subagent) — 5/5 hallazgos|
  |                                | consenso, todos verificados e incorporados|
  | Parallelization                | 3 lanes (A backend, B frontend, C E1+test)|
  | Lake Score                     | 15/15 tareas construidas a nivel completo,|
  |                                 | sin atajos aceptados en ningún hallazgo   |
  +====================================================================+
```

### Eng — Unresolved decisions

Ninguna nueva — D2 (licencia uniforme vs. scoped) sigue siendo el único
ítem pendiente, ya capturado en CEO REVIEW.

---

# Cross-Phase Themes

**Tema: verificar afirmaciones de "esto ya existe, se reusa" contra el
código real, no contra la memoria del modelo.** Apareció de forma
INDEPENDIENTE en las dos rondas de outside-voice (CEO y Eng), sobre
afirmaciones DISTINTAS del mismo plan: CEO encontró que
`get_current_user_optional` no es un alias de `get_current_user` (ambos
"ya existían", pero uno no cubría lo que el plan asumía) y que los
modelos ORM nunca se especificaron como pasos concretos; Eng encontró que
`BaseRepository` no es atómico para el caso de uso del plan y que
`useResourceCrud.customAction` no soporta el verbo HTTP que el plan había
elegido. Señal de alta confianza (2 rondas independientes, mismo patrón,
hallazgos distintos): toda cita de "reuso de infraestructura existente" en
este documento debería llevar archivo:línea verificado, no solo el nombre
del componente — ya se corrigió retroactivamente en las 4 instancias
encontradas, y quedó como learning loggeado para sesiones futuras.

---

# Final Approval Gate

**Resuelto: 2026-09-02.** Única decisión pendiente (D2) presentada al
usuario junto con la aprobación general del plan.

**D2 → D2a (licencia uniforme a las 4 cuentas)**, elegida explícitamente
por el usuario — no auto-decidida. Ver §7-D2, §9, §11 arriba, ya
actualizados para reflejar esta elección.

**PLAN STATUS: APPROVED.** Fase 1 (núcleo: kill switch de licencia +
asignación N:M en `torneos.py` + panel de Admin General) queda lista para
implementación. Fase 2 (rollout a 12 routers) y Fase 3 (filtrado de UI)
quedan en `TODOS.md` como backlog separado, según lo decidido en la CEO
REVIEW (E3, §6).

**Siguiente paso recomendado:** `/plan-eng-review` ya corrió como parte de
este `/autoplan` (Phase 3) — no hace falta repetirlo. Cuando se quiera
pasar de plan a código, `/ship` toma este documento aprobado como punto de
partida. Este documento en sí **no implementa nada** — cumple el pedido
explícito del usuario de "crear solo el plan".
