# Plan: Corrección de Bugs de Alta Local + Traspasos (Búsqueda Inteligente) + Control de Mesa (Titulares)

Generado con `/autoplan` (revisión CEO → Design → Eng). Codex no está
disponible en esta máquina (`codex` no está en PATH) — corrió en modo
`[subagent-only]`, una sola voz revisora (Claude), mismo precedente que
`docs/plans/equipos-jugadores-plan.md` y
`docs/plans/gestion-avanzada-equipos-control-mesa-plan.md` para este
mismo repo. A diferencia de esos dos planes, acá la "segunda mirada" no
fue un segundo modelo sino verificación directa contra el código real
antes de escribir cada hallazgo — ningún diagnóstico de este documento
se apoya en "debería ser así", todos citan archivo:línea.

**Solo documento — sin implementación.** El usuario pidió explícitamente
el plan, no código. El gate final de aprobación de `/autoplan` (Fase 4)
no aplica por el mismo motivo que en los dos planes anteriores.

**Entorno de referencia usado para el diagnóstico:** torneo ID 87
("Gabriel Prueba Cup"). Los IDs que cita el reporte del usuario (equipo
`#276`, perfiles `#1763`/`#1464`) fueron la pista que confirmó la causa
real del Bug 2 — ver P3/D2 más abajo.

---

## Resumen ejecutivo (para no perderse en el documento)

| # | Ítem pedido | Es... | Alcance de este plan |
|---|---|---|---|
| Bug 1 | Equipo creado con 0 jugadores | **Bug real, confirmado leyendo el código** (D1) | Fix acotado, 2 archivos |
| Bug 2 | "Equipo #276" / "perfil#1763" en vez del nombre real | **No es un bug de guardado — es de lectura** (D2). El nombre SÍ se guarda bien; lo que falla es cómo algunas pantallas resuelven el nombre a partir del ID | Fix acotado, sin backend nuevo |
| A. Traspasos — búsqueda inteligente | Pedido nuevo, **patrón ya existe en otra pantalla** (P6) | Reusar `ModalBuscarAgregarJugador` (`DetalleEquipo.tsx`), no reinventar |
| A. Autocompletado de origen | Pedido nuevo, **el endpoint que hace falta ya existe** (P7) | Solo frontend |
| A. Sugerencia de dorsal | Pedido nuevo, **el endpoint que hace falta ya existe** (P7) | Solo frontend |
| B.1 Convocatorias (roster pre-partido) | **Ya implementado** (P8, 3B-2, 2026-09-02) | Nada que hacer — se documenta para que quede claro que no es un gap |
| B.2 Validar titulares al iniciar partido | Pedido nuevo, **gap real confirmado** (P10) | Fix acotado, backend + frontend |
| B.3 Registro de sucesos (goles/tarjetas/marcador) | **Ya implementado** (P9) | Nada que hacer |

La mitad de "Parte B" del reporte del usuario ya está en producción. El
trabajo real de este plan es: 1 bug de relación rota, 1 bug de
UX de nombres (no de datos), 1 pantalla de UX nueva (Traspasos) y 1
validación de negocio nueva (titulares al iniciar partido).

---

## Fase 1 — CEO Review (Estrategia y Alcance)

### Premisas

