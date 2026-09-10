# Plan: Renderizado Dinámico de Goles por Marcador + Quick Action Bar + Timeline Reactivo (Resultado Directo)

<!-- /autoplan: nuevo plan, sin restore point previo (el archivo no existía) -->
<!-- REVERSIÓN EXPLÍCITA de D1 (Gate Final 2026-09-08, modo-vivo-sustituciones-cierre-plan.md):
     el usuario había elegido mantener la carga incremental libre en "Cargar resultado
     directo" en vez de construir la UI de slots por marcador. Hoy (2026-09-09) pide
     explícitamente construir esa UI. Reversión registrada en
     ~/.gstack/projects/Score-App/decisions.jsonl (supersede 2ece8dea-f612-467c-8bea-9bcd62efa7fb
     → c868880c-16ba-4f2a-8505-deb10a989663). Ver "Contexto de reversión" abajo. -->

**Branch**: `main` · **Fecha**: 2026-09-09 · **Solicitado por**: Gabriel Cruz

## Contexto de reversión (leer antes que el resto del plan)

El 2026-09-08, `docs/plans/modo-vivo-sustituciones-cierre-plan.md` corrió la misma pila
`/autoplan` sobre un pedido que incluía, palabra por palabra, la misma UI de slots por
marcador (su "Área 2"). Esa revisión llegó a un Gate Final con una Taste Decision (D1)
explícita: **Approach A (mantener carga incremental libre + arreglar orden cronológico)
vs. Approach B (construir la UI de slots tal como se pidió)**. El usuario eligió A. La
razón documentada por el CEO subagent en ese momento: comprometerse a un marcador final
ANTES de cargar los eventos crea un problema de reconciliación no diseñado (si el
operador se equivoca al tipear el marcador después de cargar algunos goles, ¿qué pasa
con los slots ya llenos?).

Hoy el usuario pidió explícitamente lo contrario — literalmente la UI de slots (puntos 1
y 2 de este pedido), más una versión más estricta de la lógica de sustitución (punto 3)
y el orden cronológico (punto 4, ya parcialmente resuelto por el plan de ayer). Se le
preguntó al usuario si esto era una reversión consciente o una duplicación por
desconocimiento del gate anterior — confirmó que sí, quiere revertir D1 y construir los
slots (ver el AskUserQuestion de esta sesión). Este plan:
1. Trata la reversión como reversión, nunca como si el pedido de ayer no hubiera existido.
2. **Reutiliza, sin repetir el análisis, todo lo que el plan de ayer ya diseñó y que
   sigue vigente** (chequeado contra el código real más abajo — gran parte de "Área 3"
   de ayer ya está implementada y funcionando).
3. Resuelve el problema de reconciliación que quedó señalado como "no diseñado" ayer —
   ahora es un requisito de este plan, no una nota al margen.

## Pedido original (verbatim, del prompt del usuario)

### 1. Renderizado Dinámico de Goles por Marcador
Input Inicial: En la parte superior, el operador debe ingresar el marcador final
numérico (Ej. Local 2 - Visitante 1). Generación de Slots (Iconos): Automáticamente, el
sistema debe leer esos números y renderizar "Slots" obligatorios debajo del marcador. En
el ejemplo: 2 iconos de pelota en la columna del Local y 1 icono en la del Visitante.
Datos por Slot: Cada slot de gol generado exigirá que se seleccione obligatoriamente:
Jugador Goleador y Minuto del Gol.

### 2. Barra de Eventos Adicionales
Debajo de los goles, debe existir una barra de herramientas rápida (Quick Action Bar) con
botones para: Tarjeta Amarilla, Tarjeta Roja y Cambio (Sustitución). Al hacer clic en
Amarilla o Roja, el sistema abre un pequeño formulario solicitando: Jugador y Minuto.

### 3. Lógica Estricta en el Evento de "Cambios"
Al registrar un "Cambio", el formulario debe solicitar Minuto y mostrar dos selectores
(dropdowns) que deben estar estrictamente filtrados según el estado de la alineación:
Selector "Sale" (Jugador que abandona): SOLO debe listar a los jugadores que actualmente
tengan estado de Titulares (o que estén en cancha en ese momento). Selector "Entra"
(Jugador que ingresa): SOLO debe listar a los jugadores que actualmente tengan estado de
Suplentes. Nota técnica: Al confirmar este cambio, el estado del partido debe
actualizarse internamente para que, si hay un cambio posterior, el jugador que ingresó
ahora aparezca en la lista de titulares.

### 4. Motor de Ordenamiento Cronológico (Timeline Reactivo)
Todos los hitos registrados (los goles de los slots, las tarjetas y los cambios) deben
volcarse visualmente en una lista general (Timeline) en la parte inferior.
Reordenamiento Automático: Esta lista debe escuchar el campo Minuto de cada evento. Si el
operador ingresa una Amarilla al minuto 40 y luego registra un Gol al minuto 2, el Gol
debe reubicarse automáticamente en la parte superior. El orden siempre debe ser de menor
a mayor (cronológico ascendente), reaccionando en tiempo real a cada nueva inserción.

---

## Estado actual verificado en código (working tree, commit 83c2627)

