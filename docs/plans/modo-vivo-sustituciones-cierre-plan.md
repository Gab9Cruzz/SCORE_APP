# Plan: Convocatoria (fix), Resultado Directo (slots por marcador), Modo en Vivo (cronómetro + cambios) y Cierre forzado de partido

<!-- /autoplan: nuevo plan, sin restore point previo (el archivo no existía) -->

**Branch**: `feat/equipos-jugadores-plan` · **Fecha**: 2026-09-08 · **Solicitado por**: Gabriel Cruz

## Pedido original (verbatim, traducido del prompt del usuario)

### 1. Gestión Previa: Convocatorias y Validaciones de Alineación
- Flujo "No Convocado" → "Convocado" → réplica de la lógica interactiva de Titulares/Suplentes (click o drag).
- **Bug de Límite Máximo**: el sistema permite colocar 8 titulares en un torneo de Fútbol 7. Bloquear estrictamente para no exceder el máximo definido por el formato del torneo.
- **Arranque con mínimos permitidos**: el botón "Empezar Partido" debe activarse al llegar al mínimo reglamentario, sin exigir cupo total.

### 2. Ingreso Diferido: "Cargar Resultado Directo"
- UI basada en el marcador: el operador ingresa el marcador final primero (Local 2 - Visitante 1) y el sistema renderiza "slots" (2 pelotitas a la izquierda, 1 a la derecha) que obligan a cargar jugador+minuto de cada gol.
- Barra de eventos adicionales (Amarilla, Roja, Cambio) debajo, cada una pide jugador+minuto al presionar.
- Ordenamiento cronológico automático de todo el historial de hitos por minuto.

### 3. Modo en Vivo: Cronómetro y Cambios (`/control-de-mesa/partido/{id}`)
- Sincronización de tiempo: con el partido "En Curso", el minuto de cada evento se captura automáticamente del cronómetro en ejecución, sin pedirlo manualmente.
- Flujo de sustituciones ligado al flujo de eventos: seleccionar un titular en la alineación en vivo para sacarlo abre un modal "¿Por quién ingresa?"; al confirmar se registra como Hito cronológico.
- Reglas por disciplina: deportes sin retorno del jugador que sale (fútbol profesional) vs. cambios rotativos ilimitados (básquet, fútbol 7 amateur).

### 4. Control de Estado: Excepción de "Fin de Partido"
- Terminación forzada (override): habilitar "Fin de Partido" como acción global permitida en cualquier estado (incluso 1er tiempo), con confirmación de seguridad, cerrando el partido permanentemente.

---

## Estado actual verificado en código (working tree, no HEAD — hay cambios sin commitear en curso de `gestionar-partido-alineaciones-plan.md`)

> Fuente: exploración exhaustiva de `AlineacionEditor.tsx`, `alineacion.ts`, `GestionarPartido.tsx`, `ModalResultadoDirecto.tsx`, `Cronometro.tsx`, `MesaPanel.tsx`, `eventos.ts`, `useEmpezarPartido.ts`, `hito_partido.py`, `partido.py`, `torneo.py`, `modalidad.py`, `evento_partido.py`, `errors.py`/`handlers.py`, tests nuevos y `TODOS.md`. Cita archivo:línea donde aplica.

### Área 1 — Convocatoria/alineación
- El editor real es `frontend/src/pages/control-mesa/AlineacionEditor.tsx` + `alineacion.ts` (lógica pura), NO `MesaPanel.tsx` (que solo consume la convocatoria ya guardada, líneas 52-54).
- Modelo: `Seleccion = Map<jugador_perfil_id, boolean>` (`alineacion.ts:21`). Ausente = No Convocado, `false` = Suplente, `true` = Titular. Son 3 estados, no 4.
- Mover entre zonas: botón ↑/↓ tap (`renderFila`, líneas 117-134) **y** drag & drop (`usePointerDrag`, línea 89), habilitado solo en viewport ≥1000px (decisión de producto ya tomada y confirmada por el usuario en el gate anterior: tap de primera clase en todo viewport, drag solo desktop).
- Atajo `marcarPrimerosComoTitulares` (`alineacion.ts:53-69`) asigna titular a los primeros N por dorsal.
- Con `enCurso=true`: no se puede bajar titular a suplente (`moverA` línea 64), no se puede destildar convocado (checkbox disabled línea 223), solo alta aditiva de suplente (`onSumarTardio`, línea 226).
- **Validación de MÁXIMO de titulares: confirmado que NO EXISTE, por decisión consciente y repetida**, no por bug:
  - `moverA` (`alineacion.ts` líneas 62-77) nunca rechaza un movimiento por exceso; solo calcula `faltan` (línea 60).
  - No hay campo `max_titulares` en `torneo.py` ni `modalidad.py`. `Modalidad.tamano_equipo` (`modalidad.py:25`) existe pero nada lo usa como tope superior de `ConvocadoAPartido.titular=True`.
  - **`TODOS.md:462-464` y `gestionar-partido-alineaciones-plan.md:2275-2277` documentan explícitamente esto como Decisión Audit #12 del plan anterior, diferida a propósito**: *"la validación nueva exige el mínimo al iniciar, no bloquea un exceso marcado en Convocatoria"*.
  - **Implicación para este plan**: lo que el usuario llama "bug" es en realidad la reversión de una decisión de alcance tomada explícitamente hace horas, en el mismo branch, por el mismo pipeline de revisión. Se trata como reversión de decisión, no como bugfix — ver Fase 1, Premisa P-max.
- Mínimo para "Empezar Partido": **ya implementado end-to-end**, no es trabajo nuevo:
  - `database/27_migracion_minimo_titulares.sql` + `torneo.py:63` (`minimo_jugadores_para_iniciar`, `NULL` = usar `tamano_equipo`).
  - `hito_partido.py:147-201` (`_minimo_requerido`, `_contar_titulares` contra roster activo real) + `_validar_titulares` (líneas 220-245) en `registrar()` para `Inicio_Partido`.
  - `GET /partidos/{id}/preflight-inicio` (líneas 247-312) separado del `GET /cronometro` público.
  - `GestionarPartido.tsx:504-514` consume el preflight server-side, no reimplementa la regla en cliente.
  - Cubierto por `test_minimo_para_iniciar.py` (289 líneas) y `test_titulares_inicio_partido.py`.

### Área 2 — Resultado Directo
- `ModalResultadoDirecto.tsx`, abierto desde `GestionarPartido.tsx:515-517`, solo visible si `!enCurso`.
- El marcador **no se ingresa directo como número** — se deriva agregando eventos Gol/Autogol uno a uno. **No hay slots dinámicos basados en marcador** hoy: es un formulario libre (tipo → equipo → jugador (+ jugadorIdEntra si Cambio) → minuto → "+ Agregar evento", líneas 133-209), ya pide jugador+minuto por evento — eso ya existe.
- Backend: `partido.py:124-209` (`registrar_resultado_directo`) — una sola transacción, guards de estado/torneo archivado/Corrido con ganador explícito. Deliberadamente NO valida convocatoria (decisión D4 documentada).
- Orden cronológico: `hito_partido.py` repository ordena por `id` (orden de inserción = orden cronológico real para Hitos). **Para `EventoPartido` no se encontró `ORDER BY minuto` en el repositorio** — el orden que se ve hoy en `MesaPanel.tsx:449` es un `.sort()` client-side descendente. Esto es una brecha real para el requisito de "reordenamiento automático cronológico".
- `test_resultado_directo.py` (231 líneas) cubre happy path, atomicidad, rechazos de estado/torneo archivado, no exige convocatoria — sólido.

### Área 3 — Modo en vivo: cronómetro y cambios
- `Cronometro.tsx` **no expone el minuto actual hacia afuera** (sin prop/callback `onMinutoActual`). Es un componente aislado que solo registra Hitos de tiempo (`Inicio_Partido`, `Inicio_Periodo`, `Pausa`, `Reanudacion`, `Fin_Periodo`, `Fin_Partido`) y pinta su propio `formatearMMSS`.
- `CargaEvento` en `MesaPanel.tsx` (líneas 536-709) **pide el minuto manualmente** vía `<input type="number">` (líneas 688-696) — no hay integración con `Cronometro`. Esta es la brecha central del punto 3 del pedido.
- Cambios/sustituciones: ya existen como tipo de evento (`"Cambio"`, `jugador_id` + `jugador_id_entra`), NO como pantalla aislada — pero el flujo actual es un `<select>` en el mismo formulario de `CargaEvento`, no un modal contextual disparado desde tocar a un titular en la alineación en vivo. `MesaPanel.tsx:572-591` calcula heurísticamente (no autoritativo) quién ya salió/fue expulsado para filtrar los `<select>`.
- **No hay límite de cantidad de cambios ni regla de "no-retorno" a nivel backend.** `EventoPartidoService.create` (`evento_partido.py:58-65`) solo valida árbitro asignado + partido en curso + trigger SQL de pertenencia al equipo.
- **No existe ningún campo de "disciplina/reglas de cambio" en el modelo.** `Disciplina` (`disciplina.py`) es catálogo puro. `Modalidad` (`modalidad.py`) solo tiene `tamano_equipo`/`tamano_plantilla_max`. Nada distingue fútbol profesional (sin retorno) de básquet/fútbol 7 amateur (rotativo ilimitado).

### Área 4 — Fin de partido / máquina de estados
- La máquina de estados real vive en `hito_partido.py:78-132` (`_calcular_estado`, deriva `acciones_permitidas` de la lista de Hitos), NO en `PARTIDOS.estado`.
- Gate real de "Fin de Partido" en modo `Periodos`: solo si `periodo_abierto is None` y `ultimo_periodo_cerrado == cantidad_periodos` (líneas 120-121). En modo `Corrido`: siempre disponible mientras iniciado y no finalizado (línea 123), pero exige `ganador_corrido_id` explícito (líneas 339-343).
- **`PartidoService.update` (`partido.py:69-76`) NO valida transiciones de `estado` en absoluto** — un `PATCH {estado: "Programado"}` sobre un partido `Finalizado` se acepta sin control (`schemas/partido.py:47`). Esto es un ítem del plan anterior (Bloque 2) que **quedó explícitamente pendiente** ("Agregar además validación de máquina de estados en `PartidoService.update`" — no implementado).
- Frontend: el botón "Fin de Partido"/"Finalizar partido" vive en `Cronometro.tsx` (líneas 259-293), 100% gateado por `acciones_permitidas` que viene del backend — no hay lógica de habilitación duplicada en cliente.
- No existe `EstadoInvalidoError` específico — todo pasa por `DomainRuleError` genérico (`errors.py:25-36` → 400).

### Bloques del plan anterior (`gestionar-partido-alineaciones-plan.md`) ya en código vs. pendientes
- Implementados: Bloque 0 (deadlock convocatoria↔arranque), Bloque 1 (reubicación de archivos), Bloque 3 (vista `GestionarPartido`), Bloque 4 (32 tests especificados, en su mayoría).
- Bloque 2 implementado **excepto** la validación de máquina de estados en `PartidoService.update` — que es exactamente lo que el punto 4 de este pedido necesita.
- Diferidos y aún diferidos (confirmado contra código): tope superior de titulares (punto 1 de ESTE pedido lo reabre), formación en cancha, minutos jugados, copiar alineación del partido anterior.

---

# FASE 1 — CEO Review (`/autoplan`, modo SELECTIVE EXPANSION)

**Modo**: fijado por `/autoplan` para "feature enhancement / iteración sobre sistema existente" (no greenfield, no bugfix puro, no refactor). Alcance actual = baseline bulletproof; expansiones se ofrecen individualmente y se auto-deciden con los 6 principios (completitud, hervir el lago, pragmatismo, DRY, explícito>clever, sesgo a la acción) salvo Desafíos al Usuario.

## Paso 0.5 — Voces Duales (CEO)

Codex no está disponible en esta máquina (`which codex` → not found), consistente con los 3 planes anteriores de este branch/repo. **`[subagent-only]`** — una sola voz revisora independiente, no dual-voice real.

**CLAUDE SUBAGENT (CEO — independencia estratégica)** — leyó únicamente este archivo (sin ver el research previo ni conversación), resumen de hallazgos:

1. **Finding #0 (crítico, ya resuelto por esta misma Fase 1)**: el research crudo referenciaba "Fase 1, Premisa P-max" sin que existiera — el subagente revisó el documento a mitad de escritura. Resuelto: esta sección completa la Fase 1.
2. **Q1 — Reframe de mayor apalancamiento**: las 4 Áreas no comparten causa raíz; solo comparten superficie (`control-de-mesa`). El hallazgo de mayor apalancamiento real: `PartidoService.update` (Área 4) acepta `PATCH {estado: X}` sin validar la máquina de estados — un hueco que socava las 3 áreas restantes (un "Fin de Partido" forzado, un log de sustituciones, un resultado directo no valen nada si el estado se puede desandar con un PATCH suelto).
3. **Q2 — "Bug de Límite Máximo" es un reetiquetado peligroso**: confirmado por código que es la Decisión Audit #12 (diferida dos veces, con razonamiento escrito). Nombrar esto "bug" borra la decisión de la vista. **Fix aplicado abajo**: se trata explícitamente como reversión de decisión, nunca como bugfix, en todo este documento.
4. **Q3 — Escenario de arrepentimiento a 6 meses**: (a) revertir Audit #12 sin el llamado explícito de reversión pierde la razón original si hay que revertir otra vez; (b) reglas de sustitución ancladas al eje equivocado (disciplina vs. modalidad vs. nivel competitivo); (c) el override de Fin de Partido (Área 4) se suma como mecanismo nuevo de cierre mientras el hueco de `PartidoService.update` (ya conocido, ya señalado en TODOS.md) sigue abierto — la peor combinación: dos puertas para cerrar (una validada, una no) en la misma pieza de estado.
5. **Q4 — Alternativa no analizada (Área 2, slots por marcador)**: el research ya muestra que el requisito funcional (jugador+minuto por gol) **ya existe** vía carga incremental libre. Comprometerse a un marcador final ANTES de cargar los eventos crea un problema de reconciliación no diseñado: si el operador se equivoca al tipear el marcador (2-1 en vez de 2-2) y ya cargó 2 goles locales + 1 visitante en los slots generados, corregir el marcador a 2-2 debe (a) preservar los 3 eventos ya cargados y agregar un slot visitante más, o (b) regenerar slots y perder lo cargado. Ninguna opción está diseñada en el pedido original. El modelo incremental actual evita esto por diseño (el marcador es un total derivado, nunca un input pre-comprometido).
6. **Q5 — Riesgo "competitivo" interno**: no aplica riesgo de mercado (herramienta interna). Riesgo real: (a) la reversión de Audit #12 compite con el razonamiento de la propia revisión anterior sobre el mismo branch; (b) una regla de sustitución nueva y autoritativa en backend, sumada al filtro heurístico ya existente y NO autoritativo en `MesaPanel.tsx:572-591`, crea dos fuentes de verdad que pueden divergir (cliente dice "aún elegible", backend rechaza, o viceversa) — viola la Directiva Prima #1 (cero fallos silenciosos) por omisión si no se reconcilian en el mismo cambio.
7. **Flag adicional (crítico) — conflación disciplina/modalidad/nivel**: confirmado por inspección directa de `disciplina.py` (catálogo puro, sin campos de regla) y `modalidad.py` (solo `tamano_equipo`/`tamano_plantilla_max`, sin campo de regla de cambios). El pedido del usuario mezcla 3 ejes distintos: disciplina (fútbol vs. básquet), modalidad (Fútbol 11 vs. Fútbol 7 — misma disciplina), y un nivel competitivo (profesional vs. amateur) que **no existe en ningún lado del esquema**. "Por disciplina" es el grano equivocado: el propio ejemplo del usuario necesita distinguir entre dos modalidades de la MISMA disciplina (Fútbol). El subagente recomienda seguir el precedente exacto de `Torneo.minimo_jugadores_para_iniciar` (reglamento del torneo, no del catálogo): un campo nuevo en `TORNEO`, no en `DISCIPLINA` ni `MODALIDAD`, para separar "qué deporte/formato" de "qué nivel competitivo".