| # | Premisa | Veredicto |
|---|---|---|
| P1 | El botón "Validar y crear" que describe el usuario es `ModalEquipo` dentro de `ModalAgregarInscripcion.tsx` (línea 546: texto exacto `"Validar y crear"`), alcanzado desde `/torneo-admin/torneos/{id}/equipos` → "+ Agregar Equipo" → "+ Crear equipo nuevo". | Confirmado — coincide con la ruta que dio el usuario. |
| P2 | **Bug 1, causa raíz confirmada:** `crearYRegistrar.mutate()` (`ModalAgregarInscripcion.tsx:351-370`) hace `POST /equipos` y `POST /inscripciones`, y **nunca envía `filas`** (los jugadores que el admin tipeó en la tabla del modal) a ningún endpoint. Tampoco los pasa a la pantalla siguiente: `RegistroLotePreResuelto` (línea 15-22) solo lleva `inscripcionTorneoId`/`contexto`/`volverA`, y `RegistroLoteAdminPage` arranca su estado `filas` con una fila vacía fija (`RegistroLoteAdmin.tsx:102`, ignora todo lo pre-resuelto salvo esos 3 campos). El admin tipea la plantilla, aprieta "Validar y crear", y esos datos se descartan en silencio — nunca hubo un INSERT que fallara, nunca se intentó ninguno. | Confirmado leyendo el código, no inferido. |
| P3 | **Bug 2, causa raíz confirmada — NO es lo que el reporte asume.** `EquipoService.create` (`backend/app/services/equipo.py:38-44`) persiste `data.model_dump()` tal cual — el `nombre` real llega y se guarda bien; no hay ningún fallback a `f"Equipo {id}"` en el backend (se buscó explícitamente, no existe). Lo que el usuario ve como "guardado como Equipo #276" es el resultado de un patrón de **fallback de LECTURA** repetido en 7+ lugares del frontend: `nombreEquipo.get(id) ?? \`Equipo #${id}\`` (`EquiposDelTorneo.tsx:236/275`, `PlantillasDelTorneo.tsx:120`, `MotorFormatosPanel.tsx:188`, `RegistroLoteAdmin.tsx:144-145`, `ControlDeMesa.tsx:485-486`) y su equivalente `\`Perfil #${perfilId}\`` (`ModalGestionarPlantilla.tsx:84`, `TraspasosDelTorneo.tsx:75`). Ese `Map` se arma desde un GET **sin filtrar**, `ORDER BY id ASC LIMIT 200` (`backend/app/repositories/base.py:39`, `LIMITE_LISTA = 200` en `useResourceCrud.ts:40`). Un equipo/perfil recién creado en un entorno con miles de filas de prueba previas (torneo 87 las tiene: los IDs 276/1763/1464 que cita el reporte están muy por encima de 200) cae fuera de esa ventana de 200 y su nombre nunca se resuelve — aunque esté perfecto en la base de datos. | Confirmado — se verificó que el INSERT guarda el nombre real y se identificó exactamente el punto de falla en la lectura. |
| P4 | Este patrón capado-a-200-sin-filtro **ya está documentado como deuda** en `TODOS.md`, sección "Deferido desde el plan de Equipos con Disciplina + Navegación": *"Paginación real con cursor en `/equipos` (y ahora también `/jugadores`)... sigue pendiente. En curso, pero con ciclo propio (cambio de contrato de API)"* (§3B-9). El Bug 2 reportado es la manifestación visible de esa brecha ya conocida, no una regresión nueva de este flujo. | Confirmado contra `TODOS.md`. |
| P5 | El backend **ya expone** búsqueda por nombre/cédula: `GET /jugadores?q=` (`backend/app/api/routes/jugadores.py:48`, repositorio hace `Jugador.nombre.ilike(patron) OR Jugador.cedula.ilike(patron)`, `backend/app/repositories/jugador.py:20-29`). El picker de Traspasos hoy NO lo usa — arma un `<select>` genérico (`ResourceForm`, `type: "reference"` es un `<select>` HTML plano, `ResourceForm.tsx:91-106`) sobre listas capadas a 200 sin `q=` (`TraspasosDelTorneo.tsx:50-76`), que es exactamente por qué el usuario ve `perfil#1763` en ese dropdown. | Confirmado — el backend ya resuelve la mitad del Requerimiento A sin cambios. |
| P6 | El patrón de búsqueda con debounce que pide el Requerimiento A **ya existe, funciona y está en producción** en `DetalleEquipo.tsx` (`ModalBuscarAgregarJugador`, líneas 182-369): input con debounce de 300ms (`useDebouncedEffect`, función local líneas 361-369) → `GET /jugadores?q=` → lista de resultados con "Nombre — Cédula" → alta rápida si no hay match. Construido para la Plantilla Base (`gestion-avanzada-equipos-control-mesa-plan.md`, Flujo 2). | Confirmado — es el componente a **reusar**, no a reconstruir (P4 DRY). Ver D3. |
| P7 | `GET /plantillas?jugador_perfil_id=X` (`backend/app/api/routes/plantillas.py:34-44`) **ya acepta ese filtro solo**, sin necesitar `torneo_id` — devuelve TODOS los vínculos históricos de ese perfil en cualquier torneo/equipo. Alcanza para las dos piezas de UX del Requerimiento A sin backend nuevo: (a) filtrando client-side por `estado='Activo'` + el `torneo_id` actual se resuelve "equipo de origen" o "Agencia Libre"; (b) juntando los `dorsal` no nulos de todos los vínculos (de cualquier torneo) se arma el historial de dorsales. | Confirmado — no hace falta ningún endpoint nuevo para el Requerimiento A. |
| P8 | **Requerimiento B.1 (Convocatorias/roster pre-partido) ya está implementado.** Tabla `CONVOCADO_A_PARTIDO` (`backend/app/models/convocado_a_partido.py`), servicio y endpoints `GET/PUT /partidos/{id}/convocados`, componente `Convocatoria.tsx` con checkbox de "Convocado" + "Titular" por jugador de cada plantel. Cerrado como 3B-2 el 2026-09-02 (`TODOS.md`, sección "Frontend — deferido desde el design doc..."). | Confirmado — este plan no reconstruye nada acá. |
| P9 | **Requerimiento B.3 (goles/tarjetas/marcador con minuto) ya está implementado.** `MesaPanel` (`ControlDeMesa.tsx`) ya registra `Gol/Autogol/Tarjeta Amarilla/Tarjeta Roja/Cambio` con `minuto` obligatorio (`EventoBody`, línea 26-33; `TIPOS`, línea 41-42) contra `POST /eventos-partido`, y el marcador se calcula en vivo a partir de esos eventos (línea 342-345 y 492-495), mismo criterio que `vw_goles_acreditados`. | Confirmado — este plan no reconstruye nada acá. |
| P10 | **El único gap real de la Parte B es el Requerimiento B.2.** El botón "▶ Empezar Partido" (`ControlDeMesa.tsx:145-148`) llama a `empezarPartido.mutate(p.id)` (línea 95-108), que hace `POST /partidos/{id}/hitos {tipo_hito: "Inicio_Partido"}` sin ninguna validación de plantilla. Del lado del backend, `HitoPartidoService.registrar` (`backend/app/services/hito_partido.py:106-143`) valida secuencia de hitos (`acciones_permitidas`) pero nunca composición de titulares — el partido arranca aunque nadie haya tocado "Convocados". | Confirmado — gap real, sin protección en ninguna capa. |
| P11 | `Modalidad.tamano_equipo` (`backend/app/models/modalidad.py:25`) ya significa, literalmente, "cuántos juegan a la vez" (comentario propio del modelo) — `RegistroLoteService` ya lo usa con ese sentido exacto para el tope de cupo (EC-6, `equipos-jugadores-plan.md`). Es la fuente de verdad correcta para "cuántos titulares exige esta modalidad", sin inventar un catálogo nuevo de reglas por disciplina. El ejemplo del usuario ("Fútbol 7") es ilustrativo, no literal: hoy el catálogo solo tiene sembrada "Fútbol 11" (`database/05_seed.sql:28-68`) — el catálogo es inmutable salvo migración SQL (`TODOS.md` §3B-11), así que la validación de B.2 debe leer `tamano_equipo` en runtime, nunca un número hardcodeado. El día que se migre "Fútbol 7" (fuera de alcance de este plan), la regla ya lo respeta sin tocar código. | Confirmado — evita inventar esquema nuevo. |
| P12 | Todos los `PARTIDOS` que hoy existen son de disciplinas de Equipo/Pareja (`Modalidad.tamano_equipo >= 2`): el Motor de Formatos filtra `equipo_id IS NOT NULL` al generar partidos y las disciplinas Individuales (`tamano_equipo == 1`) se inscriben directo sin fila en `EQUIPOS` (Decisión B1, `equipos-disciplina-navegacion-plan.md`) — no llegan al Motor de Formatos en absoluto. | Aceptada — la validación de B.2 no necesita una rama especial para "sin equipo", el caso no existe hoy en `PARTIDOS`. |

### D1 — Bug 1: cómo reconectar la relación Equipo↔Jugador

**La pregunta:** ¿dónde deben terminar los datos de `filas` (la tabla de
jugadores que el admin llena dentro del modal "Crear equipo nuevo")?

| Alternativa | Completeness | Veredicto |
|---|---|---|
| **A. Pasar `filas` a la pantalla de Registro por Lote y dejar que el flujo de revisión existente (válidos/inválidos, EC-1 a EC-9) haga el resto** (elegida) | 9/10 | Agregar `filasIniciales` a `RegistroLotePreResuelto` (`ModalAgregarInscripcion.tsx:15-22`), poblarlo en el `onSuccess` de `crearYRegistrar`, y usarlo como valor inicial de `useState<Fila[]>` en `RegistroLoteAdminPage` (`RegistroLoteAdmin.tsx:102`) en vez del array fijo de una fila vacía. Es literalmente completar la intención que el propio comentario del código ya declaraba: *"encadenando a la pantalla dividida de Registro por Lote — P4 DRY, no se reconstruye ese flujo acá"* (`ModalAgregarInscripcion.tsx:55-57`) — el enganche se diseñó, solo faltó pasar el dato. |
| B. Que `crearYRegistrar` llame directo a `POST /plantillas/lote/validar` + `/confirmar` dentro del mismo modal, sin pasar por la pantalla dividida | 6/10 | Evita un salto de pantalla, pero tira la validación dividida (ver qué filas son válidas/inválidas con motivo) que EC-1 a EC-9 ya construyeron y probaron — si algo sale mal, el admin queda sin la UI para corregir ahí mismo. |
| C. Bloquear "Validar y crear" hasta que las filas tengan 0 errores obvios en el modal mismo, sin backend hasta confirmar | 4/10 | No revalida contra la base (EC-7, condición de carrera) — reintroduce exactamente el bug que `_validar_lote` ya resuelve. Rechazada por P1 (completeness). |

