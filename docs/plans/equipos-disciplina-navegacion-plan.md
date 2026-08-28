# Plan: Equipos con Disciplina + Filtrado Estricto + Navegación de Torneos

Generado con `/gstack-autoplan` (revisión CEO → Design → Eng). Codex no está
disponible en esta máquina (`codex` no está en PATH) — corrió en modo
`[subagent-only]`, una sola voz revisora (Claude), mismo estado que
`equipos-jugadores-plan.md`, `torneos-admin-plan.md` y
`ediciones-catalogo-disciplinas-plan.md`.

Estado: **IMPLEMENTADO.** Las 3 decisiones abiertas se resolvieron con la
opción recomendada de cada una — **A1** (plantilla derivada), **B1**
(Categoría = Modalidad) y **C2** (backfill + `NOT NULL`, huérfanos a
`Inactivo`) — más **EC-44 literal** (al inscribir se valida solo la
Disciplina, no la Modalidad) y las **4 mejoras propuestas**.

Todo lo del plan está en el código, salvo lo que quedó explícitamente
deferido (ver `TODOS.md`, sección "Deferido desde el plan de Equipos con
Disciplina + Navegación").

Verificación: **140 tests de backend** y **113 de frontend** en verde
(eran 129 y 89 antes de este plan). La migración `13_*.sql` se corrió
end-to-end contra una base descartable con el esquema viejo, cubriendo T9
(equipo ambiguo) y T10 (equipo huérfano) — el script queda en
`backend/scripts/verificar_migracion_13.py` para poder repetirlo.

**Migración aplicada a `torneos_mvp`** (backup previo en
`database/backups/torneos_mvp_pre_equipos_disciplina_20260827_211414.dump`).
267 equipos con `Disciplina_ID`/`Modalidad_ID` NOT NULL, cero pares
incoherentes, cero inscripciones cruzadas, trigger activo. Hubo **1
huérfano** (`Equipo A`, creado ese mismo día probando el formulario viejo,
sin inscripciones ni partidos): el script frenó como está diseñado y se
resolvió borrándolo, decisión del usuario. **0 ambiguos.**

<details>
<summary>Estado original del documento (antes de implementar)</summary>

Documento de planificación únicamente — cero código, cero cambios de
esquema aplicados. El usuario pidió explícitamente solo el `.md` para
leerlo antes de implementar ("necesito que crees el md, no hagas nada
aun").

Hay 3 decisiones marcadas para tu confirmación (Decision Audit Trail
#1, #2, #3). Las tres nacen del mismo hallazgo: dos de los cuatro pedidos
asumen un modelo de datos que hoy **no existe**, y elegir cómo crearlo no
es una decisión mecánica. Ver "Decisiones que requieren tu confirmación"
al final — el resto del plan está escrito asumiendo la opción recomendada
de cada una, y señala explícitamente qué cambia si elegís otra.

</details>

---

## Resumen del módulo

Cuatro pedidos que parecen independientes pero comparten un solo eje:
**la Disciplina tiene que dejar de vivir únicamente en el Torneo y pasar
a ser un atributo del Equipo.** Sin eso, tres de los cuatro no se pueden
implementar de verdad (solo aparentar).

**A. Módulo de Gestión de Equipos** (`/torneo-admin/equipos`) — crear un
equipo exigiendo Disciplina, pedir la plantilla en el mismo flujo, y una
grilla con columnas Plantilla / Categoría / Disciplina, componentizada
para crecer.

**B. Filtrado estricto en "Agregar Equipo"** — en "Ver Torneo", solo se
ofrecen y solo se aceptan equipos de la misma Disciplina del torneo.
Frontend **y** validación en la API.

**C. Redirección tras "Nueva Edición"** — al crear una edición nueva,
caer directo en la pestaña "Agregar Equipo" de esa edición, con la
validación de disciplina heredada.

**D. Navegación tipo SofaScore en `/torneo-admin/torneos`** — barra
horizontal scrollable de Disciplinas y Modalidades con chips/iconos que
filtra el listado en vivo.

**Estos cuatro no son del mismo tamaño de riesgo.** C es un fix de ~15
líneas sobre una pantalla ya construida. D es UI nueva sobre datos que ya
existen. **A y B tocan el esquema**: hoy `EQUIPOS` es literalmente
`(ID, Nombre, Fecha_Registro, Fecha_Modificacion, Estado)` — no tiene
Disciplina, no tiene Categoría, y su "plantilla" no existe a nivel de
equipo (ver premisas abajo). Ese es el trabajo real de este plan.

---

## Fase 1 — CEO Review (Estrategia y Alcance)

### Premisas (verificadas leyendo el código, no asumidas)

| # | Premisa del pedido | Veredicto | Evidencia |
|---|---|---|---|
| P1 | "Al crear un equipo se elige la Disciplina" — el campo existe o es fácil de agregar | ⚠️ **No existe.** Cambio de esquema | `backend/app/models/equipo.py` tiene 4 columnas: `id`, `nombre`, `estado` + timestamps. `database/01_schema.sql:78-84` confirma. Ninguna FK a `DISCIPLINA` |
| P2 | "Inmediatamente después debe solicitar los jugadores (plantilla)" — un equipo puede tener plantilla | ❌ **Falso hoy.** Un equipo, por sí solo, no puede tener plantilla | `JugadorEquipo.inscripcion_torneo_id` es **NOT NULL** (`models/jugador_equipo.py`). La plantilla cuelga de `INSCRIPCIONES_TORNEO` (torneo + equipo), no de `EQUIPOS`. Un equipo creado desde el catálogo global no está en ningún torneo → no tiene dónde colgar jugadores |
| P3 | "Columna Categoría" — el dato existe | ❌ **No existe en ningún lado.** `grep -ri categoria` sobre `.py`/`.tsx`/`.sql` devuelve **cero** resultados en todo el repo | Concepto nuevo, sin definición. Ver Decisión #2 |
| P4 | "Columna Plantilla (cantidad)" — se puede contar | ⚠️ Solo sumando **todos** los torneos del equipo. No hay "la plantilla del equipo", hay N plantillas (una por inscripción) | `GET /plantillas?inscripcion_torneo_id=` o `?torneo_id=` — nunca `?equipo_id=` |
| P5 | "El filtro de Agregar Equipo hoy no filtra por disciplina" | ✅ **Confirmado** | `ModalAgregarInscripcion.tsx`, `equiposDisponibles`: filtra por `!equiposYaInscritosIds.has(e.id)` y por texto. Nada más |
| P6 | "La API tampoco valida la disciplina al inscribir" | ✅ **Confirmado, y es peor de lo que parece** | `InscripcionTorneoService.create()`: si viene `equipo_id`, hace `return await self.repo.create(torneo_id=..., equipo_id=...)` — **cero validación**. Ni siquiera verifica que el torneo exista |
| P7 | "Nueva Edición deja al admin en una pantalla vacía" | ⚠️ **Verdadero por un camino, falso por el otro** | `TorneosAdmin.tsx` → `crearTorneo.onSuccess` → `setModo({tipo:"lista"})` = vuelve al listado ✅ el pedido aplica. Pero `TorneoDashboard.tsx` → `crearEdicion.onSuccess` → `navigate("/torneo-admin/torneos/{id}")` → el `<Route index>` redirige a `equipos` — **ese camino ya hace lo pedido**. Hay dos entradas a "Nueva edición" y solo una está rota |
| P8 | "El listado de torneos se puede filtrar por Disciplina/Modalidad" | ✅ El dato está, la UI no | `GET /torneo-grupos` devuelve `ediciones[].disciplina_id` y `.modalidad_id`. `TorneosAdmin.tsx` ya cruza contra `/disciplinas` y `/modalidades`. Falta solo la barra y el estado de filtro |
| P9 | "Poner chips con iconos por disciplina es barato" | ⚠️ **28 disciplinas / 66 modalidades** cargadas por `11_catalogo_disciplinas.sql`. 94 chips no entran en una barra, y 28 iconos son 28 assets a producir | Ver Fase 2, sección D |

**Lectura de las premisas:** el pedido está bien planteado como producto,
pero **P2 y P3 describen un sistema que no es el que está construido**.
No es un malentendido del usuario: es la deuda natural de haber modelado
la plantilla como "quiénes juegan por este equipo *en este torneo*"
(que es lo correcto para traspasos, dorsales y exclusividad) y ahora
querer una vista "quiénes son de este equipo" que esa forma no responde.

### Qué ya existe (leverage map)

| Sub-problema del pedido | Ya construido | Qué falta |
|---|---|---|
| Grilla CRUD de Equipos | `SimpleResourceAdminPage` + `ResourceTable` + `useResourceCrud` — `EquiposAdmin.tsx` son 27 líneas de configuración | Columnas calculadas (no `row[key]` plano) y un formulario multi-paso. `SimpleResourceAdminPage` no soporta ninguno de los dos |
| Formulario con campo Disciplina dependiente | `TorneosAdmin.camposTorneoNuevo()` ya hace exactamente esto (Disciplina → filtra Modalidad) con `ResourceForm` de campos dinámicos | Reusar el patrón, no reinventarlo (P4 DRY) |
| Alta de plantilla multi-fila | `RegistroLoteAdminPage` + `POST /registro-lote` completo, con validación EC-2/3/4/9, cupo por modalidad y confirmación atómica | Hoy exige `inscripcion_torneo_id`. Es la pieza más valiosa a reusar |
| Catálogo Disciplina/Modalidad | `GET /disciplinas`, `/disciplinas/con-modalidades`, `/modalidades?disciplina_id=`, `CatalogoDisciplinasPage` | Nada — se consume tal cual |
| Filtro por disciplina en la API de inscripción | Nada | Todo (ver Fase 3) |
| Barra de navegación horizontal | Nada. `.admin-nav` existe pero es un `<nav>` de tabs fijos, no scrollable ni con chips | Componente nuevo |
| Redirect post-creación | `TorneoDashboard.crearEdicion` ya lo hace bien | Replicarlo en `TorneosAdmin` |

**El leverage más importante: `RegistroLoteAdminPage` ya resuelve el 80%
del pedido "solicitar el ingreso de los jugadores".** Cualquier diseño
que reconstruya un formulario de plantilla desde cero en el módulo de
Equipos está tirando 14 tests de backend (`test_registro_lote.py`) a la
basura.

### Alternativas de arquitectura consideradas

#### Para A: ¿dónde vive la "plantilla del equipo"? (Decisión #1)

| Opción | Qué implica | Completeness | Riesgo |
|---|---|---|---|
| **A1. Plantilla derivada (recomendada)** | `EQUIPOS` no gana ninguna tabla nueva. La columna "Plantilla" de la grilla se calcula: perfiles distintos con membresía en cualquier inscripción de ese equipo. Al crear un equipo desde el catálogo global **no** se pide plantilla (no hay torneo); se pide al inscribirlo a un torneo, que es donde ya funciona | 8/10 — cubre la grilla y no rompe traspasos, dorsales ni exclusividad | Bajo. Cero migración de plantillas. **Contra: no cumple literalmente "inmediatamente después debe solicitar los jugadores"** cuando el equipo se crea desde `/torneo-admin/equipos` |
| **A2. Roster permanente nuevo** | Tabla `EQUIPO_MIEMBRO (Equipo_ID, Jugador_Perfil_ID, Estado)` — el equipo tiene socios estables; `JUGADOR_EQUIPO` sigue siendo "quién jugó este torneo" | 10/10 — cumple el pedido literal | **Alto.** Dos fuentes de verdad de "quién es del equipo". Cada traspaso, baja y alta pasa a tener que decidir si toca una tabla o las dos. `fn_validar_jugador_partido` y `fn_validar_exclusividad_torneo` no saben de esta tabla |
| **A3. `Inscripcion_Torneo_ID` nullable** | Permitir plantilla sin torneo reutilizando `JUGADOR_EQUIPO` | 6/10 | **Alto y sutil.** `uq_dorsal_por_roster_vigente` y los triggers indexan por `Inscripcion_Torneo_ID`; con NULL, dos jugadores comparten dorsal sin que nada lo impida. Rompe invariantes ya testeadas |

**Recomendación: A1** — P5 (explícito sobre clever) + P3 (pragmático).
A2 es la única que cumple el pedido al pie de la letra, pero introduce
exactamente el problema que `ediciones-catalogo-disciplinas-plan.md`
acaba de resolver (dos caminos para el mismo concepto). Con A1 el flujo
que el usuario describe sigue existiendo **completo** — solo que su
entrada natural es "Agregar Equipo" dentro de un torneo (donde ya está
implementado y encadena a Registro por Lote), no el catálogo global.

> **Si elegís A2**, se agregan a este plan: tabla nueva + FK + índice
> único parcial, endpoint `POST /equipos/{id}/miembros`, decisión de qué
> pasa cuando un miembro permanente es traspasado, y ~6 tests más.
> Estimado: +1 día humano / +40 min CC sobre el resto del plan.

#### Para "Categoría" (Decisión #2)

`grep -ri categoria` = 0 resultados en todo el repo. El concepto hay que
definirlo antes de poder mostrarlo en una columna.

| Opción | Qué es "Categoría" | Completeness | Costo |
|---|---|---|---|
| **B1. Categoría = Modalidad (recomendada)** | La columna muestra `Modalidad.nombre` ("Fútbol 11", "Tenis Singles"). El equipo gana `Modalidad_ID` además de `Disciplina_ID` | 7/10 — no es una categoría etaria, pero es el único eje de clasificación que el sistema ya tiene y ya valida | Cero catálogo nuevo. Reusa `fn_validar_torneo_modalidad` como modelo |
| **B2. Catálogo de categorías etarias/género** | Sub-13, Sub-15, Sub-18, Libre, Máster, Femenino, Mixto... | 10/10 si eso es lo que querés | Tabla `CATEGORIA` + seed + FK + UI de catálogo + reglas (¿un Sub-15 puede jugar un torneo Libre?). Es **un módulo propio**, no una columna |
| **B3. Texto libre en `EQUIPOS.Categoria`** | `VARCHAR(50)` sin catálogo | 3/10 | Barato hoy, "Sub 15"/"sub-15"/"SUB15" en 3 meses. Es el mismo error de `TORNEO.Disciplina` texto libre que este proyecto ya revirtió |

**Recomendación: B1** — P1 (completeness sobre lo que el sistema
realmente modela) + P5. B3 está descartada por precedente propio del
repo. B2 es correcta si "Categoría" significa lo que sospecho, pero es
un módulo aparte y **te lo pregunto en vez de adivinarlo**, porque la
diferencia es ~30 minutos vs ~2 días.

#### Para B: ¿hasta dónde llega el filtro estricto? (Decisión #3)

| Opción | Alcance | Completeness |
|---|---|---|
| **C1. Solo equipos nuevos** | `Disciplina_ID` NOT NULL en filas nuevas; las existentes quedan NULL y se ofrecen siempre | 4/10 — el filtro tiene un agujero permanente |
| **C2. Backfill + NOT NULL (recomendada)** | La migración infiere la disciplina de cada equipo existente desde sus inscripciones; los que no se puedan inferir se resuelven con una regla explícita antes de aplicar el NOT NULL | 10/10 | Requiere decidir qué hacer con ambiguos y huérfanos (ver EC-35/EC-36) |
| **C3. Validar sin columna** | Derivar la disciplina del equipo en runtime desde su primera inscripción | 5/10 — un equipo sin inscripciones no tiene disciplina, y el pedido dice que se elige **al crear** | Descartada: contradice el pedido literal |

**Recomendación: C2** — P1 + P2 (boil-lakes: el radio del cambio son las
filas de `EQUIPOS`, y son todas).

### Alcance

**Dentro de alcance:**

- `EQUIPOS.Disciplina_ID` + `Modalidad_ID` (NOT NULL tras backfill) — migración `database/13_*.sql`
- `GET /equipos?disciplina_id=&modalidad_id=&estado=` con filtros reales
- `POST /equipos` exige `disciplina_id` + `modalidad_id`; valida que la modalidad pertenezca a la disciplina
- Validación server-side en `POST /inscripciones`: `equipo.disciplina_id == torneo.disciplina_id`, si no → 400 con mensaje accionable
- `EquipoOut` gana `plantilla_total` (conteo agregado) para la grilla — un endpoint, no N+1 desde el cliente
- `EquiposAdminPage` reescrita: grilla con Nombre / Disciplina / Categoría(=Modalidad) / Plantilla / Estado + filtros, componentizada
- Formulario de creación con Disciplina → Modalidad dependiente, y encadenado a Registro por Lote cuando el equipo se crea desde dentro de un torneo
- `ModalAgregarInscripcion` filtra por disciplina del torneo **y por `estado === "Activo"`** (bug encontrado, ver Mejora #3)
- `TorneosAdmin.submitNuevaEdicion` navega a `/torneo-admin/torneos/{nuevaId}/equipos`
- `FiltroDisciplinasBar` — barra horizontal scrollable, chips de Disciplina + Modalidad, filtra el listado en vivo
- Las 4 mejoras de la sección "Mejoras propuestas" (todas dentro del blast radius)

**NOT en scope (deferido a `TODOS.md`):**

- Catálogo de categorías etarias/género (`CATEGORIA`) — solo si elegís B2, y ahí es su propio plan
- Tabla `EQUIPO_MIEMBRO` / roster permanente — solo si elegís A2
- Iconos SVG propios por disciplina (28 assets de diseño). El plan usa emoji + inicial como placeholder, con el punto de extensión ya cableado
- Paginación real con cursor en `/equipos` (el plan sube el techo y lo hace visible; el cursor es otro trabajo)
- Filtro por Estado del torneo (Activo/Finalizado) en la barra SofaScore — el pedido dice Disciplinas y Modalidades; un tercer eje es alcance nuevo
- Persistir el filtro elegido en la URL como query param compartible — nice-to-have, no pedido
- `UNIQUE(Nombre, Disciplina_ID)` en equipos (ver EC-43)

### Dream state

```
HOY                          ESTE PLAN                      IDEAL 12 MESES
─────────────────────────    ─────────────────────────      ────────────────────────
Equipo = (nombre, estado)    Equipo = (nombre,              Equipo = entidad con
Sin disciplina.                disciplina, modalidad,         historia: escudo, sede,
Sin categoría.                 estado) + plantilla            palmarés, roster
Sin plantilla propia.          derivada                       permanente, staff

Cualquier equipo se           Solo equipos de la misma      Sugerencias: "estos 4
inscribe a cualquier          disciplina, validado en        equipos de tu disciplina
torneo. Un equipo de          front Y en API                 nunca jugaron esta
Ajedrez puede entrar a                                       edición"
un torneo de Fútbol

Nueva edición → listado       Nueva edición → pestaña       Nueva edición → opción de
vacío                         Agregar Equipo de ESA          clonar el roster de la
                              edición                        edición anterior

Torneos = grid de tarjetas    Barra SofaScore filtra por    Barra + búsqueda + estado
sin filtro. Con 66 torneos    disciplina/modalidad en        + favoritos, con iconos
de mock data es inusable      vivo                           reales por disciplina
```

**Delta:** este plan cierra el hueco de integridad (un equipo de una
disciplina en un torneo de otra es hoy posible y silencioso) y hace
navegable un listado que con los 66 torneos de mock data del plan
anterior ya está roto. No cierra el hueco de "el equipo como entidad con
identidad propia" — eso es A2 y queda marcado para tu decisión.

### Selección de modo

**SELECTIVE EXPANSION.** Extiende el esquema y la UI de los tres planes
previos; no reemplaza nada de cero. La única pieza que se reescribe es
`EquiposAdmin.tsx` (27 líneas de configuración que ya no alcanzan).

---

## Fase 2 — Design Review (UX)

### A. Módulo de Gestión de Equipos — antes / después

**Hoy:**

```
Equipos                                        [+ Nuevo]
┌──────────────┬─────────┬──────────────────┐
│ Nombre       │ Estado  │ Acciones         │
├──────────────┼─────────┼──────────────────┤
│ Los Tigres   │ Activo  │ Editar · Baja    │
└──────────────┴─────────┴──────────────────┘

[+ Nuevo] → un solo campo: Nombre. Crear. Fin.
```

Nada dice de qué juega ese equipo ni quién lo integra.

**Propuesto:**

```
Equipos                                                          [+ Nuevo equipo]
┌─ Filtros ──────────────────────────────────────────────────────────────────┐
│ Disciplina: [Todas ▾]   Categoría: [Todas ▾]   Estado: [Activos ▾]  🔍[___]│
└────────────────────────────────────────────────────────────────────────────┘
┌──────────────┬─────────────┬──────────────┬───────────┬────────┬──────────┐
│ Nombre       │ Disciplina  │ Categoría    │ Plantilla │ Estado │ Acciones │
├──────────────┼─────────────┼──────────────┼───────────┼────────┼──────────┤
│ Los Tigres   │ ⚽ Fútbol   │ Fútbol 11    │ 14 jug.   │ Activo │ Ver·Edit │
│ Nadal/Alcaraz│ 🎾 Tenis    │ Tenis Dobles │  2 jug.   │ Activo │ Ver·Edit │
│ Sin Nombre   │ 🏀 Balonc.  │ 3x3          │  0 jug.   │ Activo │ Ver·Edit │
└──────────────┴─────────────┴──────────────┴───────────┴────────┴──────────┘
```

**"Plantilla" muestra el conteo, no la lista.** Un listado resumido
("Pérez, Gómez, +12") suena más informativo pero en una grilla de 14
nombres corta en el peor lugar posible y no es accionable. El conteo es
escaneable, y el detalle vive un click más adentro. Cuando la fila diga
`0 jug.`, el conteo es un link a "Agregar jugadores" — el vacío informa
Y ofrece la salida.

**Componentización (lo que pediste explícitamente para poder crecer):**
la grilla no se construye a mano ni se estira `SimpleResourceAdminPage`.
Se compone con lo que ya existe:

```
EquiposAdminPage
├── <FiltrosRecurso/>        ← nuevo, genérico (selects + búsqueda)
├── <ResourceTable/>         ← YA EXISTE, ya soporta `render` por columna
│     └── columnas: [nombre, disciplina, categoria, plantilla, estado]
│                    ▲ cada una es un objeto de config; agregar una
│                      métrica futura = una entrada más en el array
└── <FormularioEquipo/>      ← nuevo, reusa <ResourceForm/> con campos
                               dinámicos (mismo patrón que TorneosAdmin)
```

Agregar "Partidos jugados" o "Última actividad" después = una fila más en
el array de columnas + un campo más en `EquipoOut`. Eso es lo que
"escalable" significa acá, y `ResourceTable` ya lo permite vía `render` —
no hay que inventar nada.

### Estados de interacción — grilla de Equipos

| Estado | Qué se ve |
|---|---|
| Cargando | `Cargando...` (mismo vocabulario que `ResourceTable` ya usa) |
| Vacío, sin filtros | "No hay equipos creados todavía." + `[+ Nuevo equipo]` |
| Vacío, con filtros | **"Ningún equipo de Fútbol / Fútbol 11." + `[Limpiar filtros]`** — distinto del vacío real. Un empty-state que no distingue "no hay nada" de "tu filtro no matchea" manda al admin a crear un duplicado |
| Error | `apiErrorMessage(...)` en `.error-text`, igual que el resto del módulo |
| Equipo con 0 jugadores | Fila normal, `0 jug.` como link a Registro por Lote. **No es un error** — EC-22 del plan de torneos ya estableció que un equipo con 0 jugadores es válido |
| Truncado en 200 | Banner: "Mostrando los primeros 200. Filtrá para ver el resto." Ver Mejora #1 |

### B. Creación de equipo — el flujo de dos caminos

El pedido: "el formulario debe exigir la Disciplina. **Inmediatamente
después, debe solicitar el ingreso de los jugadores.**"

Con A1 (plantilla derivada) eso se cumple **cuando hay un torneo**, y hay
dos entradas distintas al flujo. El diseño las trata distinto a propósito.

**Camino 1 — desde un torneo** (`Ver Torneo → Equipos → + Agregar Equipo
→ Crear equipo nuevo`). Es el flujo del pedido, completo, y **ya está
construido**:

```
[Modal Agregar Equipo]
  Disciplina: Fútbol (heredada del torneo, texto plano, no editable)  ← nuevo
  Nombre del equipo: [__________]
  Plantilla inicial (obligatoria):
    ┌ Cédula ┬ Nombre ┬ Correo ┬ Dorsal ┐   ← ya existe
    └────────┴────────┴────────┴────────┘
  [Validar y crear] → crea equipo + inscripción → Registro por Lote
```

Lo único que cambia acá: la disciplina se muestra **heredada del torneo**,
como texto plano y no como `<select>` — mismo criterio que "Nueva edición"
ya usa para Disciplina/Modalidad, y por la misma razón: un select
deshabilitado sigue pareciendo un campo de formulario roto.

**Camino 2 — desde el catálogo global** (`/torneo-admin/equipos → +
Nuevo`). Acá **no hay torneo**, así que no hay dónde colgar una plantilla.
En vez de pedir jugadores que no se pueden guardar:

```
Nuevo equipo
  Nombre:     [__________]
  Disciplina: [Fútbol ▾]        ← obligatorio
  Categoría:  [Fútbol 11 ▾]     ← obligatorio, filtrado por disciplina
  [Crear]

  ┌──────────────────────────────────────────────────────────┐
  │ ℹ La plantilla se carga al inscribir el equipo a un      │
  │   torneo — los jugadores se registran por torneo.        │
  │   [Crear e inscribir a un torneo →]                      │
  └──────────────────────────────────────────────────────────┘
```

El botón secundario lleva a un selector de torneos **ya filtrado por la
disciplina elegida** y de ahí al mismo Registro por Lote. **El pedido se
cumple: el admin nunca queda con un equipo vacío sin saber cómo
llenarlo.** El paso intermedio (elegir torneo) es honesto sobre el modelo
de datos en vez de esconderlo.

> Si elegís **A2** (roster permanente), el Camino 2 pide la plantilla
> directo, sin torneo, y la nota informativa desaparece.

### C. Filtrado estricto — qué ve el admin cuando algo no matchea

El pedido dice "no deben aparecer en la lista de opciones". Correcto,
pero **el silencio total tiene un costo**: el admin que buscó "Tigres" y
no lo encuentra no sabe si escribió mal, si el equipo no existe, o si es
de otra disciplina.

```
[Agregar equipo — Liga Relámpago Edición 2 · ⚽ Fútbol]
  🔍 [Tigres______]

  (sin resultados)

  ℹ Ningún equipo de Fútbol coincide con "Tigres".
    2 equipos de otras disciplinas coinciden y no se pueden inscribir acá.
                                                    ▲
                       el conteo, no los nombres — no son opciones,
                       no se muestran como si lo fueran

  — o —
  [+ Crear equipo nuevo]
```

Esto respeta la regla al pie de la letra (los equipos de otra disciplina
**no aparecen** como opción, no se pueden clickear, no se pueden
inscribir) y a la vez le dice al admin por qué su búsqueda falló. Un
número, no una lista.

### D. Barra de navegación tipo SofaScore

**El problema de escala primero:** el catálogo tiene **28 disciplinas y
66 modalidades**. Una barra con 94 chips no es navegación, es un muro.

**Decisión de diseño: la barra muestra solo lo que tiene torneos.** Si
hay torneos de 4 disciplinas, la barra tiene 4 chips + "Todos". Crece
sola con el sistema y nunca ofrece un filtro que devuelve vacío.

**Dos niveles, no uno.** Modalidad es hija de Disciplina; ponerlas al
mismo nivel obliga a leer "Fútbol 11" y "Fútbol 5" como si fueran
hermanas de "Tenis". La segunda fila aparece solo al elegir una
disciplina con más de una modalidad presente:

```
┌────────────────────────────────────────────────────────────────────────┐
│ ⬤Todos   ⚽Fútbol   🎾Tenis   🏀Baloncesto   ♟Ajedrez   🏐Voleibol  →  │ ← scroll-x
└────────────────────────────────────────────────────────────────────────┘
    ↓ (al elegir Fútbol, y solo si tiene 2+ modalidades con torneos)
┌────────────────────────────────────────────────────────────────────────┐
│  Todas   Fútbol 11   Fútbol 7   Fútbol 5                               │
└────────────────────────────────────────────────────────────────────────┘

Torneos  (3 de 12)                                      [+ Torneo nuevo]
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ Liga Relámpago   │ │ Copa Ecotec 2026 │ │ Torneo Apertura  │
│ ⚽ Fútbol 11     │ │ ⚽ Fútbol 11     │ │ ⚽ Fútbol 7      │
│ 2 ediciones      │ │ 1 edición        │ │ 1 edición        │
│ [+Ed] [Ver →]    │ │ [+Ed] [Ver →]    │ │ [+Ed] [Ver →]    │
└──────────────────┘ └──────────────────┘ └──────────────────┘
```

**Detalles que hacen o rompen esta barra:**

| Aspecto | Decisión |
|---|---|
| Iconos | Mapa `disciplina.nombre → emoji`, con fallback a la inicial en un círculo de color. **Sin assets nuevos.** El mapa vive en un módulo aparte (`iconosDisciplina.ts`) para que cambiarlo por SVG después sea reemplazar un archivo, no tocar la barra |
| Chip activo | Fondo sólido + `aria-pressed="true"`. No solo color — el color por sí solo falla WCAG y falla en monocromo |
| Scroll horizontal | `overflow-x: auto` + `scroll-snap-type: x proximity`. En desktop, gradiente de "hay más" en el borde derecho. **Nunca** scroll horizontal en el `<body>` |
| Teclado | `<button>` reales en un contenedor con `role="tablist"`, flechas ←→ mueven el foco. Un `<div onClick>` deja el filtro inalcanzable sin mouse |
| Contador | "3 de 12" al lado del título — el admin siempre sabe que está viendo un subconjunto |
| Filtro vacío | Imposible por construcción (la barra solo ofrece lo que existe), pero el empty-state igual dice "Ningún torneo de X" + `[Ver todos]` por si el estado se desincroniza tras crear/borrar |
| Estado del filtro | `useState` en `TorneosAdminPage`. **No** en la URL en esta pasada (ver NOT en scope) |
| Sin torneos | La barra **no se renderiza**. Una barra de filtros sobre cero resultados es ruido |

### Litmus scorecard (resumen)

| Dimensión | Nota | Comentario |
|---|---|---|
| Jerarquía de información | 8/10 | La grilla lidera con Nombre+Disciplina, que es como el admin busca. Categoría antes que Plantilla porque clasifica, no mide |
| Estados especificados | 9/10 | Los 6 estados de la grilla y los 4 del filtro están escritos arriba, no dejados al implementador |
| Journey emocional | 7/10 | El punto de fricción real es el Camino 2 (crear equipo sin torneo). El plan lo mitiga con un link, no lo elimina — solo A2 lo elimina |
| Especificidad | 9/10 | Mockups de las 3 pantallas, no "una tabla con filtros" |
| Accesibilidad | 8/10 | Teclado y `aria-pressed` especificados. Contraste de los chips a verificar contra el CSS real durante implementación |
| Escalabilidad (lo pedido) | 9/10 | Columnas como config, iconos como módulo aparte, filtros como componente genérico |
| Consistencia con lo existente | 9/10 | Reusa `ResourceTable`, `ResourceForm`, `useResourceCrud`, `RegistroLoteAdminPage` y el vocabulario de loading/error/vacío ya establecido |

---

## Fase 3 — Eng Review (Arquitectura, Datos, Edge Cases, Tests)

### Arquitectura

```
                        ┌──────────────────┐
                        │    DISCIPLINA    │ (28, catálogo, solo lectura)
                        └────────┬─────────┘
                                 │ 1:N
                        ┌────────▼─────────┐
                        │    MODALIDAD     │ (66, tamano_equipo)
                        └────────┬─────────┘
                    ┌────────────┴────────────┐
                    │ N:1                     │ N:1  ◄── NUEVO
          ┌─────────▼────────┐      ┌─────────▼────────┐
          │      TORNEO      │      │     EQUIPOS      │
          │ disciplina_id ✓  │      │ disciplina_id ◄──┼── NUEVO (NOT NULL)
          │ modalidad_id  ✓  │      │ modalidad_id  ◄──┼── NUEVO (NOT NULL)
          │ torneo_grupo_id  │      │ nombre, estado   │
          └─────────┬────────┘      └─────────┬────────┘
                    │                         │
                    └───────────┬─────────────┘
                                │
                   ┌────────────▼──────────────┐
                   │   INSCRIPCIONES_TORNEO    │
                   │  ⚠ AQUÍ va la validación  │
                   │  torneo.disciplina_id ==  │
                   │  equipo.disciplina_id     │
                   └────────────┬──────────────┘
                                │ 1:N
                   ┌────────────▼──────────────┐
                   │      JUGADOR_EQUIPO       │  (la "plantilla" real,
                   │  inscripcion_torneo_id ✓  │   por torneo — sin cambios)
                   └───────────────────────────┘

Frontend:
  TorneosAdminPage ──── <FiltroDisciplinasBar/>  ◄── NUEVO
       │                      └── iconosDisciplina.ts  ◄── NUEVO
       └── "+ Nueva edición" ──► navigate(/torneos/{id}/equipos)  ◄── FIX

  EquiposAdminPage (reescrita) ──┬── <FiltrosRecurso/>     ◄── NUEVO
       │                         ├── <ResourceTable/>       (existe)
       │                         └── <FormularioEquipo/>    ◄── NUEVO
       └── useCatalogo()  ◄── NUEVO (hook compartido, ver Mejora #2)

  ModalAgregarInscripcion ── filtra por disciplinaId + estado  ◄── FIX
```

**Punto de acoplamiento clave:** la validación de disciplina vive en
`InscripcionTorneoService.create()`, **no** en el router ni en un trigger
de base. Razón: el service ya es el único punto por el que pasan los dos
caminos (equipo y jugador individual), ya tiene `torneo_repo` inyectado,
y `DomainRuleError` ya se traduce a 400 en `exceptions/handlers.py`. Un
trigger daría un mensaje de Postgres crudo; el router lo dejaría fuera de
cualquier futuro llamador interno.

### Modelo de datos — migración `database/13_migracion_equipos_disciplina.sql`

Sigue la convención de 07/08/09/12: autocontenido, idempotente, fuera de
la secuencia 01-06 (que se actualiza al estado final por separado).

```sql
-- PARTE A — columnas nullable primero
ALTER TABLE EQUIPOS ADD COLUMN IF NOT EXISTS Disciplina_ID INT REFERENCES DISCIPLINA(ID);
ALTER TABLE EQUIPOS ADD COLUMN IF NOT EXISTS Modalidad_ID  INT REFERENCES MODALIDAD(ID);

-- PARTE B — backfill desde las inscripciones existentes.
-- Un equipo con inscripciones en 2+ disciplinas distintas es exactamente
-- el caso que este plan viene a impedir; si ya existe, MIN() elige una y
-- la PARTE D lo reporta para revisión manual. No se falla la migración.
UPDATE EQUIPOS e SET
    Disciplina_ID = sub.disciplina_id,
    Modalidad_ID  = sub.modalidad_id
FROM (
    SELECT i.Equipo_ID,
           MIN(t.Disciplina_ID) AS disciplina_id,
           MIN(t.Modalidad_ID)  AS modalidad_id
    FROM INSCRIPCIONES_TORNEO i
    JOIN TORNEO t ON t.ID = i.Torneo_ID
    WHERE i.Equipo_ID IS NOT NULL
    GROUP BY i.Equipo_ID
) sub
WHERE e.ID = sub.Equipo_ID AND e.Disciplina_ID IS NULL;

-- PARTE C — huérfanos (equipos sin ninguna inscripción). Regla explícita:
-- NO se les inventa una disciplina. Se los desactiva y se los reporta —
-- son equipos que nunca jugaron nada. El admin los reactiva eligiendo
-- disciplina desde la UI nueva. (Ver EC-36 y Decisión #3.)
UPDATE EQUIPOS SET Estado = 'Inactivo'
WHERE Disciplina_ID IS NULL AND Estado = 'Activo';

-- PARTE D — reporte ANTES del NOT NULL: equipos ambiguos (2+ disciplinas
-- en sus inscripciones) + huérfanos desactivados. Si devuelve filas,
-- PARAR y resolverlas a mano — el ALTER de la PARTE E falla igual si
-- quedan NULLs, pero conviene enterarse acá y no ahí.

-- PARTE E — recién ahora el NOT NULL, y la coherencia disciplina/modalidad
ALTER TABLE EQUIPOS ALTER COLUMN Disciplina_ID SET NOT NULL;
ALTER TABLE EQUIPOS ALTER COLUMN Modalidad_ID  SET NOT NULL;
-- fn_validar_equipo_modalidad: espeja fn_validar_torneo_modalidad
-- (06_triggers.sql) — la modalidad tiene que pertenecer a la disciplina.
-- Se reusa el patrón exacto, no se inventa otro.

-- PARTE F — índices para los filtros nuevos
CREATE INDEX IF NOT EXISTS idx_equipos_disciplina ON EQUIPOS(Disciplina_ID);
CREATE INDEX IF NOT EXISTS idx_equipos_modalidad  ON EQUIPOS(Modalidad_ID);
```

**Orden que importa:** B antes que C (C solo toca lo que B no pudo
resolver), C antes que E (E falla con NULLs), D entre C y E (es el punto
de parada humano). Igual que `12_migracion_catalogo_disciplinas.sql`,
esto **se verifica contra una réplica con backup previo antes de tocar
`torneos_mvp`** — `SET NOT NULL` y el `UPDATE` de estado no son triviales
de deshacer a mano.

### Decisiones de Eng (continúa la numeración desde D-Eng-8)

| # | Decisión | Por qué |
|---|---|---|
| **D-Eng-9** | La validación de disciplina va en `InscripcionTorneoService.create()`, no en trigger ni router | Único punto por el que ya pasan los dos caminos; `DomainRuleError` → 400 ya cableado. Un trigger daría un mensaje crudo de Postgres |
| **D-Eng-10** | `EquipoOut` gana `plantilla_total` calculado con **un** `GROUP BY` en el repo, no N+1 desde el cliente | `TorneoGrupoService.listar_con_ediciones` ya aceptó un N+1 conscientemente; repetir el patrón acá lo haría 2, y esta lista es más larga |
| **D-Eng-11** | El backfill usa `MIN()` sobre disciplinas ambiguas + reporte; **no** falla la migración | Fallar dejaría la base a medias sin decir cuáles son los conflictivos. Un reporte deja decidir |
| **D-Eng-12** | Equipos huérfanos (sin inscripciones) se **desactivan**, no se borran ni se les inventa disciplina | Borrar es irreversible; inventar rompe el filtro estricto en silencio. Desactivar es reversible desde la UI nueva |
| **D-Eng-13** | El filtro de `ModalAgregarInscripcion` también excluye `estado !== "Activo"` | **Bug preexistente encontrado**: hoy se puede inscribir un equipo dado de baja. Está en el blast radius exacto del cambio (misma función, misma línea) |
| **D-Eng-14** | El conteo de "equipos de otras disciplinas que coinciden" se calcula en el cliente sobre lo ya cargado, sin fetch extra | Es texto informativo. Una llamada más para un número secundario no se paga |
| **D-Eng-15** | `POST /equipos` valida `modalidad.disciplina_id == disciplina_id` en el service **además** del trigger | El trigger es la red de seguridad para un `curl` directo; el service da el mensaje legible. Mismo doble-cinturón que `fn_validar_torneo_modalidad` |
| **D-Eng-16** | La barra SofaScore deriva sus chips de los torneos ya cargados (`GET /torneo-grupos`), sin endpoint nuevo | Cero llamadas extra, y garantiza por construcción que no hay chips que filtren a vacío |
| **D-Eng-17** | `POST /inscripciones` con `equipo_id` pasa a hacer `get_or_404` del torneo | Hoy ese camino no valida ni que el torneo exista — se descubre al agregar la validación de disciplina, y es el mismo `if` |

### Edge cases (continúa la numeración desde EC-32)

| # | Caso | Comportamiento esperado |
|---|---|---|
| **EC-33** | Se inscribe un equipo de Fútbol a un torneo de Tenis vía `curl` directo | 400 `DomainRuleError`: "El equipo pertenece a Fútbol; este torneo es de Tenis." Bloqueado en el service, no solo en la UI |
| **EC-34** | Se crea un equipo con `disciplina_id=1` (Fútbol) y `modalidad_id=44` (Tenis Singles) | 400 en el service (D-Eng-15) + trigger como red de seguridad |
| **EC-35** | Migración: un equipo tiene inscripciones en **dos disciplinas distintas** | `MIN()` elige una, la PARTE D lo lista. No falla la migración (D-Eng-11) |
| **EC-36** | Migración: un equipo existe pero **nunca se inscribió a nada** | Pasa a `Estado='Inactivo'`, se reporta. Reactivable desde la UI eligiendo disciplina (D-Eng-12) |
| **EC-37** | La disciplina de un equipo se desactiva en el catálogo | El equipo sigue existiendo y sigue inscrito. No se ofrece para equipos NUEVOS. Mismo criterio que EC-31 para torneos |
| **EC-38** | El admin cambia la disciplina de un equipo **que ya está inscrito** en torneos | **Bloqueado**: `PATCH /equipos/{id}` rechaza cambiar `disciplina_id` si existe al menos una inscripción. Permitirlo dejaría inscripciones que violan la regla que este plan introduce |
| **EC-39** | Equipo con 0 jugadores en la grilla | `0 jug.`, link a Registro por Lote. Válido (EC-22) |
| **EC-40** | Más de 200 equipos en el sistema | Banner de truncado + filtros server-side. Ver Mejora #1 |
| **EC-41** | Se crea la primera edición de un grupo y el redirect apunta a `/torneos/{id}/equipos` en una disciplina **Individual** (`tamano_equipo=1`) | La pestaña "equipos" ya se ramifica y muestra "Jugadores inscritos" con "+ Agregar Jugador". El redirect es correcto sin cambios; solo el texto del mensaje difiere |
| **EC-42** | La barra SofaScore está filtrada por Fútbol y el admin crea un torneo de Tenis | Tras el `invalidateQueries` el torneo nuevo no aparece (el filtro sigue en Fútbol). El contador cambia de "3 de 12" a "3 de 13" — señal visible. Se resetea el filtro a "Todos" al crear un torneo de otra disciplina |
| **EC-43** | Dos equipos con el mismo nombre en la misma disciplina | Permitido. **No** se agrega `UNIQUE(Nombre, Disciplina_ID)` — hoy tampoco hay UNIQUE sobre `Nombre`, y agregarlo rompería datos existentes sin que nadie lo haya pedido. Anotado en `TODOS.md` |
| **EC-44** | El equipo se inscribe a un torneo de la disciplina correcta pero **modalidad** distinta (Fútbol 11 vs Fútbol 5) | **Permitido.** El pedido dice "exactamente la misma Disciplina", no modalidad. Un equipo de Fútbol 11 jugando un torneo de Fútbol 5 es legítimo. Solo `Disciplina_ID` se valida |

> **EC-44 es una interpretación literal del pedido.** Si querés que la
> modalidad también sea estricta, es cambiar una comparación por un `and`
> — decilo y lo ajusto. Lo dejo permisivo porque es lo que dice el texto y
> porque restringir de más es más difícil de revertir en producción.

### Diagrama de pruebas

| # | Qué se prueba | Tipo | Archivo | Existe |
|---|---|---|---|---|
| T1 | `POST /equipos` sin `disciplina_id` → 422 | Backend API | `test_equipos.py` | ❌ |
| T2 | `POST /equipos` con modalidad de otra disciplina → 400 (**EC-34**) | Backend API | `test_equipos.py` | ❌ |
| T3 | `GET /equipos?disciplina_id=` filtra | Backend API | `test_equipos.py` | ❌ |
| T4 | `EquipoOut.plantilla_total` cuenta perfiles distintos entre torneos | Backend API | `test_equipos.py` | ❌ |
| T5 | `POST /inscripciones` equipo/torneo de distinta disciplina → 400 (**EC-33**) | Backend API | `test_inscripciones.py` | ❌ |
| T6 | `POST /inscripciones` misma disciplina, distinta modalidad → 201 (**EC-44**) | Backend API | `test_inscripciones.py` | ❌ |
| T7 | `PATCH /equipos/{id}` cambiando disciplina con inscripciones → 400 (**EC-38**) | Backend API | `test_equipos.py` | ❌ |
| T8 | Trigger `fn_validar_equipo_modalidad` rechaza el INSERT crudo | Backend DB | `test_db_triggers_equipos_jugadores.py` | ❌ |
| T9 | Backfill: equipo con 2 disciplinas → `MIN()` + reportado (**EC-35**) | Migración | manual sobre réplica | ❌ |
| T10 | Backfill: equipo huérfano → `Inactivo` (**EC-36**) | Migración | manual sobre réplica | ❌ |
| T11 | Grilla de equipos muestra Disciplina / Categoría / Plantilla | Frontend | `EquiposAdmin.test.tsx` | ⚠️ reescribir |
| T12 | Filtro por disciplina en la grilla + empty-state filtrado | Frontend | `EquiposAdmin.test.tsx` | ❌ |
| T13 | Modal "Agregar Equipo" oculta equipos de otra disciplina | Frontend | `ModalAgregarInscripcion.test.tsx` | ❌ |
| T14 | Modal oculta equipos `Inactivo` (**D-Eng-13**) | Frontend | `ModalAgregarInscripcion.test.tsx` | ❌ |
| T15 | Mensaje "N equipos de otras disciplinas coinciden" | Frontend | `ModalAgregarInscripcion.test.tsx` | ❌ |
| T16 | "Nueva edición" desde `TorneosAdmin` navega a `/torneos/{nuevoId}/equipos` | Frontend | `TorneosAdmin.test.tsx` | ❌ |
| T17 | "Nueva edición" desde `TorneoDashboard` **sigue** navegando bien (no-regresión) | Frontend | `TorneoDashboard.test.tsx` | ⚠️ ampliar |
| T18 | Barra SofaScore: click en chip filtra las tarjetas | Frontend | `TorneosAdmin.test.tsx` | ❌ |
| T19 | Barra: solo chips de disciplinas con torneos (**D-Eng-16**) | Frontend | `TorneosAdmin.test.tsx` | ❌ |
| T20 | Barra: segunda fila de modalidades solo con 2+ modalidades | Frontend | `TorneosAdmin.test.tsx` | ❌ |
| T21 | Barra: navegación por teclado (flechas + `aria-pressed`) | Frontend | `TorneosAdmin.test.tsx` | ❌ |
| T22 | Sin torneos → la barra no se renderiza | Frontend | `TorneosAdmin.test.tsx` | ❌ |
| T23 | Redirect a una edición Individual muestra "Jugadores inscritos" (**EC-41**) | Frontend | `EquiposDelTorneo.test.tsx` | ❌ |

**Base actual: 128 tests de backend, 89 de frontend.** Este plan agrega
~21 y reescribe 2. Ninguno de los 217 existentes debería romperse
**excepto** los de `test_equipos.py` (3) y `EquiposAdmin.test.tsx`, que
construyen equipos sin `disciplina_id` — hay que actualizar sus fixtures.
Es trabajo conocido, no un riesgo.

---

## Mejoras propuestas (lo que pediste que agregara por mi cuenta)

Cuatro cosas que encontré leyendo el código, **todas dentro del blast
radius** de este plan (mismos archivos, mismas funciones) y todas < 1 día
CC. No son ideas sueltas: cada una es un bug o una fricción que este plan
va a empeorar si no se toca.

### Mejora #1 — El techo silencioso de 200 filas

`useResourceCrud` manda `limit: 200` hardcodeado (`hooks/useResourceCrud.ts`)
y la API tiene `Query(default=100, le=200)`. **La fila 201 simplemente no
existe** para el frontend: sin banner, sin aviso, sin paginación.

Hoy no molesta porque hay pocos datos. Pero el plan anterior deja un
script de mock data que crea **66 torneos con 10 inscripciones cada uno**
— eso es ~660 equipos. La grilla de equipos que este plan construye
mostraría 200 de 660 y el admin no tendría forma de saberlo. Peor: la
búsqueda del modal "Agregar Equipo" filtra **en memoria** sobre esos 200,
así que buscar un equipo real puede devolver "no hay resultados".

**Propuesta (dentro de este plan):** los filtros server-side de `/equipos`
que ya estamos agregando resuelven el 90% del caso. Encima, un banner
cuando `data.length === limit`: *"Mostrando los primeros 200. Filtrá por
disciplina para ver el resto."* Es un `if` y una línea de texto, y
convierte un fallo silencioso en uno visible. La paginación con cursor
queda deferida a `TODOS.md`.
**Costo: human ~1h / CC ~10 min.**

### Mejora #2 — `useCatalogo()`: dejar de re-derivar los mismos mapas

Cuatro componentes construyen el mismo `Map` de disciplinas y modalidades
por su cuenta: `TorneosAdmin.tsx` (`disciplinaPorId`, `modalidadPorId`),
`TorneoDashboard.tsx`, `EquiposDelTorneo.tsx` y
`ModalAgregarInscripcion.tsx`. Cuatro `useResourceCrud` sobre los mismos
dos endpoints, cuatro `useMemo` con la misma lógica.

Este plan agrega dos consumidores más (`EquiposAdminPage` y
`FiltroDisciplinasBar`), o sea seis copias del mismo código.

**Propuesta:** un hook `useCatalogo()` que devuelve
`{ disciplinas, modalidades, disciplinaPorId, modalidadPorId, modalidadesDe(disciplinaId), cargando }`.
TanStack Query ya deduplica las llamadas HTTP por `queryKey`, así que el
beneficio no es de red — es que **la lógica de "cómo se cruza el catálogo"
existe en un solo lugar**. Cuando agregues iconos, o `estado=Activo` por
defecto, tocás un archivo en vez de seis. P4 (DRY), y es exactamente la
"componentización escalable" que pediste, aplicada a los datos en vez de
a la vista.
**Costo: human ~2h / CC ~15 min.**

### Mejora #3 — El equipo dado de baja que igual se puede inscribir

Ya está arriba como D-Eng-13, pero lo repito acá porque es **un bug real
en producción hoy**, no una mejora:

```js
// ModalAgregarInscripcion.tsx — ModalEquipo, equiposDisponibles
(equipos.listQuery.data ?? []).filter(
  (e) => !equiposYaInscritosIds.has(e.id) && (texto === "" || e.nombre.toLowerCase().includes(texto))
)
```

No hay chequeo de `e.estado`. Un equipo que el admin dio de baja desde
`/torneo-admin/equipos` **sigue apareciendo en el picker y se inscribe sin
error**. `useResourceCrud` tampoco manda `estado: "Activo"` en `listParams`.
Es una línea de fix, y estamos tocando esa función igual para el filtro
por disciplina.
**Costo: human ~15 min / CC ~2 min.**

### Mejora #4 — Cerrar el N+1 de `/torneo-grupos` ahora que esa lista pasa a ser la pantalla principal

`TorneoGrupoService.listar_con_ediciones()` hace **una consulta por
grupo** — y su propio docstring lo documenta como aceptable "al volumen
actual". Ese juicio era correcto cuando la pantalla era un grid pasivo de
3 tarjetas.

Con la barra SofaScore, esta pantalla se vuelve el punto de entrada
principal del módulo y se re-consulta en cada `invalidateQueries`. Con los
66 torneos del mock data son 67 consultas por carga.

**Propuesta:** reemplazar el loop por un solo `SELECT` de todas las
ediciones `WHERE torneo_grupo_id IN (...)`, agrupado en Python. Mismo
`response_model`, mismos tests, cero cambio de contrato. Es un cambio
aislado a un método, exactamente como el docstring anticipó ("migrar a un
solo JOIN es un cambio aislado").
**Costo: human ~1h / CC ~10 min.**

> **Las 4 juntas: ~4.5h humanas / ~40 min CC.** Las 4 están en archivos
> que este plan ya modifica. Si preferís dejar alguna afuera, la #3 es la
> única que yo no dejaría — es un bug de integridad de datos, el mismo
> tipo de agujero que el pedido #2 viene a cerrar.

---

## Decision Audit Trail

| # | Fase | Decisión | Clasificación | Principio | Racional | Rechazado |
|---|---|---|---|---|---|---|
| 1 | CEO | Plantilla del equipo **derivada** de sus inscripciones, sin tabla nueva (A1) | **Requiere tu confirmación** — no cumple el pedido literal en el camino "crear equipo sin torneo" | P5 (explícito) + P3 (pragmático) | Una tabla `EQUIPO_MIEMBRO` crea dos fuentes de verdad de "quién es del equipo" que traspasos/dorsales/exclusividad no saben conciliar | A2 (roster permanente), A3 (`Inscripcion_Torneo_ID` nullable — rompe `uq_dorsal_por_roster_vigente`) |
| 2 | CEO | **Categoría = Modalidad** del equipo (B1) | **Requiere tu confirmación** — "Categoría" no existe en el repo, hay que definir qué significa | P1 (completeness sobre lo que el sistema modela) + P5 | Es el único eje de clasificación que ya existe, ya está validado y ya tiene catálogo. B3 repite el error de `TORNEO.Disciplina` que este proyecto ya revirtió | B2 (catálogo etario — módulo propio, ~2 días), B3 (texto libre) |
| 3 | CEO | Backfill + `NOT NULL` sobre **todos** los equipos existentes, huérfanos a `Inactivo` (C2) | **Requiere tu confirmación** — desactiva filas existentes | P1 + P2 (boil-lakes) | C1 (solo equipos nuevos) deja un agujero permanente en el filtro estricto que el pedido #2 viene a cerrar | C1 (parcial), C3 (derivar en runtime — contradice "se elige al crear") |
| 4 | CEO | El módulo de Equipos **no** pide plantilla cuando el equipo se crea desde el catálogo global | Taste — deriva de #1 | P5 | Pedir jugadores que no se pueden guardar es peor que un link honesto a "inscribir a un torneo" | Formulario de 2 pasos que guarda en `localStorage` hasta que haya torneo (frágil, invisible) |
| 5 | Design | Columna "Plantilla" = conteo, no listado resumido | Mecánica | P5 | Un listado truncado a 3 de 14 nombres corta en el peor lugar y no es accionable | "Pérez, Gómez, +12" |
| 6 | Design | Barra SofaScore muestra **solo disciplinas con torneos**, no las 28 | Mecánica | P3 (pragmático) | 94 chips no son navegación. Además garantiza que ningún chip filtre a vacío | Las 28 siempre; un `<select>` en vez de barra (no es lo pedido) |
| 7 | Design | Dos niveles (Disciplina → Modalidad), segunda fila condicional | Taste | P1 | Modalidad es hija de Disciplina; aplanarlas hace leer "Fútbol 11" como hermana de "Tenis" | Un solo nivel con las 66 modalidades |
| 8 | Design | Iconos: emoji + fallback a inicial, en un módulo aparte | Mecánica | P3 | 28 SVGs son trabajo de diseño, no de este plan. El módulo aparte hace que cambiarlos sea reemplazar un archivo | Sin iconos (el pedido los menciona); SVGs custom ahora |
| 9 | Design | "N equipos de otras disciplinas coinciden" — el conteo, nunca los nombres | Taste | P1 + fidelidad al pedido | Respeta "no deben aparecer en la lista de opciones" y a la vez explica por qué la búsqueda falló | Silencio total; mostrarlos deshabilitados (siguen apareciendo) |
| 10 | Eng | Validación de disciplina en el **service**, no en trigger ni router (D-Eng-9) | Mecánica | P4 (DRY) | Único punto por el que ya pasan los dos caminos; `DomainRuleError` → 400 ya cableado | Trigger (mensaje crudo de Postgres), router (deja fuera llamadores internos) |
| 11 | Eng | Backfill ambiguo usa `MIN()` + reporte, no falla la migración (D-Eng-11) | Mecánica | P6 (bias to action) | Fallar deja la base a medias sin decir cuáles son los conflictivos | Abortar la migración |
| 12 | Eng | Equipos huérfanos → `Inactivo` (D-Eng-12) | Mecánica, dentro de #3 | P5 | Borrar es irreversible; inventar disciplina rompe el filtro en silencio | `DELETE`; asignar la disciplina más común del sistema |
| 13 | Eng | Modalidad **no** se valida al inscribir, solo disciplina (EC-44) | Taste | Fidelidad literal al pedido | El pedido dice "exactamente la misma Disciplina". Un equipo de Fútbol 11 en un torneo de Fútbol 5 es legítimo | Validar también modalidad (más difícil de revertir en prod) |
| 14 | Eng | `plantilla_total` con un `GROUP BY` en el repo, no N+1 (D-Eng-10) | Mecánica | P1 | Ya hay un N+1 aceptado en `/torneo-grupos`; sumar otro sobre una lista más larga no se paga | Contar en el cliente cruzando `/plantillas` |
| 15 | Eng | `PATCH /equipos` bloquea cambiar disciplina si hay inscripciones (EC-38) | Mecánica | P1 | Permitirlo dejaría inscripciones que violan la regla que este plan introduce | Permitir y arrastrar; permitir y cancelar las inscripciones (destructivo) |
| 16 | Eng | Las 4 mejoras propuestas entran en este plan, no en `TODOS.md` | Mecánica | P2 (boil-lakes: mismo blast radius, < 1 día CC) | Las 4 tocan archivos que este plan modifica igual; la #3 es un bug de integridad activo | Deferirlas (dejaría el bug de #3 vivo) |

---

## Decisiones que requieren tu confirmación

Tres decisiones cambian el modelo de datos o desactivan filas existentes.
No las auto-decidí porque las tres tienen una alternativa razonable con un
costo muy distinto.

**1. ¿Dónde vive la plantilla de un equipo?**
- **A1 (recomendada)** — Derivada de las inscripciones. Sin tabla nueva.
  El pedido "pedir la plantilla al crear" se cumple **dentro de un
  torneo**; desde el catálogo global se ofrece un link para inscribirlo
  primero. Cero migración de plantillas. **~0 días extra.**
- **A2** — Tabla `EQUIPO_MIEMBRO` nueva: el equipo tiene socios estables
  independientes del torneo. Cumple el pedido al pie de la letra en los
  dos caminos. **+1 día humano / +40 min CC**, y hay que decidir qué pasa
  con un miembro permanente cuando es traspasado.

**2. ¿Qué es "Categoría"?**
- **B1 (recomendada)** — Es la Modalidad del equipo ("Fútbol 11",
  "Tenis Dobles"). Sin catálogo nuevo. **~0 días extra.**
- **B2** — Categoría etaria/de género (Sub-15, Libre, Femenino). Es un
  módulo propio: tabla, seed, UI de catálogo y reglas de elegibilidad.
  **+2 días humanos**, plan aparte.
- (B3, texto libre, la descarté: es el mismo error de `TORNEO.Disciplina`
  que este proyecto ya revirtió.)

**3. ¿Qué pasa con los equipos que ya existen?**
- **C2 (recomendada)** — Backfill desde sus inscripciones + `NOT NULL`.
  Los que nunca se inscribieron a nada pasan a `Inactivo` y se reportan
  para que los reactives eligiendo disciplina. El filtro estricto queda
  sin agujeros.
- **C1** — Solo los equipos nuevos llevan disciplina; los viejos quedan
  sin ella y se ofrecen en todos los torneos. Más barato, pero deja
  abierto exactamente el hueco que el pedido #2 viene a cerrar.

**Además, dos preguntas chicas** (no bloquean nada, cualquier respuesta
me sirve):
- **EC-44**: ¿la modalidad también tiene que coincidir, o solo la
  disciplina? El plan asume solo disciplina, que es lo que dice el texto.
- **Mejoras propuestas**: ¿entran las 4, o querés dejar alguna afuera? La
  #3 la recomiendo sí o sí — es un bug de integridad activo.

---

## Tareas de implementación — TODAS COMPLETADAS

- [x] **DB** — `database/13_migracion_equipos_disciplina.sql`: `EQUIPOS.Disciplina_ID`/`Modalidad_ID` nullable → backfill desde `INSCRIPCIONES_TORNEO`+`TORNEO` → huérfanos a `Inactivo` → reporte de verificación → `SET NOT NULL` → `fn_validar_equipo_modalidad` (espeja `fn_validar_torneo_modalidad`) → índices. Actualizar `01_schema.sql`/`02_constraints.sql`/`06_triggers.sql` al estado final. **Backup + corrida contra réplica antes de `torneos_mvp`.**
- [x] **Backend — Equipos** — `Equipo` gana `disciplina_id`/`modalidad_id`; `EquipoCreate` los exige; `EquipoOut` suma `disciplina_id`, `modalidad_id`, `plantilla_total`; `EquipoService.create` valida coherencia disciplina↔modalidad (D-Eng-15); `EquipoService.update` bloquea el cambio de disciplina con inscripciones (EC-38); `GET /equipos` gana `disciplina_id`/`modalidad_id`; `EquipoRepository` calcula `plantilla_total` con un `GROUP BY` (D-Eng-10).
- [x] **Backend — Inscripciones** — `InscripcionTorneoService.create()` valida `equipo.disciplina_id == torneo.disciplina_id` en el camino de equipo, `DomainRuleError` con mensaje accionable (D-Eng-9, EC-33) + `get_or_404` del torneo (D-Eng-17: hoy ese camino no valida ni que exista).
- [x] **Backend — Mejora #4** — `TorneoGrupoService.listar_con_ediciones()`: un `SELECT ... WHERE torneo_grupo_id IN (...)` en vez del loop. Mismo `response_model`, mismos tests.
- [x] **Frontend — Equipos** — `EquiposAdminPage` reescrita (sale de `SimpleResourceAdminPage`): `<FiltrosRecurso/>` nuevo + `<ResourceTable/>` con columnas `render` + `<FormularioEquipo/>` con Disciplina→Modalidad dependiente. Empty-state filtrado distinto del vacío real. Banner de truncado a 200 (Mejora #1). Link "Crear e inscribir a un torneo".
- [x] **Frontend — Modal de inscripción** — `ModalAgregarInscripcion`/`ModalEquipo` recibe `disciplinaId` del contexto y filtra por disciplina **y por `estado === "Activo"`** (D-Eng-13, Mejora #3). Mensaje con el conteo de coincidencias en otras disciplinas (D-Eng-14). Disciplina heredada como texto plano en "Crear equipo nuevo".
- [x] **Frontend — Redirect** — `TorneosAdmin.submitNuevaEdicion`: separar el `onSuccess` compartido (hoy `crearTorneo` sirve a "crear grupo" y a "nueva edición" con el mismo handler) y navegar a `/torneo-admin/torneos/{data.id}/equipos`. Verificar que `TorneoDashboard.crearEdicion` sigue funcionando (T17).
- [x] **Frontend — Barra SofaScore** — `<FiltroDisciplinasBar/>` nuevo: chips derivados de los torneos cargados (D-Eng-16), scroll-x con snap, `role="tablist"` + flechas, `aria-pressed`, segunda fila condicional de modalidades, contador "N de M", reset al crear un torneo de otra disciplina (EC-42). `iconosDisciplina.ts` como módulo aparte.
- [x] **Frontend — Mejora #2** — hook `useCatalogo()`; migrar los 4 consumidores actuales + los 2 nuevos.
- [x] **Tests** — los 23 de la tabla "Diagrama de pruebas", priorizando T5 (validación de disciplina, el corazón del pedido #2), T9/T10 (backfill, no reversible a mano) y T14 (el bug de equipos inactivos). Actualizar fixtures de `test_equipos.py` (3 tests) y `EquiposAdmin.test.tsx`.
- [x] **Regenerar** `frontend/src/api/schema.d.ts` (`npm run gen:api`) tras los cambios de schema del backend.

---

## GSTACK REVIEW REPORT

- **Modo**: SELECTIVE EXPANSION (extiende el esquema y la UI de los tres
  planes previos; solo `EquiposAdmin.tsx` se reescribe).
- **Fases corridas**: CEO ✅, Design ✅ (scope UI detectado: grilla de
  equipos, formulario de creación, modal de inscripción, barra de
  navegación), Eng ✅, DX — omitida (sin superficie de API/CLI para
  terceros, módulo interno).
- **Voces**: `[subagent-only]` en las 3 fases — Codex no disponible en
  esta máquina (binario no encontrado en PATH), mismo estado que los tres
  planes anteriores de este repo. El análisis se hizo directo sobre el
  código leído (models, services, routes, componentes y SQL citados por
  archivo), no despachando un subagente redundante — mismo criterio
  pragmático (P3) documentado en los planes previos.
- **Gates**: premisas presentadas en Fase 1, con **2 de 9 marcadas como
  falsas** (P2: un equipo no puede tener plantilla propia hoy; P3:
  "Categoría" no existe en el repo) y 3 más como parcialmente falsas
  (P1, P4, P7). Ese es el hallazgo central de este review.
- **Decisiones registradas**: 16 (ver Decision Audit Trail). **3 requieren
  tu confirmación** (#1 plantilla, #2 categoría, #3 backfill) — no se
  auto-decidieron porque cambian el modelo de datos o desactivan filas
  existentes. 13 auto-decididas.
- **Entregables cubiertos** (los 4 pedidos explícitos):
  1. Módulo de Gestión de Equipos con Disciplina obligatoria + plantilla +
     grilla componentizada → "Fase 2, A y B" + Decisiones #1/#2
  2. Filtrado estricto por disciplina, front **y** API → "Fase 2, C" +
     D-Eng-9 + EC-33/EC-44 + T5/T6/T13
  3. Redirección tras Nueva Edición → tarea de Frontend + T16/T17.
     **Ojo**: uno de los dos caminos ya lo hacía bien (P7)
  4. Barra de navegación tipo SofaScore → "Fase 2, D" + D-Eng-16 + T18-T22
- **Extra propuesto por mí** (lo que pediste): 4 mejoras en la sección
  "Mejoras propuestas" — techo silencioso de 200 filas, hook
  `useCatalogo()`, **bug de equipos inactivos inscribibles**, y N+1 de
  `/torneo-grupos`. Las 4 dentro del blast radius, ~40 min CC en total.
- **No implementado en este momento**: cero código, cero cambios de
  esquema — solo este documento, como se pidió explícitamente.
- **Siguiente paso sugerido**: responder las 3 decisiones de confirmación
  (y las 2 preguntas chicas). Con eso el plan queda cerrado y se puede ir
  directo a implementación, empezando por la migración `13_*.sql` contra
  una réplica — es el ítem de mayor riesgo y bloquea a todo el resto.

**STATUS: DONE_WITH_CONCERNS** — el plan está completo, pero 2 de las 9
premisas del pedido son falsas contra el código real (`P2`: la plantilla
no existe a nivel de equipo; `P3`: "Categoría" no existe en el repo).
Ninguna de las dos se puede resolver auto-decidiendo: dependen de qué
querés que signifiquen. Están arriba como Decisión #1 y #2.

---

## Registro de implementación

Las 3 decisiones se confirmaron con la opción recomendada (A1 / B1 / C2),
EC-44 quedó literal (solo Disciplina) y entraron las 4 mejoras.

**Lo que cambió respecto de lo planificado, y por qué:**

1. **El backfill de la PARTE B usa `DISTINCT ON`, no dos `MIN()`.** El plan
   proponía `MIN(Disciplina_ID)` y `MIN(Modalidad_ID)` por separado. Dos
   `MIN()` independientes pueden combinar la disciplina de un torneo con la
   modalidad de OTRO y producir un par incoherente — que es exactamente lo
   que rechaza el trigger de la PARTE E, dejando la migración trabada por
   un dato que ella misma se inventó. `DISTINCT ON` toma los dos valores de
   la misma fila.

2. **El conteo "N equipos de otras disciplinas coinciden" pide los datos, no
   los deriva de la lista ya cargada** (deja de cumplir D-Eng-14 al pie de
   la letra). El plan asumía que el modal tenía en memoria todos los
   equipos y filtraba por disciplina del lado del cliente. Pero la Mejora
   #1 dice —con razón— que filtrar en memoria sobre las primeras 200 filas
   es el bug, no la solución: el filtro por disciplina se movió al
   servidor, y con eso la lista cargada ya no contiene las otras
   disciplinas. La consulta extra está `enabled` solo cuando la búsqueda no
   encontró nada, que es el único momento en que ese número significa algo.

3. **Fixtures de test actualizados: 9, no 3.** El plan estimaba 3 tests de
   `test_equipos.py`. `POST /equipos` sin `disciplina_id` ahora es 422, así
   que también hubo que tocar `test_inscripciones.py`, `test_partidos.py`,
   `test_registro_lote.py` (×2) y `test_torneo_grupos.py` (×3).

4. **`TorneoDashboard.crearEdicion` navega explícito a `/equipos`.** El plan
   marcaba ese camino como "ya funciona" (P7) porque el `<Route index>`
   redirige a `equipos`. Funciona, pero dependía de esa redirección: ahora
   los dos caminos a "Nueva edición" apuntan al mismo destino escrito, y
   T17 verifica que aterriza en la pestaña, no solo en el dashboard.

5. **El mensaje de la PARTE D no afirma en qué estado quedaron los
   huérfanos.** Al correr la migración end-to-end salió que, envuelta en una
   sola transacción, el `RAISE EXCEPTION` revierte también la desactivación
   de la PARTE C — el mensaje decía "ya quedaron en Estado=Inactivo" y eso
   podía ser falso. Se corrigió el texto y se documentó la diferencia entre
   `psql -f` y `psql -1 -f` en el comentario de la PARTE C.

**Cobertura de las pruebas del "Diagrama de pruebas":** T1-T8 y T9/T10
(migración, vía `backend/scripts/verificar_migracion_13.py`), T11-T22
implementadas. **T23 (EC-41)** no se duplicó: el test que ya existía en
`EquiposDelTorneo.test.tsx` para la vista Individual verifica exactamente
lo que T23 pide (que la pestaña destino del redirect muestre "Jugadores
inscritos" y "+ Agregar Jugador"); se le agregó la referencia al EC en vez
de escribir un test gemelo.

**Cierre — arreglos extra sobre deuda preexistente.** Al pasar el
proyecto por `tsc`/`oxlint`/`build` completos aparecieron dos cosas que no
eran de este plan pero dejaban la app peor de lo necesario, y se
arreglaron:

- **Los 3 GET de `/jugadores` no tenían schema de respuesta en OpenAPI.**
  `response_model=None` es deliberado ahí (la proyección con o sin PII se
  elige en runtime según haya usuario autenticado — security review de
  `equipos-jugadores-plan.md`), pero también borra la forma de la
  respuesta del OpenAPI: quedaba `unknown`, y de ahí salían los 4 errores
  de `tsc` en `PartidoEnVivo.tsx` (`Property 'map' does not exist on type
  '{}'`). Se declaró la unión real vía `responses={200: {...}}` — el
  runtime no cambió (140 tests siguen pasando) y el contrato volvió a
  estar tipado para todos los consumidores. **`tsc` pasó de 4 errores a 0
  por primera vez.**
- **`AuthContext.tsx` exportaba un componente y no-componentes juntos**,
  lo que rompía Fast Refresh: editar el provider forzaba un reload
  completo de la página y con él la sesión de desarrollo. `useAuth` y los
  tipos se movieron a `useAuth.ts` / `authContextValue.ts`. **`oxlint`
  quedó sin un solo warning.**

**Estado final verificado:** 140 tests backend + 113 frontend, `tsc` sin
errores, `oxlint` sin warnings, `npm run build` OK, y los endpoints
probados en vivo contra `torneos_mvp` ya migrada (EC-33, EC-34, EC-38,
EC-44, T1 y D-Eng-17 responden lo esperado).