```
CEO DUAL VOICES — CONSENSUS TABLE:
═══════════════════════════════════════════════════════════════
  Dimension                           Claude  Codex  Consensus
  ──────────────────────────────────── ─────── ─────── ─────────
  1. Premises valid?                   NO      N/A    N/A (single voice) — hallazgo crítico igual se incorpora
  2. Right problem to solve?           PARCIAL N/A    N/A — reframe de apalancamiento incorporado (Bloque 0 nuevo)
  3. Scope calibration correct?        NO      N/A    N/A — Área 2 marcada TASTE/posible Desafío al Usuario
  4. Alternatives sufficiently explored?NO     N/A    N/A — 0C-bis abajo añade alternativas Área 2 y Área 3
  5. Competitive/market risks covered? N/A (interno) N/A N/A — riesgo interno de regresión sí cubierto
  6. 6-month trajectory sound?         NO      N/A    N/A — depende de resolver Área 4 antes que Área 4-override
═══════════════════════════════════════════════════════════════
CONFIRMED = both agree. DISAGREE = models differ (→ taste decision).
Missing voice = N/A (not CONFIRMED). Codex no disponible en esta máquina — [subagent-only].
Todos los hallazgos "crítico"/"alto" de la única voz disponible se incorporan igual (regla:
"single critical finding from one voice = flagged regardless").
```

## 0A. Premise Challenge

1. **¿Es el problema correcto?** Parcialmente. Las Áreas 2-4 son gaps reales y aislados (ordenamiento cronológico de eventos, sincronización de minuto con cronómetro, validación de máquina de estados). El Área 1 mezcla dos cosas de naturaleza distinta: (a) el "flujo No Convocado→Convocado" que el pedido describe como si no existiera, cuando **ya existe end-to-end** en `AlineacionEditor.tsx` (click y drag, con mínimo funcionando); y (b) una reversión real de una decisión de producto tomada dos veces en este mismo branch.
2. **¿Cuál es el resultado real de negocio?** Que una mesa de control pueda operar un partido completo (antes, durante, después) sin bloqueos falsos ni datos que mientan sobre lo que pasó. La máquina de estados sin validar (`PartidoService.update`) es la amenaza directa a ese resultado — es más directa que cualquiera de las 4 Áreas nombradas explícitamente.
3. **¿Qué pasaría si no hacemos nada?** El dolor real y verificable en código: (i) hoy se pueden cargar 8 titulares en Fútbol 7 sin ningún aviso — dato incorrecto que después alimenta estadísticas y validación de convocatoria; (ii) cargar un evento en vivo exige tipear el minuto a mano mientras el cronómetro ya lo sabe — fricción operativa, no bug de datos; (iii) un `PATCH` de estado sin validar es una bomba de tiempo silenciosa, no reportada hasta ahora en ningún test ni TODO.

**Premisa cuestionada (Premisa P-max)**: el pedido llama "bug" a la ausencia de tope de titulares. **Es falso que sea un bug** — es la Decisión Audit #12 del plan anterior (`gestionar-partido-alineaciones-plan.md:2275-2277`, `TODOS.md:462-464`), tomada explícitamente y reafirmada. La premisa "esto es un bug a corregir" se reemplaza por: "el usuario, con más contexto de uso real, quiere revertir Audit #12". Se acepta la reversión (P6, premisas razonables se aceptan) porque el usuario la pide con un ejemplo concreto y verificable (8 titulares en Fútbol 7 realmente posible hoy) — pero se documenta como reversión, nunca como bugfix, y se registra en el audit trail de decisiones (ver Decisión D-CEO-1 abajo). No es un Desafío al Usuario (el usuario mismo la pide con contexto nuevo, ningún modelo se opone a la reversión en sí — solo a que se la llame "bug").

## 0B. Existing Code Leverage

Ya cubierto exhaustivamente en "Estado actual verificado en código" arriba. Resumen de mapeo sub-problema → código existente:

| Sub-problema del pedido | Código existente que ya lo resuelve |
|---|---|
| Flujo No Convocado→Convocado, click/drag | `AlineacionEditor.tsx` + `alineacion.ts` — completo, no hace falta reconstruir nada |
| Botón "Empezar Partido" con mínimo | `preflight-inicio` + `useEmpezarPartido.ts` — completo |
| Jugador+minuto por gol/tarjeta | `ModalResultadoDirecto.tsx` formulario libre — completo, solo falta el marco "slots" que pide el usuario (Área 2 es una cuestión de UI, no de datos faltantes) |
| Botón "Fin de Partido" gateado por reglas | `Cronometro.tsx` + `hito_partido.py:_calcular_estado` — completo para el caso NO forzado |

Nada de esto se reconstruye. El plan es 100% aditivo/correctivo sobre piezas existentes, no un rediseño.

## 0C. Dream State Mapping

```
  ESTADO ACTUAL                              ESTE PLAN                                  IDEAL A 12 MESES
  ────────────────                           ─────────                                  ─────────────────
  Convocatoria: mínimo OK,     ------->      + tope de titulares por        ------->    Alineación completa:
  máximo sin control                         formato (server + UI)                      titular/suplente/lesionado/
                                                                                          sancionado, con historial
  Resultado directo: formulario ------->      + orden cronológico real       ------->    Un solo motor de eventos
  libre, orden client-side                    en backend (EventoPartido)                 (en vivo y diferido
                                                                                          comparten la misma
                                                                                          validación y el mismo
                                                                                          orden), sin duplicación
  Minuto de evento: manual      ------->      + captura automática del      ------->    Cronómetro como fuente
  siempre                                     minuto en curso (partido                   única de tiempo para
                                              En Curso)                                  todo el sistema (eventos,
                                                                                          hitos, reportes)
  Cambios: tipo de evento sin   ------->      + modal contextual desde      ------->    Reglas de sustitución
  límite ni regla de disciplina               alineación en vivo + regla                 parametrizables por
                                              autoritativa por TORNEO                    torneo, con historial de
                                                                                          quién entró/salió y cuándo
  Fin de Partido: solo vía      ------->      + override global con         ------->    Máquina de estados de
  máquina de hitos, sin                       confirmación + FIX del hueco               PARTIDOS.estado
  override para casos externos               de PartidoService.update                    completamente validada,
                                                                                          con motivo auditado para
                                                                                          cada cierre forzado
```

## 0C-bis. Implementation Alternatives (MANDATORY)

### Alternativa para Área 1 (tope de titulares)

**APPROACH A: Bloqueo server-side + UI (recomendado)**
  Summary: nuevo campo `Modalidad.max_titulares` (o reutilizar `tamano_equipo` como tope si el reglamento del torneo no lo sobreescribe), validado en el mismo lugar que ya valida el mínimo (`hito_partido.py::_validar_titulares` para el gate al iniciar) MÁS un guard en el endpoint de convocatoria (`ConvocadoAPartidoService`) que rechaza marcar titular #N+1 cuando ya hay `tamano_equipo` titulares activos. UI: `moverA` en `alineacion.ts` rechaza el movimiento en el cliente ANTES de llamar al backend (evita el viaje de red), y el backend igual valida (nunca confiar solo en cliente).
  Effort: S (backend: 1 guard + 1 test; frontend: 1 condición en `moverA` + 1 mensaje de error).
  Risk: Bajo — mismo patrón que el mínimo, ya probado.
  Pros: cierra el hueco real (8 titulares en Fútbol 7 hoy es posible); reutiliza el campo `tamano_equipo` que YA distingue formatos (Fútbol 7 vs 11) sin necesitar columna nueva.
  Cons: reabre una decisión ya tomada dos veces — requiere el llamado explícito de reversión (ver 0A).
  Reuses: `Modalidad.tamano_equipo`, patrón de `_validar_titulares`, patrón de `moverA`.

**APPROACH B: Solo UI, sin guard de backend**
  Summary: bloquear el movimiento únicamente en `alineacion.ts` (cliente), sin tocar el backend.
  Effort: XS.
  Risk: Alto — cualquier llamada directa a la API (o un bug futuro en el cliente) puede seguir generando >tamano_equipo titulares. Viola Directiva Prima #1 (cero fallos silenciosos) y el patrón ya establecido (el mínimo SÍ se valida server-side).
  Pros: más rápido de escribir.
  Cons: fuente de verdad dividida, inconsistente con el precedente inmediato (mínimo sí valida ambos lados).
  Reuses: `moverA`.

**RECOMENDACIÓN: Approach A** — P1 (completitud) + P5 (explícito). El patrón ya existe para el mínimo; replicarlo para el máximo es el camino obvio, no una abstracción nueva. Completeness: A=9/10, B=4/10.

### Alternativa para Área 2 (resultado directo — slots por marcador)

**APPROACH A: Mantener carga incremental libre + arreglar orden cronológico (recomendado)**
  Summary: no tocar la UI de `ModalResultadoDirecto.tsx` (ya pide jugador+minuto por evento, uno a la vez). Único cambio real: `EventoPartido` debe ordenarse por `minuto` (y por `id` como desempate estable) tanto en el repositorio backend como en el render de `MesaPanel.tsx` (hoy hace `.sort()` client-side descendente — moverlo a ascendente y, más importante, que el backend devuelva ya ordenado para que cualquier consumidor futuro no tenga que reimplementar el sort).
  Effort: S (1 `ORDER BY` en el repositorio + ajustar el sort de `MesaPanel.tsx` + tests).
  Risk: Bajo.
  Pros: cero riesgo de reconciliación (no hay slots pre-comprometidos que puedan quedar huérfanos si el operador corrige el marcador); resuelve el ÚNICO gap real que el research encontró (orden cronológico) sin tocar una UI que ya funciona.
  Cons: no construye literalmente la UI "marcador primero, slots después" que pidió el usuario — es una interpretación de la intención (que el operador cargue rápido y ordenado) en vez de la letra del pedido.
  Reuses: `ModalResultadoDirecto.tsx` completo, patrón de ordenamiento ya usado en `hito_partido.py` repository.

**APPROACH B: Construir la UI de slots por marcador tal como se pidió**
  Summary: agregar un paso previo "marcador final" (2 inputs numéricos), generar N íconos por lado, y mapear cada ícono a un formulario de jugador+minuto. Requiere diseñar el flujo de "corregir el marcador después de cargar algunos goles" (agregar/quitar slots preservando los ya completados) — diagrama de estados obligatorio.
  Effort: M (nuevo componente, estado de slots vs. estado de eventos, lógica de reconciliación al editar el marcador, tests de esa reconciliación).
  Risk: Medio — la reconciliación de slots es una superficie nueva de bugs (qué pasa si bajo el marcador de 2 a 1 con los 2 slots ya llenos: ¿cuál se borra?).
  Pros: coincide literalmente con la UX pedida; puede sentirse más rápido para cargar un resultado ya conocido de memoria (se sabe el marcador final de entrada).
  Cons: introduce un problema de UX no trivial (reconciliación) que no existe hoy; el research ya muestra que el dolor funcional (pedir jugador+minuto) YA está resuelto — este approach resuelve una preferencia de flujo, no un gap de datos.
  Reuses: parcialmente `ModalResultadoDirecto.tsx` (el sub-formulario de jugador+minuto se puede reusar por slot).

**RECOMENDACIÓN: Approach A** — P1 aplica distinto aquí: la "completitud" del dato (jugador+minuto por gol) ya está en el 10/10 actual; lo que falta es orden cronológico, que A resuelve directo. B agrega una superficie de UX nueva sin resolver un gap adicional de datos. Completeness (dato): A=10/10 ya cubierto, gap real=orden; B=10/10 también pero con riesgo de reconciliación nuevo. **Marcado como TASTE DECISION / posible Desafío al Usuario** — el usuario pidió explícitamente la UI de slots, y ningún modelo (solo uno disponible) se opone tajantemente a construirla, solo señala el costo de reconciliación no diseñado. Se surface en el Gate Final.

### Alternativa para Área 3 (campo de regla de sustitución)

**APPROACH A: Campo en `TORNEO` (recomendado)** — `Torneo.permite_cambios_ilimitados: bool | None` (`NULL` = usar default por modalidad: fútbol → `False` con retorno prohibido salvo lesión de portero si aplica; básquet → `True`). Mismo patrón exacto que `minimo_jugadores_para_iniciar` y `permite_walkover_grupos`: reglamento del torneo, no del catálogo. Effort: S. Risk: Bajo. Pros: separa correctamente "modalidad" (qué se juega) de "nivel/reglamento" (cómo se juega esta edición); reutiliza un patrón ya probado 2 veces en este mismo archivo. Cons: reabre la pregunta de cuál es el default correcto cuando `NULL` (requiere una decisión explícita, no asumida).

**APPROACH B: Campo en `MODALIDAD`** — asumir que la regla depende 100% del formato (Fútbol 7 siempre ilimitado, Fútbol 11 siempre limitado). Effort: XS. Risk: Medio — no permite que un torneo amateur de Fútbol 11 elija reglas rotativas, ni que un torneo "profesional" de Fútbol 7 elija no-retorno; fuerza una correlación que el propio ejemplo del usuario ya contradice parcialmente (menciona "fútbol 7 amateur" como si el amateurismo, no el formato, fuera la variable real).

**RECOMENDACIÓN: Approach A** — P5 (explícito) + el precedente ya establecido dos veces en `torneo.py`. Completeness: A=9/10 (separa los ejes correctamente), B=5/10 (conflación ya señalada por el subagente). Esta es una decisión de arquitectura de datos de una sola vía (agregar columna, elegir dueño) — se registra como decisión, no se pregunta al usuario en el gate (P2: en blast radius, <1 día CC, incorporación mecánica del patrón ya usado).

## 0D. Mode-Specific Analysis (SELECTIVE EXPANSION)