**Decisión: A.** Costo: un campo nuevo en una interfaz TypeScript + una
línea de inicialización de estado. Sin cambios de backend, sin cambios
de contrato de API.

**Edge case cubierto sin código extra:** equipo creado sin plantilla
(`filas` vacías) — mismo comportamiento que hoy (EC-22 ya dice que 0
jugadores es válido), la pantalla dividida arranca con una fila vacía
igual que si `filasIniciales` no existiera.

### D2 — Bug 2: resolver nombres reales sin construir la paginación con cursor completa (alcance acotado)

| Alternativa | Completeness | Veredicto |
|---|---|---|
| A. Paginación real con cursor + búsqueda server-side en `equipos`/`jugadores`/`perfiles` | 10/10 | Es exactamente lo que `TODOS.md` §3B-9 ya reconoció como "en curso, con ciclo propio" (rompe el contrato de API que asume offset). Rechazada **para este plan** por alcance — no se re-abre acá, sigue siendo su propio ciclo en `TODOS.md`. |
| **B. Resolución dirigida bajo demanda: cuando un ID no aparece en el mapa capado-a-200, pedirlo individual (`GET /equipos/{id}`, `GET /jugadores/{id}` — ya existen, sin backend nuevo) y cachearlo con React Query** (elegida, parte 1) | 8/10 | Elimina el síntoma exacto reportado (ver un placeholder para una fila que sí tiene nombre real) sin tocar el contrato de ningún endpoint. No resuelve el techo de 200 para LISTAR — eso sigue siendo 3B-9. |
| **C. Acotar cada consulta al alcance real de la pantalla, donde ya hay filtro disponible y gratis** (elegida, parte 2) | — (complementa a B) | `PlantillasDelTorneoPage`'s `equipos` (`PlantillasDelTorneo.tsx:74`) y `TraspasosDelTorneo.tsx:61` piden el catálogo GLOBAL de equipos sin `disciplina_id`, a diferencia de `EquiposDelTorneo.tsx:180-184` que sí filtra — mismo dato (`disciplinaId`) ya disponible vía `useOutletContext` en las tres pantallas. Reduce la ventana de 200 a algo realista sin ser una garantía matemática por sí sola (de ahí que B siga haciendo falta). |

**Decisión: B + C combinadas.** Ningún endpoint nuevo. Cambio en 3
archivos de frontend (ver Fase 3, "Cambios por archivo").

### D3 — Traspasos: reusar el buscador, no reinventarlo

Confirmado en P6: `ModalBuscarAgregarJugador` (`DetalleEquipo.tsx:182-369`)
ya resuelve "buscar por nombre o cédula con debounce" y ya está probado en
producción. Construir un componente nuevo desde cero para Traspasos
violaría P4 (DRY) y el principio de "reuse ladder" del proyecto — la
única pieza reutilizable de verdad hoy es una función local no exportada
(`useDebouncedEffect`, líneas 363-369) atada a ese archivo.

**Decisión:** extraer `useDebouncedEffect` a un hook compartido
(`frontend/src/hooks/useDebouncedValue.ts`) y construir un componente
`SelectorJugadorBuscable` (nombre tentativo) reutilizable que encapsule
"input + debounce + `GET /jugadores?q=` + lista de resultados", usado
por Traspasos (obligatorio para este plan). Se **recomienda, sin ser
bloqueante**, migrar `DetalleEquipo.tsx` y el buscador ad-hoc de
`ModalIndividual` (`ModalAgregarInscripcion.tsx:107-229`, hoy filtra en
memoria sobre la lista completa de jugadores en vez de usar `?q=`) al
mismo componente — ambos quedarían gratis arreglados del mismo techo de
200 que afecta a Bug 2, pero no son parte del pedido explícito del
usuario, así que quedan anotados como mejora opcional, no como tarea de
este plan (ver "Fuera de alcance").

### Qué ya existe (leverage map)

| Sub-problema | Ya cubierto por | Qué falta |
|---|---|---|
| Crear equipo con nombre real | `POST /equipos`, `EquipoService.create` | Nada — ya funciona (P3) |
| Buscar jugador por nombre/cédula (server-side) | `GET /jugadores?q=` | Nada en backend — conectarlo en Traspasos (frontend) |
| UI de búsqueda con debounce | `ModalBuscarAgregarJugador` (`DetalleEquipo.tsx`) | Extraer a componente compartido, usar en Traspasos |
| Historial de vínculos de un perfil (cualquier torneo) | `GET /plantillas?jugador_perfil_id=X` | Nada en backend — leerlo en el form de Traspasos |
| Validar exclusividad/estado actual en un torneo | `JugadorEquipoRepository.get_activo_en_torneo` (usado en `registro_lote.py`) | Ya alcanza vía el mismo `GET /plantillas` filtrado client-side |
| Convocatoria/titular por partido | `CONVOCADO_A_PARTIDO`, `Convocatoria.tsx`, `GET/PUT /partidos/{id}/convocados` | Nada — ya funciona (P8) |
| Registro de goles/tarjetas/marcador | `MesaPanel`, `POST /eventos-partido` | Nada — ya funciona (P9) |
| Secuencia de hitos del partido (Inicio/Fin/Pausa) | `HitoPartidoService._calcular_estado` | Agregar el chequeo de titulares ANTES de aceptar `Inicio_Partido` |
| "Cuántos titulares exige esta modalidad" | `Modalidad.tamano_equipo` | Nada — ya significa eso (P11) |

### Alcance

**Dentro de este plan:**
- Fix Bug 1: `filasIniciales` en el enganche modal→pantalla-dividida.
- Fix Bug 2: resolución dirigida por ID + filtro por `disciplina_id` donde ya está disponible, en las 3 pantallas señaladas.
- Traspasos: selector de jugador buscable (componente nuevo, reusa `?q=`), autocompletado de "Equipo de origen" (o "Agencia Libre"), chips de dorsal histórico.
- Control de Mesa: validación de titulares por modalidad al registrar el hito `Inicio_Partido`, en backend (fuente de verdad) y en frontend (UX: deshabilitar/explicar el botón antes de que el admin lo intente).

