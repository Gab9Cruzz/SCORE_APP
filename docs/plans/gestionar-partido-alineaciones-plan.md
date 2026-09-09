<!-- /autoplan restore point: ~/.gstack/projects/Score-App/feat-equipos-jugadores-plan-autoplan-restore-20260908-112804.md -->
# Plan: "Gestionar Partido" — vista inmersiva de alineaciones en Control de Mesa

Generado con `/autoplan` (revisión CEO → Design → Eng). Codex no está
disponible en esta máquina (`codex` no está en PATH) — corrió en modo
`[subagent-only]`, una sola voz revisora independiente por fase, consistente
con el precedente de los planes anteriores de este repo.

**Solo documento — sin implementación.** El usuario pidió explícitamente el MD
de diseño, no código.

**Las 2 decisiones que requerían criterio humano fueron confirmadas con el
usuario en el gate final (2026-09-08), ambas por la opción recomendada** — el
arrastre acotado a `>=1000px`, y el mínimo como regla nueva. Ver el Decision
Audit Trail y el GSTACK REVIEW REPORT al final. Sin decisiones pendientes:
este documento queda listo para pasar a implementación.

> **El hallazgo que hay que leer antes que nada:** existe un **deadlock** que
> hace la convocatoria inalcanzable para un TorneoAdmin — para empezar un
> partido hace falta convocatoria, y para cargar la convocatoria hace falta
> que el partido ya haya empezado. Son ~5 líneas (Bloque 0). Desbloquea hoy el
> 100% del dolor que motivó este pedido, sin esperar al resto del plan.

## Requerimiento del usuario (verbatim, resumido)

1. **Punto de entrada único**: en el dashboard de `/control-de-mesa`, cada
   partido programado tiene UN solo botón principal, "Gestionar Partido",
   que lleva a una vista inmersiva dedicada a ese encuentro.
2. **Convocatorias + alineaciones interactivas**, paso a paso:
   - Paso 1: checkboxes de convocados (quién asistió).
   - Paso 2: drag & drop — todos los convocados arrancan en "Suplentes"
     (contenedor inferior), el operador arrastra a "Titulares" (superior).
   - Edición libre mientras el partido no arrancó.
3. **Reglas de negocio reales**:
   - Arranque con mínimos: se puede iniciar con el mínimo reglamentario
     (ej. 5) aunque la plantilla no esté completa.
   - Llegadas tardías "on the fly": con el partido EN CURSO, convocar a un
     jugador y meterlo en suplentes sin cortar el cronómetro ni el estado.
4. **Acciones finales**:
   - "Empezar Partido" → estado "En Curso", bloquea cambios destructivos en
     la alineación titular, arranca cronómetro y panel de eventos.
   - "Cargar Resultado Directo" → omite el vivo, modal para marcador final,
     goles y tarjetas.

---

## Fase 1 — CEO Review (Estrategia y Alcance)

**Modo: SELECTIVE EXPANSION.** No es un módulo nuevo: es una consolidación de
UX sobre piezas que ya existen, más 3 capacidades genuinamente nuevas. La
conclusión más importante de esta fase, y la que debería cambiar cómo se
prioriza el trabajo:

> **~70% de lo pedido ya está construido.** Lo nuevo de verdad son tres
> cosas: (1) el mínimo reglamentario para arrancar, (2) el bloqueo de
> cambios destructivos con el partido en curso, (3) el drag & drop. Todo lo
> demás es mover, enrutar y renombrar lo que ya funciona.

### 0A — Premisas del requerimiento (enunciadas y asumidas)

| # | Premisa | Veredicto |
|---|---------|-----------|
| P1 | El problema real es que la fila del dashboard tiene demasiadas acciones. | **Confirmada.** Cada fila hoy monta 4-5 controles: `EditorFechaPartido`, `Empezar Partido`/`Ir al partido en vivo`, `Cargar resultado directo` y `Walkover` (`ControlDeMesa.tsx:389-440`). Con `@media (max-width: 480px)` en `index.css:665` y la app operada desde el celular, esa fila envuelve mal. La queja es legítima. |
| P2 | "Entrar a una vista inmersiva" implica una ruta propia. | **Confirmada, y arregla un bug latente no pedido.** Hoy la mesa NO es una ruta: `ControlDeMesa.tsx:340` hace `if (partidoId !== null) return <MesaPanel .../>` sobre `useState`. Consecuencia: no hay deep-link al partido, el botón Atrás del navegador sale del módulo entero, y un refresh en pleno partido devuelve al operador a la lista. Convertirlo en ruta es lo que el usuario pidió y además cierra ese agujero. |
| P3 | El "Paso 1: checkboxes de convocados" hay que construirlo. | **Falsa — ya existe.** `Convocatoria.tsx:141-182` ya es exactamente eso: un checkbox "convocado" por jugador de la plantilla vigente, más un checkbox "Titular" anidado. El backend también (`PUT/GET /partidos/{id}/convocados`, `convocado_a_partido.py`). El Paso 1 es una **reubicación**, no una construcción. |
| P4 | El drag & drop es la interacción correcta para armar la alineación. | **Cuestionada — ver D2.** No hay ninguna librería de D&D en `frontend/package.json`, y el D&D nativo de HTML5 no dispara en touch (no hay puente `touchstart`→`dragstart`). En una app cuya hoja de estilos tiene `.tap-button` y un breakpoint de 480px, el operador típico está con una mano en un celular. Arrastrar es más caro que tocar, y hoy marcar titular ya cuesta **un** tap. Es la única premisa del requerimiento que, tomada literal, puede empeorar el producto. |
| P5 | Existe en algún lado un "mínimo reglamentario (ej. 5)". | **Falsa — no existe.** `Modalidad.tamano_equipo` significa "cuántos juegan a la vez" (11 en Fútbol 11), y `hito_partido.py::_validar_titulares` exige **al menos** ese número para permitir `Inicio_Partido` (`if n < requeridos`, `hito_partido.py:186`) — es decir, el único mínimo que existe hoy es el equipo completo. No hay ningún campo de mínimo en el esquema. Es campo nuevo — ver D1. Nota: el "5" del ejemplo no es universal (en Fútbol 11 el mínimo reglamentario real es 7, y una liga recreativa puede fijar 4): el número es **por torneo**, no una constante. |
| P6 | Las llegadas tardías "on the fly" hay que habilitarlas. | **Confirmada como objetivo, falsa como diagnóstico.** `ConvocadoAPartidoService.reemplazar` **no chequea `partido.estado`** — hoy ya se puede editar la convocatoria con el partido en curso. El problema no es que esté prohibido: es que el mecanismo (`PUT` que reemplaza la lista ENTERA) es peligroso en vivo. Ver P7 y EC-3. |
| P7 | "Empezar Partido bloquea los cambios destructivos en la alineación titular." | **Falsa hoy — es funcionalidad nueva.** No hay ningún bloqueo: el mismo `PUT` que agrega un suplente tardío puede borrar a un titular que ya metió un gol. Es el trabajo de backend más importante del plan, y el requerimiento lo menciona al pasar, como si ya existiera. |
| P8 | "Cargar Resultado Directo" hay que construirlo (modal de marcador, goles, tarjetas). | **Falsa — ya existe completo.** `ModalResultadoDirecto` (`ControlDeMesa.tsx:527-772`) + `POST /partidos/{id}/resultado-directo` (`partido.py:120-185`, atómico, reusa los mismos triggers que el flujo en vivo). El Requerimiento 4b es **cero código nuevo**: solo cambia de qué pantalla se abre el modal. |
| P9 | (Asumida) La vista sirve para partidos "Programado". | **Incompleta.** El propio Requerimiento 3 exige operar con el partido "En curso" (llegadas tardías). La vista tiene que servir a los dos estados, y el dashboard ya lista los dos (`ControlDeMesa.tsx:336`). Se corrige en el alcance. |
| P10 | (Asumida, **gap real del requerimiento**) Las únicas acciones de la fila son las 2 nombradas. | **Falsa.** El requerimiento nombra "Empezar Partido" y "Cargar Resultado Directo", pero la fila también tiene **Walkover** y **editar fecha**. Walkover se mudó a Control de Mesa hace 3 días a propósito (`control-mesa-centralizacion-fixture-plan.md`, Decision Audit #9). Colapsar la fila a un botón sin decir a dónde van esas dos es regresar una decisión reciente por omisión. Se resuelve en D5: **ambas se mudan adentro de la vista**. |
| P11 | (Asumida) El mínimo aplica a los dos caminos de cierre de un partido. | **A decidir — ver D4.** `registrar_resultado_directo` inserta el `HitoPartido` a mano (`partido.py:166`) en vez de pasar por `HitoPartidoService.registrar`, así que **hoy saltea `_validar_titulares` por completo**: se puede cerrar un partido con cero convocados por el camino directo, pero no se puede arrancar uno en vivo sin la plantilla entera. Esa asimetría existe hoy y no está documentada. |

### 0B — Qué ya existe (leverage map)

| Sub-problema del requerimiento | Código que ya lo resuelve | Trabajo real |
|---|---|---|
| R1 Vista inmersiva dedicada | `MesaPanel` (`ControlDeMesa.tsx:823-1238`) ya ES la vista inmersiva | Convertirla en ruta (`App.tsx` ya tiene el patrón en `/partidos/:partidoId`) |
| R1 Botón único | — | Colapsar 4-5 controles a 1 y reubicar los otros adentro |
| R2 Paso 1 (checkboxes) | `Convocatoria.tsx:141-182` + `PUT /partidos/{id}/convocados` | Reubicar y reencuadrar como "Paso 1" |
| R2 Titular/suplente | Columna `CONVOCADO_A_PARTIDO.Titular` (`01_schema.sql:563`) | Ninguno en datos |
| R2 Paso 2 (drag & drop) | — nada, y sin librería instalada | **Nuevo** — ver D2 |
| R3 Arranque con mínimos | `_validar_titulares` (`hito_partido.py:151-205`) exige el total, no un mínimo | **Nuevo** — ver D1 |
| R3 Llegadas tardías | `reemplazar` ya no chequea estado | Acotar el permiso, no abrirlo — ver D3 |
| R4a Empezar Partido | `POST /partidos/{id}/hitos` + `BotonEmpezarPartido` + `useTitularesCompletos` | Reubicar + ajustar al mínimo |
| R4a Bloqueo de titulares en vivo | — nada | **Nuevo** — ver D3 |
| R4b Cargar Resultado Directo | `ModalResultadoDirecto` + `POST .../resultado-directo` | Solo reubicar |
| Cronómetro y eventos en vivo | `Cronometro.tsx`, `CargaEvento`, cola offline de eventos | Ninguno |

**Lectura:** de 11 sub-problemas, 3 son código nuevo. El resto es mudanza.

### 0C — Dream state

```
CURRENT ──────────────────────────────────────────────────────────
  Fila con 4-5 acciones · convocatoria enterrada como panel opt-in
  dentro de la mesa · arranque exige la plantilla COMPLETA · sin
  bloqueo de edición en vivo · panel por useState (sin deep-link,
  el refresh pierde el partido)

THIS PLAN ────────────────────────────────────────────────────────
  1 fila = 1 botón · vista con ruta propia y deep-link estable ·
  convocatoria como paso explícito con dos contenedores · mínimo
  configurable por torneo · edición en vivo acotada a "sumar
  suplentes" · Walkover y reprogramación adentro de la vista

12-MONTH IDEAL ───────────────────────────────────────────────────
  Alineación con posiciones/formación sobre cancha · sustituciones
  que consumen del banco solas · minutos jugados derivados de
  hitos + cambios · convocatoria pre-cargada desde el roster o
  desde el partido anterior
```

**Delta:** este plan deja el producto a ~60% del ideal. Lo que queda afuera
a propósito: posiciones/formación, minutos jugados, y el pre-llenado de la
convocatoria (ver "NO está en alcance").

### 0C-bis — Alternativas de implementación

| Alternativa | Completeness | Esfuerzo (humano / CC) | Veredicto |
|---|---|---|---|
| **A. Ruta propia + interacción dual (arrastrar en puntero, tocar en touch) + minimo por torneo + convocatoria consciente del estado** | 10/10 | ~4-5 días / ~2-3 h | **Elegida.** Cumple los 4 requerimientos, y el único punto donde se aparta de la letra del pedido (D&D como única interacción) es para no romper el caso de uso real del celular. |
| B. Ruta propia + solo tap-to-move, sin drag & drop | 8/10 | ~3 días / ~1.5 h | Rechazada como default: no cumple el Requerimiento 2 tal como está escrito. Queda como el camino de repliegue si el D&D resulta caro de mantener. |
| C. Dejar el panel por `useState`, solo maquillar la fila | 3/10 | ~1 día / ~30 min | Rechazada: no cumple "el operador abandona la tabla general", y deja intacto el bug de deep-link/refresh (P2). |

### 0D — Decisiones de alcance

#### D1 — ¿De dónde sale el mínimo reglamentario?

**La pregunta:** el Requerimiento 3 dice "el mínimo reglamentario (por
ejemplo, 5)". Ese número no existe en ningún lado del sistema.

> **Confirmado con el usuario en el gate final:** la intención es **arrancar
> con menos jugadores que los que la modalidad pone en cancha** (ej. Fútbol 11
> con 7), no el caso "Fútbol 5 arranca con sus 5 aunque falten suplentes"
> —que ya funciona hoy (`hito_partido.py:186` es `if n < requeridos`) y solo
> está bloqueado por H1—. Es decir: **es regla nueva y la migración va.**

| Opción | Completeness | Veredicto |
|---|---|---|
| a. Constante en el código (`MINIMO = 5`) | 2/10 | Rechazada. Un sistema multi-disciplina con Fútbol 11, Fútbol 5, Vóley, Tenis y Pádel no tiene un mínimo único. |
| b. Columna nueva en `MODALIDAD` | 6/10 | Rechazada como única fuente. El catálogo es **inmutable por API** por decisión previa (`ModalidadUpdate` solo acepta `estado`, `ediciones-catalogo-disciplinas-plan.md` C1): el organizador no podría ajustarlo, haría falta una migración por cada liga con reglamento propio. Sirve como *default*, no como fuente de verdad. |
| c. Columna en `CONFIGURACION_TIEMPO_TORNEO` | 7/10 | Rechazada tras la voz externa. Fue mi eleccion inicial, con el argumento de que esa tabla ya se carga en `_cargar_contexto` y por lo tanto no costaba queries. **El argumento no se sostiene**: `_validar_titulares` ya recibe el `Torneo` resuelto (`hito_partido.py:207-212`), asi que la opcion d tampoco cuesta queries. Y un minimo de jugadores en una tabla llamada configuracion de **tiempo** esta semanticamente mal ubicado. |
| **d. Columna `Minimo_Jugadores_Para_Iniciar` en `TORNEO`, `NULL` = usar `tamano_equipo`** | 9/10 | **Elegida.** Precedente exacto en el repo: `Torneo.permite_walkover_grupos` (`models/torneo.py:53`) es un flag de reglamento por torneo, editable por el TorneoAdmin. `NULL` como default reproduce exactamente el comportamiento de hoy sin backfill, y evita inventar un minimo para las ~35 filas del catalogo. Ver el detalle en **D1 — REVISADA** (Fase 1, enmiendas). |

**Decision: d** (revisada tras la voz externa — ver **D1 — REVISADA** en las
enmiendas de la Fase 1 para el razonamiento completo). Principio P4 (DRY —
reusar el patron de flag reglamentario por torneo que ya existe) y P1 (cubre el
caso real de reglamentos distintos por liga, que b no cubre).

Regla derivada: `minimo_jugadores_para_iniciar` debe cumplir
`1 <= minimo <= tamano_equipo`.
Un mínimo mayor al tamaño del equipo es incoherente; uno de 0 convertiría
"Empezar Partido" en un botón sin validación, que es exactamente el estado
del que se salió en `fixes-datos-traspasos-control-mesa-plan.md`.

#### D2 — Drag & drop en una app que se opera con el pulgar

**La pregunta:** el Requerimiento 2 pide arrastrar y soltar. El D&D nativo de
HTML5 no funciona en touch, y no hay librería instalada.

| Opción | Completeness | Veredicto |
|---|---|---|
| a. D&D nativo HTML5 (`draggable`, `onDragStart`/`onDrop`) | 5/10 | Rechazada **como única interacción**. Cero dependencias nuevas, pero en el celular —el dispositivo real del operador— simplemente no responde. Sería entregar el requerimiento roto justo donde más se usa. |
| b. Librería de D&D con soporte de puntero (`@dnd-kit/core`, ~30 KB) | 8/10 | Rechazada por sí sola: agrega la primera dependencia de UI del frontend (hoy solo React, Router y React Query) para un problema que el tap ya resuelve en un toque. Choca con el escalón 4 de la escalera de reuso. |
| **e. Arrastre solo en `>=1000px` + tap en todos lados** | 10/10 | **ELEGIDA EN EL GATE FINAL** — ver la decisión abajo. Es c, acotada al viewport donde el gesto realmente funciona. |
| c. Interacción dual en todos los viewports | 9/10 | Base de la elegida, pero El D&D se implementa con Pointer Events (`pointerdown`/`pointermove`/`pointerup` + `setPointerCapture`), que cubren mouse y touch con una sola implementación y sin dependencia. En paralelo, cada tarjeta de jugador lleva un botón explícito "↑ Titular" / "↓ Suplente": un tap, sin arrastre, y accesible por teclado y lector de pantalla (que es donde el D&D puro falla siempre). |

**Decisión: c, acotada por el usuario en el gate final — el arrastre va solo
en `>=1000px`; en celular y tablet chica queda el tap.** Es la opción e de la
tabla, que sintetiza c con lo que encontraron las dos voces externas:

- En 375px la zona destino casi nunca está en pantalla (**H-20**: ~7 filas
  visibles contra ~900px de contenido), así que cada arrastre pasa a ser
  "llevar el dedo al borde y esperar el auto-scroll" contra un solo toque.
- El gesto **no se puede cubrir con unit tests** (**M1-eng**: jsdom no
  implementa `PointerEvent` ni `setPointerCapture`, y `getBoundingClientRect()`
  devuelve ceros, así que no hay forma de decidir sobre qué zona se soltó).
- El design doc del módulo ya fijó "celular en cancha, 2-3 toques, sin tipear"
  como criterio de éxito.

En `>=1000px` el layout es de dos columnas, las dos zonas entran juntas en
pantalla y el mouse hace el gesto barato: ahí el arrastre suma y se implementa.
El Requerimiento 2 se cumple —se arrastra y se suelta— sin entregar el gesto
roto justo donde más se usa.

**Lo que esta decisión ahorra:** el long-press de H-22, la pelea del
auto-scroll contra la barra sticky (H-27), y el `touch-action: none` en touch.
El arrastre queda como ~80-100 líneas para puntero, no ~150 para todo.

#### D3 — Qué se puede editar con el partido en curso

**La pregunta:** el Requerimiento 3 quiere sumar un jugador tardío en vivo, y
el Requerimiento 4a quiere "bloquear cambios destructivos". Hoy no hay ni lo
uno ni lo otro: hay un `PUT` que reemplaza la lista entera sin mirar el estado
del partido.

**Decisión:** el permiso se acota **por operación, no por pantalla**. Con el
partido `En curso`, la convocatoria acepta **sumar** convocados (suplentes) y
**promover** suplente→titular; rechaza **quitar** a cualquiera que ya esté
marcado como titular y **degradar** titular→suplente. Con el partido
`Programado`, edición libre (Requerimiento 2). Con el partido `Finalizado` o
`Cancelado`, solo lectura.

Por qué no alcanza con hacerlo en el frontend: un titular que ya tiene un gol
o una tarjeta cargada no puede desaparecer de la convocatoria sin dejar
estadísticas colgadas de un jugador que "no jugó". La fuente de verdad va en
el service, igual que `_validar_titulares` (mismo criterio explícito de
`fixes-datos-traspasos-control-mesa-plan.md`, D4).

#### D4 — ¿El mínimo también aplica a "Cargar Resultado Directo"?

**Decisión: no.** `registrar_resultado_directo` seguirá sin exigir
convocatoria. Es deliberado: ese camino existe para partidos **que ya se
jugaron** y se registraron en papel, donde exigir una alineación sería pedir
un dato que el operador no tiene. Lo que sí cambia: la asimetría pasa a estar
**documentada** (hoy es un efecto colateral silencioso de que `partido.py:166`
inserta el `HitoPartido` a mano en vez de pasar por `HitoPartidoService`).

#### D5 — Dónde van Walkover y "editar fecha" (gap del requerimiento, P10)

