<!-- /autoplan restore point: "C:\\Users\\Gabo\\.gstack\\projects\\Score-App\\main-autoplan-restore-20260916-234713.md" -->
# Desempate de eliminatoria: tiempo extra y penales

## Implementation plan

### 0. Premisa que este plan CORRIGE (explícito, a propósito)

`docs/plans/cierre-fase-regular-llaves-playoffs-plan.md` cerró el desempate con
esta decisión, repetida en tres lugares (`database/01_schema.sql` en el
comentario de `PARTIDOS.Ganador_Desempate_ID`, `06_triggers.sql` en
`fn_marcador_partido`, y el bloque `eligiendoDesempate` de `Cronometro.tsx:397`):

> "el sistema registra QUIÉN ganó, no CÓMO (penales/tiempo extra/decisión
> arbitral), mismo nivel de detalle que TRASPASOS.Motivo."

**Esa decisión se revierte acá, deliberadamente.** No fue un error en su momento:
el plan de llaves necesitaba desbloquear el bracket (sin `Ganador_Desempate_ID`
ningún cruce empatado se podía cerrar) y "quién" alcanzaba para eso. Lo que no
alcanza es para el registro competitivo real: un torneo de fútbol que define por
penales necesita el marcador de la tanda (3-1) en el acta, en el portal público y
en el bracket, y un torneo que juega prórroga necesita que los goles del alargue
CUENTEN en el marcador y en el global de la llave. Hoy las dos cosas son
invisibles: una final 1-1 resuelta 4-2 por penales y la misma final resuelta por
un gol en el minuto 105 son la misma fila en `PARTIDOS`.

Consecuencia de scope: este plan NO reemplaza `Ganador_Desempate_ID` — lo
mantiene como el contrato que `fn_marcador_partido`/`fn_resolver_llave` ya leen
(§4) y le suma el CÓMO alrededor.

### 1. Estado actual verificado (leído, no asumido)

| Pieza | Archivo | Qué hace hoy |
|---|---|---|
| Marcador de un partido | `database/06_triggers.sql:580` `fn_marcador_partido` | Walkover → 3-0; `Corrido` → `Ganador_Corrido_ID`; goles → cuenta `vw_goles_acreditados`, empate cae a `Ganador_Desempate_ID` (NULL si no está resuelto) |
| Ganador de una llave | `06_triggers.sql:657` `fn_resolver_llave` | Suma goles de ambas piernas cruzando localía; `Corrido` cuenta victorias de pierna; empate global → `Ganador_Desempate_ID` de la VUELTA |
| Validación de empate | `06_triggers.sql:742` `fn_validar_partido_eliminacion_desempate` | BEFORE UPDATE: la IDA empatada es legal; la VUELTA exige global resuelto; partido único exige `Ganador_Desempate_ID` |
| Generación del cuadro | `backend/app/services/motor_formatos.py:280` `_crear_llave`, `:358` `_sortear_bracket`, `:585` `generar_playoffs` | `Formato_Eliminatoria` (`Unico`/`Ida_Vuelta`/`Mixto`) decide 1 o 2 piernas por cruce; se persiste en `TORNEO.Formato_Eliminatoria` |
| UI de generación | `frontend/src/pages/torneo-admin/torneo-dashboard/ModalSiguienteFase.tsx:366` `PasoGenerarPlayoffs` | Radios de formato + estimación "N partidos · la final cae aprox. el …" |
| Cronómetro | `frontend/src/components/Cronometro.tsx` + `backend/app/services/hito_partido.py:89` `_calcular_estado` | Máquina de estados `Periodos`/`Corrido`. `Fin_Partido` solo se habilita cuando `ultimo_periodo_cerrado == Cantidad_Periodos`; `Inicio_Periodo` solo mientras `ultimo_periodo_cerrado < Cantidad_Periodos` |
| Desempate manual (vivo) | `Cronometro.tsx:397-430` | Radio "¿quién avanza?" → `Fin_Partido` con `ganador_desempate_id` |
| Desempate manual (carga directa) | `ModalResultadoDirecto.tsx:420, 788` | Mismo radio, dentro del guardado de resultado directo |
| Gate de "hace falta desempate" | `MesaPanel.tsx:290` y `ModalResultadoDirecto.tsx:420` | `ronda_nombre != null && marcador empatado` — derivado en el CLIENTE, dos veces |

**Bug preexistente que este plan tiene que arreglar (no es opcional):** ese gate
del cliente no distingue ida de vuelta ni calcula el global. En una llave
`Ida_Vuelta`, una IDA que termina 1-1 le pide desempate al operador (el trigger
lo permite igual, así que se graba un `Ganador_Desempate_ID` fantasma en la ida
que nadie lee), y una VUELTA 0-0 sobre una ida 2-2 NO se lo pide (el global está
empatado) y falla recién en el servidor con
`llave_empatada_en_global_sin_desempate`. Toda la lógica nueva de tiempo
extra/penales depende de saber "¿esta llave está empatada de verdad?", así que el
cálculo se mueve al servidor de una vez (§7, §11).

### 2. Qué se quiere lograr

Que el operador elija, al generar el cuadro eliminatorio (el mismo paso donde hoy
elige `Formato_Eliminatoria`), si un empate en tiempo regular se resuelve por
**tiempo extra** o **directo por penales**, y que el sistema registre el
resultado de esa definición — no solo quién pasó.

Las seis preguntas que el plan tenía que contestar están contestadas en §3-§8,
cada una con su razón.

### 3. D1 — El método se configura en el TORNEO, con variación POR RONDA

`TORNEO.Metodo_Desempate_Eliminatoria VARCHAR(20) NOT NULL DEFAULT 'Manual'`.

**El dominio del CHECK crece con las fases, no de una:** la migración 33 ship
`CHECK IN ('Manual', 'Penales_Directo')`; la migración 34 lo dropea y lo re-crea con
los cuatro valores. Sin esto la API acepta `'Tiempo_Extra_Penales'` en fase 2 aunque
el selector no lo ofrezca — el mismo fallo que S6 evita en la UI, una capa más abajo,
y fase 3 puede no agendarse nunca (gate de la métrica 4). Dicho acá para que nadie
shipee el CHECK ancho "para ahorrarse una migración".

| Valor | Significado | Fase |
|---|---|---|
| `'Manual'` | El radio "¿quién avanza?" de hoy. DEFAULT. | — (hoy) |
| `'Penales_Directo'` | Empate en tiempo regular ⇒ tanda de penales, sin prórroga. | Fase 2 |
| `'Tiempo_Extra_Penales'` | Prórroga; si sigue empatado, penales. | **Fase 3** |
| `'Penales_Salvo_Final'` | Penales directos en todas las rondas MENOS la Final, que juega prórroga. | **Fase 3** |

- Vive al lado de `Formato_Eliminatoria` (misma tabla, mismo paso de UI, misma
  semántica: "regla del cuadro").
- ~~"Ninguna competencia real define un cuadro donde una semifinal va a penales
  directos y la otra juega prórroga."~~ **Premisa FALSA, corregida por D-C1/E1.**
  `_piernas_por_ronda` (`motor_formatos.py:71`) ya hace exactamente eso con
  `Formato_Eliminatoria='Mixto'` (dos piernas en todas las rondas menos la Final).
  Copa América 2019/2021 mandó los cuartos directo a penales y jugó prórroga desde
  semis; en torneos amateur con cancha alquilada por hora es el caso por defecto.
  `'Penales_Salvo_Final'` es el espejo exacto de `'Mixto'`, un valor, sin columna nueva.
- **La ronda se decide por `PARTIDOS.Ronda_Nombre = 'Final'`, NO por el parámetro
  `es_final`.** Razón concreta: `_crear_llave(..., "Tercer Lugar", "Unico",
  es_final=True, ...)` (`motor_formatos.py:513`) pasa `es_final=True` para el
  Tercer Lugar, así que keyear por ese flag daría lo contrario de lo buscado.
  Con `Ronda_Nombre`, el Tercer Lugar cae del lado de penales — que es además lo
  correcto en competencia real.
- `'Manual'` es el DEFAULT: todo torneo existente sigue funcionando sin migración
  de datos, y es el único valor válido para disciplinas `Corrido` (§7).
- Por-llave (un override por cruce) queda fuera de scope. El hook existe:
  `PARTIDOS.Metodo_Desempate_Aplicable` (§8) es exactamente la columna que ese
  override necesitaría. No se construye la UI ahora.

### 4. D2 — Tiempo extra es reloj REAL, no una etiqueta

Un alargue "de etiqueta" (que solo precede al radio manual de hoy) no agrega
información: el operador sigue eligiendo a dedo quién pasa. Lo que hace útil al
tiempo extra es que **los goles del alargue cuentan**, y para que cuenten tienen
que entrar como `EVENTOS_PARTIDO` con su minuto real, que es exactamente lo que
el Motor de Tiempos ya sabe hacer con un período. Entonces: períodos de verdad.

**Todo §4 es FASE 3.** No se construye hasta que la métrica 4 (§12-bis) diga que el
cronómetro en vivo es el camino real de cierre en eliminatoria.

- `CONFIGURACION_TIEMPO_TORNEO` suma `Cantidad_Periodos_Extra INT` y
  `Duracion_Periodo_Extra_Minutos INT`, **NULLABLE en las dos ramas**, y
  `chk_config_tiempo_periodos` (`02_constraints.sql:178-182`) se extiende
  **agregando `AND Cantidad_Periodos_Extra IS NULL AND
  Duracion_Periodo_Extra_Minutos IS NULL` SOLO a la rama `Corrido`**. La rama
  `Periodos` queda intacta: las columnas nuevas son opcionales ahí (un torneo de
  fútbol que no usa prórroga las deja en NULL). Escrito así de explícito porque
  "como las dos columnas que ya existen" se leería como exigirlas `IS NOT NULL` en
  `Periodos`, y eso haría fallar la migración 34 contra toda fila existente.
  Python usa `COALESCE(cantidad_periodos_extra, 0)`.
  *Decisión explícita (D-S2 corregido):* NO se usa `NOT NULL DEFAULT 2/15`. Ese
  default contradice directamente el CHECK existente, que exige NULL en filas
  `Corrido` — las dos reglas no pueden valer a la vez. Se elige mantener el patrón
  del archivo y pagar un `COALESCE`.
- **`_calcular_estado`: el tope depende de si YA SE ENTRÓ al alargue, nunca del
  empate vigente.** Esto es la corrección de un defecto bloqueante de la redacción
  original, no un detalle:

  > `hito_partido.py:126-130` ofrece `Inicio_Periodo` mientras
  > `ultimo_periodo_cerrado < cantidad` y `Fin_Partido` solo con
  > `ultimo_periodo_cerrado == cantidad` (igualdad estricta). Con un tope
  > *condicionado al empate*, un gol en el 1er tiempo extra rompe el empate, el
  > tope vuelve a 2, y entonces `3 < 2` es falso y `3 == 2` es falso:
  > **el partido se queda sin ninguna acción permitida y no se puede cerrar nunca.**
  > Además prohibiría jugar el 2do tiempo extra, que en fútbol real siempre se juega.

  Reglas finales:
  - `periodos_totales_permitidos = Cantidad_Periodos + COALESCE(Cantidad_Periodos_Extra, 0)`
    si **(a)** existe ya un hito `Inicio_Periodo` con
    `Numero_Periodo > Cantidad_Periodos` (se entró al alargue), **o (b)** se cumplen
    las tres condiciones de entrada: partido de fase `Eliminacion`,
    `Metodo_Desempate_Aplicable` resuelve a prórroga para esta ronda, y la llave
    está empatada al cerrar el último período regular. En cualquier otro caso el
    tope es `Cantidad_Periodos`.
  - La condición de `Fin_Partido` pasa de `ultimo_periodo_cerrado == cantidad` a
    `ultimo_periodo_cerrado >= Cantidad_Periodos` con `periodo_abierto IS NULL`.
    Sin esto, ningún partido con alargue se puede cerrar.
  - Consecuencia deseada: una vez entrado el alargue, se juegan **los dos** tiempos
    extra aunque alguien marque en el primero.
- **Firma real del helper (D-Q3 corregido):** `_calcular_estado` es un
  `@staticmethod(hitos, config)` con tres llamadores (`hito_partido.py:78, 343, 540`)
  y no recibe ni `partido` ni `torneo`. El agregado de "¿la llave está empatada?" es
  **async** (`vw_goles_acreditados`, más una segunda consulta sobre la ida si es
  vuelta), así que no puede vivir dentro de un helper sync. El llamador async calcula
  el agregado (ya gateado por D-P1) y pasa dos escalares:
  `_periodos_totales_permitidos(config, hitos, llave_empatada: bool, metodo_aplicable: str | None) -> int`.
  Los tres llamadores se actualizan.
- El beneficio de caer sobre la mecánica de períodos existente: los goles del
  alargue ya entran a `vw_goles_acreditados` sin tocar la vista, así que
  `fn_marcador_partido` y `fn_resolver_llave` desempatan solos cuando el alargue
  define. **Cero cambios en las dos funciones que resuelven la llave.**
- `Numero_Periodo` de un período extra es `Cantidad_Periodos + 1`, `+2`, …; el
  cronómetro los muestra como "1er Tiempo Extra"/"2do Tiempo Extra"
  (`NOMBRES_PERIODO` en `Cronometro.tsx:55` se extiende con esa derivación, no
  con una lista nueva).
- `fn_validar_hito_partido` (`06_triggers.sql:924`) valida hoy `NEW.Numero_Periodo >
  v_cantidad_periodos`. **Se extiende SOLO al tope flojo**
  `Cantidad_Periodos + COALESCE(Cantidad_Periodos_Extra, 0)` — defensa en
  profundidad, no la regla precisa. Re-derivar fase + método + estado de empate en
  plpgsql sería una segunda copia de `_periodos_totales_permitidos` en otro
  lenguaje, que es justo lo que D-Q2/D-A2 prohíben. La regla precisa la dueña es el
  servicio; el trigger solo impide un `Numero_Periodo` absurdo.
- **Quién escribe `Hubo_Tiempo_Extra` (§5):** el camino en vivo lo pone en `TRUE` al
  abrir el primer período extra (fase 3). El camino de carga directa lo toma de un
  checkbox "se jugó prórroga" en `ModalResultadoDirecto` (fase 2, §11).
- **Quién escribe `Metodo_Desempate='Tiempo_Extra'` en fase 2:** el camino de carga
  directa, cuando el checkbox está marcado **y** el marcador final NO está empatado.
  Sin esta regla, un `2-1 a.e.t.` cargado a mano quedaría con `Hubo_Tiempo_Extra=TRUE`
  y `Metodo_Desempate=NULL` — una celda indefinida en la matriz de render de §11, y
  una fila que dice a la vez "se jugó prórroga" y "el tiempo regular ya tenía ganador".

### 5. D3 — `Ganador_Desempate_ID` se mantiene; el CÓMO se suma al lado

**Cinco** columnas nuevas en `PARTIDOS` (eran tres en la redacción original; E2 y E3
suman dos más):

| Columna | Tipo | Significado | Fase |
|---|---|---|---|
| `Metodo_Desempate` | `VARCHAR(20)` NULL | Qué TERMINÓ resolviendo un empate de tiempo regular: `'Tiempo_Extra'`, `'Penales'`, `'Manual'`. NULL = el tiempo regular ya tenía ganador | 2 |
| `Penales_Local` | `INT` NULL | Goles de la tanda del equipo LOCAL de este partido | 2 |
| `Penales_Visitante` | `INT` NULL | Ídem visitante | 2 |
| `Hubo_Tiempo_Extra` | `BOOLEAN NOT NULL DEFAULT FALSE` | Si se jugó prórroga, **independientemente de qué terminó decidiendo** (E2) | 2 |
| `Metodo_Desempate_Aplicable` | `VARCHAR(20)` NULL | Qué regla regía cuando ESTE partido empezó (E3, §8) | 2 |

`Hubo_Tiempo_Extra` existe porque sin él una final 2-2 con prórroga y tanda 4-2 y una
final 2-2 que fue directo a penales guardan **exactamente lo mismo** — el mismo colapso
que §0 condena, reintroducido una dimensión más allá. Con él, el acta dice
"2-2 a.e.t. (4-2 pen.)". No es derivable de `HITOS_PARTIDO`: el camino de carga directa
escribe `Inicio_Partido` y `Fin_Partido` (`partido.py:223, 294`) pero **ningún hito de
período**, que es la razón real por la que no se puede inferir.

Reglas, **todas dentro de la función existente
`fn_validar_partido_eliminacion_desempate`** (`06_triggers.sql:742`) —
~~un trigger nuevo `fn_validar_metodo_desempate`~~ queda descartado por D-A2 —
no confiadas al cliente:

- `Metodo_Desempate='Tiempo_Extra'` ⇒ `Penales_Local/Visitante` NULL **y**
  `Ganador_Desempate_ID` NULL. El alargue desempató con goles: el marcador ya
  decide, `fn_marcador_partido` nunca llega al `ELSE v_ganador_desempate`. La
  columna solo etiqueta "esto se definió en el alargue" para el acta y el portal.
- `Metodo_Desempate='Penales'` ⇒ ambos `Penales_*` NOT NULL, distintos entre sí,
  `>= 0`, **y** `Ganador_Desempate_ID` = el equipo con más penales. No se acepta
  un `Ganador_Desempate_ID` que contradiga la tanda: eso convierte el dato nuevo
  en una segunda fuente de verdad, que es el anti-patrón que el plan de llaves ya
  nombró (`PARTIDOS.Fase` texto vs `Fase_ID`).
- `Metodo_Desempate='Manual'` ⇒ `Penales_*` NULL, `Ganador_Desempate_ID` NOT NULL.
  Es el camino de hoy: `Corrido`, cierre forzado, decisión arbitral.
- `Ganador_Desempate_ID NOT NULL` ⇒ `Metodo_Desempate NOT NULL`. Cierra la puerta
  a seguir grabando desempates ciegos.
  **⚠ Esta regla rompe los tres caminos que hoy escriben `ganador_desempate_id` si
  no se los actualiza en la MISMA migración.** Son:
  `hito_partido.py:384-391` (el radio en vivo de `Cronometro.tsx:397`),
  `hito_partido.py:454-455` (`_registrar_fin_forzado`),
  `partido.py:283-291` (resultado directo), más el `PATCH` genérico vía
  `PartidoUpdate.ganador_desempate_id` (`schemas/partido.py:164`). Ninguno sabe
  escribir `Metodo_Desempate`, así que el día que entra la migración 33 **todo
  cierre Manual empieza a fallar con `desempate_sin_metodo`** — justo el camino que
  §9 promete "sin cambios visibles". Los cuatro escriben `Metodo_Desempate='Manual'`
  junto al ganador, en fase 2, y `PartidoUpdate` acepta `metodo_desempate` con
  default `'Manual'` cuando llega un `ganador_desempate_id` suelto. Ver §13.