**Fuera de este plan (→ `TODOS.md`):**
- Paginación real con cursor de `/equipos`/`/jugadores`/`/perfiles` — sigue siendo §3B-9, este plan no lo reabre (D2 lo acota a mitigación, no solución de fondo).
- Migrar `DetalleEquipo.tsx` y `ModalIndividual` al componente de búsqueda compartido nuevo — mejora recomendada, no pedida explícitamente (D3).
- Catálogo de "Fútbol 7" u otras modalidades nuevas — la validación de B.2 ya es genérica contra `tamano_equipo`, no requiere tocar el catálogo (P11).
- Notificación al jugador traspasado — ya está aparcado en `TODOS.md` desde el plan anterior, no se reabre.
- Convertir la Convocatoria de opt-in a obligatoria para TODO flujo de Control de Mesa — la validación de B.2 solo mira si hay suficientes titulares marcados al momento de "Empezar Partido"; no obliga a usar Convocatoria en ningún otro momento del partido (ver D4 para el detalle exacto de qué se exige y qué no).

### Dream state

```
ACTUAL                              ESTE PLAN                          IDEAL 12 MESES
──────────────────────              ──────────────────────             ──────────────────────
Crear equipo con plantilla           La plantilla tipeada en el          + Un componente único
pierde los jugadores tipeados        modal viaja a Registro por           de "resolver nombre por
en el modal (Bug 1).                 Lote y se confirma ahí               ID" con caché y fetch
                                      (mismo flujo ya probado).            dirigido, sin que cada
Nombres reales invisibles                                                 pantalla arme su propio
detrás de un placeholder            IDs fuera de la ventana de           Map desde una lista
numérico cuando el ID cae            200 se resuelven al vuelo,           capada — resuelve 3B-9
fuera de una ventana de 200          sin esperar la paginación            de una vez.
filas sin que nadie lo note          real con cursor.
(Bug 2).                                                                + Búsqueda unificada de
                                     Traspasos: buscar por nombre/         jugador (un solo
Traspasos: dropdown con              cédula, origen/Agencia Libre         componente) en las 3
"perfil#ID", origen manual,          autocompletado, dorsal               pantallas que hoy lo
sin pista de dorsal histórico.       sugerido con un clic.                hacen cada una a su
                                                                           manera.
Cualquiera puede arrancar un        "Empezar Partido" exige
partido sin haber definido          titulares completos según
titulares.                          Modalidad.tamano_equipo,
                                     con mensaje claro de qué
                                     falta.
```

---

## Fase 2 — Design Review (UX)

Aplica — hay una pantalla nueva de verdad (Traspasos: selector buscable +
2 campos autocompletados + chips) y un nuevo estado bloqueante en un
flujo existente (Control de Mesa).

### Flujo 1 — Fix de "Crear equipo nuevo" (sin cambio visual)

```
[Modal "Crear equipo nuevo"]  (ModalAgregarInscripcion.tsx — sin cambios de UI)
  Nombre + tabla de filas (Cédula, Nombre, Correo, Dorsal)
        │ "Validar y crear"
        ▼
POST /equipos ──▶ POST /inscripciones ──▶ navigate(/torneo-admin/plantillas/lote,
                                             { inscripcionTorneoId, contexto, volverA,
                                               filasIniciales: filas })  ← ÚNICO cambio
        ▼
[Pantalla dividida de Registro por Lote]  (RegistroLoteAdmin.tsx — sin cambios de UI)
  arranca con las filas YA CARGADAS, el admin aprieta "Validar" como
  siempre — ve la sección Válidos/Inválidos con los mismos jugadores que
  acaba de tipear, no una tabla vacía a medio llenar de nuevo.
```

No hay ningún estado nuevo que diseñar: la pantalla dividida ya cubre
loading/empty/error/éxito-parcial (Fase 2 de `equipos-jugadores-plan.md`).
El único cambio de comportamiento visible para el admin es que **ya no
tiene que volver a tipear lo que acaba de escribir**.

### Flujo 2 — Traspasos: selector buscable + autocompletados

```
[Traspasos de esta edición] "+ Nuevo traspaso"
        ▼
┌──────────────────────────────────────────────┐
│ Jugador                                        │
│ [Buscar por nombre o cédula...________]        │  ← reemplaza el <select>
│  • Juan Pérez — 12345678                       │     (SelectorJugadorBuscable,
│  • Juana Pérez — 87654321                      │      debounce 300ms, GET /jugadores?q=)
├──────────────────────────────────────────────┤
│ Equipo de origen: Halcones FC        (auto)    │  ← read-only, se llena solo
│   — o —                                        │     al elegir el jugador
│ Equipo de origen: Agencia Libre      (auto)    │     (GET /plantillas?jugador_perfil_id=X
├──────────────────────────────────────────────┤     &torneo_id=87, busca fila Activo)
│ Equipo destino                                 │
│ [Águilas Doradas ▾]  (select normal — lo       │
│  elige el operador, sin cambios acá)           │
├──────────────────────────────────────────────┤
│ Dorsal nuevo                                   │
│ [___]                                          │
│ Dorsales usados antes: [7] [10] [23]           │  ← chips clicables
│  (histórico del jugador, cualquier torneo —     │     (GET /plantillas?jugador_perfil_id=X,
│   clic en un chip = precarga el input)          │      dorsales distintos, sin repetir)
├──────────────────────────────────────────────┤
│ Motivo (opcional)                              │
│ [___________]                                  │
│           [Cancelar]   [Traspasar]             │
└──────────────────────────────────────────────┘
```

Estados de interacción:

| Estado | Comportamiento |
|---|---|
| Sin texto de búsqueda | Sin resultados mostrados, sin llamar a la API (mismo criterio que `DetalleEquipo.tsx`: `enabled: textoDebounced.trim() !== ""`). |
| Búsqueda sin resultados | "Ningún jugador coincide con '{texto}'." — no ofrece "crear jugador nuevo" acá (a diferencia de Plantilla Base): un traspaso es sobre un jugador que YA existe en algún lado del sistema; si no aparece, es un dato de búsqueda, no un alta. |
| Jugador elegido, sin membresía activa en este torneo | "Equipo de origen: Agencia Libre" — texto literal, no vacío ni "—" (pedido explícito del usuario). |
| Jugador elegido, con membresía activa en este torneo | "Equipo de origen: {nombre real}" — resuelto, nunca `Perfil #ID`. |
| Jugador sin ningún dorsal histórico | Fila de chips no se muestra (sección vacía se oculta, mismo criterio que el resto del sistema — nunca un panel vacío con encabezado). |
| Click en un chip de dorsal | Precarga el input "Dorsal nuevo" con ese valor — el admin puede seguir editándolo a mano después. |
| Cambiar el jugador buscado después de haber elegido uno | Resetea origen/dorsal-sugerido (evita mostrar el origen del jugador anterior con el nombre del nuevo). |