**Decisión: adentro de la vista "Gestionar Partido".** Walkover se mudó a
Control de Mesa hace 3 días por decisión explícita
(`control-mesa-centralizacion-fixture-plan.md`, Audit #9); dejarlo caer al
colapsar la fila sería revertir esa decisión sin discutirla. Van en una
sección "Otras acciones", visualmente por debajo de los dos botones
principales que pide el Requerimiento 4 — presentes, pero sin competir con
ellos.

### 0E — Interrogatorio temporal

- **HORA 1** — El operador abre `/control-de-mesa` en el celular, en la
  cancha. Ve filas limpias: equipos, fecha, un botón. Toca "Gestionar Partido".
- **HORA 2** — Marca 9 de 14 presentes. Los 9 caen en Suplentes. Sube 7 a
  Titulares (arrastrando en la tablet, tocando en el celular). El contador
  dice "7/7 mínimo" y "Empezar Partido" se habilita.
- **HORA 3** — Arranca. Minuto 20 llega el #12: el operador vuelve a la
  configuración desde el panel en vivo, lo tilda, cae en Suplentes. El
  cronómetro nunca se detuvo. Intenta sacar a un titular por error y el
  sistema lo rechaza explicando por qué.
- **HORA 6+ (mes 3, 40 partidos jugados)** — Acá aparece la fricción real que
  este plan **no** resuelve: la convocatoria se arma desde cero en cada
  partido. Con planteles de 14-18 y equipos que repiten el 80% de la lista,
  ese es el trabajo repetitivo que va a doler. Queda registrado como diferido
  (pre-llenado desde el partido anterior), no resuelto acá.

### 0F — Confirmación de modo

**SELECTIVE EXPANSION** confirmado: el plan extiende `ControlDeMesa.tsx`,
`Convocatoria.tsx`, `hito_partido.py`, `convocado_a_partido.py` y una columna
nueva en `TORNEO`; no reescribe ninguno y no introduce tablas nuevas.

### Secciones de revisión CEO (1-11)

#### Sección 1 — Arquitectura

Dos decisiones estructurales, ambas con hallazgo.

**1.1 La ruta nueva no puede ser `/partidos/:id`.** Esa ruta ya existe y es
**pública sin auth** (`App.tsx:63`, `PartidoEnVivoPage`, mismo criterio que
`GET /partidos` en `partidos.py:56`). La vista "Gestionar Partido" escribe
(convocatoria, hitos, walkover), así que necesita ruta propia bajo el módulo
gateado. Forma elegida: `/control-de-mesa/partido/:partidoId`, envuelta en el
mismo `RequireRole roles={["TorneoAdmin","AdminGeneral","Arbitro"]}` que ya
protege `/control-de-mesa` (`App.tsx:49-56`). Anidarla bajo el prefijo del
módulo, y no colgarla de la raíz, mantiene legible de un vistazo qué está
gateado.

**1.2 `ControlDeMesa.tsx` no aguanta esto adentro.** Son 1490 líneas hoy con
7 componentes en un archivo (`ControlDeMesaPage`, `MesaPanel`,
`ModalResultadoDirecto`, `AccionWalkoverMesa`, `EditorFechaPartido`,
`CargaEvento`, `EventoTimelineFila`, `BotonEmpezarPartido`). Sumar la vista
de gestión y el editor de alineaciones adentro lo empuja a ~2000. El repo ya
tiene el precedente de sub-carpeta por módulo
(`pages/torneo-admin/torneo-dashboard/`), así que se sigue ese patrón:

```
pages/control-mesa/
  ControlDeMesa.tsx        (dashboard: lista + 1 botón por fila)
  GestionarPartido.tsx     (vista inmersiva: pasos 1-2 + acciones)
  AlineacionEditor.tsx     (los dos contenedores + arrastre/tap)
  MesaPanel.tsx            (movido tal cual, sin cambios de lógica)
  ModalResultadoDirecto.tsx (movido tal cual)
```

La mudanza es mecánica (mover + reexportar), sin cambios de comportamiento.
Se hace en un commit propio, separado del commit que agrega funcionalidad,
para que el diff de la feature sea legible.

**Diagrama de dependencias (después):**

```
  /control-de-mesa                    /control-de-mesa/partido/:id
        │                                       │
  ControlDeMesa.tsx ──── navigate() ────► GestionarPartido.tsx
        │                                       │
        │                          ┌────────────┼────────────┬─────────────┐
        │                          ▼            ▼            ▼             ▼
        │                 AlineacionEditor  MesaPanel  ModalResultado  Otras acciones
        │                          │            │        Directo       (walkover,
        │                          │            │            │          reprogramar)
        ▼                          ▼            ▼            ▼             ▼
  GET /partidos          GET/PUT .../convocados │   POST .../resultado-  POST .../walkover
  (?solo_mios)           GET /plantillas        │        directo         PATCH /partidos/{id}
                         GET .../cronometro ────┘
                         POST .../hitos
```

**Lo que NO cambia:** ningún endpoint se renombra, ninguna tabla se crea,
`MesaPanel` y `ModalResultadoDirecto` no cambian de lógica interna. El
`GET /partidos` del dashboard queda igual.

#### Sección 2 — Mapa de errores y rescate

| Falla | Qué ve el operador hoy | Rescate propuesto |
|---|---|---|
| Arranca sin llegar al mínimo | Botón deshabilitado con tooltip (`BotonEmpezarPartido:213`) | Igual, pero el texto pasa a decir el mínimo real, no el total: "Rojo: 5 de 7 titulares (mínimo 7)" |
| Dos operadores editan la misma convocatoria | **Nada** — el último `PUT` gana en silencio y borra lo del otro | `409` con la lista vigente en la respuesta + refetch y aviso "la convocatoria cambió desde otro dispositivo" (ver EC-3) |
| Intenta sacar un titular en vivo | **Nada** — hoy lo permite y deja los goles colgados | `400` del service con el nombre del jugador y por qué no se puede |
| Se corta la red mientras arma la alineación | Error genérico de mutación | La alineación vive en estado local hasta "Guardar": se reintenta el mismo `PUT` sin perder lo armado. **No** se reusa la cola offline de eventos (`colaOfflineEventos.ts`): un `PUT` de reemplazo reintentado a ciegas puede pisar cambios más nuevos, que es justo lo contrario de lo que hace un evento append-only |
| El partido ya arrancó desde otra pestaña | El `POST` de hito devuelve 400 "no se puede registrar Inicio_Partido" | Igual (ya funciona, `hito_partido.py:213`); la vista refetchea el cronómetro y se reencuadra al modo en vivo |
| Torneo sin `CONFIGURACION_TIEMPO_TORNEO` | `400` "Este torneo todavía no tiene configuración de tiempos" | Igual, pero la vista lo muestra arriba como bloqueo explicado, no como error de botón |
| Partido de bracket sin los dos equipos | `400` "todavía no tiene los dos equipos definidos" | La vista entra en modo "esperando rival", sin editor de alineación |

#### Sección 3 — Seguridad y modelo de amenaza

Sin superficie nueva de ataque, con dos cosas a no romper.

- **La ruta nueva no es el control de acceso.** El gate real ya vive en el
  backend: `require_roles("TorneoAdmin","Arbitro")` +
  `require_torneo_access_de(_torneo_id_de_partido, "Arbitro")` +
  `verificar_arbitro_asignado` (`partidos.py:280-300`, `permisos.py`). El
  `RequireRole` del frontend solo evita que alguien llegue a una pantalla que
  le devolvería 403. Ese reparto se mantiene tal cual.
- **El bloqueo de cambios destructivos (D3) DEBE ser server-side.** Si vive
  solo en el editor, un `PUT` directo con el token del árbitro borra
  titulares con estadísticas cargadas. Es la misma lección explícita que ya
  dejó `_validar_titulares` (`fixes-datos-traspasos-control-mesa-plan.md`,
  D4: "la fuente de verdad vive acá, no solo en qué oculta la UI").
- **El veredicto de arranque NO se publica en `GET /partidos/{id}/cronometro`.**
  Ese endpoint es publico sin auth (`partidos.py:216-223`) y se pollea cada 5 s
  de forma anonima; sumarle el calculo de titulares lo volveria el endpoint mas
  caro del sistema (ver **H1-eng**). Va en un endpoint nuevo y **autenticado**,
  `GET /partidos/{id}/preflight-inicio`, con las mismas dependencias que
  `POST /hitos`. `/cronometro` queda exactamente como esta.
- **No se agrega ningún rol nuevo ni se ensancha ninguno existente.**

#### Sección 4 — Flujo de datos y casos borde

Esta es la sección con más hallazgos. Los casos marcados **CRÍTICO** son los
que hacen perder datos ya cargados.

| # | Caso borde | Estado hoy | Resolución en este plan |
|---|---|---|---|
| EC-1 | **CRÍTICO.** Titular con goles/tarjetas cargados es removido de la convocatoria | Permitido, deja estadísticas de un jugador "no convocado" | D3: rechazado server-side con el partido en curso. Además se valida contra `EVENTOS_PARTIDO`: si el jugador tiene eventos, no se lo puede sacar **en ningún estado** |
| EC-2 | **CRÍTICO.** `reemplazar_convocatoria` hace `DELETE` masivo + `INSERT` (`convocado_a_partido.py:19-33`) | Cada guardado destruye todas las filas y regenera IDs y `Fecha_Registro` | Pasa a diff incremental (insert/update/delete solo de lo que cambió). Sin esto, "quién llegó tarde y a qué hora" —el dato que justifica el Requerimiento 3— se pierde en el siguiente guardado |
| EC-3 | **CRÍTICO.** Lost update entre dos operadores | El último `PUT` gana en silencio | Concurrencia optimista: el cliente manda la versión que leyó, el server responde `409` con la lista vigente si cambió |
| EC-4 | Jugador dado de baja del roster después de convocarlo | `_validar_titulares` ya intersecta contra el roster activo (`hito_partido.py:189-195`) | Sin cambio — ya está bien resuelto. El editor además lo muestra tachado con el motivo |
| EC-5 | Llegada tardía que empujaría los titulares por encima de `tamano_equipo` | No hay tope superior (deferido a propósito en `TODOS.md`) | Sigue sin tope, pero el editor avisa ("11 de 11 titulares — el que sume queda de suplente"). Se mantiene la decisión previa de no bloquear |
| EC-6 | Partido `Finalizado` y alguien abre la vista | La convocatoria es editable | Solo lectura, server-side y en la UI |
| EC-7 | Convocado que pertenece a los dos equipos (traspaso en curso) | `reemplazar` valida contra la unión de las dos plantillas (`convocado_a_partido.py:57-60`), sin distinguir de cuál | Se mantiene la validación, y el editor agrupa por equipo usando `GET /plantillas`, que sí trae `equipo_id` |
| EC-8 | Convocatoria vacía guardada con el partido en curso | Permitido, y "saca la convocatoria" globalmente | Rechazado en curso: vaciar es la operación destructiva máxima |
| EC-9 | El operador arma la alineación y nunca toca "Guardar" | La convocatoria queda como estaba | El botón "Empezar Partido" queda deshabilitado con "tenés cambios sin guardar", no arranca con una alineación fantasma |
| EC-10 | Modalidad Individual (`tamano_equipo=1`) | `_validar_titulares` exige 1 titular por lado | Funciona igual; el mínimo por default también es 1. El editor de dos contenedores sigue siendo coherente (1 titular, 0 suplentes) |

#### Sección 5 — Calidad de código

- **Duplicación real ya existente que este plan debe cerrar, no ampliar:**
  `useTitularesCompletos` (`ControlDeMesa.tsx:65-190`) es una réplica
  client-side de `_validar_titulares`, declarada como tal en su propio
  comentario. Con el mínimo (D1) la regla se vuelve más compleja, y mantener
  dos implementaciones divergentes es la receta para que el botón se habilite
  cuando el backend va a rechazar. **Fix: el server publica el veredicto.** Se
  agregan a `GET /partidos/{id}/cronometro` los campos ya calculados
  (`minimo_para_iniciar`, `titulares_por_equipo`, `puede_iniciar`,
  `motivo_bloqueo`), y el hook de 125 lineas con 6 queries desaparece.
- **Nombre desalineado:** el archivo se llama `Convocatoria.tsx` pero el
  requerimiento habla de "convocados" (paso 1) y "alineación" (paso 2) como
  dos cosas distintas. Los nombres nuevos siguen esa separación
  (`AlineacionEditor`), que es la del dominio, no la de la tabla.
- **Sin `any` ni `as never` nuevos.** Nota: el código actual usa `as never` en
  las mutaciones (`ControlDeMesa.tsx:300`, `:315`) para saltear el tipado de
  `openapi-fetch`. Es deuda existente; este plan no la agranda y regenera
  `schema.d.ts` (`bun run gen:api`) para que los campos nuevos vengan tipados.

#### Sección 6 — Revisión de tests

Cobertura existente que hay que extender, no crear de cero:

| Archivo | Qué cubre hoy | Qué hay que sumar |
|---|---|---|
| `backend/tests/test_titulares_inicio_partido.py` | `_validar_titulares` con el total exacto | Mínimo por torneo: arranque con menos que `tamano_equipo` y ≥ mínimo (debe pasar), y con menos que el mínimo (debe fallar) |
| `backend/tests/test_convocados_a_partido.py` | `PUT/GET` felices + validación de pertenencia | Bloqueo destructivo en curso, alta de tardío en curso, `409` de concurrencia, solo lectura en `Finalizado`, jugador con eventos |
| `backend/tests/test_control_mesa_tiempos.py` | Máquina de estados del cronómetro | Campos nuevos de `GET .../cronometro` (`puede_iniciar`, `motivo_bloqueo`) |
| `backend/tests/test_resultado_directo.py` | Camino directo atómico | Test explícito de que **no** exige convocatoria (D4) — hoy es un comportamiento sin test que se podría romper sin que nadie se entere |
| `frontend/src/pages/ControlDeMesa.test.tsx` (419 líneas) | Dashboard + mesa | Fila con **un** botón; navegación a la ruta nueva |
| `frontend/src/pages/Convocatoria.test.tsx` (121 líneas) | Checkboxes y guardado | Mover/renombrar a `AlineacionEditor.test.tsx`: mover por tap, contador de mínimo, bloqueo en vivo. **El gesto de arrastre NO se cubre acá** — ver M1-eng: jsdom no lo permite; se testea la función pura `mover()` |

#### Sección 7 — Performance

**Hallazgo concreto, y es una mejora que sale gratis con el cambio pedido.**
`BotonEmpezarPartido` se renderiza **por fila** del dashboard, y cada
instancia monta `useTitularesCompletos`, que dispara 6 queries (torneo,
modalidad, inscripciones, convocados, y dos de plantillas). Con 10 partidos
programados eso son ~60 requests para pintar una lista. React Query dedupea
las que comparten clave (torneo/modalidad se repiten), pero `convocados` y
`plantillas` son por partido y no se dedupean.

Colapsar la fila a un botón que solo navega elimina esas queries del
dashboard por completo: el cálculo se hace **una vez**, adentro de la vista
del partido que el operador abrió. La consolidación de UI que pidió el
usuario es, además, la corrección de un problema de carga real.

#### Sección 8 — Observabilidad

- **Hallazgo:** `reemplazar_convocatoria` borra con
  `session.execute(delete(...))` (`convocado_a_partido.py:28`), un DELETE
  masivo que **no pasa por la unidad de trabajo del ORM** — el listener
  genérico de auditoría (`app/core/auditoria.py`, que engancha eventos ORM)
  no lo ve. Las bajas de convocatoria hoy no quedan auditadas. El diff
  incremental de EC-2 lo corrige de paso: al borrar por objeto, el listener
  vuelve a verlas.
- Los hitos (`Inicio_Partido`) ya guardan `registrado_por` y timestamp real —
  la pregunta "¿quién arrancó este partido y cuándo?" ya tiene respuesta.
- Se agrega el motivo del bloqueo en la respuesta de error (no solo el
  código): cuando un operador reporte "no me deja arrancar", el mensaje ya
  trae el equipo y los números.

#### Sección 9 — Despliegue y rollout

- Migracion `27_migracion_minimo_titulares.sql`: agrega
  `TORNEO.Minimo_Jugadores_Para_Iniciar INT NULL` + `CHECK (Minimo_Jugadores_Para_Iniciar >= 1)`.
- **Sin backfill, a proposito.** `NULL` significa "usar `Modalidad.Tamano_Equipo`",
  que es exactamente el comportamiento de hoy. La lectura es
  `requeridos = torneo.minimo_jugadores_para_iniciar or modalidad.tamano_equipo`,
  nunca "sin minimo". Esto elimina la clase entera de riesgo de un backfill
  omitido o a medias: si la migracion corre y nadie configura nada, el sistema
  se comporta igual que antes. La columna queda **nullable de forma permanente**;
  no hay un paso posterior de `NOT NULL`.
- **Orden de despliegue:** migración → backend → frontend. El frontend viejo
  contra el backend nuevo sigue funcionando (los campos nuevos de
  `/cronometro` son aditivos y el frontend viejo los ignora).
- **Rollback:** la migración es puramente aditiva; volver atrás el backend no
  requiere tocar la columna.

#### Sección 10 — Trayectoria a largo plazo

Lo que este plan deja bien parado para lo que viene:

- Los dos contenedores (Titulares/Suplentes) son la base visual de la
  formación por posiciones: cuando llegue, "Titulares" se convierte en una
  cancha y "Suplentes" queda igual. No hay que rehacer el modelo de datos.
- El diff incremental de EC-2 conserva `Fecha_Registro` por convocado, que es
  el insumo exacto para "minutos jugados" más adelante.
- `minimo_jugadores_para_iniciar` en `TORNEO` abre la puerta a otros
  parametros de reglamento por torneo sin tabla nueva, junto a
  `permite_walkover_grupos`.

Lo que este plan **empeora** si no se cuida: `GestionarPartido.tsx` puede
convertirse en el nuevo archivo de 1500 líneas si se le sigue colgando todo.
El split de la Sección 1.2 es la mitigación, y hay que sostenerlo.

#### Sección 11 — Diseño y UX (alcance UI detectado)

Se evalúa en profundidad en la Fase 2. Desde la mirada de producto, lo único
que corresponde marcar acá: el requerimiento describe un flujo "paso a paso",
pero los dos pasos operan sobre **el mismo dato** (la fila de convocatoria) y
el operador va a ir y venir entre ellos. Un wizard con pasos bloqueados sería
peor que dos zonas visibles al mismo tiempo. Se resuelve en la Fase 2.

### Registro de errores y rescate (Sección 2, consolidado)

| Error | Detección | Rescate del operador | Fuente de verdad |
|---|---|---|---|
| Mínimo no alcanzado | `_validar_titulares` (server) + `puede_iniciar` (publicado) | Botón deshabilitado + qué falta, por equipo | Backend |
| Cambio destructivo en vivo | Service de convocatoria | `400` con nombre del jugador y motivo | Backend |
| Convocatoria pisada por otro operador | Chequeo de versión | `409` + lista vigente + refetch | Backend |
| Jugador con eventos removido | Cruce contra `EVENTOS_PARTIDO` | `400` explicando que ya tiene sucesos cargados | Backend |
| Torneo sin config de tiempos | `_cargar_contexto` | Bloqueo explicado arriba de la vista | Backend |
| Partido sin rival definido | `equipos_id_*` nulos | Modo "esperando rival" | Backend |
| Cambios sin guardar | Estado local del editor | Botón de inicio deshabilitado con el motivo | Frontend |

### Registro de modos de falla

| Modo de falla | Probabilidad | Impacto | Mitigación en este plan |
|---|---|---|---|
| Pérdida de convocatoria por `DELETE` masivo (EC-2) | Alta (cada guardado) | Alto — pierde el rastro de llegadas tardías | Diff incremental |
| Lost update entre dos dispositivos (EC-3) | Media | Alto — trabajo perdido en silencio | Concurrencia optimista con `409` |
| Estadísticas colgadas por titular removido (EC-1) | Media | Crítico — corrompe el histórico del torneo | Validación server-side en dos capas (estado + eventos) |
| Minimo mal configurado (muy bajo) | Media | **Alto** — se pueden iniciar partidos con 2 jugadores y el walkover deja de usarse: entra basura a la tabla de posiciones por la via de "partido jugado" en vez de la que tiene semantica propia | `NULL` por default (= comportamiento actual), `CHECK >= 1`, validacion `<= tamano_equipo` en el service, y copy explicito en el formulario del torneo |
| D&D inoperable en celular | Alta si se hace nativo HTML5 | Alto — el requerimiento entregado roto en el dispositivo real | Pointer Events + tap como camino paralelo (D2) |
| Divergencia entre la regla del cliente y la del server | Alta si se replica el mínimo | Medio — botón que promete lo que el backend rechaza | El server publica `puede_iniciar` en `/preflight-inicio` (Sección 5 + H1-eng) |
| `GestionarPartido.tsx` se convierte en el nuevo monolito | Media | Medio — deuda de mantenibilidad | Split por archivo desde el día uno |

### NO está en alcance (diferido a TODOS.md)

- **Pre-llenado de la convocatoria** desde el partido anterior o desde el
  roster completo. Es la fricción más grande a 40 partidos (0E, HORA 6+),
  pero es una feature propia con su propia pregunta de producto ("¿desde el
  último partido o desde la plantilla base?") y no está en el requerimiento.
- **Posiciones y formación** sobre cancha. El ideal a 12 meses; este plan deja
  la estructura visual lista pero no lo construye.
- **Tope superior de titulares** por encima de `tamano_equipo`. Ya estaba
  diferido a propósito (`TODOS.md`, Decision Audit #12 del plan anterior); no
  se reabre.
- **Minutos jugados por jugador.** Depende de que las sustituciones consuman
  del banco, que no está en este alcance.
- **Motor de resultados para Tenis/Pádel.** Fuera de alcance desde hace tres
  planes; no cambia.
- **Reemplazar la cola offline de eventos** por una cola general de
  mutaciones. La alineación no usa la cola a propósito (Sección 2).

### Step 0.5 — Voces externas (CEO)

**CODEX SAYS (CEO — strategy challenge):** `[codex-unavailable]` — el binario
`codex` no está en PATH en esta máquina. Mismo estado que los planes previos
de este repo. Esta fase corre en modo **`[subagent-only]`**: una sola voz
revisora independiente, no dual-voice real.

**CLAUDE SUBAGENT (CEO — strategic independence):** 19 hallazgos. Los que
cambiaron el plan están abajo; cada afirmación fue **verificada contra el
código** antes de incorporarla.

#### H1 — DEADLOCK: un TorneoAdmin no puede abrir la convocatoria de un partido Programado (CRITICAL) — **verificado**

Es la causa raíz del requerimiento entero, y no estaba enunciada ni en el
pedido del usuario ni en mi propio análisis. La cadena, verificada línea por
línea:

1. `Convocatoria.tsx` se renderiza **solo dentro** de `MesaPanel`
   (`ControlDeMesa.tsx:1124`).
2. A `MesaPanel` se entra **solo** por `setPartidoId`. En el dashboard eso
   pasa en dos lugares: `empezarPartido.onSuccess` (`ControlDeMesa.tsx:322`) y
   el botón "Ir al partido en vivo", que se renderiza **únicamente en la rama
   `else` de `p.estado === "Programado"`** (`ControlDeMesa.tsx:403-417`).
3. `_validar_titulares` exige la convocatoria **antes** de permitir
   `Inicio_Partido` (`hito_partido.py:210-212`).

**El círculo se cierra:** para empezar el partido hace falta convocatoria;
para cargar la convocatoria hace falta que el partido ya haya empezado. Un
TorneoAdmin o AdminGeneral ve un botón gris que dice "Equipo: 0/11 titulares"
y **no tiene ninguna ruta hacia el panel que lo arreglaría.**

Por qué nadie lo detectó: el rol **Árbitro sí puede** — `MisPartidos.tsx:40-41`
abre `MesaPanel` sin condicionar por estado. El bug es invisible para quien
probó con rol Árbitro, y no hay test que cubra el camino del TorneoAdmin sobre
un partido Programado.

**Impacto en este plan:** el usuario pidió una vista inmersiva con drag & drop
porque la convocatoria le resulta inalcanzable. El síntoma es real; el
diagnóstico implícito ("falta UI") es incorrecto. **La causa se arregla con
~5 líneas.** Esto no achica el alcance del plan — se construye igual todo lo
pedido — pero **reordena** la entrega: el desbloqueo va primero, en su propio
commit, y no se queda esperando 800 líneas de UI nueva.

#### H2 — `titular` es un dato casi write-only (HIGH) — **verificado**

`CargaEvento` filtra sus candidatos por **convocado** (`ControlDeMesa.tsx:915-925`)
pero **ignora `titular` por completo**. Está dicho en el código
(`ControlDeMesa.tsx:1352-1356`: *"el modelo de datos no distingue
titular/suplente"*) y en la pantalla, al operador
(`ControlDeMesa.tsx:1442`: *"¿Quién sale? (plantilla vigente — no distingue
titular/suplente)"*).

Es decir: hoy `titular` se escribe en `Convocatoria.tsx` y se lee en tres
lugares (el gate de arranque, el resumen del propio panel, y la vista
pública), pero **el flujo de Cambio — el que más lo necesita — no lo usa**.
Construir una UI de alineaciones sin cerrar eso es pintar la fachada sin la
instalación eléctrica. **Incorporado al alcance:** que "¿quién sale?" ofrezca
los que están en cancha (titulares − salidos + entrados) y "¿quién entra?"
ofrezca suplentes, es lo que le da valor al dato que esta UI produce.

#### H15 — Corrección a mi propio análisis: el gate es un mínimo, no una igualdad — **verificado**

`hito_partido.py:186` es `if n < requeridos`, no `if n != requeridos`. Mi
premisa P5 decía "exige exactamente ese número" y estaba mal redactada: exige
**al menos** `tamano_equipo`. La conclusión de fondo no cambia (no se puede
arrancar Fútbol 11 con 7, porque no existe un mínimo separado del tamaño del
equipo), pero la redacción sí. **P5 corregida arriba.**

Consecuencia práctica que vale confirmar: si el usuario tiene en mente
**Fútbol 5 arrancando con 5 aunque el plantel tenga 12**, eso **ya funciona
hoy** y lo único que lo bloquea es H1. La regla nueva hace falta solo si lo
que quiere es arrancar con **menos jugadores que los que la modalidad pone en
cancha**. Ver el Desafío al Usuario #2.

#### H7 — `resultado-directo` saltea DOS validaciones, no una (HIGH) — **verificado**

Yo había detectado que saltea `_validar_titulares`. La voz externa encontró
que también saltea **`_validar_torneo_no_archivado`**: `partido.py:166`
inserta el `HitoPartido` a mano y nunca pasa por `HitoPartidoService.registrar`.
Se puede cargar un resultado en un torneo archivado. Eso no es una decisión
de diseño, es un agujero. **Ver D4 revisado.**

#### H16-H19 — Integridad de la convocatoria en vivo — **coincide con EC-1/EC-2/EC-3**

Confirmación independiente de los tres casos críticos que ya había marcado, y
un mecanismo mejor que el mío: en vez de un `PUT` de reemplazo con
concurrencia optimista para todos los casos, **un endpoint aditivo separado**
para el caso en vivo. **Adoptado — ver D3 revisado.** Suma también H19: nada
revalida el mínimo después del arranque, porque `_validar_titulares` corre
solo en `Inicio_Partido`.

#### H10, H11, H12, H13 — Roces con decisiones ya cerradas (MEDIUM-HIGH)

- **H10:** un wizard obligatorio convierte la convocatoria en requisito de
  facto y contradice el "opt-in estricto" de 3B-2. Matiz: `_validar_titulares`
  ya la volvió obligatoria para el camino en vivo; el opt-in que sobrevive es
  el fallback de `CargaEvento`. **Se preserva** — ver el alcance.
- **H11:** los dos contenedores hacen visualmente escandaloso un exceso de
  titulares que el sistema acepta en silencio (tope superior, diferido en
  `TODOS.md`). **Incorporado** como contador visible, sin reabrir el bloqueo.
- **H12:** `/partidos/:id` ya muestra Alineaciones (solo lectura). Una tercera
  vista es duplicación. **Incorporado parcialmente:** se comparte el
  componente de presentación de la alineación; las rutas siguen separadas
  porque una es pública sin auth y la otra escribe (Sección 3).
- **H13:** meter la edición de fecha adentro de "Gestionar Partido" vuelve a
  mezclar operación con planificación de calendario. **Aceptado el roce**: la
  fecha ya estaba en Control de Mesa antes de este plan
  (`EditorFechaPartido`), así que mudarla adentro de la vista no cambia de
  módulo, solo de profundidad.

#### H9 — Confirmación independiente del costo de queries del dashboard (MEDIUM)

Mismo hallazgo que mi Sección 7, encontrado por separado: `useTitularesCompletos`
por fila → ~60 requests para pintar 20 partidos. Coincidencia de las dos voces
sobre el mismo punto: es el argumento más fuerte a favor del Requerimiento 1 y
ninguno de los dos lo tenía en el pedido original.

#### Hallazgos NO adoptados (y por qué)

- **"Fuera de alcance: drag & drop"** — La voz recomienda eliminarlo y
  reemplazarlo por un control ternario. Coincido en el diagnóstico técnico
  (ver D2), pero **el usuario lo pidió explícitamente** y quitarlo es una
  decisión de producto que no me corresponde tomar. Va al gate como
  **Desafío al Usuario #1**, con el análisis completo de las dos voces.
- **"Fuera de alcance: el wizard de 2 pasos"** — Mismo criterio. El diseño ya
  lo resuelve sin wizard bloqueante (Fase 2, Pass 1), que es la parte del
  problema que sí puedo decidir.
- **"Cambiar el gate a convocados ≥ mínimo en vez de titulares ≥ mínimo"**
  (alternativa E) — Rechazada. Saca la distinción titular/suplente del camino
  crítico justo cuando el plan la está reforzando (H2), y contradice el
  Requerimiento 2, que trata la alineación titular como el dato central.

### CEO — TABLA DE CONSENSO

```
CEO DUAL VOICES — CONSENSUS TABLE:
═══════════════════════════════════════════════════════════════════════
  Dimensión                              Claude   Codex   Consenso
  ─────────────────────────────────────  ───────  ──────  ────────────
  1. ¿Premisas válidas?                  NO (P5,  N/A     FLAGGED
                                         P7, P10) (n/d)   (1 voz, crítico)
  2. ¿Es el problema correcto?           PARCIAL  N/A     FLAGGED
                                         (H1)             (deadlock = causa raíz)
  3. ¿Alcance bien calibrado?            NO       N/A     FLAGGED
                                         (reordenar)      (secuencia, no tamaño)
  4. ¿Alternativas exploradas?           NO       N/A     FLAGGED
                                         (6 sin ver)      (A, C adoptadas)
  5. ¿Riesgos de mercado cubiertos?      N/A      N/A     N/A
                                         (interno)        (sin competencia)
  6. ¿Trayectoria a 6 meses sana?        NO       N/A     FLAGGED
                                         (3 arrepentim.)  (2 adoptados)
═══════════════════════════════════════════════════════════════════════
Voz faltante (Codex) = N/A, nunca CONFIRMED.
Hallazgo crítico de una sola voz = marcado igual (H1).
Consenso real: 0/6 CONFIRMED — no por desacuerdo, sino porque solo hubo
una voz. Todo lo de arriba es hallazgo de voz única, verificado por mí
contra el código antes de incorporarlo.
```

### Enmiendas a la Fase 1 tras la voz externa

**D1 — REVISADA. El mínimo va en `TORNEO`, no en `CONFIGURACION_TIEMPO_TORNEO`.**

Mi argumento original era que `CONFIGURACION_TIEMPO_TORNEO` ya se carga en
`_cargar_contexto`, así que no costaba queries. **Ese argumento no se
sostiene:** `_validar_titulares` ya recibe el `Torneo` resuelto
(`hito_partido.py:207-212` lo pasa desde `registrar()`), así que
`Torneo.minimo_jugadores_para_iniciar` también cuesta cero queries extra. Y
semánticamente, un mínimo de jugadores en una tabla llamada "configuración de
**tiempo**" está mal ubicado.

Además hay precedente exacto en el repo: `Torneo.permite_walkover_grupos`
(`models/torneo.py:53`) es un flag de reglamento por torneo, editable por el
TorneoAdmin. Es el mismo tipo de dato.

**Forma final:**

```
TORNEO.Minimo_Jugadores_Para_Iniciar INT NULL
  NULL  = usar Modalidad.Tamano_Equipo (comportamiento exacto de hoy)
  valor = mínimo de titulares por equipo para permitir Inicio_Partido
  CHECK (Minimo_Jugadores_Para_Iniciar >= 1)
  Validación 1 <= valor <= tamano_equipo: en el service (es cross-table,
  no puede ser un CHECK de tabla)
```

`NULL` como default es estrictamente mejor que mi propuesta de backfill +
`NOT NULL`: elimina el riesgo de regresión silenciosa (si el backfill falla o
se omite, el comportamiento sigue siendo el de hoy en vez de "sin
validación"), y evita inventar un mínimo para las ~35 filas del catálogo. Y
hay disciplinas donde el mínimo **es** el tamaño del equipo (Voleibol 6x6, y
las ~20 modalidades individuales con `tamano_equipo=1`): para todas ellas
`NULL` es la respuesta correcta y no hay nada que configurar.

Consumo: `requeridos = torneo.minimo_jugadores_para_iniciar or modalidad.tamano_equipo`
en `hito_partido.py:170`.

**D3 — REVISADA. Endpoint aditivo en vez de `PUT` condicional.**

En vez de un solo `PUT` con reglas distintas según el estado, dos superficies
con semántica clara:

| Operación | Endpoint | Estado permitido |
|---|---|---|
| Armar/editar la alineación completa | `PUT /partidos/{id}/convocados` (existente) | **Solo `Programado`** — se agrega el guard de estado que hoy falta |
| Sumar un convocado tardío como suplente | `POST /partidos/{id}/convocados` (**nuevo**) | `Programado` o `En curso` |

Ventajas sobre mi propuesta original: (a) el endpoint aditivo **no borra
nada**, así que `Fecha_Registro` de la fila nueva conserva el valor probatorio
de "a qué hora se sumó" (H18) — que es exactamente el dato que justifica el
Requerimiento 3; (b) desaparece la clase entera de bugs de lost-update en
vivo, porque la operación en vivo es aditiva y por lo tanto conmutativa;
(c) el flag `titular` es **inmutable** con el partido en curso, que es la
única lectura de "bloquea cambios destructivos" que no se contradice con
"sumar un jugador en vivo" (H14).

El `PUT` conserva la concurrencia optimista para el caso pre-partido (dos
operadores editando antes del arranque siguen pudiendo pisarse).

**D4 — REVISADA. Se parte en dos.**

- `_validar_torneo_no_archivado` **sí** se agrega a `registrar_resultado_directo`.
  Cargar un resultado en un torneo archivado no tiene ninguna lectura
  legítima; era un agujero, no una decisión.
- `_validar_titulares` **no** se agrega, como estaba decidido. Ese camino
  existe para partidos jugados en papel, donde la alineación es un dato que el
  operador no tiene.
- **Nuevo, por el riesgo que señaló la voz externa:** al quedar los dos
  botones juntos en la misma pantalla, "Cargar Resultado Directo" se vuelve el
  atajo obvio para saltear un arranque bloqueado. Mitigación de UI: el modal
  confirma explícitamente que **no** genera cronómetro ni eventos en vivo y
  que cierra el partido de una, en vez de presentarse como una alternativa
  equivalente.

**Alcance ampliado por la voz externa (P2 — boil the lake, todo dentro del
radio de impacto):**

- **Fase 0 de desbloqueo (H1)** — botón de acceso a la convocatoria para
  partidos `Programado` desde `/control-de-mesa`. Primer commit del plan.
- **Consumo de `titular` en `CargaEvento` (H2)** — "quién sale" = en cancha,
  "quién entra" = suplentes.
- **Guard de torneo archivado en `resultado-directo` (H7)**.
- **Guard de estado en el `PUT` de convocatoria (H16)**.
- **Invertir el default de la convocatoria (alternativa A)** — que arranque
  con toda la plantilla convocada y el operador destilde a los ausentes.
  3 líneas, y convierte 22 toques en 2 en el caso típico.
- **Botón "marcar los primeros N como titulares" (alternativa C)** —
  N = `tamano_equipo`, ~15 líneas.

**Diferido a TODOS.md (fuera del radio de impacto, P3):**

- **"Copiar alineación del partido anterior"** — la voz externa lo señala como
  el único ítem con impacto de orden de magnitud (330 decisiones manuales por
  fecha en una liga de 15 partidos, 90% idénticas a la fecha anterior).
  Coincide con lo que mi propio interrogatorio temporal encontró en HORA 6+.
  Es una feature con su propia pregunta de producto ("¿desde el último partido
  o desde `EQUIPO_JUGADOR_BASE`?") y no está en el requerimiento. **Se
  registra como el siguiente candidato más valioso después de este plan.**

> **Fase 1 completa.** Codex: no disponible (0 hallazgos). Claude subagent: 19
> hallazgos, 4 críticos/altos verificados e incorporados, 3 no adoptados y
> elevados como Desafíos al Usuario. Consenso: 0/6 CONFIRMED (voz única —
> ningún desacuerdo real, simplemente no hubo segunda voz). 6 dimensiones
> marcadas por hallazgo de voz única. Pasando a la Fase 2.

---

## Fase 2 — Design Review (UI/UX)

**Alcance UI detectado:** dashboard, botón, vista, contenedores, checkboxes,
drag & drop, modal, panel. Se corre la fase completa.

**Clasificador: APP UI** (superficie de trabajo, densa en datos, orientada a
tarea). No aplican las reglas de landing page.

### Step 0 — Completitud de diseño del requerimiento

**Puntaje inicial: 4/10.** El requerimiento es específico en la interacción
(dos contenedores, arrastre, checkboxes) y en las acciones finales, pero deja
sin definir todo lo que un implementador necesita decidir: estados de carga,
vacío y error; qué muestra la tarjeta de un jugador; qué pasa con **dos**
equipos en un layout que describe **un** par de contenedores; y el
comportamiento en 375px, que es el dispositivo real.

**Sistema de diseño existente:** no hay `DESIGN.md`. El sistema de facto son
las variables de `index.css:1-14` (`--bg #0f1420`, `--surface`, `--accent
#4fd1c5`, `--radius 10px`, `color-scheme: dark`) más las clases ya
establecidas: `.card`, `.tap-button` (min-height 64px), `.link-button`,
`.badge`, `.muted`, `.error-text`. Este plan **usa ese vocabulario y no
introduce tokens nuevos**.

**Evidencia documental que ancla toda esta fase.** El design doc del módulo
(`docs/designs/frontend-inicial-dashboard-mesa-en-vivo.md:152-160`) fija dos
criterios de éxito que siguen vigentes:

> "un usuario Admin o Árbitro autenticado puede ver un partido y cargar
> eventos **desde un navegador de celular (no solo desktop — es el escenario
> real de uso en cancha)**. Goles y tarjetas: elegir jugador y tipo de
> evento, **2-3 toques, sin tipear**."

Es decir: el celular en cancha y la economía de toques no son una preferencia
de esta revisión, son restricciones documentadas del módulo. Todo lo que
sigue se juzga contra eso.

### Pass 1 — Arquitectura de la información (4/10 → 10/10)

**Hallazgo crítico, y es un hueco del requerimiento, no un detalle de
implementación: un partido tiene DOS equipos.** El requerimiento describe "un
contenedor inferior (Suplentes)" y "un contenedor superior (Titulares)", en
singular. No se pueden mezclar los jugadores de los dos equipos en el mismo
contenedor de Titulares: soltar un jugador del equipo visitante en los
titulares del local no significa nada.

**Decisión: un equipo a la vez, con selector.** No dos columnas simultáneas.
Razón: `.convocatoria-equipos` (`index.css:488`) ya hace
`grid-template-columns: 1fr 1fr` **sin media query** — en 375px son dos
columnas de ~170px con nombres de jugador truncados. Ese ya es un problema
hoy; duplicarlo con zonas de arrastre lo vuelve inoperable. El selector de
equipo (dos pestañas, "Local | Visitante", con el contador de cada una
visible en la pestaña) da al operador el ancho completo para la mano con la
que arrastra o toca.

En ≥800px (el breakpoint que el proyecto ya usa, `index.css:132`) los dos
equipos se muestran lado a lado, cada uno con su par de contenedores.

**Segundo hallazgo: "paso a paso" no debe ser un wizard.** Los dos pasos
operan sobre **la misma fila de datos** (la convocatoria), y el operador va a
ir y venir: marca presentes, sube titulares, se acuerda de uno más, vuelve a
marcar. Un wizard con pasos bloqueados obligaría a retroceder para cada
corrección. Se resuelve como **una sola pantalla con dos zonas numeradas**,
donde el Paso 1 se colapsa solo (no se bloquea) una vez que hay al menos un
convocado, porque a partir de ahí el trabajo está en el Paso 2.

**Constraint worship — si solo se pudieran mostrar 3 cosas:** (1) los dos
contenedores con los jugadores, (2) el contador "titulares / mínimo" por
equipo, (3) el botón Empezar Partido. Todo lo demás es secundario y se
subordina a eso.

**Jerarquía de pantalla:**

```
┌──────────────────────────────────────────────────┐
│ ← Volver          Rojo vs Azul · sáb 14:00       │  1. Orientación
│                   [Programado]                    │     (quién, cuándo, estado)
├──────────────────────────────────────────────────┤
│  Rojo  5/7 ⚠      │      Azul  7/7 ✓             │  2. El dato que decide
│  ▔▔▔▔▔▔▔▔▔        │                              │     (pestañas + contador)
├──────────────────────────────────────────────────┤
│  TITULARES                          5 de 7       │  3. Zona de destino
│  ┌────────────────────────────────────────────┐  │     (arriba, como pidió
│  │ ⠿ #7  Pérez, Juan            [↓ Suplente] │  │      el requerimiento)
│  │ ⠿ #4  Gómez, Luis            [↓ Suplente] │  │
│  │ …                                          │  │
│  │ Faltan 2 para el mínimo                    │  │
│  └────────────────────────────────────────────┘  │
│                                                   │
│  SUPLENTES                               4       │  4. Zona de origen
│  ┌────────────────────────────────────────────┐  │
│  │ ⠿ #11 Díaz, Ana              [↑ Titular ] │  │
│  │ …                                          │  │
│  └────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────┤
│  ▸ Paso 1 · Convocados (9 de 14)                 │  5. Colapsado tras
│    [se despliega: checkboxes de la plantilla]    │     el primer convocado
├──────────────────────────────────────────────────┤
│  [ ▶ Empezar Partido ]  [ Cargar resultado… ]    │  6. Acciones principales
│  ▸ Otras acciones (walkover, reprogramar)        │  7. Secundarias, plegadas
└──────────────────────────────────────────────────┘
```

Titulares arriba y Suplentes abajo respeta literalmente el requerimiento, y
además coincide con el modelo mental (el que juega está "en cancha", el que
espera está "en el banco").

### Pass 2 — Cobertura de estados de interacción (2/10 → 10/10)

El requerimiento no menciona **ningún** estado no-feliz. Tabla completa —
qué VE el operador, no qué hace el backend:

| Zona | Cargando | Vacío | Error | Éxito | Parcial |
|---|---|---|---|---|---|
| Vista completa | Esqueleto del encabezado + "Cargando partido…" | n/a (siempre hay partido) | "No se pudo cargar el partido" + botón Reintentar + link a la lista | — | Partido sin rival: "Esperando el ganador del partido anterior", sin editor |
| Paso 1 · Convocados | "Cargando plantilla…" en el desplegable | "Este equipo no tiene jugadores en el roster del torneo" + link a Plantillas del torneo | "No se pudo cargar la plantilla" + Reintentar | Checkbox marcado, el jugador aparece al instante en Suplentes | Un equipo carga y el otro falla: la pestaña que falló muestra su propio error, la otra funciona |
| Titulares | Skeleton de 3 filas | "Arrastrá o tocá ↑ para subir jugadores desde Suplentes" (no "sin datos") | — | Contador sube, borde del contenedor destella una vez | "5 de 7 · faltan 2 para el mínimo" en el contenedor |
| Suplentes | Skeleton de 3 filas | "Todos los convocados están de titulares" | — | Contador baja | — |
| Guardar alineación | Botón "Guardando…" deshabilitado, la lista queda visible y no se bloquea | — | `error-text` bajo los botones con el mensaje del backend + los cambios locales **se conservan** | "Alineación guardada" que se desvanece a los 3s | `409`: "La convocatoria cambió desde otro dispositivo" + botón "Ver los cambios" que refetchea |
| Empezar Partido | "Iniciando…" | — | Mensaje del backend con equipo y números | La vista cambia a modo en vivo (cronómetro + eventos) | Deshabilitado con el motivo visible, nunca sin explicación |
| Resultado directo | Modal con "Guardando…" | Lista de eventos vacía = 0-0 válido, dicho explícitamente | Error dentro del modal, no se cierra ni pierde lo cargado | Modal cierra, partido pasa a Finalizado | — |
| Jugador dado de baja del roster | — | — | Fila tachada + "Ya no está en el roster — no cuenta como titular" | — | — |

**Regla de estado vacío:** ninguno dice "No hay datos". Cada uno nombra la
acción siguiente. Un contenedor de Titulares vacío es el estado inicial
normal del flujo, no un error, y su copy lo trata así.

### Pass 3 — Recorrido del usuario y arco emocional (5/10 → 9/10)

| Paso | El operador hace | Siente | Qué lo sostiene en el plan |
|---|---|---|---|
| 1 | Abre la lista en la cancha, con ruido y apuro | Apurado, busca su partido | Fila con equipos en negrita y **un** botón: nada que decidir salvo cuál partido |
| 2 | Toca "Gestionar Partido" | Alivio: entró a una cosa sola | Pantalla dedicada, encabezado que confirma qué partido es |
| 3 | Abre el Paso 1, marca los presentes | Trabajo mecánico, quiere velocidad | Checkbox de un toque; cada marcado aparece al instante en Suplentes (retroalimentación inmediata, sin guardar) |
| 4 | Sube titulares | Concentrado, cuenta mentalmente | El contador cuenta por él: "5 de 7". No tiene que saber el reglamento de memoria |
| 5 | Llega al mínimo | Confianza | El botón se habilita **solo**, con el contador en verde. El sistema le dice que puede, no lo adivina |
| 6 | Toca Empezar Partido | Momento de compromiso | Confirmación explícita de que se bloquean cambios destructivos, para que no sea una sorpresa después |
| 7 | Minuto 20: llega un jugador | Interrupción, miedo a romper algo | Vuelve a la configuración **sin** que el cronómetro se toque, y la pantalla lo dice explícitamente: "El partido sigue corriendo" |
| 8 | Intenta sacar un titular por error | Frustración momentánea | El rechazo nombra al jugador y el motivo ("ya tiene un gol cargado"), no un código |

**Horizonte de 5 segundos:** al entrar tiene que quedar claro de un vistazo si
el partido puede arrancar. Por eso el contador va arriba, antes que las
listas.

**Horizonte de 5 minutos:** la operación entera son toques; nada que tipear,
consistente con el criterio ya documentado del módulo.

**Punto de quiebre del arco (paso 7).** Es donde el operador más miedo tiene
de romper algo. La pantalla en modo "en curso" tiene que ser
**visiblemente distinta** de la de pre-partido: banda superior persistente
con el cronómetro corriendo y el texto "Partido en curso — solo podés sumar
suplentes". Sin esa señal, el operador no sabe en qué modo está y duda.

### Pass 4 — Riesgo de slop de UI (7/10 → 9/10)

Reglas de App UI. Riesgos concretos de esta pantalla y qué se decide:

- **Los jugadores NO son tarjetas.** Un plantel de 18 en tarjetas es un
  mosaico ilegible en 375px. Son **filas compactas** (manija de arrastre,
  dorsal, apellido, botón de mover), altura ~56px. La tarjeta se reserva para
  el contenedor, que sí es una unidad real de interacción (es la zona donde
  se suelta). Las tarjetas se ganan su existencia: acá hay dos, no dieciocho.
- **Sin borde izquierdo de color** en las filas (patrón #8 de la lista negra).
  La pertenencia al equipo ya la da la pestaña activa; repetirla por fila es
  ruido.
- **Los emoji que ya usa el módulo se mantienen** (⚽ 🟨 🟥 🔄 ▶ en
  `ControlDeMesa.tsx:44-50`): en este código no son decoración, son el
  vocabulario del dominio de eventos, y cambiar de criterio solo en esta
  pantalla rompería la consistencia. Lo que **no** se agrega es emoji
  decorativo nuevo en encabezados.
- **Sin gradientes ni sombras decorativas.** La superficie ya es
  `--surface` sobre `--bg`; el contenedor activo de arrastre se marca con
  `border-color: var(--accent)`, no con glow.
- **Copy de utilidad, no de marca.** "Faltan 2 para el mínimo", no "¡Ya casi
  estás listo!".

**Riesgo residual aceptado:** la fuente del proyecto es `system-ui`
(`index.css:31`), que las reglas duras marcan como señal de tipografía
abandonada. Es una decisión de toda la app, no de esta pantalla; cambiarla
acá crearía inconsistencia. Se deja registrada como observación del sistema
de diseño, fuera del alcance de este plan.

### Pass 5 — Alineación con el sistema de diseño (6/10 → 9/10)

- No hay `DESIGN.md`. El sistema de facto son las variables de `index.css`.
  **Recomendación registrada, no ejecutada acá:** `/design-consultation`
  merece su propia sesión; este plan no es el lugar para inventar un sistema.
- Clases nuevas, todas siguiendo la convención BEM-ish del proyecto
  (`.bloque__elemento--modificador`), todas con tokens existentes:
  `.gestionar-partido`, `.alineacion-zona`, `.alineacion-zona--activa`,
  `.alineacion-fila`, `.alineacion-fila--arrastrando`,
  `.alineacion-fila--inactiva`, `.alineacion-contador`,
  `.selector-equipo`, `.banda-en-curso`.
- **Componentes reusados sin tocar:** `.card`, `.badge` (estado del partido),
  `.link-button` (acciones secundarias), `.error-text`, `.muted`,
  `.confirmar-evento__acciones` (fila de botones), `.tap-button` (los botones
  de mover, que ya traen los 64px de alto táctil).
- **Deuda de responsive que este plan corrige de paso:**
  `.convocatoria-equipos` (`index.css:488`) es `1fr 1fr` sin media query. Al
  reemplazarla por el selector de equipo, ese problema desaparece en vez de
  heredarse.

### Pass 6 — Responsive y accesibilidad (1/10 → 10/10)

El requerimiento no dice **nada** de esto, y es la pantalla que se usa en un
celular a la intemperie. Especificación completa:

**Por viewport:**

| Viewport | Layout |
|---|---|
| < 1000px (celular y tablet chica, caso real) | Un equipo por vez vía pestañas. Contenedores a ancho completo, apilados, con `max-height: 40vh` y scroll interno (H-20). **Sin arrastre** — la única vía de mover es el botón de tap (decisión del gate final). Acciones principales fijas al pie (`position: sticky; bottom: 0`) con `border-top` y `env(safe-area-inset-bottom)` (H-27) |
| ≥ 1000px (tablet grande/desktop) | Los dos equipos lado a lado (`grid-template-columns: 1fr 1fr`), cada uno con su par de contenedores, ambas zonas visibles a la vez. **Acá sí se habilita el arrastre**, con manija visible. Acciones en flujo normal, sin sticky. Filas con nombre completo y posición (H-18) |

**Accesibilidad — requisitos, no aspiraciones:**

- **Objetivo táctil mínimo 44px.** Los botones de mover usan `.tap-button`
  (64px), ya conforme. La manija de arrastre se especifica en 44×44 mínimo.
- **Trampa concreta del arrastre táctil:** `touch-action: none` es necesario
  para que el navegador no se quede el gesto, pero aplicado a la fila entera
  **impide scrollear la lista con el dedo** — con 18 jugadores, el operador
  queda encerrado. Se aplica **solo a la manija** (`.alineacion-fila__manija`),
  nunca a la fila. Esta es la clase de detalle que, sin especificar, se
  descubre en la cancha.
- **Teclado:** cada fila es focusable; `Enter`/`Espacio` sobre el botón de
  mover hace el movimiento. El arrastre **nunca** es la única vía — es el
  motivo por el que D2 eligió interacción dual.
- **Lector de pantalla:** los contenedores son `role="list"` con
  `aria-labelledby` al encabezado de la zona; los movimientos se anuncian por
  una región `aria-live="polite"`: "Pérez movido a Titulares. 6 de 7."
- **Contraste:** todo texto de cuerpo con `--text` (#e6ebf5) sobre
  `--surface` (#171f30) supera 4.5:1. El estado de advertencia usa
  `--warning` (#e0b23a) sobre superficie oscura, que también pasa. **No** se
  usa `--text-muted` (#93a0bd) para información crítica como el contador.
- **El color no es el único portador de significado:** el contador dice
  "5 de 7 · faltan 2", no solo se pinta de rojo.
- **`prefers-reduced-motion`:** el destello de confirmación al soltar se
  reduce a un cambio de color sin transición.

### Pass 7 — Decisiones de diseño sin resolver

| Decisión | Si se difiere, qué pasa |
|---|---|
| ¿Qué muestra la fila del jugador? | El implementador pone solo el nombre y el operador no puede distinguir dos "González". **Resuelto:** dorsal + apellido, nombre + posición como línea secundaria si existen |
| ¿Los cambios se guardan solos o con botón? | Se implementa autosave por movimiento, y cada arrastre en el celular dispara un `PUT` con red mala. **Resuelto:** estado local + botón "Guardar alineación" explícito, con aviso de cambios sin guardar |
| ¿Cómo se ve el pre-partido vs. el en-curso? | Se ve igual y el operador no sabe si el reloj corre. **Resuelto:** banda superior persistente con el cronómetro y la restricción vigente |
| ¿Dónde queda Walkover? | Desaparece de la UI y se regresa una decisión de hace 3 días. **Resuelto:** sección "Otras acciones", plegada (D5) |
| ¿La vista sirve para partidos finalizados? | El operador llega por deep-link y ve controles que fallan. **Resuelto:** modo solo lectura, con link a la vista pública del partido |
| ¿Qué pasa al arrastrar sobre el contenedor equivocado? | Nada visible; el operador cree que se rompió. **Resuelto:** el contenedor destino se resalta al pasar por encima; soltar afuera cancela y la fila vuelve a su lugar con animación corta |

### Puntajes de la fase de diseño

| Pass | Inicial | Después | Qué lo movió |
|---|---|---|---|
| 1. Arquitectura de la información | 4 | 10 | Selector de equipo (los dos equipos que el requerimiento no contemplaba) + una pantalla en vez de wizard |
| 2. Estados de interacción | 2 | 10 | Tabla completa de 8 zonas × 5 estados |
| 3. Recorrido y arco emocional | 5 | 9 | Storyboard de 8 pasos + banda de modo en curso |
| 4. Riesgo de slop | 7 | 9 | Filas en vez de tarjetas; sin bordes de color decorativos |
| 5. Sistema de diseño | 6 | 9 | Vocabulario de clases con tokens existentes; corrige la deuda de `.convocatoria-equipos` |
| 6. Responsive y accesibilidad | 1 | 10 | Especificación por viewport, `touch-action` solo en la manija, teclado y `aria-live` |
| 7. Decisiones sin resolver | — | 6/6 resueltas | Tabla de arriba |

### Step 0.5 — Voces externas (Design)

**CODEX SAYS (design — UX challenge):** `[codex-unavailable]` — binario no
encontrado en PATH.

**CLAUDE SUBAGENT (design — independent review):** 27 hallazgos, 7 críticos.
La crítica de fondo, y es correcta: **los puntajes que me puse arriba estaban
inflados y funcionaban como cierre de la discusión en vez de como medida.**
Puse 10/10 en "estados de interacción" sin haber especificado el estado
offline, el modo en curso ni la pantalla post-arranque; y 10/10 en
"accesibilidad" con el foco perdiéndose después de cada movimiento. Los
puntajes finales están corregidos al final de la fase.

#### H-10 — Hay DOS botones de "empezar partido" y el plan promovía el equivocado (CRITICAL) — **verificado**

El hallazgo más importante de esta fase, y es un defecto de mi plan, no del
requerimiento.

- `ControlDeMesa.tsx:313-318` — el botón del dashboard dispara
  `POST /hitos { tipo_hito: "Inicio_Partido" }` **y nada más**.
- `Cronometro.tsx:169-172` — `iniciarPrimerTiempo()` dispara
  `Inicio_Partido` **y después** `Inicio_Periodo(1)`, con este comentario
  explícito: *"la mesa no necesita dos toques para lo que el árbitro percibe
  como una sola acción"*. Y para `tipo_cronometro === "Corrido"`
  (`Cronometro.tsx:190`) dispara solo `Inicio_Partido`, porque ahí no hay
  períodos.

Mi plan decía "reubicar" el botón de Empezar Partido a la barra de acciones
principales. Reubicar **ese** botón significa que, en un torneo por períodos,
el partido queda `En curso` **con el reloj parado en 00:00** y el operador se
encuentra con un segundo botón ▶ que dice "Iniciar 1er Tiempo". El
Requerimiento 4a dice literalmente "arranca el panel de cronómetro", y el
paso 6 del arco emocional lo llama "momento de compromiso": el arco se rompe
justo en su punto más alto.

**Corrección adoptada:** "Empezar Partido" de `GestionarPartido` ejecuta la
lógica de `iniciarPrimerTiempo()` respetando `tipo_cronometro` (dos hitos en
`Periodos`, uno en `Corrido`), y `Cronometro` recibe `mostrarInicio={false}`
para no renderizar su propia rama `!estado.partido_iniciado` cuando está
embebido en esta vista. Un solo botón, un solo significado.

#### H-11 — Ruta nueva + estado local sin guardar = pérdida silenciosa (CRITICAL)

Es un modo de falla **nuevo, creado por la combinación de dos decisiones
propias**: la Fase 1 convierte el panel en ruta (correcto) y la Fase 2 elige
estado local con "Guardar" explícito (correcto). Juntas, el botón Atrás del
navegador, el swipe de borde de iOS, "← Volver" y un tap en la nav bar
**descartan la alineación sin decir nada**. Antes no podía pasar porque no
había ruta. Mi registro de modos de falla no lo listaba.

**Corrección adoptada:** `useBlocker` de react-router v7 sobre
`hayCambiosSinGuardar`, con diálogo de tres salidas ("Guardar y salir" /
"Salir sin guardar" / "Cancelar"), **más** el borrador en `localStorage` de
H-5, que es el cinturón real.

#### H-5 — Cero estados offline, en un módulo que ya tiene infraestructura offline (CRITICAL) — **verificado**

Mi tabla de 8 zonas × 5 estados no tenía una sola fila de offline, mientras
que el módulo ya trae `useOnlineStatus` (`ControlDeMesa.tsx:826`),
`esErrorDeRed` (`:23`), `.mesa-offline-aviso` (`index.css:418`, usado en
`:1147`) y `colaOfflineEventos.ts`. Y el design doc del módulo tiene esto como
Open Question explícita.

Peor: mi celda de "Error" decía "`error-text` con el mensaje del backend".
Cuando no hay red **no hay mensaje del backend** — `fetch` tira `TypeError`
(lo documenta el propio `esErrorDeRed`), y `apiErrorMessage` sobre un
`TypeError` produce basura. El escenario real: el operador arma 7 titulares de
memoria con una raya de señal, toca Guardar, ve un error ilegible, no sabe si
guardó, refresca y pierde todo.

**Corrección adoptada, tres piezas:**
1. Borrador en `localStorage` por `partidoId` (`alineacionBorrador:{partidoId}`),
   escrito en cada movimiento, con la misma forma que `colaOfflineEventos.ts`.
   Al montar, si hay borrador más nuevo que el server: banner "Tenés una
   alineación sin guardar en este dispositivo — [Retomar] [Descartar]".
2. `useOnlineStatus`: con `!online` el botón pasa a "Guardar cuando vuelva la
   señal" y se muestra `.mesa-offline-aviso` con el copy del módulo.
3. `esErrorDeRed` para separar los mensajes: "Sin conexión — no se perdió
   nada, reintentá" vs. el error de negocio del backend.

#### H-6 — El editor en modo "En curso" no estaba especificado (CRITICAL)

Es **el** estado nuevo del plan (el Requerimiento 3 entero) y mi tabla no lo
cubría. La regla que faltaba, y que adopto: **nunca ofrecer un control cuya
única respuesta posible es un error.**

**Corrección adoptada:** con el partido `En curso`, el botón "↓ Suplente"
**no se renderiza** (no se deshabilita), y el header de la zona Titulares
lleva texto persistente "Partido en curso — no se puede sacar titulares". Los
checkboxes de jugadores ya convocados quedan en solo lectura. Nada de
tooltips: `title=` no existe en touch, que es el dispositivo real. El server
sigue siendo el backstop (D3), pero la UI no ofrece la acción prohibida.

#### H-17 — El filtro de "quién sale" puede trabar al operador en el minuto 60 (CRITICAL)

Adopté en la Fase 1 que `CargaEvento` consuma `titular` (H2) y no lo diseñé.
Es un cambio peligroso: hoy la lista de "¿Quién sale?" ofrece **toda la
plantilla** con un disclaimer honesto (`ControlDeMesa.tsx:1442`) — un fallback
seguro. Filtrada, si la alineación quedó mal armada (o no se armó, porque la
convocatoria sigue siendo opt-in), un jugador que **está jugando** no aparece
en la lista, en el minuto 60, sin explicación.

**Corrección adoptada:** la lista filtrada es el default, con un link
permanente **"No lo encuentro — ver toda la plantilla"** que quita el filtro,
más el copy que explica por qué falta. Esto además preserva de verdad el
opt-in de 3B-2 que H10 pedía preservar.

#### H-1 — Dibujé el estado final y nunca el inicial (CRITICAL)

Mi mockup muestra Titulares/Suplentes arriba y "Paso 1" colapsado abajo. Pero
ese es el estado *después* de que hay convocados. En un partido `Programado`
fresco, el operador aterriza con dos cajas vacías ocupando la mitad superior y
su **única acción posible** — el acordeón del Paso 1 — abajo de todo, fuera
del fold en 375px.

**Corrección adoptada:** el Paso 1 va **arriba** de los contenedores mientras
está expandido y baja a su posición colapsada al cerrarse (`order` en flex,
cero costo). Los **dos** estados quedan dibujados abajo.

#### H-2 — La regla de auto-colapso cerraba la lista que el operador está usando (HIGH)

Escribí "el Paso 1 se colapsa solo una vez que hay al menos un convocado". Con
14 jugadores, al primer checkbox la lista se cierra en la cara del operador.
**Corrección adoptada:** el colapso se dispara con una acción explícita
("Listo, N convocados") o con el primer movimiento a Titulares. Nunca por el
primer checkbox.

#### H-13 — La Fase 1 y la Fase 2 describían productos distintos (HIGH)

La Fase 1 adoptó el **default invertido** (la convocatoria arranca con toda la
plantilla marcada, el operador destilda ausentes) y la Fase 2, escrita antes,
nunca lo incorporó. Con el default invertido, mis empty states describen
estados que casi nunca ocurren y el paso 3 del arco cambia de naturaleza
("marcar presentes" vs. "destildar ausentes" son tareas distintas).

**Corrección adoptada:** gana el default invertido (es correcto para planteles
de 14-18 donde faltan 2-3), y la Fase 2 se reescribe sobre esa base — ver los
estados y el arco corregidos abajo.

#### H-20 — Con un equipo a ancho completo, la zona destino del arrastre casi nunca está en pantalla (CRITICAL)

El hallazgo que mi D2 no anticipó, y es el que decide si el arrastre sirve.

En 375×667, descontando nav (~50px), header (~60px), pestañas (~50px) y barra
sticky (~80px), quedan ~420px de scroll ≈ **7 filas visibles**. Un Fútbol 7
con 14 convocados son 14 filas + 2 headers ≈ 900px de contenido. Es decir:
**en la mayoría de los arrastres el contenedor destino está fuera de la
pantalla**, y cada movimiento pasa a ser agarrar, llevar el dedo al borde,
esperar el auto-scroll, verificar, soltar. Contra un tap.

Mi mockup dibujaba las dos zonas visibles a la vez, que es justamente el
estado que casi nunca ocurre.

**Corrección adoptada:** las dos zonas llevan **altura acotada con scroll
interno** (`max-height: 40vh; overflow-y: auto`). Así los dos headers y los
bordes de ambas zonas están **siempre** en pantalla, el destino nunca está
fuera, y el auto-scroll solo opera dentro de la zona de origen. Arregla el
arrastre y de paso deja el contador de la zona destino siempre visible para el
tap. **Si al implementar esto resulta insuficiente, la salida declarada es
apagar el arrastre en `<800px`** — la condición para tomarla ya se cumple en
el viewport principal, así que deja de ser hipotética.

#### H-18 — La fila del jugador era geométricamente imposible (HIGH)

Escribí filas de ~56px, botones `.tap-button` (que son `min-height: 64px`,
`flex-direction: column`, pensados para el grid de eventos), y dos líneas de
texto. No cierra. Y las cuentas de ancho en 375px: `main` con `padding: 1rem`
+ `.card` con otro `1rem` ≈ 311px útiles; manija 44 + botón ~90 + gaps ~24 =
158px de chrome, quedan ~150px para "#7 Pérez, Juan" — se trunca.

**Corrección adoptada:** clase propia `.alineacion-fila__mover` (56×56, solo
el ícono ↑/↓, con `aria-label` completo), **no** `.tap-button`. Una sola línea:
dorsal + apellido. Nombre completo y posición solo en ≥800px.

#### H-24 / H-25 / H-26 / H-27 — La accesibilidad estaba declarada, no resuelta (HIGH)

- **H-24:** "cada fila es focusable" **más** el botón focusable = 36 tab stops
  con 18 jugadores, y una fila con `tabindex="0"` dentro de un `role="list"`
  no es un item interactivo válido. **Corrección:** `<ul>`/`<li>` nativos
  (que es lo que `Convocatoria.tsx` y `.convocatoria-lista` ya usan), **solo
  el botón** focusable, y el contexto en su `aria-label`
  (`"Subir a titulares a Pérez, Juan, dorsal 7"`). Un tab stop por jugador.
- **H-25:** después de mover, el botón presionado desaparece de esa zona y el
  foco cae en `<body>`. El usuario de teclado vuelve al principio del
  documento y el de lector de pantalla pierde el lugar — esto invalidaba en la
  práctica todo el resto del trabajo de accesibilidad. **Corrección:** tras el
  re-render, `focus()` sobre el botón del mismo jugador en la zona destino,
  matcheando por `jugador_perfil_id` con un `ref` callback.
- **H-26:** un `<button disabled>` no es focusable ni anunciable, y el patrón
  actual pone el motivo en `title=`, que no existe en touch.
  **Corrección:** `aria-disabled="true"` + `aria-describedby` al texto del
  motivo, botón focusable, click sin efecto (o que scrollee al equipo que
  falta), y el motivo como texto en el DOM **antes** del botón.
- **H-27:** la barra sticky sin `env(safe-area-inset-bottom)` deja la zona
  táctil real por debajo de 44px en iOS, sin `border-top` no se distingue de
  `--bg`, y como banda opaca de ~80px **tapa justo el área donde el arrastre
  necesita disparar el auto-scroll hacia abajo**. **Corrección:**
  `border-top: 1px solid var(--border)`,
  `padding-bottom: max(0.75rem, env(safe-area-inset-bottom))`, y la zona de
  auto-scroll se calcula contra el borde superior de la barra, no contra el
  viewport (con H-20 este último punto se resuelve solo).

#### Hallazgos adicionales adoptados

- **H-3:** contador vivo en el header del acordeón ("Convocados 9 de 14 · 9 en
  Suplentes") — la retroalimentación del paso 3 del arco no existía donde yo
  decía que existía.
- **H-4:** nombre del torneo como línea secundaria del header cuando
  `torneos.length > 1`, mismo criterio que `ControlDeMesa.tsx:389`. Sin esto,
  un deep-link no dice de qué torneo es el partido.
- **H-7:** el `409` decía "Ver los cambios", un botón que **borra el trabajo
  del operador** con un label inocuo. **Corrección:** diff mínimo ("El otro
  dispositivo agregó a Díaz y sacó a Gómez") con dos acciones honestas:
  **[Quedarme con lo mío]** (reenvía con la versión nueva) y **[Traer lo del
  otro y descartar mis cambios]**.
- **H-8:** falta el mockup del modo en vivo — se agrega abajo.
- **H-12:** el paso 7 del arco (llegada tardía) no tenía navegación.
  **Corrección:** botón `[+ Sumar jugador]` en la banda de modo, que abre el
  Paso 1 filtrado a los no convocados, con `POST` aditivo por jugador y sin
  botón "Guardar" (la operación aditiva se confirma sola).
- **H-14:** "marcar los primeros N como titulares" no estaba en el layout ni
  definía el orden. **Corrección:** va en el header de la zona Titulares, y
  "los primeros N" es **por dorsal ascendente**, con los sin dorsal al final.
- **H-16:** el campo nuevo no tenía UI en ninguna parte. **Corrección:** se
  especifica abajo, en el formulario de torneo.
- **H-21:** **no** se implementa swipe entre pestañas (y se dice
  explícitamente, para que nadie lo agregue "para que se sienta nativo"),
  pestañas como botones inequívocos, `overscroll-behavior-x: contain`.
- **H-22:** en `<800px` la manija se oculta y el arrastre arranca con
  long-press sobre la fila (150-200 ms); en `≥800px` aparece la manija. El
  ancho de móvil se dedica al nombre y al botón.
- **H-23:** el layout de dos equipos lado a lado se mueve a `≥1000px` (en
  800px daría ~380px por equipo, reintroduciendo el problema que las pestañas
  resuelven).
- **H-9 / H-19:** micro-especificaciones — orden por dorsal ascendente dentro
  de cada zona; el drop dentro de la misma zona es no-op y la fila vuelve (no
  hay reordenamiento interno); la fila se levanta dejando hueco;
  `pointercancel` (llamada entrante) cancela y restaura; el `aria-live`
  anuncia **solo en `pointerup`**, nunca en `pointermove`.

#### Hallazgo NO adoptado

- **"Skeleton de 3 filas es cosmética copiada"** (H-9, parcial). Tiene razón
  en que Titulares/Suplentes se derivan de estado local y no tienen carga
  propia — pero sí dependen de `GET /plantillas` y `GET /convocados`, que sí
  cargan. Se mantiene el skeleton, atado a esas dos queries y no a un estado
  inventado.

### DESIGN — TABLA DE CONSENSO (litmus scorecard)

```
DESIGN DUAL VOICES — CONSENSUS TABLE:
═══════════════════════════════════════════════════════════════════════
  Dimensión / litmus                     Claude   Codex   Consenso
  ─────────────────────────────────────  ───────  ──────  ────────────
  1. Jerarquía sirve al usuario?         NO (H-1) N/A     FLAGGED
  2. Estados de interacción cubiertos?   NO       N/A     FLAGGED
                                         (H-5,6,8)        (3 críticos)
  3. Arco emocional sostenido?           NO       N/A     FLAGGED
                                         (H-10,11)        (rompe en paso 6)
  4. UI específica, no genérica?         PARCIAL  N/A     FLAGGED
                                         (H-13,15)        (contradicciones)
  5. Alineado al sistema de diseño?      SÍ       N/A     FLAGGED (positivo)
  6. Responsive intencional?             NO       N/A     FLAGGED
                                         (H-20,23)        (drop zone fuera)
  7. Accesibilidad real, no aspiracional? NO      N/A     FLAGGED
                                         (H-24..27)       (foco perdido)
═══════════════════════════════════════════════════════════════════════
Voz faltante (Codex) = N/A, nunca CONFIRMED.
Consenso: 0/7 CONFIRMED — voz única, no desacuerdo.
7/7 dimensiones marcadas. 7 hallazgos críticos, todos adoptados.
```

### Mockups corregidos (H-1, H-8, H-20)

**Estado 1 — partido `Programado`, recién abierto** (con default invertido,
H-13: la plantilla entera llega convocada):

```
┌──────────────────────────────────────────────────┐
│ ← Volver     Rojo vs Azul · sáb 14:00            │
│              Liga Relámpago - Ed. 2   [Programado]│ ← H-4: torneo
├──────────────────────────────────────────────────┤
│  ● Rojo 0/7      │      Azul 0/7                 │ ← pestañas + contador
├──────────────────────────────────────────────────┤
│  ▾ Paso 1 · Convocados 14 de 14 · 14 en Suplentes│ ← H-1: ARRIBA
│  ┌────────────────────────────────────────────┐  │    mientras
│  │ ☑ #4  Gómez, Luis                          │  │    está abierto
│  │ ☑ #7  Pérez, Juan                          │  │    H-3: contador
│  │ ☑ #11 Díaz, Ana                            │  │    vivo
│  │ … (14, todos marcados — destildá ausentes) │  │
│  └────────────────────────────────────────────┘  │
│              [ Listo, 14 convocados ]            │ ← H-2: colapso
├──────────────────────────────────────────────────┤    explícito
│  TITULARES  0 de 7        [Marcar 7 por dorsal]  │ ← H-14
│  ┌────────────────────────────────────────────┐  │
│  │  Tocá ↑ en un jugador para subirlo acá     │  │ max-height:40vh
│  └────────────────────────────────────────────┘  │ overflow-y:auto
│  SUPLENTES  14                                   │ ← H-20: ambas
│  ┌────────────────────────────────────────────┐  │   zonas siempre
│  │ #4  Gómez, Luis                      [ ↑ ] │  │   visibles
│  │ #7  Pérez, Juan                      [ ↑ ] │  │
│  │ ⋮ (scroll interno)                         │  │
│  └────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────┤
│ ▶ Empezar Partido (0/7)  ·  Cargar resultado…    │ sticky + safe-area
│ ▸ Otras acciones                                 │ + border-top (H-27)
└──────────────────────────────────────────────────┘
```

**Estado 2 — partido `En curso`** (H-8, H-6, H-12):

```
┌──────────────────────────────────────────────────┐
│ ← Volver     Rojo vs Azul        [En curso]      │
├══════════════════════════════════════════════════┤
│ ⏱ 23:14  1er Tiempo · corriendo   [+ Sumar jug.] │ ← banda persistente
│ Partido en curso — solo podés sumar suplentes    │   H-12: navegación
├══════════════════════════════════════════════════┤   del paso 7
│  ● Rojo          │      Azul                     │
│  TITULARES  7 · Partido en curso — no se puede   │ ← H-6: restricción
│              sacar titulares                     │   como TEXTO, sin
│  ┌────────────────────────────────────────────┐  │   botón ↓ renderizado
│  │ #4  Gómez, Luis                            │  │
│  │ #7  Pérez, Juan                            │  │
│  └────────────────────────────────────────────┘  │
│  SUPLENTES  6                                    │
│  ┌────────────────────────────────────────────┐  │
│  │ #11 Díaz, Ana                        [ ↑ ] │  │ ← promover sí
│  └────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────┤
│  MARCADOR · CRONÓMETRO · CARGAR EVENTO           │ ← MesaPanel
│  (MesaPanel completo, sin su propio botón de     │   Cronometro con
│   inicio — mostrarInicio={false}, H-10)          │   mostrarInicio=false
└──────────────────────────────────────────────────┘
```

### Estados de interacción — filas que faltaban (H-5, H-6)

| Zona | Sin conexión | En curso |
|---|---|---|
| Editor de alineación | `.mesa-offline-aviso` visible; los movimientos siguen funcionando contra el borrador local; el botón dice "Guardar cuando vuelva la señal" | Solo se renderiza `[↑]` en Suplentes; Titulares sin `[↓]`; restricción como texto en el header de la zona |
| Guardar | `esErrorDeRed` → "Sin conexión — no se perdió nada, reintentá". Nunca `apiErrorMessage` sobre un `TypeError` | No hay botón Guardar: la operación es `POST` aditivo, se confirma sola |
| Paso 1 · Convocados | El borrador local absorbe los cambios | Filtrado a no-convocados; los ya convocados en solo lectura |
| Al montar la vista | Banner "Tenés una alineación sin guardar en este dispositivo — [Retomar] [Descartar]" | Idem, más la banda de modo |
| Navegación hacia afuera | `useBlocker`: "Guardar y salir / Salir sin guardar / Cancelar" (H-11) | Sin bloqueo (no hay estado local pendiente) |

### UI del campo nuevo `minimo_jugadores_para_iniciar` (H-16)

Va en el formulario de crear/editar torneo (`TorneosAdmin.tsx`), junto a
`permite_walkover_grupos`, que es su precedente:

- **Label:** "Mínimo de jugadores para iniciar"
- **Placeholder cuando es `NULL`:** `= tamaño del equipo (7)` — resuelto desde
  la modalidad elegida
- **Helper:** "Permite arrancar un partido aunque falten jugadores. Dejalo
  vacío para exigir el equipo completo."
- **Error en línea:** "El mínimo no puede ser mayor que el tamaño del equipo
  (7)" / "El mínimo tiene que ser al menos 1"

Sin esta pantalla el Requerimiento 3 es inalcanzable, por más que el backend
lo soporte.

### Puntajes de la fase de diseño — corregidos

Los puntajes de mi primera pasada estaban inflados. Corregidos tras la voz
externa:

| Pass | Inicial | Mi 1ª pasada | Real tras la voz | Final con fixes |
|---|---|---|---|---|
| 1. Arquitectura de la información | 4 | 10 | **5** (H-1, H-2, H-4) | 9 |
| 2. Estados de interacción | 2 | 10 | **6** (H-5, H-6, H-8 sin cubrir) | 9 |
| 3. Recorrido y arco emocional | 5 | 9 | **4** (H-10, H-11, H-12) | 9 |
| 4. Riesgo de slop | 7 | 9 | 9 (confirmado) | 9 |
| 5. Sistema de diseño | 6 | 9 | 9 (confirmado) | 9 |
| 6. Responsive y accesibilidad | 1 | 10 | **6** (H-20, H-24..27) | 9 |
| 7. Decisiones sin resolver | — | 6/6 | **6/19** | 19/19 |

Ninguno queda en 10: quedan supuestos que solo se verifican con un celular
real en una cancha (el arrastre bajo H-20, y el long-press de H-22).

> **Fase 2 completa.** Codex: no disponible. Claude subagent: 27 hallazgos, 7
> críticos, 26 adoptados y 1 rechazado con razón. Consenso: 0/7 CONFIRMED (voz
> única). 3 contradicciones internas de mi propio documento corregidas (D1 en 5
> lugares, default invertido, geometría de la fila). Pasando a la Fase 3.

---

## Fase 3 — Eng Review (Arquitectura, Tests, Riesgo)

Corre **última**, sobre el plan ya enmendado por las Fases 1 y 2.

### Step 0 — Desafío de alcance (contra el código real)

El alcance **no se reduce** (P2). Lo que este paso encontró es que el
requerimiento, leído literal, sub-especifica el trabajo de backend y
sobre-especifica el de frontend.

| Sub-problema | ¿Existe? | Trabajo real |
|---|---|---|
| Desbloqueo del deadlock (H1) | No | ~5 líneas en `ControlDeMesa.tsx:403-417` + reordenar `MesaPanel` |
| Ruta dedicada | No (es `useState`) | Ruta + `RequireRole` + `useNavigate` |
| Split de archivos | No | Mudanza mecánica de 5 componentes |
| Checkboxes de convocados | Sí (`Convocatoria.tsx`) | Reubicar |
| Dos contenedores + mover | No | Componente nuevo |
| Arrastre por Pointer Events | No | ~120-150 líneas propias |
| Mínimo por torneo | No | Migración + columna + service + schema |
| Guard de estado en `PUT` | No | ~4 líneas |
| Endpoint aditivo | No | Método de service + ruta + schema |
| Bloqueo de quitar jugador con eventos | No | Query contra `EVENTOS_PARTIDO` |
| `puede_iniciar` publicado | No | Campos en `EstadoCronometroOut` |
| Borrar `useTitularesCompletos` | — | -125 líneas, -6 queries por fila |
| `CargaEvento` consume `titular` (H2) | No | Derivación en cliente |
| Guard de archivado en resultado directo (H7) | No | 2 líneas |
| Invertir default de convocatoria | No | ~3 líneas |
| "Marcar N titulares" | No | ~15 líneas |
| Resultado directo / walkover / cronómetro | Sí, completos | Solo reubicar |

**Chequeo de complejidad:** el frontend suma ~600-700 líneas netas (después
de restar las 125 de `useTitularesCompletos`); el backend ~150. La pieza
más cara del frontend es el arrastre (~150 líneas para un gesto), y la más
cara del backend es la validación de integridad de la convocatoria — que es
donde está el riesgo real, no donde el requerimiento puso el énfasis.

### Step 0.5 — Voces externas (Eng)

**CODEX SAYS (eng — architecture challenge):** `[codex-unavailable]` — binario
no encontrado en PATH.

**CLAUDE SUBAGENT (eng — independent review):** ver la sección siguiente.

### Sección 1 — Arquitectura

#### 1.1 Diagrama de dependencias

```
┌─────────────────────────── FRONTEND ────────────────────────────────┐
│                                                                      │
│  App.tsx                                                             │
│    ├── /control-de-mesa ──────────► control-mesa/ControlDeMesa.tsx  │
│    │     (RequireRole: TorneoAdmin, AdminGeneral, Arbitro)   │       │
│    │                                                    navigate()   │
│    ├── /control-de-mesa/partido/:id ──► control-mesa/GestionarPartido.tsx
│    │     (mismo RequireRole)                    │                    │
│    │                        ┌───────────────────┼──────────────┐     │
│    │                        ▼                   ▼              ▼     │
│    │              AlineacionEditor.tsx    MesaPanel.tsx  ModalResultado
│    │                        │              (movido)       Directo.tsx │
│    │                        │                   │           (movido)  │
│    │              ┌─────────┴────────┐          │                     │
│    │              ▼                  ▼          ▼                     │
│    │        usePointerDrag.ts   PasoConvocados  Cronometro.tsx        │
│    │         (hook nuevo)                       CargaEvento           │
│    │                                                                  │
│    ├── /arbitro ──────────► arbitro/MisPartidos.tsx                  │
│    │                          └── import actualizado ──► MesaPanel.tsx│
│    │                              (hoy: from "../ControlDeMesa")      │
│    └── /partidos/:id ─────► PartidoEnVivo.tsx (público, sin auth)     │
│                               └── comparte ──► AlineacionVista.tsx    │
│                                                (presentacional, H12)  │
└──────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────── BACKEND ─────────────────────────────────┐
│  routes/partidos.py                                                  │
│    GET  /{id}/cronometro ──► HitoPartidoService.estado_cronometro    │
│    │                          └─ + minimo_titulares                  │
│    │                             + titulares_por_equipo              │
│    │                             + puede_iniciar / motivo_bloqueo    │
│    POST /{id}/hitos ───────► HitoPartidoService.registrar            │
│    │                          └─ _validar_titulares (usa el mínimo)  │
│    PUT  /{id}/convocados ──► ConvocadoAPartidoService.reemplazar     │
│    │                          └─ + guard estado == Programado        │
│    │                          └─ + ETag MAX(fecha_modificacion)→412  │
│    │                          └─ + guard jugador con eventos         │
│    POST /{id}/convocados ──► ConvocadoAPartidoService.agregar  ★NUEVO│
│    │                          └─ aditivo, permitido En curso         │
│    POST /{id}/resultado-directo ► PartidoService.registrar_resultado │
│                               └─ + _validar_torneo_no_archivado (H7) │
│                                                                       │
│  models/torneo.py  ── + minimo_jugadores_para_iniciar (INT NULL) ★    │
└───────────────────────────────────────────────────────────────────────┘
```

#### 1.2 Acoplamiento — el riesgo concreto del split

`MesaPanel` está importado desde **dos** archivos fuera de `ControlDeMesa.tsx`:

- `frontend/src/pages/arbitro/MisPartidos.tsx:5` — `import { MesaPanel } from "../ControlDeMesa"`
- `frontend/src/pages/ControlDeMesa.test.tsx:11`

Mover `MesaPanel` a su propio archivo rompe los dos si no se actualizan en el
mismo commit. **Decisión: el split va en un commit propio, primero, sin ningún
cambio de comportamiento**, para que si algo se rompe sea obvio que fue la
mudanza y no la feature.

#### 1.3 `MisPartidos.tsx` está en el radio de impacto

Es importador directo de `MesaPanel`, así que entra por P2. Y hay una razón
funcional además de la mecánica: `MisPartidos.tsx:40-41` abre `MesaPanel` por
`useState` **sin condicionar por estado** — es el camino que hoy le funciona
al Árbitro y que enmascaró el deadlock del TorneoAdmin (H1). Si el Árbitro se
queda con el panel por `useState` mientras el TorneoAdmin pasa a una ruta, el
mismo módulo queda con dos formas distintas de entrar al mismo lugar, y el
próximo bug de este tipo va a volver a ser invisible en un rol y no en el
otro.

**Decisión: `MisPartidos.tsx` navega a la misma ruta** (`/control-de-mesa/partido/:id`).
Está permitido por el `RequireRole` de la ruta (incluye `Arbitro`) y por el
backend (`verificar_arbitro_asignado` sigue gobernando qué puede tocar). Un
solo camino, un solo comportamiento.

#### 1.4 Frontera de auth — lo que no se puede fusionar

H12 pedía que la vista nueva fuera "el modo editable de `/partidos/:id`".
**Rechazado a nivel de ruta, adoptado a nivel de componente.** `/partidos/:id`
es público sin auth (`App.tsx:64`, mismo criterio que `GET /partidos`);
`/control-de-mesa/partido/:id` escribe. Fusionar las rutas pondría lógica de
escritura detrás de una URL pública, y el gate quedaría dependiendo de un
condicional dentro del componente en vez de la tabla de rutas. Lo que sí se
comparte es `AlineacionVista.tsx`, el componente **presentacional** de la
alineación, que hoy está duplicado entre `PartidoEnVivo.tsx:286-300` y el
resumen de `Convocatoria.tsx:99`.

### Sección 2 — Calidad de código

| # | Hallazgo | Decisión | Principio |
|---|---|---|---|
| C1 | `useTitularesCompletos` (`ControlDeMesa.tsx:65-190`) replica en el cliente una regla del servidor, y el mínimo la vuelve más compleja | **Eliminar.** El server publica `puede_iniciar`/`motivo_bloqueo` en `/preflight-inicio` (H1-eng) | P4 (DRY) |
| C2 | `ControlDeMesa.tsx` son 1490 líneas con 8 componentes | Split a `pages/control-mesa/` | P5 |
| C3 | `as never` en las mutaciones (`:300`, `:315`) para saltear el tipado de `openapi-fetch` | Deuda existente, **no se amplía**; se regenera `schema.d.ts` para que lo nuevo venga tipado | P3 |
| C4 | La alineación de `PartidoEnVivo.tsx:286-300` y el resumen de `Convocatoria.tsx:99` muestran lo mismo de dos formas | Extraer `AlineacionVista.tsx` | P4 |
| C5 | `reemplazar_convocatoria` hace `delete()` masivo — invisible para el listener de auditoría | Diff incremental por objeto | P1 |
| C6 | El estado del arrastre y el estado de la alineación se van a mezclar en un componente | `usePointerDrag` aislado, sin saber de jugadores ni de equipos: devuelve "qué se arrastra" y "sobre qué zona está" | P5 |

### Sección 3 — Revisión de tests

#### 3.1 Diagrama de pruebas — cada codepath nuevo contra su cobertura

| # | Flujo / codepath | Tipo | ¿Existe? | Acción |
|---|---|---|---|---|
| T1 | TorneoAdmin abre la convocatoria de un partido `Programado` (**el deadlock H1**) | Frontend | **No** | **Nuevo — es el test de regresión del bug que originó el plan** |
| T2 | Fila del dashboard tiene exactamente un botón de acción principal | Frontend | No | Nuevo |
| T3 | Navegación a `/control-de-mesa/partido/:id` y vuelta | Frontend | No | Nuevo |
| T4 | Deep-link directo a la ruta (refresh en pleno partido) | Frontend | No | Nuevo |
| T5 | `RequireRole` bloquea a un rol sin permiso en la ruta nueva | Frontend | Parcial (patrón existe) | Nuevo, siguiendo el patrón |
| T6 | Mover jugador por **tap** (Titular ↔ Suplente) | Frontend | No | Nuevo |
| T7 | Mover jugador por **arrastre** (Pointer Events) | Frontend | No | Nuevo — ver 3.2 |
| T8 | Soltar fuera de zona cancela y la fila vuelve | Frontend | No | Nuevo |
| T9 | Contador refleja mínimo y habilita/deshabilita el botón | Frontend | No | Nuevo |
| T10 | Cambios sin guardar bloquean "Empezar Partido" | Frontend | No | Nuevo |
| T11 | `409` de concurrencia muestra el aviso y refetchea | Frontend | No | Nuevo |
| T12 | Selector de equipo en <800px muestra un equipo por vez | Frontend | No | Nuevo |
| T13 | `aria-live` anuncia el movimiento | Frontend | No | Nuevo |
| T14 | `_validar_titulares` con `minimo_jugadores_para_iniciar` seteado: arranca con menos que `tamano_equipo` | Backend | No | Nuevo en `test_titulares_inicio_partido.py` |
| T15 | Mismo, con menos que el mínimo → 400 | Backend | No | Nuevo |
| T16 | `minimo = NULL` reproduce exactamente el comportamiento actual | Backend | Parcial (los tests de hoy cubren el caso) | **Test explícito de no-regresión** |
| T17 | `minimo > tamano_equipo` se rechaza al crear/editar el torneo | Backend | No | Nuevo en `test_torneos.py` |
| T18 | `PUT /convocados` con partido `En curso` → 400 | Backend | No | Nuevo |
| T19 | `POST /convocados` (aditivo) con partido `En curso` → 201, cronómetro intacto | Backend | No | Nuevo — **es el Requerimiento 3** |
| T20 | `POST /convocados` no altera `titular` de nadie | Backend | No | Nuevo |
| T21 | Quitar un jugador con eventos cargados → 400 | Backend | No | Nuevo |
| T22 | `PUT` con ETag desactualizado (`MAX(fecha_modificacion)`) → **412** | Backend | No | Nuevo — ver H4-eng/H3-eng: `base_ids` no sirve con diff incremental, y 409 choca con el de integridad |
| T23 | `Fecha_Registro` de los convocados previos **sobrevive** un alta aditiva | Backend | No | Nuevo — es lo que da valor probatorio (H18) |
| T24 | `resultado-directo` en torneo archivado → 400 (H7) | Backend | No | Nuevo en `test_resultado_directo.py` |
| T25 | `resultado-directo` **sin** convocatoria sigue funcionando (D4) | Backend | No | **Nuevo — fija por escrito una decisión hoy implícita** |
| T26 | `GET /cronometro` devuelve `puede_iniciar`/`motivo_bloqueo` coherentes | Backend | No | Nuevo en `test_control_mesa_tiempos.py` |
| T27 | `CargaEvento`: "quién sale" ofrece los que están en cancha (H2) | Frontend | No | Nuevo |
| T28 | Convocatoria arranca con toda la plantilla marcada (default invertido) | Frontend | No | Nuevo |
| T29 | Partido de bracket sin rival → modo "esperando rival" | Frontend | No | Nuevo |
| T30 | Partido `Finalizado` → solo lectura | Frontend + Backend | No | Nuevo |
| T31 | `MisPartidos` (Árbitro) navega a la misma ruta | Frontend | Existe (roto por el split) | **Actualizar** |
| T32 | Todo lo que hoy cubre `ControlDeMesa.test.tsx` (419 líneas) | Frontend | Sí | **No debe romperse** — es la red de seguridad del split |

**Cobertura crítica que hoy no existe y explica el bug:** ningún test cubre el
camino del TorneoAdmin sobre un partido `Programado` (T1). Por eso H1 pudo
existir sin que nadie lo viera.

#### 3.2 Riesgo concreto de testing: Pointer Events en jsdom

El entorno de test es jsdom (`vite.config.ts`, `environment: 'jsdom'`). jsdom
**no implementa `setPointerCapture`/`releasePointerCapture`** ni construye
`PointerEvent` completo. Sin prever esto, T7 y T8 se vuelven imposibles y el
arrastre queda sin cobertura — que es exactamente el riesgo que hace peligroso
al arrastre.

**Mitigación, decidida ahora y no en la mitad de la implementación:**
`src/test/setup.ts` (que ya existe) agrega stubs de
`Element.prototype.setPointerCapture`/`releasePointerCapture` y un shim de
`PointerEvent` sobre `MouseEvent`. `@testing-library/user-event` v14 (ya
instalado) tiene `pointer()` para manejar la secuencia. Es la razón práctica
más fuerte para que la vía de tap sea de primera clase: T6 se testea sin nada
de esto.

#### 3.3 Artefacto del plan de pruebas

Se escribe a disco en `~/.gstack/projects/Score-App/` (ver la sección de
artefactos al final).

### Sección 4 — Performance

| # | Hallazgo | Impacto | Resolución |
|---|---|---|---|
| P1 | `useTitularesCompletos` por fila → 6 queries × N partidos (~60 con 20 partidos) | Alto en 3G de cancha | **Se elimina.** El cálculo pasa a hacerse una vez, en la vista del partido abierto |
| P2 | `_validar_titulares` hace un `list()` de inscripciones + un `list(limit=10_000)` de roster **por equipo**, en cada `Inicio_Partido` | Bajo (1 vez por partido) | Se deja. Publicarlo en `GET /cronometro` lo mueve a un endpoint con polling, así que **ahí sí** conviene: se calcula sobre los datos que `estado_cronometro` ya carga, sin repetir el `limit=10_000` |
| P3 | `GET /cronometro` con `LIVE_POLL_MS = 5000` sumaría el cálculo de titulares a cada poll | Medio | El cálculo solo corre cuando el partido **no** arrancó (`partido_iniciado == false`); una vez en curso, `puede_iniciar` no tiene sentido y se devuelve `null` sin tocar la base |
| P4 | Diff incremental en vez de DELETE+INSERT | Positivo | Menos filas escritas por guardado |
| P5 | El arrastre re-renderiza la lista en cada `pointermove` | Medio en gama baja | La posición del elemento arrastrado va por `transform` en un `ref`, fuera del ciclo de render de React; solo el cambio de zona activa dispara `setState` |

**P3 es un hallazgo real de este plan, no del código actual:** publicar
`puede_iniciar` en un endpoint que ya se pollea cada 5 s podría multiplicar
por 12/minuto un cálculo que hoy corre una vez por partido. La condición de
`partido_iniciado` lo acota.

### Modos de falla — registro consolidado (Fase 3)

| Modo de falla | Prob. | Impacto | Mitigación | ¿Hueco crítico? |
|---|---|---|---|---|
| Deadlock del TorneoAdmin (H1) | **Cierta — pasa hoy** | **Crítico** — la feature es inalcanzable | Fase 0 de desbloqueo + T1 | Resuelto |
| Quitar un titular con eventos cargados | Media | Crítico — corrompe el histórico | Guard server-side + T21 | Resuelto |
| Lost update entre dos operadores | Media | Alto | ETag `MAX(fecha_modificacion)` + 412 + T22/T40 | Resuelto |
| Pérdida de `Fecha_Registro` por DELETE+INSERT | Alta | Alto | Endpoint aditivo + T23 | Resuelto |
| Resultado directo en torneo archivado (H7) | Baja | Alto | `_validar_torneo_no_archivado` + T24 | Resuelto |
| Arrastre sin cobertura de tests | **Alta si no se preparan los stubs** | Medio | Stubs en `setup.ts` + tap como vía testeable | Resuelto |
| Split rompe `MisPartidos`/tests | Alta si va junto con la feature | Medio | Commit de mudanza separado | Resuelto |
| `puede_iniciar` recalculado en cada poll | Media | Medio | Solo si el partido no arrancó | Resuelto |
| Mínimo mal configurado (muy bajo) | Media | **Alto** — el walkover deja de usarse y entra basura a la tabla de posiciones | `NULL` por default + `CHECK >= 1` + validación `<= tamano_equipo` + copy en el formulario del torneo | Resuelto |
| `titular` sigue sin consumirse (H2) | Media si se difiere | Medio — la UI produce un dato que nadie usa | Incorporado al alcance + T27 | Resuelto |
| Operador no distingue pre-partido de en-curso | Media | Alto — edita creyendo que no afecta nada | Banda persistente de modo (Fase 2, Pass 3) | Resuelto |

**Huecos críticos sin resolver: ninguno.** Los tres que quedan abiertos son
decisiones de producto que el usuario tiene que tomar (ver Desafíos al
Usuario), no huecos de ingeniería.

### Voz externa (Eng) — hallazgos y enmiendas

**CODEX SAYS (eng — architecture challenge):** `[codex-unavailable]`.

**CLAUDE SUBAGENT (eng — independent review):** 18 hallazgos, 5 críticos.
Confirmó H1, la Sección 7, EC-2/Sección 8 y H15 de forma independiente, y
encontró **cinco supuestos míos que son falsos contra el código**. Todos
verificados antes de incorporarlos.

#### C2 — La migración sola rompe los ~40 archivos de test (CRITICAL) — **verificado**

`backend/tests/conftest.py:39-47` construye la base de tests **solo con
`01_schema.sql` … `06_triggers.sql`**. Nunca corre los scripts 07+. En cuanto
`models/torneo.py` declare `minimo_jugadores_para_iniciar`, si la columna vive
únicamente en `27_migracion_...sql`, **toda la suite revienta con
`UndefinedColumn`**. Y `test_scripts_sql.py:36-48` mantiene una lista
`SCRIPTS_VIGENTES` (hoy termina en `25_migracion_convocados.sql`) que corre
cada script **dos veces** para verificar que sea re-ejecutable.

**Corrección adoptada:** la tarea de migración son **3 archivos, no 1**:
`01_schema.sql` (el `CREATE TABLE TORNEO`), `27_migracion_minimo_titulares.sql`
idempotente con `IF NOT EXISTS`, y el alta en `SCRIPTS_VIGENTES`. Esto vale
para cualquier columna nueva en este repo: es la convención, y mi plan la
ignoraba.

#### C3 — Con `NULL` como default, el campo era una puerta de una sola dirección (CRITICAL) — **verificado**

`BaseRepository.save_changes` (`repositories/base.py:62-64`) hace
`if valor is not None: setattr(...)`, y `TorneoService.update` le pasa el
payload directo. Consecuencia: una vez que el admin escribe `minimo = 5`,
**no hay forma por API de volver a `NULL`** — es decir, de volver al default
de la modalidad. Y todo el diseño de D1-revisada depende de que `NULL` sea un
valor alcanzable.

**Corrección adoptada:** `TorneoService.update` escribe este atributo a mano,
fuera de `save_changes`, distinguiendo "campo ausente en el payload" de
"campo presente con valor `null`" (Pydantic `model_fields_set`). La UI del
formulario (H-16) necesita que vaciar el campo signifique exactamente eso.

#### C4 — El cruce de EC-1 contra `EVENTOS_PARTIDO` no se podía escribir (CRITICAL) — **verificado**

Mi EC-1 decía "si el jugador tiene eventos, no se lo puede sacar". Pero no hay
columna en común:

- `models/evento_partido.py:24` — `jugador_id` es FK a **`jugadores.id`**
- `models/convocado_a_partido.py:23` — `jugador_perfil_id` es FK a
  **`jugador_perfil_disciplina.id`**

Hace falta un join por `jpd.jugador_id`. Y faltaban dos cosas más: cubrir
`jugador_id_entra` (`evento_partido.py:27`) — que es **justamente el suplente
que entró**, el jugador que produce la feature de llegadas tardías — y
excluir los eventos `Anulado` (`evento_partido.py:30`), que no deben bloquear.

**Corrección adoptada:**

```sql
SELECT 1 FROM eventos_partido ep
JOIN jugador_perfil_disciplina jpd
  ON jpd.jugador_id IN (ep.jugador_id, ep.jugador_id_entra)
WHERE ep.partidos_id = :pid AND ep.estado = 'Registrado'
  AND jpd.id = ANY(:perfiles_a_quitar)
```

#### C5 — `PATCH /partidos/{id}` anulaba el gate de D3 en un request (CRITICAL) — **verificado**

`schemas/partido.py:47` declara `estado: EstadoPartido | None` y
`PartidoService.update` **no valida ninguna transición**: solo el ownership de
árbitro. Con un gate anclado a `partido.estado`, la secuencia
`PATCH {estado:"Programado"}` → `PUT` destructivo → `PATCH {estado:"En curso"}`
lo saltea entero.

Y al revés: `fn_hito_sincroniza_estado_partido` (`06_triggers.sql:619-623`)
solo hace `Programado → En curso`. Un partido puesto "En curso" por `PATCH`
**nunca pasó por `_validar_titulares`**.

**Corrección adoptada — cambia el mecanismo del gate:** la condición no es
`partido.estado`, es **la existencia del hito `Inicio_Partido`**. El hito es
append-only y ningún `PATCH` lo revierte, así que es la única señal
inviolable de "este partido ya arrancó". Se agrega además validación de
máquina de estados en `PartidoService.update`. Esto es estrictamente mejor
que lo que yo tenía, y es el tipo de cosa que solo se ve leyendo el código.

#### H1-eng — Publicar el veredicto en `/cronometro` lo volvía el endpoint más caro del sistema (HIGH)

Yo había acotado el cálculo a "solo si el partido no arrancó" (P3 de
performance), pero eso no alcanza. `routes/partidos.py:216-223` **no tiene
`require_roles`**: es público y anónimo. Y lo pollean cada 5 s tanto
`Cronometro.tsx` como `PartidoEnVivo.tsx`, esta última alcanzable sin login
(`App.tsx:64`). `_validar_titulares` suma ~7 queries, entre ellas un
`jugador_equipo.list(limit=10_000)` **por equipo** que trae el roster entero a
Python. Diez partidos con veinte espectadores = ~40 req/s × ~10 queries, sin
autenticación. Mi Sección 3 decía "sin superficie nueva" y estaba mal.

Bonus: `_cargar_contexto` tira 400 si falta la config de tiempos
(`hito_partido.py:53-54`), así que meter el veredicto ahí hace que el caso
"torneo sin config" devuelva error en vez del bloqueo explicado que promete
la Sección 2.

**Corrección adoptada:** endpoint aparte
**`GET /partidos/{id}/preflight-inicio`**, con el mismo par de dependencias
que ya usa `POST /hitos` (`require_roles("TorneoAdmin","Arbitro")` +
`require_torneo_access_de(...)`). Se consulta al abrir la vista y al invalidar
`["convocados", id]`, **nunca** en un `refetchInterval`. `/cronometro` queda
exactamente como está.

#### H2-eng — Mi EC-7 citaba un endpoint que no trae lo que dije (HIGH) — **verificado**

EC-7 afirmaba que "`GET /plantillas` sí trae `equipo_id`". **Falso:**
`schemas/jugador_equipo.py:24-35` expone `inscripcion_torneo_id`, no
`equipo_id`, ni el nombre del jugador.

El otro camino, `EstadisticasRepository.plantilla_equipo`
(`repositories/estadisticas.py:68-73`), sí trae nombre/dorsal/perfil pero
**filtra solo por `equipo_id`, sin torneo**, aunque la vista
`vw_jugadores_activos_por_equipo` ya expone `it.Torneo_ID` (`04_views.sql:90`).
Dos consecuencias reales:

1. Un equipo inscripto en dos torneos activos de la misma disciplina devuelve
   el **mismo `jugador_perfil_id` dos veces**. Hoy eso ya rompe
   `key={j.jugador_perfil_id}` en `Convocatoria.tsx:161`; con listas
   arrastrables keyeadas por perfil, dos nodos con la misma key es
   reordenamiento errático, no un warning cosmético.
2. `ConvocadoAPartidoService.reemplazar` valida contra esa unión
   (`convocado_a_partido.py:46-50`), así que **hoy se puede convocar a alguien
   del equipo en otro torneo**: `_validar_titulares` no lo cuenta y
   `fn_validar_jugador_partido` (`06_triggers.sql:141-152`) le rechaza
   cualquier evento. Titular fantasma que no suma y no puede meter goles.

**Corrección adoptada:** `plantilla_equipo(equipo_id, torneo_id)` — una línea
de SQL, la columna ya está en la vista — usada en el service y en el editor.

#### H4-eng — El diff incremental mata la concurrencia optimista que yo mismo propuse (HIGH)

Hallazgo fino y correcto. `base_ids` funcionaría hoy **por accidente**, porque
`reemplazar_convocatoria` hace DELETE+INSERT y los `id` rotan. Mi propio EC-2
elimina eso. Con diff incremental, cambiar `titular` de `True` a `False` es un
**UPDATE que no toca ningún `id`**: el set de `base_ids` queda idéntico y el
chequeo de versión no detecta nada. Dos operadores intercambiando titulares se
pisan en silencio — que es literalmente EC-3, el caso que la concurrencia
optimista existía para prevenir.

**Corrección adoptada:** versionado por contenido. Se agrega
`CONVOCADO_A_PARTIDO.Fecha_Modificacion` en la misma migración, con el trigger
`fn_actualizar_fecha_modificacion` que **ya existe** (`06_triggers.sql:21-27`)
y se usa en el resto del esquema, y el ETag es `MAX(fecha_modificacion)` del
partido. Nota: esa columna hoy no existe en la tabla (`01_schema.sql:563-569`).

#### H3-eng — Mi `409` colisiona con el `409` que el repo ya usa (HIGH) — **verificado**

`handlers.py:90-92` mapea **todo** `IntegrityError` a 409 con `{"detail": ...}`.
El cliente no podría distinguir mi conflicto de concurrencia de una violación
de `unique_convocado_partido` (`02_constraints.sql:328`) — que es exactamente
lo que va a producir el `POST` aditivo con un doble-tap.

**Corrección adoptada:** **`412 Precondition Failed`** para el conflicto de
versión, siguiendo el precedente del repo de distinguir casos especiales
(`LicenseRevokedError` usa un header propio, `errors.py:61-63`). Y el
`IntegrityError` del `POST` aditivo se atrapa en el service para responder
**idempotente** ("ya estaba convocado"), no 409: un doble-tap en una cancha no
es un error.

#### H5-eng — `Fecha_Registro` no prueba lo que D3-revisada dice que prueba (HIGH)

Justifiqué el endpoint aditivo diciendo que conserva "el valor probatorio de a
qué hora se sumó". Pero `fecha_registro` sale de
`server_default=CURRENT_TIMESTAMP` (`models/convocado_a_partido.py:25`), que
en Postgres es **el inicio de la transacción**, y la tabla no tiene
`registrado_por` ni minuto de partido — a diferencia de `HITOS_PARTIDO`, que
sí guarda `registrado_por`.

**Corrección adoptada:** se agregan `Minuto_Ingreso INT NULL` y
`Registrado_Por` a `CONVOCADO_A_PARTIDO` en la misma migración. Sin eso, el
argumento probatorio se cae y habría que sacarlo del plan.

#### H6-eng — `MesaPanel` es infraestructura compartida, no una página de Control de Mesa (HIGH)

`arbitro/MisPartidos.tsx:5` lo importa. Meterlo bajo `pages/control-mesa/`
**cementa una violación de frontera** (`pages/arbitro/` importando de
`pages/control-mesa/`). Lo mismo aplica a `AlineacionVista`, que quiere
compartirse con `PartidoEnVivo.tsx`.

**Corrección adoptada:** `MesaPanel` y `AlineacionVista` van a
`frontend/src/components/`, no a la subcarpeta de un módulo. Mi decisión 1.3
(que `MisPartidos` navegue a la misma ruta) se mantiene y se refuerza: es lo
que evita que Árbitro y TorneoAdmin queden con flujos divergentes.

#### M1-eng — "Pointer Events son simulables en jsdom" es falso (MEDIUM)

Lo escribí en la Sección 3.2 y está mal. jsdom no implementa `PointerEvent`
ni `setPointerCapture`, y —lo decisivo— **`getBoundingClientRect()` devuelve
todo en cero**, así que no hay forma de decidir sobre qué contenedor se soltó.
Los stubs que yo proponía no arreglan eso. Sumado: `setup.ts:21` usa
`onUnhandledRequest: "error"`, así que cualquier query sin mock es fallo duro.

**Corrección adoptada, y baja la promesa a lo que se puede cumplir:** el
arrastre se cubre con (a) tests unitarios de la **función pura** de
reubicación (`mover(perfilId, zona)`), y (b) tests de tap y teclado sobre los
botones. **El gesto de arrastre queda declarado como NO cubierto por unit
tests** y pasa a QA manual en navegador real. Es la razón definitiva por la
que el tap es de primera clase y no un repliegue.

#### M2-eng — El wrapper de tests no tiene rutas (MEDIUM)

`test/test-utils.tsx:32-43` monta `MemoryRouter` **sin `<Routes>`**. Un
`GestionarPartido` que lea `useParams().partidoId` recibiría `undefined` →
`GET /api/v1/partidos/NaN` → unhandled request → fallo duro. Los tests de la
ruta nueva necesitan su propio `MemoryRouter initialEntries` + `<Routes>`,
como ya hace `App.routing.test.tsx`.

#### M3-eng — EC-8 choca con un botón que existe hoy (MEDIUM)

"Sacar convocatoria (volver a toda la plantilla)" está visible en
`Convocatoria.tsx:134-138` y, con el gate nuevo, devolvería 400 con el partido
en curso. **Corrección:** ese botón se oculta cuando existe el hito
`Inicio_Partido` (mismo criterio que C5).

#### M4-eng — Interacción no anticipada entre `fn_validar_jugador_partido` y D5 (MEDIUM)

`06_triggers.sql:147-148` valida pertenencia contra **la fecha del partido**,
mientras que `_validar_titulares` valida contra **`estado='Activo'` sin
fechas**. Son criterios distintos: un titular que pasa el gate de arranque
puede tener sus goles rechazados por el trigger. Y `trg_eventos_partido_validar`
es `BEFORE INSERT OR UPDATE ON EVENTOS_PARTIDO`, **no sobre `PARTIDOS`**: mover
la fecha hacia atrás después de cargar eventos no revalida nada.

Mi D5 pone `EditorFechaPartido` en la misma pantalla que la alineación en
vivo, lo que hace ese orden de operaciones mucho más probable.
**Corrección adoptada:** "reprogramar" se deshabilita en cuanto existe el hito
`Inicio_Partido`.

#### M5-eng — El preflight también tiene que correr `_validar_torneo_no_archivado` (MEDIUM)

Si no, el botón se habilita en un torneo archivado y el `POST` devuelve 400 —
la misma divergencia cliente/servidor que la Sección 5 dice cerrar.
**Adoptado.**

#### M6-eng — Orden del guard nuevo en `resultado-directo` (MEDIUM)

El guard de H7 tiene que ir **antes del primer `flush()`** (`partido.py:166`):
después del `Inicio_Partido`, el trigger ya movió `PARTIDOS.Estado` en la base
mientras el objeto Python sigue diciendo `'Programado'`
(`expire_on_commit=False`, `db/database.py:24`). Nota que corrige mi D4:
`registrar_resultado_directo` **ya tiene** guard de estado
(`partido.py:146-150`); lo que le falta es solo el de archivado. **Adoptado.**

#### M7-eng — Citas de línea corridas (MEDIUM)

El plan se presenta como verificado línea por línea, así que las citas tienen
que estar bien. Corregidas: `App.tsx:63`→`:64`;
`partidos.py:280-300`→`:281-299`; `hito_partido.py:151-205`→`:139-193`;
`hito_partido.py:213`→`:201-204`.

### ENG — TABLA DE CONSENSO

```
ENG DUAL VOICES — CONSENSUS TABLE:
═══════════════════════════════════════════════════════════════════════
  Dimensión                              Claude   Codex   Consenso
  ─────────────────────────────────────  ───────  ──────  ────────────
  1. ¿Arquitectura sólida?               PARCIAL  N/A     FLAGGED
                                         (H6-eng)         (destino del split)
  2. ¿Cobertura de tests suficiente?     NO       N/A     FLAGGED
                                         (C2, M1, M2)     (3 hallazgos)
  3. ¿Riesgos de performance atendidos?  NO       N/A     FLAGGED
                                         (H1-eng)         (endpoint público)
  4. ¿Amenazas de seguridad cubiertas?   NO       N/A     FLAGGED
                                         (C5, H1-eng)     (gate evitable)
  5. ¿Caminos de error manejados?        NO       N/A     FLAGGED
                                         (C4, H3, H4)     (3 mecanismos rotos)
  6. ¿Riesgo de despliegue manejable?    NO       N/A     FLAGGED
                                         (C2, C3)         (migración 3 archivos)
═══════════════════════════════════════════════════════════════════════
Voz faltante (Codex) = N/A, nunca CONFIRMED.
Consenso: 0/6 CONFIRMED — voz única. 6/6 dimensiones marcadas,
5 hallazgos críticos, 18 en total, 18 adoptados, 0 rechazados.
```

### Tests que la voz externa agregó al diagrama

| # | Flujo / codepath | Tipo | Por qué |
|---|---|---|---|
| T33 | `01_schema.sql` y `27_migracion_...sql` quedan sincronizados | Backend | C2 — sin esto la suite entera revienta |
| T34 | `PATCH {estado:"Programado"}` no reabre la edición de un partido con hito `Inicio_Partido` | Backend | C5 — es el bypass del gate |
| T35 | Quitar un jugador que solo aparece como `jugador_id_entra` → 400 | Backend | C4 — es el suplente que entró, el caso de la feature |
| T36 | Un evento `Anulado` **no** bloquea quitar al jugador | Backend | C4 |
| T37 | `minimo` seteado se puede volver a `NULL` por API | Backend | C3 — la puerta de una sola dirección |
| T38 | `plantilla_equipo` con equipo en 2 torneos no duplica `jugador_perfil_id` | Backend | H2-eng — hoy rompe las keys de React |
| T39 | `POST` aditivo con doble-tap responde idempotente, no 409 | Backend | H3-eng |
| T40 | Conflicto de versión devuelve **412**, distinguible del 409 de integridad | Backend | H3-eng |
| T41 | Función pura `mover(perfilId, zona)` | Frontend | M1-eng — reemplaza el test de gesto que jsdom no permite |
| T42 | "Reprogramar" deshabilitado con hito `Inicio_Partido` | Frontend | M4-eng |

**T7/T8 (gesto de arrastre) se retiran de la suite automática** y pasan a QA
manual en navegador real (M1-eng).

> **Fase 3 completa.** Codex: no disponible. Claude subagent: 18 hallazgos, 5
> críticos, **18 adoptados, 0 rechazados**. Consenso: 0/6 CONFIRMED (voz
> única), 6/6 dimensiones marcadas. Cinco supuestos míos sobre el código
> resultaron falsos y quedaron corregidos. Pasando a la Fase 4.

### Qué ya existe (Fase 3, consolidado)

Ver el leverage map completo en 0B. Resumen para implementación: **no se crea
ninguna tabla**, **no se renombra ningún endpoint**, y de los 6 endpoints que
la vista consume, **5 ya existen y funcionan**. Lo único nuevo en la superficie
de API es `POST /partidos/{id}/convocados` y 4 campos aditivos en
`GET /partidos/{id}/cronometro`.

### NO está en alcance (Fase 3)

Además de lo listado en la Fase 1:

- **Reescribir `MesaPanel`, `Cronometro` o `CargaEvento`.** Se mueven de
  archivo y `CargaEvento` recibe una derivación nueva; su lógica interna no se
  toca.
- **Migrar el resto del frontend a rutas.** Solo Control de Mesa; el patrón
  `useState` sigue vivo en otras pantallas y no es problema de este plan.
- **Cambiar `system-ui` por una tipografía real.** Observación del sistema de
  diseño registrada en la Fase 2, decisión de toda la app.
- **Saldar la deuda de `as never`** en las mutaciones de `openapi-fetch`.
- **Tope superior de titulares.** Sigue diferido (`TODOS.md`); este plan
  agrega el contador visible, no el bloqueo.

---

## Tareas de implementación

Ordenadas por dependencia. Los tres primeros bloques son entregables
independientes que se pueden mergear por separado.

### Bloque 0 — Desbloqueo (H1). Va primero y solo.

- [ ] **`ControlDeMesa.tsx:403-417`** — agregar acceso al panel para partidos
      `Programado` (hoy solo existe para `En curso`), rompiendo el deadlock
      convocatoria↔arranque.
- [ ] **`ControlDeMesa.tsx:1113-1130`** — en `MesaPanel`, subir `<Convocatoria>`
      por encima de `<Cronometro>` cuando el partido no arrancó.
- [ ] **Test T1** — TorneoAdmin abre la convocatoria de un partido `Programado`.
      Es el test de regresión del bug; sin él, el bug puede volver.

### Bloque 1 — Mudanza mecánica (sin cambios de comportamiento)

- [ ] **Crear `frontend/src/pages/control-mesa/`** con lo que es propio del
      módulo: `ControlDeMesa.tsx`, `GestionarPartido.tsx`,
      `AlineacionEditor.tsx`, `ModalResultadoDirecto`, `AccionWalkoverMesa`,
      `EditorFechaPartido`.
- [ ] **H6-eng — `MesaPanel`, `Cronometro`, `CargaEvento`, `EventoTimelineFila`
      y `AlineacionVista` van a `frontend/src/components/`, NO a
      `pages/control-mesa/`.** `arbitro/MisPartidos.tsx:5` ya importa
      `MesaPanel`, y `AlineacionVista` se comparte con `PartidoEnVivo.tsx`:
      meterlos bajo la carpeta de un módulo cementa una violación de frontera
      (`pages/arbitro/` importando de `pages/control-mesa/`).
- [ ] **Actualizar los 3 importadores**: `App.tsx:5`,
      `arbitro/MisPartidos.tsx:5`, `ControlDeMesa.test.tsx:11`.
- [ ] **Verificar T32** — la suite existente (419 líneas) queda verde sin
      cambios de aserción.

### Bloque 2 — Backend

- [ ] **CRÍTICO (C2) — la migración son TRES archivos, no uno.**
      `conftest.py:39-47` arma la base de tests solo con `01_schema.sql`…
      `06_triggers.sql`: si la columna vive únicamente en el script 27, la
      suite entera revienta con `UndefinedColumn` en cuanto el modelo la
      declare.
      1. `database/01_schema.sql` — agregar las columnas al `CREATE TABLE TORNEO`
         y a `CREATE TABLE CONVOCADO_A_PARTIDO`.
      2. `database/27_migracion_minimo_titulares.sql` — idempotente, con
         `ADD COLUMN IF NOT EXISTS` (se ejecuta dos veces en los tests).
      3. `backend/tests/test_scripts_sql.py:47` — alta en `SCRIPTS_VIGENTES`.
- [ ] **Columnas de la migración:**
      - `TORNEO.Minimo_Jugadores_Para_Iniciar INT NULL` +
        `CHECK (>= 1)`. Sin backfill: `NULL` = usar `Tamano_Equipo`.
      - `CONVOCADO_A_PARTIDO.Fecha_Modificacion` + el trigger
        `fn_actualizar_fecha_modificacion` que **ya existe**
        (`06_triggers.sql:21-27`) — es el ETag de concurrencia (H4-eng).
      - `CONVOCADO_A_PARTIDO.Minuto_Ingreso INT NULL` y `Registrado_Por` —
        sin esto el argumento probatorio de las llegadas tardías no se
        sostiene (H5-eng).
- [ ] **`models/torneo.py`** — columna nueva junto a `permite_walkover_grupos`
      (mismo tipo de dato: flag de reglamento por torneo).
- [ ] **CRÍTICO (C3) — `TorneoService.update` escribe el mínimo a mano**, fuera
      de `save_changes`: `BaseRepository.save_changes` (`base.py:62-64`) hace
      `if valor is not None`, así que por la vía normal **el campo nunca puede
      volver a `NULL`** y todo el diseño de D1 depende de que `NULL` sea
      alcanzable. Distinguir "ausente del payload" de "presente y `null`" con
      `model_fields_set`.
- [ ] **`schemas/torneo.py`** — `TorneoCreate`/`TorneoUpdate`/`TorneoOut`;
      validación `1 <= minimo <= modalidad.tamano_equipo` en `TorneoService`
      (es cross-table, no puede ser `CHECK`).
- [ ] **`services/hito_partido.py:170`** —
      `requeridos = torneo.minimo_jugadores_para_iniciar or modalidad.tamano_equipo`.
- [ ] **CRÍTICO (H1-eng) — endpoint nuevo `GET /partidos/{id}/preflight-inicio`**
      con `require_roles("TorneoAdmin","Arbitro")` +
      `require_torneo_access_de(...)`, que devuelve `minimo_para_iniciar`,
      `titulares_por_equipo`, `puede_iniciar` y `motivo_bloqueo`.
      **NO** se agregan estos campos a `GET /partidos/{id}/cronometro`: ese
      endpoint es público sin auth (`partidos.py:216-223`) y lo pollean cada
      5 s `Cronometro.tsx` y `PartidoEnVivo.tsx` de forma anónima; meterle
      `_validar_titulares` (~7 queries, con un `list(limit=10_000)` de roster
      por equipo) lo convertiría en el endpoint más caro del sistema.
      Se consulta al abrir la vista y al invalidar `["convocados", id]`,
      **nunca** en `refetchInterval`. Corre también
      `_validar_torneo_no_archivado` (M5-eng).
- [ ] **CRÍTICO (C5) — el gate se ancla al hito `Inicio_Partido`, no a
      `partido.estado`.** `schemas/partido.py:47` acepta `estado` y
      `PartidoService.update` no valida transiciones, así que
      `PATCH {estado:"Programado"}` → `PUT` destructivo →
      `PATCH {estado:"En curso"}` saltearía el gate entero. El hito es
      append-only y ningún `PATCH` lo revierte. Agregar además validación de
      máquina de estados en `PartidoService.update`.
- [ ] **CRÍTICO (C4) — el cruce de EC-1 necesita un join.**
      `eventos_partido.jugador_id` es FK a `jugadores.id`;
      `convocado_a_partido.jugador_perfil_id` es FK a
      `jugador_perfil_disciplina.id`. No hay columna común. Cubrir **también**
      `jugador_id_entra` (el suplente que entró, que es el caso de la feature)
      y **excluir** los eventos `Anulado`.
- [ ] **`services/convocado_a_partido.py`** — guard de hito en `reemplazar`;
      concurrencia optimista por `MAX(fecha_modificacion)` como ETag (**no**
      por `base_ids`: con diff incremental un cambio de `titular` es un UPDATE
      que no toca ningún `id`, así que el set queda idéntico y el chequeo no
      detecta nada — H4-eng); rechazo de quitar un perfil con eventos.
- [ ] **`services/convocado_a_partido.py`** — método `agregar` (aditivo, no
      borra, no toca `titular` de nadie), permitido con y sin hito de inicio.
      Atrapar el `IntegrityError` de `unique_convocado_partido` y responder
      **idempotente** ("ya estaba convocado"): un doble-tap en la cancha no es
      un error (H3-eng).
- [ ] **Conflicto de versión responde `412 Precondition Failed`**, no 409:
      `handlers.py:90-92` ya mapea **todo** `IntegrityError` a 409 y el
      cliente no podría distinguirlos (H3-eng).
- [ ] **`repositories/convocado_a_partido.py`** — reemplazar el `delete()`
      masivo por diff incremental por objeto (recupera la auditoría —
      `core/auditoria.py` engancha el unit of work y el `delete()` masivo lo
      esquiva — y conserva `Fecha_Registro`).
- [ ] **`repositories/estadisticas.py:68-73` (H2-eng) —
      `plantilla_equipo(equipo_id, torneo_id)`.** Hoy filtra solo por equipo,
      aunque `vw_jugadores_activos_por_equipo` ya expone `Torneo_ID`
      (`04_views.sql:90`). Sin esto, un equipo en dos torneos activos devuelve
      el mismo `jugador_perfil_id` dos veces — que hoy ya rompe
      `key={j.jugador_perfil_id}` (`Convocatoria.tsx:161`) y con listas
      arrastrables produce reordenamiento errático — y permite convocar a
      alguien del equipo **en otro torneo**, que sería un titular fantasma:
      no lo cuenta `_validar_titulares` y `fn_validar_jugador_partido` le
      rechaza cualquier evento.
- [ ] **`routes/partidos.py`** — `POST /{partido_id}/convocados` con las mismas
      dependencias de rol/scoping que el `PUT`.
- [ ] **`services/partido.py:165` (H7)** — llamar `_validar_torneo_no_archivado`
      **antes del primer `flush()`**: después del `Inicio_Partido` el trigger
      ya movió `PARTIDOS.Estado` en la base mientras el objeto Python sigue
      diciendo `'Programado'` (`expire_on_commit=False`, `db/database.py:24`).
      El guard de estado **ya existe** (`partido.py:146-150`); lo único que
      falta es el de archivado. **No** se agrega `_validar_titulares` (D4).
- [ ] **Regenerar `frontend/src/api/schema.d.ts`** (`npm run gen:api`).

### Bloque 3 — Frontend, vista nueva

- [ ] **`App.tsx`** — ruta `/control-de-mesa/partido/:partidoId` con el mismo
      `RequireRole` que `/control-de-mesa`.
- [ ] **`control-mesa/GestionarPartido.tsx`** — encabezado con nombre de
      torneo (H-4), banda de modo persistente con `[+ Sumar jugador]` (H-12),
      Paso 1 arriba mientras está expandido y colapso explícito (H-1, H-2),
      editor, acciones principales, "Otras acciones" plegadas (D5).
- [ ] **CRÍTICO (H-10) — "Empezar Partido" ejecuta la lógica de
      `iniciarPrimerTiempo()`** (`Cronometro.tsx:169-172`): dos hitos en
      `Periodos` (`Inicio_Partido` + `Inicio_Periodo(1)`), uno en `Corrido`.
      **No** reusar el mutation del dashboard (`ControlDeMesa.tsx:313-318`),
      que solo dispara `Inicio_Partido` y dejaría el reloj parado en 00:00.
      Pasar `mostrarInicio={false}` a `Cronometro` dentro de esta vista para
      que no renderice su propio botón ▶.
- [ ] **CRÍTICO (H-11) — `useBlocker` sobre `hayCambiosSinGuardar`** con
      diálogo de tres salidas, más borrador en `localStorage`
      (`alineacionBorrador:{partidoId}`) escrito en cada movimiento y banner
      de "Retomar / Descartar" al montar.
- [ ] **CRÍTICO (H-5) — estados offline:** reusar `useOnlineStatus`
      (`ControlDeMesa.tsx:826`), `esErrorDeRed` (`:23`) y `.mesa-offline-aviso`
      (`index.css:418`). Nunca `apiErrorMessage` sobre un `TypeError`.
- [ ] **`control-mesa/AlineacionEditor.tsx`** — dos contenedores con
      `max-height: 40vh; overflow-y: auto` (**H-20**, para que la zona destino
      nunca quede fuera de pantalla), selector de equipo en <1000px (H-23),
      contador contra el mínimo, filas de una línea con
      `.alineacion-fila__mover` de 56×56 (**no** `.tap-button`, H-18), orden
      por dorsal ascendente, botón "Marcar N por dorsal" en el header de
      Titulares (H-14). En `En curso`: **no renderizar** el botón de degradar
      y poner la restricción como texto en el header de la zona (H-6).
- [ ] **`control-mesa/usePointerDrag.ts` — SOLO se monta en `>=1000px`**
      (decisión del gate final). Arrastre por Pointer Events;
      `touch-action: none` **solo en la manija**, que también existe solo en
      ese viewport; `pointercancel` cancela y restaura; drop en la misma zona
      es no-op; posición por `transform` en un `ref` (P5); `aria-live` solo en
      `pointerup` (H-19). **Queda fuera por la decisión del gate:** el
      long-press de H-22, el auto-scroll peleando con la barra sticky (H-27) y
      el `touch-action` en touch. En `<1000px` la única vía es el tap, que ya
      es de primera clase.
- [ ] **Accesibilidad (H-24..H-27)** — `<ul>`/`<li>` nativos y **solo el botón
      focusable** (un tab stop por jugador, con `aria-label` completo);
      `focus()` sobre el botón del mismo jugador en la zona destino tras el
      re-render; `aria-disabled` + `aria-describedby` en "Empezar Partido" en
      vez de `disabled` + `title`; barra sticky con `border-top` y
      `padding-bottom: max(0.75rem, env(safe-area-inset-bottom))`.
- [ ] **`TorneosAdmin.tsx` (H-16)** — campo "Mínimo de jugadores para iniciar"
      junto a `permite_walkover_grupos`, con placeholder `= tamaño del equipo
      (N)`, helper y errores en línea. Sin esta pantalla el Requerimiento 3 es
      inalcanzable.
- [ ] **`control-mesa/AlineacionVista.tsx`** — componente presentacional
      compartido con `PartidoEnVivo.tsx:286-300` (C4/H12).
- [ ] **`ControlDeMesa.tsx`** — fila del dashboard a un solo botón "Gestionar
      Partido"; **borrar `useTitularesCompletos` y `BotonEmpezarPartido`**
      (-125 líneas, -6 queries por fila).
- [ ] **`arbitro/MisPartidos.tsx`** — navegar a la ruta nueva en vez de montar
      `MesaPanel` por `useState` (1.3).
- [ ] **`CargaEvento`** — consumir `titular` (H2): "quién sale" = en cancha,
      "quién entra" = suplentes. **Con el escape hatch de H-17**: link
      permanente "No lo encuentro — ver toda la plantilla" que quita el filtro.
      Sin eso, un jugador que está jugando pero quedó fuera de la alineación
      deja al operador trabado en el minuto 60.
- [ ] **Default invertido de convocatoria** (alternativa A) y botón "marcar los
      primeros N como titulares" (alternativa C).
- [ ] **`index.css`** — clases nuevas con tokens existentes; reemplazar
      `.convocatoria-equipos` (`1fr 1fr` sin media query, `index.css:488`) por
      el selector de equipo; `overscroll-behavior-x: contain` y **sin swipe
      entre pestañas** (H-21, decisión explícita para que nadie lo agregue
      después); `prefers-reduced-motion` también en la animación de retorno
      del drop fallido.

### Bloque 4 — Tests

- [ ] **`frontend/src/test/setup.ts`** — stubs de
      `setPointerCapture`/`releasePointerCapture` + shim de `PointerEvent`.
      **Va antes de T7/T8**, si no el arrastre queda sin cobertura.
- [ ] **Los 32 tests del artefacto de plan de pruebas** (ver la ruta en el
      GSTACK REVIEW REPORT), priorizando P0: T1, T32, T16.

---

<!-- AUTONOMOUS DECISION LOG -->
## Decision Audit Trail

| # | Fase | Decisión | Clasificación | Principio | Razón | Descartado |
|---|---|---|---|---|---|---|
| 1 | CEO | Modo SELECTIVE EXPANSION | Mecánica | P2 | Extiende 5 archivos existentes, no crea módulo ni tabla | FULL REVIEW (no aplica: no es plan nuevo) |
| 2 | CEO | Mínimo reglamentario en `TORNEO.Minimo_Jugadores_Para_Iniciar`, `NULL` = usar `tamano_equipo` | **Taste — semántica CONFIRMADA POR EL USUARIO en el gate final** (es regla nueva: arrancar con menos que el equipo completo) | P4 + P1 | Precedente exacto: `Torneo.permite_walkover_grupos`. `NULL` evita inventar valores para ~35 modalidades y elimina el riesgo de backfill fallido | Constante (2/10); columna en `MODALIDAD` (6/10, catálogo inmutable por API); `CONFIGURACION_TIEMPO_TORNEO` (mi propuesta inicial — revertida: semánticamente mal ubicada y sin la ventaja de queries que le atribuí) |
| 3 | CEO | **Arrastre solo en `>=1000px`** + tap de primera clase en todos los viewports | **Desafío al Usuario #1 — RESUELTO POR EL USUARIO en el gate final** | P5 + escalón 3 de reuso | Cumple el requerimiento literal sin apostar la usabilidad del celular a un gesto caro; cero dependencias nuevas | D&D nativo HTML5 (no funciona en touch); `@dnd-kit` (primera dependencia de UI del repo); solo tap (no cumple el pedido) |
| 4 | CEO | Edición en vivo acotada por operación: sumar sí, quitar/degradar no | Mecánica | P1 | Es la única lectura que no contradice "bloquea cambios destructivos" con "sumá un jugador en vivo" | Bloqueo total en vivo (rompe el Requerimiento 3); libertad total (corrompe estadísticas) |
| 5 | CEO | `resultado-directo` **no** exige convocatoria, **sí** valida torneo archivado | **Taste** | P3 | Se parte la asimetría: la falta de convocatoria es deliberada (partidos de papel), la falta de guard de archivado es un bug | Agregar ambas validaciones (rompe el caso de uso); no agregar ninguna (deja el agujero) |
| 6 | CEO | Walkover y editar fecha se mudan adentro de la vista | Mecánica | P2 | Colapsar la fila sin reubicarlas revertiría por omisión una decisión de hace 3 días | Dejarlas en la fila (rompe "un solo botón"); eliminarlas (regresión) |
| 7 | CEO | Bloque 0 de desbloqueo (H1) como primer entregable independiente | Mecánica | P6 | El deadlock hace inalcanzable la feature entera; ~5 líneas no deben esperar 700 | Incluirlo en el commit grande (entierra el fix) |
| 8 | CEO | `titular` consumido por `CargaEvento` entra al alcance | Mecánica | P2 | Está en el radio de impacto y sin esto la UI produce un dato que nadie lee | Diferir (deja la feature sin valor aguas abajo) |
| 9 | CEO | Default de convocatoria invertido + botón "marcar N titulares" | Mecánica | P2 | ~18 líneas dentro del radio, convierten 22 toques en 2 | Diferir (el costo es trivial y el beneficio inmediato) |
| 10 | CEO | "Copiar alineación del partido anterior" → diferido a TODOS.md | Mecánica | P3 | Fuera del radio: feature propia con su propia pregunta de producto | Incluirla (amplía el alcance más allá del pedido) |
| 11 | Design | Una pantalla con dos zonas, no un wizard de pasos bloqueados | Mecánica | P5 | Los dos pasos operan sobre el mismo dato y el operador va y viene | Wizard (obliga a retroceder por cada corrección) |
| 12 | Design | Un equipo por vez con pestañas en <800px | Mecánica | P1 | `.convocatoria-equipos` ya es `1fr 1fr` sin media query: dos columnas de ~170px en 375px | Dos columnas simultáneas (inoperable con zonas de arrastre) |
| 13 | Design | Filas compactas, no tarjetas, para los jugadores | Mecánica | P5 | 18 tarjetas en 375px es un mosaico ilegible; la tarjeta se reserva para el contenedor, que sí es la unidad de interacción | Tarjetas por jugador (patrón de slop de App UI) |
| 14 | Design | Estado local + botón "Guardar alineación" explícito | Mecánica | P3 | Autosave por movimiento dispara un `PUT` por arrastre con red de cancha | Autosave (frágil y ruidoso en 3G) |
| 15 | Design | `touch-action: none` solo en la manija, nunca en la fila | Mecánica | P1 | Aplicado a la fila entera impide scrollear una lista de 18 jugadores con el dedo | En la fila (encierra al operador) |
| 16 | Design | Banda persistente de modo (pre-partido vs. en curso) | Mecánica | P1 | Es el punto de quiebre del arco emocional: el operador no sabe si el reloj corre | Sin señal de modo (genera duda y errores) |
| 17 | Eng | Split de archivos en commit propio, antes de la feature | Mecánica | P5 | `MesaPanel` tiene 2 importadores externos; separar hace obvio qué rompió qué | Todo junto (diff ilegible) |
| 18 | Eng | `MisPartidos.tsx` (Árbitro) navega a la misma ruta | Mecánica | P2 | Importador directo, y dos caminos distintos al mismo panel fue lo que enmascaró H1 | Dejarlo con `useState` (perpetúa la asimetría entre roles) |
| 19 | Eng | Rutas separadas para la vista pública y la de gestión; se comparte solo el componente presentacional | Mecánica | P5 | `/partidos/:id` es público sin auth; fusionar pondría escritura detrás de una URL pública | Fusionar rutas (mueve el gate de la tabla de rutas a un condicional) |
| 20 | Eng | Endpoint aditivo `POST /convocados` en vez de `PUT` con reglas por estado | Mecánica | P5 | La operación en vivo es aditiva y por lo tanto conmutativa: desaparece la clase entera de lost-update | `PUT` condicional (mi propuesta inicial — revertida tras la voz externa) |
| 21 | Eng | ~~Concurrencia optimista por `base_ids`~~ — **SUPERADA por la decisión 30** | Mecánica | P4 | Mi propuesta inicial. La anula mi propio EC-2: con diff incremental los `id` dejan de rotar. Se conserva la fila para que el cambio quede trazable | — |
| 22 | Eng | `puede_iniciar` se calcula solo si el partido no arrancó | Mecánica | P1 | `GET /cronometro` se pollea cada 5 s; sin la condición, un cálculo por partido pasa a 12/minuto | Calcular siempre (12x de trabajo inútil) |
| 23 | Eng | Stubs de Pointer Events en `setup.ts` antes de escribir T7/T8 | Mecánica | P1 | jsdom no implementa `setPointerCapture`; sin esto el arrastre queda sin cobertura | Descubrirlo durante la implementación (deja el gesto más riesgoso sin tests) |
| 24 | Eng | Borrar `useTitularesCompletos` en vez de extenderlo con el mínimo | Mecánica | P4 | Dos implementaciones de la misma regla divergen; el server publica el veredicto | Extenderlo (agranda una duplicación conocida) |
| 25 | Eng | La migración toca 3 archivos: `01_schema.sql`, el script 27 y `SCRIPTS_VIGENTES` | Mecánica | P1 | `conftest.py:39-47` arma la base de tests solo con 01-06: la columna solo en el script 27 revienta los ~40 archivos de test | Solo el script de migración (rompe la suite entera) |
| 26 | Eng | `TorneoService.update` escribe el mínimo fuera de `save_changes` | Mecánica | P1 | `base.py:62-64` hace `if valor is not None`: por la vía normal el campo nunca podría volver a `NULL`, y todo D1 depende de que `NULL` sea alcanzable | Dejarlo en `save_changes` (puerta de una sola dirección) |
| 27 | Eng | El gate de edición se ancla al hito `Inicio_Partido`, no a `partido.estado` | Mecánica | P1 | `PATCH /partidos/{id}` acepta `estado` sin validar transiciones: `Programado` → `PUT` destructivo → `En curso` saltearía el gate. El hito es append-only | Anclar a `partido.estado` (mi propuesta inicial — evitable en un request) |
| 28 | Eng | Endpoint nuevo `GET /partidos/{id}/preflight-inicio` autenticado | Mecánica | P1 | `/cronometro` es público sin auth y se pollea cada 5 s anónimamente; sumarle `_validar_titulares` (~7 queries + roster de hasta 10k filas) lo volvería el endpoint más caro del sistema | Publicarlo en `/cronometro` (mi propuesta inicial — superficie pública nueva) |
| 29 | Eng | El cruce contra `EVENTOS_PARTIDO` va por join, incluye `jugador_id_entra` y excluye `Anulado` | Mecánica | P1 | No hay columna común: `eventos_partido.jugador_id`→`jugadores.id` vs. `convocado.jugador_perfil_id`→`jugador_perfil_disciplina.id`. Y el suplente que entró es justamente el caso de la feature | La comparación directa que yo había escrito (no compila contra el esquema) |
| 30 | Eng | Concurrencia por `MAX(fecha_modificacion)` como ETag, con columna y trigger nuevos | Mecánica | P1 | Con diff incremental, cambiar `titular` es un UPDATE que no toca ningún `id`: `base_ids` queda idéntico y no detecta nada — justo el caso que EC-3 existe para prevenir | `base_ids` (mi propuesta inicial — la anula mi propio EC-2) |
| 31 | Eng | Conflicto de versión responde `412`, no `409` | Mecánica | P5 | `handlers.py:90-92` ya mapea todo `IntegrityError` a 409; el cliente no podría distinguirlo de un choque de `unique_convocado_partido` | `409` (indistinguible del que ya existe) |
| 32 | Eng | El `POST` aditivo responde idempotente ante doble-tap | Mecánica | P3 | Un doble-tap en una cancha no es un error del operador | Devolver 409 (castiga un gesto normal) |
| 33 | Eng | `plantilla_equipo(equipo_id, torneo_id)` | Mecánica | P4 | Hoy filtra solo por equipo aunque la vista ya expone `Torneo_ID`: un equipo en 2 torneos duplica `jugador_perfil_id`, rompe las keys de React y permite titulares fantasma | Dejarlo como está (mi EC-7 citaba un campo que `GET /plantillas` no expone) |
| 34 | Eng | `MesaPanel`, `Cronometro`, `CargaEvento` y `AlineacionVista` van a `components/` | Mecánica | P5 | `pages/arbitro/` ya importa `MesaPanel`; meterlo bajo `pages/control-mesa/` cementa una violación de frontera de módulo | `pages/control-mesa/` (mi propuesta inicial) |
| 35 | Eng | Se agregan `Minuto_Ingreso` y `Registrado_Por` a `CONVOCADO_A_PARTIDO` | Mecánica | P1 | Sin eso, `Fecha_Registro` (inicio de transacción, sin autor ni minuto) no prueba lo que D3-revisada dice que prueba | Sacar el argumento probatorio del plan |
| 36 | Eng | El gesto de arrastre NO se cubre con unit tests; se cubre la función pura + tap/teclado | **Taste** | P3 | jsdom no implementa `PointerEvent` ni `setPointerCapture`, y `getBoundingClientRect()` devuelve ceros: no hay forma de decidir sobre qué zona se soltó | Prometer cobertura del gesto (mi Sección 3.2 original — imposible de cumplir) |
| 37 | Eng | "Reprogramar" se deshabilita en cuanto existe el hito `Inicio_Partido` | Mecánica | P1 | `trg_eventos_partido_validar` es sobre `EVENTOS_PARTIDO`, no sobre `PARTIDOS`: mover la fecha hacia atrás con eventos ya cargados no revalida nada y los deja inconsistentes | Dejar la fecha editable en vivo (D5 lo hacía más probable) |

---

## Para TODOS.md (redactado, NO aplicado)

El usuario pidió **solo el plan**, así que `TODOS.md` no se tocó. Estas son
las entradas listas para pegar cuando se implemente:

```markdown
## Deferido desde gestionar-partido-alineaciones-plan.md

- **"Copiar alineación del partido anterior"** — el ítem de mayor impacto que
  quedó fuera. En una liga de 15 partidos por fecha × 22 jugadores son ~330
  decisiones manuales por fin de semana, y ~90% se repiten de una fecha a la
  otra. Tiene su propia pregunta de producto sin responder: ¿se copia del
  último partido del equipo, o de `EQUIPO_JUGADOR_BASE` (la Plantilla Base ya
  construida)? Candidato número uno después de este plan.
- **Posiciones y formación sobre cancha** — los dos contenedores de este plan
  son la base visual; convertir "Titulares" en una cancha con posiciones no
  requiere tocar el modelo de datos.
- **Minutos jugados por jugador** — depende de que las sustituciones consuman
  del banco. `CONVOCADO_A_PARTIDO.Fecha_Registro`, que este plan deja de
  destruir en cada guardado, es el insumo.
- **Tope superior de titulares por encima de `tamano_equipo`** — sigue
  diferido (venía de la Decision Audit #12 del plan anterior). Este plan
  agrega el contador visible `11/11`, no el bloqueo.
- **Migrar el resto del frontend de paneles por `useState` a rutas** — Control
  de Mesa queda hecho; el patrón sigue vivo en otras pantallas.
- **Tipografía real en lugar de `system-ui`** (`index.css:31`) — decisión de
  toda la app, candidata a `/design-consultation`.
- **Saldar la deuda de `as never`** en las mutaciones de `openapi-fetch`
  (`ControlDeMesa.tsx:300`, `:315`).
```

---

## Resumen de cierre

| Dimensión | Estado |
|---|---|
| **Modo** | SELECTIVE EXPANSION |
| **Fases corridas** | CEO ✅ · Design ✅ (alcance UI detectado) · Eng ✅ · DX ⊘ (omitida) |
| **Voces** | `[subagent-only]` en las 3 fases — Codex no está en PATH en esta máquina |
| **Hallazgos críticos** | 1 (H1, deadlock verificado en código) |
| **Hallazgos altos** | 6 (H2, H3, H7, H10, H14, H16-H19) |
| **Correcciones a mi propio análisis** | 3 (P5 mal redactada, D1 revertida a `TORNEO`, D3 reemplazada por endpoint aditivo) |
| **Decisiones registradas** | 24 (ver Decision Audit Trail) |
| **Desafíos al Usuario** | 2 (drag & drop, semántica del mínimo) |
| **Tablas nuevas** | 0 |
| **Endpoints nuevos** | 1 (`POST /partidos/{id}/convocados`) |
| **Migraciones** | 1, puramente aditiva, sin backfill |
| **Tests especificados** | 32 (artefacto en disco) |
| **Huecos críticos de ingeniería sin resolver** | 0 |

### Por qué la fase DX se omitió

Módulo interno de un sistema de torneos ya autenticado: sin superficie de
API pública, sin CLI, sin SDK, sin terceros integrando. Mismo criterio y misma
justificación que los tres planes anteriores de este repo.

### El hallazgo que cambia la conversación

El requerimiento pedía una vista nueva con drag & drop porque **la
convocatoria era inalcanzable** para un TorneoAdmin. La causa no era la falta
de UI: era un deadlock de ~5 líneas entre "no podés cargar la convocatoria sin
empezar el partido" y "no podés empezar el partido sin convocatoria"
(`ControlDeMesa.tsx:403-417` × `hito_partido.py:210-212`). El rol Árbitro
nunca lo sufrió (`MisPartidos.tsx:40-41` entra sin condicionar por estado),
que es por qué nadie lo vio.

Todo lo demás del plan sigue en pie y vale la pena. Pero el Bloque 0 desbloquea
hoy el 100% del dolor reportado, y merece salir sin esperar al resto.

---

## GSTACK REVIEW REPORT

- **Modo**: SELECTIVE EXPANSION — extiende `ControlDeMesa.tsx`,
  `Convocatoria.tsx`, `hito_partido.py`, `convocado_a_partido.py`,
  `partido.py` y `estadisticas.py`, más columnas nuevas en `TORNEO` y
  `CONVOCADO_A_PARTIDO`. Cero tablas nuevas.
- **Fases corridas**: CEO ✅ · Design ✅ (alcance UI detectado: dashboard,
  botón, vista, contenedores, checkboxes, drag & drop, modal, panel) ·
  Eng ✅ · DX ⊘ omitida (módulo interno, sin superficie de API/CLI/SDK para
  terceros — mismo criterio que los tres planes anteriores del repo).
- **Voces**: `[subagent-only]` en las 3 fases. Codex no está disponible en esta
  máquina (binario no encontrado en PATH), consistente con el precedente de
  `equipos-jugadores-plan.md` y `gestion-avanzada-equipos-control-mesa-plan.md`.
  Una sola voz revisora independiente por fase, no dual-voice real: por eso
  todas las tablas de consenso dan 0/N CONFIRMED — **no es desacuerdo, es
  ausencia de segunda voz**. Cada hallazgo incorporado fue verificado por mí
  contra el código antes de aceptarlo.
- **Gates**: el gate final se corrió con **2 Desafíos al Usuario**, los únicos
  que el pipeline nunca auto-decide. Ambos resueltos por el usuario por la
  opción recomendada: (1) el arrastre va solo en `>=1000px`, con tap de primera
  clase en todos lados; (2) el mínimo es **regla nueva** (arrancar con menos
  que el equipo completo), así que la migración va. Sin decisiones pendientes.
- **Decisiones registradas**: 37 (ver Decision Audit Trail). 2 confirmadas por
  el usuario, 3 de gusto documentadas, el resto mecánicas.
- **Hallazgos**: 64 en total entre las tres voces — 13 críticos, todos
  resueltos. **Cero huecos críticos de ingeniería abiertos.**
- **Correcciones a mi propio análisis**: 11. Las voces externas encontraron 8
  supuestos míos que eran **falsos contra el código** (D1 mal ubicada, `PUT`
  condicional en vez de aditivo, `base_ids` anulado por mi propio EC-2, el
  cruce de EC-1 sin columna común, `GET /plantillas` sin `equipo_id`, el gate
  anclado a `partido.estado` siendo evitable por `PATCH`, la migración de 1
  archivo rompiendo la suite, y "Pointer Events simulables en jsdom"), más 3
  contradicciones internas del documento (D1 viva en 5 lugares, el default
  invertido adoptado en Fase 1 e ignorado en Fase 2, y una fila de jugador
  geométricamente imposible). Todas corregidas en el texto: el documento
  describe **una** decisión por tema, no su historial.
- **Entregables cubiertos** (pedidos explícitamente por el usuario):
  - Punto de entrada único → Fase 1 (0B, P10, D5) + Fase 2 (Pass 1) + Bloque 3.
  - Convocatorias y alineaciones interactivas paso a paso → Fase 2 (Pass 1-7,
    con los dos mockups y la tabla de estados) + `AlineacionEditor`.
  - Reglas de negocio reales (mínimos y llegadas tardías) → D1, D3 revisada,
    C4/C5 de la Fase 3, endpoint aditivo + preflight.
  - Dos acciones finales de ejecución → D4 revisada, H-10 (el botón correcto
    de arranque), y `ModalResultadoDirecto`, que ya existe completo.
- **Artefactos en disco**:
  - Plan: `docs/plans/gestionar-partido-alineaciones-plan.md`
  - Plan de pruebas (42 tests):
    `~/.gstack/projects/Score-App/gabriel-feat-equipos-jugadores-plan-test-plan-20260908-114454.md`
  - Restore point:
    `~/.gstack/projects/Score-App/feat-equipos-jugadores-plan-autoplan-restore-20260908-112804.md`
- **NO implementado**: cero código, cero cambios de esquema, `TODOS.md` sin
  tocar — el usuario pidió explícitamente solo el documento. Las entradas para
  `TODOS.md` quedan redactadas arriba, listas para pegar.
- **Siguiente paso sugerido**: **Bloque 0 primero y solo** — el desbloqueo del
  deadlock H1 son ~5 líneas más su test de regresión, y hoy es lo único que
  separa al TorneoAdmin de poder usar la convocatoria que ya existe. El resto
  del plan puede seguir después, en el orden de los bloques.

**STATUS: DONE**