**Complexity check**: el plan ensamblado toca ~10-12 archivos (backend: `torneo.py`, `modalidad.py` NO tocado tras 0C-bis, `hito_partido.py`, `evento_partido.py`, `partido.py`, `convocado_a_partido.py`/service, `errors.py`, 2-3 migraciones nuevas idempotentes; frontend: `alineacion.ts`, `AlineacionEditor.tsx`, `Cronometro.tsx`, `MesaPanel.tsx`, `eventos.ts`, nuevo modal de sustitución). Está por encima del umbral de "más de 8 archivos = smell" del propio skill — pero cada Área es independiente y aditiva (no hay una sola clase/servicio nuevo que concentre la complejidad); se trata como 4 sub-entregas independientes, no como una sola pieza monolítica. No se reduce el alcance (P2: todo está en blast radius de "gestión de partido en vivo").

**Mínimo conjunto de cambios**: Área 1 (tope) y Área 2 (orden cronológico) son cambios aislados de S effort. Área 4 (máquina de estados + override) depende de sí misma para ser segura — no se puede separar el fix del override sin dejar el override inseguro. Área 3 es la más grande (campo nuevo + UI de modal + reconciliar heurística existente).

**Escaneo de expansión (candidatos, NO agregados a alcance todavía):**
1. **10x check**: un motor de reglas de partido parametrizable por torneo (mínimo, máximo, cambios, tiempo extra) como un solo objeto `ReglamentoTorneo` en vez de columnas sueltas en `TORNEO`. Effort: L. Sería una refactorización estructural, no una extensión de esta feature — excede el blast radius de este plan (>1 día CC, introduce un nuevo concepto de dominio).
2. **Delight opportunities** (≥5): (a) badge visual "🟨 tarjeta pendiente de sanción" en la próxima convocatoria si el jugador está suspendido; (b) atajo de teclado para cargar gol al jugador más reciente que anotó (recurrencia típica); (c) undo de 5 segundos tras cerrar un partido por error; (d) contador visible "cambios usados X/Y" en el panel en vivo cuando el torneo limita cantidad; (e) exportar el resultado directo cargado como texto plano para pegar en un grupo de WhatsApp del torneo.
3. **Platform potential**: el campo `Torneo.permite_cambios_ilimitados` (Área 3) y el futuro tope de sustituciones por partido podrían generalizarse a un objeto de reglamento reusable por otros deportes que se agreguen después (vóley, handball) — pero eso es el ítem 1 de arriba, ya diferido.

**Auto-decisión de expansiones (principios, sin preguntar — SELECTIVE EXPANSION delega en autoplan):**
- (a) badge de sanción pendiente → **DEFERIR a TODOS.md** (P2: fuera del blast radius directo — depende de un concepto de "sanciones" que no existe en el modelo hoy).
- (b) atajo de teclado → **CORTAR** (P5/P3: mejora marginal, no pedida, agrega superficie de UI sin beneficio claro medido).
- (c) undo de 5 segundos tras cerrar partido → **INCORPORAR A ALCANCE** de Área 4 (P1: el propio pedido exige "confirmación de seguridad" antes de cerrar — un undo corto es la forma más barata y completa de dar esa seguridad sin bloquear el flujo con un modal extra; <1 día CC, mismo archivo que ya se toca).
- (d) contador "cambios usados X/Y" → **INCORPORAR A ALCANCE** de Área 3 (P1/P2: si se agrega el campo de tope, mostrar el contador es la mitad barata y obvia del valor — sin esto la regla es invisible para el operador hasta que falla).
- (e) exportar a texto plano → **DEFERIR a TODOS.md** (P2: fuera de blast radius, es una feature de comunicación externa, no de gestión de partido).
- Motor de reglamento genérico (ítem 1) → **DEFERIR a TODOS.md** (ya justificado arriba).

## 0D-POST. CEO Plan persistido

Escrito en `~/.gstack/projects/Score-App/ceo-plans/2026-09-08-modo-vivo-sustituciones-cierre.md` (ver Fase 1 completa arriba como fuente; el archivo persistido resume Vision + Scope Decisions + Accepted/Deferred, formato estándar del skill).

## 0E. Temporal Interrogation

```
  HORA 1 (fundaciones):     Migraciones idempotentes (tope no hace falta columna nueva —
                            reusa tamano_equipo; Área 3 sí necesita 1 columna en TORNEO;
                            Área 4 no necesita columna, solo lógica de validación).
                            Decidir el mensaje de error exacto para el rechazo de tope
                            (¿bloquea el movimiento silenciosamente o muestra un toast?).
  HORA 2-3 (lógica core):   Ambigüedad esperada: ¿el tope cuenta contra `tamano_equipo`
                            o contra un nuevo `max_titulares` independiente? (Resuelto en
                            0C-bis: reusar tamano_equipo, no crear columna). ¿El override de
                            Fin de Partido registra un Hito nuevo o reutiliza `Fin_Partido`
                            con un flag `forzado=true`? (Debe ser el mismo Hito con flag —
                            NO un tipo nuevo, para no duplicar la lógica de `_calcular_estado`
                            que ya trata `Fin_Partido` como terminal).
  HORA 4-5 (integración):   Sorpresa esperada: el modal de sustitución "¿por quién ingresa?"
                            necesita la MISMA lista de "elegibles para entrar" que hoy calcula
                            heurísticamente `MesaPanel.tsx:572-591` — hay que decidir si ese
                            cálculo se mueve al backend (fuente única) antes de construir el
                            modal, o si el modal sigue confiando en el cliente (rechazado,
                            ver Q5 arriba: crea 2 fuentes de verdad).
  HORA 6+ (pulido/tests):   Se van a necesitar tests de concurrencia: dos clicks simultáneos
                            en "Fin de Partido forzado" (doble-submit), y un test de que el
                            override NO se puede deshacer pasado el undo de 5s.
```

## 0F. Mode Confirmation

**SELECTIVE EXPANSION**, fijado por `/autoplan`. Alcance base = las 4 Áreas del pedido + el Bloque 0 (fix de `PartidoService.update`) que el CEO subagent identificó como prerequisito real de Área 4. Expansiones aceptadas: undo de 5s (Área 4), contador de cambios (Área 3). Diferidas: badge de sanción, atajo de teclado, exportar a WhatsApp, motor de reglamento genérico.

**Verificación de la propuesta de Bloque 0 contra el código real** (regla "afirmaciones necesitan evidencia"): confirmado en `database/06_triggers.sql` que `fn_hito_sincroniza_estado_partido` (líneas 624-636) YA sincroniza `PARTIDOS.Estado` automáticamente a partir de los Hitos (`Inicio_Partido`→`'En curso'`, `Fin_Partido`→`'Finalizado'`), y que `fn_propagar_ganador_bracket` (líneas 490-547) se dispara SINCRÓNICAMENTE cuando `Estado` pasa a `'Finalizado'` en un partido de bracket, propagando el ganador a la siguiente ronda **en la misma transacción**. Esto confirma dos cosas:
1. El hueco de `PartidoService.update` (`partido.py:69-76`) es que el PATCH puede escribir `PARTIDOS.Estado` **directamente**, sin pasar por ningún Hito — un camino paralelo que los triggers no cubren (los triggers reaccionan a INSERT en HITOS, no a UPDATE directo de `PARTIDOS.Estado`).
2. El fix más limpio, consistente con la arquitectura ya establecida en este branch (Bloque 0 del plan anterior ancló los gates de negocio al Hito, no a `PARTIDOS.estado`): **remover `estado` como campo escribible de `PartidoUpdateSchema`** — `PARTIDOS.Estado` pasa a ser 100% derivado de Hitos, nunca un valor que un PATCH pueda fijar directamente. El override de Fin de Partido forzado (Área 4) inserta un Hito `Fin_Partido` (con `forzado=true`), nunca un PATCH de estado — así reutiliza el mismo trigger ya probado en vez de crear un segundo camino de escritura.
3. Esto también confirma el riesgo de "undo" señalado por la revisión del CEO plan doc: una vez que el Hito `Fin_Partido` se inserta, la propagación de bracket ya ocurrió en la misma transacción — por eso el undo de 5s debe ser **de commit diferido en el cliente** (no se envía el POST hasta que expira la ventana), no una transacción compensatoria server-side.

## Secciones 1-11 (revisión completa, SELECTIVE EXPANSION)

### Sección 1 — Arquitectura
Diagrama de dependencias (componentes nuevos en `+`, existentes sin cambio en texto plano):

```
  AlineacionEditor.tsx ──(PUT/POST convocados)──▶ ConvocadoAPartidoService
        │                                               │
        │ +moverA rechaza exceso                        + guard tamano_equipo
        ▼                                               ▼
  alineacion.ts (pura)                          hito_partido._validar_titulares (min+max)

  MesaPanel.tsx ──(POST /partidos/{id}/eventos)──▶ EventoPartidoService.create
        │  +CargaEvento ya no pide minuto            │
        │  cuando enCurso=true                        + minuto tomado del backend
        ▼                                              (Cronometro expone getMinutoActual())
  Cronometro.tsx ──+onMinutoActual(cb)──▶ (nuevo canal de estado hermano→hermano,
        │                                   vía prop callback, sin duplicar cálculo)
        │
        + ModalSustitucion.tsx (nuevo) ──(POST evento tipo=Cambio)──▶ EventoPartidoService.create
                                                │
                                                + guard tope de cambios (Torneo) +
                                                  guard no-retorno (si aplica)

  GestionarPartido.tsx ──(POST /partidos/{id}/hitos, forzado=true)──▶ HitoPartidoService.registrar
        │  +botón "Fin de Partido forzado" global                │
        │  +modal confirmar + undo 5s (commit diferido cliente)  + Fin_Partido acepta desde
        ▼                                                          cualquier acciones_permitidas
  PartidoService.update ──X estado ya no aceptado en PATCH──▶ (solo Hitos mutan estado)

  ModalResultadoDirecto.tsx (sin cambios de UI) ──▶ PartidoService.registrar_resultado_directo
        (sin cambios)                                  │
                                                         + EventoPartidoRepository.listar
                                                           ahora ORDER BY minuto, id
```

**Data flow (Área 3, evento en vivo — las 4 rutas):**
```
  INPUT (click "Cargar evento")──▶ VALIDACIÓN (partido en curso?)──▶ TRANSFORM (minuto=Cronometro.getMinutoActual())──▶ PERSIST (POST evento)──▶ OUTPUT (timeline actualizada)
     │                                    │                                  │                                            │                          │
     ▼                                    ▼                                  ▼                                            ▼                          ▼
  [nil: Cronometro aún no montado?]  [partido pausado?]              [cronómetro en pausa: minuto              [POST falla: red offline]        [timeline no refresca:
   → deshabilitar botón hasta que    → permitir igual (evento          congelado, se usa el último              → ya cubierto por la cola          refetch tras 200,
   Cronometro emita el primer tick   registrado en pausa es           valor conocido, no bloquear]              offline-first existente en         invalidar query]
                                      legítimo: p.ej. tarjeta a                                                  MesaPanel.test.tsx]
                                      quien discute en el entretiempo]
```

**Máquina de estados de Hitos (Área 4, override) — transición nueva marcada con `**`:**
```
  [sin Inicio_Partido] --Inicio_Partido--> [iniciado, sin Fin_Partido]
                                                  │
                        Pausa/Reanudacion/Inicio_Periodo/Fin_Periodo (como hoy)
                                                  │
                                                  ├──Fin_Partido (gate normal: todo período cerrado, o Corrido)──▶ [Finalizado]
                                                  │
                                                  └──**Fin_Partido(forzado=true) — permitido desde CUALQUIER
                                                        acciones_permitidas mientras iniciado y no finalizado**──▶ [Finalizado, motivo_cierre="forzado"]

  [Finalizado] --X ningún PATCH de estado ni Hito nuevo--> (terminal, inmutable)
```
El único estado "imposible" nuevo a prevenir: doble `Fin_Partido` (normal + forzado, o forzado dos veces) — ya cubierto por el guard existente `partido_finalizado` en `_calcular_estado` (rechaza cualquier Hito si ya hay `Fin_Partido`).

**Coupling**: `Cronometro.tsx` pasa de aislado a exponer estado hacia `MesaPanel.tsx` (nuevo prop `onMinutoActual`). Justificado — es la única forma de cumplir el requisito sin duplicar el cálculo de `elapsedMs`. `ModalSustitucion.tsx` se acopla a `AlineacionEditor`/`GestionarPartido` (necesita la lista de convocados vigentes) — se resuelve pasándole los mismos datos que ya carga `GestionarPartido`, sin query propia.

**Escalamiento**: sin cambios de forma — mismo volumen de escritura (1 evento = 1 POST), el `COUNT` del contador de cambios es sobre filas ya indexadas por `partido_id` (`EventoPartido` ya tiene ese índice por el patrón existente de listado de eventos).

**Punto único de falla**: ninguno nuevo — todo pasa por los mismos servicios (`HitoPartidoService`, `EventoPartidoService`) que ya son el único camino de escritura para partido/eventos.

**Seguridad**: el override de Fin de Partido forzado debe verificar el mismo scoping que ya usa `HitoPartidoService.registrar` (árbitro asignado al partido, o rol TorneoAdmin/Mesa — mismo guard que el resto de Hitos). Nadie nuevo gana acceso.

**Escenario de fallo en producción**: el modal de sustitución falla si `Cronometro` no emitió aún el primer tick (`onMinutoActual` es `null`) — debe deshabilitar el submit, no enviar `minuto=null` o `minuto=0` silenciosamente (ver Sección 2).

**Rollback**: cada pieza es una migración aditiva + código adicional — revert de código estándar; el guard de tope de titulares y el de cambios se pueden desactivar con un flag de config si aparecen falsos positivos en producción (torneo real con datos inconsistentes) sin necesitar rollback de esquema.

### Sección 2 — Mapa de Errores y Rescates