### Flujo 3 — Control de Mesa: bloqueo de "Empezar Partido" sin titulares completos

```
[/control-de-mesa] fila de un partido "Programado"
        │ click "▶ Empezar Partido"
        ▼
POST /partidos/{id}/hitos {tipo_hito: "Inicio_Partido"}
        │
        ├── titulares completos en ambos equipos ──▶ arranca igual que hoy
        │                                              (Inicio_Partido, estado → "En curso")
        │
        └── faltan titulares ────────────────────────▶ 409 con mensaje específico:
                                                          "Halcones FC tiene 5 titulares
                                                          marcados, esta modalidad exige 7.
                                                          Definí la convocatoria antes de
                                                          empezar el partido."
                                                                  │
                                                                  ▼
                                                         Frontend: en vez de un error-text
                                                         genérico, el botón "▶ Empezar
                                                         Partido" pasa a estar deshabilitado
                                                         de entrada si el chequeo (mismo
                                                         cálculo, hecho client-side con los
                                                         datos que Convocatoria.tsx ya trae)
                                                         no da los titulares exigidos, con un
                                                         link directo "Definir convocatoria"
                                                         que abre el mismo panel de Convocatoria
                                                         (ya existe, Convocatoria.tsx) — el
                                                         admin nunca ve el 409 en el camino
                                                         feliz, solo si hay una carrera entre
                                                         dos pestañas.
```

Estados de interacción:

| Estado | Comportamiento |
|---|---|
| Sin convocatoria guardada en absoluto | Botón deshabilitado con tooltip/texto "Definí la convocatoria (0 de N titulares) antes de empezar" — nunca un botón habilitado que falla recién al hacer click. |
| Convocatoria guardada, titulares incompletos en un solo equipo | Mismo bloqueo, mensaje nombra el equipo específico que falta (no "faltan titulares" genérico). |
| Convocatoria guardada, titulares completos en ambos | Botón habilitado, comportamiento idéntico al actual. |
| Carrera: dos pestañas, una arranca el partido mientras la otra edita convocatoria | El backend es la fuente de verdad (409 explícito) — el frontend recalcula tras el error y vuelve a deshabilitar el botón, no se queda en un estado inconsistente. |
| Modalidad Pareja (`tamano_equipo == 2`) | Misma regla, exige exactamente 2 titulares por lado — no es un caso especial, es el mismo número genérico (P11). |

### Litmus scorecard (resumen)

| Dimensión | Score |
|---|---|
| Jerarquía de información (Traspasos: jugador → origen derivado → destino elegido → dorsal, en ese orden causal) | 9/10 |
| Estados especificados (tablas arriba, ningún estado dejado a interpretación) | 9/10 |
| Especificidad (mensaje de titulares nombra equipo y números reales, no "faltan titulares") | 9/10 |
| Alineación con patrones existentes (reusa `ModalBuscarAgregarJugador`, `Convocatoria.tsx`, mismo criterio de chips que no existía antes — único elemento visual genuinamente nuevo) | 8/10 |
| Responsive / uso desde celular en cancha (Control de Mesa) | Hereda el criterio ya establecido en `gestion-avanzada-equipos-control-mesa-plan.md` ("2-3 toques, sin tipear") — el bloqueo del botón es una lectura, no un formulario nuevo, no compromete ese criterio. |

---

## Fase 3 — Eng Review (Arquitectura, Datos, Edge Cases, Tests)

### Arquitectura

```
Frontend (Vite)                              Backend (FastAPI)                    DB (Postgres)
────────────────                              ──────────────────                   ─────────────
ModalAgregarInscripcion.tsx (ModalEquipo)                                          (sin cambios de
  crearYRegistrar.onSuccess                                                         esquema en todo
  agrega filasIniciales: filas    ──────▶  navigate(state) — sin red nueva          este plan)
        │
        ▼
RegistroLoteAdmin.tsx
  useState<Fila[]>(preResuelto?.filasIniciales ?? [FILA_VACIA])
  resto del flujo sin cambios          ──▶  POST /plantillas/lote/validar
                                             POST /plantillas/lote/confirmar
                                             (ya existen, sin cambios)

PlantillasDelTorneo.tsx / TraspasosDelTorneo.tsx
  equipos query: agrega { disciplina_id }  ──▶  GET /equipos?disciplina_id=X
  resolverNombreFaltante(id)               ──▶  GET /equipos/{id}  (fetch dirigido,
                                                  solo si el id no está en el mapa,
                                                  cacheado por queryKey ["equipo", id])
  mismo patrón para jugadores/perfiles     ──▶  GET /jugadores/{id}

TraspasosDelTorneo.tsx (nuevo)
  SelectorJugadorBuscable               ──▶  GET /jugadores?q=...        (ya existe)
  useOrigenAutocompletado(perfilId,
    torneoId)                           ──▶  GET /plantillas?jugador_perfil_id=X
                                              &torneo_id=torneoId   (ya existe, se
                                              filtra client-side por estado=Activo)
  useDorsalesHistoricos(perfilId)       ──▶  GET /plantillas?jugador_perfil_id=X
                                              (ya existe, sin torneo_id — se
                                              deduplican los `dorsal` no nulos)

ControlDeMesa.tsx (ControlDeMesaPage)
  useTitularesCompletos(partidoId)      ──▶  GET /partidos/{id}/convocados  (ya existe)
                                         ──▶  GET /modalidades/{id}         (ya existe,
                                              para tamano_equipo)
  botón "Empezar Partido" deshabilitado
  si el cálculo local no cierra

                                         POST /partidos/{id}/hitos
                                           {tipo_hito: "Inicio_Partido"}
                                                │
                                                ▼
                                    HitoPartidoService.registrar()  ── NUEVO: valida
                                      (hito_partido.py:106)             titulares antes
                                                │                        de crear el hito
                                                ▼
                                    _validar_titulares_inicio(partido)  ── nuevo método
                                      - resuelve torneo → modalidad → tamano_equipo
                                      - resuelve roster activo de cada equipo
                                        (JugadorEquipoRepository, ya existe)
                                      - cuenta ConvocadoAPartido.titular=True cuyo
                                        jugador_perfil_id está en ese roster
                                      - 409 DomainRuleError si algún lado no llega
                                                │
                                                ▼
                                          HITOS_PARTIDO  (sin cambios de esquema)
```

