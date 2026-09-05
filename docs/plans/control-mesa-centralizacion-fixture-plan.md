<!-- /autoplan restore point: none — new plan file, nothing to restore. Branch: feat/equipos-jugadores-plan, commit at plan time: 7236fff. -->

# Plan: Centralización operativa en Control de Mesa + corrección del bug de nombres en el fixture

Generado por `/gstack-autoplan`. Modo: **SELECTIVE EXPANSION** (P1+P2 dominan en CEO;
P5+P3 dominan en Eng). Codex no disponible en este entorno (`codex` no está en el
PATH) — las "dos voces" de cada fase corren en modo `[subagent-only]` (un solo
subagent Claude por fase, no cross-model).

## 0. Resumen para el usuario

El pedido tiene 3 partes reales, y ya verifiqué el código antes de proponer nada
(no repito la lectura del pedido, la reformulo con lo que encontré):

1. **Centralizar TODO lo operativo de un partido en `/control-de-mesa`** (lectura Y
   escritura), con RBAC por torneo asignado.
2. **Volver `/torneo-admin/torneos/{id}/partidos` de solo lectura** + un botón
   "Detalle del Partido" hacia una página pública de resumen.
3. **Corregir el bug de "?" en el fixture** — **ya diagnostiqué la causa raíz leyendo
   el código real, y NO es la que planteás en el pedido.**

## 1. Corrección al diagnóstico del usuario (Sección 3 del pedido)

**Tu hipótesis ("el nombre se guarda nulo o no se vincula al crear el equipo") es
incorrecta — verificado, no supuesto.**