```
  MÉTODO/CODEPATH                              | QUÉ PUEDE SALIR MAL                          | CLASE DE EXCEPCIÓN
  ----------------------------------------------|-----------------------------------------------|--------------------
  ConvocadoAPartidoService.marcar_titular        | Ya hay tamano_equipo titulares                 | DomainRuleError (nuevo mensaje)
  EventoPartidoService.create (evento en vivo)   | Cronometro sin tick aún (minuto=None)          | ValidationError (Pydantic, 422)
  EventoPartidoService.create (tipo=Cambio)      | Tope de cambios alcanzado                      | DomainRuleError
  EventoPartidoService.create (tipo=Cambio)      | Jugador que sale ya salió (no-retorno)         | DomainRuleError
  HitoPartidoService.registrar (Fin_Partido      | Partido ya Finalizado                          | DomainRuleError (ya existe)
    forzado=true)                                |                                                |
  PartidoService.update                          | Alguien manda `estado` en el payload           | ValidationError (422, campo removido del schema, no 400 de dominio)
  EventoPartidoRepository.listar (orden nuevo)   | Empate exacto de minuto entre 2 eventos        | (no es error — desempate por id, determinístico)

  CLASE DE EXCEPCIÓN         | RESCATADA? | ACCIÓN DE RESCATE                          | QUÉ VE EL USUARIO
  ---------------------------|------------|---------------------------------------------|---------------------------------
  DomainRuleError (tope)     | Sí (ya existe el patrón) | 400 con detail                | "Ya hay {tamano_equipo} titulares para este equipo"
  ValidationError (minuto)   | N ← GAP    | —                                             | 422 genérico ← MALO, debe mapearse a mensaje "Cronómetro aún no iniciado, esperá el primer tick"
  DomainRuleError (tope cambios) | Sí (nuevo, mismo patrón) | 400 con detail          | "Tope de cambios alcanzado para este equipo (X/X)"
  DomainRuleError (no-retorno)   | Sí (nuevo, mismo patrón) | 400 con detail          | "{jugador} ya no puede reingresar en este formato"
  DomainRuleError (doble Fin_Partido) | Sí (ya existe)     | 400 con detail          | "El partido ya está finalizado"
```
**GAP real encontrado**: el 422 genérico de Pydantic para "minuto faltante" no da un mensaje accionable — se decide (P5) mapear ese caso específico a un mensaje de dominio antes de llegar a Pydantic (validar `Cronometro` montado en el frontend, deshabilitando el submit, como primera línea de defensa; y en el backend, aceptar `minuto: int | None` y devolver `DomainRuleError` explícito si es `None` y el partido está en curso, en vez de dejar que el 422 gonérico lo tape).

### Sección 3 — Seguridad y Modelo de Amenazas
- **Superficie nueva**: 1 endpoint modificado (`PATCH /partidos/{id}` pierde el campo `estado`, reduce superficie), 0 endpoints nuevos (el override reusa `POST /partidos/{id}/hitos` con un campo `forzado: bool` opcional), 1 campo nuevo en `TORNEO` (tope de cambios), posible campo nuevo `motivo_cierre` en el Hito de Fin_Partido.
- **Validación de input**: `forzado: bool` — default `False`, rechazar valores no-booleanos vía Pydantic (ya automático). `minuto` en eventos en vivo — dejar de aceptarlo del cliente cuando el partido está en curso (se ignora si lo manda, se usa el del servidor) para cerrar la posibilidad de que un cliente falsifique el minuto de un evento en vivo — **hallazgo nuevo de seguridad de datos**, no solo de UX: hoy el minuto es 100% confiable en el cliente.
- **Autorización**: el override de Fin de Partido forzado usa el mismo guard de rol que ya protege `POST /partidos/{id}/hitos` (árbitro asignado o Mesa/TorneoAdmin) — ningún actor nuevo gana la capacidad de cerrar partidos.
- **Secretos**: ninguno nuevo.
- **Dependencias**: ninguna nueva (todo con lo ya instalado).
- **Auditoría**: el Hito de Fin_Partido forzado debe llevar `motivo_cierre` (texto libre corto, ej. "clima", "abandono") capturado en el modal de confirmación — sin esto, un cierre forzado es indistinguible de uno normal en el historial, lo cual es un GAP de auditoría real dado que el pedido explícitamente habla de "factores externos".

### Sección 4 — Flujo de Datos y Casos Límite de Interacción

```
  INTERACCIÓN                          | CASO LÍMITE                          | CUBIERTO? | CÓMO
  --------------------------------------|---------------------------------------|-----------|------
  Mover jugador a Titulares (tope)       | Doble-click rápido (2 movimientos     | Sí, tras este plan | guard server-side idempotente,
                                          | antes de que el guard responda)       |           | rechaza el segundo si ya se pasó
  Cargar evento en vivo                  | Cronómetro en pausa                   | Sí (diseñado arriba) | usa el último minuto conocido
  Cargar evento en vivo                  | Doble-submit del mismo gol             | Parcial ← GAP | ya existe idempotencia para POST
                                          |                                        |           | aditivo de convocados; NO confirmado
                                          |                                        |           | que `EventoPartidoService.create` sea
                                          |                                        |           | idempotente — requiere test explícito
  Modal de sustitución                   | Cerrar el modal sin elegir reemplazo   | Debe diseñarse | no debe registrar ningún evento;
                                          |                                        |           | el titular "sale" solo se persiste si
                                          |                                        |           | se confirma con un "entra" válido
  Fin de Partido forzado                 | Doble-click en el botón                | Debe diseñarse | el modal de confirmación + el undo de
                                          |                                        |           | 5s ya actúan como debounce natural,
                                          |                                        |           | pero el POST en sí debe ser idempotente
                                          |                                        |           | (rechazar si ya hay Fin_Partido, no
                                          |                                        |           | crear un segundo Hito)
  Fin de Partido forzado                 | Usuario navega fuera durante los 5s    | Debe diseñarse | el commit diferido debe sobrevivir un
   (undo de commit diferido)              | de la ventana de undo                 |           | cambio de pantalla (setTimeout a nivel
                                          |                                        |           | de query client, no de componente
                                          |                                        |           | montado) — si no, un F5 accidental
                                          |                                        |           | cancela silenciosamente el cierre
                                          |                                        |           | (comportamiento razonable pero debe
                                          |                                        |           | ser EXPLÍCITO, no un accidente de
                                          |                                        |           | implementación)
```
**GAP marcado arriba (doble-submit de evento en vivo)** se resuelve en Fase 3 (Eng): agregar test explícito de POST duplicado para `EventoPartidoService.create`, mismo patrón que ya existe para convocados (`test_convocatoria_en_vivo.py`, idempotencia del POST).

### Sección 5 — Calidad de Código
- **Organización**: todo el código nuevo sigue el patrón `pages/control-mesa/` + `components/` ya establecido por el plan anterior — no se crea una estructura nueva.
- **DRY**: riesgo real señalado en 0A/subagent — el cálculo heurístico de "quién puede entrar/salir" en `MesaPanel.tsx:572-591` debe **eliminarse y reemplazarse**, no duplicarse, por la validación autoritativa de backend (tope de cambios + no-retorno). Si el modal de sustitución nuevo agrega su propio cálculo de elegibilidad en paralelo al de `MesaPanel.tsx`, es una violación DRY inmediata — deben compartir una sola fuente (idealmente el backend, vía un endpoint que devuelva "elegibles para entrar" ya filtrados).
- **Nombres**: `forzado` (booleano en el Hito) es más claro que alternativas como `override` (anglicismo) o `manual` (ambiguo con "hito manual" que ya podría significar otra cosa) — se mantiene consistente con el resto del código en español.
- **Sobre-ingeniería**: el motor de reglamento genérico (diferido en 0D) sería sobre-ingeniería para este alcance — correctamente cortado.
- **Sub-ingeniería a vigilar**: el contador de "cambios usados" NO debe implementarse como un `useState` local que se resetea al refrescar la página — debe leer siempre del backend (mismo patrón que `preflight-inicio`), o el contador miente tras un F5.
- **Complejidad ciclomática**: `_calcular_estado` en `hito_partido.py` ya es la función más compleja del área (múltiples ramas por modo Periodos/Corrido) — agregar `forzado=true` como un branch más la empuja un poco más; vale la pena, al tocarla, extraer la rama de "Fin_Partido permitido" a una función nombrada (`_fin_partido_permitido(estado, forzado)`) en vez de un `if` más anidado.

### Sección 6 — Revisión de Tests