### Cambios por archivo

**Bug 1 (D1):**
- `frontend/src/pages/torneo-admin/torneo-dashboard/ModalAgregarInscripcion.tsx`
  - `RegistroLotePreResuelto`-adjacent: agregar `filasIniciales: FilaPlantilla[]` (o el tipo `Fila[]` que use `RegistroLoteAdmin.tsx`, homologar nombres de campo si difieren) al objeto de navegación en `crearYRegistrar.onSuccess` (línea ~372-381).
- `frontend/src/pages/torneo-admin/RegistroLoteAdmin.tsx`
  - `RegistroLotePreResuelto` (interfaz, línea 15-22): agregar el campo opcional `filasIniciales?: Fila[]`.
  - Línea 102: `useState<Fila[]>(preResuelto?.filasIniciales?.length ? preResuelto.filasIniciales : [{ ...FILA_VACIA }])`.

**Bug 2 (D2):**
- `frontend/src/pages/torneo-admin/torneo-dashboard/PlantillasDelTorneo.tsx` (línea 74): agregar `listParams: { disciplina_id: disciplinaId }` a la query de `equipos` (mismo patrón que `EquiposDelTorneo.tsx:180-184`).
- `frontend/src/pages/torneo-admin/torneo-dashboard/TraspasosDelTorneo.tsx` (línea 61): mismo cambio.
- Nuevo hook compartido `frontend/src/hooks/useResolverNombreFaltante.ts` (o similar): dado un `Map<id, nombre>` ya construido y la lista de IDs realmente referenciados en la pantalla, dispara `GET /equipos/{id}` (o `/jugadores/{id}`) solo para los IDs ausentes del mapa, vía `useQueries` de React Query (uno por ID faltante, cacheado por `queryKey: ["equipo", id]` — no compite con el `queryKey: ["equipos"]` de la lista capada). Aplicar en los 3 archivos de la tabla de P3 que arman `nombreEquipo`/`etiquetaJugador`.

**Traspasos (D3):**
- Nuevo: `frontend/src/hooks/useDebouncedValue.ts` — extraído de `useDebouncedEffect` (`DetalleEquipo.tsx:363-369`), misma firma, exportado.
- Nuevo: `frontend/src/components/admin/SelectorJugadorBuscable.tsx` — extraído de `ModalBuscarAgregarJugador` (`DetalleEquipo.tsx:185-359`), generalizado para no asumir "agregar a un equipo" sino simplemente "elegir un `JugadorRow`" (callback `onElegir(jugador)`), sin la parte de multimilitancia (no aplica a Traspasos).
- `frontend/src/pages/torneo-admin/torneo-dashboard/TraspasosDelTorneo.tsx`:
  - Reemplazar el campo `jugador_perfil_id` (`type: "reference"`, línea 89-95) por `SelectorJugadorBuscable` fuera de `ResourceForm` (mismo criterio que ya usa `ModalAgregarInscripcion` para su propio buscador — no todo tiene que vivir dentro de `ResourceForm`).
  - Nuevo hook local `useOrigenActualDelPerfil(jugadorPerfilId, torneoId)`: `GET /plantillas?jugador_perfil_id=X&torneo_id=torneoId`, toma la fila con `estado === "Activo"` (si hay), resuelve `inscripcion_torneo_id → equipo_id → nombre` (mismo mapa `nombreEquipoDeInscripcion` que ya existe en el archivo, línea 67-72) o `"Agencia Libre"` si no hay ninguna.
  - Nuevo hook local `useDorsalesHistoricos(jugadorPerfilId)`: `GET /plantillas?jugador_perfil_id=X` (sin `torneo_id`), `[...new Set(filas.map(f => f.dorsal).filter(d => d != null))]`.
  - Campo "Equipo de origen" pasa de `type: "reference"` editable a un `<input readOnly>` (o texto plano) con el valor resuelto — el operador ya no lo elige, solo lo ve (Requerimiento A: *"El Equipo Destino lo selecciona el operador"*, implica que el de origen no).
  - Fila de chips debajo de "Dorsal nuevo": `<button type="button">` por cada dorsal distinto, `onClick` setea el valor del campo `dorsal_nuevo` del form.

**Control de Mesa (D4/B.2):**
- `backend/app/services/hito_partido.py`:
  - Nuevo método privado `_validar_titulares(partido: Partido) -> None`, llamado desde `registrar()` (línea ~110-115) solo cuando `data.tipo_hito == "Inicio_Partido"`.
  - Resuelve `torneo = torneo_repo.get_or_404(partido.torneo_id)` → `modalidad = modalidad_repo.get_or_404(torneo.modalidad_id)` → `requeridos = modalidad.tamano_equipo`.
  - Para cada lado (`partido.equipos_id_local`, `partido.equipos_id_visitante`): resuelve la `inscripcion_torneo_id` de ese equipo en ese torneo, junta los `jugador_perfil_id` con `JugadorEquipo.estado == "Activo"` en esa inscripción (reusa `JugadorEquipoRepository`, patrón ya usado en `registro_lote.py`), cuenta cuántos de `ConvocadoAPartido` (`titular=True`, `partido_id=partido.id`) caen en ese conjunto.
  - Si algún lado no llega a `requeridos`: `raise DomainRuleError(f"{nombre_equipo} tiene {n} titulares marcados, esta modalidad exige {requeridos}. Definí la convocatoria antes de empezar el partido.")`.
  - Necesita inyectar `ModalidadRepository`, `TorneoRepository`, `EquipoRepository`, `JugadorEquipoRepository`, `ConvocadoAPartidoRepository` en el `__init__` del servicio (varios ya existen en el proyecto, ver imports de `registro_lote.py` para los patrones de uso).
- `frontend/src/pages/ControlDeMesa.tsx`:
  - Nuevo hook `useTitularesCompletos(partido)`: trae `GET /partidos/{id}/convocados` + `GET /modalidades/{modalidad_id}` (via el torneo del partido) + el roster de cada equipo (`GET /plantillas?inscripcion_torneo_id=X`, ya existe) y replica el mismo cálculo que el backend (client-side, solo para UX — el backend sigue siendo la fuente de verdad).
  - Botón "▶ Empezar Partido" (línea 145-148): `disabled={empezarPartido.isPending || !titularesCompletos}`, con texto de ayuda (`title=` o párrafo) mostrando el detalle "{equipo}: {n}/{requeridos} titulares" cuando está deshabilitado por este motivo.
  - Mensaje de error de `empezarPartido.isError` (línea 126) ya renderiza `apiErrorMessage(...)` — el 409 nuevo del backend aparece ahí sin cambios adicionales si el chequeo client-side quedara desactualizado (carrera entre pestañas).