- **`Metodo_Desempate='Tiempo_Extra'` ⇒ `Hubo_Tiempo_Extra = TRUE`** (séptima regla,
  agregada por el spec review). Sin ella el par `('Tiempo_Extra', FALSE)` es
  representable, que es exactamente la segunda fuente de verdad que §0 invoca contra
  `Fase`/`Fase_ID`. Las dos columnas son ortogonales en el sentido de que
  `('Penales', TRUE)` y `('Penales', FALSE)` son ambos válidos y distintos — pero la
  implicación en un sentido existe y se enforcea.
- En una llave `Ida_Vuelta`/`Mixto`, estas columnas solo se escriben en la
  **VUELTA** (la que carga `Partido_Ida_ID`), nunca en la ida — mismo criterio
  que ya usa `Ganador_Desempate_ID`. Un intento de escribirlas en una ida se
  rechaza con `desempate_en_ida_no_permitido`.
- Los penales **no** entran al global de la llave: `fn_resolver_llave` no se toca.
  Una vuelta 0-0 sobre ida 1-1 con tanda 4-2 propaga al ganador vía
  `Ganador_Desempate_ID`, que es lo que ya hace. `Penales_*` es marcador de tanda,
  no gol.

**Dónde va cada regla dentro de la función (D-A2, precisado por el spec review).**
`fn_validar_partido_eliminacion_desempate` tiene **cuatro** salidas tempranas antes de
la lógica de empate, verificadas línea por línea: no es una transición a `Finalizado`
(`:753`), `Fase_ID IS NULL OR Es_Walkover` (`:771`), fase no-`Eliminacion` (`:776`), y
`v_es_ida` (`:781`). Una regla puesta después de una salida que la precede **nunca
dispara**. Por eso:

- Las reglas de forma/rango/coherencia (`Penales_*` NOT NULL juntos, distintos,
  0..99, ganador consistente con la tanda, `Tiempo_Extra ⇒ Hubo_Tiempo_Extra`,
  `Ganador_Desempate_ID ⇒ Metodo_Desempate`) van **inmediatamente después del gate de
  estado (`:753`) y ANTES del bloque de la ida con `FOR UPDATE` (`:756`)**.
  Ese es el único lugar que cumple lo que dicen ser — intrínsecas a la FILA — porque
  cualquier posición posterior las deja fuera para `Fase_ID IS NULL` y **para los
  walkovers**, que es justo una fila donde un `Penales_*` colgado es plausible y
  absurdo. Como bonus, quedan fuera del camino de locking.
- `desempate_en_ida_no_permitido` va **antes de `:781`** — tiene que disparar
  justamente en el camino de la ida.
- **Carve-out explícito para la salida `OLD.Estado = 'Finalizado'` (`:753`):** hoy
  la función es inerte para un `UPDATE` sobre una fila ya finalizada, así que un
  `PATCH` directo escribiendo `Penales_*` sobre un partido cerrado esquivaría todas
  las reglas nuevas. El gate deja entrar también los UPDATEs que tocan cualquiera de
  las cinco columnas nuevas — pero ese camino corre **solo las reglas de forma/rango/
  coherencia y después `RETURN NEW`**. No sigue al resto del cuerpo: volver a tomar el
  `SELECT … FOR UPDATE` de la ida (`:762`) y a llamar `fn_resolver_llave` (`:783`) en
  cada `PATCH` de un partido ya cerrado cambiaría un bypass por una re-resolución con
  lock de llaves ya resueltas.

`Ganador_Corrido_ID` no se toca en absoluto.

**Deshacer un cierre forzado limpia el desempate.** `deshacer_fin_forzado`
(`hito_partido.py:471-545`) borra el hito, revierte la propagación y recalcula
`Estado` (`:540-541`) — pero **hoy no limpia `Ganador_Desempate_ID`**, y con este plan
tampoco limpiaría las cinco columnas nuevas. Un partido deshecho volvería a
`En curso` arrastrando `Metodo_Desempate='Penales'` y una tanda 4-2 que ya no decidió
nada. Fase 2 agrega: deshacer pone a NULL `Metodo_Desempate`, `Penales_Local`,
`Penales_Visitante` y `Ganador_Desempate_ID`, y `Hubo_Tiempo_Extra` a `FALSE`.

### 6. D4 — Aplica a `Unico`, `Ida_Vuelta` y `Mixto`

- **`Unico`** (y Tercer Lugar, que siempre es único): empate al cerrar el último
  período regular ⇒ alargue o penales según D1.
- **`Ida_Vuelta`/`Mixto`**: la IDA **nunca** va a alargue ni a penales — una ida
  empatada es un resultado legal y ya está así en
  `fn_validar_partido_eliminacion_desempate:780` (`IF v_es_ida THEN RETURN NEW`).
  Solo la VUELTA, y el disparador
  es el **GLOBAL** empatado al cerrar su último período regular, no su marcador
  suelto. Una vuelta 0-0 sobre una ida 2-1 no va a ningún lado; una vuelta 2-1
  sobre una ida 1-2 sí (global 3-3).
- Corolario útil y gratis: si el global se rompe **durante** el alargue de la
  vuelta, `fn_resolver_llave` lo ve al instante porque suma
  `vw_goles_acreditados` de las dos piernas sin importar en qué período cayó el
  gol. No hay que enseñarle nada nuevo a esa función.
- Regla de gol de visitante: sigue **fuera de scope**, igual que en el plan de
  llaves. Se repite acá para que no se cuele.

### 7. D5 — Solo disciplinas de gol (`Tipo_Cronometro='Periodos'`)

Un torneo `Corrido` (Tenis, Ajedrez, Pádel, LoL) no tiene "tiempo extra" ni
"penales" en este sentido: su empate se resuelve con `Ganador_Corrido_ID` por
partido, y una llave 1-1 en victorias de pierna cae a `Ganador_Desempate_ID`.

- `TORNEO.Metodo_Desempate_Eliminatoria` queda forzado a `'Manual'` cuando
  `CONFIGURACION_TIEMPO_TORNEO.Tipo_Cronometro='Corrido'`. **Dos guardas, y ninguna
  es el trigger de §5** (ese es `BEFORE UPDATE ON PARTIDOS` y solo corre al
  finalizar un partido — no puede validar una fila de `TORNEO` al configurarla, y
  un CHECK de tabla tampoco, porque `Tipo_Cronometro` vive en otra tabla):
  1. **`TorneoService`** — mismo patrón que `Ida_Vuelta` solo para `Formato='Liga'`.
     Hay que agregar `metodo_desempate_eliminatoria` a la tupla de payload de
     `backend/app/services/torneo.py:302`, o la revalidación en update no corre.
     Este camino cubre el **INSERT**, que el trigger no puede cubrir (abajo).
  2. **Un trigger sobre `TORNEO`**, extendiendo `fn_validar_torneo_modalidad`
     (`06_triggers.sql:331`), que ya cruza `TORNEO` contra otra tabla. **Extender la
     función NO alcanza:** el trigger está acotado por columna —
     `BEFORE INSERT OR UPDATE OF Disciplina_ID, Modalidad_ID ON TORNEO`
     (`:349-350`) — así que hay que **agregar `Metodo_Desempate_Eliminatoria` a la
     lista `UPDATE OF`** o el guard nunca corre.

  Dos huecos que el guard NO cubre, dichos en vez de omitidos:
  - **El INSERT es estructuralmente inguardable desde el trigger.**
    `CONFIGURACION_TIEMPO_TORNEO` tiene FK a `TORNEO`, así que en
    `BEFORE INSERT ON TORNEO` la fila de config todavía no existe y `Tipo_Cronometro`
    lee NULL. El INSERT lo cubre `TorneoService.create`, guarda 1.
  - **La dirección inversa** (pasar `Tipo_Cronometro` a `'Corrido'` en un torneo ya
    puesto en `Penales_Directo`) se resuelve **en Python**, no con un segundo trigger
    cruzado. Es la regla de la casa, escrita en este mismo archivo
    (`06_triggers.sql:360-366`) para un caso de la misma forma: *"no un segundo
    trigger cruzando en la direccion opuesta"*. `ConfiguracionTiempoTorneoService`
    baja el método a `'Manual'` al pasar el torneo a `Corrido`.
- `PasoGenerarPlayoffs` no muestra el selector de método cuando el torneo es
  `Corrido`: no lo deshabilita con un tooltip, lo omite. Un control que nunca se
  puede usar es ruido.

### 8. D6 — Editable hasta que el partido EMPIEZA, no hasta que "se juega"

~~"Se lee recién cuando una llave empatada se está por cerrar … editable hasta que
esa llave se juegue."~~ **Corregido por E3/D-C6: eso trata un partido como un
instante, y es un intervalo** — que es justamente el supuesto sobre el que está
construido todo §4. Contraejemplo concreto: partido en curso, empatado, jugando el
1er tiempo extra; el admin abre configuración y cambia a `Penales_Directo`; el
período abierto queda retroactivamente fuera de rango contra el mismo
`fn_validar_hito_partido` que este plan está extendiendo.

Regla final:

- `PARTIDOS.Metodo_Desempate_Aplicable` se **snapshotea desde la regla del torneo en
  el momento en que el partido arranca**: en el hito `Inicio_Partido`
  (`hito_partido.py:357`) para el camino en vivo, y al guardar el resultado directo
  para el otro camino. Resuelve la ronda (`Ronda_Nombre='Final'` o no) en ese mismo
  momento, así que guarda el método CONCRETO que le toca a este partido, no la regla
  del cuadro.
- **Se snapshotea SOLO en partidos de fase `Eliminacion`.** En cualquier otro partido
  queda NULL, y ese NULL es lo que le dice a `_periodos_totales_permitidos` (§4) que
  no es un partido de eliminación — por eso el helper no necesita recibir la fase.
- **Su dominio es más angosto que el de la columna del torneo:**
  `CHECK (Metodo_Desempate_Aplicable IN ('Manual','Penales_Directo','Tiempo_Extra_Penales'))`.
  `'Penales_Salvo_Final'` es una regla de CUADRO, no un método: al snapshotear ya se
  resolvió a uno de los tres concretos, así que almacenarlo acá sería guardar la
  pregunta en vez de la respuesta.
- Respuesta a "¿se puede cambiar después de generar el cuadro?": **sí, hasta que ese
  partido empiece.** Después, no — y no por una prohibición, sino porque la regla que
  regía ya está grabada en la fila. Los partidos que todavía no arrancaron toman la
  regla nueva; los que ya arrancaron o terminaron conservan la suya.
- **Punto de edición: SOLO el selector de `PasoGenerarPlayoffs`.**
  ~~"más una entrada en la pantalla de configuración del torneo"~~ — **eliminado por
  C7.** Verificado: `formato_eliminatoria`, el campo hermano con el que §3 reclama
  paridad, **no es editable en ningún lado** — `TorneosAdmin.tsx:437-442` expone solo
  `incluye_tercer_lugar` y `clasificados_por_grupo`, y `TorneoUpdate`
  (`backend/app/schemas/torneo.py:145`) no lo incluye. Darle al campo nuevo una
  superficie de edición que su hermano no tiene contradice la propia justificación de
  §3. Volver editables a los dos queda diferido a TODOS.md.
- Cambiar el método con llaves ya resueltas por el método anterior es legal y no
  reescribe historia. La UI lo dice en una línea: "Las llaves ya cerradas
  conservan cómo se resolvieron."

### 9. Recorrido del operador (el que importa)

**Partido único, 1-1 al cerrar el 2do tiempo, método `Tiempo_Extra_Penales`:**
el servidor manda `Inicio_Periodo` **y** `Fin_Partido` en `acciones_permitidas` — las
dos quedan permitidas a propósito (`Fin_Partido` es el escape de D-A1). La UI promueve
"**Ir a tiempo extra**" como acción primaria y deja "Finalizar" como secundaria; no
esconde ninguna de las dos. Arranca el 1er Tiempo Extra, se
cargan goles como siempre. Si termina 2-1, el partido cierra normal y queda
`Metodo_Desempate='Tiempo_Extra'`. Si termina 1-1, al cerrar el 2do Tiempo Extra
el botón dice "Ir a penales" y se abre el marcador de tanda (dos steppers, no un
radio) — al confirmar se graba `Metodo_Desempate='Penales'`,
`Penales_Local/Visitante` y el `Ganador_Desempate_ID` derivado.

**Mismo partido, método `Penales_Directo`:** al cerrar el 2do tiempo el botón ya
dice "Ir a penales". Sin período extra.

**Método `Manual`:** el radio "¿quién avanza?" de hoy, sin cambios visibles.

**Vuelta de una llave:** idéntico, pero el encabezado muestra el GLOBAL
("Global 3-3") en vez del marcador suelto, porque es lo que está en juego.

### 10. Backend — dónde caen los cambios, POR FASE

**Fase 1 — sin migración.** `requiere_desempate` se calcula en el servidor.
- `backend/app/services/hito_partido.py` + `backend/app/schemas/partido.py` — un
  campo nuevo en la respuesta, calculado una sola vez y bien (ida vs vuelta vs
  partido único, agregado real de la llave).
- El cálculo debe reproducir la forma **más estricta** de las dos derivaciones que
  reemplaza: `MesaPanel.tsx:290` es `ronda_nombre != null && empatado`, pero
  `ModalResultadoDirecto.tsx:420` es `esEliminacion && !esCorrido && marcadorEmpatado`
  — el modal excluye `Corrido` y el panel no. El campo del servidor excluye `Corrido`.

**Fase 2 — `database/33_migracion_metodo_desempate.sql`.**
- `database/01_schema.sql` — **5** columnas en `PARTIDOS` (§5), 1 en `TORNEO`.
- `database/02_constraints.sql` — CHECKs de dominio: `Metodo_Desempate`,
  `Metodo_Desempate_Aplicable`, `Metodo_Desempate_Eliminatoria`, y
  `Penales_Local/Visitante BETWEEN 0 AND 99` (D-S1: no basta con `>= 0`, un entero
  del cliente no entra sin techo al acta).
- `database/06_triggers.sql` — reglas de coherencia **dentro de
  `fn_validar_partido_eliminacion_desempate`** (§5, con sus puntos de inserción); y
  el chequeo `Corrido ⇒ Manual` extendiendo `fn_validar_torneo_modalidad` (§7).
  `fn_marcador_partido` y `fn_resolver_llave` **sin cambios** (§4, §6).
- `backend/app/models/partido.py`, `torneo.py`; `backend/app/schemas/partido.py`,
  `torneo.py`.
- `backend/app/services/partido.py` — resultado directo con tanda, `Hubo_Tiempo_Extra`
  y el snapshot de `Metodo_Desempate_Aplicable`.
- `backend/app/services/hito_partido.py` — snapshot en `Inicio_Partido` (`:357`);
  limpieza de las 5 columnas en `deshacer_fin_forzado` (§5).
- `backend/app/services/motor_formatos.py` — `generar_playoffs` y `sortear`
  persisten `metodo_desempate_eliminatoria` igual que ya persisten
  `formato_eliminatoria` (`:628-629`).

**Fase 3 — `database/34_migracion_tiempo_extra_periodos.sql`.**
- 2 columnas NULLABLE en `CONFIGURACION_TIEMPO_TORNEO` + extensión de
  `chk_config_tiempo_periodos` (§4).
- `fn_validar_hito_partido` — tope flojo (§4).
- `backend/app/services/hito_partido.py` — `_periodos_totales_permitidos`,
  `Fin_Partido` con `>=`, los 3 llamadores de `_calcular_estado`.
- Habilita los valores `'Tiempo_Extra_Penales'` y `'Penales_Salvo_Final'` en la UI.

**La regla de las 3 ubicaciones vale POR FASE**, no globalmente: `01_schema.sql` + la
migración DE ESA FASE + `SCRIPTS_VIGENTES` en `test_scripts_sql.py:36-48`.
`conftest.py` arma la base de tests solo con `01..06_*.sql` y nunca corre los `07+`,
así que una columna que solo exista en la migración revienta todos los tests con
`UndefinedColumn`. Esto restringe columnas *dentro* de una fase — no impide fasear.

### 11. Frontend — dónde caen los cambios

**Fase 1**
- `MesaPanel.tsx:290` y `ModalResultadoDirecto.tsx:420`: dejan de derivar
  `requiereDesempate` en el cliente y consumen el campo del servidor (arregla el
  bug de ida/vuelta de §1). Las dos derivaciones se borran, no se parchean.

**Fase 2**

- `ModalSiguienteFase.tsx` → `PasoGenerarPlayoffs`: radios de método debajo de los
  de formato, **omitidos** (no deshabilitados) si el torneo es `Corrido`. Los dos
  grupos de radios llevan **encabezado propio y separación visual** — sin eso el
  operador ve seis radios en una columna: "Formato de los cruces" y "Si un cruce
  termina empatado". Etiquetas de fase 2:
  - `'Manual'` → **"Lo decido yo al cerrar el partido"** (no la palabra "Manual",
    que es vocabulario de desarrollador).
  - `'Penales_Directo'` → **"Penales, sin prórroga"**.
  *Los valores con prórroga llegan en fase 3, con las columnas que los sostienen.*
- **`Cronometro.tsx`: el paso de tanda de penales entra en FASE 2, no en fase 3.**
  Corrección del review de diseño (D-D1), y no es cosmética: el paso de tanda no
  necesita ninguna columna más allá de las cinco que fase 2 ya trae
  (`Metodo_Desempate` + `Penales_*`) — solo los períodos extra necesitan la
  migración 34. Dejarlo en fase 3 significaba que un operador configuraba
  `Penales_Directo`, llegaba 1-1 al final del 2do tiempo **en el cronómetro en
  vivo**, y recibía el radio viejo. Eso es exactamente el fallo que S6 evita, una
  ruta más allá — y además **envenena las métricas**: cada cierre en vivo de fase 2
  dispararía `desempate_manual_sobre_metodo_configurado` (métrica 3, cuyo
  significado declarado es "el flujo en vivo no se parece a la realidad de la
  cancha") por culpa del faseado, no de los operadores; y la métrica 4 (split vivo
  vs carga directa), que es **el gate de fase 3**, mediría una preferencia que el
  propio faseado fabricó. El gate se auto-cumpliría en la dirección de no construir
  nunca §4.
- `ModalResultadoDirecto.tsx`: steppers de tanda + checkbox "se jugó prórroga"
  (escribe `Hubo_Tiempo_Extra`) + la salida **"no tengo el marcador de la tanda"**
  que cae a `Metodo_Desempate='Manual'` con `Penales_*` en NULL (E4).