> Fuente: lectura directa de `ModalResultadoDirecto.tsx`, `MesaPanel.tsx`,
> `ModalSustitucion.tsx`, `eventos.ts`, `evento_partido.py` (service),
> `partido.py::registrar_resultado_directo`, `06_triggers.sql`. Cita archivo:línea.
> **Hallazgo central**: el plan de ayer (`modo-vivo-sustituciones-cierre-plan.md`) está
> mucho más implementado de lo que el `git status` de esta sesión sugiere (solo
> `Cronometro.tsx` aparece modificado, por un fix no relacionado — botón "Fin del
> Partido" — no por este plan). Áreas 1, 3 y parte de 2 de ese plan ya están en código,
> committeadas. Esto reduce drásticamente el trabajo nuevo real de este pedido.

### Ya implementado y funcionando (Modo en Vivo — `MesaPanel.tsx`, no tocar)
- **Minuto automático desde el cronómetro**: `EventoPartidoService.create` (`evento_partido.py:71-90`)
  ignora `data.minuto` del cliente y lo calcula siempre server-side (`_minuto_en_vivo`,
  líneas 92-105). Exactamente lo que pedía Área 3 (T3/T22) del plan de ayer.
- **Tope de cambios + no-retorno, autoritativo en backend**: `_validar_reglas_cambio`
  (`evento_partido.py:107-147`) — `Torneo.permite_cambios_ilimitados` +
  `Torneo.maximo_cambios_por_equipo`, mismo patrón que el resto del dominio.
- **Tope de titulares, autoritativo en DB**: `fn_validar_tope_titulares`
  (`06_triggers.sql:101-159`), trigger `trg_convocado_validar_tope_titulares`.
- **"Sale" ya filtrado a titulares reales**: `MesaPanel.tsx:180-183` deriva
  `titularesPerfilIds` de `GET /convocados` (campo `titular: boolean`); la zona
  "Alineación en vivo" (líneas 516-552) solo lista titulares con botón "Sacar", que abre
  `ModalSustitucion` (Área 3, T4 — ya construido, `ModalSustitucion.tsx` completo).
- **Contador "cambios usados X/Y"**: `MesaPanel.tsx:217-230`, derivado de la timeline real
  (no `useState` local), exactamente como pedía la Sección 5 del plan de ayer.
- **Orden cronológico server-side**: `EventoPartidoRepository.list` ya devuelve
  `ORDER BY minuto, id` (comentario `MesaPanel.tsx:590-593`, T7 del plan de ayer). El
  frontend hace `.reverse()` para mostrar lo más reciente arriba (display descendente).

### Gaps reales confirmados (nuevos hallazgos de esta sesión, no del plan de ayer)

1. **Bug de inconsistencia — dos cálculos de elegibilidad de Cambio, uno sin filtro de
   titular/suplente.** `ModalSustitucion` (disparado al tocar un titular en la
   alineación en vivo) usa `calcularElegibilidadCambios` + un filtro adicional en el
   caller (`MesaPanel.tsx:557-563`). Pero `CargaEvento` (el formulario genérico de tipo
   Gol/Autogol/🟨/🟥/🔄, siempre visible debajo) tiene su PROPIO cálculo independiente
   (`MesaPanel.tsx:718-725`) que el propio código admite en un comentario visible al
   operador: *"¿Quién sale? (plantilla vigente — no distingue titular/suplente)"*
   (línea 796). Por ese segundo camino, un titular que nunca salió puede aparecer como
   candidato a "Entra" en un Cambio, y un suplente ya usado puede aparecer para "Sale" —
   exactamente lo que el pedido de hoy (punto 3) quiere prohibir "estrictamente".
2. **La lista "Entra" de `ModalSustitucion` tampoco excluye titulares.** `elegibles`
   (`MesaPanel.tsx:558-563`) = plantilla convocada, menos quien sale, menos
   salidos/expulsados, menos quien ya entró — pero NUNCA excluye explícitamente a
   `titularesPerfilIds`. Si el equipo tiene 2 titulares y se saca al Titular A, el
   Titular B (que sigue en cancha) puede aparecer en la lista de "por quién entra" del
   modal — un titular "entrando" por otro titular no tiene sentido de dominio.
3. **Doble-salida del mismo jugador, sin guardia.** El chequeo de no-retorno
   (`evento_partido.py:121-133`) valida que `jugador_id_entra` no haya salido antes —
   pero nada valida que `jugador_id` (quien sale AHORA) no haya salido YA en un Cambio
   previo. Combinado con el hallazgo 2 (la lista "Sale" de la alineación en vivo,
   `MesaPanel.tsx:526`, no excluye a quien ya salió — `titularesEquipo` no filtra por
   `salidosOExpulsados`), un titular ya sustituido puede volver a aparecer con botón
   "Sacar" y generar un segundo evento Cambio con el mismo `jugador_id` saliente. Dato
   corrupto silencioso: dos "salidas" del mismo jugador en la misma timeline.
4. **Orden de DISPLAY es descendente (más reciente arriba), el pedido de hoy pide
   ascendente explícito.** T7 de ayer resolvió el orden CORRECTO en el backend
   (`ORDER BY minuto, id` ascendente) pero el frontend invierte para mostrar (línea 594,
   `.reverse()`) — una elección de UX deliberada (feed tipo "más reciente primero"), no
   un bug. El pedido de hoy es inequívoco: *"El orden siempre debe ser de menor a
   mayor"*. Esto es un cambio de UX visible sobre algo que ya se decidió ayer
   explícitamente distinto — se marca TASTE DECISION en la Fase 1 (ver 0C-bis), no se
   cambia en silencio.
5. **Nada de esto existe en "Cargar resultado directo" (`ModalResultadoDirecto.tsx`) —
   el modal que el pedido de hoy en realidad describe.** El input "marcador final" del
   punto 1 solo tiene sentido en este modal (en Modo en Vivo el marcador se DERIVA de
   eventos ya cargados, nunca se ingresa). Hoy este modal:
   - No tiene input de marcador ni genera slots — es un `<select>` de tipo + botón
     "+ Agregar evento" (líneas 133-209), uno a la vez.
   - Los `<select>` de "Sale"/"Entra" para Cambio usan `plantillaEquipo` COMPLETA
     (líneas 82-83, sin filtrar por convocatoria en absoluto) — ni siquiera tiene el
     nivel de filtrado (débil) que Modo en Vivo sí tiene.
   - `eventos` (el array local acumulado antes de guardar, línea 72-74) no valida
     elegibilidad entre sí — se puede agregar el mismo jugador como "Entra" dos veces
     en la misma carga, sin aviso, hasta que el backend rechace el batch entero al
     guardar (o no lo rechace: ver Premisa D4 abajo, `registrar_resultado_directo` NO
     corre `_validar_reglas_cambio` — ver siguiente hallazgo).
   - La lista mostrada (`eventos-timeline`, líneas 212-225) es el orden de INSERCIÓN,
     sin ningún sort — ni ascendente ni descendente. El punto 4 del pedido de hoy
     ("reordenamiento automático... en tiempo real") no existe en absoluto acá.
6. **`registrar_resultado_directo` NO corre `_validar_reglas_cambio`.** Confirmado
   leyendo `partido.py:133-...` completo — inserta Hitos + Eventos directo con
   `session.add()`/`flush()`, pasando por los triggers de DB (`fn_validar_jugador_partido`)
   pero NO por el método de servicio que valida tope de cambios / no-retorno. Un
   resultado directo cargado hoy puede tener 10 cambios para un equipo con tope 5, sin
   ningún rechazo.

### Premisa central a resolver — tensión con Decisión D4 (deliberada, documentada)

`registrar_resultado_directo` (`partido.py:170-179`) documenta explícitamente **D4**:
*"La [validación] de titulares NO se agrega, a propósito: este camino existe para
partidos que YA se jugaron y se registraron en papel, donde exigir una alineación sería
pedir un dato que el operador no tiene."* Es decir: **"Cargar resultado directo" fue
diseñado específicamente para el caso SIN convocatoria guardada.**

El punto 3 de hoy exige selectores "estrictamente filtrados" por titular/suplente — un
requisito que **solo es satisfacible si existe una convocatoria con `titular` marcado**
para ese partido. Estos dos hechos son incompatibles tal como están escritos. Se resuelve
en la Fase 1 (0A, Premise Challenge) — no se descarta D4 (partidos genuinamente sin
convocatoria siguen existiendo), pero se hace explícito el caso feliz vs. el caso
degradado en vez de dejarlo implícito.

---

# FASE 1 — CEO Review (`/autoplan`, modo SELECTIVE EXPANSION)

## Paso 0.5 — Voces Duales (CEO)

Codex no disponible en esta máquina (`command -v codex` → not found, preflight
`[codex-unavailable: binary not found]`) — **`[subagent-only]`**, mismo estado que los
últimos 4 planes de este repo.

**CLAUDE SUBAGENT (CEO — independencia estratégica)** — leyó solo el plan (research +
contexto de reversión, sin ver esta sección ni la conversación previa), verificó 3 de las
citas de código de forma independiente (las 3 confirmadas exactas), hallazgos:

1. **Crítico**: la reversión de D1 se está justificando sobre un mecanismo de
   reconciliación que todavía no existe — el documento afirma que el problema "se
   resuelve en Fase 1" sin haber diseñado nada todavía. Circular: no se puede dar por
   ganada la reversión antes de que el diseño que la justifica exista y sobreviva su
   propia revisión.
2. **Crítico**: la resolución propuesta (mantener D4 + hacer explícito el caso
   feliz/degradado) bifurca permanentemente el modal para el caso minoritario — nada en
   el plan estima qué fracción del uso real de "resultado directo" tiene convocatoria
   guardada. Dado que esa vía existe *específicamente* para partidos sin convocatoria,
   podría ser la mayoría de los usos reales, no la minoría.
3. **Alto**: el reframe de mayor apalancamiento no fue evaluado — Modo en Vivo
   (`CargaEvento`/`MesaPanel`) ya tiene minuto automático, validación de cambios y (una
   vez arreglado) filtrado titular/suplente correcto, en el único lugar donde una
   convocatoria existe con confiabilidad. ¿Puede "resultado directo" ser una variante de
   ese motor ya correcto en vez de un segundo motor de slots+validación construido desde
   cero?
4. **Alto**: los 3 bugs reales (cálculo de elegibilidad inconsistente entre
   `ModalSustitucion`/`CargaEvento`, lista "Entra" sin excluir titulares, sin guarda
   contra doble-salida del mismo jugador) son el riesgo de integridad de datos de HOY,
   son baratos de arreglar, y no tienen conflicto de premisa — no deberían esperar a que
   se resuelva el debate arquitectónico de los slots.
5. **Medio**: 4 pedidos distintos están apilados en un solo gate — la Quick Action Bar
   (punto 2) y el orden ascendente (punto 4) son baratos, de bajo riesgo, y no dependen
   de la tensión D4. Solo los puntos 1 y 3 están bloqueados por esa tensión.

Riesgo competitivo/interno (herramienta interna, sin mercado): la alternativa interna más
simple — extender el motor de entrada en vivo ya correcto en vez de construir un segundo
motor de validación/slots — podría dejar obsoleta la mayor parte de la superficie nueva
de este plan antes de construirla. Esa opción no estaba en el documento y se incorpora
abajo en 0C-bis.

```
CEO DUAL VOICES — CONSENSUS TABLE:
═══════════════════════════════════════════════════════════════
  Dimension                           Claude  Codex  Consensus
  ──────────────────────────────────── ─────── ─────── ─────────
  1. Premises valid?                   NO      N/A    N/A (single voice) — 2 hallazgos críticos incorporados igual
  2. Right problem to solve?           PARCIAL N/A    N/A — reframe de reuso incorporado en 0C-bis (Approach C)
  3. Scope calibration correct?        NO      N/A    N/A — gate se divide en Track A (bugs+bar+orden) y Track B (slots)
  4. Alternatives sufficiently explored?NO     N/A    N/A — 0C-bis añade Approach C (reuso del motor en vivo)
  5. Competitive/market risks covered? N/A (interno) N/A N/A — riesgo interno de obsolescencia sí cubierto
  6. 6-month trajectory sound?         PARCIAL N/A    N/A — depende de que Track B no perpetúe una bifurcación de mantenimiento
═══════════════════════════════════════════════════════════════
CONFIRMED = both agree. DISAGREE = models differ (→ taste decision).
Missing voice = N/A (not CONFIRMED). Codex no disponible en esta máquina — [subagent-only].
Los 2 hallazgos "crítico" y 2 "alto" de la única voz disponible se incorporan igual (regla:
"single critical finding from one voice = flagged regardless").
```

## 0A. Premise Challenge

1. **¿Es el problema correcto?** Parcialmente, y el subagent tiene razón en que el plan
   original conflaba 4 pedidos de riesgo/costo muy distintos bajo una sola pregunta de
   "¿construimos los slots?". Los puntos 2 (Quick Action Bar) y 4 (orden ascendente) no
   dependen de resolver la tensión D4 en absoluto — ya tienen 90% de su base construida
   (`CargaEvento` ya es un tap-grid de eventos; el backend ya ordena ascendente, solo el
   display invierte). Los puntos 1 y 3 sí dependen de resolver D4.
2. **¿Cuál es el resultado real?** Que un operador pueda cargar el historial completo de
   un partido (jugado en vivo o registrado después) sin poder generar datos imposibles —
   un titular "entrando" por sí mismo, un jugador saliendo dos veces, un cambio que
   excede el tope del torneo — **sin importar por cuál de los 2 caminos (Modo en Vivo o
   Resultado Directo) haya entrado el dato.** Hoy eso NO es cierto: los 3 bugs
   confirmados (ver "Estado actual") significan que el mismo dominio de negocio tiene 2-3
   niveles de rigor distintos según el formulario usado — la superficie de bug real
   más grande de este plan, y no requiere resolver nada de arquitectura de slots.
3. **¿Qué pasaría si no hacemos nada?** Los 3 bugs de integridad de datos (elegibilidad
   inconsistente, Entra sin filtrar titulares, doble-salida sin guarda) siguen activos
   HOY en producción, en el camino que SÍ se usa (Modo en Vivo, `MesaPanel`) — no son
   hipotéticos, están confirmados leyendo el código. El punto 1 (slots) sin construir
   solo significa seguir usando el formulario libre actual, que ya captura jugador+minuto
   por gol — dolor de UX, no de datos.

**Premisa cuestionada y resuelta (Premisa D4-alcance)**: el pedido de hoy asume,
implícitamente, que "Cargar resultado directo" siempre tiene una convocatoria con
titulares marcados disponible para filtrar. El código (`partido.py:170-179`, Decisión
D4) documenta lo contrario a propósito: ese camino existe PARA los partidos sin
convocatoria. El subagent señala correctamente que no hay forma de saber, sin
instrumentación, qué fracción del uso real tiene convocatoria — y que construir una UI
elaborada de slots+filtrado estricto para un caso que podría ser minoritario es un riesgo
real de sobre-inversión. **Resolución (no se pregunta al usuario — P1/P2 aplican
directamente, ver 0C-bis Approach A)**: el filtrado estricto se construye para degradar
con gracia — si hay convocatoria, filtra estrictamente tal como pide el punto 3; si no
hay convocatoria, usa la plantilla completa (comportamiento D4 actual, sin cambios) y lo
dice explícitamente en la UI, en vez de fallar o de simular un filtrado que no puede
cumplir. Esto no es una premisa "claramente equivocada" que amerite Desafío al Usuario —
es una que necesitaba precisión técnica que el pedido no tenía cómo anticipar sin leer el
código primero.

## 0B. Existing Code Leverage

| Sub-problema del pedido | Código existente que ya lo resuelve |
|---|---|
| Jugador+minuto por gol/tarjeta (punto 1, dato) | `ModalResultadoDirecto.tsx` formulario libre — completo; falta solo el marco visual de "slots" |
| Barra de botones para tipo de evento (punto 2) | `CargaEvento` (`MesaPanel.tsx:759-767`) ya es un tap-grid de 5 botones (Gol/Autogol/🟨/🟥/🔄) — Modo en Vivo ya tiene esto, Resultado Directo no |
| Filtrado Sale=Titular (mitad del punto 3) | `MesaPanel.tsx:180-183,526` ya deriva titulares reales de la convocatoria y los usa para la lista "Sale" en Modo en Vivo |
| Actualización interna de estado tras Cambio (nota técnica del punto 3) | Parcialmente: `calcularElegibilidadCambios` (`eventos.ts:50-62`) ya deriva "quién salió"/"quién entró" de la timeline real (no de un flag mutable) — el patrón correcto ya existe, solo falta extenderlo con el eje titular/suplente y usarlo en los 3 call-sites |
| Orden cronológico (punto 4, dato) | `EventoPartidoRepository.list` ya ordena `ASC` por minuto,id (T7 del plan de ayer) — el dato ya está ordenado, solo el display de Modo en Vivo lo invierte; Resultado Directo no ordena nada todavía |
| Reactividad en tiempo real (punto 4) | Ya existe vía React Query (`invalidateQueries` en cada mutación) para Modo en Vivo — Resultado Directo usa estado local `eventos`, no reactivo a queries, pero tampoco lo necesita (todo vive en el mismo componente) |

Nada de esto se reconstruye. La superficie genuinamente nueva es: (a) el marco visual de
slots-por-marcador con su reconciliación, (b) la extensión del eje titular/suplente al
helper compartido de elegibilidad + su adopción en los 3 call-sites, (c) el guard de
doble-salida en backend, (d) llevar el tap-grid + orden ascendente a Resultado Directo.

## 0C. Dream State Mapping

```
  ESTADO ACTUAL                                  ESTE PLAN                                    IDEAL A 12 MESES
  ────────────────                               ─────────                                    ─────────────────
  Elegibilidad de Cambio: 2-3       ------->      1 sola función compartida,         ------->  Motor de eventos único:
  cálculos independientes,                        extendida con eje titular/                   Modo en Vivo y Resultado
  inconsistentes entre Modo en                    suplente, usada por los 3                     Directo son la MISMA
  Vivo y Resultado Directo                        call-sites (CargaEvento,                      superficie de captura,
                                                   ModalSustitucion, nuevo                       con 2 disparadores de UI
                                                   flujo de Resultado Directo)                   distintos, no 2 motores
  Resultado Directo: formulario     ------->      + slots por marcador con           ------->  Cualquier forma de cargar
  libre, sin orden, sin filtro                    reconciliación diseñada +                     un partido (en vivo o
  de titular/suplente en absoluto                 filtrado que degrada con                      después) produce datos
                                                   gracia sin convocatoria                       igualmente confiables
  Doble-salida del mismo jugador:   ------->      + guard server-side               ------->  Toda transición de estado
  sin ninguna guarda, dato                        (mismo patrón que no-retorno)                 de un jugador en un
  corrupto silencioso posible                                                                   partido pasa por un solo
                                                                                                 punto de validación
  Orden de display: descendente     ------->      ascendente explícito, en          ------->  Timeline como fuente
  (Modo en Vivo), inexistente                     ambos formularios,                           única de verdad temporal,
  (Resultado Directo)                             reaccionando en tiempo real                   reusable en reportes
```

## 0C-bis. Implementation Alternatives (MANDATORY)

### Alternativa A — Slots por marcador con reconciliación (el problema que D1 dejó sin diseñar)

**APPROACH A: Slots derivados de un array editable, nunca una estructura separada (recomendado)**
  Summary: el input de marcador NO crea una estructura de datos nueva — solo
  pre-rellena el `eventos[]` que `ModalResultadoDirecto` ya tiene (línea 72-74) con N
  slots vacíos de tipo Gol/Autogol (obligando jugador+minuto por slot, tal como pide el
  punto 1). Si el operador corrige el marcador después de llenar algunos slots: agregar
  slots vacíos al final del lado que subió, o — si el lado bajó y hay slots YA llenos de
  más — pedir confirmación explícita de cuál slot lleno se descarta (nunca un borrado
  silencioso). El array sigue siendo la única fuente de verdad; el marcador es una vista
  derivada de él (`local = eventos.filter(gol local).length`), igual que ya lo es en Modo
  en Vivo (`marcador` en `MesaPanel.tsx:235-246`, mismo patrón, reusado).
  Effort: M (nuevo componente de slots + estado de reconciliación + tests de los 3 casos:
  subir marcador, bajar marcador sin slots llenos afectados, bajar marcador con slots
  llenos afectados).
  Risk: Bajo-Medio — la reconciliación es superficie nueva, pero acotada (mismo array,
  mismas validaciones ya existentes, ningún estado paralelo).
  Pros: resuelve exactamente el gap que D1 dejó sin diseñar ayer; el marcador nunca puede
  desincronizarse del array de eventos porque es un cálculo derivado, no un campo aparte
  que haya que mantener sincronizado a mano.
  Cons: requiere diseñar y testear 3 sub-casos de reconciliación explícitamente — más
  trabajo que un slot rígido.
  Reuses: patrón de `marcador` derivado de `MesaPanel.tsx:235-246`, el array `eventos[]`
  que `ModalResultadoDirecto` ya tiene.

**APPROACH B: Marcador como precommit rígido, sin edición post-generación**
  Summary: una vez ingresado el marcador, los slots quedan fijos; para corregir un
  marcador mal tipeado hay que descartar todo lo cargado y reempezar.
  Effort: S.
  Risk: Alto — reintroduce EXACTAMENTE el problema que causó el rechazo original de D1
  (Q4 del plan de ayer): un typo en el marcador después de cargar 2-3 goles borra todo.
  Pros: mitad del esfuerzo de A.
  Cons: falla el propio motivo por el que D1 se revirtió — no resuelve el problema, lo
  vuelve a dejar sin diseñar.
  Reuses: nada nuevo, reemplaza el formulario libre entero.

**RECOMENDACIÓN: Approach A** — P1 (completitud) + P5 (explícito, reusa el patrón de
marcador-derivado que ya existe en Modo en Vivo en vez de inventar uno). Completeness:
A=9/10 (resuelve el problema de reconciliación explícitamente), B=3/10 (no lo resuelve,
solo lo esconde). No es Taste Decision — Approach B fue exactamente lo que el CEO de ayer
ya identificó como el problema, no hay ambigüedad real.

### Alternativa B — Dónde vive el filtrado titular/suplente (DRY + degradación con gracia)

**APPROACH A: Un solo helper compartido, extendido, usado en los 3 call-sites (recomendado)**
  Summary: extender `calcularElegibilidadCambios` (`eventos.ts`) para aceptar también
  `titularesPerfilIds` (ya se calcula en `MesaPanel.tsx:180-183`) y devolver, además de
  `salidosOExpulsados`/`yaEntraron`, un tercer set `noEsTitularAhora` — vacío (= sin
  filtrar, comportamiento D4 actual) cuando no hay convocatoria cargada para ese partido.
  Los 3 call-sites (`CargaEvento`, `ModalSustitucion` vía su caller, y el nuevo flujo de
  Cambio en `ModalResultadoDirecto`) consumen la MISMA función — nunca vuelven a
  implementar su propio filtro. La UI muestra un aviso breve ("plantilla completa — sin
  convocatoria guardada") cuando el set de titulares está vacío, en vez de fallar
  silenciosamente o de fingir que sí filtró.
  Effort: S (extender 1 función + actualizar 3 call-sites + 1 mensaje de UI condicional).
  Risk: Bajo — mismo patrón ya usado, solo se agrega un eje.
  Pros: cierra el bug DRY confirmado (hallazgo 1) Y resuelve la tensión D4 (hallazgo del
  subagent #2) en el mismo cambio — degrada con gracia en vez de bifurcar el modal
  permanentemente.
  Cons: el 3er call-site (Resultado Directo) es código nuevo — no es un fix de 3 líneas,
  es fix + adopción.
  Reuses: `calcularElegibilidadCambios`, `titularesPerfilIds` (ya calculado).

**APPROACH B: Requerir convocatoria obligatoria para usar el filtrado estricto en Resultado Directo (bloquear el resto)**
  Summary: si no hay convocatoria guardada, el botón "Cambio" del Quick Action Bar en
  Resultado Directo se deshabilita con un mensaje ("Cargá la convocatoria primero").
  Effort: XS.
  Risk: Medio-Alto — rompe el caso de uso que D4 protege a propósito (partido sin
  convocatoria, cargado desde papel) para el tipo de evento más común de sustitución;
  fuerza un flujo de 2 pasos (ir a convocatoria, volver) para algo que hoy es 1 paso.
  Pros: más simple de construir, cero ambigüedad de UI.
  Cons: regresión real de UX para el caso que el modal fue diseñado a servir; viola P1
  (completitud) al resolver solo el caso feliz.
  Reuses: nada nuevo, solo un guard condicional.

**RECOMENDACIÓN: Approach A** — P1 + P4 (DRY) dominan en fase Eng/CEO respectivamente,
ambos apuntan al mismo lado acá. Completeness: A=9/10 (cubre ambos casos: con y sin
convocatoria), B=5/10 (cubre solo el caso feliz, regresiona el caso D4). No es Taste
Decision — resuelve el hallazgo crítico #2 del subagent sin sacrificar nada.

### Alternativa C — Reuso del motor de Modo en Vivo vs. motor nuevo en Resultado Directo (reframe del subagent)

**APPROACH A: Extender Resultado Directo con los mismos átomos de UI que Modo en Vivo, sin fusionar los flujos (recomendado)**
  Summary: el reframe del subagent (punto 3, alto) es válido a medias — fusionar
  literalmente los 2 flujos en un único motor no es viable sin trabajo adicional no
  pedido: Resultado Directo opera sobre un partido `'Programado'` en una única
  transacción atómica al final (Inicio+eventos+Fin de una vez), mientras Modo en Vivo
  opera sobre un partido ya `'En curso'` con persistencia inmediata por evento — son dos
  máquinas de estado de partido genuinamente distintas (`partido.py:159-163` exige
  `'Programado'`; `evento_partido.py:34-38` exige `'En curso'`), no una diferencia
  cosmética. Fusionarlas de verdad es un rediseño de la máquina de estados de partido,
  fuera de blast radius de este pedido. **Lo que SÍ se reusa, y es exactamente el punto
  de apalancamiento real que señaló el subagent**: los ÁTOMOS de UI y lógica —
  `ModalSustitucion` (componente completo, reusable tal cual para el flujo de Cambio de
  Resultado Directo), el tap-grid de `CargaEvento` (mismo patrón visual para el Quick
  Action Bar), y el helper de elegibilidad de la Alternativa B. Cero motor nuevo de
  validación — se ensamblan piezas ya construidas y probadas.
  Effort: incluido en el effort de las Alternativas A y B de arriba (no es trabajo
  adicional, es la forma de construirlas).
  Risk: Bajo.
  Pros: responde al hallazgo #3 del subagent (evita reinventar el motor) sin adoptar el
  riesgo de fusionar 2 máquinas de estado distintas fuera de alcance.
  Cons: Resultado Directo sigue siendo un formulario/flujo separado de Modo en Vivo — la
  fusión completa (idea del subagent) queda diferida a TODOS.md como oportunidad real,
  no descartada por completo.

**APPROACH B: Fusionar completamente ambos flujos en un único componente parametrizado por modo**
  Summary: un solo `PartidoEventosEditor` que recibe `modo: "en-vivo" | "resultado-directo"`
  y ajusta minuto (automático vs. manual), persistencia (inmediata vs. batch) y máquina
  de estados (Programado→Finalizado en 1 paso vs. En curso incremental) internamente.
  Effort: L — toca la máquina de estados de `Partido`, ambos servicios backend, y ambos
  componentes frontend a la vez.
  Risk: Alto — exactamente el tipo de expansión que P2 (hervir el lago) manda diferir:
  fuera de blast radius de "agregar slots+quick-bar+filtrado" (>1 día CC, introduce un
  concepto de dominio nuevo — "modo de carga" como parámetro de primera clase).
  Pros: sería la superficie ideal a 12 meses (ver 0C) si se justifica con más señal de
  uso real.
  Cons: reescritura no pedida, mezclada con lo que sí se pidió — retrasaría todo el plan
  para especular sobre una fusión que ni el propio pedido del usuario sugiere.

**RECOMENDACIÓN: Approach A** — P2 (hervir el lago con límite: blast radius + <1 día CC)
aplica en contra de B. El reframe del subagent se incorpora en su forma correcta (reusar
átomos), no en su forma máxima (fusionar máquinas de estado). Completeness:
Note: options differ in kind (composición vs. fusión arquitectónica), no en cobertura —
no se fabrica un score de completitud entre "reusar piezas" y "reescribir el dominio".
La fusión completa (Approach B) se registra en "NOT in scope" / TODOS.md como
oportunidad de plataforma real, señalada por 2 voces (CEO de ayer implícitamente, este
subagent explícitamente) — candidata fuerte para una futura sesión con más contexto de
uso real.

### Alternativa D — Dirección de display del timeline (hallazgo 4)

**APPROACH A: Cambiar a ascendente en ambos formularios, tal como se pidió literalmente (recomendado)**
  Summary: quitar el `.reverse()` de Modo en Vivo (`MesaPanel.tsx:594`) y construir el
  timeline de Resultado Directo ya ordenado ascendente desde el inicio (`eventos[]`
  ordenado por `minuto` en cada render, con `id` de inserción como desempate estable para
  minutos iguales).
  Effort: XS (Modo en Vivo: quitar 1 llamada; Resultado Directo: agregar 1 `.sort()`).
  Risk: Bajo, pero cambia una decisión de UX reciente y deliberada (T7 de ayer eligió
  descendente a propósito, "más reciente arriba", un patrón común de feed de actividad).
  Pros: cumple el pedido literal e inequívoco de hoy ("el orden siempre debe ser de menor
  a mayor"); consistente entre los 2 formularios (hoy Modo en Vivo es descendente,
  Resultado Directo no ordena nada — ninguno de los 2 coincide con el pedido).
  Cons: un operador de mesa mirando un partido largo pierde el "scroll cero" de ver lo
  último cargado sin desplazarse — trade-off real de usabilidad, no solo estético.

**APPROACH B: Mantener descendente en Modo en Vivo (comportamiento actual), ascendente solo en Resultado Directo (nuevo)**
  Summary: no tocar Modo en Vivo (T7 ya decidido y en uso); construir Resultado Directo
  ascendente desde cero, ya que ahí no hay una decisión previa que revertir.
  Effort: XS (solo Resultado Directo).
  Risk: Bajo, pero dos formularios del mismo dominio muestran el mismo tipo de dato en
  direcciones opuestas — inconsistencia de producto real.
  Pros: no revierte una decisión de ayer sin conversación explícita con el usuario.
  Cons: inconsistencia visible entre los 2 flujos del mismo dominio; no cumple el pedido
  literal de hoy para Modo en Vivo, que sigue mostrando descendente.

**RECOMENDACIÓN: neutral entre A y B — esto es una Taste Decision explícita, se marca
para el Gate Final.** Completeness: Note: options differ in kind (preferencia de
dirección de feed), no en cobertura — ambas cumplen el requisito funcional de "reordenar
en tiempo real por minuto", difieren en qué dirección. P1 (completitud del pedido
literal) favorece A; P3 (pragmatismo, no tocar una decisión de UX reciente sin
conversación) favorece B. Sin ganador claro por los 6 principios — se surface en el Gate
Final como Choice, no se auto-decide en silencio.

## 0D. Mode-Specific Analysis (SELECTIVE EXPANSION)

**Complexity check**: el plan ensamblado toca ~6-7 archivos (frontend:
`ModalResultadoDirecto.tsx` [reescritura sustancial], `MesaPanel.tsx` [3 fixes
puntuales], `eventos.ts` [extender 1 función], nuevo componente de slots reusando
`ModalSustitucion.tsx` sin cambios; backend: `evento_partido.py` [1 guard nuevo +
reusar `_validar_reglas_cambio` desde `registrar_resultado_directo`], `partido.py`
[llamar la validación que hoy se saltea]). Por debajo del umbral de "más de 8 archivos =
smell" — no se activa el corte de complejidad. Se trata como 2 tracks independientes
(Track A: bugs+bar+orden, Track B: slots+reconciliación), no como una sola pieza.

**Mínimo conjunto de cambios**: Track A (los 3 bugs + Quick Action Bar en Resultado
Directo + `_validar_reglas_cambio` también en `registrar_resultado_directo`) es
autocontenido y no depende de resolver nada de arquitectura — se puede enviar solo. Track
B (slots + reconciliación) depende de que el helper compartido de Track A ya exista (la
Alternativa B de arriba es prerequisito de la Alternativa A).

**Escaneo de expansión (candidatos, NO agregados a alcance todavía):**
1. **10x check**: fusión completa de Modo en Vivo + Resultado Directo en un único motor
   de eventos parametrizado (Alternativa C, Approach B arriba) — Effort L, excede blast
   radius, diferido a TODOS.md.
2. **Delight opportunities** (≥5): (a) al tipear el marcador, si ya hay eventos Gol
   cargados de una sesión anterior sin guardar (ej. el operador refrescó la página sin
   guardar), sugerir restaurarlos desde `localStorage` en vez de perderlos; (b) atajo:
   tras completar un slot de Gol, saltar automáticamente el foco al selector de jugador
   del siguiente slot vacío; (c) mostrar el marcador parcial ("2 de 2 goles Local
   cargados") mientras se llenan los slots, no solo al final; (d) en el Quick Action Bar,
   recordar el último equipo usado como default del siguiente evento (reduce taps
   repetidos cuando varios eventos seguidos son del mismo equipo); (e) validación
   temprana en el cliente (no solo al guardar) si dos slots de Cambio en la misma carga
   local usan el mismo `jugador_id_entra` — feedback inmediato en vez de esperar el
   rechazo del backend al guardar todo el batch.
3. **Platform potential**: el helper de elegibilidad extendido (Alternativa B) es
   reusable por cualquier futuro punto de captura de eventos (ej. una futura app móvil
   de árbitro) — ya es una pieza de plataforma, no haría falta generalizarlo más.

**Auto-decisión de expansiones (principios, sin preguntar — SELECTIVE EXPANSION delega en autoplan):**
- (a) restaurar desde localStorage → **DEFERIR a TODOS.md** (P2: fuera de blast radius
  directo, requiere diseño de persistencia local no pedido).
- (b) autofocus al siguiente slot → **INCORPORAR A ALCANCE** de Track B (P1: mejora
  directa y barata de la propia UI de slots que se está construyendo, <1 día CC, mismo
  componente).
- (c) contador parcial "X de N goles cargados" → **INCORPORAR A ALCANCE** de Track B
  (P1: es la mitad barata y obvia de dar feedback visual sobre el propio progreso de
  slots — sin esto el operador no sabe cuántos le faltan).
- (d) recordar último equipo → **CORTAR** (P5/P3: mejora marginal no pedida, agrega
  estado adicional sin beneficio claro medido).
- (e) validación temprana de `jugador_id_entra` duplicado en el batch local → **INCORPORAR
  A ALCANCE** de Track B (P1: la Sección 4 de este mismo plan ya identifica esto como
  gap real — feedback inmediato es más completo que esperar el rechazo del backend al
  guardar todo).
- Fusión completa de motores (ítem 1) → **DEFERIR a TODOS.md** (ya justificado en
  Alternativa C arriba).

## 0E. Temporal Interrogation

```
  HORA 1 (fundaciones):     Extender `calcularElegibilidadCambios` con el eje titular/
                            suplente (Alternativa B) — esto es prerequisito de TODO lo
                            demás (Track A y Track B lo consumen). Decidir el mensaje
                            exacto de UI para el caso "sin convocatoria" (aviso pasivo
                            vs. banner — resuelto en Fase 2, Design).
  HORA 2-3 (lógica core):   Ambigüedad esperada: ¿el guard de doble-salida en backend
                            rechaza con 400 o simplemente ignora el segundo intento?
                            (Resuelto abajo, Sección 2: mismo patrón que no-retorno,
                            400 con mensaje de dominio — nunca un no-op silencioso,
                            Directiva Prima #1). ¿`registrar_resultado_directo` llama a
                            `_validar_reglas_cambio` por cada evento dentro del loop de
                            inserción, o se valida el batch completo antes de insertar
                            nada? (Debe ser por evento, dentro del mismo flush() que ya
                            usa — mantiene la atomicidad ya diseñada en ese método, un
                            evento inválido aborta TODA la transacción, no solo se salta).
  HORA 4-5 (integración):   Sorpresa esperada: el componente de slots necesita saber, por
                            cada slot de Cambio, la lista de "quién ya salió DENTRO de
                            este mismo batch local todavía no guardado" — no solo la
                            timeline ya persistida (que para un partido `'Programado'`
                            está vacía, es resultado directo). El helper de la
                            Alternativa B debe aceptar también los eventos locales no
                            guardados todavía como fuente adicional de "salidos"/"ya
                            entraron", no solo `eventosRegistrados` del servidor.
  HORA 6+ (pulido/tests):   Van a hacer falta tests de reconciliación de marcador (subir/
                            bajar con slots llenos), tests del guard de doble-salida
                            (unit backend), y un test explícito de que
                            `registrar_resultado_directo` ahora SÍ rechaza un batch que
                            excede el tope de cambios del torneo (hoy no lo hace,
                            hallazgo 6).
```

## 0F. Mode Confirmation

**SELECTIVE EXPANSION**, fijado por `/autoplan` (feature enhancement / iteración sobre
sistema existente, no greenfield ni bugfix puro). Alcance base = Track A (3 bugs de
integridad + Quick Action Bar en Resultado Directo + validación de reglas de cambio en
resultado directo) + Track B (slots por marcador con reconciliación, filtrado
titular/suplente con degradación con gracia). Expansiones aceptadas: autofocus al
siguiente slot, contador parcial de progreso, validación temprana de duplicados en el
batch local. Diferidas: restaurar desde localStorage, recordar último equipo (cortada),
fusión completa de motores de eventos. Taste Decision pendiente para el Gate Final:
dirección de display del timeline (Alternativa D).

## Secciones 1-11 (revisión completa, SELECTIVE EXPANSION)

### Sección 1 — Arquitectura

```
  ModalResultadoDirecto.tsx (reescrito)                      MesaPanel.tsx (3 fixes puntuales)
        │                                                           │
        │ +InputMarcador → genera slots[]                          │ fix: titularesEquipo excluye
        │ +QuickActionBar (reusa tap-grid de CargaEvento)           │   salidosOExpulsados (hallazgo 3)
        │ +slots Gol/Autogol (jugador+minuto obligatorio)           │ fix: elegibles de ModalSustitucion
        │ +ModalSustitucion (REUSADO tal cual, sin cambios)         │   excluye titularesPerfilIds (h.2)
        ▼                                                           ▼
  eventos[] (array local, única fuente de verdad — el          CargaEvento (tap-grid existente)
  marcador es DERIVADO, nunca un campo aparte)                       │
        │                                                            │ fix: usa el MISMO helper
        │ +sort ascendente por minuto (Alternativa D, si A elegida)  │   compartido (ya no reimplementa
        ▼                                                            │   su propio filtro sin titular)
  calcularElegibilidadCambios (eventos.ts, EXTENDIDA)◀──────────────┘
        │  +eje titular/suplente (titularesPerfilIds → tercer set)
        │  +acepta también eventos locales no guardados (batch en curso)
        │  +retorna set vacío = "sin convocatoria, sin filtrar" (degrada D4)
        ▼
  POST /api/v1/partidos/{id}/resultado-directo ──▶ PartidoService.registrar_resultado_directo
        │  +ahora llama _validar_reglas_cambio por cada evento tipo Cambio,
        │    dentro del mismo flush() ya existente (atomicidad sin cambios)
        ▼
  EventoPartidoService._validar_reglas_cambio (backend, SIN cambios de firma)
        │  +nuevo guard: jugador_id (quien sale) no puede tener ya un
        │    Cambio previo como saliente en este partido (hallazgo 3)
        ▼
  06_triggers.sql (fn_validar_jugador_partido, fn_validar_tope_titulares) — SIN cambios
```

**Data flow (slot de Gol, las 4 rutas):**
```
  INPUT (input marcador)──▶ VALIDACIÓN (número ≥0, ≤ límite razonable)──▶ TRANSFORM (genera/ajusta slots[])──▶ PERSIST (al guardar todo el batch)──▶ OUTPUT (timeline + marcador)
     │                              │                                          │                                        │                                 │
     ▼                              ▼                                          ▼                                        ▼                                 ▼
  [nil: input vacío]         [negativo o no-numérico]                 [marcador baja con slots        [POST falla: red offline           [timeline no refresca:
   → botón "generar slots"    → rechazar, no generar slots             llenos afectados → confirmar     o rechazo de dominio]              re-render inmediato,
   deshabilitado hasta                                                 cuál se descarta, Alternativa A]  → error inline, batch                es estado local, no
   marcador ≥0 en ambos                                                                                   completo NO se pierde                query — no hace
   lados]                                                                                                 (eventos[] sigue en                 falta invalidar nada]
                                                                                                            memoria, reintentar)
```

**Máquina de estados (slots ↔ eventos[], reconciliación de marcador):**
```
  [sin marcador ingresado] --ingresa 2-1--> [4 slots vacíos: 2 Gol-Local, 2 Gol-Visitante... ]

  espera: "2 Gol Local, 1 Gol Visitante" = 3 slots totales, no 4 (corrección: N slots = suma de
  ambos números, cada uno tipado Gol o Autogol según a quién se le acredita)

  [N slots vacíos] --llena K de N--> [K llenos, N-K vacíos]
        │
        ├──corrige marcador HACIA ARRIBA (ej. Local 2→3)──▶ [agrega 1 slot vacío al final del lado
        │                                                     Local — los K llenos NO se tocan]
        │
        └──corrige marcador HACIA ABAJO, afecta un slot lleno (ej. Local 2→1, con los 2 ya llenos)
                    │
                    ▼
           [modal de confirmación: "¿cuál de los 2 goles cargados se descarta?" — el operador
            elige explícitamente, NUNCA se borra el más reciente/antiguo por default]
```
Estado "imposible" a prevenir: marcador con slots parcialmente indefinidos (ej. "3 slots, 2
dicen Gol-Local y 1 sin tipo asignado") — no debería poder pasar porque el tipo del slot lo
define el marcador mismo al generarlo (todos los slots del lado Local son Gol o Autogol
acreditado a Local, nunca "sin tipo").

**Coupling**: el componente de slots pasa a depender de `ModalSustitucion` (import directo,
sin duplicar su JSX) y del helper extendido de `eventos.ts` — mismas dependencias que
`MesaPanel.tsx` ya tiene, no se crea una dependencia nueva entre módulos que antes no se
tocaban.

**Escalamiento**: sin cambios de forma — el volumen es el mismo (N eventos por partido,
decenas como mucho), el guard nuevo de doble-salida es una consulta indexada por
`partidos_id` + `jugador_id` (mismo índice que ya usa el chequeo de no-retorno).

**Punto único de falla**: ninguno nuevo — `_validar_reglas_cambio` sigue siendo el único
camino de validación de reglas de cambio; ahora simplemente se llama desde 2 lugares
(`create` y `registrar_resultado_directo`) en vez de 1.

**Seguridad**: sin cambios de superficie de autorización — `registrar_resultado_directo`
ya exige `verificar_arbitro_asignado`; el nuevo guard de doble-salida corre dentro del
mismo método ya protegido.

**Escenario de fallo en producción**: el operador cierra la pestaña con el batch de
Resultado Directo a medio llenar (varios slots completados, sin guardar) — hoy esto ya
pierde el trabajo (estado 100% local, sin persistencia intermedia), sin cambios de este
plan. Se registra en "NOT in scope" (persistencia local fue evaluada como delight y
diferida arriba, 0D).

**Rollback**: todo el trabajo es aditivo (nuevo componente de slots, guard nuevo, helper
extendido con un parámetro más) o llama a una función ya existente desde un lugar nuevo
(`_validar_reglas_cambio` desde `registrar_resultado_directo`) — revert de código estándar,
sin migración de esquema involucrada en absoluto (no se agrega ninguna columna).

### Sección 2 — Mapa de Errores y Rescates

```
  MÉTODO/CODEPATH                                | QUÉ PUEDE SALIR MAL                            | CLASE DE EXCEPCIÓN
  -------------------------------------------------|--------------------------------------------------|--------------------
  EventoPartidoService._validar_reglas_cambio      | jugador_id (sale) ya tiene un Cambio previo      | DomainRuleError (nuevo mensaje)
    (nuevo guard, hallazgo 3)                       | como saliente en este partido                    |
  PartidoService.registrar_resultado_directo        | Un evento del batch viola tope de cambios o       | DomainRuleError (ya existe en
    (ahora SÍ valida, hallazgo 6)                    | no-retorno                                        | _validar_reglas_cambio, solo
                                                      |                                                    | faltaba llamarla acá)
  Componente de slots (frontend)                    | Marcador baja afectando un slot ya lleno          | Estado de UI, no excepción —
                                                      |                                                    | requiere confirmación explícita
  Componente de slots (frontend)                    | Dos slots de Cambio en el mismo batch local        | Validación de UI (ver Sección 4)
                                                      | usan el mismo jugador_id_entra                    | antes de intentar el POST
  calcularElegibilidadCambios extendida (frontend)  | Convocatoria no cargada para este partido          | No es error — degrada a "sin
                                                      |                                                    | filtrar", visible en UI
  ModalSustitucion / CargaEvento (ya existentes)    | Backend rechaza el Cambio (tope/no-retorno) pese   | Ya manejado — `apiErrorMessage`
                                                      | al filtro cliente (carrera con otro operador)      | + mensaje de dominio visible

  CLASE DE EXCEPCIÓN                    | RESCATADA? | ACCIÓN DE RESCATE                        | QUÉ VE EL USUARIO
  ---------------------------------------|------------|--------------------------------------------|---------------------------------
  DomainRuleError (doble-salida)         | Sí (nuevo, mismo patrón que no-retorno) | 400 con detail | "{jugador} ya salió por cambio antes en este partido"
  DomainRuleError (tope/no-retorno en    | Sí (reusa código ya rescatado)          | 400 con detail | mismo mensaje que Modo en Vivo
    resultado directo)                   |            |                                              | ya muestra hoy
  Reconciliación de marcador (frontend)  | Sí (por diseño, Sección 1)              | modal de confirmación explícito | nunca un borrado silencioso
  jugador_id_entra duplicado en batch    | Sí (nuevo, cliente)                     | botón "Agregar" deshabilitado + mensaje | "Ese jugador ya está marcado para entrar en otro cambio de esta carga"
    local (frontend)                     |            |                                              |
```
**GAP cerrado por este plan** (era el hallazgo 6): hoy `registrar_resultado_directo` no
llama a `_validar_reglas_cambio` en absoluto — un resultado directo con 10 cambios para un
equipo con tope 5 se acepta sin aviso. Se cierra llamando la misma función ya usada por el
camino en vivo, dentro del mismo `flush()` por evento (mantiene la atomicidad ya diseñada:
si el evento N-ésimo del batch viola una regla, la transacción completa se revierte, ni
Inicio_Partido ni los eventos previos quedan a medias).

### Sección 3 — Seguridad y Modelo de Amenazas
- **Superficie nueva**: 0 endpoints nuevos (el guard de doble-salida vive dentro de
  `_validar_reglas_cambio`, ya invocado por rutas existentes; `registrar_resultado_directo`
  ahora llama una función ya expuesta indirectamente, no agrega superficie). 0 columnas
  nuevas de base de datos.
- **Validación de input**: el marcador (2 números) se valida como entero ≥0 en el
  cliente antes de generar slots — el backend nunca recibe "marcador" como campo, solo
  recibe los eventos ya derivados (mismo contrato que hoy, `ResultadoDirectoCreate`).
  Ningún input nuevo cruza al backend sin pasar por el mismo schema que ya existe.
- **Autorización**: sin cambios — el guard de doble-salida corre dentro de un método ya
  protegido por `verificar_arbitro_asignado`. Nadie nuevo gana acceso a nada.
- **Secretos**: ninguno nuevo.
- **Dependencias**: ninguna nueva.
- **Auditoría**: el guard de doble-salida, al rechazar, deja el intento SIN persistir
  (como cualquier `DomainRuleError`) — no hay un registro explícito de "intento
  rechazado" hoy en el dominio (ninguna otra validación de negocio lo tiene tampoco), así
  que esto es consistente con el patrón existente, no una regresión.
- **Hallazgo de seguridad de datos (confirmado, hallazgo 3)**: sin el guard nuevo, un
  cliente que reintenta un submit (doble-click, o un bug de UI) puede generar un segundo
  evento Cambio con el mismo `jugador_id` saliente sin que nada lo impida hoy — esto ya
  es explotable en producción en Modo en Vivo, no es hipotético del plan nuevo.

### Sección 4 — Flujo de Datos y Casos Límite de Interacción

```
  INTERACCIÓN                            | CASO LÍMITE                              | CUBIERTO? | CÓMO
  ----------------------------------------|--------------------------------------------|-----------|------
  Ingresar marcador                       | 0-0 (sin goles)                            | Sí        | 0 slots generados, timeline puede quedar vacía de goles — 0-0 es válido (ya lo dice el mensaje actual, línea 211)
  Ingresar marcador                       | Marcador muy alto (ej. 25-0, error de tipeo)| Parcial ← GAP | sin límite superior razonable hoy — se agrega validación blanda (advertencia, no bloqueo: fútbol amateur puede tener goleadas reales)
  Corregir marcador                       | Bajar con slots llenos afectados            | Sí (diseñado, Sección 1) | modal de confirmación explícito
  Corregir marcador                       | Subir con slots vacíos ya existentes        | Sí        | agrega slots vacíos al final, no reordena los existentes
  Slot de Cambio (Sale/Entra)             | 0 suplentes elegibles                       | Sí (ya diseñado ayer, ModalSustitucion) | mensaje "no hay suplentes disponibles", reusado tal cual
  Slot de Cambio (Sale/Entra)             | Convocatoria no guardada para este partido  | Sí (nuevo, Alternativa B) | degrada a plantilla completa + aviso visible
  Doble-submit del batch completo         | Click doble en "Guardar resultado"          | Parcial ← GAP | `mutation.isPending` ya deshabilita el botón (línea 246) pero no hay idempotencia server-side explícita del batch — requiere test explícito (ver Sección 6)
  Quick Action Bar (Amarilla/Roja)        | Cerrar el formulario pequeño sin completar   | Sí        | mismo patrón que CargaEvento ya tiene (reset sin persistir, líneas 711-716)
  Timeline reactivo                       | Insertar 2 eventos con el mismo minuto exacto| Sí        | desempate por orden de inserción local (id incremental del array), estable
```
**GAP marcado (doble-submit del batch)** se resuelve en Fase 3 (Eng): agregar test
explícito de POST duplicado para `registrar_resultado_directo`, mismo criterio que ya
existe para convocados (`test_convocatoria_en_vivo.py`) y que el plan de ayer ya había
marcado pendiente para `EventoPartidoService.create` en vivo — este es el mismo gap, en
el segundo camino de escritura.

### Sección 5 — Calidad de Código
- **DRY (hallazgo central de este plan)**: los 2-3 cálculos de elegibilidad de Cambio
  hoy independientes (`CargaEvento` línea 718-725, `ModalSustitucion`'s caller línea
  557-563, y el `ModalResultadoDirecto` sin ningún cálculo) se consolidan en 1 función
  (`calcularElegibilidadCambios` extendida). Esto es la corrección directa del riesgo que
  el plan de ayer (Sección 5) ya había señalado como posible y que el código de hoy
  confirma que efectivamente ocurrió — 2 de los 3 call-sites divergieron.
- **Nombres**: `noEsTitularAhora` (el tercer set que retorna el helper extendido) sigue
  la convención ya establecida de los otros 2 sets (`salidosOExpulsados`, `yaEntraron`) —
  un sustantivo/predicado en español, consistente con el resto del archivo.
- **Organización**: el componente de slots vive en `pages/control-mesa/` junto a
  `ModalResultadoDirecto.tsx` (lo reemplaza/extiende in situ) — no se crea una carpeta
  nueva para 1 componente.
- **Sobre-ingeniería a evitar**: NO construir un "motor de slots genérico" reusable para
  otros tipos de evento futuros (tarjetas también podrían tener "slots", en teoría) — el
  pedido es específicamente sobre goles; generalizar sin un segundo caso de uso real es
  la abstracción prematura que P5 pide evitar.
- **Sub-ingeniería a vigilar**: el contador parcial "X de N goles cargados" (expansión
  aceptada en 0D) debe leer del array `eventos[]` real, no de un contador separado que
  pueda desincronizarse si el operador quita un evento ya cargado (botón "Quitar", línea
  219 ya existe) — mismo cuidado que el contador "cambios usados" de Modo en Vivo ya
  tiene (Sección 5 del plan de ayer).
- **Complejidad ciclomática**: el nuevo componente de slots va a tener varias ramas
  (marcador vacío / slots vacíos / slots parciales / slots completos / reconciliación en
  curso) — vale la pena, desde el inicio, extraer la lógica de reconciliación a una
  función pura testeable aparte (`reconciliarSlots(eventosActuales, marcadorNuevo)`) en
  vez de un `useEffect` con ramas anidadas, siguiendo el patrón ya usado en `alineacion.ts`
  (lógica pura separada del componente, plan `gestionar-partido-alineaciones-plan.md`).

### Sección 6 — Revisión de Tests

```
  NUEVOS FLUJOS UX:
    - Ingresar marcador → ver slots generados (2 Local, 1 Visitante en el ejemplo)
    - Llenar un slot de Gol con jugador+minuto
    - Corregir el marcador hacia arriba con slots ya llenos (no los toca)
    - Corregir el marcador hacia abajo afectando un slot lleno → modal de confirmación
    - Tocar "Cambio" en el Quick Action Bar → Sale filtrado a titulares, Entra a suplentes
    - Sin convocatoria guardada → Sale/Entra muestran plantilla completa + aviso
    - Guardar el batch completo → timeline final ordenada (Alternativa D, según se decida)

  NUEVOS FLUJOS DE DATOS:
    - calcularElegibilidadCambios extendida: con convocatoria → filtra titular/suplente;
      sin convocatoria → set vacío (no filtra)
    - calcularElegibilidadCambios extendida: considera también eventos locales no
      guardados del batch en curso, no solo `eventosRegistrados` del servidor
    - registrar_resultado_directo → ahora llama _validar_reglas_cambio por evento
    - EventoPartidoService._validar_reglas_cambio → nuevo guard de doble-salida

  NUEVOS CODEPATHS:
    - reconciliarSlots(eventosActuales, marcadorNuevo) — función pura nueva
    - Guard de doble-salida en _validar_reglas_cambio

  NUEVOS ERROR/RESCUE PATHS: ver Sección 2 completa arriba.

  NUEVAS INTEGRACIONES: ninguna externa.
```
Para cada ítem: tipo de test, happy/failure/edge:
- Reconciliación de marcador: **Unit** (`reconciliarSlots.test.ts`: subir con llenos, bajar
  sin afectar llenos, bajar afectando llenos → requiere confirmación) — la función pura es
  trivial de testear sin montar React.
- Doble-salida: **Integration** (nuevo `test_doble_salida_cambio.py`: 2do Cambio con el
  mismo `jugador_id` saliente → 400 con mensaje de dominio).
- `registrar_resultado_directo` valida reglas de cambio: **Integration** (extender
  `test_resultado_directo.py`: batch con cambios que exceden el tope → 400, transacción
  completa revertida, 0 filas persistidas).
- Filtrado titular/suplente con y sin convocatoria: **Unit** (`eventos.test.ts`, extender
  el test existente de `calcularElegibilidadCambios` con el caso "sin convocatoria = sin
  filtrar" y "con convocatoria = filtra titular/suplente").
- Quick Action Bar en Resultado Directo: **Component** (nuevo test del componente de
  slots, RTL — abre formulario de Amarilla/Roja, pide jugador+minuto, cierra sin
  persistir si se cancela, mismo patrón que `MesaPanel.test.tsx` ya usa para `CargaEvento`).
- **Test ambición 2am-viernes**: un operador carga un resultado directo de un torneo con
  tope de cambios=3, mete 5 Cambios en el batch local antes de guardar (porque el
  cliente todavía no valida esto en tiempo real dentro del batch) — sin el fix de la
  Sección 2, esto se guarda tal cual, sin aviso, y el reporte de estadísticas del torneo
  queda con datos que violan su propio reglamento. Ese es el test que justifica el
  Bloque de la Sección 2.
- **Test hostil de QA**: doble-click en "Guardar resultado" con conexión lenta (2
  requests simultáneos al mismo `registrar_resultado_directo`) — verificar que no se
  crean 2 partidos finalizados ni se duplican los eventos.
- Pirámide: mayoría unit (`reconciliarSlots`, helper de elegibilidad extendido) +
  integration (guards de servicio) + un puñado de component tests (slots, Quick Action
  Bar) — consistente con el resto del repo, sin E2E nuevos.
- Flakiness: ningún timer nuevo en este plan (a diferencia del plan de ayer, que sí tenía
  el undo de 5s) — no hay riesgo de flakiness por tiempo real acá.

### Sección 7 — Rendimiento
- Sin N+1 nuevos: el guard de doble-salida es una consulta indexada por `partidos_id` +
  `jugador_id` (mismo índice que ya usa el chequeo de no-retorno, confirmado en
  `evento_partido.py:122-128` — mismo patrón de `self.repo.list(...)`).
- Sin estructuras de memoria nuevas de tamaño no acotado — `eventos[]` local en
  `ModalResultadoDirecto` ya existe y crece con el mismo volumen de siempre (decenas de
  eventos por partido, como mucho).
- El componente de slots re-renderiza en cada tecla del input de marcador — verificar que
  la generación/reconciliación de slots no dispare un re-render costoso de toda la lista
  de eventos ya cargados; usar el mismo patrón de `useMemo` que `MesaPanel.tsx` ya usa
  para `marcador`/`cambiosUsadosPorEquipo` (P5: explícito, patrón ya probado).

### Sección 8 — Observabilidad
- Sin dashboards ni alertas nuevas — el volumen y la criticidad de este plan (formulario
  de carga de datos, sin infraestructura nueva) no lo justifica, consistente con el resto
  del dominio de eventos de partido (Modo en Vivo tampoco tiene métricas dedicadas).
- Debuggabilidad: si en 3 semanas se reporta "el resultado directo de tal partido tiene
  un cambio raro", el `DomainRuleError` del guard nuevo (con el mensaje de dominio
  específico) más el registro estándar de excepciones ya logueado por el handler
  genérico (`errors.py`/`handlers.py`, ya existente) es suficiente para reconstruirlo —
  mismo nivel de observabilidad que el resto del dominio, sin gap nuevo.

### Sección 9 — Despliegue y Rollout
- Migraciones: **ninguna** — este plan no agrega columnas ni tablas nuevas (el eje
  titular/suplente ya existe en `ConvocadoAPartido.titular`, se reusa, no se crea).
- Orden de despliegue: backend primero (el guard de doble-salida y la validación de
  reglas de cambio en `registrar_resultado_directo` empiezan a rechazar), frontend
  segundo (empieza a mostrar los nuevos controles) — mismo orden que los 2 planes
  anteriores de este repo ya siguieron.
- Ventana de riesgo: baja — todos los cambios de backend son restricciones nuevas (nunca
  amplían lo que ya se aceptaba), consistentes con el patrón de "agregar guard, nunca
  quitar uno". El único riesgo real: si HOY existe algún resultado directo ya guardado en
  producción con cambios que excedan el tope de su torneo (posible, dado el hallazgo 6),
  el guard nuevo no afecta datos ya persistidos — solo nuevas cargas, sin necesidad de
  backfill ni migración de datos existentes.
- Verificación post-deploy: cargar un resultado directo de prueba con marcador 2-1,
  llenar los 3 slots, intentar un 4to cambio que exceda el tope del torneo de prueba
  (debe rechazar), corregir el marcador a 2-0 con los 2 slots locales ya llenos (debe
  pedir confirmación de cuál descartar).

### Sección 10 — Trayectoria a Largo Plazo
- Deuda introducida: mínima — se consolida deuda existente (el DRY confirmado) en vez de
  agregarla. La bifurcación D4-consciente (con/sin convocatoria) en el helper compartido
  es la única deuda conceptual nueva, y está documentada explícitamente en el código
  (comentario del set vacío = degradación).
- Reversibilidad: 5/5 — todo el código nuevo es aditivo (guard, extensión de función,
  componente nuevo) o reusa componentes existentes sin modificarlos (`ModalSustitucion`
  se importa tal cual). Ningún cambio de contrato de API, ninguna migración de esquema.
- Pregunta a 1 año: un ingeniero nuevo leyendo `calcularElegibilidadCambios` con el
  comentario explícito de por qué el set de titulares puede venir vacío (degradación D4)
  debería entender la decisión sin tener que leer este plan — se decide dejar ese
  comentario en el código, no solo en el plan (mismo criterio que el resto del repo ya
  usa para decisiones no obvias).
- Encaja con la trayectoria ya iniciada por el plan de ayer (un solo motor de validación
  de reglas de cambio, reusado desde ambos caminos de escritura) — la refuerza en vez de
  contradecirla, cerrando la brecha que ese plan dejó abierta sin saberlo (Resultado
  Directo nunca llamaba a `_validar_reglas_cambio`).

### Sección 11 — Diseño y UX (alcance UI confirmado en Fase 0)
Cubierto a fondo en Fase 2 (Design Review) más abajo — acá solo la intencionalidad de
alto nivel:
- **Jerarquía de información**: marcador arriba (input), slots debajo (obligatorios,
  visualmente agrupados por equipo), Quick Action Bar debajo de los slots (tal como pide
  el pedido — "Debajo de los goles"), timeline al final. El pedido ya especifica el orden
  de arriba a abajo; se respeta tal cual, es una jerarquía razonable (dato más
  estructurado primero, eventos sueltos después, historial al final).
- **Cobertura de estados de interacción**: se completa en Fase 2 (Design Pass 2).
- **AI slop**: ninguno esperado — reusa el lenguaje visual ya establecido
  (`tap-grid`, `tap-button`, `modal-panel`) de `control-mesa/`, sin inventar un sistema
  visual nuevo.
- **Responsive**: hereda las decisiones ya tomadas para `control-mesa/` (tap de primera
  clase en todo viewport) — un input numérico + botones no necesita drag, no reabre esa
  decisión.
- **Accesibilidad**: el input de marcador necesita `aria-label` explícito por lado
  ("Goles Local", "Goles Visitante") — se completa en Fase 2.

Recomendación (regla del propio skill): dado el alcance UI real de este plan, correr
`/plan-design-review` a continuación — se ejecuta como Fase 2 de este mismo `/autoplan`.

## "NO en alcance" (diferido con motivo)

- Fusión completa de Modo en Vivo + Resultado Directo en un único motor parametrizado
  (Alternativa C, Approach B) — refactor estructural de la máquina de estados de
  `Partido`, excede 1 día CC, requiere más señal de uso real primero.
- Restaurar un batch local no guardado desde `localStorage` tras un refresh accidental —
  fuera de blast radius directo, requiere diseño de persistencia no pedido.
- Recordar el último equipo usado como default del siguiente evento — mejora marginal no
  pedida.
- Persistencia intermedia del batch de Resultado Directo (guardar parcial antes de
  completar todo) — cambiaría la atomicidad "todo o nada" que la Sección 11 del plan
  original de `control-mesa-centralizacion-fixture-plan.md` fijó a propósito para este
  camino; no se reabre acá.
- Backfill de resultados directos ya guardados que violen el tope de cambios de su
  torneo (posible dado el hallazgo 6) — el guard nuevo solo protege cargas futuras;
  auditar datos históricos es una tarea operativa separada, no de este plan.

## "Qué ya existe" (mapeo completo)

Ver tabla en 0B arriba. Resumen: minuto automático en vivo, tope de titulares/cambios
autoritativo en backend, "Sale" filtrado a titulares reales en Modo en Vivo, contador de
cambios usados, orden cronológico ascendente en el backend, `ModalSustitucion` completo y
reusable tal cual, tap-grid de eventos ya existente en `CargaEvento` — todo esto se reusa
sin tocar.

## Delta de estado ideal

Ver diagrama 0C arriba (CURRENT → THIS PLAN → 12-MONTH IDEAL). Este plan no llega al
ideal de 12 meses (motor de eventos único entre Modo en Vivo y Resultado Directo) pero
cierra 3 brechas de integridad de datos reales y activas hoy (elegibilidad inconsistente,
Entra sin filtrar titulares, doble-salida sin guarda) más el gap funcional del punto 1
del pedido (slots por marcador) — sin las cuales cualquier trabajo futuro sobre reportes
o estadísticas de sustituciones hereda datos potencialmente incorrectos, en CUALQUIERA de
los 2 caminos de carga.

## Registro de Modos de Fallo

```
  CODEPATH                                    | MODO DE FALLO                            | RESCATADO? | TEST? | QUÉ VE EL USUARIO           | LOGUEADO?
  ----------------------------------------------|---------------------------------------------|------------|-------|--------------------------------|----------
  _validar_reglas_cambio (guard doble-salida)   | jugador_id ya salió antes                   | Sí (nuevo) | Sí (nuevo) | mensaje de dominio       | Sí (handler genérico)
  registrar_resultado_directo                    | batch viola tope/no-retorno                 | Sí (nuevo, reusa código) | Sí (nuevo) | mensaje de dominio, 0 filas persistidas | Sí
  Componente de slots (reconciliación)           | marcador baja afectando slot lleno          | Sí (diseñado, Secc. 1)   | Sí (nuevo) | modal de confirmación explícito | N/A (no llega a persistir)
  Componente de slots (batch local)              | jugador_id_entra duplicado en el batch      | Sí (nuevo, cliente)      | Sí (nuevo) | botón deshabilitado + mensaje | N/A (no llega a persistir)
  calcularElegibilidadCambios extendida          | sin convocatoria guardada                   | Sí (por diseño, degrada) | Sí (nuevo) | aviso visible, plantilla completa | N/A (no es error)
  Guardar batch completo                         | doble-submit (2 clicks rápidos)              | Parcial ← GAP            | Sí (nuevo, ver Secc. 6)  | botón ya deshabilitado por `isPending`, falta confirmar idempotencia server-side | Sí (si el 2do intento llega, se loguea como cualquier request)
```
Ninguna fila queda con RESCATADO=N y USUARIO VE=Silencioso — la única fila "Parcial" se
cierra con un test explícito en Fase 3 (Eng), no queda abierta sin plan.

## Diagramas producidos
1. Arquitectura del sistema (Sección 1) ✅
2. Flujo de datos con rutas sombra (Sección 1, slot de Gol) ✅
3. Máquina de estados (Sección 1, reconciliación de slots) ✅
4. Diagrama de despliegue: no aplica (sin infraestructura nueva, sin migraciones — ya
   cubierto en prosa en Sección 9).
5. Flowchart de rollback: no aplica (revert estándar de código, ya cubierto en Sección 1).

## Auditoría de diagramas existentes
No se encontraron diagramas ASCII obsoletos en los archivos que este plan toca — ni
`ModalResultadoDirecto.tsx` ni `eventos.ts` tenían diagramas embebidos en comentarios
antes de este plan.

## Implementation Tasks (CEO phase)
Ver artefacto en disco: `~/.gstack/projects/Score-App/tasks-ceo-review-20260909-122528.jsonl`
(9 tareas, T1-T9 — T1-T5 son Track A, autocontenido; T6-T9 son Track B, dependen de T1).

## Decision Audit Trail (parcial — Fase 1)

| # | Fase | Decisión | Clasificación | Principio | Racional | Rechazado |
|---|------|----------|----------------|-----------|----------|-----------|
| 1 | CEO | Reversión de D1: construir slots por marcador | Mechanical (ya decidido por el usuario fuera de esta revisión) | — | Usuario confirmó explícitamente vía AskUserQuestion | Mantener carga incremental libre sin slots |
| 2 | CEO | Filtrado titular/suplente degrada con gracia sin convocatoria (Alternativa B, Approach A) | Mechanical (hallazgo crítico único incorporado directo) | P1+P4 | Cubre caso feliz y degradado sin bifurcar el modal permanentemente | Approach B (bloquear el flujo entero sin convocatoria) |
| 3 | CEO | Slots derivados de array editable con reconciliación explícita (Alternativa A, Approach A) | Mechanical | P1+P5 | Resuelve exactamente el gap que causó el rechazo de D1 ayer | Approach B (precommit rígido) |
| 4 | CEO | Reusar átomos de UI (ModalSustitucion, tap-grid) en vez de fusionar máquinas de estado (Alternativa C, Approach A) | Mechanical | P2 | Fusión completa excede blast radius (>1 día CC, máquina de estados nueva) | Approach B (fusión completa de motores) |
| 5 | CEO | Dirección de display del timeline (ascendente vs. mantener descendente en Modo en Vivo) | **Taste Decision** | — | Sin ganador claro entre P1 (pedido literal) y P3 (no tocar decisión de UX reciente) | — (surface en Gate Final) |
| 6 | CEO | Autofocus + contador parcial + validación temprana de duplicados | Mechanical (cherry-pick SELECTIVE EXPANSION) | P1 | Mejoras baratas y directas de la propia UI que se construye | — |
| 7 | CEO | Restaurar batch desde localStorage / recordar último equipo / fusión completa de motores | Mechanical (cherry-pick) | P2/P3/P5 | Fuera de blast radius o mejora marginal no pedida | Diferidos a TODOS.md / cortados |

## Completion Summary — CEO Review

```
  +====================================================================+
  |            MEGA PLAN REVIEW — COMPLETION SUMMARY (CEO)             |
  +====================================================================+
  | Mode selected        | SELECTIVE EXPANSION                          |
  | System Audit         | modo-vivo-sustituciones-cierre-plan.md ya    |
  |                       | mayormente implementado; git status solo    |
  |                       | muestra 1 archivo no relacionado modificado |
  | Step 0               | Reversión D1 confirmada por el usuario;      |
  |                       | tensión D4 resuelta con degradación con      |
  |                       | gracia (no Desafío al Usuario — precisión    |
  |                       | técnica, no reversión de dirección)          |
  | Section 1  (Arch)    | 3 diagramas producidos, 0 issues bloqueantes |
  | Section 2  (Errors)  | 6 codepaths mapeados, 1 GAP cerrado (T5)     |
  | Section 3  (Security) | 1 hallazgo confirmado (doble-salida, ya      |
  |                       | explotable hoy en Modo en Vivo)              |
  | Section 4  (Data/UX) | 9 casos límite, 2 GAPS marcados y resueltos  |
  | Section 5  (Quality) | 1 hallazgo central (DRY confirmado, no solo  |
  |                       | teórico), nombres, complejidad anticipada    |
  | Section 6  (Tests)   | Diagrama producido, 6 gaps de test nuevos    |
  | Section 7  (Perf)    | 1 hallazgo (memoización del cálculo de slots)|
  | Section 8  (Observ)  | 0 gaps — nivel consistente con el resto del  |
  |                       | dominio, sin infraestructura nueva           |
  | Section 9  (Deploy)  | 0 migraciones, riesgo bajo, 1 orden definido |
  | Section 10 (Future)  | Reversibilidad: 5/5, deuda: mínima (consolida)|
  | Section 11 (Design)  | intencionalidad alta, detalle completo en    |
  |                       | Fase 2                                       |
  +--------------------------------------------------------------------+
  | NOT in scope         | escrito (5 items)                            |
  | What already exists  | escrito                                      |
  | Dream state delta    | escrito                                       |
  | Error/rescue registry| 6 codepaths, 0 CRITICAL GAPS (todo diseñado) |
  | Failure modes        | 6 total, 0 CRITICAL GAPS tras diseño         |
  | TODOS.md updates     | 2 items (fusión completa de motores,          |
  |                       | persistencia local de batch) — Fase 3        |
  | Scope proposals      | 6 propuestas, 3 aceptadas, 2 diferidas, 1     |
  |                       | cortada                                       |
  | Outside voice        | [subagent-only] — Codex no disponible; 2      |
  |                       | hallazgos críticos y 2 altos incorporados     |
  | Lake Score           | 9/9 tareas eligieron la opción más completa   |
  |                       | (Track A entero + Track B con degradación)    |
  | Diagrams produced    | 3 (arquitectura, flujo de datos, máquina de   |
  |                       | estados de reconciliación)                    |
  | Stale diagrams found | 0                                             |
  | Unresolved decisions | 1 (dirección de display del timeline —        |
  |                       | Alternativa D, Taste Decision, ver Gate Final)|
  +====================================================================+
```

**PHASE 1 COMPLETE.** Codex: no disponible (0 concerns, [subagent-only]). Claude
subagent: 5 hallazgos (2 críticos, 2 altos, 1 medio) — todos incorporados directamente
(reencuadre de la reversión D1 como pendiente de diseño en vez de resuelta, degradación
con gracia para la tensión D4, reuso de átomos de UI en vez de fusión de motores,
separación en 2 tracks independientes, priorización de los 3 bugs confirmados). Consenso:
N/A (voz única) — los hallazgos críticos se incorporaron igual. Pasando a Fase 2 (Design).

---

# FASE 2 — Design Review (alcance UI confirmado en Fase 0)

**DESIGN.md**: no existe en el repo (mismo estado que los 3 planes anteriores). Se
procede con principios universales + convenciones ya establecidas en `control-mesa/`.
**Mockups visuales**: `gstack-design`/`$D` no disponible en esta máquina — revisión
basada en wireframes ASCII + especificación textual, sin imágenes generadas.

**Clasificación**: App UI (mesa de control interna) — jerarquía calma, lenguaje
utilitario, chrome mínimo.

## Paso 0.5 — Voces Duales (Design)

`[subagent-only]` — Codex no disponible, mismo criterio que Fase 1.

**CLAUDE SUBAGENT (design — completitud independiente)** — leyó solo el plan (Fase 1
completa, sin ver esta sección), hallazgos:

1. **Crítico**: el modal de reconciliación está afirmado, no diseñado — dice que existe
   una "confirmación explícita" pero no especifica CÓMO el operador identifica cuál slot
   es el erróneo cuando varios lucen idénticos (jugador+minuto), sin sugerencia por
   default ni escape hatch para cancelar la corrección y mantener el marcador anterior.
2. **Alto**: el estado degradado "sin convocatoria" está afirmado, no diseñado — un
   aviso de una línea no comunica el riesgo real (en modo degradado, un titular en
   cancha SÍ puede aparecer como "Entra", justo lo que el punto 3 del pedido quiere
   prohibir) — y el CEO ya señaló que este caso podría ser la MAYORÍA del uso real, no
   la minoría.
3. **Alto**: ambigüedad de Autogol — el pedido solo describe "Jugador Goleador y
   Minuto" por slot, sin especificar cómo un slot se vuelve Gol vs. Autogol, ni si el
   selector de jugador de un slot Local puede traer jugadores del plantel Visitante.
4. **Medio**: cero cobertura de estados de interacción (loading/empty/error/success) —
   diferido a propósito a Fase 2, pero el batch es atómico (todo o nada) — un rechazo
   del backend (ej. un evento viola el tope de cambios) descarta toda la sesión de
   tipeo del operador si el error no se mapea al slot específico ofensor.
5. **Medio**: la jerarquía (marcador → slots → Quick Action Bar → timeline) solo repite
   el orden literal del pedido, sin peso visual especificado ni respuesta para un
   marcador alto (10-0): ¿scroll? ¿elementos fijos?
6. **Medio**: mismo problema de raíz que el hallazgo 1 — la corrección de marcador no
   tiene escape hatch en general, no solo en el caso de descarte.

```
DESIGN OUTSIDE VOICES — LITMUS SCORECARD:
═══════════════════════════════════════════════════════════════
  Check                                    Claude  Codex  Consensus
  ─────────────────────────────────────── ─────── ─────── ─────────
  1. Marca/producto inconfundible?         N/A (App UI interno)          N/A N/A
  2. Un ancla visual fuerte?                N/A (no aplica a App UI)      N/A N/A
  3. Escaneable solo con encabezados?       PARCIAL — falta peso visual   N/A N/A
  4. Cada sección tiene un solo trabajo?    SÍ (marcador/slots/QAB/       N/A N/A
                                             timeline, cada uno 1 tarea)
  5. ¿Las cards son necesarias?             N/A (reusa `card`/`tap-grid`  N/A N/A
                                             ya existentes)
  6. ¿El movimiento mejora la jerarquía?    N/A (sin animación nueva)     N/A N/A
  7. ¿Premium sin sombras decorativas?      N/A (App UI, no aplica)       N/A N/A
─────────────────────────────────────── ─────── ─────── ─────────
  Rechazos duros disparados:                0 (ninguno de los 7 patrones de landing page aplica)
═══════════════════════════════════════════════════════════════
```
Sin rechazos duros. Los hallazgos reales están en especificidad de estados y de la
lógica de corrección — exactamente lo que las 7 pasadas de abajo resuelven.

## Pass 1 — Arquitectura de Información: 5/10 → 9/10

**Por qué 5**: la jerarquía (marcador → slots → QAB → timeline) es correcta pero
genérica — repite el orden del pedido sin peso visual ni wireframe espacial, y no
resuelve qué pasa con un marcador alto (hallazgo 5 del subagent).

**Wireframe agregado**:
```
┌─────────────────────────────────────────────────────────────────────┐
│ ZONA PRIMARIA (siempre visible, fija arriba — no scrollea)           │
│  Cargar resultado directo — Local vs Visitante                       │
│  Marcador:  Local [ 2 ]  —  [ 1 ] Visitante        (input, autofocus)│
│  Goles cargados: 2 de 2 (Local) · 1 de 1 (Visitante)  ← contador     │
│  parcial (expansión aceptada, 0D), visible apenas hay ≥1 slot        │
├─────────────────────────────────────────────────────────────────────┤
│ ZONA SECUNDARIA (slots, scrollea si son muchos — ver umbral abajo)   │
│  LOCAL                              │  VISITANTE                     │
│  ⚽ Slot 1: #10 Pérez — min 23 ✓     │  ⚽ Slot 1: #7 Gómez — min 40 ✓ │
│  ⚽ Slot 2: (vacío) — elegir...      │                                │
├─────────────────────────────────────────────────────────────────────┤
│ ZONA TERCIARIA (Quick Action Bar — fija, siempre visible debajo de   │
│  los slots, nunca detrás de scroll: son acciones frecuentes)         │
│  [ 🟨 Amarilla ]  [ 🟥 Roja ]  [ 🔄 Cambio ]                          │
├─────────────────────────────────────────────────────────────────────┤
│ ZONA CUATERNARIA (timeline, scrolleable, menor urgencia)             │
│  min 2   ⚽ Pérez (Local)                                             │
│  min 23  🟨 Gómez (Visitante)                                        │
│  min 40  ⚽ Gómez (Visitante)      ← orden: ver Fase 1, Alternativa D │
└─────────────────────────────────────────────────────────────────────┘
```
**Umbral de scroll (resuelve hallazgo 5)**: hasta 6 slots visibles por columna sin
scroll (cubre la enorme mayoría de partidos amateur); más de 6 activa scroll interno de
la zona secundaria — el marcador (zona primaria) y el Quick Action Bar (zona terciaria)
quedan fijos siempre, porque son los controles de mayor frecuencia de uso, mismo
criterio que el plan de ayer fijó para "Fin de Partido forzado" (descubribilidad >
prolijidad visual).

## Pass 2 — Cobertura de Estados de Interacción: 2/10 → 9/10

Tabla completa (resuelve hallazgo 4 — mapeo de error al slot ofensor específico, no solo
al batch):
```
FEATURE                 | LOADING           | EMPTY                    | ERROR                            | SUCCESS                    | PARTIAL
--------------------------|--------------------|---------------------------|------------------------------------|-----------------------------|------------------
Input de marcador         | —                 | sin ingresar → slots no   | valor negativo/no-numérico →       | slots generados, contador  | marcador ingresado
                           |                    | se generan, mensaje       | input rechaza el caracter (mismo   | parcial visible            | solo de un lado →
                           |                    | "ingresá el marcador      | patrón que `<input type=number>`   |                             | el otro lado sigue
                           |                    | para empezar"             | ya usa en el resto del repo)       |                             | sin slots (válido:
                           |                    |                           |                                     |                             | 2-0 es un caso real)
Slot individual            | —                 | vacío → "elegir jugador   | ninguno propio (la validación      | jugador+minuto elegidos,   | jugador elegido,
                           |                    | y minuto"                 | vive al guardar el batch completo, | slot marca ✓                | minuto vacío (o
                           |                    |                           | ver fila "Guardar batch")          |                             | viceversa) → no
                           |                    |                           |                                     |                             | cuenta como lleno
Corrección de marcador     | —                 | —                         | baja afectando slot(s) lleno(s) →  | slots ajustados, contador  | operador cancela la
(resuelve hallazgo 1 y 6)  |                    |                           | modal de reconciliación (ver Pass  | parcial actualizado         | corrección → el
                           |                    |                           | 3 para el diseño completo)         |                             | marcador vuelve al
                           |                    |                           |                                     |                             | valor anterior, CERO
                           |                    |                           |                                     |                             | slots se tocan
Cambio (Sale/Entra)        | spinner al abrir   | 0 elegibles → mismo       | GET de convocatoria falla →        | evento agregado al batch   | sale elegido, entra
                           | (carga convocatoria)| patrón ya resuelto de     | reintentar inline, no bloquea el   | local (aún no persistido)  | pendiente → botón
                           |                    | `ModalSustitucion` (reusado)| resto del formulario              |                             | "Agregar" deshabilitado
Modo degradado (sin        | —                 | —                         | —                                 | —                           | banner persistente (NO
convocatoria, resuelve     |                    |                           |                                     |                             | dismiss-once, ver Pass 6
hallazgo 2)                |                    |                           |                                     |                             | para el diseño completo)
Guardar batch completo     | botón "Guardando..."| —                        | rechazo de dominio (tope cambios,  | partido pasa a Finalizado, | doble-click → 2do
                           | (mismo patrón ya   |                           | doble-salida) → el error se        | modal cierra                | click no-op mientras
                           | existente, línea   |                           | MAPEA al evento específico del     |                             | `isPending` (ya
                           | 246-247)           |                           | batch que lo causó (resalta ese    |                             | existente, línea 246)
                           |                    |                           | slot/evento en rojo, no solo un    |                             |
                           |                    |                           | toast genérico) — resuelve         |                             |
                           |                    |                           | hallazgo 4 del subagent            |                             |
```

## Pass 3 — Recorrido del Usuario y Arco Emocional: 3/10 → 8/10

**Diseño completo del modal de reconciliación (resuelve hallazgo crítico 1 y hallazgo
6 — el mismo problema de raíz que causó el rechazo de D1 ayer, ahora con mecanismo
concreto, no solo "existe una confirmación"):**

```
Operador tipeó "Local 2" por error, quiso decir "Local 1". Ya cargó 2 slots llenos
(#10 Pérez min 23, #14 Ruiz min 55). Corrige el input a "1".

┌───────────────────────────────────────────────────────────────┐
│  Bajaste el marcador de Local a 1 — hay 2 goles cargados        │
│  ¿Cuál de los dos descartás?                                    │
│                                                                   │
│  ○ #10 Pérez — min 23           (sugerido: el más reciente, ●   │
│  ● #14 Ruiz  — min 55            preseleccionado por default)   │
│                                                                   │
│  [ Cancelar — mantener marcador en 2 ]   [ Descartar seleccionado ]│
└───────────────────────────────────────────────────────────────┘
```
Reglas explícitas (cierran el hallazgo 1 del subagent):
- **Sugerencia por default**: el slot más recientemente llenado queda preseleccionado
  (radio button ya marcado) — la corrección típica es "me equivoqué recién", no un gol
  cargado hace rato; el operador puede cambiar la selección con un tap si no es así.
- **Escape hatch explícito**: "Cancelar — mantener marcador en 2" revierte el input al
  valor anterior y CERO slots se tocan — nunca un estado intermedio donde el marcador
  dice 1 pero siguen existiendo 2 slots llenos.
- Ningún borrado ocurre hasta que el operador confirma "Descartar seleccionado" — el
  mismo criterio de "nunca un borrado silencioso" que Fase 1 (Sección 1) ya exigía, acá
  con el mecanismo real, no solo la regla.

**Storyboard (agrega detalle al arco emocional):**
```
PASO | EL OPERADOR HACE                | SIENTE                    | EL PLAN ESPECIFICA?
-----|-----------------------------------|-----------------------------|---------------------
1    | Tipea el marcador final           | Confianza — dato que ya sabe| Autofocus en el primer input (Pass 1)
2    | Llena los slots uno a uno         | Rutina, mecánico            | Contador parcial visible (Pass 1)
3    | Nota que se equivocó en el        | Frustración leve, urgencia  | Modal de reconciliación con
     | marcador                          | de corregir rápido          | sugerencia por default (arriba)
4    | Corrige y confirma (o cancela)    | Alivio si el default era    | Escape hatch explícito (arriba)
     |                                    | correcto; control si no     |
5    | Usa el Quick Action Bar para       | Rutina — ya conoce el patrón| Reusa tap-grid de CargaEvento,
     | tarjetas/cambios                  | (mismo lenguaje visual)     | cero curva de aprendizaje nueva
6    | Guarda el resultado completo       | Ansiedad breve (¿se guardó  | Estado "Guardando..." + mapeo de
     |                                    | bien?)                       | error al slot específico (Pass 2)
```

## Pass 4 — Riesgo de "AI Slop": 8/10 → 9/10

Clasificación: App UI. Ningún patrón de rechazo duro aplica. El wireframe reusa
explícitamente `card`, `tap-grid`, `tap-button`, `modal-panel`, `modal-overlay` — las
mismas clases que `MesaPanel.tsx`/`ModalSustitucion.tsx` ya usan, sin inventar lenguaje
visual nuevo. **Cita concreta** (para no repetir el error de una afirmación de diseño
sin `archivo:línea`, ya señalado en el plan de ayer): `MesaPanel.tsx:759-767` es el
tap-grid que el Quick Action Bar nuevo reusa tal cual.

## Pass 5 — Alineación con el Sistema de Diseño: N/A (no existe DESIGN.md) → recomendación registrada

Sin `DESIGN.md`, no hay tokens que validar. Recomendación ya hecha por los 4 planes
anteriores de este repo — no se repite como hallazgo nuevo, solo se re-registra la
recomendación de correr `/design-consultation` en algún momento futuro, fuera de alcance
de este plan puntual.

## Pass 6 — Responsive y Accesibilidad: 5/10 → 9/10

- El input de marcador necesita `aria-label` explícito por lado ("Goles Local", "Goles
  Visitante") — ya anticipado en Fase 1, Sección 11, confirmado acá como requisito, no
  solo intención.
- **Diseño completo del banner de modo degradado (resuelve hallazgo crítico/alto 2 del
  subagent)**: banner PERSISTENTE (no un toast que desaparece, no "dismiss-once") en la
  zona secundaria, arriba de los selectores Sale/Entra, con `aria-live="polite"` (no
  `assertive` — no es una emergencia como el cierre forzado del plan de ayer, es
  informativo pero debe permanecer legible todo el tiempo que el modo degradado esté
  activo): *"Sin convocatoria guardada para este partido — no se puede distinguir
  titular de suplente. Mostrando el plantel completo."* Además, **tag inline en cada
  opción del selector** cuando el modo está degradado (ej. "#10 Pérez (sin datos de
  alineación)") — refuerzo directo en el punto de decisión, no solo un aviso separado
  que el operador puede no conectar con la lista que tiene enfrente. Esto cierra la
  brecha que el subagent señaló: un aviso de una línea no comunicaba que CUALQUIER
  jugador (incluido un titular en cancha) puede aparecer en "Entra" en este modo.
- Quick Action Bar: objetivo táctil mínimo 44px (mismo criterio que el resto de
  `tap-button` en `control-mesa/`, sin decisión nueva).
- El modal de reconciliación (Pass 3) es el elemento de mayor prioridad de foco de
  teclado mientras está abierto — `role="dialog"` `aria-modal="true"`, mismo patrón que
  `ModalSustitucion.tsx:28` ya usa.

## Pass 7 — Decisiones de Diseño No Resueltas (resueltas en esta pasada)

```
DECISIÓN NECESARIA                          | SI SE DIFIERE, QUÉ PASA                                | RESUELTO
----------------------------------------------|------------------------------------------------------------|------------
Cómo un slot se vuelve Gol vs. Autogol        | el implementador inventa una regla ambigua                | inferido del equipo del jugador elegido: si el jugador pertenece al plantel RIVAL del lado del slot, el evento se guarda como Autogol acreditado a ese lado — mismo criterio que `marcador` en `MesaPanel.tsx:241` ya usa (`acreditadoLocal = tipo === "Autogol" ? equipo !== local : equipo === local`); el selector de jugador de un slot Local SÍ puede traer del plantel Visitante, a propósito (autogol real)
Sugerencia por default en el modal de         | operador debe revisar cada slot manualmente para           | el más recientemente llenado (arriba, Pass 3)
reconciliación                                | encontrar el erróneo, bajo presión                         |
Forma del banner de modo degradado            | un aviso pasivo undersella el riesgo real (titular          | banner persistente + tag inline por opción (Pass 6)
                                               | apareciendo como "Entra")                                  |
Mapeo de error de batch al slot ofensor        | toast genérico, operador no sabe cuál de N eventos falló   | resalta el slot/evento específico en rojo (Pass 2)
Escape hatch en corrección de marcador         | estado intermedio inconsistente (marcador dice X, slots     | "Cancelar — mantener marcador anterior", revierte ambos
                                               | dicen Y)                                                   | atómicamente (Pass 3)
Umbral de scroll para muchos goles             | layout se rompe con un marcador alto (10-0)                 | 6 slots visibles por columna, luego scroll interno; marcador y Quick Action Bar quedan fijos (Pass 1)
```

**PHASE 2 COMPLETE.** Codex: no disponible (0 concerns). Claude subagent: 6 hallazgos (1
crítico, 2 altos, 3 medios) — los 6 incorporados directamente como fixes estructurales
(P5: auto-fix, son gaps de completitud de estados/mecanismo, no preferencias estéticas).
0 hallazgos quedan como Taste Decision en esta fase. Pasando a Fase 3 (Eng, última fase,
revisa el plan ya enmendado por Fases 1 y 2).

## "NO en alcance" (Design)
- `/design-consultation` para un DESIGN.md formal — recomendado, fuera de esta feature
  puntual (mismo criterio que los 4 planes anteriores de este repo).
- Mockups visuales generados por herramienta — no disponible en esta máquina; revisión
  basada en wireframes ASCII + especificación textual.

## "Qué ya existe" (Design)
- `tap-grid`/`tap-button`/`card`/`modal-panel`/`modal-overlay` — vocabulario visual
  completo de `control-mesa/`, reusado sin cambios.
- `ModalSustitucion.tsx` — reusado tal cual para el Cambio del Quick Action Bar, sin
  reimplementar su JSX.
- Patrón de `marcador` derivado (`MesaPanel.tsx:235-246`) — reusado para inferir
  Gol/Autogol por slot (Pass 7) y para el contador parcial (Pass 1).

## TODOS.md updates (Design)
- Ninguna deuda de diseño nueva diferida — los 6 hallazgos se resolvieron dentro de esta
  misma pasada. La recomendación de `/design-consultation` ya está registrada como deuda
  conocida por los planes anteriores, no se duplica acá.

## Implementation Tasks (Design phase)
Los hallazgos de Fase 2 se incorporan como especificación ampliada de T6/T7 (ya
registrados en el artefacto de Fase 1) — no generan tareas nuevas, refinan el alcance de
las existentes: el modal de reconciliación (T6) ahora incluye sugerencia por default +
escape hatch; el Quick Action Bar / slots (T6/T7) ahora incluyen el banner de modo
degradado + tags inline + mapeo de error a slot específico.

## Completion Summary — Design Review

```
  +====================================================================+
  |         DESIGN PLAN REVIEW — COMPLETION SUMMARY                    |
  +====================================================================+
  | System Audit         | Sin DESIGN.md; App UI interno confirmado    |
  | Step 0               | Rating inicial 4/10 (promedio de las 7      |
  |                       | pasadas antes de esta revisión)             |
  | Pass 1  (Info Arch)  | 5/10 → 9/10 (wireframe de 4 zonas + umbral  |
  |                       | de scroll)                                   |
  | Pass 2  (States)     | 2/10 → 9/10 (mapeo de error a slot          |
  |                       | específico, no solo batch)                   |
  | Pass 3  (Journey)     | 3/10 → 8/10 (modal de reconciliación con    |
  |                       | sugerencia + escape hatch, mecanismo real)   |
  | Pass 4  (AI Slop)     | 8/10 → 9/10 (cita concreta agregada)         |
  | Pass 5  (Design Sys)  | N/A → recomendación registrada (sin DESIGN.md)|
  | Pass 6  (Responsive)  | 5/10 → 9/10 (banner persistente + tags      |
  |                       | inline del modo degradado)                   |
  | Pass 7  (Decisions)   | 6 resueltas, 0 diferidas                     |
  +--------------------------------------------------------------------+
  | NOT in scope          | escrito (2 items)                            |
  | What already exists   | escrito                                      |
  | TODOS.md updates      | 0 items nuevos                               |
  +====================================================================+
```

---

# FASE 3 — Eng Review (última fase, revisa el plan ya enmendado por Fases 1 y 2)

## Paso 0 — Scope Challenge

Alcance de Fases 1-2 se mantiene sin reducir (P2, override de autoplan). El plan sigue
tocando ~6-7 archivos, dentro del umbral. Se agrega 1 archivo nuevo no anticipado en
Fase 1 (`backend/app/services/reglas_cambio.py`, ver Sección 1 abajo) como consecuencia
directa de un hallazgo de esta fase — no es scope creep, es la forma correcta de
implementar T4/T5 sin el acoplamiento servicio-a-servicio sin precedente en este repo.

## Paso 0.5 — Voces Duales (Eng)

`[subagent-only]` — Codex no disponible.

**CLAUDE SUBAGENT (eng — independencia arquitectónica)** — leyó solo el plan completo
(Fases 1-2), verificó 6 de las citas de código contra el archivo real (las 6 exactas),
hallazgos:

1. **Crítico**: el guard de doble-salida, si se anida dentro del mismo
   `if not torneo.permite_cambios_ilimitados and data.jugador_id_entra is not None:`
   (`evento_partido.py:121`) que ya existe para no-retorno, queda **desactivado
   exactamente para los torneos con cambios ilimitados** — que es al revés de lo que
   debería pasar: "cambios ilimitados" es un toggle sobre REINGRESO, no licencia para
   registrar la misma salida dos veces. El plan de Fase 1 no lo dejaba explícito.
2. **Alto**: sin defensa contra 2 llamadas concurrentes a `registrar_resultado_directo`
   — el método lee `estado != 'Programado'` una sola vez sin lock de fila; 2 requests
   simultáneos (doble-click antes de que React re-renderice `isPending`, o 2 pestañas)
   pueden ambos pasar el guard y ambos insertar Inicio_Partido+eventos+Fin_Partido. La
   Fase 1 lo dejó como "GAP, ver Sección 6 (test)" sin diseñar el fix real — un test no
   arregla una carrera, solo la detecta.
3. **Alto**: acoplamiento servicio-a-servicio sin precedente — el plan dice que
   `registrar_resultado_directo` "reusa `_validar_reglas_cambio`", pero es un método
   PRIVADO de `EventoPartidoService`, una clase distinta con sus propios repos. Ningún
   servicio de este repo instancia otro servicio (`grep "Service(session)" app/services`
   no encuentra ningún caso). La Fase 1 se saltó esta decisión arquitectónica real.
4. **Alto**: `calcularElegibilidadCambios` extendida, tal como la especificó la Fase 1
   (un solo set negado `noEsTitularAhora`, más una segunda fuente de eventos locales
   pegada encima), es ambigua de polaridad entre sus 2 consumidores (Sale necesita
   "es titular", Entra necesita "es suplente") y, en el caso degradado (sin
   convocatoria), el set vacío no-opea correctamente para Sale pero anula en silencio el
   propósito real del filtro de Entra — cada call-site va a necesitar su propia rama
   para el caso degradado de todos modos, lo que socava el objetivo DRY que la Fase 1 le
   atribuía a este refactor.
5. **Medio**: el invariante "el marcador nunca se desincroniza de `eventos[]`" (razón
   central por la que Fase 1 prefirió Approach A sobre el precommit rígido) puede
   romperse en silencio si `reconciliarSlots` cuenta Autogol con un filtro ingenuo de
   `equipo_id` en vez de la fórmula `acreditadoLocal` que `MesaPanel.tsx:241` ya usa —
   sin un test explícito de esto, la garantía que justificó la decisión de arquitectura
   completa queda sin verificar.

```
ENG DUAL VOICES — CONSENSUS TABLE:
═══════════════════════════════════════════════════════════════
  Dimension                           Claude  Codex  Consensus
  ──────────────────────────────────── ─────── ─────── ─────────
  1. Architecture sound?               NO      N/A    N/A (single voice) — hallazgo 3 y 4 corrigen el diseño abajo
  2. Test coverage sufficient?         NO      N/A    N/A — 4 tests nuevos agregados (hallazgos 1,2,3,5)
  3. Performance risks addressed?      N/A     N/A    N/A — sin hallazgos de performance nuevos
  4. Security threats covered?         PARCIAL N/A    N/A — hallazgo 1 es una brecha de integridad de datos real
  5. Error paths handled?              PARCIAL N/A    N/A — hallazgo 2 (carrera) no tenía fix diseñado, solo test
  6. Deployment risk manageable?       SÍ      N/A    N/A — sin migraciones, sin cambio de contrato
═══════════════════════════════════════════════════════════════
CONFIRMED = both agree. DISAGREE = models differ (→ taste decision).
Missing voice = N/A (not CONFIRMED). Codex no disponible — [subagent-only].
Los 1 hallazgo crítico y 3 altos se incorporan igual (regla: "single critical finding
from one voice = flagged regardless").
```

## Correcciones Fase 3 (aplicadas al diseño de Fase 1, no un plan aparte)

1. **Guard de doble-salida: incondicional, fuera del `if` de no-retorno.** Se mueve a su
   propio chequeo, ANTES del bloque `if not torneo.permite_cambios_ilimitados...` —
   corre siempre, sin importar la configuración de cambios ilimitados del torneo.
   Consulta: `jugador_id` (quien sale ahora) no debe tener ya un evento `Cambio`
   `Registrado` previo con ese mismo `jugador_id` como saliente, en este partido —
   independiente de `permite_cambios_ilimitados` (ese flag gobierna REINGRESO, no
   doble-registro de la misma salida).

2. **Concurrencia de `registrar_resultado_directo`: lock de fila, no solo test.** Se
   agrega `SELECT ... FOR UPDATE` sobre la fila de `Partido` al inicio del método (antes
   de leer `estado`), mismo criterio que cualquier transición de estado exclusiva
   debería usar — el método ya abre una transacción explícita (`session.add()` +
   `flush()` + un solo `commit()` al final, según el comentario existente en
   `partido.py:144-154`), así que agregar el lock es coherente con el diseño ya
   presente, no una reestructuración. Alternativa descartada: índice único parcial sobre
   `(partido_id)` para `tipo_hito='Inicio_Partido'` — más simple, pero el lock de fila
   también protege contra una futura segunda forma de mutar `estado` desde
   'Programado', mientras el índice solo protege esta tabla puntual; se prefiere el lock
   por P1 (cobertura más completa del mismo problema).

3. **Extraer la validación de reglas de cambio a una función compartida, no un método
   privado reusado entre servicios.** Nuevo archivo `backend/app/services/reglas_cambio.py`
   con una función module-level `validar_reglas_cambio(torneo, evento_partido_repo,
   jugador_id, jugador_id_entra, equipo_id, eventos_id) -> None` (lanza `DomainRuleError`,
   no retorna nada) — exactamente la lógica que hoy vive en
   `EventoPartidoService._validar_reglas_cambio`, movida ahí. `EventoPartidoService`
   pasa a llamarla (ya no la define como método propio); `PartidoService.registrar_resultado_directo`
   la importa y la llama directo, instanciando su propio `EventoPartidoRepository(session)`
   (mismo patrón que ya usa para sus otros repos en `__init__`, línea 20-28) — sin que
   ningún servicio instancie a otro. Consistente con el patrón "toda la validación de
   negocio vive en una función/trigger reusable, nunca duplicada" que el propio
   `EventoPartidoService` ya documenta en su docstring de clase.

4. **`calcularElegibilidadCambios` se divide en 2 funciones puras, no 1 función
   sobrecargada.** `deriveHistorialElegibilidad(eventos)` — misma forma que la función
   actual, recibe un array ya mergeado (server + batch local, mergeado por el caller, no
   por la función — el orden de merge se documenta en el JSDoc: eventos del servidor
   primero, luego los locales del batch en curso, para que el desempate por índice sea
   determinístico). `deriveTitularSuplente(titularesPerfilIds, plantilla)` — retorna
   `{titulares: Set, suplentes: Set}` EXPLÍCITOS (no un solo set negado), vacíos ambos
   cuando no hay convocatoria (`titularesPerfilIds.size === 0`) — cada call-site decide
   explícitamente si usa `titulares` (para Sale) o `suplentes` (para Entra), sin
   ambigüedad de polaridad. El caso degradado se vuelve un `if (titulares.size === 0 &&
   suplentes.size === 0)` explícito en cada call-site (mostrar plantilla completa +
   banner), no un no-op implícito que dependía de sets vacíos comportándose "bien" por
   accidente.

5. **`reconciliarSlots` debe usar la fórmula `acreditadoLocal`, no `equipo_id` ingenuo,
   para contar Autogol.** Se documenta explícitamente en el JSDoc de la función y se
   agrega un test unitario dedicado (ver Sección 3) que verifica que un slot Autogol
   cuenta para el lado CONTRARIO al equipo del jugador seleccionado — el mismo caso que
   rompería en silencio el invariante "marcador = f(eventos)" que justificó elegir
   Approach A sobre el precommit rígido en 0C-bis.

## Sección 1 — Arquitectura (diagrama de dependencias, revisado)

```
  ModalResultadoDirecto.tsx                                    MesaPanel.tsx (3 fixes)
        │                                                             │
        │ +InputMarcador, +slots[], +QuickActionBar                  │ usa deriveTitularSuplente
        │ +ModalSustitucion (reusado)                                 │ + deriveHistorialElegibilidad
        ▼                                                             ▼
  reconciliarSlots.ts (NUEVO, función pura)              eventos.ts (2 funciones, separadas de la 1 actual)
        │  usa acreditadoLocal (mismo criterio que                │  deriveHistorialElegibilidad(eventos)
        │  MesaPanel.tsx:241) para contar Autogol                 │  deriveTitularSuplente(titularesPerfilIds, plantilla)
        ▼                                                             │  → {titulares, suplentes} explícitos, nunca 1 set negado
  eventos[] local (única fuente de verdad, marcador derivado)
        │
        ▼
  POST /api/v1/partidos/{id}/resultado-directo
        ▼
  PartidoService.registrar_resultado_directo (backend)
        │  +SELECT ... FOR UPDATE sobre Partido (NUEVO — corrección 2, cierra
        │    la carrera de doble-submit/doble-pestaña)
        │  +instancia su PROPIO EventoPartidoRepository(session) (mismo
        │    patrón que sus otros repos, sin instanciar EventoPartidoService)
        ▼
  validar_reglas_cambio(torneo, evento_partido_repo, ...) ◀── NUEVO módulo compartido
        │  backend/app/services/reglas_cambio.py — función module-level,
        │  llamada por PartidoService Y EventoPartidoService (que pasa a ser
        │  un wrapper delgado sobre la misma función, no la dueña de la lógica)
        │  +guard de doble-salida AHORA INCONDICIONAL (corrección 1 — fuera
        │    del `if not permite_cambios_ilimitados`)
        ▼
  06_triggers.sql (fn_validar_jugador_partido, fn_validar_tope_titulares) — SIN cambios
```

**Coupling (revisado)**: la extracción a `reglas_cambio.py` REDUCE el acoplamiento
propuesto en Fase 1 (que hubiera sido servicio-a-servicio, sin precedente) a
función-a-función, el mismo nivel de acoplamiento que ya existe entre servicios y
repositorios en todo el repo. `EventoPartidoService` pasa de "dueño" de la lógica a
"consumidor" de ella — cambio de forma, no de comportamiento observable (mismos mensajes
de error, mismas condiciones).

**Seguridad (revisado)**: el lock de fila (`SELECT ... FOR UPDATE`) no cambia la
superficie de autorización — corre dentro del mismo método ya protegido por
`verificar_arbitro_asignado`. El guard de doble-salida incondicional cierra una brecha de
integridad de datos que hoy es explotable en producción para CUALQUIER configuración de
torneo (antes de esta corrección, solo se hubiera cerrado para torneos con
`permite_cambios_ilimitados=False`).

**Rollback (revisado)**: `reglas_cambio.py` es un archivo nuevo, aditivo — revert
estándar. El lock de fila es un cambio de comportamiento de concurrencia sin cambio de
esquema — revert estándar también.

## Sección 2 — Calidad de Código (revisado)

- **DRY (reforzado)**: la extracción a `reglas_cambio.py` es el mismo principio que
  motivó consolidar `calcularElegibilidadCambios` en el frontend — una sola función de
  validación de negocio, nunca duplicada entre 2 puntos de entrada (en vivo /
  resultado directo). Antes de esta corrección, el plan de Fase 1 hubiera dejado la
  lógica viviendo en un solo lugar (bien) pero accedida de una forma sin precedente en
  el repo (servicio llamando a otro servicio) — ahora sigue el patrón ya establecido
  (lógica de dominio en una función/módulo compartido, cada servicio la consume).
- **Nombres**: `deriveHistorialElegibilidad`/`deriveTitularSuplente` (prefijo `derive`)
  comunican explícitamente "esto es un cálculo puro sobre datos existentes, no una
  fuente de verdad propia" — mismo criterio de nombrado que ya usa `calcularMinutoActual`
  en el backend (`minuto_partido.py`, prefijo verbal explícito).
- **Complejidad ciclomática**: `validar_reglas_cambio` gana 1 rama más (el guard
  incondicional de doble-salida) — se mantiene por debajo del umbral de 5 ramas que
  Fase 1 (Sección 5) ya había anticipado vigilar.

## Sección 3 — Revisión de Tests (NUNCA se comprime — ver diagrama completo)

```
  NUEVOS FLUJOS UX:               (ver Fase 1, Sección 6 — sin cambios)

  NUEVOS DATOS FLOWS (agregados por esta fase):
    - PartidoService.registrar_resultado_directo adquiere lock de fila antes de leer estado
    - validar_reglas_cambio corre incondicionalmente el guard de doble-salida
    - deriveTitularSuplente retorna {titulares, suplentes} explícitos, vacíos sin convocatoria
    - reconciliarSlots cuenta Autogol vía acreditadoLocal, no equipo_id ingenuo

  NUEVOS CODEPATHS (agregados por esta fase):
    - Guard de doble-salida corre para torneos con permite_cambios_ilimitados=True también
    - Adquisición de lock de fila con 2 requests concurrentes (carrera)

  NUEVOS ERROR/RESCUE PATHS: ver Fase 1, Sección 2 (sin cambios de fondo, solo de dónde
  vive el código que los lanza).
```
Para cada ítem NUEVO de esta fase: tipo de test, happy/failure/edge:
- **Doble-salida con cambios ilimitados** (corrección 1, CRÍTICO — no estaba en el plan
  de Fase 1): **Integration**, nuevo caso en `test_doble_salida_cambio.py`: torneo con
  `permite_cambios_ilimitados=True`, 2do Cambio con el mismo `jugador_id` saliente → 400,
  el mismo mensaje de dominio que con `permite_cambios_ilimitados=False`. Sin este test,
  la corrección 1 puede revertirse sin que nada lo note.
- **Concurrencia de `registrar_resultado_directo`** (corrección 2, ALTO): **Integration**,
  nuevo `test_resultado_directo_concurrencia.py` — 2 requests simultáneos (asyncio.gather)
  al mismo `partido_id` 'Programado'; verificar que solo 1 completa y el 2do recibe un
  error de dominio claro ("este partido ya no está Programado"), no un 500 ni 2 partidos
  Finalizados.
- **Extracción a `reglas_cambio.py`** (corrección 3, sin comportamiento nuevo): los
  tests EXISTENTES de `evento_partido.py` (no-retorno, tope de cambios) deben seguir
  pasando sin modificación — es una refactorización, la suite existente es la prueba de
  regresión; se agrega 1 test nuevo confirmando que `registrar_resultado_directo`
  también rechaza un batch que excede el tope (ya estaba en Fase 1, Sección 6, T5).
- **`deriveTitularSuplente` split** (corrección 4): **Unit**, extender `eventos.test.ts`
  con casos separados para cada función — `deriveHistorialElegibilidad` (mismo test que
  hoy tiene `calcularElegibilidadCambios`, solo renombrado) y `deriveTitularSuplente`
  (con convocatoria → sets correctos; sin convocatoria → ambos sets vacíos, verificado
  explícitamente en vez de asumido).
- **`reconciliarSlots` con Autogol** (corrección 5, MEDIO): **Unit**, nuevo caso en
  `reconciliarSlots.test.ts` — un slot Autogol de un jugador del plantel Visitante debe
  contarse hacia el marcador Local (acreditadoLocal), no hacia Visitante; verifica que
  bajar el marcador Local en 1 ofrece como candidato a descartar tanto un Gol Local como
  un Autogol del Visitante (ambos suman al mismo lado).
- **Test ambición 2am-viernes (actualizado)**: 2 operadores en 2 dispositivos distintos
  cargan resultado directo del MISMO partido 'Programado' al mismo tiempo (ej. un
  árbitro y un delegado de mesa, ambos con acceso) — sin el lock de fila (corrección 2),
  esto crea un partido con eventos duplicados o 2 Hitos `Fin_Partido`, silenciosamente.
- **Test hostil de QA**: cargar un torneo con `permite_cambios_ilimitados=True` y sacar
  al mismo jugador 3 veces seguidas en el mismo batch de resultado directo — antes de la
  corrección 1, esto se aceptaba sin aviso.
- Pirámide: sin cambios respecto a Fase 1 — mayoría unit, integration para los guards,
  component para la UI. El test de concurrencia es el único con perfil distinto
  (requiere `asyncio.gather`, no es un unit test puro) — documentado como tal para no
  sorprender a quien lo lea después.
- Flakiness: el test de concurrencia debe usar timeouts generosos y no depender de
  orden de ejecución real entre los 2 requests (el resultado válido es "exactamente 1 de
  los 2 gana", cualquiera de los 2 — el test no debe asumir cuál).

### Artefacto de test plan (escrito en disco)

Ver `~/.gstack/projects/Score-App/gabriel-main-test-plan-20260909.md` (detalle completo
de casos, mapeado a archivos de test existentes y nuevos).

## Sección 4 — Rendimiento (revisado)
- El `SELECT ... FOR UPDATE` nuevo (corrección 2) es sobre 1 fila por `id` (primary key)
  — sin riesgo de lock de tabla ni de rango; se libera al `commit()` final del mismo
  método, que ya existe.
- Sin cambios respecto al análisis de Fase 1, Sección 7 en el resto (sin N+1 nuevos,
  sin estructuras de memoria no acotadas).

**PHASE 3 COMPLETE.** Codex: no disponible (0 concerns). Claude subagent: 5 hallazgos (1
crítico, 3 altos, 1 medio) — los 5 incorporados como correcciones directas al diseño de
Fase 1 (guard incondicional, lock de fila, extracción a función compartida, split de
funciones puras, fórmula de Autogol en reconciliación). 0 huecos críticos de ingeniería
quedan sin resolver. Pasando al Gate Final.

## "NO en alcance" (Eng, agregado a lo ya listado en Fase 1)
- Índice único parcial como alternativa al lock de fila (corrección 2) — descartado, el
  lock cubre más superficie del mismo problema (ver Corrección 2 arriba).
- Mover MÁS lógica de negocio a módulos compartidos de la que este plan toca — el
  refactor se limita a `validar_reglas_cambio`, el único punto que este plan
  específicamente necesita compartir entre 2 servicios; no se aprovecha para
  "limpiar" otra lógica no relacionada (P5: cambio quirúrgico, no una reorganización
  general del backend).

## "Qué ya existe" (Eng, agregado)
- Patrón de transacción explícita con `commit()` único al final
  (`partido.py:144-154`, ya documentado) — el lock de fila nuevo se inserta dentro de
  ese mismo patrón, sin reestructurarlo.
- `EventoPartidoRepository` — ya instanciable de forma independiente (patrón que
  `PartidoService.__init__` ya sigue para sus otros 4 repos) — se reusa el mismo
  patrón para darle a `PartidoService` su propia instancia, sin acoplarse a
  `EventoPartidoService`.

## Registro de Modos de Fallo (final, agregado tras Fase 3)

```
  CODEPATH                                      | MODO DE FALLO                              | RESCATADO? | TEST? | QUÉ VE EL USUARIO              | LOGUEADO?
  ------------------------------------------------|-----------------------------------------------|------------|-------|-----------------------------------|----------
  validar_reglas_cambio (guard doble-salida,      | jugador_id ya salió antes, CUALQUIER          | Sí (corregido, incondicional) | Sí (nuevo, caso ilimitado) | mensaje de dominio | Sí
    ahora incondicional)                          | configuración de torneo                        |            |       |                                    |
  registrar_resultado_directo (lock de fila)      | 2 requests concurrentes, mismo partido         | Sí (nuevo, corrección 2)  | Sí (nuevo, asyncio.gather) | error de dominio claro al 2do | Sí
                                                    | 'Programado'                                    |            |       |                                    |
  reconciliarSlots (fórmula Autogol)              | Autogol contado con equipo_id ingenuo en vez   | Sí (corregido, fórmula     | Sí (nuevo, corrección 5)  | N/A (invariante interno,     | N/A
                                                    | de acreditadoLocal                             | explícita)                |       | nunca visible al usuario si    |
                                                    |                                                  |                            |       | está bien implementado)       |
```
Todas las filas de Fase 1 + Fase 2 siguen con RESCATADO=Sí tras las correcciones de Fase
3 — ninguna fila queda con RESCATADO=N y USUARIO VE=Silencioso en el registro final.

## TODOS.md updates (agregadas de las 3 fases, escritas ahora)

Presentado como Choice único agregando las 3 fases (autoplan no pausa por cada TODO
individualmente — SELECTIVE EXPANSION delega la decisión en los 6 principios, igual que
el resto de las expansiones de este run):

| # | Item | Fase de origen | Por qué se difiere | Prioridad |
|---|------|-----------------|----------------------|-----------|
| 1 | Fusión completa de Modo en Vivo + Resultado Directo en un único motor de eventos parametrizado por modo | CEO (0C-bis, Alternativa C) | Excede blast radius (>1 día CC), requiere más señal de uso real de qué fracción de resultado-directo tiene convocatoria guardada antes de justificar el rediseño | P3 |
| 2 | Restaurar un batch local de Resultado Directo no guardado desde `localStorage` tras un refresh accidental | CEO (0D, delight) | Fuera de blast radius directo, requiere diseño de persistencia local no pedido | P3 |
| 3 | `/design-consultation` para un DESIGN.md formal del proyecto | Design (recomendación heredada de 4 planes anteriores) | Deuda de diseño conocida, no específica de esta feature | P3 |

Escritas en `TODOS.md` (Fase 3, Eng corre último — agrega las 3 fases en un solo pase).

## Decision Audit Trail (completo — las 3 fases)

| # | Fase | Decisión | Clasificación | Principio | Racional | Rechazado |
|---|------|----------|----------------|-----------|----------|-----------|
| 1 | CEO | Reversión de D1: construir slots por marcador | Mechanical | — | Usuario confirmó explícitamente vía AskUserQuestion | Mantener carga incremental libre sin slots |
| 2 | CEO | Filtrado titular/suplente degrada con gracia sin convocatoria | Mechanical | P1+P4 | Cubre caso feliz y degradado sin bifurcar el modal permanentemente | Bloquear el flujo entero sin convocatoria |
| 3 | CEO | Slots derivados de array editable con reconciliación explícita | Mechanical | P1+P5 | Resuelve exactamente el gap que causó el rechazo de D1 ayer | Precommit rígido |
| 4 | CEO | Reusar átomos de UI en vez de fusionar máquinas de estado | Mechanical | P2 | Fusión completa excede blast radius | Fusión completa de motores |
| 5 | CEO | Dirección de display del timeline | **Taste Decision → resuelta por el usuario en el Gate Final** | — | Usuario eligió ascendente en ambos formularios (cumple el pedido literal) | Mantener descendente en Modo en Vivo |
| 6 | CEO | Autofocus + contador parcial + validación temprana de duplicados | Mechanical | P1 | Mejoras baratas y directas de la propia UI que se construye | — |
| 7 | CEO | Restaurar batch/recordar equipo/fusión completa | Mechanical | P2/P3/P5 | Fuera de blast radius o mejora marginal | Diferidos/cortados |
| 8 | Design | Modal de reconciliación con sugerencia por default + escape hatch | Mechanical (auto-fix estructural) | P1 | Cierra el gap que causó el rechazo de D1 — mecanismo, no solo regla | — |
| 9 | Design | Banner persistente + tag inline para modo degradado (no aviso pasivo) | Mechanical (auto-fix estructural) | P1 | Un aviso de una línea undersellaba el riesgo real señalado por el subagent | Aviso pasivo de una línea |
| 10 | Design | Autogol inferido del equipo del jugador (acreditadoLocal), selector cross-equipo permitido | Mechanical | P5 | Mismo criterio que `MesaPanel.tsx:241` ya usa, sin inventar uno nuevo | — |
| 11 | Design | Umbral de 6 slots visibles antes de scroll, marcador+QAB fijos | Mechanical | P5 | Resuelve el caso de marcador alto sin over-engineering | — |
| 12 | Eng | Guard de doble-salida incondicional | Mechanical (hallazgo crítico único incorporado) | — | Estaba anidado en un `if` que lo desactivaba para torneos con cambios ilimitados — bug, no diseño | Guard anidado (como especificó Fase 1) |
| 13 | Eng | Lock de fila (`FOR UPDATE`) sobre `Partido` en `registrar_resultado_directo` | Mechanical | P1 | Cubre más superficie del mismo problema que un índice único parcial | Índice único parcial |
| 14 | Eng | Extraer `validar_reglas_cambio` a módulo compartido, no método privado reusado | Mechanical | P5 | Ningún servicio del repo instancia otro — sin precedente, se evita introducirlo | Servicio instanciando a otro servicio |
| 15 | Eng | Dividir `calcularElegibilidadCambios` en 2 funciones puras con sets explícitos | Mechanical | P5 | Elimina ambigüedad de polaridad entre consumidores Sale/Entra | 1 función con 1 set negado (como especificó Fase 1) |
| 16 | Eng | `reconciliarSlots` usa fórmula `acreditadoLocal` para Autogol | Mechanical | P1 | Protege el invariante que justificó la decisión de arquitectura completa (0C-bis, Alternativa A) | Filtro `equipo_id` ingenuo |

## Completion Summary — Eng Review

```
  +====================================================================+
  |            MEGA PLAN REVIEW — COMPLETION SUMMARY (ENG)             |
  +====================================================================+
  | Scope challenge      | Alcance mantenido, +1 archivo nuevo         |
  |                       | justificado (reglas_cambio.py)              |
  | Section 1  (Arch)    | Diagrama revisado, 3 correcciones aplicadas |
  | Section 2  (Quality) | DRY reforzado, nombres explícitos            |
  | Section 3  (Tests)   | 21 tests mapeados (7 backend, 14 frontend), |
  |                       | artefacto escrito en disco                   |
  | Section 4  (Perf)    | 1 hallazgo (lock de fila, alcance acotado)   |
  +--------------------------------------------------------------------+
  | NOT in scope          | escrito (2 items nuevos + 5 de Fase 1)       |
  | What already exists   | escrito (2 items nuevos + tabla de Fase 1)   |
  | Test plan artifact     | ~/.gstack/projects/Score-App/gabriel-main-  |
  |                        | test-plan-20260909.md                        |
  | Failure modes          | 3 filas nuevas, 0 CRITICAL GAPS tras diseño |
  | TODOS.md updates       | 3 items (agregados de las 3 fases)           |
  | Outside voice          | [subagent-only] — 1 crítico + 3 altos + 1    |
  |                        | medio incorporados                            |
  | Lake Score             | 5/5 correcciones Eng eligieron la opción más |
  |                        | completa                                      |
  | Diagrams produced      | 1 (dependencias, revisado)                    |
  | Stale diagrams found   | 0                                             |
  | Unresolved decisions   | 1 (dirección de display — Taste Decision,     |
  |                        | Alternativa D, ver Gate Final)                |
  +====================================================================+
```

---

## Review Readiness Dashboard

```
+====================================================================+
|                    REVIEW READINESS DASHBOARD                       |
+====================================================================+
| Review          | Runs | Last Run            | Status                     | Required |
|-----------------|------|---------------------|----------------------------|----------|
| Eng Review      |  1   | 2026-09-09 (hoy)    | CLEAR (PLAN via /autoplan) | YES      |
| CEO Review      |  1   | 2026-09-09 (hoy)    | issues_open (1 unresolved, ver Gate) | no |
| Design Review   |  1   | 2026-09-09 (hoy)    | CLEAR (FULL via /autoplan)| no       |
| Adversarial     |  0   | —                    | —                          | no       |
| Outside Voice   |  0   | —                    | —                          | no (Codex no disponible en esta máquina) |
+--------------------------------------------------------------------+
| VERDICT: CLEARED — Eng Review passed (0 unresolved, 0 critical gaps)|
+====================================================================+
```
Nota de frescura: las 6 entradas de esta corrida comparten `commit 83c2627` /
`wtree 91d3728...` (working tree sucio, `dirty:true`) — son de ESTA sesión, no stale.

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | issues_open | 6 propuestas, 3 aceptadas, 2 diferidas, 1 Taste Decision sin resolver |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | no disponible | Codex no está en PATH en esta máquina |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | clean | 5 issues, 0 critical gaps (todos corregidos) |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | clean | score: 4/10 → 9/10, 6 decisiones |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | omitida | módulo interno, sin superficie de API/CLI/SDK para terceros |

**CROSS-MODEL:** no aplica — Codex no disponible en esta máquina en las 3 fases; todas
las voces fueron `[subagent-only]`.
**VERDICT:** CEO + ENG + DESIGN CLEARED — ready to implement.

**Gate Final resuelto por el usuario (2026-09-09):**
- Alternativa D (Fase 1, Taste Decision): el usuario eligió **orden ascendente en ambos
  formularios** — se quita el `.reverse()` de `MesaPanel.tsx:594` (Modo en Vivo pasa a
  mostrar de menor a mayor minuto, igual que Resultado Directo). Ya reflejado en T8.
- Gate general: **Aprobado tal cual**, incluidas las 16 decisiones del Decision Audit
  Trail (Fases 1-3) y las 14 tareas de implementación (T1-T14).

NO UNRESOLVED DECISIONS