```
  NUEVOS FLUJOS UX:
    - Mover jugador a Titulares cuando ya se llegó al tope → bloqueado con mensaje
    - Cargar evento en vivo sin tipear minuto (autocompletado)
    - Sacar un titular desde la alineación en vivo → modal "¿Por quién ingresa?"
    - Botón "Fin de Partido forzado" visible y habilitado en cualquier estado del partido
    - Confirmar cierre forzado → ventana de undo de 5s → cierre efectivo
    - Cancelar el cierre forzado dentro de los 5s → partido sigue como estaba

  NUEVOS FLUJOS DE DATOS:
    - moverA (cliente) rechaza exceso ANTES del POST
    - POST convocados/titular (backend) rechaza exceso aunque el cliente falle
    - GET cronómetro → minuto propagado a CargaEvento vía prop, sin round-trip nuevo
    - POST evento tipo=Cambio → valida tope + no-retorno vía Torneo.permite_cambios_ilimitados
    - POST hitos {tipo: Fin_Partido, forzado: true} → Fin_Partido permitido sin gate de período

  NUEVOS CODEPATHS:
    - _validar_titulares ahora valida MÁXIMO además de mínimo
    - _calcular_estado agrega la rama "Fin_Partido siempre permitido si forzado=true e iniciado y no finalizado"
    - EventoPartidoRepository.listar agrega ORDER BY minuto, id
    - PartidoUpdateSchema ya no acepta `estado`

  NUEVOS ERROR/RESCUE PATHS: ver Sección 2 completa arriba.

  NUEVAS INTEGRACIONES: ninguna externa — todo interno al mismo backend/frontend.
```
Para cada ítem: tipo de test, existe o no, happy/failure/edge:
- Tope de titulares: **Unit** (`alineacion.test.ts`: `mover` rechaza exceso) + **Integration** (`test_titulares_inicio_partido.py` o nuevo `test_tope_titulares.py`: POST que intenta marcar titular #N+1 → 400). Edge: torneo con `tamano_equipo=null` (no debería existir, pero probar que no crashea).
- Minuto automático: **Integration** (nuevo test backend: evento en vivo sin `minuto` en el payload usa el del servidor) + **Component** (`MesaPanel.test.tsx`: `CargaEvento` no muestra el input de minuto cuando `enCurso`).
- Modal de sustitución: **Component** (nuevo `ModalSustitucion.test.tsx`: abre al tocar un titular, cierra sin persistir si se cancela, persiste evento `Cambio` al confirmar) + **Integration** (backend: no-retorno rechaza reingreso, tope de cambios rechaza el N+1).
- Fin de Partido forzado: **Integration** (nuevo `test_fin_forzado.py`: Hito `Fin_Partido forzado=true` aceptado desde CUALQUIER `acciones_permitidas` mientras iniciado y no finalizado; rechazado si ya finalizado — doble-submit) + **Component** (confirm modal + undo timer, incluyendo el caso "navegar fuera durante los 5s").
- Orden cronológico: **Integration** (nuevo test: insertar evento min 40 y luego min 2, verificar que el GET los devuelve ordenados 2 antes que 40).
- **Test ambición 2am-viernes**: el que rompería en producción sin este plan es un torneo de Fútbol 7 con 8 titulares cargados y nadie lo nota hasta la revisión de estadísticas post-partido — ESE es el test que justifica todo el Bloque de Área 1.
- **Test hostil de QA**: doble-click en "Fin de Partido forzado" durante la ventana de undo, en dos pestañas del navegador simultáneas — verificar que no se crean 2 Hitos `Fin_Partido`.
- Pirámide: mayoría unit (validaciones puras) + integration (guards de servicio) + un puñado de component tests (modal de sustitución, timer de undo) — sin E2E nuevos, consistente con el resto del repo.
- Flakiness: el timer de undo de 5s en tests debe mockear el tiempo (`vi.useFakeTimers()` o equivalente), nunca esperar 5s reales.

### Sección 7 — Rendimiento
- Sin N+1 nuevos: el `COUNT` de cambios usados es una query indexada por `partido_id`+`equipo_id` (mismo índice que ya usa el listado de eventos).
- Sin estructuras de memoria nuevas de tamaño no acotado — todo por partido individual.
- El único índice a verificar: si `EventoPartidoRepository.listar` pasa de ordenar en cliente a `ORDER BY minuto, id` en el backend, confirmar que existe índice sobre `(partido_id, minuto)` o que el volumen por partido (decenas de eventos) hace irrelevante el índice — a este volumen, no hace falta índice nuevo.
- Cronómetro emitiendo `onMinutoActual` en cada tick (probablemente 1/segundo) hacia `MesaPanel` — verificar que no dispara un re-render costoso de toda la timeline; debe ser un valor leído on-demand al abrir `CargaEvento`, no un state que re-renderiza cada segundo (P5: explícito, evitar el patrón ingenuo).

### Sección 8 — Observabilidad
- Log estructurado al insertar un Hito `Fin_Partido forzado=true` (quién, cuándo, `motivo_cierre`, desde qué `acciones_permitidas` estaba el partido) — esto es el único mecanismo de auditoría de un cierre fuera de lo normal, debe quedar en logs Y en el propio Hito.
- Métrica sugerida (día 1): conteo de cierres forzados por semana — un número alto e inesperado indica que el flujo normal de cierre tiene fricción real que empuja a la gente al override.
- Debuggabilidad: si en 3 semanas se reporta "el partido X se cerró solo", el log del Hito forzado + su `motivo_cierre` debe ser suficiente para reconstruirlo sin acceso a la base en vivo.

### Sección 9 — Despliegue y Rollout
- Migraciones: 2 nuevas idempotentes (`IF NOT EXISTS`) — `Torneo.permite_cambios_ilimitados` y (si se decide) `HitoPartido.motivo_cierre`/`forzado`. Mismo patrón que `27_migracion_minimo_titulares.sql`: agregar a `01_schema.sql`, `02_constraints.sql` si aplica, y a `SCRIPTS_VIGENTES` de `test_scripts_sql.py` (pitfall ya conocido en este repo: `score-app-conftest-solo-corre-01-06`).
- Orden de despliegue: migrar primero (columnas nuevas con default `NULL`/`False`, no rompen filas existentes), backend segundo (empieza a validar), frontend tercero (empieza a mostrar los nuevos controles) — mismo orden que el plan anterior ya siguió.
- Ventana de riesgo: ninguna — todos los cambios son aditivos o restringen (nunca amplían) lo que ya se aceptaba, salvo el retiro de `estado` de `PartidoUpdateSchema`, que es un cambio de contrato de API. Verificar que ningún consumidor del frontend actual manda `estado` en un PATCH hoy (grep rápido antes de implementar, en Fase 3).
- Verificación post-deploy: cargar un partido de prueba en Fútbol 7, intentar un 8vo titular (debe rechazar), forzar un cierre en pleno primer tiempo (debe pedir confirmación + permitir undo).

### Sección 10 — Trayectoria a Largo Plazo
- Deuda introducida: mínima — se sigue el patrón ya establecido (columna en TORNEO) en vez de crear abstracciones nuevas.
- Reversibilidad: 4/5 — todo son guards adicionales y una columna con default seguro; el único cambio de una vía es retirar `estado` de `PartidoUpdateSchema` (un cliente externo que dependiera de setearlo directamente se rompe, pero no hay clientes externos, es un sistema interno).
- Pregunta a 1 año: un ingeniero nuevo leyendo `_calcular_estado` con la rama `forzado` extraída a `_fin_partido_permitido` debería entenderla sin contexto adicional — se decide extraerla (Sección 5) justamente por esto.
- Encaja con la trayectoria ya iniciada (Hito como única fuente de verdad de estado) — refuerza esa dirección en vez de contradecirla.

### Sección 11 — Diseño y UX (alcance UI confirmado en Fase 0)
- **Jerarquía de información**: en `AlineacionEditor`, el contador "11/11 titulares" ya existe (visible) — agregar el bloqueo no cambia la jerarquía, solo el comportamiento al exceder. En el panel en vivo, el botón "Fin de Partido forzado" debe estar visualmente separado (no como una opción más de una lista) del flujo normal de cierre, para no confundirlo con un cierre de rutina — un patrón de "acción destructiva" (color/posición distintos), consistente con cómo el resto del sistema trata acciones irreversibles.
- **Cobertura de estados de interacción**:
```
  FEATURE                  | LOADING            | EMPTY                | ERROR                        | SUCCESS              | PARCIAL
  --------------------------|--------------------|-----------------------|-------------------------------|-----------------------|-------------------
  Modal sustitución          | lista de elegibles | 0 suplentes elegibles| POST falla (red)              | evento Cambio creado  | titular elegido, sin
                              | cargando            | (todos ya sancionados/| → reintentar, no cerrar modal  | y modal cierra        | reemplazo elegido aún
                              |                     | ya entraron)          |                                |                       | → bloquear confirmar
  Fin de Partido forzado     | —                  | —                     | POST falla tras confirmar     | Hito creado, partido  | usuario cerró la
                              |                     |                       | (red) → mostrar error,        | Finalizado            | pestaña durante los 5s
                              |                     |                       | mantener el estado de "aún    |                       | de undo (ver Sección 4)
                              |                     |                       | no cerrado" visible           |                       |
  Contador cambios usados    | —                  | torneo sin tope       | —                             | X/Y visible           | —
                              |                     | configurado → no      |                                |                       |
                              |                     | mostrar el contador   |                                |                       |
```
- **Arco emocional**: el operador de mesa en un cierre forzado está probablemente en una situación estresante (clima, incidente) — el modal de confirmación debe ser rápido de completar (1 campo de motivo, no un formulario largo) y el undo de 5s da margen sin fricción para deshacer un toque accidental bajo estrés.
- **Riesgo de "AI slop"**: ninguno detectado — todos los componentes nuevos siguen patrones visuales ya establecidos en `control-mesa/`, no se inventa un lenguaje visual nuevo.
- **Responsive**: el modal de sustitución debe respetar la misma regla ya decidida para drag&drop (tap de primera clase en todo viewport) — es un modal con selects, no requiere drag, así que funciona igual en todos los tamaños sin decisión nueva.
- **Accesibilidad**: el botón "Fin de Partido forzado" necesita `aria-label` explícito distinto de los botones normales de fin de período/partido, para que un lector de pantalla no los confunda.

Diagrama de flujo de usuario requerido (sustitución en vivo):
```
  [Alineación en vivo, titular visible] --tap/click en el titular--▶ [Modal: "¿Por quién ingresa?"]
                                                                            │
                                                    ┌───────────────────────┼───────────────────────┐
                                                    ▼                       ▼                       ▼
                                          [elige suplente]          [cancela/cierra]        [no hay elegibles]
                                                    │                       │                       │
                                                    ▼                       ▼                       ▼
                                          [confirma] ──POST──▶       [sin cambios,           [mensaje: "no hay
                                          Hito Cambio creado          modal cierra]           suplentes disponibles"]
                                          │
                                          ▼
                                  [timeline actualizada,
                                   contador de cambios +1]
```

Recomendación (regla del propio skill): dado el alcance UI real de este plan, correr `/plan-design-review` a continuación para una auditoría visual más profunda del modal de sustitución y del botón de cierre forzado — se ejecuta como Fase 2 de este mismo `/autoplan`.

## "NO en alcance" (diferido con motivo)

- Badge de sanción pendiente en convocatoria — depende de un modelo de "sanciones" inexistente.
- Atajo de teclado para cargar gol al último goleador — mejora marginal no pedida.
- Exportar resultado directo a texto plano (WhatsApp) — comunicación externa, fuera de blast radius.
- Motor de reglamento de torneo genérico (`ReglamentoTorneo`) — refactor estructural, excede 1 día CC.
- Tope superior de titulares vía columna nueva (`max_titulares` independiente) — se descartó por 0C-bis Approach A: se reusa `Modalidad.tamano_equipo`, no hace falta columna nueva.
- Formación/posiciones en cancha, minutos jugados por jugador, copiar alineación del partido anterior — diferidos por planes anteriores, este plan no los reabre.
- "Slots por marcador" tal como se pidió literalmente en Área 2 — ver Desafío al Usuario D1 en el Gate Final; queda pendiente de decisión del usuario, no cortado unilateralmente.

## "Qué ya existe" (mapeo completo)

Ver tabla en 0B arriba. Resumen: convocatoria interactiva completa, mínimo para iniciar completo, formulario de resultado directo con jugador+minuto por evento completo, máquina de estados por Hito completa para el caso no-forzado, tipo de evento "Cambio" ya modelado en `EventoPartido` (solo falta la UI contextual + las reglas de tope/no-retorno).

## Delta de estado ideal

Ver diagrama 0C arriba (CURRENT → THIS PLAN → 12-MONTH IDEAL). Este plan no llega al ideal de 12 meses (motor de reglamento unificado, historial de sanciones) pero cierra las 3 brechas de integridad de datos más urgentes: tope de titulares, minuto confiable, y máquina de estados sin bypass — sin las cuales cualquier trabajo futuro sobre reportes/estadísticas hereda datos potencialmente incorrectos.

## Registro de Modos de Fallo

```
  CODEPATH                                  | MODO DE FALLO                        | RESCATADO? | TEST? | QUÉ VE EL USUARIO      | LOGUEADO?
  -------------------------------------------|----------------------------------------|------------|-------|-------------------------|----------
  ConvocadoAPartidoService.marcar_titular     | Exceso de titulares                    | Sí (nuevo) | Sí (nuevo) | mensaje de dominio  | Sí (excepción ya logueada por el handler genérico)
  EventoPartidoService.create (en vivo)       | minuto=None con partido en curso       | Sí (nuevo, ver Sección 2 GAP) | Sí (nuevo) | mensaje de dominio, no 422 genérico | Sí
  EventoPartidoService.create (Cambio)        | Tope de cambios excedido                | Sí (nuevo) | Sí (nuevo) | mensaje de dominio  | Sí
  EventoPartidoService.create (Cambio)        | No-retorno violado                      | Sí (nuevo) | Sí (nuevo) | mensaje de dominio  | Sí
  HitoPartidoService.registrar (forzado)      | Doble-submit (2 Fin_Partido)             | Sí (guard ya existe: partido_finalizado) | Sí (nuevo test explícito) | "el partido ya está finalizado" | Sí
  PartidoService.update                       | Cliente manda `estado` en el payload    | Sí (rechazado por schema, 422) | Sí (nuevo) | 422 con detail claro | Sí
  ModalSustitucion (frontend)                 | Cierra sin elegir reemplazo              | Debe diseñarse — CRITICAL si no: evento fantasma sin "entra" | Sí (nuevo) | modal cierra sin persistir | N/A (no llega a persistir)
  Undo de cierre forzado (frontend)           | Usuario navega fuera durante los 5s      | Debe diseñarse — ver Sección 4 | Sí (nuevo) | comportamiento explícito, no accidental | N/A
```
Ninguna fila queda con RESCATADO=N y USUARIO VE=Silencioso tras el diseño de arriba — las dos filas "Debe diseñarse" se resuelven en Fase 3 (Eng) antes de escribir código, no se dejan abiertas.

## Diagramas producidos
1. Arquitectura del sistema (Sección 1) ✅
2. Flujo de datos con rutas sombra (Sección 1, evento en vivo) ✅
3. Máquina de estados (Sección 1, Hitos con `forzado`) ✅
4. Flujo de usuario (Sección 11, sustitución) ✅
5. Flujo de despliegue: no aplica (sin cambios de infraestructura, solo migraciones + código, ya cubierto en Sección 9 en prosa)
6. Flowchart de rollback: no aplica (revert estándar de código + flags de config, ya cubierto en Sección 1)

## Auditoría de diagramas existentes
No se encontraron diagramas ASCII obsoletos en los archivos que este plan toca — `gestionar-partido-alineaciones-plan.md` no tiene diagramas embebidos en el código en sí (viven en el plan, no en comentarios de código).

## Implementation Tasks (CEO phase)
Ver artefacto en disco: `~/.gstack/projects/Score-App/tasks-ceo-review-20260908-191053.jsonl` (8 tareas, T1-T8, agregadas en el Gate Final junto con las de Design/Eng).

## Completion Summary — CEO Review

```
  +====================================================================+
  |            MEGA PLAN REVIEW — COMPLETION SUMMARY (CEO)             |
  +====================================================================+
  | Mode selected        | SELECTIVE EXPANSION                          |
  | System Audit         | 4 archivos de test nuevos, migracion 27      |
  |                       | sin trackear, plan anterior recien cerrado   |
  | Step 0               | Premisa P-max revertida explicitamente (no   |
  |                       | bug); Bloque 0 agregado como prerequisito    |
  | Section 1  (Arch)    | 3 diagramas producidos, 0 issues bloqueantes |
  | Section 2  (Errors)  | 7 codepaths mapeados, 1 GAP (422 minuto)     |
  | Section 3  (Security) | 3 hallazgos, 1 Medio (minuto falsificable)   |
  | Section 4  (Data/UX) | 6 casos limite, 2 marcados "debe disenarse"  |
  | Section 5  (Quality) | 3 hallazgos (DRY heuristica, nombres, cx)    |
  | Section 6  (Tests)   | Diagrama producido, 6 gaps de test nuevos    |
  | Section 7  (Perf)    | 1 hallazgo (re-render de Cronometro)         |
  | Section 8  (Observ)  | 2 gaps (log de cierre forzado, metrica)      |
  | Section 9  (Deploy)  | 1 riesgo (retiro de campo estado del schema) |
  | Section 10 (Future)  | Reversibilidad: 4/5, deuda: minima           |
  | Section 11 (Design)  | 5 hallazgos, recomienda /plan-design-review  |
  +--------------------------------------------------------------------+
  | NOT in scope         | escrito (7 items)                            |
  | What already exists  | escrito                                      |
  | Dream state delta    | escrito                                       |
  | Error/rescue registry| 7 metodos, 0 CRITICAL GAPS (todo disenado)   |
  | Failure modes        | 8 total, 0 CRITICAL GAPS tras diseno         |
  | TODOS.md updates     | 3 items (badge sancion, export WhatsApp,     |
  |                       | motor de reglamento) — se escriben en Fase 3 |
  | Scope proposals      | 6 propuestas, 3 aceptadas, 2 diferidas, 1    |
  |                       | cortada                                       |
  | CEO plan             | escrito + 1 ronda de revision adversarial    |
  | Outside voice        | [subagent-only] — Codex no disponible        |
  | Lake Score           | 8/8 tareas eligieron la opcion mas completa  |
  | Diagrams produced    | 4 (arquitectura, flujo de datos, maquina de  |
  |                       | estados, flujo de usuario)                   |
  | Stale diagrams found | 0                                             |
  | Unresolved decisions | 1 (Area 2: slots por marcador — Desafio al   |
  |                       | Usuario, ver Gate Final)                     |
  +====================================================================+
```

**PHASE 1 COMPLETE.** Codex: no disponible (0 concerns, [subagent-only]). Claude subagent: 8 hallazgos (2 críticos, 4 altos, 2 medios). Consensus: N/A (single voice) — todos los hallazgos críticos/altos se incorporaron igual. Pasando a Fase 2 (Design).

---

# FASE 2 — Design Review (alcance UI confirmado en Fase 0)

**DESIGN.md**: no existe en el repo. Se procede con principios universales + las convenciones ya establecidas en `control-mesa/` (mismo criterio que el plan anterior). **Mockups visuales**: `gstack-design`/`$D` no está instalado en esta máquina (`DESIGN_NOT_AVAILABLE`) — revisión basada en texto/wireframes ASCII, sin imágenes generadas.

**Clasificación**: App UI (mesa de control interna, no landing page) — aplican las reglas de App UI: jerarquía de superficie calma, lenguaje utilitario, chrome mínimo, cards solo si la card ES la interacción.

## Paso 0.5 — Voces Duales (Design)

`[subagent-only]` — Codex no disponible, mismo criterio que Fase 1.

**CLAUDE SUBAGENT (design — completitud independiente)** — leyó solo el plan, hallazgos:
1. **Crítico**: no existe wireframe espacial del panel en vivo (solo diagramas de dependencia/interacción, no de layout) — el propio plan asume jerarquía sin definirla.
2. **Alto**: dos contadores "cambios usados" (uno por equipo) no reconocidos como par visual.
3. **Alto**: orden interno del modal de sustitución sin especificar — debe liderar con la identidad del jugador que sale.
4. **Crítico**: rechazo de tope de titulares (el ítem MÁS importante del pedido original) no tiene ningún estado de UI diseñado — riesgo de leerse como "el botón no funciona".
5. **Crítico**: ventana de undo de 5s sin ningún diseño visual — es el momento más crítico de seguridad de toda la feature.
6. **Medio-alto**: falta estado de error para "no cargó la lista de elegibles" en el modal de sustitución.
7. **Medio**: `motivo_cierre` como texto libre es la elección equivocada bajo estrés — y además arruina la métrica de observabilidad (Sección 8) al fragmentar el mismo motivo en strings distintas.
8. **Crítico**: el mecanismo de undo **contradice su propio caso de uso** — en el escenario de clima/incidente que el pedido cita como ejemplo, la atención del operador se va de la pantalla justo después de confirmar (por diseño del escenario), así que un countdown pasivo que "sobrevive" a la navegación se dispara exactamente cuando nadie está mirando. No protege contra el caso que dice proteger.
9. Estado vacío del modal de sustitución ("no hay suplentes disponibles") es un callejón sin salida — debería ofrecer inline la acción de alta tardía (`onSumarTardio`) que ya existe, en vez de forzar cancelar/navegar/reintentar.
10. Falta estado de éxito explícito tras un cierre forzado (confirmación de que el bracket se actualizó).
11. Especificidad: el plan es muy específico en contratos de datos pero genérico en copy/layout visual — ningún texto literal de botón/modal está definido todavía.

```
DESIGN OUTSIDE VOICES — LITMUS SCORECARD:
═══════════════════════════════════════════════════════════════
  Check                                    Claude  Codex  Consensus
  ─────────────────────────────────────── ─────── ─────── ─────────
  1. Marca/producto inconfundible?         N/A (App UI interno, no aplica) N/A N/A
  2. Un ancla visual fuerte?                N/A (no aplica a App UI)       N/A N/A
  3. Escaneable solo con encabezados?       PARCIAL — falta wireframe      N/A N/A
  4. Cada sección tiene un solo trabajo?    SÍ (por diseño de Sección 1)   N/A N/A
  5. ¿Las cards son necesarias?             N/A (no hay cards nuevas)      N/A N/A
  6. ¿El movimiento mejora la jerarquía?    N/A (sin animación nueva)      N/A N/A
  7. ¿Premium sin sombras decorativas?      N/A (App UI, no aplica)        N/A N/A
─────────────────────────────────────── ─────── ─────── ─────────
  Rechazos duros disparados:                0 (ninguno de los 7 patrones de landing page aplica a un App UI interno)
═══════════════════════════════════════════════════════════════
```
Sin rechazos duros — el plan no tiene ninguno de los 7 patrones de marketing prohibidos (no aplica, es una herramienta interna). Los hallazgos reales están en completitud de estados y especificidad, no en estética de marca.

## Pass 1 — Arquitectura de Información: 4/10 → 9/10

**Por qué 4**: existían diagramas de dependencia y de flujo de interacción, pero ningún wireframe espacial — no se podía responder "qué ve el operador primero, segundo, tercero" en el panel en vivo.

**Wireframe agregado** (zona primaria/secundaria/terciaria, resuelve Finding 1+2 del subagent):
```
┌─────────────────────────────────────────────────────────────────────┐
│ ZONA PRIMARIA (siempre visible, arriba)                              │
│  ┌───────────────┐   Marcador: LOCAL 2 — 1 VISITANTE   ┌───────────┐│
│  │  Cronómetro    │                                     │Fin Partido││
│  │  23:41  ⏸ ▶    │   [Iniciar 2do Tiempo] [Pausa]      │ forzado ▲ ││ ← botón fijo,
│  └───────────────┘                                       └───────────┘│  aislado visualmente
├─────────────────────────────────────────────────────────────────────┤
│ ZONA SECUNDARIA (alineación en vivo, dos columnas espejadas)         │
│  EQUIPO LOCAL                    │  EQUIPO VISITANTE                 │
│  Cambios usados: 2/5             │  Cambios usados: 1/5              │ ← par visual,
│  ● 10 Pérez (titular, tap=sale)  │  ● 7 Gómez (titular, tap=sale)    │   mismo peso
│  ○ 4 Ruiz  (suplente)            │  ○ 9 Díaz  (suplente)             │
├─────────────────────────────────────────────────────────────────────┤
│ ZONA TERCIARIA (historial, scrolleable, menor urgencia)              │
│  min 40  ⚽ Pérez (Local)                                             │
│  min 23  🟨 Gómez (Visitante)                                        │
│  min 2   ⚽ Ruiz (Local)   ← reordenado cronológicamente automático   │
└─────────────────────────────────────────────────────────────────────┘
```
"Fin de Partido forzado" vive **fijo en la zona primaria, nunca detrás de un menú** — decisión explícita (resuelve la ambigüedad #2 del subagent: descubribilidad de emergencia > prolijidad visual).

## Pass 2 — Cobertura de Estados de Interacción: 3/10 → 9/10

Tabla ampliada (agrega las 2 filas que faltaban por completo — tope de titulares y undo — más el estado de error faltante en el modal):

```
FEATURE                | LOADING              | EMPTY                    | ERROR                          | SUCCESS                      | PARTIAL
------------------------|----------------------|--------------------------|--------------------------------|-------------------------------|------------------
Tope de titulares       | —                    | —                        | intento de exceso: la fila     | movimiento aceptado, contador  | —
(Área 1, GAP crítico    |                      |                          | rebota visualmente (snap-back) | "11/11" pasa a full            |
cerrado en esta pasada) |                      |                          | + toast con el mensaje exacto  |                                 |
                        |                      |                          | del backend — NUNCA un no-op   |                                 |
                        |                      |                          | silencioso                     |                                 |
Modal sustitución       | spinner al abrir,    | 0 elegibles → NO es un   | (a) GET de elegibles falla →   | evento Cambio creado, modal    | jugador que sale
                        | cargando elegibles   | callejón sin salida:     | reintentar inline, modal       | cierra, timeline + contador se | elegido, sin
                        |                      | ofrece "Agregar suplente| sigue abierto; (b) POST falla  | actualizan                     | reemplazo aún →
                        |                      | ahora" (reusa           | (red) → error inline, modal    |                                 | botón Confirmar
                        |                      | onSumarTardio) inline   | sigue abierto, reintentar      |                                 | deshabilitado
Fin de Partido forzado  | (ver fila "Undo"     | —                        | POST falla tras expirar los 5s | "Partido finalizado por cierre | usuario cerró la
                        | abajo — es su propio |                          | → error explícito, el partido  | forzado. {motivo}. Bracket     | pestaña durante
                        | estado, no un        |                          | NO queda en estado ambiguo     | actualizado." (mensaje de      | los 5s → ver
                        | "loading" genérico)  |                          | (retry visible)                 | éxito explícito, no un toast   | Undo abajo
                        |                      |                          |                                 | genérico)                      |
Undo de cierre forzado  | banner persistente,  | —                        | —                               | banner desaparece,             | banner debe
(commit diferido)       | alto contraste,      |                          |                                 | confirmación de éxito arriba   | sobrevivir
                        | countdown visible    |                          |                                 |                                 | cambio de pantalla
                        | ("Cerrando partido   |                          |                                 |                                 | DENTRO de la app
                        | en 5s… [DESHACER]"), |                          |                                 |                                 | (ver Pass 3, no
                        | NO un toast chico     |                          |                                 |                                 | pasivo)
Contador cambios usados | —                    | torneo sin tope → no se | —                               | "X/Y" visible, por equipo,     | —
                        |                      | muestra el contador      |                                 | par espejado (ver wireframe)   |
```

## Pass 3 — Recorrido del Usuario y Arco Emocional: 3/10 → 8/10

Storyboard del cierre forzado (agrega detalle a lo que antes era una sola oración):
```
PASO | EL OPERADOR HACE            | SIENTE                  | EL PLAN ESPECIFICA?
-----|------------------------------|--------------------------|---------------------
1    | Clima/incidente ocurre       | Estrés, urgencia         | Botón fijo en zona primaria (Pass 1)
2    | Toca "Fin de Partido forzado"| ¿Funcionó mi tap?        | Modal de confirmación se abre inmediato
3    | Elige motivo (chip/picklist) | Quiere ser rápido        | Picklist + "Otro" — NO texto libre puro (ver hallazgo #7 abajo)
4    | Confirma                    | Ansiedad: ¿ya se cerró?  | Banner persistente de countdown, alto contraste
5    | Se aleja de la pantalla      | Atención en la emergencia| **Requiere reenganche, no countdown pasivo puro**
     | (por el propio escenario)   | real, no en el software  | (ver hallazgo crítico #8 abajo — resuelto)
6    | Vuelve a mirar (o no)        | Necesita saber "¿terminó?"| Estado de éxito explícito con texto completo
```

**Hallazgo crítico #8 resuelto**: el subagent señaló correctamente que un countdown puramente pasivo se dispara justo cuando el operador dejó de mirar la pantalla (el propio escenario de uso lo garantiza). **Decisión de diseño**: el commit diferido de 5s NO arranca su cuenta regresiva hasta que la ventana recupera foco/visibilidad (`document.visibilitychange`) — si el operador navega a otra pantalla dentro de la app, el timer se pausa, no sigue corriendo a ciegas. Al volver, el banner persistente sigue mostrando el countdown restante. Esto convierte el "no puede olvidarse el cierre" en un requisito real, no en un accidente de implementación (ítem que la Sección 4 de Fase 1 ya marcaba como "debe ser explícito").

## Pass 4 — Riesgo de "AI Slop": 8/10 → 9/10

Clasificación: App UI. Ningún patrón de los 7 de rechazo duro aplica (son específicos de landing pages/marketing). Revisando contra la lista universal: sin grids de 3 columnas, sin iconos en círculos de color decorativos, sin texto centrado por defecto, sin blobs decorativos — el panel reusa la densidad ya establecida en `MesaPanel.tsx`/`GestionarPartido.tsx`. **Corrección al hallazgo #9 del subagent** (afirmación sin evidencia): el patrón visual reusado es específicamente el layout de dos columnas por equipo ya usado en `AlineacionEditor.tsx` (zonas "Titulares"/"Suplentes" lado a lado) — se cita explícitamente para no repetir el error de una afirmación de diseño sin `archivo:línea`.

## Pass 5 — Alineación con el Sistema de Diseño: N/A (no existe DESIGN.md) → recomendación registrada

Sin `DESIGN.md`, no hay tokens que validar. Se recomienda (ya recomendado por los 3 planes anteriores de este repo, no se repite la recomendación como hallazgo nuevo) correr `/design-consultation` en algún momento futuro — fuera de alcance de este plan.

## Pass 6 — Responsive y Accesibilidad: 5/10 → 8/10

- El modal de sustitución no requiere drag — funciona igual en cualquier viewport, sin necesitar la decisión de "tap de primera clase" que sí aplicó a `AlineacionEditor` (ya tomada, se hereda).
- El banner de countdown de undo debe ser el elemento de MAYOR prioridad de foco de teclado mientras está visible (un usuario de teclado/lector de pantalla no debe poder "perderse" el estado más crítico de seguridad de toda la feature) — `aria-live="assertive"` en el banner, no `polite`.
- Botón "Fin de Partido forzado": `aria-label` explícito distinto de los botones normales de cierre de período (ya señalado en Fase 1, Sección 11).
- Objetivo táctil mínimo de 44px para el chip de motivo (se toca bajo estrés, no es momento de precisión fina).

## Pass 7 — Decisiones de Diseño No Resueltas (resueltas en esta pasada)

```
DECISIÓN NECESARIA                         | SI SE DIFIERE, QUÉ PASA                              | RESUELTO
---------------------------------------------|--------------------------------------------------------|------------
Copy literal del botón de cierre forzado     | el implementador inventa un texto ambiguo             | "Finalizar partido (forzado)" — nunca solo "Finalizar", para diferenciarlo del cierre normal
Forma del campo motivo_cierre                | texto libre fragmenta la métrica de observabilidad     | picklist (Clima, Incidente, Lesión grave, Orden de seguridad, Otro) + campo libre solo si "Otro"
Orden de la lista de elegibles en el modal   | orden inconsistente entre desarrolladores              | por dorsal ascendente — consistente con `marcarPrimerosComoTitulares` y el resto de `AlineacionEditor`
Comportamiento del countdown al perder foco  | se dispara mientras el operador no mira (hallazgo #8)  | se pausa en visibilitychange, banner persiste al volver
Estado vacío de "sin suplentes elegibles"    | callejón sin salida, operador debe cancelar y navegar  | ofrece inline la acción de alta tardía (onSumarTardio)
Ubicación del botón de cierre forzado        | podría terminar detrás de un menú, poco descubrible    | fijo en zona primaria del wireframe (Pass 1)
```

**PHASE 2 COMPLETE.** Codex: no disponible (0 concerns). Claude subagent: 11 hallazgos (4 críticos, 3 altos, 2 medio-altos, 2 medios) — los 4 críticos y 3 altos incorporados directamente como fixes estructurales (P5: auto-fix, no es una decisión de gusto). 0 hallazgos quedan como TASTE DECISION (todos eran gaps de completitud, no preferencias estéticas). Pasando a Fase 3 (Eng, última fase, revisa el plan ya enmendado por Fases 1 y 2).

## "NO en alcance" (Design)
- `/design-consultation` para un DESIGN.md formal — recomendado pero fuera de esta feature puntual (mismo criterio que los 3 planes anteriores).
- Mockups visuales generados por herramienta — `gstack-design` no está instalado; revisión basada en wireframes ASCII + especificación textual.

## "Qué ya existe" (Design)
- Layout de dos columnas por equipo ya usado en `AlineacionEditor.tsx` (Titulares/Suplentes lado a lado) — reusado para el par de contadores "cambios usados".
- `onSumarTardio` (alta tardía de suplente) ya existe — reusado como salida del estado vacío del modal de sustitución en vez de construir un flujo nuevo.
- Densidad visual y componentes de `MesaPanel.tsx`/`GestionarPartido.tsx` — heredados sin cambios de lenguaje visual.

## TODOS.md updates (Design)
- Ninguna deuda de diseño nueva diferida — los 7 hallazgos altos/críticos se resolvieron dentro de esta misma pasada (fixes estructurales, no diferibles sin dejar la feature incompleta). La única recomendación diferida (`/design-consultation` para DESIGN.md) ya está registrada como deuda conocida por los 3 planes anteriores de este repo — no se duplica aquí.

## Implementation Tasks (Design phase)
Ver artefacto en disco: `~/.gstack/projects/Score-App/tasks-design-review-20260908-191753.jsonl` (5 tareas, T9-T13).

## Completion Summary — Design Review

```
  +====================================================================+
  |         DESIGN PLAN REVIEW — COMPLETION SUMMARY                    |
  +====================================================================+
  | System Audit         | Sin DESIGN.md; App UI interno confirmado    |
  | Step 0               | Rating inicial 4/10, foco: todos los 7 pases|
  | Pass 1  (Info Arch)  | 4/10 → 9/10 (wireframe de 3 zonas agregado) |
  | Pass 2  (States)     | 3/10 → 9/10 (2 filas criticas agregadas)    |
  | Pass 3  (Journey)    | 3/10 → 8/10 (undo re-diseñado, hallazgo #8) |
  | Pass 4  (AI Slop)    | 8/10 → 9/10 (cita concreta agregada)        |
  | Pass 5  (Design Sys) | N/A → recomendacion registrada (sin DESIGN.md)|
  | Pass 6  (Responsive) | 5/10 → 8/10 (aria-live, touch targets)      |
  | Pass 7  (Decisions)  | 6 resueltas, 0 diferidas                    |
  +--------------------------------------------------------------------+
  | NOT in scope         | escrito (2 items)                            |
  | What already exists  | escrito                                      |
  | TODOS.md updates     | 0 items nuevos (recomendacion ya registrada) |
  | Approved Mockups     | 0 generados (gstack-design no instalado)     |
  | Decisions made       | 6 agregadas al plan                          |
  | Decisions deferred   | 0                                            |
  | Overall design score | 4/10 → 9/10                                  |
  +====================================================================+
```

---

# FASE 3 — Eng Review (última fase, revisa el plan ya enmendado por Fases 1-2)

## Paso 0 — Scope Challenge

**Qué ya existe**: cubierto en 0B (Fase 1). **Mínimo conjunto de cambios**: cubierto en 0D (Fase 1) — ya se decidió no reducir alcance (P2). **Complexity check**: el plan toca ~12 archivos, por encima del umbral de 8 — ya reconocido en Fase 1 0D; `/autoplan` fija "Scope challenge: never reduce (P2)", así que no se reduce, se procede con las 4 Áreas + Bloque 0 como 4 sub-entregas independientes. **TODOS cross-reference**: `TODOS.md:462-464` (tope diferido, este plan lo reabre — ya documentado como reversión), sin otros bloqueos.

## Paso 0.5 — Voces Duales (Eng)

`[subagent-only]` — Codex no disponible, mismo criterio que Fases 1-2.

**CLAUDE SUBAGENT (eng — independencia arquitectónica)** — leyó el plan Y el código fuente real (no solo el prosa del plan), hallazgos verificados con cita archivo:línea:

1. **[CRÍTICO]** Retirar `estado` de `PartidoUpdateSchema` NO produce un 422 como afirmaba el plan — Pydantic v2 default es `extra="ignore"` (confirmado: ningún schema de `backend/app/schemas/` fija `extra="forbid"`), así que un PATCH con `estado` sería **silenciosamente ignorado**, exactamente el fallo silencioso que la Directiva Prima #1 prohíbe. **Corregido abajo.**
2. **[ALTO]** `backend/tests/test_partidos.py:117-135` YA hace `PATCH /partidos/{id} {estado: "En curso"}` y espera 200 — este cambio rompe tests existentes que hoy pasan. **Corregido abajo** (se actualizan como parte del mismo cambio).
3. **[MEDIO]** `PartidoService.marcar_walkover` (`partido.py:120-122`) ya escribe `Estado` directamente hoy, sin pasar por Hito — la afirmación "100% derivado de Hitos" es falsa tal cual estaba redactada. **Corregido**: se documenta como excepción reconocida (walkover tiene sus propios guards), no como violación.
4. **[MEDIO]** La Sección 1/3 de Fase 1 citaba un rol `Mesa` que no existe — `database/02_constraints.sql:295`: `chk_usuarios_rol CHECK (Rol IN ('AdminGeneral','TorneoAdmin','Arbitro','Publico'))`. **Corregido**: el guard real es el mismo que ya protege el resto de Hitos (árbitro asignado vía `verificar_arbitro_asignado`, o el scoping de torneo que ya envuelve la ruta para `TorneoAdmin`/`AdminGeneral`) — no un rol nuevo.
5. **[MEDIO]** El método citado `ConvocadoAPartidoService.marcar_titular` no existe — el servicio real solo tiene `reemplazar` (PUT completo, pre-arranque) y `agregar` (POST aditivo). **Corregido**: se especifica exactamente en cuál de los dos (y en qué línea) va el guard.
6. **[ALTO]** Race de concurrencia real en "no doble Fin_Partido": `HITOS_PARTIDO` no tiene ningún índice único, solo un trigger `BEFORE INSERT` con `SELECT COUNT(*)` (`fn_validar_hito_partido`, `06_triggers.sql:598-608`) — clásico TOCTOU bajo dos transacciones concurrentes. **Corregido**: índice único parcial a nivel DB.
7. **[ALTO]** Race de concurrencia idéntica en el tope de titulares nuevo: `agregar` (`convocado_a_partido.py:206-259`) no tiene control de versión, solo captura `IntegrityError` de la unicidad convocado-jugador, no de un conteo. **Corregido**: guard a nivel DB (trigger con lock de fila), no solo aplicación.
8. **[ALTO]** Ninguna alternativa fue evaluada para el mecanismo de undo de Área 4 (0C-bis solo cubrió Áreas 1-3) — y la que se eligió (commit diferido 100% cliente) **no protege contra el escenario que dice proteger**: si el navegador/dispositivo falla durante los 5s (batería, crash, pérdida de red — exactamente lo que pasa en un evento de clima/incidente), el partido **nunca se cierra** y nadie lo sabe, porque todo el estado de "pendiente de cerrar" vive solo en memoria del cliente. El propio "Hallazgo crítico #8" de Fase 2 solo resolvió el caso de navegación DENTRO de la app, no el caso más probable (el dispositivo deja de responder). **CORREGIDO — ver "Corrección de Diseño" abajo, supera la decisión de Fase 1.**
9. **Verificación aparte, confirma un hallazgo ya hecho**: "minuto falsificable por el cliente" es cierto hoy (`evento_partido.py:58-65`, sin cross-check contra el tiempo real del Hito) — el plan lo tenía bien.
10. **Verificación aparte, confirma un hallazgo ya hecho**: `Modalidad.tamano_equipo` SÍ es el campo correcto ("cuántos juegan A LA VEZ", `modalidad.py:8-14`, distinto de `tamano_plantilla_max`) — pero rompe la simetría con el patrón de override a nivel TORNEO que el propio plan cita 2 veces (`minimo_jugadores_para_iniciar`). **Corregido**: se agrega un override opcional simétrico.

```
ENG DUAL VOICES — CONSENSUS TABLE:
═══════════════════════════════════════════════════════════════
  Dimension                           Claude  Codex  Consensus
  ──────────────────────────────────── ─────── ─────── ─────────
  1. Architecture sound?               NO (2 huecos crít./altos) N/A N/A — corregidos abajo
  2. Test coverage sufficient?         NO (concurrencia, crash)  N/A N/A — corregidos abajo
  3. Performance risks addressed?      SÍ                        N/A N/A
  4. Security threats covered?         PARCIAL (rol inexistente) N/A N/A — corregido
  5. Error paths handled?              NO (extra=ignore)         N/A N/A — corregido
  6. Deployment risk manageable?       SÍ (tras las correcciones)N/A N/A
═══════════════════════════════════════════════════════════════
CONFIRMED = both agree. Codex no disponible — [subagent-only]. Todos los hallazgos
crítico/alto de la única voz se incorporan igual (misma regla aplicada en Fases 1-2).
```

## Corrección de Diseño (supera la Decisión de Fase 1 sobre el undo de Área 4)

**Decisión anterior** (Fase 1, 0F): commit diferido 100% cliente, POST retrasado 5s.
**Corrección**: el Hito `Fin_Partido(forzado=true)` se inserta **de inmediato** al confirmar (soft-commit server-side) — dispara la cascada normal (trigger sincroniza `Estado='Finalizado'`, propaga bracket si aplica), exactamente igual que un cierre normal. La ventana de 5s deja de ser "no enviar el POST" y pasa a ser **una ventana de deshacer real, autoritativa en el servidor**:

```
  POST /partidos/{id}/hitos {tipo: Fin_Partido, forzado: true, motivo_cierre}
        │
        ▼
  Hito insertado ──▶ trigger sincroniza Estado='Finalizado' ──▶ (si aplica) trigger propaga bracket
        │
        ▼
  Respuesta incluye deshacer_disponible_hasta = Timestamp_Real + 5s
        │
        ▼
  Cliente muestra banner persistente con countdown (Pass 3, Fase 2 — sin cambios en el diseño visual)
        │
        ├──(usuario toca DESHACER, o vuelve tras perder foco y el countdown no expiró)──┐
        │                                                                                ▼
        │                                                          POST /partidos/{id}/deshacer-cierre-forzado
        │                                                                │
        │                                                    valida: (a) último Hito es
        │                                                    Fin_Partido(forzado=true) de ESTE
        │                                                    partido, (b) ahora <= deshacer_disponible_hasta
        │                                                    (chequeado en SERVIDOR, no en cliente),
        │                                                    (c) si hubo propagación de bracket, el partido
        │                                                    siguiente NO tiene hitos/eventos propios
        │                                                    todavía (si ya avanzó, se rechaza el deshacer
        │                                                    con mensaje explícito: "ya no se puede deshacer,
        │                                                    el rival ya avanzó")
        │                                                                │
        │                                                                ▼
        │                                              transacción atómica: borra el Hito Fin_Partido,
        │                                              recalcula Estado desde los Hitos restantes (reusa
        │                                              _calcular_estado, no un valor hardcodeado), revierte
        │                                              el slot de equipo propagado en el partido siguiente
        │                                              si corresponde
        │
        └──(no se toca nada en 5s, o el deshacer llega tarde/es rechazado)──▶ el cierre queda firme
                                                                               (ya lo estaba desde el insert)
```
**Por qué esto es más seguro, no menos**: el partido queda cerrado desde el instante de la confirmación — visible a cualquier otro operador, al bracket, a la auditoría — sin depender de que un navegador/dispositivo siga vivo 5 segundos en medio de una emergencia. El caso "el dispositivo muere durante la ventana" ahora simplemente significa "el deshacer no se ejecutó" — el resultado (partido cerrado) es el mismo que si el operador hubiera esperado los 5s, que es el comportamiento correcto por defecto. Reusa el patrón de transacción atómica multi-paso ya probado en `PartidoService.registrar_resultado_directo` (`partido.py:124-209`, flush intermedios + commit único).

**Ajuste de UI (Fase 2) que se mantiene sin cambios**: el banner persistente con countdown y el pausado por `visibilitychange` siguen siendo correctos — ahora comunican un estado real del servidor (una ventana de deshacer que SÍ existe del lado del servidor), no una ficción del cliente.

## Sección 1 — Arquitectura (correcciones aplicadas)

**Diagrama de dependencias actualizado** (reemplaza el de Fase 1 en los puntos corregidos):
```
  GestionarPartido.tsx ──POST /partidos/{id}/hitos {forzado:true}──▶ HitoPartidoService.registrar
        │                                                                    │
        │ +banner countdown, deshacer_disponible_hasta del server           + inserta Hito de inmediato
        │                                                                    │ (soft-commit, no diferido)
        ▼                                                                    ▼
  (banner countdown)◀──POST /deshacer-cierre-forzado (dentro de la ventana)──HitoPartidoService.deshacer_forzado (nuevo)
                                                                              │
                                                                              + transacción atómica: borra
                                                                                Hito, recalcula estado,
                                                                                revierte propagación si es
                                                                                seguro

  PartidoService.update ──X estado con extra="forbid" en PartidoUpdateSchema──▶ 422 real (no ignore silencioso)
        │
        + marcar_walkover documentado como excepción reconocida (guards propios, no pasa por Hito)

  ConvocadoAPartidoService.agregar ──+trigger fn_validar_tope_titulares (lock de fila,──▶ CONVOCADO_A_PARTIDO
    (guard de tope AQUÍ,                cierra el race de concurrencia)
     línea 206-259, no en un
     método "marcar_titular"
     inexistente)

  HITOS_PARTIDO ──+índice único parcial (Partido_ID) WHERE Tipo_Hito='Fin_Partido'──▶ (race de doble-submit
                                                                                        cerrado a nivel DB)

  Torneo.maximo_titulares_permitido (nuevo, NULL=usar tamano_equipo) ──▶ simetría con
                                                                          minimo_jugadores_para_iniciar
```

**Auth boundary corregido**: el override de Fin de Partido forzado usa exactamente el mismo guard que ya protege `POST /partidos/{id}/hitos` hoy — árbitro asignado (`verificar_arbitro_asignado`) o el scoping de torneo que ya envuelve la ruta para roles de gestión (`TorneoAdmin`/`AdminGeneral`, los únicos roles reales según `chk_usuarios_rol`). No se introduce ningún rol nuevo ni ninguna superficie de autorización nueva.

**Escenario de fallo en producción (nuevo, corregido)**: dispositivo del operador pierde energía/conexión durante la ventana de deshacer → con el diseño corregido, el partido queda cerrado (comportamiento correcto, ver arriba) en vez de quedar indefinidamente sin cerrar (el bug que tenía el diseño anterior).

## Sección 2 — Calidad de Código (correcciones)

- `PartidoUpdate` (`schemas/partido.py`) gana `model_config = ConfigDict(extra="forbid")` — verificar primero que ningún caller legítimo depende de campos extra siendo ignorados (no se encontró ninguno en el código actual).
- Referencias a `ConvocadoAPartidoService.marcar_titular` en todo este documento (Fase 1, Sección 2) se corrigen a `ConvocadoAPartidoService.agregar` (el guard de tope vive en su branch `ya_arranco`/pre-arranque, línea 206-259) — actualizar antes de implementar.
- Referencias a "rol Mesa" (Fase 1, Sección 1/3) se corrigen a "árbitro asignado o scoping de torneo existente" en todo el documento.
- `marcar_walkover` se documenta explícitamente en el código (comentario) como la excepción reconocida a "Hito es la única fuente de verdad de Estado" — no se toca su comportamiento (tiene sus propios guards, fuera de alcance de este plan).

## Sección 3 — Revisión de Tests (diagrama de cobertura)

```
CODE PATHS                                                    USER FLOWS
[+] backend/app/schemas/partido.py                            [+] Cierre forzado de partido
  └── PartidoUpdate.model_config extra=forbid                   ├── [★★★ NUEVO] Confirmar → Hito insertado
      ├── [GAP→TEST] PATCH con estado → 422 (no 200 silencioso) │   de inmediato, banner countdown
      └── [GAP→TEST] test_partidos.py:117-135 ACTUALIZAR        ├── [★★★ NUEVO] Deshacer dentro de la
          (ya no puede esperar 200 al mandar estado)             │   ventana → Hito borrado, estado
                                                                  │   recalculado
[+] backend/app/services/hito_partido.py                        ├── [★★  NUEVO] Deshacer rechazado (rival
  ├── _validar_titulares (+ tope máximo)                         │   ya avanzó) → mensaje explícito
  │   ├── [★★★ NUEVO] rechaza exceso, respeta maximo_titulares_  ├── [GAP→E2E] Deshacer fuera de la
  │   │   permitido si está seteado, si no usa tamano_equipo      │   ventana (server-side) → rechazado
  │   └── [GAP] concurrencia: 2 requests simultáneos cerca        └── [GAP→E2E crash-sim] Simular pérdida
  │       del tope (test con 2 transacciones DB reales,               de conexión tras confirmar → partido
  │       no 2 llamadas HTTP secuenciales)                            queda cerrado igual (verificar
  ├── registrar (Fin_Partido, forzado=true)                           contra DB directamente, no UI)
  │   ├── [★★★ NUEVO] permitido desde cualquier acciones_permitidas
  │   ├── [GAP] doble-submit CONCURRENTE (2 transacciones DB reales
  │   │   contra el índice único parcial nuevo, no 2 HTTP secuenciales)
  │   └── [★★  NUEVO] rechaza si ya Finalizado (guard existente)
  └── deshacer_forzado (NUEVO método)
      ├── [★★★ NUEVO] dentro de ventana + rival sin avanzar → éxito
      ├── [★★★ NUEVO] fuera de ventana (chequeado server-side) → rechazado
      └── [★★★ NUEVO] rival ya avanzó → rechazado con mensaje explícito

[+] backend/app/services/convocado_a_partido.py
  └── agregar (+ guard de tope vía trigger fn_validar_tope_titulares)
      ├── [★★★ NUEVO] rechaza exceso
      └── [GAP] concurrencia: 2 POST simultáneos cerca del tope (2
          transacciones DB reales contra el trigger con lock de fila)

[+] database/06_triggers.sql / nueva migración
  ├── índice único parcial HITOS_PARTIDO(Partido_ID) WHERE Tipo_Hito='Fin_Partido'
  │   └── [★★★ NUEVO] test de integridad: INSERT directo duplicado -> IntegrityError
  └── fn_validar_tope_titulares (trigger BEFORE INSERT/UPDATE, lock de fila)
      └── [★★★ NUEVO] test de integridad: INSERT directo por encima del tope -> excepción

[+] frontend/src/components/Cronometro.tsx
  ├── onMinutoActual (nuevo prop callback)
  │   └── [★★  NUEVO] MesaPanel recibe el minuto sin round-trip nuevo
  └── banner de deshacer (countdown desde deshacer_disponible_hasta del SERVIDOR,
      no un timer local inventado)
      ├── [★★★ NUEVO] countdown correcto tras recargar la página a mitad de la ventana
      │   (el server-side timestamp lo permite; el diseño anterior NO lo hubiera permitido)
      └── [★★  NUEVO] aria-live=assertive, pausa visual en visibilitychange (Pass 3, Fase 2)

[+] frontend/src/pages/control-mesa/GestionarPartido.tsx / AlineacionEditor.tsx
  ├── ModalSustitucion (nuevo)
  │   ├── [★★★ NUEVO] elige elegible → evento Cambio creado
  │   ├── [★★  NUEVO] cierra sin elegir → no persiste nada
  │   ├── [GAP] estado vacío → ofrece onSumarTardio inline (Pass 2/7, Fase 2)
  │   └── [GAP] falla el GET de elegibles → retry inline, modal abierto (Pass 2, Fase 2)
  └── moverA (alineacion.ts) rechaza exceso client-side
      └── [★★★ NUEVO] snap-back + toast con mensaje exacto del backend (Pass 2, Fase 2)

[+] backend/app/repositories/evento_partido.py (u homólogo)
  └── listar ORDER BY minuto, id
      └── [★★  NUEVO] insertar min 40 luego min 2 → GET devuelve 2 antes que 40

COVERAGE: 0/22 paths tested hoy (todo es código nuevo) — 22 tests especificados en el
artefacto de disco, 6 marcados [GAP→E2E]/concurrencia real (requieren 2 transacciones/
sesiones simultáneas, no 2 llamadas secuenciales — la clase de test que Fase 1 marcaba
como cubierta y en realidad no lo estaba).
QUALITY objetivo: ★★★ en los 6 paths de concurrencia y en el mecanismo de deshacer
(son los que determinan si el partido queda cerrado o no bajo fallo real).
```

### REGRESIÓN (regla obligatoria)
El retiro de `estado` de `PartidoUpdateSchema` modifica comportamiento EXISTENTE (`test_partidos.py:117-135` pasa hoy) — se marca **CRÍTICO**, sin AskUserQuestion, per la Regla de Regresión: se actualizan esos 2 tests como parte del mismo cambio (ya no esperan 200 al mandar `estado` en el PATCH; el nuevo comportamiento esperado es 422).

### Artefacto de plan de pruebas
Escrito en disco: `~/.gstack/projects/Score-App/gabriel-feat-equipos-jugadores-plan-eng-review-test-plan-20260908.md`.

## Sección 4 — Rendimiento

Sin cambios respecto al análisis de Fase 1 (Sección 7) salvo lo siguiente, encontrado al diseñar los guards de concurrencia:
- El trigger `fn_validar_tope_titulares` (nuevo) hace `SELECT ... FOR UPDATE` sobre la fila del partido para serializar escrituras concurrentes de convocatoria — a este volumen (una convocatoria por partido, decenas de jugadores) el costo de lock es despreciable; NO se traduce en contención real salvo el caso adversarial de 2 requests exactamente simultáneos, que es justamente el caso que el lock existe para resolver correctamente, no para optimizar.
- El endpoint `deshacer-cierre-forzado` hace una lectura adicional (verificar que el partido siguiente del bracket no tenga hitos propios) antes de la transacción de reversión — una query indexada por `partido_id`, sin impacto medible.
- Nada nuevo de N+1: todos los guards nuevos son lecturas puntuales por partido/equipo, ya indexadas por el esquema existente.

## Worktree parallelization strategy

| Paso | Módulos tocados | Depende de |
|------|------------------|------------|
| Bloque 0 (estado + `extra=forbid` + tests rotos) | `backend/app/schemas/`, `backend/app/services/partido.py`, `backend/tests/` | — |
| Área 1 (tope de titulares + migración `maximo_titulares_permitido` + trigger de concurrencia) | `backend/app/models/torneo.py`, `backend/app/services/convocado_a_partido.py`, `backend/app/services/hito_partido.py`, `database/`, `frontend/.../alineacion.ts` | — |
| Área 2 (orden cronológico) | `backend/app/repositories/`, `frontend/.../MesaPanel.tsx` | — |
| Área 3 (minuto automático + modal sustitución + reglas de cambio) | `frontend/.../Cronometro.tsx`, `frontend/.../MesaPanel.tsx`, `frontend/.../GestionarPartido.tsx`, `backend/app/models/torneo.py`, `backend/app/services/evento_partido.py`, `database/` | Bloque 0 (comparte `torneo.py`/migraciones con Área 1 — coordinar el orden de columnas nuevas) |
| Área 4 (Fin de Partido forzado + deshacer + índice único) | `backend/app/services/hito_partido.py`, `database/`, `frontend/.../Cronometro.tsx` | Bloque 0 (mismo archivo `hito_partido.py` que Área 1 — secuencial entre sí) |

**Lanes**:
- Lane A: Bloque 0 (independiente, arranca primero — desbloquea el resto al tocar el schema compartido).
- Lane B: Área 2 (100% independiente — ni una sola dependencia con las demás áreas, puede correr en paralelo con todo).
- Lane C (secuencial dentro de sí misma): Bloque 0 → Área 1 → Área 4 (las tres tocan `hito_partido.py` y/o `torneo.py`/migraciones — mismo módulo, ordenar migraciones para no chocar en la numeración de archivos `NN_migracion_*.sql`).
- Lane D: Área 3 frontend (Cronometro/MesaPanel) puede empezar en paralelo con Lane C una vez que Bloque 0 esté mergeado; el campo `Torneo.permite_cambios_ilimitados` de Área 3 backend debe coordinarse con Área 1 backend para no numerar dos migraciones en conflicto.

**Orden de ejecución**: lanzar Lane A (Bloque 0) primero, en solitario. Al mergear, lanzar Lane B (Área 2) y Lane C (Área 1→4) en paralelo en worktrees separados; Lane D (Área 3) arranca en paralelo con Lane C pero coordina las migraciones antes de mergear cualquiera de las dos.

**Conflictos señalados**: Lane C y Lane D ambas tocan `backend/app/models/torneo.py` y agregan migraciones nuevas — mismo archivo, alto riesgo de conflicto de merge si corren totalmente en paralelo sin coordinación de numeración de migraciones. Recomendado: Lane C reserva el número de migración para `maximo_titulares_permitido`, Lane D reserva el siguiente para `permite_cambios_ilimitados`, se comunican antes de escribir.

## "NO en alcance" (Eng)
- Reescribir `marcar_walkover` para que pase por Hito — fuera de alcance, tiene sus propios guards ya probados, no es parte de este pedido.
- Un mecanismo genérico de "operación reversible con ventana de gracia" reutilizable para otras acciones destructivas del sistema — el patrón de `deshacer-cierre-forzado` es específico a este caso; generalizarlo es una refactorización de plataforma fuera del blast radius de este plan (mismo criterio que el motor de reglamento genérico, ya diferido en Fase 1).
- Distinguir formalmente en el schema `EventoPartidoCreate` entre "vivo" y "retroactivo" con dos tipos separados — se resuelve con una validación condicional simple (si `partido.estado == 'En curso'`, ignorar `minuto` del payload), no con dos schemas — evaluado y descartado por sobre-ingeniería (P5).

## "Qué ya existe" (Eng)
Ver 0B (Fase 1) — sin cambios. Adicional encontrado en esta fase: `fn_validar_hito_partido` ya establece el PATRÓN de validación por trigger `BEFORE INSERT` que `fn_validar_tope_titulares` (nuevo) replica — no se inventa un mecanismo nuevo de validación a nivel DB, se sigue el que ya existe.

## Registro de Modos de Fallo (actualizado con hallazgos de Fase 3)

```
  CODEPATH                                    | MODO DE FALLO                          | RESCATADO? | TEST? | QUÉ VE EL USUARIO      | LOGUEADO?
  ----------------------------------------------|------------------------------------------|------------|-------|-------------------------|----------
  PartidoUpdate schema                          | Cliente manda estado en el payload       | Sí (extra=forbid, corregido) | Sí (nuevo) | 422 real, no 200 silencioso | Sí
  ConvocadoAPartidoService.agregar              | 2 requests concurrentes cerca del tope   | Sí (trigger con lock, corregido) | Sí (nuevo, 2 transacciones reales) | uno de los dos ve el mensaje de tope | Sí
  HitoPartidoService.registrar (Fin_Partido)    | 2 requests concurrentes de cierre        | Sí (índice único parcial, corregido) | Sí (nuevo, 2 transacciones reales) | uno de los dos ve "ya finalizado" | Sí
  HitoPartidoService.deshacer_forzado (nuevo)   | Rival ya avanzó en el bracket             | Sí (guard nuevo) | Sí (nuevo) | mensaje explícito "no se puede deshacer" | Sí
  HitoPartidoService.deshacer_forzado (nuevo)   | Ventana expirada (chequeo server-side)    | Sí (guard nuevo) | Sí (nuevo) | mensaje "la ventana ya expiró" | Sí
  Cierre forzado + fallo de dispositivo         | Navegador/red cae durante los 5s          | Sí (por diseño: el cierre ya es firme desde el insert) | Sí (nuevo) | partido queda cerrado igual (correcto) | Sí
```
Ninguna fila queda con RESCATADO=N, TEST=N, USUARIO VE=Silencioso — los 2 gaps críticos que trajo la Fase 3 (extra=ignore silencioso, undo que no protege su propio escenario) quedan cerrados por las correcciones de esta fase.

## TODOS.md updates (Eng — recolecta lo diferido en las 3 fases)

Se agregan a `TODOS.md` las 3 entradas diferidas (Fase 1, 0D) más 1 nueva encontrada en esta fase:
1. Badge de sanción pendiente en convocatoria — bloqueado por falta de modelo de sanciones.
2. Exportar resultado directo a texto plano (WhatsApp) — fuera de blast radius.
3. Motor de reglamento de torneo genérico (`ReglamentoTorneo`) — refactor estructural, L effort.
4. **Nuevo**: mecanismo genérico de "operación reversible con ventana de gracia" — el patrón de `deshacer-cierre-forzado` construido aquí es candidato a generalizarse si aparece una segunda necesidad similar (ej. deshacer un walkover marcado por error) — no se construye ahora (P2, un solo caso de uso no justifica la abstracción), se anota para cuando aparezca el segundo caso.

## Implementation Tasks (Eng phase)
Ver artefacto en disco: `~/.gstack/projects/Score-App/tasks-eng-review-20260908-193010.jsonl` (12 tareas, T14-T25).

## Completion Summary — Eng Review

```
  +====================================================================+
  |            ENG PLAN REVIEW — COMPLETION SUMMARY                    |
  +====================================================================+
  | Step 0 (Scope)       | Aceptado tal cual (P2: never reduce), 12    |
  |                       | archivos, tratado como 4 sub-entregas       |
  | Architecture Review  | 6 issues (2 crit, 3 alt, 1 med) — corregidos|
  | Code Quality Review  | 4 issues (nombres/refs incorrectas) — fix   |
  | Test Review          | diagrama de 22 paths, 6 gaps de concurrencia|
  |                       | identificados y resueltos                   |
  | Performance Review   | 1 hallazgo (lock de fila), sin riesgo real  |
  | NOT in scope         | escrito (3 items)                            |
  | What already exists  | escrito                                      |
  | TODOS.md updates     | 4 items escritos (3 diferidos + 1 nuevo)    |
  | Failure modes        | 6 codepaths, 0 CRITICAL GAPS tras correccion|
  | Outside voice        | [subagent-only], Codex no disponible         |
  | Parallelization      | 4 lanes, 2 paralelas + 2 secuenciales entre si|
  | Lake Score           | 12/12 tareas eligieron la opcion completa   |
  +====================================================================+
```

**PHASE 3 COMPLETE.** Codex: no disponible (0 concerns). Claude subagent: 10 hallazgos (2 críticos, 4 altos, 4 medios) — todos incorporados como correcciones directas al plan (arquitectura + diseño de Área 4 revisado). 0 huecos críticos de ingeniería quedan sin resolver. Pasando al Gate Final.

## Review Readiness Dashboard

```
+====================================================================+
|                    REVIEW READINESS DASHBOARD                       |
+====================================================================+
| Review          | Runs | Last Run            | Status              | Required |
|-----------------|------|---------------------|---------------------|----------|
| Eng Review      |  4   | 2026-09-08 (hoy)    | CLEAR (PLAN via /autoplan) | YES |
| CEO Review      |  4   | 2026-09-08 (hoy)    | issues_open (1 unresolved, ver Gate) | no |
| Design Review   |  3   | 2026-09-08 (hoy)    | CLEAR (score 4→9, FULL via /autoplan) | no |
| Adversarial     |  0   | —                    | —                    | no       |
| Outside Voice   |  0   | —                    | —                    | no (Codex no disponible en esta máquina) |
+--------------------------------------------------------------------+
| VERDICT: CLEARED — Eng Review passed (0 unresolved, 0 critical gaps)|
+====================================================================+
```
Nota de frescura: los 4 registros de esta corrida comparten `commit d310abb` / working tree sucio (`dirty:true`) — son de ESTA sesión, no stale. Sin notas de staleness adicionales.

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 4 | issues_open | 6 propuestas, 3 aceptadas, 2 diferidas, 1 Desafío al Usuario sin resolver |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | no disponible | Codex no está en PATH en esta máquina |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 4 | clean | 10 issues, 0 critical gaps (todos corregidos) |
| Design Review | `/plan-design-review` | UI/UX gaps | 3 | clean | score: 4/10 → 9/10, 6 decisiones |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | omitida | módulo interno, sin superficie de API/CLI/SDK para terceros |

**CROSS-MODEL:** no aplica — Codex no disponible en esta máquina en las 3 fases; todas las voces fueron `[subagent-only]`.
**VERDICT:** CEO + ENG + DESIGN CLEARED — ready to implement.

**Gate Final resuelto por el usuario (2026-09-08):**
- D1 (Área 2, Taste Decision): el usuario eligió **mantener la carga incremental libre** (Approach A) — solo se arregla el orden cronológico server-side de `EventoPartido`. No se construye la UI de "slots por marcador". Ya reflejado en la tarea T7.
- Gate general: **Aprobado tal cual**, incluidas las correcciones de Fase 3 (extra=forbid, undo server-side, triggers de concurrencia).

NO UNRESOLVED DECISIONS