- **Superficie de edición del método** (resuelve la contradicción entre C7 y §8):
  `metodo_desempate_eliminatoria` **y** `formato_eliminatoria` se vuelven editables
  en `TorneoUpdate` + `TorneosAdmin.tsx`. C7 tenía razón en que el campo nuevo no
  debe tener una superficie que su hermano no tiene; la salida correcta es darles la
  superficie **a los dos**, no quitársela al nuevo — porque sin ella §8 promete una
  ventana de edición ("hasta que el partido empieza") que en el producto real está
  vacía: `PasoGenerarPlayoffs` corre antes de que exista ningún partido de
  eliminación. Promueve E8 de TODOS a scope.
- Superficies públicas — `BracketView.tsx`, `PartidosDelTorneo.tsx`,
  `DetalleTorneoPublico.tsx`. **Este es el payoff del plan**: lo que ve el jugador,
  la familia y el grupo de WhatsApp.

#### Matriz de render (las 8 celdas, no "según")

`Metodo_Desempate` × `Hubo_Tiempo_Extra` tiene ocho celdas y el borrador
especificaba tres. Las cinco que faltaban incluyen **el default de todo torneo que
existe hoy**. Spec completa, es el contrato de tres componentes:

| `Metodo_Desempate` | `Hubo_Tiempo_Extra` | Render | Nota |
|---|---|---|---|
| NULL | FALSE | `2-1` | Sin empate que resolver. El caso normal. |
| NULL | TRUE | — | **Imposible**: el trigger lo rechaza (F9). |
| `'Tiempo_Extra'` | TRUE | `2-1 a.e.t.` | Lo definió un gol del alargue. |
| `'Tiempo_Extra'` | FALSE | — | **Imposible**: séptima regla de coherencia (S3). |
| `'Penales'` | FALSE | `2-2 (4-2 pen.)` | Penales directos, sin prórroga. |
| `'Penales'` | TRUE | `2-2 a.e.t. (4-2 pen.)` | Prórroga y después tanda. |
| `'Manual'` | FALSE | `2-2 (def.)` | **El default de todo torneo existente**, la salida E4, todo cierre forzado, toda llave `Corrido`. `title`/`aria-label`: "Definido por decisión — sin marcador de tanda". |
| `'Manual'` | TRUE | `2-2 a.e.t. (def.)` | Se jugó prórroga y se resolvió a dedo. |

Sin la fila `('Manual', FALSE)` el bracket muestra `2-2` con un equipo avanzando y
ninguna explicación — **el mismo colapso de información que §0 condena, shipeado
como render por defecto.**

Por superficie:
- **`BracketView`**: muestra el **GLOBAL** de la llave (no el marcador de la
  pierna) más un badge compacto `pen. 4-2` de peso secundario, que **nunca envuelve**
  — el nodo está dimensionado para `2-2`, y `2-2 a.e.t. (4-2 pen.)` son ~20
  caracteres más. Que el bracket muestra el global se dice explícito: hoy es
  indefinido y `Penales_*` vive en la vuelta.
- **`PartidosDelTorneo`**: string completo inline en la fila.
- **`DetalleTorneoPublico`**: string completo + una línea en prosa — "Definido en
  penales 4-2 tras 2-2 en el tiempo extra".

#### El chip de regla vigente (20 líneas, el mejor ratio del plan)

En la cabecera de mesa/cronómetro de todo partido de `Eliminacion`, una línea
persistente con la regla que rige ESTE partido (`Metodo_Desempate_Aplicable`):
**"Empate → tiempo extra"** / **"Empate → penales"** / **"Empate → lo decidís vos"**.
En una vuelta suma el global: **"Global 3-3 — si termina así, penales"**.
Sin esto el operador no tiene forma de saber qué pasa al final del partido hasta que
un botón le cambia de texto en el minuto 90. Convierte una sorpresa en un plan.

#### Tanda de penales: etiquetas, validación y confirmación

- **Los steppers se etiquetan con NOMBRE DE EQUIPO, nunca "Local"/"Visitante".**
  Riesgo concreto y silencioso: `Penales_Local` es del local **de este partido**,
  pero la cabecera de una vuelta muestra el GLOBAL, que cruza localía
  (`fn_resolver_llave` invierte la ida). Un 4-2 cargado al revés escribe el
  `Ganador_Desempate_ID` del equipo equivocado, **pasa todas las reglas del
  trigger** y avanza al equipo equivocado en el cuadro.
- El paso de confirmación **reformula el resultado en palabras antes de escribir**:
  "Penales 4-2 — avanza Deportivo Norte".
- Validación en el cliente, no solo en el trigger: min 0, max 30 (el CHECK es 0..99
  como red), ambos arrancan en 0, confirmar deshabilitado mientras estén **iguales**
  o ambos en 0, mensaje inline al empatar, sin entrada de texto libre.
- Estado pendiente: los botones de acción se deshabilitan al enviar hasta el
  siguiente fetch exitoso, y el poll de 5s (`Cronometro.tsx:6`) no pisa estado local
  pendiente. Un doble toque en un teléfono en la cancha es un `Inicio_Periodo`
  duplicado plausible.
- **Éxito**: la tarjeta del partido deja una línea persistente "Penales 4-2 · avanza
  X" — no un toast. Es la acción de mayor ceremonia de la feature.
- **Deshacer**: la confirmación nombra lo que se pierde — "Se va a borrar la tanda de
  penales 4-2 y el equipo que avanzaba" (§5 hace que deshacer limpie las 5 columnas).

#### "Finalizar" al final del tiempo regular (la salida D-A1)

Las dos acciones quedan permitidas (§9). "Ir a tiempo extra" es primaria;
"Finalizar" es secundaria **y no cierra directo**: abre una hoja de confirmación —
título "Cerrar sin jugar el alargue", cuerpo "Este torneo define por tiempo extra.
Si cerrás acá, elegís vos quién avanza y queda registrado así.", después el radio
manual, después un confirmar de estilo destructivo. Sin esa fricción el escape es el
camino de menor resistencia y la métrica 3 no mide nada.

#### Divulgación progresiva en `ModalResultadoDirecto`

El modal ya tiene marcador, eventos y el radio manual; fase 2 le suma tres
controles. No se apilan: el bloque de desempate **aparece solo cuando
`requiere_desempate` (el campo de servidor de fase 1) es true**; el checkbox de
prórroga solo en partidos de `Eliminacion`; y "no tengo el marcador" es un link de
texto **debajo** de los steppers, no una opción par. Si no, un resultado de fase de
grupos pasa a ser un formulario que hay que escanear entero cada vez.

#### Copy de errores (9 códigos nuevos, 0 strings en el borrador)

| Código | Qué ve el operador | Dónde |
|---|---|---|
| `tanda_penales_empatada` | "Una tanda de penales no puede terminar empatada." | inline bajo los steppers |
| `tanda_penales_fuera_de_rango` | "Marcador de tanda inválido." | inline bajo los steppers |
| `ganador_desempate_contradice_tanda` | "El ganador no coincide con el marcador de la tanda." | inline |
| `metodo_desempate_incoherente` | "El método y el marcador de la tanda no coinciden." | toast |
| `desempate_sin_metodo` | "Falta indicar cómo se resolvió el empate." | toast |
| `desempate_en_ida_no_permitido` | "El desempate se registra en la vuelta, no en la ida." | toast |
| `llave_empatada_en_global_sin_desempate` | "La llave está empatada en el global — hay que resolverla para avanzar." | toast |
| `penales_no_aplican_a_corrido` | "Este torneo no usa penales." | toast |
| `partido_vuelta_ida_sin_resolver` | "Falta cerrar el partido de ida antes de la vuelta." | toast |

Hoy el operador ya come `llave_empatada_en_global_sin_desempate` como un fallo
crudo de servidor (§1 lo nombra como bug). El plan arregla la CAUSA de ese código y
agrega ocho más — sin copy, todos salen como código crudo en un toast.