### Modelo de datos

**Sin cambios de esquema en todo este plan.** Los tres problemas se
resuelven con datos que ya existen (`EQUIPOS.Nombre`, `JUGADOR_EQUIPO`,
`CONVOCADO_A_PARTIDO`, `MODALIDAD.Tamano_Equipo`) — es la señal más
fuerte de que ninguno de los tres pedidos necesitaba una tabla nueva,
solo conectar piezas que el sistema ya tiene.

### Edge cases

| # | Caso | Resolución |
|---|---|---|
| EC-A1 | Modal "Crear equipo nuevo" con la tabla de jugadores vacía (equipo sin plantilla inicial) | `filasIniciales` viaja vacío o ausente — pantalla dividida arranca igual que hoy (EC-22 ya cubre 0 jugadores como válido). |
| EC-A2 | Admin edita una fila en el modal, se arrepiente, borra el texto antes de "Validar y crear" | Sin cambios: `filasConDato` (línea 400, sin tocar) ya filtra filas totalmente vacías antes de habilitar el botón. |
| EC-B1 | `GET /equipos/{id}` (fetch dirigido) devuelve 404 porque el equipo fue dado de baja lógica entre que se listó y se intentó resolver | El nombre sigue existiendo en la fila (soft-delete no borra `Nombre`) — un 404 acá sería un bug de backend distinto; en la práctica `soft_delete` solo cambia `Estado`, `GET /equipos/{id}` no filtra por estado (`obtener_equipo`, `equipos.py:39-41`), así que esto no debería ocurrir. Documentado por completitud. |
| EC-B2 | Un torneo con más de 200 equipos de la MISMA disciplina | D2 (fetch dirigido) sigue resolviendo el nombre igual — el techo de 200 solo afecta qué aparece LISTADO por default en otras pantallas (fuera de alcance, 3B-9), no la resolución de un ID puntual. |
| EC-Tr1 | Jugador elegido en Traspasos no tiene NINGÚN vínculo histórico (recién creado, nunca jugó en ningún equipo) | "Equipo de origen: Agencia Libre" (0 filas Activo) + sin fila de chips de dorsal (0 dorsales históricos) — ambos ya cubiertos por "lista vacía" en los hooks nuevos, sin caso especial de código. |
| EC-Tr2 | Jugador con membresía activa en el torneo actual, pero en el MISMO equipo que el destino elegido | No es un caso nuevo — el backend de `TraspasoCreate`/`TraspasoService.crear` ya existe y decide qué hacer con un traspaso origen==destino; este plan no toca esa validación, solo cómo se completan los campos en la UI. |
| EC-Tr3 | Jugador con más de una membresía activa histórica en el MISMO torneo (no debería poder pasar por la exclusividad del trigger, pero el fetch trae varias filas) | `useOrigenActualDelPerfil` toma la primera fila `Activo` que encuentre — si hubiera más de una sería un dato inconsistente que ya rompería otras partes del sistema (`fn_validar_exclusividad_torneo`), no algo que este hook deba resolver. |
| EC-CM1 | Modalidad Pareja (`tamano_equipo == 2`) | Mismo cálculo genérico, exige 2 titulares por lado — sin rama especial (P11, P12). |
| EC-CM2 | Convocatoria nunca se guardó para este partido (`GET /convocados` devuelve `[]`) | 0 titulares en ambos lados → bloqueado con el mismo mensaje, nombrando "0 de N" — no es un caso de error, es el estado inicial esperado de cualquier partido antes de definir la convocatoria. |
| EC-CM3 | Carrera: la pestaña A recalcula "titulares completos" y habilita el botón; en el medio, la pestaña B saca un titular desde Convocatoria; la pestaña A hace click | El backend rechaza con 409 real (fuente de verdad) — la pestaña A no puede arrancar el partido con datos viejos, solo ve el error y su chequeo local se invalida en el próximo refetch (`queryClient.invalidateQueries` sobre `["convocados", partidoId]` cuando `Convocatoria.tsx` guarda, ya existe). |
| EC-CM4 | Un equipo tiene MÁS titulares marcados que `tamano_equipo` (ej. 8 titulares en Fútbol 11 real de 11 — no debería pasar porque 11 es el total, pero en una modalidad de 7 alguien marca 9) | Fuera de alcance de la validación de INICIO — `Convocatoria.tsx` no impone un tope de titulares al guardar (podría ser un plan aparte); este plan solo exige el MÍNIMO al arrancar, no bloquea un exceso. Se anota como límite explícito, no como bug. |

### Diagrama de pruebas

| Flujo/rama nueva | Tipo de test | Prioridad |
|---|---|---|
| `filasIniciales` viaja del modal a la pantalla dividida y se ve precargada | Integración (frontend, testing-library) | Alta — es el fix del bug reportado, necesita evidencia directa |
| Crear equipo con plantilla desde el modal → jugadores terminan en `JUGADOR_EQUIPO` tras "Confirmar" | Integración end-to-end (backend + frontend) | Alta — reproduce el reporte original tal cual |
| `PlantillasDelTorneoPage`/`TraspasosDelTorneo.tsx` muestran el nombre real de un equipo/jugador con ID fuera de los primeros 200 | Integración (mock de 200+ filas, verificar que NO aparece el fallback `#ID`) | Alta — es la prueba de regresión exacta del Bug 2 |
| `SelectorJugadorBuscable` — debounce dispara `GET /jugadores?q=` con el texto correcto, no antes de 300ms | Unit (frontend) | Media |
| `useOrigenActualDelPerfil` — jugador con membresía activa devuelve el nombre del equipo; sin membresía devuelve "Agencia Libre" | Unit (frontend, con mocks de `GET /plantillas`) | Alta |
| `useDorsalesHistoricos` — deduplica dorsales repetidos entre torneos, ignora `null` | Unit (frontend) | Media |
| Click en un chip de dorsal precarga el input | Unit/integración (frontend) | Baja |
| `_validar_titulares` — bloquea `Inicio_Partido` con 0 convocatoria | Integración (backend, pytest) | Alta |
| `_validar_titulares` — bloquea con titulares parciales en un solo equipo, mensaje nombra el equipo correcto | Integración (backend) | Alta |
| `_validar_titulares` — permite `Inicio_Partido` con titulares exactos | Integración (backend) | Alta |
| `_validar_titulares` — modalidad Pareja exige exactamente 2 | Integración (backend) | Media |
| `_validar_titulares` — un `ConvocadoAPartido.titular=True` de un jugador que YA NO está en el roster activo (dado de baja después de convocarlo) no cuenta | DB/Integración (backend) — edge case de integridad | Media |
| Botón "Empezar Partido" deshabilitado en frontend cuando el cálculo local no cierra, con el texto correcto de "N/M titulares" | Integración (frontend) | Alta |
| Carrera EC-CM3: 409 real del backend se muestra aunque el frontend lo tuviera habilitado | Integración (backend, simulando estado desactualizado) | Media |