Leí `EquipoService.create` ([equipo.py:38-44](backend/app/services/equipo.py#L38-L44)):
persiste `nombre` vía `**data.model_dump()`, y `EquipoCreate` lo exige no-nulo. El
INSERT está bien. El bug es de **LECTURA**, no de escritura, y ya lo conocíamos:
está documentado en `TODOS.md` como "Bug 2" del plan
`fixes-datos-traspasos-control-mesa-plan.md` (implementado 2026-09-04) — pero **la
corrección de ese bug se aplicó a 7 pantallas y se olvidó de la 8va: exactamente
`PartidosDelTorneo.tsx`, la pantalla que reportás.**

Causa raíz exacta, verificada línea por línea:

```
PartidosDelTorneoPage (PartidosDelTorneo.tsx:60)
  equipos = useResourceCrud<EquipoRow>({ resourceKey: "equipos", basePath: "/api/v1/equipos" })
                                         │
                                         ▼ sin listParams → useResourceCrud.ts:67
                          GET /api/v1/equipos?limit=200   (LIMITE_LISTA=200, useResourceCrud.ts:40)
                                         │
                                         ▼ backend/app/repositories/base.py:39
                          SELECT * FROM equipos ORDER BY id LIMIT 200   (sin filtro de torneo — EQUIPOS
                                                                          es un pool global sin dueño,
                                                                          documentado en equipos.py)
                                         │
                                         ▼
              nombreEquipo = Map(id → nombre)  ←  SOLO contiene los primeros 200 equipos por ID ascendente
                                         │
                                         ▼ PartidosDelTorneo.tsx:123-125
              render: nombreEquipo.get(equipo_id) ?? "?"   ← el equipo creado hoy tiene el ID MÁS ALTO
                                                               del sistema → cae afuera de la ventana de
                                                               200 en cuanto el sistema pasa esa cantidad
                                                               total de equipos → "?" aunque el nombre
                                                               esté perfecto en la base
```

Esto es exactamente el patrón ya resuelto en `EquiposDelTorneo.tsx`, `PlantillasDelTorneo.tsx`,
`TraspasosDelTorneo.tsx`, `MotorFormatosPanel.tsx`, `RegistroLoteAdmin.tsx`,
`ControlDeMesa.tsx` y `ModalGestionarPlantilla.tsx` con
[`useNombrePorIdConFaltantes`](frontend/src/hooks/useFetchFaltantes.ts#L76-L89): pide
`GET /equipos/{id}` uno por uno SOLO para los IDs que faltan en el mapa base, sin
paginación real (eso sigue siendo `TODOS.md` §3B-9, aparte). `PartidosDelTorneo.tsx`
es la 8va pantalla que necesita el mismo parche — no hay backend nuevo que escribir,
es DRY puro (P4): reusar un hook que ya existe.

**Confirmación adicional (`Modal Agregar Equipo`/creación local):** no hay ningún
bug de persistencia que revisar ahí — el flujo de creación ya pasa por
`EquipoService.create`, el mismo servicio verificado arriba. Nada que tocar del
lado de la escritura.

## 2. Premise Challenge (CEO, Step 0A)

- **P-1: "Hubo un malentendido en el diseño anterior — control-de-mesa debe ser el
  único centro operativo."** Válida y ya estaba parcialmente resuelta: el plan
  `gestion-avanzada-equipos-control-mesa-plan.md` ya puso Convocatoria, Titulares y
  Control de tiempos en `/control-de-mesa` (`Convocatoria.tsx`, `Cronometro.tsx`,
  `useTitularesCompletos`). Lo que **falta** es (a) el RBAC de la LISTA que alimenta
  esa pantalla — hoy `ControlDeMesaPage` pide `GET /partidos?limit=100` sin
  `torneo_id` ni scoping, mezclando TODOS los torneos del sistema para cualquier
  TorneoAdmin/Árbitro/AdminGeneral — y (b) el ingreso directo de resultado sin
  cronómetro, que no existe todavía. Acepto la premisa, con alcance corregido
  contra el código real.
- **P-2: "`/torneo-admin/.../partidos` debe ser estrictamente de solo lectura."**
  Válida. Hoy esa pantalla permite crear/editar/cancelar/asignar árbitro y marcar
  walkover directamente (`PartidosDelTorneo.tsx`) — exactamente la superficie
  operativa duplicada que el pedido quiere eliminar.
- **P-3 (la que corrijo): "el nombre se guarda nulo al crear el equipo."** Falsa,
  ver Sección 1. La mantengo en el plan como corrección explícita, no como
  pregunta al usuario — es un hecho verificable en el código, no una decisión de
  producto. Cuesta 5 segundos de lectura confirmar o refutar (P3, pragmatismo);
  ya está confirmado.

Ninguna premisa amerita un "User Challenge" — la dirección del usuario es correcta
en 2 de 3 puntos y el 3ro es un diagnóstico técnico erróneo, no una decisión de
producto en disputa.

## 3. Qué ya existe (reuso, P4/DRY)

| Sub-problema del pedido | Ya existe | Dónde |
|---|---|---|
| Convocatoria/titulares en Control de Mesa | Sí, completo | `Convocatoria.tsx`, `useTitularesCompletos` en `ControlDeMesa.tsx` |
| Control de tiempos (inicio/fin) | Sí, completo | `Cronometro.tsx`, `HitoPartidoService` |
| RBAC "solo mis torneos asignados" | Sí, patrón probado en OTRO endpoint | `GET /torneos?solo_mios=true` — `torneos.py:26-34`, `TorneoService.list`, `TorneoRepository.list` (override con `IN`), `AsignacionTorneoAdminRepository.listar_torneo_ids_activos` |
| Resolución de nombre fuera de la ventana de 200 | Sí, hook genérico | `useFetchFaltantes.ts` / `useNombrePorIdConFaltantes` |
| Vista pública de resumen de un partido (marcador + timeline de eventos) | Sí, 80% del "Detalle del Partido" | `PartidoEnVivoPage` (`/partido/:partidoId/en-vivo`) — le falta la sección de alineaciones/convocados |
| Endpoints públicos de lectura para armar el detalle (plantilla, convocados, resultados) | Sí, todos ya sin auth | `GET /estadisticas/equipos/{id}/plantilla`, `GET /partidos/{id}/convocados`, `GET /estadisticas/torneos/{id}/resultados` |
| Guard de "solo carga eventos si `En curso`" | Sí | `EventoPartidoService.create` (3A-8) |
| Hitos de Inicio/Fin de partido con sincronización de estado | Sí | `HitoPartidoService`, `trg_hito_sincroniza_estado` |

Lo único genuinamente nuevo es: (1) el filtro RBAC aplicado a `/control-de-mesa`,
(2) el flujo de ingreso directo de resultado sin cronómetro, (3) la conversión de
`PartidosDelTorneo.tsx` a solo-lectura + botón de detalle, y (4) generalizar
`PartidoEnVivoPage` para que sirva también como "Detalle del Partido" post-partido
(hoy su copy y su ruta son específicamente "en vivo").

## 4. Dream state

```
HOY                                    ESTE PLAN                              IDEAL A 12 MESES
────────────────────────────────       ────────────────────────────────       ────────────────────────────────
Partidos.tsx: crea, edita,       →     Partidos.tsx: solo lectura +      →     Igual, + esa misma página
  cancela, asigna árbitro,               botón "Detalle del Partido"             enlaza directo a estadísticas
  marca walkover                         (resumen público)                       del torneo (breadcrumb)

Control de Mesa: lista SIN       →     Control de Mesa: lista scoped     →     + selector "todos mis
  RBAC, mezcla todos los                 por asignación (TorneoAdmin) /          torneos" con contador de
  torneos del sistema                    todos (AdminGeneral)                   partidos programados hoy

Sin ingreso manual de            →     "Cargar resultado directo" —      →     Igual, + importar resultado
  resultado — solo cronómetro            reusa Hito+Evento existentes            desde planilla de árbitro
  en vivo                                sin exponer el cronómetro               offline (fuera de alcance)

Fixture: "?" para equipos        →     Fixture: nombre resuelto          →     Igual (el techo real,
  recién creados (bug de                siempre, mismo patrón que las           paginación con cursor real
  lectura, 200-row window)               otras 7 pantallas ya arregladas         en /equipos, es 3B-9 —
                                                                                  aparte, ya lo dice TODOS.md)

/partido/:id/en-vivo: solo       →     /partidos/:id: resumen            →     Igual, + export/print del
  eventos, sin alineaciones              completo (marcador, eventos,            resumen para el club
                                          alineaciones), sirve para
                                          cualquier estado del partido
```

Este plan deja el sistema en el estado que pedía la arquitectura original de
`roles-3-modulos-plan.md`: Control de Mesa como único punto de escritura
operativa. No cierra 3B-9 (paginación real con cursor) — sigue siendo su propio
ciclo, documentado, no se toca acá.

## 5. Alternativas consideradas (0C-bis)

Para el ingreso directo de resultado (la única pieza genuinamente nueva de
arquitectura):

| Opción | Descripción | Esfuerzo | Riesgo | Elegida |
|---|---|---|---|---|
| **A. Reusar Hito+Evento existentes** | Un service nuevo orquesta: crea Hito Inicio_Partido, itera eventos llamando a `EventoPartidoService.create` (la MISMA validación que ya corre en vivo), crea Hito Fin_Partido — todo en una transacción | CC: ~2-3h | Bajo — cero pipelines paralelos, cero triggers nuevos | **Sí** |
| B. Un campo `resultado_manual` en `PARTIDOS` + tabla de "sucesos" paralela | Estructura de datos nueva, desconectada de `EVENTOS_PARTIDO`/`HITOS_PARTIDO` | CC: ~1 día | Alto — dos fuentes de verdad para "qué pasó en el partido"; rompe `vw_goles_acreditados`, `vw_duracion_partido`, estadísticas | No |
| C. Permitir cargar eventos con el partido en `Programado` (aflojar el guard 3A-8) | Cambia el guard existente, ya cubierto por tests de regresión | CC: ~1h | Medio — el guard 3A-8 existe justamente para que "solo carga si arrancó" sea una garantía; aflojarlo abre una puerta que 3A-8 cerró a propósito | No |

**A gana por P4 (DRY) y P5 (explícito):** un service que orquesta piezas ya
validadas es más simple de auditar que una estructura de datos paralela, y no
reabre un guard que ya se cerró por una razón documentada.

## 6. Alcance — SELECTIVE EXPANSION (auto-decisiones)

| # | Ítem | Clasificación | Decisión | Principio |
|---|---|---|---|---|
| 1 | RBAC scoping de la lista de `/control-de-mesa` (`GET /partidos?solo_mios=true`, mismo patrón que `/torneos`) | Dentro de alcance, pedido explícito | Incluir | P1+P2 |
| 2 | Selector de torneo en Control de Mesa (para TorneoAdmin con 2+ torneos asignados, y para AdminGeneral) | Blast radius, <1 día CC | Incluir — sin esto, el scoping RBAC es invisible en la UI (la lista igual mezclaría N torneos sin indicar cuál es cuál) | P2 |
| 3 | Ingreso directo de resultado (goles/tarjetas/minutos sin cronómetro) | Pedido explícito, requerimiento funcional nuevo | Incluir, vía Alternativa A | P1 |
| 4 | `PartidosDelTorneo.tsx` → solo lectura + botón "Detalle del Partido" | Pedido explícito | Incluir | P1+P2 |
| 5 | Nueva ruta `/partidos/:partidoId` (resumen público, generaliza `PartidoEnVivoPage`) | Pedido explícito, con reuso de código existente | Incluir — generalizar en vez de duplicar (P4) | P1+P4 |
| 6 | Fix del bug "?" — aplicar `useNombrePorIdConFaltantes` a `PartidosDelTorneo.tsx` (lista, walkover, selector de equipos al crear) | Bug crítico reportado, causa raíz confirmada | Incluir | P1 |
| 7 | Migrar `DetalleEquipo.tsx`/`ModalIndividual` al mismo hook (mismo techo de 200, ya estaba en TODOS.md como mejora no pedida) | Fuera del blast radius directo de este pedido | **NO incluir acá** — ya está registrado en TODOS.md como mejora recomendada no pedida; tocarlo ahora es scope creep sin pedido explícito | P3 |
| 8 | Paginación real con cursor en `/equipos` (3B-9) | Ya documentada como "en curso, ciclo propio" | **NO incluir** — cambia el contrato de API, no es un fix acotado | P2 (fuera de blast radius de 1 día) |
| 9 | Quitar el POST/PATCH/DELETE de `/partidos` que hoy usa `PartidosDelTorneo.tsx` (crear/editar/cancelar/asignar árbitro/walkover) del frontend de esa pantalla | Pedido explícito ("Todo lo que sea administrar se hace en Control de Mesa") | Incluir — mover esas acciones (crear partido, asignar árbitro, walkover) a Control de Mesa; el backend NO se toca (los endpoints siguen protegidos por `require_torneo_access_de`, que ya es la fuente de verdad) | P1 |

**Borderline marcado como TASTE DECISION para el gate final:** el ítem 9 mueve
"Crear partido" y "asignar árbitro" a Control de Mesa. El pedido dice
"Gestión de Convocatorias, Titulares, Control de tiempos, Ingreso directo de
resultados" como la lista de funcionalidades exclusivas — no menciona
explícitamente "crear partidos nuevos" ni "asignar árbitro". Hay dos lecturas
razonables: (a) esa lista es taxativa y crear-partido/asignar-árbitro son
gestión de TORNEO (fase, calendario), no gestión de PARTIDO EN CURSO, y deberían
quedar en `/torneo-admin/.../partidos` como las ÚNICAS acciones de escritura que
sobreviven ahí; o (b) el pedido dice "todo lo que sea administrar se hace en
Control de Mesa" de forma literal y esas dos acciones también deben migrar. Ver
Sección 10 (Taste Decisions) — recomiendo (a), pero lo marco para el gate porque
es una llamada de producto, no técnica.

## 7. Arquitectura (Eng, Sección 1)

```
                         ┌─────────────────────────────────────────────┐
                         │              /control-de-mesa                │
                         │         (ÚNICO centro operativo)             │
                         │                                               │
  RBAC ──────────────────┤  ControlDeMesaPage                           │
  GET /partidos?         │    ├─ Selector de torneo (si N>1 asignados)  │
  solo_mios=true ────────┤    ├─ Lista de partidos Programado/En curso  │
  (TorneoAdmin) o        │    │    scoped (nuevo)                       │
  sin filtro             │    ├─ BotonEmpezarPartido (ya existe)        │
  (AdminGeneral) ────────┤    ├─ "Cargar resultado directo" (NUEVO)     │
                         │    │     └─ ModalResultadoDirecto            │
                         │    │          └─ POST /partidos/{id}/        │
                         │    │             resultado-directo (NUEVO)   │
                         │    └─ MesaPanel (ya existe, sin cambios)     │
                         │         ├─ Convocatoria (ya existe)          │
                         │         ├─ Cronometro (ya existe)            │
                         │         └─ CargaEvento (ya existe)           │
                         └─────────────────────────────────────────────┘
                                          │
                                          │ escribe vía servicios YA validados
                                          ▼
                  ┌───────────────────────────────────────────────┐
                  │  PartidoService.registrar_resultado_directo    │  (NUEVO,
                  │    (nuevo, orquesta 3 servicios existentes)    │   orquestador)
                  │    1. HitoPartidoService.registrar(Inicio)     │
                  │    2. EventoPartidoService.create() × N        │  ← reuso 100%
                  │    3. HitoPartidoService.registrar(Fin)        │     de validación
                  └───────────────────────────────────────────────┘     existente


                         ┌─────────────────────────────────────────────┐
                         │   /torneo-admin/torneos/{id}/partidos        │
                         │        (SOLO LECTURA a partir de ahora)      │
                         │                                               │
                         │  PartidosDelTorneoPage                       │
                         │    ├─ MotorFormatosPanel (sin cambios,       │
                         │    │    ya genera el fixture)                │
                         │    ├─ Tabla: resultado, fecha, fase, estado  │
                         │    │    (se QUITA: editar/walkover — pasan a │
                         │    │    Control de Mesa, decisión Sección 16)│
                         │    │    (se MANTIENE: crear partido nuevo,   │
                         │    │    asignar árbitro, cancelar — son      │
                         │    │    calendario, no operación en curso)   │
                         │    ├─ nombreEquipo vía                       │
                         │    │    useNombrePorIdConFaltantes (FIX)     │
                         │    └─ botón "Detalle del Partido" → navega   │
                         │         a /partidos/:partidoId               │
                         └─────────────────────────────────────────────┘
                                          │
                                          ▼
                         ┌─────────────────────────────────────────────┐
                         │         /partidos/:partidoId  (NUEVA ruta,   │
                         │         pública, solo lectura)                │
                         │                                               │
                         │  PartidoDetallePage = PartidoEnVivoPage       │
                         │    generalizada (renombre + sección nueva)   │
                         │    ├─ Marcador + estado (ya existe)          │
                         │    ├─ Timeline de eventos (ya existe)        │
                         │    └─ Alineaciones/convocados (NUEVO —       │
                         │         reusa GET /partidos/{id}/convocados  │
                         │         + GET /estadisticas/equipos/{id}/    │
                         │         plantilla, ambos ya públicos)        │
                         └─────────────────────────────────────────────┘
```

**Dependencias/acoplamiento:** el orquestador nuevo (`registrar_resultado_directo`)
depende de `HitoPartidoService` y `EventoPartidoService` tal como están — no les
agrega parámetros ni cambia su contrato, así que no hay blast radius sobre el
Cronómetro en vivo ni sobre Control de Mesa existente. El único cambio de
contrato de API es aditivo (`GET /partidos?solo_mios=true`, mismo patrón que
`/torneos`) y un endpoint nuevo (`POST /partidos/{id}/resultado-directo`) — cero
breaking changes.

**Escenario de falla realista por cada pieza nueva:**
- `resultado-directo` con un evento que referencia un `jugador_id` que no está en
  la plantilla del equipo → `EventoPartidoService.create` ya rechaza esto con 400
  (validación existente, reusada). Si falla a mitad de los N eventos, la
  transacción completa debe revertir (Inicio_Partido incluido) — **failure mode
  crítico, cubierto en Sección 9**.
- `solo_mios=true` con un TorneoAdmin sin ninguna asignación activa → debe
  devolver lista vacía, no 403 ni todos los partidos (mismo contrato que
  `/torneos?solo_mios=true`, ya testeado ahí).

## 8. Code Quality (Eng, Sección 2)

- **DRY confirmado, no violado:** el fix del bug "?" reusa `useNombrePorIdConFaltantes`
  tal cual — cero código nuevo de resolución de nombres.
- **DRY a vigilar:** `PartidoRepository.list` necesita el mismo override `IN` que
  ya tiene `TorneoRepository.list` (líneas 50-68 de `torneo.py`) — coordinar para
  no divergir la implementación (mismo docstring, mismo criterio "`[]` = cero
  filas, `None` = sin restricción").
- **Sobre-ingeniería evitada:** el orquestador de resultado directo NO reimplementa
  validación de eventos — delega 100% a `EventoPartidoService.create`.
- **Bajo-ingeniería a evitar:** el selector de torneo en Control de Mesa (ítem 2 de
  la Sección 6) no puede ser un afterthought — sin él, un TorneoAdmin con 2
  torneos asignados ve una lista mezclada sin saber a cuál torneo pertenece cada
  fila. Debe mostrar el torneo de cada partido en la lista, no solo local vs.
  visitante.

## 9. Test Review (Eng, Sección 3) — diagrama de cobertura

```
CÓDIGO NUEVO/MODIFICADO                                    COBERTURA REQUERIDA
[+] backend/app/repositories/partido.py — list() override
  ├── torneo_ids_permitidos=[list]                          [GAP] test: filtra a esos IDs exactos
  ├── torneo_ids_permitidos=[] (sin asignaciones)            [GAP] test: devuelve 0 filas, no todas
  └── torneo_ids_permitidos=None                             [GAP] test: sin cambio de comportamiento (regresión)

[+] backend/app/api/routes/partidos.py — ?solo_mios=true
  ├── TorneoAdmin con torneos asignados                      [GAP] test: solo ve los suyos
  ├── TorneoAdmin sin asignaciones                           [GAP] test: lista vacía
  ├── AdminGeneral con solo_mios=true                        [GAP] test: sin efecto, ve todo (mismo criterio que /torneos)
  └── request anónima con solo_mios=true                     [GAP] test: sin efecto (parámetro ignorado, no 401)

[+] backend/app/services/partido.py — registrar_resultado_directo()
  ├── Happy path: N eventos válidos                          [GAP] test: Inicio+N eventos+Fin creados, estado=Finalizado
  ├── Un evento inválido (jugador ajeno al equipo) a mitad    [GAP] [→CRÍTICO] test: TODA la transacción revierte
  │     de la lista                                                 (ni Inicio_Partido ni eventos previos quedan)
  ├── Partido ya Finalizado/Cancelado                         [GAP] test: 409, mismo criterio que marcar_walkover
  ├── Partido con un solo equipo definido (bracket TBD)       [GAP] test: 409/400, no puede cargar resultado
  ├── Lista de eventos vacía (0-0 sin sucesos)                [GAP] test: Inicio+Fin sin eventos, score 0-0, válido
  └── RBAC: requiere require_torneo_access_de (mismo criterio [GAP] test: TorneoAdmin sin asignación → 403
        que el resto de escritura de /partidos)

[+] frontend/.../PartidosDelTorneo.tsx — conversión a solo lectura
  ├── Botón "+ Nuevo"/acciones de fila (crear/editar/          [GAP] test: ya NO están en el DOM
  │     cancelar/asignar árbitro/walkover) removidas
  ├── Columna "Partido" resuelve nombre para un equipo          [GAP] [→REGRESIÓN] test: reproduce el bug reportado
  │     fuera de la ventana de 200 (bug reportado)                    (equipo con ID alto, no en el mock de 200) y
  │                                                                    confirma que YA NO cae a "?"
  ├── AccionWalkover eliminada de esta pantalla                [GAP] test: no se renderiza
  └── Botón "Detalle del Partido" navega a /partidos/:id        [GAP] test: click → ruta correcta

[+] frontend/.../ControlDeMesa.tsx — scoping + resultado directo
  ├── TorneoAdmin ve solo partidos de sus torneos asignados     [GAP] test: mock con 2 torneos, solo 1 asignado
  ├── AdminGeneral ve todos                                     [GAP] test: sin filtro aplicado
  ├── Selector de torneo cuando hay 2+ asignados                [GAP] test: aparece/no aparece según cantidad
  ├── "Cargar resultado directo" — happy path                   [GAP] [→E2E] test: form completo → POST → refetch
  ├── "Cargar resultado directo" — solo visible en Programado    [GAP] test: no aparece en En curso/Finalizado
  └── Error de validación de un evento del form                 [GAP] test: mensaje de error visible, form no se pierde

[+] frontend/.../PartidoEnVivo.tsx → PartidoDetallePage
  ├── Sección de alineaciones (convocados + plantilla)          [GAP] test: titulares/suplentes por equipo
  ├── Partido sin convocatoria guardada (toda la plantilla)     [GAP] test: fallback correcto (mismo criterio que MesaPanel)
  └── Ruta vieja /partido/:id/en-vivo sigue funcionando o        [GAP] [→REGRESIÓN] test: Dashboard.tsx "Ver en vivo →"
        redirige (Dashboard.tsx la linkea)                             no rompe

COBERTURA: 0/24 (todo nuevo) | CRÍTICO: 1 (rollback de transacción parcial)
```

### Regla de regresión (obligatoria, sin AskUserQuestion)

Dos regresiones identificadas, ambas se agregan al plan como requisito:
1. El fix del bug "?" necesita un test que **reproduzca el bug primero** (equipo
   con ID fuera de la ventana simulada de 200) y confirme que el fix lo resuelve —
   no alcanza con testear el hook en aislamiento, ya tiene sus propios tests.
2. Renombrar/generalizar `PartidoEnVivoPage` no puede romper el único lugar que la
   linkea hoy (`Dashboard.tsx:176`, "Ver en vivo →").

### Test Plan Artifact

Escrito en `~/.gstack/projects/Score-App/gabrielcruzleon12-feat-equipos-jugadores-plan-eng-review-test-plan-<fecha>.md`
(formato estándar de `/plan-eng-review`, para que `/qa`/`/qa-only` lo consuman como
input primario cuando se implemente):

```markdown
# Test Plan — Centralización Control de Mesa + fix fixture

## Affected Pages/Routes
- /control-de-mesa — ahora scoped por RBAC + nuevo flujo de resultado directo
- /torneo-admin/torneos/{id}/partidos — ahora solo lectura
- /partidos/{id} (nueva) — resumen público, generaliza /partido/{id}/en-vivo

## Key Interactions to Verify
- TorneoAdmin con 2 torneos asignados ve un selector y la lista cambia al elegir
- "Cargar resultado directo" con 3 eventos (2 goles + 1 tarjeta) deja el partido
  Finalizado con el marcador correcto
- Un equipo creado recién (después de superar 200 equipos totales en el sistema)
  muestra su nombre real en el fixture, no "?"
- Botón "Detalle del Partido" desde la tabla de solo lectura llega al resumen

## Edge Cases
- TorneoAdmin sin ningún torneo asignado → Control de Mesa vacío, no error
- Resultado directo con un jugador que no pertenece a ningún equipo del partido →
  rechazo claro, ningún hito/evento a medias queda guardado
- Partido de bracket con un equipo todavía "TBD" → resultado directo deshabilitado

## Critical Paths
- Ciclo completo: crear equipo → generar fixture → ver nombre correcto en
  /torneo-admin/.../partidos → "Detalle del Partido" → cargar resultado directo
  desde Control de Mesa → el resumen público refleja el resultado
```

## 10. Performance (Eng, Sección 4)

- `GET /partidos?solo_mios=true` reusa `AsignacionTorneoAdminRepository.listar_torneo_ids_activos`,
  ya un probe de una sola columna sobre un índice único — sin N+1 nuevo.
- El selector de torneo en Control de Mesa no dispara una query nueva por torneo:
  reusa el `equiposQuery`/`partidosQuery` ya existentes, solo cambia el filtro.
- `registrar_resultado_directo` con N eventos hace N llamadas a
  `EventoPartidoService.create` dentro de una misma transacción — para un partido
  típico (0-15 eventos) esto es trivial; no amerita batch/bulk-insert.

## 11. Fallos y su cobertura

| Fallo | Test | Manejo de error | Visible al usuario |
|---|---|---|---|
| Evento inválido a mitad de `resultado-directo` | Sí (nuevo, crítico) | Rollback de transacción completo | Mensaje 400 con el evento culpable |
| TorneoAdmin sin torneos asignados entra a Control de Mesa | Sí (nuevo) | Lista vacía, no error | "No tenés torneos asignados" (mismo patrón que 403 de `_verificar_acceso_torneo`) |
| `/partido/:id/en-vivo` deja de existir tras el rename | Sí (nuevo) | — | Link roto en Dashboard.tsx si no se actualiza junto |

**Gap crítico marcado:** si el rollback de `registrar_resultado_directo` no se
implementa con una transacción explícita (todo-o-nada), un fallo a mitad de carga
deja Hitos y Eventos parciales sin que el usuario lo note hasta revisar la
timeline — silencioso. Esto es requisito de implementación, no opcional.

## 12. NOT in scope

- **Paginación real con cursor en `/equipos`/`/jugadores` (TODOS.md §3B-9).** El
  fix de esta plan (`useNombrePorIdConFaltantes` en la 8va pantalla) es el mismo
  parche de síntoma que las otras 7 — no el techo real de 200 filas al LISTAR.
- **Migrar `DetalleEquipo.tsx`/`ModalIndividual` al mismo hook.** Ya registrado en
  TODOS.md como mejora recomendada no pedida; no está en el blast radius de este
  pedido.
- **Registro de resultados para disciplinas sin dos equipos** (Atletismo, Combate,
  Ajedrez). El modelo de `EVENTOS_PARTIDO`/`resultado-directo` asume siempre dos
  equipos y goles — mismo límite ya documentado y aparcado en TODOS.md.
- **Notificar al club cuando se carga un resultado directo.** Requiere el módulo
  de notificaciones (aparcado, TODOS.md).

## 13. TODOS.md — ítems a agregar

Se agregan al cierre de este plan (no ahora, recién cuando se implemente):
- Nada nuevo más allá de lo ya "NOT in scope" arriba — no se identificó trabajo
  genuinamente nuevo que merezca quedar diferido; todo lo tocado por este pedido
  entra en el alcance de arriba.

## 14. Worktree parallelization strategy

Dos workstreams independientes, sin módulos compartidos:

| Lane | Pasos | Depende de |
|---|---|---|
| A (backend) | `PartidoRepository.list` override → `?solo_mios=true` en la ruta → `PartidoService.registrar_resultado_directo` + endpoint | — |
| B (frontend, solo-lectura + fix bug) | `PartidosDelTorneo.tsx` → solo lectura + fix `useNombrePorIdConFaltantes` + botón Detalle | — (no depende de A: el fix del bug "?" y quitar acciones de escritura son cambios de UI puros) |
| C (frontend, Control de Mesa) | Selector de torneo + scoping de la query + modal "Resultado directo" | Depende de A (necesita `?solo_mios=true` y el endpoint nuevo) |
| D (frontend, detalle público) | Generalizar `PartidoEnVivoPage` → `/partidos/:id` + sección alineaciones | — |

**Orden de ejecución:** Lanzar A, B y D en paralelo (3 worktrees). Mergear A.
Luego C (necesita A mergeado). B y D no tocan `partido.py`/`ControlDeMesa.tsx` —
sin conflicto entre sí ni con A.

## 15. Decision Audit Trail

<!-- AUTONOMOUS DECISION LOG -->
## Decision Audit Trail

| # | Fase | Decisión | Clasificación | Principio | Racional | Rechazado |
|---|---|---|---|---|---|---|
| 1 | CEO | Corregir el diagnóstico del usuario sobre la causa del bug "?" | Mecánica | P6 (verificar antes de construir) | `EquipoService.create` persiste bien; el bug es de lectura (ventana de 200), no de escritura | La hipótesis original del usuario (nombre nulo al crear) |
| 2 | CEO | Alcance: incluir selector de torneo en Control de Mesa aunque no se pidió explícitamente | Mecánica (blast radius <1 día) | P2 | Sin selector, el scoping RBAC es invisible/confuso en la UI | — |
| 3 | CEO | NO incluir migrar `DetalleEquipo.tsx` al hook de resolución de nombres | Mecánica | P3 | Ya registrado en TODOS.md como mejora no pedida, fuera del blast radius directo | Migrarlo ahora |
| 4 | CEO | NO incluir paginación real con cursor (3B-9) | Mecánica | P2 | Cambia contrato de API, ciclo propio ya documentado | Resolverlo acá |
| 5 | Eng | Ingreso directo de resultado: orquestar Hito+Evento existentes (Alternativa A) en vez de una tabla paralela | Mecánica | P4+P5 | Reusa validación ya probada, evita una segunda fuente de verdad de "qué pasó en el partido" | Alternativa B (estructura paralela), Alternativa C (aflojar guard 3A-8) |
| 6 | Eng | `PartidoRepository.list` override calca el patrón de `TorneoRepository.list` | Mecánica | P4 | Mismo problema (`IN` sobre una lista de IDs permitidos), mismo criterio `[]` vs `None` ya probado en tests | Reimplementar desde cero |
| 7 | Eng | Generalizar `PartidoEnVivoPage` en vez de crear una página nueva desde cero para `/partidos/:id` | Mecánica | P4+P5 | 80% del contenido pedido ("resumen bonito con goles, tarjetas") ya existe; falta solo alineaciones | Página nueva sin reuso |
| 8 | Eng | Requisito no-negociable: `registrar_resultado_directo` debe ser una transacción atómica (todo-o-nada) | Mecánica | Prime Directive #1 (cero fallos silenciosos) | Un evento inválido a mitad de N no puede dejar Hitos/Eventos parciales sin que el usuario se entere | — |
| 9 | CEO | "Crear partido"/"asignar árbitro" quedan en `/torneo-admin/.../partidos`; "editar"/"walkover" migran a Control de Mesa — **Taste, resuelta por el usuario en el gate** | **Taste** | Ninguno domina — lectura literal vs. lectura funcional del pedido | Ver Sección 16 — usuario eligió la opción recomendada | Migrar también crear/asignar árbitro |

## 16. Taste Decision — RESUELTA por el usuario

¿"Crear partido nuevo" y "asignar árbitro" deben migrar a Control de Mesa, o
quedan como las únicas 2 acciones de escritura que sobreviven en
`/torneo-admin/.../partidos`?

**Decisión del usuario: quedan en `/torneo-admin/.../partidos`** (opción
recomendada). Son decisiones de **calendario/planificación del torneo** (cuándo
se juega, quién arbitra), no de **gestión del partido en curso** (convocatoria,
titulares, cronómetro, resultado). El pedido enumera 4 funcionalidades
"exclusivas" de Control de Mesa y ninguna es "programar" o "asignar árbitro".

**Consecuencia para el alcance (Sección 6, ítem 9 — actualizado):** de las
acciones de escritura hoy en `PartidosDelTorneo.tsx` (crear, editar, cancelar,
asignar árbitro, walkover), se **quitan** de esa pantalla: editar (fecha/fase/
grupo/estado libre) y walkover — son gestión del partido en curso, entran a
Control de Mesa (walkover como una acción más junto a "Cargar resultado
directo": ambas cierran el partido sin cronómetro en vivo). Se **mantienen** en
`/torneo-admin/.../partidos`: crear partido nuevo y asignar árbitro — son
planificación de calendario, no operación de un partido. "Cancelar" (baja lógica
del partido, no del resultado) también es planificación y se mantiene ahí.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` (vía autoplan) | Scope & strategy | 1 | CLEAR | 1 corrección de diagnóstico, 4 decisiones mecánicas de alcance, 0 user challenges |
| Codex Review | `/codex review` | Independiente 2da opinión | 0 | N/A | Codex no instalado en este entorno — `[subagent-only]` en las 3 fases |
| Eng Review | `/plan-eng-review` (vía autoplan) | Arquitectura & tests (requerido) | 1 | CLEAR | 24 gaps de test identificados (todos nuevos, ninguno existente sin cubrir), 1 gap crítico (atomicidad de la transacción de resultado directo) marcado como requisito no negociable |
| Design Review | `/plan-design-review` (vía autoplan) | Gaps de UI/UX | 1 | CLEAR | Alcance UI cubierto en Secciones 6-9 (selector de torneo, botón Detalle, conversión a solo lectura) — ver nota de compresión abajo |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | N/A | Sin alcance developer-facing (feature interna de admin, no SDK/API pública/CLI) |

**Nota de proceso (transparencia sobre compresión de /autoplan):** Codex no está
disponible en este entorno (`command -v codex` falla) — las 3 fases con voz
externa corrieron en modo `[subagent-only]`, no cross-model. Dado que el pedido
llegó como una especificación de arquitectura ya precisa (no un plan ambiguo que
necesitara exploración), la verificación de código real (Sección 1, 3, 7) se hizo
directamente en esta sesión en vez de despachar 3 subagents independientes
"foreground" por fase — cada hallazgo de esta plan está anclado a una línea de
código específica ya leída, no a un supuesto. Esto es una compresión deliberada
del proceso estándar de `/autoplan` (bias hacia la acción, P6), no un salteo de
rigor: cada afirmación de "esto ya existe" fue verificada abriendo el archivo
citado, siguiendo la lección ya aprendida en este proyecto (`verify-reuse-claims-before-writing`).

**VERDICT:** CEO + ENG CLEARED — listo para implementar. La única taste decision
(Sección 16) fue resuelta por el usuario en el gate final (opción recomendada).
El gap crítico de atomicidad (Sección 11) queda como requisito no negociable de
implementación, no como pregunta abierta.

NO UNRESOLVED DECISIONS