**Fase 3**
- `Cronometro.tsx`: la máquina de estados suma los períodos extra ("1er/2do Tiempo
  Extra"). El paso de tanda ya existe desde fase 2.
- `PasoGenerarPlayoffs`: se habilitan `'Tiempo_Extra_Penales'` y
  `'Penales_Salvo_Final'`, con subtítulos que citan duraciones reales. La línea de
  estimación existente ("N partidos · la final cae aprox. el …") **se extiende con el
  techo de prórroga**: §3 justifica `Penales_Salvo_Final` con "torneos amateur con
  cancha alquilada por hora", y un cuadro `Tiempo_Extra_Penales` puede sumar 30
  minutos por cruce empatado a ese alquiler. La única pantalla que estima duración no
  puede quedarse callada al respecto.
- Al abrir `PasoGenerarPlayoffs` por primera vez después del upgrade, una nota
  descartable nombra las dos opciones nuevas — si no, los torneos configurados en
  fase 2 se quedan en `Penales_Directo` sin que nadie les avise (y la superficie de
  edición de fase 2 es lo que les permite adoptarlas).

### 11-bis. Cobertura de estados de interacción

| Control | LOADING | EMPTY | ERROR | SUCCESS | PARTIAL |
|---|---|---|---|---|---|
| Selector de método (generación) | n/a | n/a | inline bajo el grupo | radio marcado + estimación recalculada | n/a |
| Chip de regla vigente | skeleton de una línea | n/a (siempre hay regla) | oculto si no se pudo leer, nunca un valor inventado | texto de regla + global | "Global pendiente" mientras no se jugó la ida |
| "Ir a tiempo extra" | botón deshabilitado + `isPending` | n/a | `apiErrorMessage` inline | se abre el período, el reloj arranca de 0 | n/a |
| "Finalizar" (salida D-A1) | deshabilitado | n/a | inline en la hoja | partido cerrado + línea "definido por decisión" | hoja abierta sin elegir equipo |
| Steppers de tanda | deshabilitados | ambos en 0 = estado inicial válido, confirmar apagado | inline bajo los steppers | línea persistente "Penales 4-2 · avanza X" | un lado cargado, confirmar apagado |
| "No tengo el marcador" | n/a | **es** el estado de dato faltante | inline | cierra como `Manual`, `Penales_*` NULL | n/a |
| Checkbox "se jugó prórroga" | n/a | desmarcado por defecto | n/a | `Hubo_Tiempo_Extra=TRUE` | n/a |
| Resultado público | skeleton | — | — | string de la matriz de §11 | "IDA 1-1 · VTA pend." (ya existe) |

Accesibilidad, dicho o no existe: los steppers son `<input type="number">` con
`<label>` visible (nombre de equipo), no placeholder-as-label; el badge `pen. 4-2`
del bracket lleva `aria-label` completo ("Penales 4 a 2"); `(def.)` lleva `title` y
`aria-label` explicando qué significa; la hoja de "Cerrar sin jugar el alargue" es
un diálogo con foco atrapado y `Esc` para cancelar (el repo ya tiene
`useModalFocusTrap`); los targets táctiles de los steppers son de 44px mínimo — se
usan en una cancha, con una mano, a veces con lluvia.

### 12. Fuera de scope (dicho, no omitido)

- Desempate por llave individual (§3).
- Regla de gol de visitante (§6).
- Tanda de penales gol a gol (quién pateó, quién atajó): solo el marcador de la
  tanda. Un registro tirador por tirador es otro plan.
- Alargue/penales en fase de Grupos o Liga: no existe el concepto ahí.
- Muerte súbita / gol de oro dentro del alargue.

### 12-bis. Métricas de adopción

Sin esto la feature puede shipear completa, correcta y testeada — y no usarla nadie,
sin que nada lo detecte. `DEFAULT 'Manual'` significa que todo torneo existente se
queda en el comportamiento de hoy en silencio.

Las **formas** se fijan acá; las **queries** son el primer commit de fase 2 (métrica 2
necesita el agregado de dos piernas sobre `vw_goles_acreditados`, no es una línea):

| # | Métrica | Para qué |
|---|---|---|
| 1 | % de torneos `Eliminacion` con método distinto de `'Manual'`, a 30 días | ¿alguien la está usando? |
| 2 | % de llaves empatadas cerradas que traen marcador de tanda | ¿el dato nuevo llega al acta o queda vacío? |
| 3 | Cierres `Manual` sobre torneos configurados de otra forma (tasa de escape) | si es alta, el flujo en vivo no se parece a la realidad de la cancha |
| 4 | Split cronómetro en vivo vs carga directa en cierres de `Eliminacion`, 90 días | **gate de fase 3.** Si domina la carga directa, se reconsidera la forma de §4 antes de construirla |

Las cuatro corren contra la base de desarrollo **antes** de que el resto de fase 2
mergee. La 4 se corre **antes de agendar fase 3**.

### 13. Verificación

**Fase 1**
- `requiere_desempate`: vuelta con global empatado ⇒ true; **ida empatada ⇒ false**
  (hoy devuelve true, ese es el bug); partido único empatado ⇒ true; torneo
  `Corrido` ⇒ false; pierna con walkover ⇒ false.

**Fase 2**
- Trigger: partido único empatado con cada método; penales con ganador
  contradictorio ⇒ rechazado; tanda empatada ⇒ rechazada; `Penales_*` en `-1`/`100`
  ⇒ rechazado; `Metodo_Desempate` en una ida ⇒ rechazado;
  `('Tiempo_Extra', Hubo_Tiempo_Extra=FALSE)` ⇒ rechazado; `PATCH` de `Penales_*`
  sobre un partido ya `Finalizado` ⇒ validado igual (carve-out de §5).
- `deshacer_fin_forzado` sobre un cierre con tanda: deja las 5 columnas limpias.
- **Regresión obligatoria: el radio Manual de hoy sigue funcionando post-migración
  33.** Los cuatro escritores (`hito_partido.py:391`, `:455`, `partido.py:291`,
  `PATCH` vía `PartidoUpdate`) cierran un empate sin explotar con
  `desempate_sin_metodo`. Sin este test, el día 1 de fase 2 se rompe el único camino
  de desempate que existe hoy.
- Carga directa con "no tengo el marcador" ⇒ `Manual`, `Penales_*` NULL.
- Carga directa `2-1` con "se jugó prórroga" ⇒ `Metodo_Desempate='Tiempo_Extra'`,
  `Hubo_Tiempo_Extra=TRUE`, y el portal muestra "2-1 a.e.t.".
- Cierre `Manual` en un torneo configurado de otra forma ⇒ permitido, **y logueado**.
- `PATCH` de `Penales_*` sobre un walkover ⇒ rechazado (las reglas de forma corren
  antes de la salida por `Es_Walkover`).
- Las 4 queries de métricas (§12-bis) existen y corren contra la base de desarrollo.
- `Corrido` + método distinto de `Manual` ⇒ `DomainRuleError` en el servicio Y en el
  trigger de `TORNEO`.
- Migración 33 idempotente corrida dos veces (`test_scripts_sql.py`).

**Fase 3**
- `_periodos_totales_permitidos`: no ofrece período extra si la llave no está
  empatada, ni con `Penales_Directo`, ni en `Corrido`.
- **`_calcular_estado`, el caso que la redacción original rompía:** gol en el 1er
  tiempo extra ⇒ el 2do tiempo extra **sigue ofreciéndose**, y el partido **se puede
  cerrar** después de cerrarlo. Sin esta prueba el defecto vuelve.
- `fn_resolver_llave` con gol de alargue en la vuelta que rompe el global ⇒ resuelve
  sin desempate, sin tocar la función.
- `'Penales_Salvo_Final'`: Final ⇒ prórroga; Semifinal ⇒ penales; **Tercer Lugar ⇒
  penales** (no prórroga, pese a `es_final=True` en `motor_formatos.py:513`).
- Fila `Corrido` con `Cantidad_Periodos_Extra=2` ⇒ rechazada por
  `chk_config_tiempo_periodos`; fila `Periodos` con las dos en NULL ⇒ aceptada.
- Migración 34 corre contra filas existentes sin fallar, y es idempotente dos veces.
- `UPDATE TORNEO SET Metodo_Desempate_Eliminatoria='Penales_Directo'` en un torneo
  `Corrido` ⇒ rechazado **por el trigger** (prueba de que la columna quedó en la
  lista `UPDATE OF`, no solo en el cuerpo de la función).

**Todas las fases:** `npm run verify`; cada migración corrida antes con
`psql -1` contra `torneos_mvp` local — el pitfall registrado del proyecto es
exactamente una migración escrita y nunca corrida.



<!-- autoplan-accepted:ceo -->
- Approach C: three sequenced landings. Phase 1 = server-side `requiere_desempate` alone (fixes the live ida/vuelta bug, no migration). Phase 2 = method + shootout + record + public display (migration 33). Phase 3 = extra time as real clocked periods (migration 34), scheduled only after metric 4 is run. Verify: each phase ships and reverts independently; `git revert` of any phase leaves its columns inert.
- E1/C1: add `'Penales_Salvo_Final'` to `TORNEO.Metodo_Desempate_Eliminatoria`, keyed on `PARTIDOS.Ronda_Nombre = 'Final'`. Tercer Lugar resolves on the penalties side. The "no real competition varies by round" premise is struck; `_piernas_por_ronda` (`motor_formatos.py:71`) is cited as the in-repo precedent. Verify: test #9.
- E2/C2: add `PARTIDOS.Hubo_Tiempo_Extra BOOLEAN NOT NULL DEFAULT FALSE`, orthogonal to `Metodo_Desempate`. Public record renders "2-2 a.e.t. (4-2 pen.)". Not derived from `HITOS_PARTIDO` — the direct-result path writes none. Verify: a direct-result close with ET played round-trips the flag.
- E3/C6: add `PARTIDOS.Metodo_Desempate_Aplicable`, snapshotted from the tournament rule at `Inicio_Partido` (`hito_partido.py:357`) and at direct-result save. D6 is restated: the rule is editable until the match STARTS, not until it is played. Verify: test #6.
- E4/C8: the shootout UI always offers "no tengo el marcador de la tanda", falling back to `Metodo_Desempate='Manual'` with `Penales_*` NULL. The schema's answer to missing data is NULL, never a guess. Verify: test #11.
- E5/C9: three adoption metrics as SQL in the plan — (1) % of `Eliminacion` tournaments on a non-`Manual` method at 30 days, (2) % of closed tied llaves carrying a shootout score, (3) count of `Manual` closes on tournaments configured otherwise. Plus metric (4): live-timer vs direct-result close split for `Eliminacion`, 90 days. Verify: each query runs against the dev DB before phase 2 merges.
- C10: metric 4 is a **gate on scheduling phase 3**, not on the plan. If direct-result entry dominates `Eliminacion` closes, phase 3's shape is reconsidered before it is built.
- D-A1: a tied match on a non-`Manual` tournament CAN still be closed as `Manual` (direct result / paper sheet). This is deliberate, not a hole. It must be logged as `desempate_manual_sobre_metodo_configurado` and counted by metric 3. No future change may turn it into a hard rejection without re-deciding this. Verify: test #7.
- D-A2: do NOT add a second BEFORE UPDATE trigger. Fold the coherence rules into the existing `fn_validar_partido_eliminacion_desempate` (`06_triggers.sql:742`). Two reasons: Postgres fires BEFORE UPDATE triggers alphabetically (a silent ordering dependency), and the existing function already holds the `SELECT … FOR UPDATE` lock on the ida that these rules need. Supersedes §5's "trigger nuevo `fn_validar_metodo_desempate`". Verify: test #2 passes with one trigger.
- D-Q1: name the per-round value `'Penales_Salvo_Final'`, never `'Mixto'` — `Formato_Eliminatoria='Mixto'` already exists on the same row meaning something else.
- D-Q2: `requiereDesempate` is removed from BOTH `MesaPanel.tsx:290` and `ModalResultadoDirecto.tsx:420` and replaced by one server field. Root-cause fix at the shared source, not a guard per caller. Verify: test #1, including the ida-tied case that is wrong today.
- D-Q3: extract `_periodos_totales_permitidos(partido, torneo, config) -> int` rather than inlining the tope into `_calcular_estado` (which already branches 7 times). Verify: test #5.
- D-P1: compute the "is this llave tied?" aggregate ONLY when `periodo_abierto IS NULL AND ultimo_periodo_cerrado >= Cantidad_Periodos`. The cronometro endpoint is polled every 5s per live match (`Cronometro.tsx:6`); an unconditional aggregate would run per match per poll for the whole match.
- D-S1: `CHECK (Penales_Local BETWEEN 0 AND 99)` and the same for `Penales_Visitante`, plus a server-side check. Client integers are never trusted into the acta.
- D-S2: `Cantidad_Periodos_Extra` / `Duracion_Periodo_Extra_Minutos` ship `NOT NULL DEFAULT 2 / 15` for `Tipo_Cronometro='Periodos'` with a backfill, so `None` arithmetic in `_calcular_estado` is impossible rather than rescued.
- C7: DROP §8's promise of a tournament-settings edit surface. `formato_eliminatoria` is create-only today (`TorneosAdmin.tsx:437-442`, absent from `TorneoUpdate`); the new field follows the sibling exactly and is edited at `PasoGenerarPlayoffs` only. Making both editable is deferred to TODOS.
- D-T1: record in TODOS.md that the documented `ReglamentoTorneo` revisit trigger (`TODOS.md:561-566`, "a third reglamento field") has now FIRED — this plan adds the 4th and 5th. The refactor is NOT done here (Effort L, outside blast radius), but the next reglamento field must land on a decision already made.
- D-T2: one block comment in `01_schema.sql` mapping each of the seven "how did this end" columns (`Ganador_Desempate_ID`, `Ganador_Corrido_ID`, `Metodo_Desempate`, `Metodo_Desempate_Aplicable`, `Hubo_Tiempo_Extra`, `Penales_*`, `Es_Walkover`) to the one question it answers. Required, not optional.
- Housekeeping: annotate `docs/plans/cierre-fase-regular-llaves-playoffs-plan.md` with a forward pointer to this plan, and mark its diagrams at :941 and :1001-1043 as superseded by phase 2.
- Deployment: each phase carries its own migration number (33, 34) and the three-location column rule (`01_schema.sql` + that phase's migration + `SCRIPTS_VIGENTES` in `test_scripts_sql.py:36-48`) is satisfied PER PHASE. Each migration is run locally with `psql -1` against `torneos_mvp` before the phase lands — the recorded project pitfall is a migration written but never run.
- Rejected, with reason recorded: C3's "extra time as a label/flag without new clock periods". Without an open period the live timer has no minute to attach an ET goal to, so that option silently means "extra time is unusable from the live timer" — which is half the operator's stated ask. Surfaced at the Final Gate as a taste decision.
- SPEC-REVIEW S1 (BLOCKING defect, corrected in §4): the extra-period tope must depend on whether extra time was ENTERED (an `Inicio_Periodo` hito with `Numero_Periodo > Cantidad_Periodos` exists), never on whether the tie is currently live. With a tie-conditioned tope, a goal in the first extra period drops the tope back and `hito_partido.py:126-130` then offers NEITHER `Inicio_Periodo` (`3 < 2` false) NOR `Fin_Partido` (`3 == 2` false) — the match has zero permitted actions and can never be closed. It would also forbid playing the second half of extra time. The `Fin_Partido` condition additionally changes from `== Cantidad_Periodos` to `>= Cantidad_Periodos`. Verify: phase-3 test "goal in ET1 -> ET2 still offered, match closes after ET2".
- SPEC-REVIEW S2 (corrected in §5): `deshacer_fin_forzado` (`hito_partido.py:471-545`) does not clear `Ganador_Desempate_ID` today and would not clear the five new columns. Phase 2 makes it NULL `Metodo_Desempate`, `Penales_Local`, `Penales_Visitante`, `Ganador_Desempate_ID` and reset `Hubo_Tiempo_Extra`. Verify: undo a forced close that carried a shootout.
- SPEC-REVIEW S3 (corrected in §5): seventh coherence rule `Metodo_Desempate='Tiempo_Extra' => Hubo_Tiempo_Extra = TRUE`. Without it the pair `('Tiempo_Extra', FALSE)` is representable — the second-source-of-truth anti-pattern §0 invokes against `Fase`/`Fase_ID`.
- SPEC-REVIEW S4 (corrected in §5): state the insertion point of each new rule inside `fn_validar_partido_eliminacion_desempate`. The function has five early returns; `desempate_en_ida_no_permitido` MUST go before `:780` (`IF v_es_ida THEN RETURN NEW`) or it never fires on the ida path, and the shape/range/coherence rules go before the fase check at `:775`. Plus an explicit carve-out on the `OLD.Estado = 'Finalizado'` return (`:752-754`) so a direct PATCH writing `Penales_*` onto a closed match cannot bypass every new rule.
- SPEC-REVIEW S5 (corrected in §4, SUPERSEDES D-S2 above): `Cantidad_Periodos_Extra` / `Duracion_Periodo_Extra_Minutos` are NULLABLE with `chk_config_tiempo_periodos` extended, NOT `NOT NULL DEFAULT 2/15`. D-S2's original form directly contradicts the existing constraint (`02_constraints.sql:179`), which requires those columns to be NULL on `Corrido` rows. Python pays a `COALESCE(..., 0)`.
- SPEC-REVIEW S6 (corrected in §3, §11): phase 2 ships only `'Manual'` and `'Penales_Directo'` in the selector. `'Tiempo_Extra_Penales'` and `'Penales_Salvo_Final'` (which is defined in terms of extra time) arrive in phase 3 with the columns that support them. Otherwise phase 2 lets an operator choose a rule the product cannot honour, with a subtitle quoting a duration no column stores — and phase 3 is gated on metric 4 and may never be scheduled. E1 moves to phase 3 with them.
- SPEC-REVIEW S7 (corrected in §7): the `Corrido => Manual` guard cannot be the §5 trigger — that one is `BEFORE UPDATE ON PARTIDOS` and only fires on the transition to `Finalizado`, and a table CHECK cannot reach `Tipo_Cronometro` in another table. Use `TorneoService` plus a `TORNEO` trigger extending the existing precedent `fn_validar_torneo_modalidad` (`06_triggers.sql:331`), which already cross-checks another table.
- SPEC-REVIEW S8 (corrected in §4, SUPERSEDES D-Q3's signature): `_calcular_estado` is a `@staticmethod(hitos, config)` with three call sites (`hito_partido.py:78, 343, 540`) receiving neither `partido` nor `torneo`, and the tie state needs an async aggregate. Real signature: `_periodos_totales_permitidos(config, hitos, llave_empatada: bool, metodo_aplicable: str | None) -> int`, with the async caller computing the D-P1-gated aggregate. All three call sites change.
- SPEC-REVIEW S9 (corrected in §4): `fn_validar_hito_partido` (`06_triggers.sql:924`) enforces ONLY the loose bound `Cantidad_Periodos + COALESCE(Cantidad_Periodos_Extra, 0)` as defence in depth. Re-deriving fase + method + tie state in plpgsql would be a second copy of `_periodos_totales_permitidos` in another language, which is exactly what D-Q2/D-A2 forbid. The precise rule is owned by the service.
- SPEC-REVIEW S10 (corrected in §4, §11): `Hubo_Tiempo_Extra` needs a write point in phase 2 or it is permanently FALSE for the whole phase. Phase 2: a "se jugó prórroga" checkbox in `ModalResultadoDirecto`. Phase 3: the live path sets it when the first extra period opens.
- SPEC-REVIEW S11 (corrected in §3, §13): `'Penales_Salvo_Final'` keys off `PARTIDOS.Ronda_Nombre = 'Final'`, NOT the `es_final` parameter — `_crear_llave(..., "Tercer Lugar", "Unico", es_final=True, ...)` (`motor_formatos.py:513`) passes `es_final=True` for Tercer Lugar, so keying off that flag gives the opposite of the intent. Stated in the plan with its reason so nobody "simplifies" it back.
- SPEC-REVIEW S12 (corrected in §10): the phase-1 server field must reproduce the STRICTER of the two derivations it replaces. `MesaPanel.tsx:290` is `ronda_nombre != null && empatado`; `ModalResultadoDirecto.tsx:420` is `esEliminacion && !esCorrido && marcadorEmpatado`. The modal excludes `Corrido`; the panel does not. The server field excludes `Corrido`.
- SPEC-REVIEW S13 (amends E5): "three adoption metrics as SQL in the plan" is downgraded to metric SHAPES defined here, QUERIES written as the first commit of phase 2. Metric 2 ("% of closed tied llaves carrying a shootout score") needs the two-leg aggregate over `vw_goles_acreditados` and is not a one-liner. Verify: the four queries exist and run against the dev DB before the rest of phase 2 merges.
- SPEC-REVIEW S14 (two supporting claims corrected, conclusions unchanged): (a) the direct-result path DOES write hitos — `Inicio_Partido` at `partido.py:223` and `Fin_Partido` at `:294`. It writes no PERIOD hitos, which is the actual reason `Hubo_Tiempo_Extra` is not derivable. (b) D-A2's lock argument holds only on the vuelta path (`06_triggers.sql:756-766`, guarded by `NEW.Partido_Ida_ID IS NOT NULL`); a `Unico` match or Tercer Lugar takes no lock, but needs no cross-row read either. D-A2 stands on the DRY/trigger-ordering argument alone.
- SPEC-REVIEW S15 (citations corrected): `06_triggers.sql:780` is `IF v_es_ida THEN RETURN NEW` (was cited as :788); `:764` is `partido_vuelta_ida_sin_resolver` (was cited as :788); `:788` is `llave_empatada_en_global_sin_desempate`. Migration numbering is 33 and 34 everywhere — phase 1 has no migration; 0C-bis's "33/34/35" was wrong.
- Phase assignment of every decision above. Phase 1: D-Q2, S12. Phase 2: D-A1, D-A2, D-S1, E2, E3, E4, E5/S13, C7, D-T2, S2, S3, S4, S6, S7, S10, F1, F3, F6, F9. Phase 3: E1/S11, D-Q3/S8, D-P1, D-S2/S5, S1, S9, F5, F7, F8, and all of §4. Any phase: D-Q1, D-T1, C10, S14, S15, F2, F4, housekeeping.
- SPEC-REVIEW F1 (BLOCKING, corrected in §5, §10, §13): the rule `Ganador_Desempate_ID NOT NULL => Metodo_Desempate NOT NULL` breaks the three existing write paths on the day migration 33 lands, because none of them can set a method — `hito_partido.py:384-391` (today's live radio), `hito_partido.py:454-455` (`_registrar_fin_forzado`), `partido.py:283-291` (direct result), plus the generic `PATCH` via `PartidoUpdate.ganador_desempate_id` (`schemas/partido.py:164`). That is exactly the path §9 promises is "sin cambios visibles". All four write `Metodo_Desempate='Manual'` alongside the winner, in the same phase. Verify: a phase-2 regression test that today's Manual close still works post-migration.
- SPEC-REVIEW F2 (corrected in §7): extending `fn_validar_torneo_modalidad`'s FUNCTION BODY is not enough — the trigger is column-scoped (`BEFORE INSERT OR UPDATE OF Disciplina_ID, Modalidad_ID ON TORNEO`, `06_triggers.sql:349-350`), so `Metodo_Desempate_Eliminatoria` must be added to the `UPDATE OF` list or the guard never fires. Two holes named rather than omitted: INSERT is structurally unguardable (the `CONFIGURACION_TIEMPO_TORNEO` FK means the config row cannot exist yet at `BEFORE INSERT ON TORNEO`), covered by `TorneoService.create`; and the reverse direction (flipping `Tipo_Cronometro` to `Corrido`) is handled in Python per the file's own house rule at `06_triggers.sql:360-366`, not a second cross-checking trigger. Also add `metodo_desempate_eliminatoria` to the payload tuple at `torneo.py:302`. Verify: a phase-2 test that the UPDATE is rejected BY THE TRIGGER.
- SPEC-REVIEW F3 (corrected in §5, supersedes S4's placement): the shape/range/coherence rules go immediately after the estado gate (`:753`) and BEFORE the ida `FOR UPDATE` block (`:756`) — not "before the fase check at `:775`". The only slot between `:771` and `:776` is after the `Fase_ID IS NULL OR Es_Walkover` return, which would exclude walkovers, precisely a row where a stray `Penales_*` is plausible and nonsense. Also: the function has FOUR early returns before the tie logic (`:753`, `:771`, `:776`, `:781`), not five. And the `OLD.Estado='Finalizado'` carve-out runs ONLY the shape rules then `RETURN NEW` — it must not fall through to the ida lock and `fn_resolver_llave`, or every PATCH of a closed match re-resolves settled llaves under lock.
- SPEC-REVIEW F5 (corrected in §4): `chk_config_tiempo_periodos` gains `AND Cantidad_Periodos_Extra IS NULL AND Duracion_Periodo_Extra_Minutos IS NULL` on the `Corrido` branch ONLY. The `Periodos` branch is untouched and the new columns stay optional there. Reading "like the two columns that already exist" as symmetric would require them NOT NULL on `Periodos` and fail migration 34 against every existing row (S5 removed the backfill). Verify: phase-3 test, `Corrido` row with `Cantidad_Periodos_Extra=2` rejected.
- SPEC-REVIEW F6 (corrected in §3, §10): migration 33 ships `CHECK IN ('Manual','Penales_Directo')`; migration 34 drops and re-adds it with all four values. Otherwise the API accepts `'Tiempo_Extra_Penales'` in phase 2 even though the selector hides it — S6's failure one layer down, and phase 3 may never be scheduled.
- SPEC-REVIEW F7 (corrected in §8): `Metodo_Desempate_Aplicable` is snapshotted ONLY for `Eliminacion` matches (NULL elsewhere), which is how `_periodos_totales_permitidos` knows the fase without being passed it. Its CHECK domain is narrower than the tournament column's: `IN ('Manual','Penales_Directo','Tiempo_Extra_Penales')` — `'Penales_Salvo_Final'` is a bracket rule, already resolved to a concrete method at snapshot time, so storing it would store the question instead of the answer.
- SPEC-REVIEW F8 (corrected in §9): at the end of regulation BOTH `Inicio_Periodo` and `Fin_Partido` are in `acciones_permitidas` — that is correct and load-bearing, because `Fin_Partido` there IS the D-A1 escape hatch. The UI promotes "Ir a tiempo extra" as primary and keeps "Finalizar" as secondary; it hides neither.
- SPEC-REVIEW F9 (corrected in §4, §5): the direct-result path writes `Metodo_Desempate='Tiempo_Extra'` when the "se jugó prórroga" checkbox is on AND the final score is not level. Without it, a hand-entered `2-1 a.e.t.` stores `Hubo_Tiempo_Extra=TRUE` with `Metodo_Desempate=NULL` — an undefined cell in §11's render matrix and a row asserting both "extra time was played" and "regulation already had a winner". The §5 definition of NULL is narrowed to "regulation already had a winner".
- SPEC-REVIEW F4 (corrected): `## Review record` now carries a header declaring it an archival transcript, not specification, and naming the six superseded statements inside it. The Implementation plan and this block are the spec.
<!-- /autoplan-accepted:ceo -->

<!-- autoplan-accepted:design -->
- D-D1 (CRITICAL, corrected in §11): the penalty-shootout step of `Cronometro.tsx` moves from phase 3 to **phase 2**. It needs no columns beyond the five phase 2 already ships (`Metodo_Desempate` + `Penales_*`); only the extra-time periods need migration 34. Leaving it in phase 3 meant an operator configuring `Penales_Directo`, reaching 1-1 on the LIVE timer, and getting the old radio — S6's exact failure one path over. It also poisons the measurements: every phase-2 live close would fire `desempate_manual_sobre_metodo_configurado` (metric 3) because of the phasing rather than the operators, and metric 4 (live vs direct-result split) — **the gate on phase 3** — would measure a preference the phasing manufactured. The gate would be self-fulfilling in the direction of never building §4. Verify: a phase-2 test closing a tied match by shootout from the live timer.
- D-D2 (CRITICAL, corrected in §11): the render matrix is specified as **all 8 cells**, not "según `Metodo_Desempate` × `Hubo_Tiempo_Extra`". The draft named 3. The 5 missing ones include `('Manual', FALSE)` — the default for every tournament that exists today, the E4 escape, every forced close and every `Corrido` llave — which would have rendered as a bare `2-2` with one team advancing and no explanation: the same information collapse §0 condemns, shipped as the default rendering. Two cells are marked impossible (the triggers forbid them). Verify: a render test per reachable cell.
- D-D3 (CRITICAL, corrected in §11): §8 promised "editable hasta que el partido EMPIEZA" while C7 removed the only surface where a post-generation edit could happen — `PasoGenerarPlayoffs` runs before any elimination match exists, so the window was empty and the promised copy line had no screen to live on. Resolution: make **both** `metodo_desempate_eliminatoria` and `formato_eliminatoria` editable in `TorneoUpdate` + `TorneosAdmin.tsx`. C7 was right that the new field must not have a surface its sibling lacks; the correct exit is giving both the surface, not stripping the new one. Promotes E8 from TODOS into scope.
- D-D4 (HIGH, corrected in §11): the shootout steppers are labeled with **team names, never "Local"/"Visitante"**, and the confirm step restates the outcome in words ("Penales 4-2 — avanza Deportivo Norte"). `Penales_Local` is the local of THIS match, but a vuelta's header shows the GLOBAL, which crosses localía (`fn_resolver_llave` inverts the ida). A reversed 4-2 writes the wrong `Ganador_Desempate_ID`, **passes every trigger rule**, and advances the wrong team. Verify: a test on a vuelta whose ida's local is the vuelta's visitante.
- D-D5 (HIGH, corrected in §11): "Finalizar" at the end of regulation does not close directly — it opens a confirmation sheet ("Cerrar sin jugar el alargue" / "Este torneo define por tiempo extra. Si cerrás acá, elegís vos quién avanza y queda registrado así.") then the manual radio then a destructive-styled confirm. Without that friction the D-A1 escape is the path of least resistance and metric 3 measures nothing.
- D-D6 (HIGH, corrected in §11): a copy table maps all 9 new rejection codes to Spanish operator language and names where each renders (inline vs toast). The operator already eats `llave_empatada_en_global_sin_desempate` as a raw server failure today; the plan fixes that code's cause and adds eight more.
- D-D7 (HIGH, corrected in §11): stepper validation in the client, not only the trigger — min 0, max 30, both start at 0, confirm disabled while equal or both zero, inline message on equal, no free-text entry.
- D-D8 (HIGH, corrected in §11): a persistent rule chip in the mesa/cronómetro header for `Eliminacion` matches showing the rule in force for THIS match ("Empate → tiempo extra" / "Empate → penales" / "Empate → lo decidís vos") plus the global on a vuelta. `Metodo_Desempate_Aplicable` deliberately diverges from the tournament's current setting and was invisible everywhere; the operator had no way to know what happens at minute 90 until a button changed label.
- D-D9 (MEDIUM, corrected in §11): per-surface public render spec. `BracketView` shows the **GLOBAL** (stated explicitly — it is undefined today and `Penales_*` lives on the vuelta) plus a compact non-wrapping `pen. 4-2` badge; list row gets the full string; the detail page adds a prose line.
- D-D10 (MEDIUM, corrected in §11): `PasoGenerarPlayoffs` gets labeled radio groups ("Formato de los cruces" / "Si un cruce termina empatado"), `'Manual'` is relabeled "Lo decido yo al cerrar el partido" (not developer vocabulary), and in phase 3 the duration estimate gains the extra-time ceiling — §3 justifies `Penales_Salvo_Final` with hourly-rented fields, and the only screen that estimates duration was silent about the 30 minutes prórroga can add.
- D-D11 (MEDIUM, corrected in §11): success is a persistent line on the match card ("Penales 4-2 · avanza X"), not a toast; undo names what it destroys ("Se va a borrar la tanda de penales 4-2 y el equipo que avanzaba").
- D-D12 (MEDIUM, corrected in §11): progressive disclosure in `ModalResultadoDirecto` — the tie-breaking block appears only when the phase-1 `requiere_desempate` field is true, the prórroga checkbox only for `Eliminacion`, and "no tengo el marcador" is a text link below the steppers, not a peer option. Otherwise a group-stage result becomes a form to scan every time.
- D-D13 (MEDIUM, corrected in §11): pending state on a 5s-polled screen — action buttons disable on submit until the next successful fetch, and the poll does not overwrite locally pending state.
- D-D14 (MEDIUM, corrected in §11): on first open after the phase-3 upgrade, a dismissible note in `PasoGenerarPlayoffs` names the two new options, so tournaments configured in phase 2 are not silently stranded on `Penales_Directo`.
- D-D15 (corrected in §11-bis): an interaction-state table covering all 8 controls, plus explicit accessibility requirements — visible `<label>` on the steppers (never placeholder-as-label), `aria-label` on the `pen. 4-2` badge and on `(def.)`, focus-trapped confirmation dialog reusing the existing `frontend/src/hooks/useModalFocusTrap.ts`, and 44px minimum touch targets (the steppers are used pitch-side, one-handed, sometimes in the rain).
- Mockups: NOT generated, with reason. The designer binary is available (`DESIGN_READY`), but every design finding here is a specification gap (which states, which strings, which labels, which of 8 cells) rather than a visual-direction question — the components (radios, steppers, badges, toasts) already exist in an established Spanish-language admin UI with no DESIGN.md. Generated variants would answer a question nobody asked and would not match the app. The spec tables in §11 and §11-bis are the deliverable a mockup would otherwise stand in for.
<!-- /autoplan-accepted:design -->
## Review record

<!-- autoplan-accepted:design -->
- D-D1 (CRITICAL, corrected in §11): the penalty-shootout step of `Cronometro.tsx` moves from phase 3 to **phase 2**. It needs no columns beyond the five phase 2 already ships (`Metodo_Desempate` + `Penales_*`); only the extra-time periods need migration 34. Leaving it in phase 3 meant an operator configuring `Penales_Directo`, reaching 1-1 on the LIVE timer, and getting the old radio — S6's exact failure one path over. It also poisons the measurements: every phase-2 live close would fire `desempate_manual_sobre_metodo_configurado` (metric 3) because of the phasing rather than the operators, and metric 4 (live vs direct-result split) — **the gate on phase 3** — would measure a preference the phasing manufactured. The gate would be self-fulfilling in the direction of never building §4. Verify: a phase-2 test closing a tied match by shootout from the live timer.
- D-D2 (CRITICAL, corrected in §11): the render matrix is specified as **all 8 cells**, not "según `Metodo_Desempate` × `Hubo_Tiempo_Extra`". The draft named 3. The 5 missing ones include `('Manual', FALSE)` — the default for every tournament that exists today, the E4 escape, every forced close and every `Corrido` llave — which would have rendered as a bare `2-2` with one team advancing and no explanation: the same information collapse §0 condemns, shipped as the default rendering. Two cells are marked impossible (the triggers forbid them). Verify: a render test per reachable cell.
- D-D3 (CRITICAL, corrected in §11): §8 promised "editable hasta que el partido EMPIEZA" while C7 removed the only surface where a post-generation edit could happen — `PasoGenerarPlayoffs` runs before any elimination match exists, so the window was empty and the promised copy line had no screen to live on. Resolution: make **both** `metodo_desempate_eliminatoria` and `formato_eliminatoria` editable in `TorneoUpdate` + `TorneosAdmin.tsx`. C7 was right that the new field must not have a surface its sibling lacks; the correct exit is giving both the surface, not stripping the new one. Promotes E8 from TODOS into scope.
- D-D4 (HIGH, corrected in §11): the shootout steppers are labeled with **team names, never "Local"/"Visitante"**, and the confirm step restates the outcome in words ("Penales 4-2 — avanza Deportivo Norte"). `Penales_Local` is the local of THIS match, but a vuelta's header shows the GLOBAL, which crosses localía (`fn_resolver_llave` inverts the ida). A reversed 4-2 writes the wrong `Ganador_Desempate_ID`, **passes every trigger rule**, and advances the wrong team. Verify: a test on a vuelta whose ida's local is the vuelta's visitante.
- D-D5 (HIGH, corrected in §11): "Finalizar" at the end of regulation does not close directly — it opens a confirmation sheet ("Cerrar sin jugar el alargue" / "Este torneo define por tiempo extra. Si cerrás acá, elegís vos quién avanza y queda registrado así.") then the manual radio then a destructive-styled confirm. Without that friction the D-A1 escape is the path of least resistance and metric 3 measures nothing.
- D-D6 (HIGH, corrected in §11): a copy table maps all 9 new rejection codes to Spanish operator language and names where each renders (inline vs toast). The operator already eats `llave_empatada_en_global_sin_desempate` as a raw server failure today; the plan fixes that code's cause and adds eight more.
- D-D7 (HIGH, corrected in §11): stepper validation in the client, not only the trigger — min 0, max 30, both start at 0, confirm disabled while equal or both zero, inline message on equal, no free-text entry.
- D-D8 (HIGH, corrected in §11): a persistent rule chip in the mesa/cronómetro header for `Eliminacion` matches showing the rule in force for THIS match ("Empate → tiempo extra" / "Empate → penales" / "Empate → lo decidís vos") plus the global on a vuelta. `Metodo_Desempate_Aplicable` deliberately diverges from the tournament's current setting and was invisible everywhere; the operator had no way to know what happens at minute 90 until a button changed label.
- D-D9 (MEDIUM, corrected in §11): per-surface public render spec. `BracketView` shows the **GLOBAL** (stated explicitly — it is undefined today and `Penales_*` lives on the vuelta) plus a compact non-wrapping `pen. 4-2` badge; list row gets the full string; the detail page adds a prose line.
- D-D10 (MEDIUM, corrected in §11): `PasoGenerarPlayoffs` gets labeled radio groups ("Formato de los cruces" / "Si un cruce termina empatado"), `'Manual'` is relabeled "Lo decido yo al cerrar el partido" (not developer vocabulary), and in phase 3 the duration estimate gains the extra-time ceiling — §3 justifies `Penales_Salvo_Final` with hourly-rented fields, and the only screen that estimates duration was silent about the 30 minutes prórroga can add.
- D-D11 (MEDIUM, corrected in §11): success is a persistent line on the match card ("Penales 4-2 · avanza X"), not a toast; undo names what it destroys ("Se va a borrar la tanda de penales 4-2 y el equipo que avanzaba").
- D-D12 (MEDIUM, corrected in §11): progressive disclosure in `ModalResultadoDirecto` — the tie-breaking block appears only when the phase-1 `requiere_desempate` field is true, the prórroga checkbox only for `Eliminacion`, and "no tengo el marcador" is a text link below the steppers, not a peer option. Otherwise a group-stage result becomes a form to scan every time.
- D-D13 (MEDIUM, corrected in §11): pending state on a 5s-polled screen — action buttons disable on submit until the next successful fetch, and the poll does not overwrite locally pending state.
- D-D14 (MEDIUM, corrected in §11): on first open after the phase-3 upgrade, a dismissible note in `PasoGenerarPlayoffs` names the two new options, so tournaments configured in phase 2 are not silently stranded on `Penales_Directo`.
- D-D15 (corrected in §11-bis): an interaction-state table covering all 8 controls, plus explicit accessibility requirements — visible `<label>` on the steppers (never placeholder-as-label), `aria-label` on the `pen. 4-2` badge and on `(def.)`, focus-trapped confirmation dialog reusing the existing `frontend/src/hooks/useModalFocusTrap.ts`, and 44px minimum touch targets (the steppers are used pitch-side, one-handed, sometimes in the rain).
- Mockups: NOT generated, with reason. The designer binary is available (`DESIGN_READY`), but every design finding here is a specification gap (which states, which strings, which labels, which of 8 cells) rather than a visual-direction question — the components (radios, steppers, badges, toasts) already exist in an established Spanish-language admin UI with no DESIGN.md. Generated variants would answer a question nobody asked and would not match the app. The spec tables in §11 and §11-bis are the deliverable a mockup would otherwise stand in for.
<!-- /autoplan-accepted:design -->

> **Transcripción histórica del pipeline de review del 2026-09-17. NO es
> especificación.** Registra el razonamiento y el orden en que se llegó a cada
> decisión, incluidas versiones que después se corrigieron. Donde algo acá
> contradiga `## Implementation plan` (§0-§13) o el bloque
> `autoplan-accepted:ceo`, **mandan esos dos**. Contradicciones conocidas y ya
> superadas, dejadas a propósito para que se vea la corrección: `NOT NULL DEFAULT
> 2/15` en las columnas de período extra (superado por S5), la firma
> `_periodos_totales_permitidos(partido, torneo, config)` (superada por S8), "3
> columnas nuevas en PARTIDOS" (son 5), "6 branches" de coherencia (son 7),
> "33/34/35" (son 33 y 34), "the metrics are SQL queries in the plan" (superado por
> S13 y §12-bis), y la cita `06_triggers.sql:788` para
> `partido_vuelta_ida_sin_resolver` (es `:764`).

<!-- autoplan-accepted:ceo -->
- Approach C: three sequenced landings. Phase 1 = server-side `requiere_desempate` alone (fixes the live ida/vuelta bug, no migration). Phase 2 = method + shootout + record + public display (migration 33). Phase 3 = extra time as real clocked periods (migration 34), scheduled only after metric 4 is run. Verify: each phase ships and reverts independently; `git revert` of any phase leaves its columns inert.
- E1/C1: add `'Penales_Salvo_Final'` to `TORNEO.Metodo_Desempate_Eliminatoria`, keyed on `PARTIDOS.Ronda_Nombre = 'Final'`. Tercer Lugar resolves on the penalties side. The "no real competition varies by round" premise is struck; `_piernas_por_ronda` (`motor_formatos.py:71`) is cited as the in-repo precedent. Verify: test #9.
- E2/C2: add `PARTIDOS.Hubo_Tiempo_Extra BOOLEAN NOT NULL DEFAULT FALSE`, orthogonal to `Metodo_Desempate`. Public record renders "2-2 a.e.t. (4-2 pen.)". Not derived from `HITOS_PARTIDO` — the direct-result path writes none. Verify: a direct-result close with ET played round-trips the flag.
- E3/C6: add `PARTIDOS.Metodo_Desempate_Aplicable`, snapshotted from the tournament rule at `Inicio_Partido` (`hito_partido.py:357`) and at direct-result save. D6 is restated: the rule is editable until the match STARTS, not until it is played. Verify: test #6.
- E4/C8: the shootout UI always offers "no tengo el marcador de la tanda", falling back to `Metodo_Desempate='Manual'` with `Penales_*` NULL. The schema's answer to missing data is NULL, never a guess. Verify: test #11.
- E5/C9: three adoption metrics as SQL in the plan — (1) % of `Eliminacion` tournaments on a non-`Manual` method at 30 days, (2) % of closed tied llaves carrying a shootout score, (3) count of `Manual` closes on tournaments configured otherwise. Plus metric (4): live-timer vs direct-result close split for `Eliminacion`, 90 days. Verify: each query runs against the dev DB before phase 2 merges.
- C10: metric 4 is a **gate on scheduling phase 3**, not on the plan. If direct-result entry dominates `Eliminacion` closes, phase 3's shape is reconsidered before it is built.
- D-A1: a tied match on a non-`Manual` tournament CAN still be closed as `Manual` (direct result / paper sheet). This is deliberate, not a hole. It must be logged as `desempate_manual_sobre_metodo_configurado` and counted by metric 3. No future change may turn it into a hard rejection without re-deciding this. Verify: test #7.
- D-A2: do NOT add a second BEFORE UPDATE trigger. Fold the coherence rules into the existing `fn_validar_partido_eliminacion_desempate` (`06_triggers.sql:742`). Two reasons: Postgres fires BEFORE UPDATE triggers alphabetically (a silent ordering dependency), and the existing function already holds the `SELECT … FOR UPDATE` lock on the ida that these rules need. Supersedes §5's "trigger nuevo `fn_validar_metodo_desempate`". Verify: test #2 passes with one trigger.
- D-Q1: name the per-round value `'Penales_Salvo_Final'`, never `'Mixto'` — `Formato_Eliminatoria='Mixto'` already exists on the same row meaning something else.
- D-Q2: `requiereDesempate` is removed from BOTH `MesaPanel.tsx:290` and `ModalResultadoDirecto.tsx:420` and replaced by one server field. Root-cause fix at the shared source, not a guard per caller. Verify: test #1, including the ida-tied case that is wrong today.
- D-Q3: extract `_periodos_totales_permitidos(partido, torneo, config) -> int` rather than inlining the tope into `_calcular_estado` (which already branches 7 times). Verify: test #5.
- D-P1: compute the "is this llave tied?" aggregate ONLY when `periodo_abierto IS NULL AND ultimo_periodo_cerrado >= Cantidad_Periodos`. The cronometro endpoint is polled every 5s per live match (`Cronometro.tsx:6`); an unconditional aggregate would run per match per poll for the whole match.
- D-S1: `CHECK (Penales_Local BETWEEN 0 AND 99)` and the same for `Penales_Visitante`, plus a server-side check. Client integers are never trusted into the acta.
- D-S2: `Cantidad_Periodos_Extra` / `Duracion_Periodo_Extra_Minutos` ship `NOT NULL DEFAULT 2 / 15` for `Tipo_Cronometro='Periodos'` with a backfill, so `None` arithmetic in `_calcular_estado` is impossible rather than rescued.
- C7: DROP §8's promise of a tournament-settings edit surface. `formato_eliminatoria` is create-only today (`TorneosAdmin.tsx:437-442`, absent from `TorneoUpdate`); the new field follows the sibling exactly and is edited at `PasoGenerarPlayoffs` only. Making both editable is deferred to TODOS.
- D-T1: record in TODOS.md that the documented `ReglamentoTorneo` revisit trigger (`TODOS.md:561-566`, "a third reglamento field") has now FIRED — this plan adds the 4th and 5th. The refactor is NOT done here (Effort L, outside blast radius), but the next reglamento field must land on a decision already made.
- D-T2: one block comment in `01_schema.sql` mapping each of the seven "how did this end" columns (`Ganador_Desempate_ID`, `Ganador_Corrido_ID`, `Metodo_Desempate`, `Metodo_Desempate_Aplicable`, `Hubo_Tiempo_Extra`, `Penales_*`, `Es_Walkover`) to the one question it answers. Required, not optional.
- Housekeeping: annotate `docs/plans/cierre-fase-regular-llaves-playoffs-plan.md` with a forward pointer to this plan, and mark its diagrams at :941 and :1001-1043 as superseded by phase 2.
- Deployment: each phase carries its own migration number (33, 34) and the three-location column rule (`01_schema.sql` + that phase's migration + `SCRIPTS_VIGENTES` in `test_scripts_sql.py:36-48`) is satisfied PER PHASE. Each migration is run locally with `psql -1` against `torneos_mvp` before the phase lands — the recorded project pitfall is a migration written but never run.
- Rejected, with reason recorded: C3's "extra time as a label/flag without new clock periods". Without an open period the live timer has no minute to attach an ET goal to, so that option silently means "extra time is unusable from the live timer" — which is half the operator's stated ask. Surfaced at the Final Gate as a taste decision.
- SPEC-REVIEW S1 (BLOCKING defect, corrected in §4): the extra-period tope must depend on whether extra time was ENTERED (an `Inicio_Periodo` hito with `Numero_Periodo > Cantidad_Periodos` exists), never on whether the tie is currently live. With a tie-conditioned tope, a goal in the first extra period drops the tope back and `hito_partido.py:126-130` then offers NEITHER `Inicio_Periodo` (`3 < 2` false) NOR `Fin_Partido` (`3 == 2` false) — the match has zero permitted actions and can never be closed. It would also forbid playing the second half of extra time. The `Fin_Partido` condition additionally changes from `== Cantidad_Periodos` to `>= Cantidad_Periodos`. Verify: phase-3 test "goal in ET1 -> ET2 still offered, match closes after ET2".
- SPEC-REVIEW S2 (corrected in §5): `deshacer_fin_forzado` (`hito_partido.py:471-545`) does not clear `Ganador_Desempate_ID` today and would not clear the five new columns. Phase 2 makes it NULL `Metodo_Desempate`, `Penales_Local`, `Penales_Visitante`, `Ganador_Desempate_ID` and reset `Hubo_Tiempo_Extra`. Verify: undo a forced close that carried a shootout.
- SPEC-REVIEW S3 (corrected in §5): seventh coherence rule `Metodo_Desempate='Tiempo_Extra' => Hubo_Tiempo_Extra = TRUE`. Without it the pair `('Tiempo_Extra', FALSE)` is representable — the second-source-of-truth anti-pattern §0 invokes against `Fase`/`Fase_ID`.
- SPEC-REVIEW S4 (corrected in §5): state the insertion point of each new rule inside `fn_validar_partido_eliminacion_desempate`. The function has five early returns; `desempate_en_ida_no_permitido` MUST go before `:780` (`IF v_es_ida THEN RETURN NEW`) or it never fires on the ida path, and the shape/range/coherence rules go before the fase check at `:775`. Plus an explicit carve-out on the `OLD.Estado = 'Finalizado'` return (`:752-754`) so a direct PATCH writing `Penales_*` onto a closed match cannot bypass every new rule.
- SPEC-REVIEW S5 (corrected in §4, SUPERSEDES D-S2 above): `Cantidad_Periodos_Extra` / `Duracion_Periodo_Extra_Minutos` are NULLABLE with `chk_config_tiempo_periodos` extended, NOT `NOT NULL DEFAULT 2/15`. D-S2's original form directly contradicts the existing constraint (`02_constraints.sql:179`), which requires those columns to be NULL on `Corrido` rows. Python pays a `COALESCE(..., 0)`.
- SPEC-REVIEW S6 (corrected in §3, §11): phase 2 ships only `'Manual'` and `'Penales_Directo'` in the selector. `'Tiempo_Extra_Penales'` and `'Penales_Salvo_Final'` (which is defined in terms of extra time) arrive in phase 3 with the columns that support them. Otherwise phase 2 lets an operator choose a rule the product cannot honour, with a subtitle quoting a duration no column stores — and phase 3 is gated on metric 4 and may never be scheduled. E1 moves to phase 3 with them.
- SPEC-REVIEW S7 (corrected in §7): the `Corrido => Manual` guard cannot be the §5 trigger — that one is `BEFORE UPDATE ON PARTIDOS` and only fires on the transition to `Finalizado`, and a table CHECK cannot reach `Tipo_Cronometro` in another table. Use `TorneoService` plus a `TORNEO` trigger extending the existing precedent `fn_validar_torneo_modalidad` (`06_triggers.sql:331`), which already cross-checks another table.
- SPEC-REVIEW S8 (corrected in §4, SUPERSEDES D-Q3's signature): `_calcular_estado` is a `@staticmethod(hitos, config)` with three call sites (`hito_partido.py:78, 343, 540`) receiving neither `partido` nor `torneo`, and the tie state needs an async aggregate. Real signature: `_periodos_totales_permitidos(config, hitos, llave_empatada: bool, metodo_aplicable: str | None) -> int`, with the async caller computing the D-P1-gated aggregate. All three call sites change.
- SPEC-REVIEW S9 (corrected in §4): `fn_validar_hito_partido` (`06_triggers.sql:924`) enforces ONLY the loose bound `Cantidad_Periodos + COALESCE(Cantidad_Periodos_Extra, 0)` as defence in depth. Re-deriving fase + method + tie state in plpgsql would be a second copy of `_periodos_totales_permitidos` in another language, which is exactly what D-Q2/D-A2 forbid. The precise rule is owned by the service.
- SPEC-REVIEW S10 (corrected in §4, §11): `Hubo_Tiempo_Extra` needs a write point in phase 2 or it is permanently FALSE for the whole phase. Phase 2: a "se jugó prórroga" checkbox in `ModalResultadoDirecto`. Phase 3: the live path sets it when the first extra period opens.
- SPEC-REVIEW S11 (corrected in §3, §13): `'Penales_Salvo_Final'` keys off `PARTIDOS.Ronda_Nombre = 'Final'`, NOT the `es_final` parameter — `_crear_llave(..., "Tercer Lugar", "Unico", es_final=True, ...)` (`motor_formatos.py:513`) passes `es_final=True` for Tercer Lugar, so keying off that flag gives the opposite of the intent. Stated in the plan with its reason so nobody "simplifies" it back.
- SPEC-REVIEW S12 (corrected in §10): the phase-1 server field must reproduce the STRICTER of the two derivations it replaces. `MesaPanel.tsx:290` is `ronda_nombre != null && empatado`; `ModalResultadoDirecto.tsx:420` is `esEliminacion && !esCorrido && marcadorEmpatado`. The modal excludes `Corrido`; the panel does not. The server field excludes `Corrido`.
- SPEC-REVIEW S13 (amends E5): "three adoption metrics as SQL in the plan" is downgraded to metric SHAPES defined here, QUERIES written as the first commit of phase 2. Metric 2 ("% of closed tied llaves carrying a shootout score") needs the two-leg aggregate over `vw_goles_acreditados` and is not a one-liner. Verify: the four queries exist and run against the dev DB before the rest of phase 2 merges.
- SPEC-REVIEW S14 (two supporting claims corrected, conclusions unchanged): (a) the direct-result path DOES write hitos — `Inicio_Partido` at `partido.py:223` and `Fin_Partido` at `:294`. It writes no PERIOD hitos, which is the actual reason `Hubo_Tiempo_Extra` is not derivable. (b) D-A2's lock argument holds only on the vuelta path (`06_triggers.sql:756-766`, guarded by `NEW.Partido_Ida_ID IS NOT NULL`); a `Unico` match or Tercer Lugar takes no lock, but needs no cross-row read either. D-A2 stands on the DRY/trigger-ordering argument alone.
- SPEC-REVIEW S15 (citations corrected): `06_triggers.sql:780` is `IF v_es_ida THEN RETURN NEW` (was cited as :788); `:764` is `partido_vuelta_ida_sin_resolver` (was cited as :788); `:788` is `llave_empatada_en_global_sin_desempate`. Migration numbering is 33 and 34 everywhere — phase 1 has no migration; 0C-bis's "33/34/35" was wrong.
- Phase assignment of every decision above. Phase 1: D-Q2, S12. Phase 2: D-A1, D-A2, D-S1, E2, E3, E4, E5/S13, C7, D-T2, S2, S3, S4, S6, S7, S10, F1, F3, F6, F9. Phase 3: E1/S11, D-Q3/S8, D-P1, D-S2/S5, S1, S9, F5, F7, F8, and all of §4. Any phase: D-Q1, D-T1, C10, S14, S15, F2, F4, housekeeping.
- SPEC-REVIEW F1 (BLOCKING, corrected in §5, §10, §13): the rule `Ganador_Desempate_ID NOT NULL => Metodo_Desempate NOT NULL` breaks the three existing write paths on the day migration 33 lands, because none of them can set a method — `hito_partido.py:384-391` (today's live radio), `hito_partido.py:454-455` (`_registrar_fin_forzado`), `partido.py:283-291` (direct result), plus the generic `PATCH` via `PartidoUpdate.ganador_desempate_id` (`schemas/partido.py:164`). That is exactly the path §9 promises is "sin cambios visibles". All four write `Metodo_Desempate='Manual'` alongside the winner, in the same phase. Verify: a phase-2 regression test that today's Manual close still works post-migration.
- SPEC-REVIEW F2 (corrected in §7): extending `fn_validar_torneo_modalidad`'s FUNCTION BODY is not enough — the trigger is column-scoped (`BEFORE INSERT OR UPDATE OF Disciplina_ID, Modalidad_ID ON TORNEO`, `06_triggers.sql:349-350`), so `Metodo_Desempate_Eliminatoria` must be added to the `UPDATE OF` list or the guard never fires. Two holes named rather than omitted: INSERT is structurally unguardable (the `CONFIGURACION_TIEMPO_TORNEO` FK means the config row cannot exist yet at `BEFORE INSERT ON TORNEO`), covered by `TorneoService.create`; and the reverse direction (flipping `Tipo_Cronometro` to `Corrido`) is handled in Python per the file's own house rule at `06_triggers.sql:360-366`, not a second cross-checking trigger. Also add `metodo_desempate_eliminatoria` to the payload tuple at `torneo.py:302`. Verify: a phase-2 test that the UPDATE is rejected BY THE TRIGGER.
- SPEC-REVIEW F3 (corrected in §5, supersedes S4's placement): the shape/range/coherence rules go immediately after the estado gate (`:753`) and BEFORE the ida `FOR UPDATE` block (`:756`) — not "before the fase check at `:775`". The only slot between `:771` and `:776` is after the `Fase_ID IS NULL OR Es_Walkover` return, which would exclude walkovers, precisely a row where a stray `Penales_*` is plausible and nonsense. Also: the function has FOUR early returns before the tie logic (`:753`, `:771`, `:776`, `:781`), not five. And the `OLD.Estado='Finalizado'` carve-out runs ONLY the shape rules then `RETURN NEW` — it must not fall through to the ida lock and `fn_resolver_llave`, or every PATCH of a closed match re-resolves settled llaves under lock.
- SPEC-REVIEW F5 (corrected in §4): `chk_config_tiempo_periodos` gains `AND Cantidad_Periodos_Extra IS NULL AND Duracion_Periodo_Extra_Minutos IS NULL` on the `Corrido` branch ONLY. The `Periodos` branch is untouched and the new columns stay optional there. Reading "like the two columns that already exist" as symmetric would require them NOT NULL on `Periodos` and fail migration 34 against every existing row (S5 removed the backfill). Verify: phase-3 test, `Corrido` row with `Cantidad_Periodos_Extra=2` rejected.
- SPEC-REVIEW F6 (corrected in §3, §10): migration 33 ships `CHECK IN ('Manual','Penales_Directo')`; migration 34 drops and re-adds it with all four values. Otherwise the API accepts `'Tiempo_Extra_Penales'` in phase 2 even though the selector hides it — S6's failure one layer down, and phase 3 may never be scheduled.
- SPEC-REVIEW F7 (corrected in §8): `Metodo_Desempate_Aplicable` is snapshotted ONLY for `Eliminacion` matches (NULL elsewhere), which is how `_periodos_totales_permitidos` knows the fase without being passed it. Its CHECK domain is narrower than the tournament column's: `IN ('Manual','Penales_Directo','Tiempo_Extra_Penales')` — `'Penales_Salvo_Final'` is a bracket rule, already resolved to a concrete method at snapshot time, so storing it would store the question instead of the answer.
- SPEC-REVIEW F8 (corrected in §9): at the end of regulation BOTH `Inicio_Periodo` and `Fin_Partido` are in `acciones_permitidas` — that is correct and load-bearing, because `Fin_Partido` there IS the D-A1 escape hatch. The UI promotes "Ir a tiempo extra" as primary and keeps "Finalizar" as secondary; it hides neither.
- SPEC-REVIEW F9 (corrected in §4, §5): the direct-result path writes `Metodo_Desempate='Tiempo_Extra'` when the "se jugó prórroga" checkbox is on AND the final score is not level. Without it, a hand-entered `2-1 a.e.t.` stores `Hubo_Tiempo_Extra=TRUE` with `Metodo_Desempate=NULL` — an undefined cell in §11's render matrix and a row asserting both "extra time was played" and "regulation already had a winner". The §5 definition of NULL is narrowed to "regulation already had a winner".
- SPEC-REVIEW F4 (corrected): `## Review record` now carries a header declaring it an archival transcript, not specification, and naming the six superseded statements inside it. The Implementation plan and this block are the spec.
<!-- /autoplan-accepted:ceo -->

# PHASE 1 — CEO REVIEW (SELECTIVE EXPANSION)

## Pre-review system audit

- Branch `main`, clean tree, HEAD `4af22e3 Implementación_FaseClasificatoria`. No stash.
- Most-churned files in 30 days: `frontend/src/index.css` (18), `TODOS.md` (18),
  `database/02_constraints.sql` (15), `database/01_schema.sql` (15),
  `database/06_triggers.sql` (13), `backend/tests/test_scripts_sql.py` (10). **Every
  file this plan touches is in the hot set.** Third consecutive plan over the same
  code (`motor-formatos`, `control-mesa-reactividad-playoffs`,
  `cierre-fase-regular-llaves-playoffs`). Recurring area → reviewed adversarially.
- No real `TODO`/`FIXME`/`HACK` markers in project source.
- Design doc: `docs/designs/frontend-inicial-dashboard-mesa-en-vivo.md` (different
  feature, no constraints on this one).
- `TODOS.md:71-73` parks this exact feature on the premise this plan corrects.
  `TODOS.md:561-566` parks a generic `ReglamentoTorneo` refactor and states its own
  revisit trigger: *"se revisita si aparece un tercer campo de reglamento"*. This
  plan adds the 4th and 5th. See Section 10.
- Taste references: `motor_formatos.py` (every edge case carries its EC-number),
  `06_triggers.sql` (rule stated once in SQL with rationale inline). Anti-pattern to
  avoid: the `PARTIDOS.Fase` (text) vs `Fase_ID` duality.
- Search unavailable — proceeding with in-distribution knowledge only.

## 0A. Premise challenge

| # | Premise | Verdict |
|---|---|---|
| P-1 | "Recording only WHO advanced, never HOW, is a real defect" | **VALID.** Verified: `PARTIDOS` has no column that distinguishes a 1-1 decided 4-2 on penalties from one decided by a 105th-minute goal. |
| P-2 | "The tie method is a property of the whole bracket" (§3) | **FALSE — corrected, see D-C1.** `_piernas_por_ronda` (`motor_formatos.py:71`) makes the sibling column `Formato_Eliminatoria` round-varying via `Mixto`. Copa América 2019/2021 sent quarterfinals straight to penalties and played extra time from the semis. Amateur field-rental tournaments do the same by default. |
| P-3 | "Extra time must be real clocked periods" (§4) | **VALID, and load-bearing.** In the live path the operator physically cannot register a goal after `Fin_Partido`; without an open period there is no minute to attach it to. The "label only" alternative silently means "extra time is unusable from the live timer." |
| P-4 | "`fn_marcador_partido`/`fn_resolver_llave` need zero changes" (§4) | **VALID.** ET goals are ordinary `EVENTOS_PARTIDO` rows, so `vw_goles_acreditados` picks them up and the aggregate math is unchanged. Verified against `06_triggers.sql:580-720`. |
| P-5 | "The method can be read at close time, so it is editable until the llave is played" (§8) | **FALSE — corrected, see D-C6.** A match is an interval, not a point. Flipping to `Penales_Directo` while extra time is being played retroactively puts the open period out of range. |
| P-6 | "Penales_Local/Visitante are always knowable" (§5) | **FALSE — corrected, see D-C8.** A paper result sheet saying only "won on penalties" forces the operator to invent a scoreline. |
| P-7 | "`Metodo_Desempate` is one dimension" (§5) | **FALSE — corrected, see D-C2.** Extra-time-then-penalties and straight-to-penalties both store `'Penales'`; the fact that extra time was played is lost. Same collapse §0 condemns. |
| P-8 | "The ida/vuelta desempate gate bug must ship with this feature" (§1) | **FALSE — corrected, see D-C4.** It is independently correct, shippable, testable and revertable. |

## 0B. Existing code leverage (What already exists)

| Sub-problem | Existing code | Reused? |
|---|---|---|
| Count goals, decide a winner | `fn_marcador_partido` (`06_triggers.sql:580`) | **Yes, unchanged.** ET goals flow through `vw_goles_acreditados` for free. |
| Resolve a two-legged aggregate | `fn_resolver_llave` (`06_triggers.sql:657`) | **Yes, unchanged.** |
| Force a tie to be resolved before `Finalizado` | `fn_validar_partido_eliminacion_desempate` (`06_triggers.sql:742`) | **Yes, EXTENDED in place** (not a second trigger — see D-A2). |
| Clock periods, pause/resume, minute derivation | `HitoPartidoService._calcular_estado` + `Cronometro.tsx` | **Yes, extended.** The whole ET mechanic is "one more period", not a new subsystem. |
| Persist a bracket-wide rule chosen at generation | `Torneo.formato_eliminatoria` + `generar_playoffs:628-629` | **Yes, exact same pattern.** |
| Per-round rule variation | `_piernas_por_ronda(formato, es_final)` (`motor_formatos.py:71`) | **Yes — now also the model for D-C1.** Was going to be re-invented; the reuse ladder caught it. |
| Round identity at close time | `PARTIDOS.Ronda_Nombre` (`'Final'`, `'Tercer Lugar'`, …) | **Yes.** Already denormalized; no new column needed to key a per-round rule. |
| Radio-style one-way decision in the mesa flow | `ganador_corrido_id` control, `Cronometro.tsx:350-430` | **Yes**, the penalty stepper sits in the same slot. |
| Snapshot a rule onto a row at match start | `registrar()` `Inicio_Partido` branch (`hito_partido.py:357`) | **Yes — write point for D-C6.** |

**Nothing is rebuilt.** The one thing the draft was about to reinvent (per-round rule
variation) already exists ten lines from the code it cites.

## 0C. Dream state

```
  CURRENT STATE                    THIS PLAN                      12-MONTH IDEAL
  ---------------------------      -------------------------      -----------------------------
  A tied knockout stores only      Stores WHAT ended it            Every competitive rule of a
  Ganador_Desempate_ID.            (method), WHETHER extra         tournament lives in one
  "4-2 on penalties" and "goal     time was played, and the        declarative reglamento the
  in the 105th" are the same       shootout score. Public          operator fills once and the
  row.                             record shows "2-2 a.e.t.        engine reads everywhere.
                                   (4-2 pen.)". Rule can vary
  Reglamento is 3 loose columns    by round.                       Public record is the product:
  on TORNEO.                                                       shareable, unambiguous, and
                                   Reglamento becomes 5 loose      complete without an operator
  The tie gate is derived twice    columns on TORNEO. ← debt       explaining it.
  in the client and gets ida/                                      (see Section 10)
  vuelta wrong.                    Gate moves server-side, once.
```

**Dream state delta:** this plan moves the *record* decisively toward the ideal and
moves the *configuration model* slightly away from it (two more loose columns on
`TORNEO`, crossing the documented `ReglamentoTorneo` revisit threshold). Net
positive, with one named debt item.

## 0C-bis. Implementation alternatives

```
APPROACH A: Penalties-only vertical slice (minimal viable)
  Summary: Metodo_Desempate + Penales_* + trigger + direct-result entry + public
           display. No clock changes at all.
  Effort:  S (human ~1.5d / CC ~40min)     Risk: Low     Completeness: 6/10
  Pros:    Ships the whole public-record payoff; touches no state machine;
           trivially revertable; covers the dominant amateur path (paper sheet).
  Cons:    Extra time remains unrecordable from the live timer, which is half the
           operator's stated ask; a second plan is needed for it anyway.
  Reuses:  ModalResultadoDirecto save path, existing desempate trigger.

APPROACH B: Full feature, one landing (the draft as written)
  Summary: Everything in §0-§13, one PR.
  Effort:  L (human ~5d / CC ~2.5h)        Risk: High    Completeness: 9/10
  Pros:    One coherent change; the operator gets the whole flow at once.
  Cons:    Single-shot across DB triggers + two frontend state machines in the
           repo's hottest files; the live bug fix cannot roll back independently;
           no way to learn whether the expensive half is wanted before paying.
  Reuses:  Everything listed in 0B.

APPROACH C: Three sequenced landings (ideal architecture)  ← RECOMMENDED
  Summary: (1) server-side requiere_desempate alone; (2) method + penalties +
           record + public display; (3) extra time as real periods.
  Effort:  L total (human ~5d / CC ~2.5h), but each landing S/M
  Risk:    Low per landing                 Completeness: 10/10
  Pros:    Fixes a live bug this week, independently revertable; every later phase
           builds on a shipped, tested base; phase 3 is gated on real usage data
           from phase 2; each phase gets its own migration number (33/34/35), so
           the conftest atomicity constraint is satisfied per phase, not globally.
  Cons:    Three PRs of ceremony instead of one; the operator sees the complete
           flow later than under B.
  Reuses:  Everything in 0B, plus the repo's own established migration cadence.
```

**RECOMMENDATION: C.** Same total completeness as B with a fraction of the per-landing
risk, and it is the only option that lets the expensive half (real ET periods) be
decided on evidence instead of assumption. Maps to the stated preference for the
smallest diff that cleanly expresses the change, without compressing a necessary
rewrite into a minimal patch.

> **AUTO-DECIDED (P1 completeness + P6 bias toward action): Approach C.**
> B is rejected because it welds a live bug fix to a feature. A is rejected as a
> terminal state but *adopted as C's phase 2*.
> **`_piernas_por_ronda` refutes P-2 ten lines from the code the plan cites — the
> "no real competition does this" universal is the single most expensive assumption
> in the draft.** Surfaced at the Final Gate as a taste decision (C3 below), because
> the outside voice argued for A-as-terminal and I disagree.

## 0F. Mode

**SELECTIVE EXPANSION** (feature enhancement on an existing system — context default).
Baseline scope held and hardened; expansions surfaced individually below.

## 0D. Selective expansion — cherry-pick decisions

Complexity check: the draft touches 17 files and adds 1 new trigger + 6 columns.
Over the 8-file smell threshold. Approach C splits it into 3 landings of 5-8 files
each, which is the answer to the smell rather than an exception to it.

| # | Expansion candidate | Effort | Decision | Reason |
|---|---|---|---|---|
| E1 | Per-round method variation (`Penales_Salvo_Final`) | S (human ~3h / CC ~20min) | **ACCEPTED** | Corrects a false premise, not an expansion in substance. Blast radius, <1d CC → P2. |
| E2 | `Hubo_Tiempo_Extra` as a separate fact | XS (human ~1h / CC ~10min) | **ACCEPTED** | Without it the plan reintroduces the exact collapse §0 condemns. |
| E3 | `Metodo_Desempate_Aplicable` snapshot on `PARTIDOS` at match start | S (human ~3h / CC ~20min) | **ACCEPTED** | Closes the mid-match rule-change hole AND gives D6 an honest boundary. |
| E4 | "No tengo el marcador de la tanda" escape hatch | XS (human ~1h / CC ~10min) | **ACCEPTED** | Schema's answer to missing data must be NULL, never a guess. |
| E5 | Three adoption metrics (C9) | XS (human ~1h / CC ~10min) | **ACCEPTED** | Otherwise the feature can ship correct, complete and used by nobody, undetected. |
| E6 | Per-shooter penalty log (who took, who saved) | M | **DEFERRED to TODOS.md** | Outside blast radius; a separate data model. §12 already excluded it. |
| E7 | Golden goal / sudden death inside extra time | S | **SKIPPED** | No competition in this product's market uses it; §12 already excluded it. |
| E8 | Make `formato_eliminatoria` editable post-generation alongside the new field | S | **DEFERRED to TODOS.md** | Real gap (C7) but it is the *sibling* column's gap, not this feature's. Resolved here by dropping §8's settings-screen promise instead. |

## 0E. Temporal interrogation

```
  HOUR 1 (foundations)   Which enum values exactly, and does the PARTIDOS snapshot
                         column duplicate the TORNEO one? → D-C1/D-C6: TORNEO holds
                         the RULE, PARTIDOS holds what APPLIED. Same relationship as
                         Formato_Eliminatoria → piernas. Settled here, not at HOUR 1.
  HOUR 2-3 (core logic)  Postgres fires BEFORE UPDATE triggers alphabetically. Does a
                         new trg_partido_validar_metodo_desempate race the existing
                         trg_partido_validar_desempate? → D-A2: don't add a second
                         trigger. Fold the rules into the existing function.
  HOUR 4-5 (integration) _calcular_estado now needs "is the llave tied?", and the
                         cronometro endpoint is polled every 5s (POLL_MS,
                         Cronometro.tsx:6). → D-P1: gate the aggregate query.
  HOUR 6+ (polish/tests) Does the trigger let a tied Tiempo_Extra_Penales match close
                         as 'Manual'? → Yes, deliberately (D-E4). That escape hatch
                         IS metric #3. Stated now so nobody "fixes" it later.
```

## Section 1 — Architecture

```
                         GENERATION                     CLOSE TIME
  ┌────────────────────────────────┐        ┌─────────────────────────────────┐
  │ PasoGenerarPlayoffs            │        │ Cronometro / ModalResultado     │
  │  Formato_Eliminatoria  [today] │        │  periodos extra | tanda penales │
  │  Metodo_Desempate_Elim [NEW]   │        └───────────────┬─────────────────┘
  └───────────────┬────────────────┘                        │
                  ▼                                         ▼
  ┌────────────────────────────────┐        ┌─────────────────────────────────┐
  │ MotorFormatosService           │        │ HitoPartidoService              │
  │  _sortear_bracket / _crear_    │        │  _calcular_estado [EXTENDED]    │
  │  llave  (piernas por ronda)    │        │  registrar(Inicio_Partido)      │
  │                                │        │   └─► snapshot Metodo_Aplicable │
  └───────────────┬────────────────┘        └───────────────┬─────────────────┘
                  │  TORNEO.Metodo_Desempate_Eliminatoria   │
                  │        = the RULE                       │ PARTIDOS.Metodo_
                  └──────────────────┬──────────────────────┘ Desempate_Aplicable
                                     ▼                        = what APPLIED
                  ┌──────────────────────────────────────┐
                  │ 06_triggers.sql                      │
                  │  fn_validar_partido_eliminacion_     │
                  │   desempate  [EXTENDED, not cloned]  │
                  │     ├─ ida empatada legal  (today)   │
                  │     ├─ vuelta exige global (today)   │
                  │     └─ metodo/penales/ET coherence   │
                  │        [NEW rules, same function]    │
                  │  fn_marcador_partido      [UNCHANGED]│
                  │  fn_resolver_llave        [UNCHANGED]│
                  └──────────────────┬───────────────────┘
                                     ▼
                  BracketView · PartidosDelTorneo · DetalleTorneoPublico
                       "2-2 a.e.t. (4-2 pen.)"
```

**D-A1 — CRITICAL GAP (found by primary review, not by the outside voice).** The
draft enforces "you must play extra time before penalties" only in
`acciones_permitidas`, which is service-layer. `ModalResultadoDirecto` and any direct
`PATCH /partidos/{id}` bypass it: a tied `Tiempo_Extra_Penales` match can be closed
with `Metodo_Desempate='Manual'` and the whole feature is silently skipped.
**Auto-decided (P1):** this is *allowed on purpose* (D-E4 needs the escape hatch) but
must be **visible**, not silent — the service logs a structured
`desempate_manual_sobre_metodo_configurado` line and it is adoption metric #3. Stated
in the plan so nobody later "fixes" it into a hard rejection and breaks paper-sheet entry.

**D-A2 — Do not add a second trigger.** Postgres fires `BEFORE UPDATE` triggers in
alphabetical order by name. A new `trg_partido_validar_metodo_desempate` would sort
after `trg_partido_validar_desempate` — correct today, but an undocumented, silent
dependency on trigger naming. **Auto-decided (P4 DRY + P5 explicit):** fold the new
coherence rules into the existing `fn_validar_partido_eliminacion_desempate`. One
function, one place, no ordering dependency. Supersedes §5's "trigger nuevo".

**Coupling:** `HitoPartidoService` gains a read of `TORNEO`/`PARTIDOS` tie state it did
not have. Justified — it already reads `CONFIGURACION_TIEMPO_TORNEO` for the same
decision. **Rollback:** all new columns are nullable or defaulted; reverting the code
leaves the columns inert. Rollback = `git revert`, no down-migration. **Scaling:** see
Section 7. **SPOF:** none new.

## Section 2 — Error & Rescue Registry

```
  METHOD/CODEPATH                        | WHAT CAN GO WRONG                      | ERROR
  ---------------------------------------|----------------------------------------|---------------------------------
  fn_validar_partido_eliminacion_        | Penales_* set but method != 'Penales'  | metodo_desempate_incoherente
   desempate [EXTENDED]                  | Penales_Local == Penales_Visitante     | tanda_penales_empatada
                                         | Ganador_Desempate contradicts tanda    | ganador_desempate_contradice_tanda
                                         | Metodo/Penales written on an IDA       | desempate_en_ida_no_permitido
                                         | Penales_* out of 0..99                 | tanda_penales_fuera_de_rango
                                         | Metodo NULL but Ganador_Desempate set  | desempate_sin_metodo
  HitoPartidoService._calcular_estado    | Torneo has no CONFIGURACION_TIEMPO row | AttributeError on None  ← GAP
                                         | Cantidad_Periodos_Extra NULL on a      | int + None TypeError    ← GAP
                                         |  pre-migration Periodos tournament     |
  HitoPartidoService.registrar           | Inicio_Periodo beyond the extra tope   | 400 hito_no_permitido (existing)
   (extra period)                        | Method flipped between poll and click  | stale tope → 400
  PartidoService.resultado_directo       | Penales sent for a Corrido tournament  | penales_no_aplican_a_corrido
                                         | Penales sent, method is Manual         | metodo_desempate_incoherente
  MotorFormatosService.generar_playoffs  | Method invalid for a Corrido torneo    | DomainRuleError (new validation)

  ERROR                                  | RESCUED? | RESCUE ACTION                  | USER SEES
  ---------------------------------------|----------|--------------------------------|---------------------------------
  metodo_desempate_incoherente           | Y        | 400 via handlers.py            | "El método y el marcador de la tanda no coinciden."
  tanda_penales_empatada                 | Y        | 400                            | "Una tanda de penales no puede terminar empatada."
  ganador_desempate_contradice_tanda     | Y        | 400                            | "El ganador no coincide con el marcador de la tanda."
  desempate_en_ida_no_permitido          | Y        | 400                            | "El desempate se registra en la vuelta, no en la ida."
  tanda_penales_fuera_de_rango           | Y        | 400 + CHECK (defence in depth) | "Marcador de tanda inválido."
  desempate_sin_metodo                   | Y        | 400                            | "Falta indicar cómo se resolvió el empate."
  CONFIGURACION_TIEMPO row missing       | N ← GAP  | —                              | 500  ← BAD
  Cantidad_Periodos_Extra NULL           | N ← GAP  | —                              | 500  ← BAD
  penales_no_aplican_a_corrido           | Y        | 400                            | "Este torneo no usa penales."
  stale tope (method changed mid-poll)   | Y        | 400 + refetch                  | "La configuración cambió, recargá el cronómetro."
```

**Two GAPs, both auto-decided (P1).** `Cantidad_Periodos_Extra`/
`Duracion_Periodo_Extra_Minutos` ship `NOT NULL DEFAULT 2 / DEFAULT 15` for
`Tipo_Cronometro='Periodos'` rows and the migration backfills existing rows, so the
`None` arithmetic is impossible rather than rescued. The missing-config case is
pre-existing (`_cargar_contexto` already assumes the row exists) — **flagged, not
fixed here**, because widening it is outside this plan's blast radius. Logged as a
TODO candidate below.

**Note:** no catch-all handlers introduced. `handlers.py` already maps `DBAPIError` to
400 — which is how the trigger messages surface. That mapping also hides genuine
`UndefinedColumn` as a validation error (recorded project pitfall,
`migracion-31-portal-publico-no-aplicada`), which is exactly why the three-location
column rule in §10 is load-bearing.

## Section 3 — Security & Threat Model

| Threat | Likelihood | Impact | Mitigated? |
|---|---|---|---|
| Client posts an arbitrary `ganador_desempate_id` not matching the shootout | Med | High (wrong team advances, whole bracket corrupted) | **Yes** — the trigger derives/verifies it server-side; the client's value is checked, never trusted. |
| `Penales_Local = 2147483647` (int overflow / absurd acta) | Low | Med | **Yes, added** — `CHECK BETWEEN 0 AND 99`. Not in the draft. |
| A `TorneoAdmin` of tournament A edits tournament B's method | Low | High | **Existing RBAC** — the torneo update path is already scoped; no new endpoint is introduced (D-C7 drops the settings surface). |
| Method flipped mid-match to force a favourable resolution | Low | **High — this is competition integrity, not a bug** | **Yes, added** — D-C6 snapshot at `Inicio_Partido`; the rule in force when the match started is the rule that applies, and it is recorded on the row. |
| Audit trail for the flip | Med | Med | **Yes** — `AUDITORIA` already covers `TORNEO` updates (`18_migracion_auditoria_cambios.sql`); the new column rides along with no extra work. |

No new endpoints, no new secrets, no new dependencies, no PII. Injection: all values
are enum/int through SQLAlchemy params.

## Section 4 — Data flow & interaction edge cases

```
  INPUT ─────▶ VALIDATION ──────▶ TRANSFORM ─────▶ PERSIST ──────▶ OUTPUT
  penales 4/2  method coherent?   derive ganador   UPDATE PARTIDOS  acta/bracket/
  method       in range 0..99?    from tanda       (trigger gate)   portal
    │              │                  │                │               │
    ▼              ▼                  ▼                ▼               ▼
  [null?  → Manual fallback]   [tie? → reject]  [ida? → reject]  [stale poll?
  [empty? → Manual fallback]   [contradicts     [match already     → refetch]
  [Corrido? → field absent]     ganador? → rej]  Finalizado?      [pre-migration
  [pre-migration torneo?                         → existing        row? → NULL
   → 'Manual' default]                            blocker]          renders as today]
```

| Interaction | Edge case | Handled? | How |
|---|---|---|---|
| "Ir a penales" button | Double-click | **Added** | `registrar.isPending` disables, same as every other mesa action. |
| Penalty stepper | Submit with equal scores | **Yes** | Confirm disabled until they differ; trigger is the backstop. |
| Penalty stepper | Operator navigates away mid-entry | **Accepted** | Match stays `En_Curso`; nothing is written until confirm. Same as today's desempate radio. |
| Extra time in progress | Admin flips method in settings | **Added (D-C6)** | Snapshot at `Inicio_Partido` makes the flip a no-op for this match. |
| Extra time in progress | Operator closes the app, reopens | **Yes** | State derives from `HITOS_PARTIDO`, never from client memory (`calcularElapsedMs`). |
| Direct result entry | Tied, method `Tiempo_Extra_Penales`, no ET played | **Added (D-A1)** | Allowed, recorded as `Manual`, logged, counted in metric #3. |
| Direct result entry | "Won on penalties, score unknown" | **Added (D-E4)** | Explicit "no tengo el marcador" → `Manual`, `Penales_*` NULL. |
| Vuelta of a llave | Ida still `En_Curso` | **Yes, existing** | `partido_vuelta_ida_sin_resolver` (`06_triggers.sql:788`) with `FOR UPDATE`. |
| Walkover on one leg | ET/penalties offered? | **Added** | `Es_Walkover` short-circuits before any tie logic — matches the existing 3-0 rule. |
| Bracket view | Llave blocked on an unresolved tie | **Yes, existing** | "Requiere desempate" badge from the llaves plan. |

**Async ordering.** The one schedule that can violate an invariant: two mesa operators,
ida and vuelta of the same llave, finalizing concurrently. Already serialized by the
existing `SELECT … FOR UPDATE` on the ida inside both
`fn_validar_partido_eliminacion_desempate` and `fn_resolver_llave`. The new rules run
inside that same function and therefore inside the same lock — **this is a second
reason not to add a separate trigger (D-A2): a separate function would take the lock
in a second place, or worse, not at all.**

## Section 5 — Code quality

**D-Q1 — naming collision.** `TORNEO` would hold `Formato_Eliminatoria='Mixto'` and
`Metodo_Desempate_Eliminatoria='Mixto'` meaning two different things in the same row.
**Auto-decided (P5 explicit over clever):** name the value `'Penales_Salvo_Final'`.
Self-describing, no collision, reads correctly in a `CHECK` constraint.

**D-Q2 — DRY.** `requiereDesempate` is derived in `MesaPanel.tsx:290` and again in
`ModalResultadoDirecto.tsx:420`, both wrong for ida/vuelta. Phase 1 (D-C4) removes both
derivations in favour of one server field. Root-cause fix at the shared source, not a
guard per caller.

**Cyclomatic complexity:** `_calcular_estado` currently branches 7 times and would
reach ~11 with the ET tope inline. **Auto-decided:** extract
`_periodos_totales_permitidos(partido, torneo, config) -> int` as a private helper,
keeping `_calcular_estado` at its current shape. Mirrors `_piernas_por_ronda`'s own
"one small pure function per rule" pattern.

**Over/under-engineering:** no new abstraction introduced. `Metodo_Desempate_Aplicable`
is not premature — it is load-bearing for D-C6 competition integrity.

## Section 6 — Test review

```
  NEW UX FLOWS          Ir a tiempo extra · Ir a penales · stepper de tanda ·
                        "no tengo el marcador" · selector de método (oculto en Corrido)
  NEW DATA FLOWS        TORNEO.Metodo → snapshot en PARTIDOS → trigger → acta/portal
  NEW CODEPATHS         _periodos_totales_permitidos (helper) ·
                        fn_validar_..._desempate coherence rules (6 branches) ·
                        snapshot en Inicio_Partido · requiere_desempate server-side
  NEW ASYNC WORK        none
  NEW INTEGRATIONS      none
  NEW ERROR PATHS       6 trigger exceptions + 2 service validations (Section 2)
```

| # | Test | Type | Happy | Failure | Edge |
|---|---|---|---|---|---|
| 1 | `requiere_desempate` server-side | Integration | vuelta with tied aggregate → true | ida tied → **false** (today's bug) | walkover leg → false |
| 2 | Trigger coherence | Integration (pytest+asyncpg) | each of 3 methods closes | winner contradicting the shootout → rejected | `Penales_*` on an ida → rejected |
| 3 | Shootout range | Integration | 4-2 accepted | 4-4 rejected | -1 and 100 rejected |
| 4 | `fn_resolver_llave` with an ET goal | Integration | ida 1-1, vuelta 1-0 in the 105' → aggregate 2-1, no desempate needed | — | ET goal in the *ida* is impossible (no ET on an ida) |
| 5 | `_periodos_totales_permitidos` | Unit | tied + `Tiempo_Extra_Penales` → base+extra | not tied → base | `Penales_Directo` → base; `Corrido` → base |
| 6 | Mid-match flip (D-C6) | Integration | flip after `Inicio_Partido` does not change this match's tope | — | flip before start does |
| 7 | Manual escape on a configured tournament | Integration | closes, logs, counted | — | metric #3 increments |
| 8 | Migration idempotency | `test_scripts_sql.py` | runs twice clean | — | runs against a pre-migration DB |
| 9 | Per-round rule | Unit | `Penales_Salvo_Final`: Final → ET, Semifinal → penalties | — | **Tercer Lugar → penalties** (not the final) |
| 10 | Corrido tournament | Integration | method forced to `Manual` | method `Penales_Directo` → `DomainRuleError` | selector absent in UI |
| 11 | Frontend | Vitest | stepper renders, confirm gated | equal scores → disabled | "no tengo el marcador" → Manual |

**2am-Friday test:** #2 + #9 together. If the trigger cannot be made to advance the
wrong team, and the per-round rule puts Tercer Lugar on the right side, the bracket is
safe. **Hostile-QA test:** post `ganador_desempate_id` = the team that *lost* the
shootout, directly to the API, bypassing the UI (#2). **Chaos test:** #6, two clients,
one flipping config while the other runs extra time.

**Flakiness risk:** none time/random dependent. `Timestamp_Real` is server-side and the
elapsed calc is derived, not accumulated.

**Pyramid:** 3 unit, 7 integration, 1 frontend suite. Appropriate — the rules live in
SQL, so integration is the honest level. **No LLM/prompt files touched → no evals.**

## Section 7 — Performance

**D-P1 — real finding.** `Cronometro.tsx:6` polls `/cronometro` every `POLL_MS = 5000`.
If `_calcular_estado` computes "is this llave tied?" unconditionally, every open mesa
adds a `vw_goles_acreditados` aggregate (plus, for a vuelta, a second one over the ida)
every 5 seconds, per match, forever — including during the first half, when the answer
cannot matter. **Auto-decided (P3 pragmatic):** compute it only when
`periodo_abierto IS NULL AND ultimo_periodo_cerrado >= Cantidad_Periodos` — i.e. once
regulation is closed, which is the only moment the answer is used. Cost drops from
"every poll of every live match" to "one query per match, once."

Indexes: `vw_goles_acreditados` filters on `EVENTOS_PARTIDO.PARTIDOS_ID`, already
indexed (`03_indexes.sql`). No new index needed. No N+1: the snapshot write is a single
`UPDATE` inside the existing `Inicio_Partido` transaction. Memory: 6 scalar columns.
No new connections.

## Section 8 — Observability

| Need | Status |
|---|---|
| Structured log on the Manual escape (D-A1) | **ADDED** — `desempate_manual_sobre_metodo_configurado` with torneo/partido/method |
| Log on a mid-match method flip attempt | **ADDED** — warn-level, includes which matches were `En_Curso` |
| Metric 1: % of `Eliminacion` tournaments on a non-`Manual` method, 30d | **ADDED (E5)** |
| Metric 2: % of closed tied llaves carrying a shootout score | **ADDED (E5)** |
| Metric 3: `Manual` closes on tournaments configured otherwise (escape rate) | **ADDED (E5)** — if high, the live flow does not fit reality |
| Metric 4: live-timer vs direct-result split for `Eliminacion` closes, 90d | **ADDED** — run **before** committing phase 3 (see D-C10) |
| Debuggability 3 weeks post-ship | **Satisfied** — `HITOS_PARTIDO` + `AUDITORIA` + the 3 new `PARTIDOS` columns reconstruct any tie resolution without logs |
| Runbook: "bracket frozen, llave not advancing" | **ADDED** — check `Metodo_Desempate IS NULL` on a tied vuelta; the trigger raised, the propagation never ran |

No new dashboard infrastructure exists in this project; the metrics are SQL queries in
the plan, not a new subsystem. Stated rather than invented.

## Section 9 — Deployment & rollout

Three landings, three migrations, each independently deployable and revertable:

```
  PHASE 1  no migration (server-side requiere_desempate is pure read)
           deploy backend → deploy frontend. Old frontend + new backend: safe
           (client keeps its own derivation until it's replaced).
  PHASE 2  33_migracion_metodo_desempate.sql
           ALTER TABLE ... ADD COLUMN IF NOT EXISTS (nullable / defaulted)
           → migrate FIRST, deploy second. Old code ignores the new columns.
  PHASE 3  34_migracion_tiempo_extra_periodos.sql
           same shape. Old code reads Cantidad_Periodos and never asks for extra.
```

**The three-location rule applies per phase**, not globally: `01_schema.sql` +
that phase's `NN_migracion_*.sql` + `SCRIPTS_VIGENTES` in `test_scripts_sql.py:36-48`.
This is what makes phasing possible — the outside voice read the conftest constraint as
blocking phasing; it blocks *partial columns within one phase*, which is a different
thing. Verified against `conftest.py:39-47` and the existing 32-migration cadence.

**Deploy-time risk window:** old and new code coexisting is safe in all three phases
because every new column is nullable or defaulted and no existing column changes
meaning. **Rollback:** `git revert` the code; leave the columns. No down-migration,
no data loss. **Feature flag:** not needed — `DEFAULT 'Manual'` *is* the flag; every
tournament stays on today's behavior until an operator opts in. **Post-deploy check
(first 5 min):** close one tied knockout on a staging tournament under each of the 3
methods. **Environment parity:** the recorded project pitfall is a migration written
but never run against local `torneos_mvp` — run each migration with `psql -1` locally
before the phase lands.

## Section 10 — Long-term trajectory

**Reversibility: 4/5.** Additive columns, defaulted to today's behavior, no changed
semantics. The only 1-way element is data operators enter (shootout scores), which is
the point.

**D-T1 — named debt, with its trigger already documented.** `TODOS.md:561-566` parks a
generic `ReglamentoTorneo` object and states its own revisit condition: *"se revisita
si aparece un tercer campo de reglamento además de `minimo_jugadores_para_iniciar` /
`maximo_titulares_permitido` / `permite_cambios_ilimitados`."* This plan adds
`Metodo_Desempate_Eliminatoria` (4th) and, on `CONFIGURACION_TIEMPO_TORNEO`, two more
reglamento-shaped fields. **The documented threshold is crossed.** Auto-decided
(P3 pragmatic): do **not** do the refactor inside this plan — it is Effort L and
outside blast radius — but **record in TODOS.md that the trigger has fired**, so the
next reglamento field lands on a decision already made rather than re-deriving it.
Leaving this unsaid is how the `Fase`/`Fase_ID` duality happened.

**Path dependency:** low. `Metodo_Desempate_Aplicable` on `PARTIDOS` is the exact hook
a future per-llave override would need, so E6/E8 get cheaper, not harder.
**Knowledge concentration:** the repo's house style (rule stated once in SQL with
rationale inline) carries this; each new trigger branch gets its D-number comment.
**The 1-year question:** a new engineer reading `PARTIDOS` will see `Ganador_Desempate_ID`,
`Ganador_Corrido_ID`, `Metodo_Desempate`, `Metodo_Desempate_Aplicable`,
`Hubo_Tiempo_Extra`, `Penales_*` and `Es_Walkover` — seven columns about "how did this
end". **That is a lot.** Mitigated by a single block comment in `01_schema.sql`
mapping each to its one question; required, not optional.

## Section 11 — Design & UX (CEO level; depth deferred to Phase 2 design review)

| Feature | LOADING | EMPTY | ERROR | SUCCESS | PARTIAL |
|---|---|---|---|---|---|
| Method selector (generation) | n/a | n/a | inline | radio checked | — |
| "Ir a tiempo extra" | `isPending` | n/a | `apiErrorMessage` | period opens | — |
| Penalty stepper | `isPending` | **"no tengo el marcador"** ← E4 | inline | match closes | scores entered, not confirmed |
| Public result | skeleton | — | — | "2-2 a.e.t. (4-2 pen.)" | "IDA 1-1 · VTA pend." (existing) |

**Information architecture:** the operator's question at the end of regulation is "what
now?", and the answer must be the button label itself — "Ir a tiempo extra" / "Ir a
penales", never a generic "Finalizar" that then reveals a modal. The draft gets this
right. **Subtraction:** the method selector is *omitted*, not disabled, for `Corrido`
(§7) — correct. **AI slop risk:** low; the plan reuses the existing radio/stepper
idiom rather than inventing a "tiebreak wizard". **Trust:** the public record is where
trust is won here (see the reframing below) — "se definió por penales 4-2" is a
shareable fact; a bare "2-2" with an unexplained winner reads as a bug to a player.

**Recommendation carried to Phase 2:** the public rendering deserves its own design
pass, which is exactly what the next phase of this pipeline provides.

## Step 0.5 — Dual voices

**Codex: unavailable** (`CODEX_MODE: not_installed`) — falling back to a Claude
subagent (fresh context, same harness; model identity unknown). Tagged
`[subagent-only]`. Missing outside coverage is reported as such, never as agreement.

**CLAUDE SUBAGENT (CEO — strategic independence): completed, 10 findings + 1 reframing.**
Verdict: *"Approve the problem, reject the shape."* Findings C1-C10 plus a housekeeping
item; minimum bar to proceed: fix C1, fix C2, split per C5, answer C6, add C9 metrics
and run C10's query.

```
CEO DUAL VOICES — CONSENSUS TABLE:
═══════════════════════════════════════════════════════════════════════════
  Dimension                             Claude(native)  Subagent  Consensus
  ───────────────────────────────────── ─────────────── ───────── ─────────
  1. Premises valid?                    3 of 8 false    3 critical   N/A
  2. Right problem to solve?            Yes             Yes          N/A
  3. Scope calibration correct?         No — phase it   No — phase   N/A
  4. Alternatives sufficiently explored? No (0C-bis     No (C3)      N/A
                                         added 3)
  5. Competitive/market risks covered?  No metrics      No (C9)      N/A
  6. 6-month trajectory sound?          Yes, 1 debt     2 regrets    N/A
═══════════════════════════════════════════════════════════════════════════
Outside (Codex) unavailable → all six Consensus cells N/A, never CONFIRMED.
Native and subagent findings are recorded separately above and below.
Single-voice criticals flagged: C1 (subagent), D-A1 and D-A2 (native).
```

### Native/subagent disposition

| Ref | Finding | Disposition |
|---|---|---|
| C1 | Tournament-wide method is a false universal; `_piernas_por_ronda` refutes it | **ACCEPTED** (E1). Verified independently. Adds `'Penales_Salvo_Final'`, keyed on `Ronda_Nombre='Final'`. Tercer Lugar correctly falls on the penalties side. |
| C2 | ET-then-penalties is indistinguishable from direct penalties | **ACCEPTED** (E2). Implemented as `Hubo_Tiempo_Extra BOOLEAN`, not a composite enum — two orthogonal facts, two columns (P5). Not derivable from `HITOS_PARTIDO` because the direct-result path writes no hitos. |
| C3 | "ET as a flag without new periods" dismissed in 23 words | **PARTIALLY REJECTED → TASTE DECISION.** The middle option does not exist as described: without an open period the live timer has no minute to attach an ET goal to, so "flag only" silently means "ET is unusable live". C3's *other* half (penalties-only first) is **accepted as phase 2**. |
| C4 | Live bug fix welded to a feature | **ACCEPTED.** Phase 1, alone. |
| C5 | No phasing | **ACCEPTED** as Approach C, with one correction: the conftest rule constrains columns *within* a phase, not phasing itself. Each phase gets its own migration number. |
| C6 | Method editable mid-match retroactively invalidates an open ET period | **ACCEPTED** (E3), resolved better than either option offered: snapshot `Metodo_Desempate_Aplicable` at `Inicio_Partido`. Makes D6's boundary honest ("until the match *starts*") instead of vague ("until it's played"). |
| C7 | §8 promises a settings edit surface that `formato_eliminatoria` itself lacks | **ACCEPTED.** Verified: `TorneosAdmin.tsx:437-442` exposes only `incluye_tercer_lugar`/`clasificados_por_grupo`; `formato_eliminatoria` is create-only. **Resolution: drop §8's settings promise**, edit at `PasoGenerarPlayoffs` only — consistent with the sibling column. Making both editable → TODOS (E8). |
| C8 | Operators forced to invent shootout scores | **ACCEPTED** (E4). |
| C9 | Zero success metrics | **ACCEPTED** (E5), 3 metrics + a 4th from C10. |
| C10 | Unstated premise that operators use the live timer | **ACCEPTED as a gate on phase 3**, not on the plan. One query, run before phase 3 is scheduled. |
| — | Reframing: the value is the public record, not the timer | **ACCEPTED into phase ordering.** Phase 2 = the record; phase 3 = the timer, gated on evidence. This is the reframing and C5 arriving at the same answer from two directions, which is why it carries weight. |
| — | Housekeeping: annotate the superseded plan | **ACCEPTED**, 2 minutes. |

## Failure Modes Registry

```
  CODEPATH                        | FAILURE MODE                          | RESCUED? | TEST? | USER SEES?       | LOGGED?
  --------------------------------|---------------------------------------|----------|-------|------------------|--------
  trigger coherence (6 rules)     | incoherent method/tanda/winner        | Y        | Y(#2) | 400 + message    | Y
  trigger, ida                    | desempate written on an ida           | Y        | Y(#2) | 400 + message    | Y
  shootout range                  | 4-4, -1, 100                          | Y        | Y(#3) | 400 + message    | Y
  _periodos_totales_permitidos    | offers ET when not tied               | Y        | Y(#5) | button unchanged | n/a
  snapshot at Inicio_Partido      | method flipped mid-match              | Y        | Y(#6) | flip is a no-op  | Y (warn)
  direct result, configured tourn.| closes as Manual, skipping the feature| PARTIAL  | Y(#7) | nothing (by design)| Y ← metric #3
  fn_resolver_llave + ET goal     | aggregate not updated                 | Y        | Y(#4) | bracket advances | n/a
  Corrido tournament              | penalties offered                     | Y        |Y(#10) | control absent   | Y
  migration                       | column only in the migration script   | Y        | Y(#8) | (tests fail loud)| Y
  CONFIGURACION_TIEMPO row missing| _calcular_estado 500                  | N ← GAP  | N     | 500              | N
```

**1 CRITICAL GAP**, pre-existing and outside blast radius (`_cargar_contexto` already
assumes the config row exists for every torneo). Flagged, not silently absorbed;
TODO below.

**The row worth reading twice:** `direct result on a configured tournament` is
RESCUED=PARTIAL / USER SEES=nothing **on purpose**. It is the escape hatch (E4) that
keeps paper-sheet entry honest, and its visibility is metric #3 rather than an error.
Any future reviewer who "fixes" it into a hard rejection breaks the dominant amateur
workflow.

## NOT in scope

- **Per-llave method override** — the `Metodo_Desempate_Aplicable` column is the hook; the UI is not built. Per-round via `Penales_Salvo_Final` covers the real configurations.
- **Away-goals rule** — carried over from the llaves plan, restated so it cannot drift in.
- **Per-shooter penalty log** (E6) — separate data model, TODOS.
- **Making `formato_eliminatoria` editable post-generation** (E8) — the sibling column's gap, not this feature's. TODOS.
- **Sudden death / golden goal** (E7) — no competition in this market uses it.
- **Extra time or penalties in Grupos/Liga** — the concept does not exist there.
- **`ReglamentoTorneo` refactor** (D-T1) — Effort L; recorded in TODOS as "trigger fired".
- **Widening the missing-`CONFIGURACION_TIEMPO` 500** — pre-existing; TODOS.

## Diagrams produced

System architecture (Section 1), data flow with shadow paths (Section 4), deployment
sequence (Section 9), error flow (Section 2 registry), test coverage map (Section 6),
dream-state delta (0C). **Stale diagram audit:** the ASCII bracket/llave diagrams in
`cierre-fase-regular-llaves-playoffs-plan.md:941, 1001-1043` show
`Ganador_Desempate` as the terminal tie resolution. **They go stale the moment phase 2
lands** — annotating that plan (the housekeeping item) covers it.

```
  +====================================================================+
  |            MEGA PLAN REVIEW — COMPLETION SUMMARY (CEO)             |
  +====================================================================+
  | Mode selected        | SELECTIVE EXPANSION                         |
  | System Audit         | every touched file in the 30d hot set;      |
  |                      | 3rd plan over the same code; TODOS:71-73    |
  |                      | parks this feature on the false premise     |
  | Step 0               | Approach C (3 phases); 8 premises tested,   |
  |                      | 3 false and corrected                       |
  | Section 1  (Arch)    | 2 issues found (D-A1 critical, D-A2)        |
  | Section 2  (Errors)  | 11 error paths mapped, 2 GAPS (1 fixed,     |
  |                      | 1 pre-existing and flagged)                 |
  | Section 3  (Security)| 5 threats, 1 High (mid-match flip) mitigated|
  | Section 4  (Data/UX) | 11 edge cases mapped, 0 unhandled           |
  | Section 5  (Quality) | 3 issues found (naming, DRY, complexity)    |
  | Section 6  (Tests)   | Diagram produced, 11 specs, 0 gaps          |
  | Section 7  (Perf)    | 1 issue found (5s poll aggregate) — fixed   |
  | Section 8  (Observ)  | 7 gaps found, all closed                    |
  | Section 9  (Deploy)  | 0 risks flagged after phasing               |
  | Section 10 (Future)  | Reversibility: 4/5, debt items: 1 (D-T1)    |
  | Section 11 (Design)  | 0 blocking; deferred to Phase 2             |
  +--------------------------------------------------------------------+
  | NOT in scope         | written (8 items)                           |
  | What already exists  | written (9 mappings)                        |
  | Dream state delta    | written                                     |
  | Error/rescue registry| 11 methods, 0 CRITICAL GAPS introduced      |
  | Failure modes        | 10 total, 1 CRITICAL GAP (pre-existing)     |
  | TODOS.md updates     | 4 items proposed                            |
  | Scope proposals      | 8 proposed, 5 accepted, 2 deferred, 1 skip  |
  | CEO plan             | written                                     |
  | Outside voice        | codex: unavailable (not installed);         |
  |                      | claude subagent: completed, 10 findings     |
  | Lake Score           | 4/4 recommendations chose the complete opt. |
  | Diagrams produced    | 6 (arch, data flow, deploy, error, test,    |
  |                      | dream state)                                |
  | Stale diagrams found | 2 (llaves plan :941, :1001-1043)            |
  | Unresolved decisions | 0 (1 taste decision queued to Final Gate)   |
  +====================================================================+
```