---

## Decision Audit Trail

| # | Fase | Decisión | Clasificación | Principio | Racional |
|---|---|---|---|---|---|
| 1 | CEO | Bug 1 se resuelve haciendo viajar `filas` a Registro por Lote, no reconstruyendo el flujo de confirmación en el modal | Mecánica | P4 (DRY) + P5 (explícito) | El enganche a la pantalla dividida ya estaba diseñado en el comentario del propio código — solo faltaba el dato |
| 2 | CEO | Bug 2 diagnosticado como bug de LECTURA (fallback de nombre), no de escritura — se descarta reabrir el INSERT | Mecánica | Claimed Limitations Need Evidence | Se verificó el `EquipoService.create` real, guarda el nombre correcto; el placeholder es un fallback documentado en 7+ archivos |
| 3 | CEO | Bug 2 se resuelve con fetch dirigido + filtro por disciplina, no con paginación de cursor completa | Taste (borderline scope) | P2 (boil lakes, límite explícito) | 3B-9 ya es su propio ciclo reconocido en `TODOS.md`; resolver el síntoma reportado no exige resolver todo ese proyecto |
| 4 | CEO | Traspasos reusa `ModalBuscarAgregarJugador`/`useDebouncedEffect` extraídos a componente/hook compartido, en vez de construir un buscador nuevo | Mecánica | P4 (DRY) | Ya existe, probado, mismo backend (`?q=`) |
| 5 | CEO | Migrar `DetalleEquipo.tsx`/`ModalIndividual` al componente compartido nuevo queda como mejora opcional, no tarea de este plan | Taste | P2 (boil lakes) | No fue pedido explícitamente; se anota para no perder la oportunidad, sin forzar el alcance |
| 6 | CEO | Autocompletado de origen y dorsal histórico se resuelven con `GET /plantillas?jugador_perfil_id=` ya existente, sin backend nuevo | Mecánica | P4 (DRY) | El endpoint ya acepta ese filtro solo, sin requerir `torneo_id` |
| 7 | CEO | Convocatorias (B.1) y Registro de sucesos (B.3) se documentan como ya implementados, no se tocan | Mecánica | Evidencia de código | Confirmado contra `Convocatoria.tsx`, `MesaPanel`/`ControlDeMesa.tsx` y `TODOS.md` (3B-2) |
| 8 | CEO | `Modalidad.tamano_equipo` es la fuente de verdad para "titulares exigidos", no un catálogo nuevo | Mecánica | P4 (DRY) + P11 | Ya significa "cuántos juegan a la vez", usado con ese sentido en `RegistroLoteService` |
| 9 | Design | Botón "Empezar Partido" se deshabilita preventivamente en frontend, además del 409 de backend | Mecánica | P1 (completeness) | Evita que el admin vea un error recién al hacer click; backend sigue siendo la fuente de verdad para la carrera EC-CM3 |
| 10 | Design | Campo "Equipo de origen" pasa de editable a solo-lectura en Traspasos | Taste | P5 (explícito) | El requerimiento dice que el origen se "autocompleta evaluando su estado" — dejarlo editable después contradice esa premisa; el operador solo controla destino |
| 11 | Eng | Validación de titulares vive en `HitoPartidoService.registrar`, no en un servicio nuevo | Mecánica | P4 (DRY) | Es el único punto por el que pasa cualquier camino que dispare `Inicio_Partido` (dashboard o Cronómetro), evita duplicar el chequeo |
| 12 | Eng | Exceso de titulares (más que `tamano_equipo`) no se bloquea, solo el déficit | Taste | P2 (boil lakes, límite) | No fue parte del pedido ("exigir que se seleccione la alineación titular... exactamente N"); agregar un tope además de un piso es una regla distinta que nadie pidió |

---

## GSTACK REVIEW REPORT

- **Modo**: SELECTIVE FIX + EXTENSIÓN ACOTADA (2 bugs de flujo existente + 1 pantalla de UX nueva + 1 validación de negocio nueva). Sin cambios de esquema.
- **Fases corridas**: CEO ✅ (12 premisas verificadas contra código real, 3 decisiones de arquitectura), Design ✅ (scope UI detectado: selector buscable, chips, estados de botón deshabilitado), Eng ✅, DX — omitida (sin superficie de API/CLI para terceros, módulo interno).
- **Voces**: `[subagent-only]` — Codex no disponible en esta máquina (binario no encontrado en PATH). Diagnóstico verificado directamente contra el código fuente real en cada premisa (no se aceptó ninguna afirmación de "esto ya existe" sin abrir el archivo y citar la línea) — mitiga el riesgo que normalmente cubre la segunda voz.
- **Gates**: 0 decisiones de arquitectura pendientes de confirmar con el usuario — a diferencia de los dos planes anteriores de este repo, ninguna decisión acá reabre un modelo de datos ni introduce una tabla nueva, así que no hay una D1-tipo-"pregunta al usuario" bloqueante. El gate final de aprobación no aplica (documento pedido explícitamente, no implementación).
- **Decisiones registradas**: 12 (ver Decision Audit Trail). 0 taste decisions sin resolver, 0 user challenges (ninguna decisión de los dos modelos contradice la dirección que pidió el usuario — de hecho la mitad del pedido de Parte B ya estaba resuelto, lo cual se documenta en vez de re-litigarse).
- **Hallazgo más importante para priorizar la implementación:** el Bug 2 reportado ("nombres placeholder") **no es el mismo bug que el Bug 1** ni comparte causa raíz con él, a pesar de que el reporte los agrupa bajo "Data Binding" — es un bug de lectura ya explicado por una brecha conocida (3B-9), mientras que el Bug 1 sí es una pérdida de datos real en el flujo de escritura. Tratarlos como el mismo problema llevaría a "arreglar" el INSERT de `EquipoService.create` (que ya funciona bien) en vez del verdadero punto de falla.
- **No implementado**: cero código ni cambios de esquema — solo este documento, como se pidió.
- **Siguiente paso sugerido**: implementar en el orden Bug 1 → Bug 2 → Control de Mesa (B.2) → Traspasos (A) — los dos bugs son los de menor esfuerzo y mayor impacto inmediato (el admin está perdiendo datos reales hoy), Control de Mesa es una validación acotada de una sola función de servicio, y Traspasos es la pieza de mayor superficie de UI nueva. `/plan-eng-review` interactivo si se quiere una segunda pasada humana antes de implementar, o directo a implementación con este documento como referencia.

**STATUS: DONE**
