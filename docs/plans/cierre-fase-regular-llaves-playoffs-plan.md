<!-- /autoplan restore point: "C:\\Users\\Gabo\\.gstack\\projects\\Score-App\\main-autoplan-restore-20260915-230156.md" -->
> **Superado en parte por `docs/plans/desempate-tiempo-extra-penales-plan.md`
> (2026-09-17).** Este plan cerró el desempate de eliminatoria registrando
> solo QUIÉN ganó (`PARTIDOS.Ganador_Desempate_ID`), deliberadamente sin el
> CÓMO — ese plan revierte esa decisión: suma `Metodo_Desempate`, `Penales_
> Local/Visitante`, `Hubo_Tiempo_Extra` y `Metodo_Desempate_Aplicable` al
> lado de `Ganador_Desempate_ID` (que se MANTIENE, no se reemplaza). Los dos
> diagramas ASCII de bracket/llave más abajo (§941, §1001-1043) muestran
> `Ganador_Desempate` como la resolución TERMINAL del desempate — desde la
> Fase 2 de ese plan, dejaron de estar completos.
# Cierre de Fase Regular, Motor de Llaves y Flexibilidad de Grupos

Pedido del 2026-09-16. Tres requerimientos encadenados sobre el Motor de
Formatos existente (`motor-formatos-plantillas-navegacion-plan.md`,
`control-mesa-reactividad-playoffs-plan.md`):

1. Detectar el fin de la fase regular y ofrecer "Configurar Siguiente Fase"
   con dos caminos excluyentes (cierre directo con campeones, o playoffs).
   En Formato Grupos el cierre directo no existe.
2. Selector de formato de eliminatoria: Único, Ida y Vuelta, Mixto.
3. La fase de grupos debe poder jugarse a partido único o ida y vuelta.

## Qué existe hoy (verificado en el código)

- `TORNEO.formato`: `Liga` | `Eliminacion` | `Grupos_Playoffs`
  (`backend/app/models/torneo.py:38`). `ida_vuelta` (bool),
  `equipos_por_grupo`, `clasificados_por_grupo`, `incluye_tercer_lugar`.
- `FASE` (`backend/app/models/fase.py`): `tipo` ∈ Liga|Grupos|Eliminacion,
  `orden`, `estado` ∈ Pendiente|En_Curso|Finalizada. Decisión G1: UNA fase
  para todo el bracket, el nombre de ronda se denormaliza en
  `PARTIDOS.ronda_nombre`.
- `MotorFormatosService` (`backend/app/services/motor_formatos.py`, 450
  líneas): `generar_fixture` (Liga), `sortear` (bracket o grupos),
  `generar_playoffs` (cruce grupos→bracket), `bracket` (lectura).
- `_sortear_bracket` crea **un** `PARTIDO` por cruce. El encadenamiento
  vive en `PARTIDOS.partido_siguiente_id` / `slot_siguiente` y
  `partido_perdedor_siguiente_id` / `slot_perdedor_siguiente`.
- `fn_propagar_ganador_bracket` (`database/06_triggers.sql:602`) resuelve
  ganador por goles de UN partido y lo empuja al siguiente.
- `fn_validar_partido_eliminacion_desempate` (`06_triggers.sql:559`) exige
  `Ganador_Desempate_ID` en cualquier partido de fase Eliminación que
  termine empatado en goles.
- `_sortear_grupos` llama `algoritmo_fixture_liga(..., ida_vuelta=False)`
  **hardcodeado** (`motor_formatos.py:213`).
- `TorneoService._validar_parametros_formato` (`services/torneo.py:211`)
  **rechaza** `ida_vuelta=True` en formatos distintos de Liga, y
  `clasificados_por_grupo` en formatos distintos de Grupos_Playoffs.
- `generar_playoffs` rechaza cualquier formato que no sea
  `Grupos_Playoffs`. No hay camino Liga → eliminatoria.
- **No existe ningún concepto de campeón** en el código ni en el esquema
  (`grep -i campe` no devuelve nada). Terminar un torneo hoy es solo
  `TORNEO.estado = 'Finalizado'`, sin podio.
- Frontend: `MotorFormatosPanel.tsx` (233 líneas) decide qué botón mostrar
  escaneando `partidos` en el cliente; `BracketView.tsx` pinta el bracket.

## Implementation plan

### Fase A — Modelo de datos (`database/32_migracion_cierre_fase_y_llaves.sql`)

Tres bloques de columnas nuevas, todas nullable o con default, sin backfill
destructivo.

**A1. Podio del torneo** (`TORNEO`):

| Columna | Tipo | Default | Para qué |
|---|---|---|---|
| `Campeon_Equipo_ID` | INT FK equipos | NULL | 1er puesto |
| `Subcampeon_Equipo_ID` | INT FK equipos | NULL | 2do puesto |
| `Tercer_Puesto_Equipo_ID` | INT FK equipos | NULL | 3er puesto |
| `Fecha_Cierre` | TIMESTAMP | NULL | cuándo se cerró |

Los tres son nullable porque un torneo en curso no tiene podio, y porque un
torneo de 2 equipos no tiene tercer puesto.

**A2. Formato de eliminatoria** (`TORNEO`):

| Columna | Tipo | Default | Valores |
|---|---|---|---|
| `Formato_Eliminatoria` | VARCHAR(20) | `'Unico'` | `Unico` \| `Ida_Vuelta` \| `Mixto` |

CHECK `chk_torneo_formato_eliminatoria`. Default `'Unico'` reproduce el
comportamiento actual exacto para todo torneo existente — sin esto, una base
vieja cambiaría de comportamiento al aplicar la migración.

**A3. Encadenamiento de llave a dos partidos** (`PARTIDOS`):

| Columna | Tipo | Default | Para qué |
|---|---|---|---|
| `Partido_Ida_ID` | INT FK partidos | NULL | en el partido de VUELTA, apunta al de IDA |

Una sola columna, autorreferencial, mismo patrón que el
`Partido_Siguiente_ID` que ya existe. El partido de IDA **no** lleva
`Partido_Siguiente_ID` (no propaga solo); el de VUELTA sí. "Es ida" se
deriva: un partido es IDA si otro lo referencia. No se agrega una columna
`Es_Vuelta` redundante — `Partido_Ida_ID IS NOT NULL` ya lo dice.

**Por qué no una tabla `LLAVE` nueva.** Agrupar los 2 partidos en una
entidad "llave" es el modelo conceptualmente más limpio, pero obliga a mover
el encadenamiento de `PARTIDOS` a `LLAVE` y reescribir
`fn_propagar_ganador_bracket`, `_sortear_bracket`, `bracket()` y
`BracketView.tsx` enteros. Una columna autorreferencial cubre lo mismo con
el patrón que el bracket ya usa. Si más adelante aparecen llaves a 3
partidos, ahí sí conviene la tabla.

**A4. Flexibilidad de grupos — sin columna nueva.** Requerimiento 3 se
resuelve **reusando `TORNEO.ida_vuelta`**, que ya existe y hoy está
prohibido en Grupos_Playoffs. Se relaja `_validar_parametros_formato` para
aceptarlo en `Grupos_Playoffs` con el significado "round robin doble dentro
de cada grupo", y `_sortear_grupos` deja de hardcodear `False`. No se agrega
`Grupos_Ida_Vuelta`: sería una segunda columna con exactamente la misma
semántica.

**A5. Disciplina de migración** (aprendizaje registrado, confianza 10/10):
`backend/tests/conftest.py` arma la base de tests SOLO con
`01_schema.sql`..`06_triggers.sql`. Cada columna nueva va en **tres**
lugares o los ~40 archivos de test revientan con `UndefinedColumn`:

1. `database/01_schema.sql` (estado final del esquema),
2. `database/32_migracion_cierre_fase_y_llaves.sql` (idempotente con
   `IF NOT EXISTS` — `test_scripts_sql.py` lo corre **dos veces**),
3. la lista `SCRIPTS_VIGENTES` de `backend/tests/test_scripts_sql.py:36-48`.

Más `02_constraints.sql` (FK + CHECK), `06_triggers.sql` (Fase B) y una
entrada en `database/README.md`.

### Fase B — Motor: resolución de llaves a dos partidos (SQL)

**B1. Helper compartido `fn_marcador_partido(p_partido_id INT)`** que
devuelve `(goles_local, goles_visitante)` aplicando la regla de walkover
(3-0 al presente) y contando `vw_goles_acreditados` si no lo hay. Hoy esa
lógica está duplicada en `fn_propagar_ganador_bracket` y en
`fn_validar_partido_eliminacion_desempate`; la llave a dos partidos la
necesitaría una tercera vez. Se extrae una vez y los dos triggers existentes
pasan a llamarla — arreglo en la raíz, no un guard por llamador.

**B2. `fn_resolver_llave(p_partido_vuelta_id INT)`** → `equipo_ganador_id`.
Suma `fn_marcador_partido` de IDA y de VUELTA (invirtiendo local/visitante
en la vuelta). Si el global está empatado, devuelve
`PARTIDOS.Ganador_Desempate_ID` de la VUELTA.

**Regla de gol de visitante: NO se implementa.** Empate global se resuelve
por desempate manual registrado en la vuelta, igual que hoy se resuelve un
empate de partido único. Las competencias grandes la eliminaron (UEFA 2021)
y el sistema ya registra "quién ganó", no "cómo". Fuera de alcance explícito.

**B3. `fn_propagar_ganador_bracket` — tres ramas:**

- Partido sin `Partido_Ida_ID` y sin nadie que lo referencie: comportamiento
  actual, intacto.
- Partido de **IDA** (otro partido lo referencia): **no propaga nada**.
  Termina y espera la vuelta.
- Partido de **VUELTA**: propaga el resultado de `fn_resolver_llave`, no el
  de su propio marcador. El perdedor al Tercer Lugar sale de la misma
  resolución.

**B4. `fn_validar_partido_eliminacion_desempate` — dos correcciones:**

- Un 0-0 en la **IDA** es legal. Hoy el trigger lo rechazaría pidiendo
  `Ganador_Desempate_ID`. La validación se saltea en partidos de ida.
- En la **VUELTA** la validación se aplica sobre el **global** de la llave,
  no sobre el marcador de ese partido: 1-0 en la vuelta tras perder 0-1 la
  ida está empatado globalmente y sí exige desempate; 2-2 en la vuelta tras
  ganar 1-0 la ida no exige nada.

**B5. Orden de borrado en `_preparar_rehacer_si_corresponde`.**
`motor_formatos.py:130` borra los `PARTIDOS` de la fase uno por uno. Con la
FK autorreferencial nueva, borrar la IDA antes que la VUELTA viola la FK.
Se ordena el borrado (vueltas primero, o `ON DELETE SET NULL` en
`Partido_Ida_ID`). Se verifica con un test dedicado de "rehacer sorteo con
llaves ida y vuelta".

### Fase C — Motor: generación de llaves y cierre (Python)

**C1. `_sortear_bracket` acepta `formato_eliminatoria`.** Para cada cruce y
cada shell de ronda, decide 1 o 2 partidos:

- `Unico`: 1 partido por cruce. Camino actual, sin cambios de forma.
- `Ida_Vuelta`: 2 partidos por cruce en **todas** las rondas, Final incluida.
- `Mixto`: 2 partidos en todas las rondas **menos** la Final, que es 1.

Reglas transversales:

- **Localía**: la IDA la juega de local el primer equipo del cruce; la
  VUELTA invierte. El que cierra de local es el mejor sembrado (el que viene
  primero del cruce de grupos / de la tabla).
- **Tercer Lugar: siempre partido único**, en los tres formatos. No es una
  ronda del bracket, es un partido de consolación; ninguna competencia real
  lo juega a doble partido. Decisión a confirmar en el gate.
- **Shells de ronda 2+**: cada shell pasa a ser 2 shells encadenados
  (`Partido_Ida_ID`), ambos con los equipos en NULL hasta que el trigger los
  complete. La vuelta lleva `Partido_Siguiente_ID`; la ida no.
- **Byes**: sin cambios — un equipo con bye no juega ida ni vuelta.
- **Caso `rondas <= 1`** (exactamente 2 equipos, la Final es el único
  partido): bajo `Ida_Vuelta` son 2 partidos; bajo `Mixto` y `Unico`, 1.
- `ronda_nombre` se mantiene idéntico en ambas piernas ("Semifinal" las dos);
  la distinción ida/vuelta la da `Partido_Ida_ID`, no el nombre.
- `fecha_partido`: la vuelta se programa 7 días después de la ida, mismo
  criterio que las jornadas de liga (`timedelta(days=7)`).

**C2. `generar_playoffs` se generaliza a Liga.** Hoy rechaza todo formato
que no sea `Grupos_Playoffs`. Pasa a aceptar:

- `Grupos_Playoffs`: camino actual (`_cruzar_grupos`, 1°A-2°B…).
- `Liga`: **nuevo** `_cruzar_tabla_unica(tabla, n)` — siembra estándar sobre
  la tabla única: 1 vs N, 2 vs N-1, 3 vs N-2… Es el cruce correcto para una
  liguilla; `_cruzar_grupos` no aplica (no hay grupos).
- `Eliminacion`: sigue rechazando (ya es un bracket).

El `n` de clasificados sale de `Torneo.clasificados_por_grupo`, reusado para
Liga con el significado "cuántos de la tabla pasan a la liguilla". Una sola
columna en vez de dos con semántica idéntica; se documenta en el modelo.
`_validar_parametros_formato` se relaja para aceptarla en Liga.

La guarda de fase completa se mantiene tal cual: todos los partidos de la
fase en `Finalizado` **o `Cancelado`**. El pedido dice "100% Finalizado",
pero un partido cancelado nunca pasa a Finalizado y dejaría el torneo
trabado para siempre. Se mantiene la regla vigente y se nombra en la UI
("N de M resueltos").

**C3. Cierre del torneo — `cerrar_torneo(torneo_id, usuario_id)`.** Nuevo
método. Resuelve el podio y lo persiste:

- Fase actual `Liga`: podio = primeros 3 de
  `EstadisticasRepository.tabla_posiciones(torneo_id)`, con el mismo
  `ORDER BY pts, dg, gf, orden_manual, equipo` que ya usa el sistema.
- Fase actual `Grupos`: **no se ofrece** (ver C4) — la tabla de grupos no
  produce un orden global comparable.
- Fase actual `Eliminacion`: campeón y subcampeón salen de la Final
  resuelta (vía `fn_resolver_llave` si es a doble partido); tercero, del
  partido de Tercer Lugar si existe, NULL si no.

Efectos: setea los tres FK del podio + `Fecha_Cierre`,
`FASE.estado = 'Finalizada'`, `TORNEO.estado = 'Finalizado'`. Idempotente y
rechazado si el torneo ya está cerrado.

**Alcance ampliado sobre el pedido (declarado, no silencioso):** el pedido
solo pide podio en el cierre directo (Opción A). Un torneo que sí juega
playoffs también termina con campeón, y sin esto quedaría con las tres
columnas en NULL para siempre. El cierre por final de bracket usa el mismo
método. Radio de explosión: el mismo servicio y la misma tabla, sin
infraestructura nueva.

**C4. Estado de fase como fuente única — `GET /torneos/{id}/estado-fase`.**
Hoy `MotorFormatosPanel.tsx` reimplementa en el cliente la regla de "fase
terminada" (`partidosGrupos.every(...)`) que el backend ya tiene en
`generar_playoffs`. Agregar Liga duplicaría la regla por tercera vez. Se
expone una vez:

```json
{
  "fase_actual": { "id": 7, "nombre": "Liga", "tipo": "Liga", "estado": "En_Curso" },
  "partidos_total": 30,
  "partidos_resueltos": 30,
  "fase_completa": true,
  "acciones_disponibles": ["cerrar_directo", "generar_playoffs"],
  "torneo_cerrado": false,
  "podio": null
}
```

`acciones_disponibles` es lo que hace la UI condicional trivial y deja la
regla del pedido en un solo lugar:

| Formato | Fase actual | acciones_disponibles |
|---|---|---|
| Liga | Liga completa | `["cerrar_directo", "generar_playoffs"]` |
| Grupos_Playoffs | Grupos completa | `["generar_playoffs"]` — sin cierre directo |
| Liga o Grupos_Playoffs | Eliminacion, Final resuelta | `["cerrar_directo"]` |
| Eliminacion | Final resuelta | `["cerrar_directo"]` |
| cualquiera | fase incompleta | `[]` |

Que la Opción A no exista en Formato Grupos es **regla del servidor**, no
una rama del componente: `cerrar_torneo` la rechaza con 400 aunque alguien
llame el endpoint a mano.

### Fase D — API

| Método | Ruta | Cuerpo | Notas |
|---|---|---|---|
| GET | `/torneos/{id}/estado-fase` | — | `require_torneo_access`, no público |
| POST | `/torneos/{id}/cerrar` | — | 400 si fase Grupos, si fase incompleta o si ya está cerrado |
| POST | `/torneos/{id}/playoffs` | `+ formato_eliminatoria` | extiende `PlayoffsRequest` |

`PlayoffsRequest` suma
`formato_eliminatoria: Literal["Unico","Ida_Vuelta","Mixto"] | None = None`.
Igual que `clasificados_por_grupo` (Gate Final T2 de
`control-mesa-reactividad-playoffs-plan.md`): si se manda, **se persiste**
en `Torneo.formato_eliminatoria`; si no, se usa el guardado.

`PartidoOut` expone `partido_ida_id` para que `BracketView` pueda agrupar.
`TorneoOut` expone las columnas del podio y `formato_eliminatoria`.

Después de tocar schemas: `cd frontend && npm run gen:api` (regenera
`src/api/schema.d.ts` contra el OpenAPI vivo). Sin eso el frontend tipado
no compila contra las rutas nuevas.

### Fase E — Frontend

**E1. `MotorFormatosPanel.tsx`** deja de escanear `partidos` para decidir y
consume `GET /estado-fase`. Cuando
`fase_completa && acciones_disponibles.length > 0`, muestra el botón
primario **"Configurar Siguiente Fase"**. Cuando `torneo_cerrado`, muestra
el podio en vez de acciones.

**E2. `ModalSiguienteFase`** (nuevo, patrón `.modal-panel` ya establecido en
`ModalClasificadosPorGrupo` — nunca `window.prompt`). Dos pasos:

- **Paso 1 — camino.** Dos opciones mutuamente excluyentes como radios, no
  dos botones sueltos: "Terminar el torneo (campeones por tabla)" y "Jugar
  Playoffs". El primero **no se renderiza** si `cerrar_directo` no está en
  `acciones_disponibles` (Formato Grupos). El modal nunca muestra una opción
  que el servidor va a rechazar.
- **Paso 2a — cierre directo.** Preview del podio leído de la tabla de
  posiciones (1°, 2°, 3° con nombre de equipo y puntos) + confirmación
  explícita: es una acción de una sola vía, el usuario ve exactamente a
  quién está coronando antes de apretar.
- **Paso 2b — playoffs.** Absorbe el `ModalClasificadosPorGrupo` existente
  (clasificados por grupo / de la tabla) y suma el **selector de formato de
  eliminatoria**: tres radios con subtítulo explicando cada uno ("Único: un
  partido por cruce, hasta la final" / "Ida y vuelta: dos partidos por
  cruce, final incluida" / "Mixto: ida y vuelta salvo la final, a un
  partido"). Precargado con `Torneo.formato_eliminatoria`.

`ModalClasificadosPorGrupo` se **absorbe**, no se duplica: hoy es el único
paso previo a generar playoffs y ahora es el paso 2b del mismo flujo.

**E3. `BracketView.tsx`** agrupa por llave: cuando un partido tiene
`partido_ida_id`, se pintan las dos piernas juntas con el global
("Ida 1-0 · Vuelta 1-1 · Global 2-1"). Un bracket `Unico` se sigue viendo
exactamente igual que hoy.

**E4. Podio.** Cuando el torneo está cerrado, `TorneoDashboard` muestra el
podio (1°/2°/3°) arriba. El portal público (`DetalleTorneoPublico.tsx`)
también, si el torneo está `publicado`.

### Fase F — Tests

Backend (`backend/tests/`):

- `test_motor_formatos_llaves.py` (nuevo): generación de bracket en los 3
  formatos y en los 3 tamaños críticos (2, 4, 8 equipos); Mixto con final a
  un partido; conteo exacto de partidos por ronda; localía invertida en la
  vuelta; Tercer Lugar siempre único; rehacer sorteo con llaves (FK B5).
- `test_db_triggers_motor_formatos.py` (extender): ida 0-0 no exige
  desempate; vuelta empatada en global sí lo exige; global desempatado no;
  propagación solo desde la vuelta; walkover en una de las dos piernas suma
  3-0 al global.
- `test_cierre_torneo.py` (nuevo): podio por tabla en Liga; rechazo en
  Grupos; podio por bracket con y sin Tercer Lugar; fase incompleta → 400;
  cierre doble → 400; torneo de 2 equipos deja tercero NULL.
- `test_motor_formatos.py` (extender): Liga → playoffs (liguilla) con
  `_cruzar_tabla_unica`; grupos a ida y vuelta duplican los partidos del
  grupo; `estado-fase` devuelve las acciones correctas en cada combinación
  de la tabla de C4.
- `test_torneos.py` (extender): `_validar_parametros_formato` acepta
  `ida_vuelta` en Grupos_Playoffs y `clasificados_por_grupo` en Liga.
- `test_scripts_sql.py`: agregar `32_migracion_cierre_fase_y_llaves.sql` a
  `SCRIPTS_VIGENTES` (corre el script dos veces — la idempotencia es parte
  del test).

Frontend (`vitest`):

- `MotorFormatosPanel.test.tsx` (extender): botón "Configurar Siguiente
  Fase" solo con `fase_completa`; en Formato Grupos el modal no ofrece
  cierre directo; selección de formato de eliminatoria llega al POST.
- `ModalSiguienteFase.test.tsx` (nuevo): exclusividad de los dos caminos,
  preview de podio, los 3 radios de formato.
- `BracketView.test.tsx`: agrupación ida/vuelta y cálculo del global.

Verificación: `cd backend && pytest`, `cd frontend && npm run verify`.

### Orden de ejecución

A (migración) → B (triggers SQL) → C (servicio) → D (API + `gen:api`) →
E (frontend). F se escribe junto a cada fase, no al final.

B depende de A. C depende de B (los tests de C fallan sin los triggers).
E depende de D (`schema.d.ts`). A/B son un bloque atómico: la migración sin
los triggers deja columnas que nadie respeta.

### Qué NO está en alcance

- **Regla de gol de visitante** en el desempate de llaves (B2).
- **Llaves a 3+ partidos** (triangulares, formato Apertura/Clausura).
- **Tercer Lugar a doble partido** (siempre único, C1).
- **Reprogramación de fechas** de las piernas: la vuelta se agenda +7 días
  automático; mover fechas ya se hace por la edición manual de partidos.
- **Cambiar el formato de eliminatoria después de generado el bracket**: se
  rehace el sorteo con el flujo existente
  (`_preparar_rehacer_si_corresponde`) mientras no haya resultados.
- **Formato Eliminacion puro con Ida_Vuelta desde el sorteo inicial**: el
  selector vive en el flujo de "Configurar Siguiente Fase", que es
  post-fase-regular. Un torneo `Eliminacion` puro no tiene fase regular.
  Se resuelve exponiendo `formato_eliminatoria` en el alta del torneo —
  **una línea de schema**, pero es alcance distinto al pedido; a decidir en
  el gate.

### Premisas que corrijo del pedido

1. **"100% de los partidos en Finalizado"** → la condición real es
   `Finalizado` **o** `Cancelado`. Un partido cancelado nunca llega a
   Finalizado; con la regla literal, cualquier torneo con una cancelación
   queda trabado sin poder cerrar ni pasar a playoffs. Es la regla que
   `generar_playoffs` ya aplica hoy.
2. **"Opción A define 1ro, 2do y 3ro"** → un torneo de 2 equipos no tiene
   tercero. `Tercer_Puesto_Equipo_ID` queda NULL, no se inventa.
3. **El pedido solo pide podio en la Opción A** → también se corona al
   terminar los playoffs (C3). Sin eso, el camino B nunca produce campeón.

### Preguntas abiertas

- ¿El Tercer Lugar a partido único en los tres formatos, o sigue al formato
  elegido? (Recomendado: siempre único.)
- ¿Reusar `clasificados_por_grupo` para la liguilla de Liga, o columna
  propia `clasificados_a_playoffs`? (Recomendado: reusar.)
- ¿`formato_eliminatoria` también en el alta de un torneo `Eliminacion`
  puro? (Fuera del pedido literal, una línea de schema.)


<!-- autoplan-accepted:ceo -->
- Desempate UI for `ganador_desempate_id` ships as Phase 0, before any two-legged work, modelled on the existing `ganador_corrido_id` control in `Cronometro.tsx`. Verify: a tied elimination match can be closed from the UI (`npm run verify` + a control-mesa test).
- `fn_marcador_partido` resolves winner-of-match, not goals: walkover to the present team, Corrido to `Ganador_Corrido_ID`, otherwise goals. Verify: `test_db_triggers_motor_formatos.py` proves a Corrido bracket advances.
- `POST /torneos/{id}/reabrir` ships in the same release as `cerrar_torneo`, clearing the three podium FKs and `Fecha_Cierre` and restoring `TORNEO.estado` and `FASE.estado`. Verify: `test_cierre_torneo.py` close-reopen-reclose round trip.
- Result writes are rejected on a closed tournament, reusing the archived-tournament guard pattern at `services/partido.py:212`. Verify: a mesa write against a closed tournament returns 400.
- `cerrar_torneo` rejects with a specific 400 when podium slots are tied through `gf`, and the close modal lets the admin order the tied teams explicitly. The server validates each submitted team is inscribed and is genuinely tied with the team it displaces. Verify: `test_cierre_torneo.py` tie cases.
- `cerrar_torneo` validates the standings table has at least as many rows as podium slots and that every podium team has PJ > 0; `generar_playoffs` validates the qualifier count before `_sortear_bracket`. Verify: a 3-team Liga with one unplayed team returns 400; an all-cancelled group returns 400.
- A vuelta cannot be finalised while its ida is not `Finalizado` or `Cancelado`, enforced in the same BEFORE trigger. Verify: finalising the vuelta first returns 400.
- Byes are assigned by seed rank, not by cross-list position, fixing the latent case in `_cruzar_grupos` as well. Verify: 2/4/6/8 qualifiers each give byes to the top seeds.
- B5 collapses to `ON DELETE SET NULL` on `Partido_Ida_ID`, matching `02_constraints.sql:249-250`. Delete ordering is not an alternative. Verify: rehacer sorteo with two-legged ties.
- B1 lands as its own commit with zero behavior change and existing trigger tests green, before any `Partido_Ida_ID` work.
- Bracket dates get real round spacing: round R at `fecha_base + 7*R`, vuelta at +3 days. Verify: `test_motor_formatos_llaves.py` date assertions.
- The stored podium renders as a snapshot ("Podio confirmado el {Fecha_Cierre}") and `estado-fase` flags when the computed top-3 differs from it.
- `_sortear_bracket` extracts `_crear_llave(padre, slot, formato, es_final)` so it keeps one branch per concept. Verify: `test_motor_formatos_algoritmos.py`.
- The VUELTA carries `partido_perdedor_siguiente_id` / `slot_perdedor_siguiente` for the Tercer Lugar hookup.
- `formato_eliminatoria` is exposed at tournament creation so a pure `Eliminacion` tournament can be two-legged.
- `_validar_parametros_formato`'s combined `equipos_por_grupo`/`clasificados_por_grupo` condition is split, with per-format error text.
- `Mixto` stays in the generator and the UI. The user named all three formats; cutting one is not a reviewer's call.
- Missing UI states ship: empty standings, close-rejected-on-tie, and ida-played/vuelta-pending in `BracketView`. The three-radio selector and the podium preview are checked at 375px.
- `cerrar_torneo` and `reabrir_torneo` each emit a structured log line naming torneo_id, usuario_id, resolved podium and fase transition.
- The `_sortear_bracket` docstring and the `fn_propagar_ganador_bracket` comment are updated to describe the two-legged shape in the same commit.
- The format-distribution query runs before coding: `SELECT formato, estado, COUNT(*) FROM TORNEO GROUP BY 1,2`.
- The `Preguntas abiertas` section is resolved in-plan and removed: Tercer Lugar always single; `clasificados_por_grupo` reused (pending Taste Decision T3); `formato_eliminatoria` at creation.
- Palmares across editions is deferred to TODOS.md, not built here.
- Bracket date spacing is exactly: round R at `fecha_base + 7*R`, vuelta at ida + 3 days. This supersedes the "+7 dias" wording in Implementation plan C1, which is struck.
- The alphabetical-tie defect is NOT fully covered by the close modal. `_cruzar_tabla_unica` must reject or surface a gf-level tie that straddles the qualification cut, because seeding a liguilla off an alphabetically-broken tie is the same defect one step earlier. `EstadisticasDelTorneo.tsx` and the public standings must render tied teams as tied rather than implying a ranking the data does not support. Taste Decision TD1 is restated accordingly: the close modal covers the podium write only.
- The closed-tournament write-guard is enforced in the trigger layer, not at one call site. Verified: the archived-tournament pattern needed two guards (`services/partido.py:211` and `services/hito_partido.py:144`, invoked at :315 and :362) and `services/evento_partido.py` has none at all, so a single-site lock would leave goals and cards writable on a closed tournament and the standings would keep moving. A BEFORE trigger rejecting writes when `TORNEO.estado = 'Finalizado'` covers PARTIDOS, EVENTOS_PARTIDO and HITOS_PARTIDO at once, and every future path. Verify: a goal recorded against a closed tournament returns 400.
- Manual podium ordering from the tie-resolution modal persists across `reabrir_torneo` and re-close: `reabrir` clears the three podium FKs, so the chosen order of tied teams is stored separately and re-offered as the default on re-close, never silently discarded.
- Taste decisions are labelled TD1/TD2/TD3 so they stop colliding with implementation tasks T1/T2/T3.
- PRE-EXISTING BUG, flagged not fixed here: `services/evento_partido.py` has no archived-tournament guard, so goals and cards can be recorded against an archived tournament today. `services/partido.py:197-198` calls that exact case "un agujero" and plugged it only for `registrar_resultado_directo`. CORRECTION to the earlier claim in this block that the closed-tournament trigger fixes it for free: it does not. Verified `chk_torneo_estado` is `Activo|Inactivo|Finalizado` (`02_constraints.sql:53`) while archived is `TORNEO_GRUPO.estado IN ('Activo','Archivado')` (`:38`) — different table. Covering archived needs a `TORNEO -> TORNEO_GRUPO` join in the same trigger. Do that, or the hole gets its own TODO; it does not come for free either way.
- PRECEDENCE: where this accepted block and the Implementation plan body disagree, this block wins. Specifically superseded and no longer authoritative in the body: the `Preguntas abiertas` section, the "a decidir en el gate" deferrals for `formato_eliminatoria` at creation and for Tercer Lugar, the "+7 dias" vuelta wording in C1, and the T1/T2/T3 taste-decision labels (now TD1/TD2/TD3).
- `fn_marcador_partido` return contract, stated once: it returns `(ganador_equipo_id, goles_local, goles_visitante)`. B1's "devuelve (goles_local, goles_visitante)" is superseded. `fn_resolver_llave` sums goals for goal-scored disciplines; for a Corrido llave it counts leg wins. Corrido rule: one win each is a tie and falls through to `Ganador_Desempate_ID` of the vuelta, same as a goal tie.
- A `Cancelado` leg contributes 0-0 and no leg win to the aggregate. It never blocks the vuelta (F12's guard accepts `Finalizado` or `Cancelado` on the ida).
- `POST /torneos/{id}/cerrar` takes `CerrarTorneoRequest { orden_podio: list[int] | None }` — the admin's explicit ordering of teams tied through gf, or null to take the table as-is. Section 3's "takes no body, so no input validation surface" is superseded: the server validates every submitted id is inscribed in the tournament and is genuinely tied with the team it displaces.
- Manual podium ordering needs storage, which Fase A1 does not define. Add `TORNEO.Orden_Podio_Manual JSONB NULL` in A1 — unless TD1 resolves toward `INSCRIPCIONES_TORNEO.orden_manual`, which subsumes it and is then the only place the order lives.
- `POST /torneos/{id}/reabrir` is missing from the Fase D table. Add it: `require_roles("TorneoAdmin")` + `require_torneo_access()`, no body, 400 if the tournament is not closed. It sets `TORNEO.estado = 'Activo'`, returns the last `FASE` to `En_Curso`, clears the three podium FKs and `Fecha_Cierre`, and leaves `Orden_Podio_Manual` intact so the admin does not redo it.
- The direct-close rejection keys on the CURRENT FASE tipo, never on `Torneo.formato`. C4's prose says "Formato Grupos" and the API table says "fase Grupos"; the formato reading would make every `Grupos_Playoffs` tournament permanently unclosable, including after its playoffs finish. Fase tipo is the rule.
- `cerrar_torneo` REJECTS with 400 when the tournament is already closed. It is not idempotent. The "idempotente y rechazado" wording in C3, the "400 idempotente" in the data-flow diagram and "idempotent-or-reject" in Section 4 all collapse to: reject with 400.
- `estado-fase` computes the podium-divergence flag only when `torneo_cerrado` is true. Section 7's "one count query" holds for the open-tournament path, which is the one that gets polled; a closed tournament adds one `tabla_posiciones` call per dashboard open.
- The write-guard trigger ships in the SAME release as `reabrir_torneo`, never before it. Section 9's "nothing to revert" is too optimistic otherwise: migration 32 alone would freeze every already-`Finalizado` tournament with no escape hatch.
- Write-guard trigger scope, stated explicitly: INSERT/UPDATE/DELETE on `EVENTOS_PARTIDO` and `HITOS_PARTIDO`, UPDATE on `PARTIDOS`. Exempt: the writes `cerrar_torneo` and `reabrir_torneo` make themselves. `_preparar_rehacer_si_corresponde` needs no exemption because it cannot run on a closed tournament. Cost is a 2-hop lookup on the hottest write path in the app — measure it against the existing evento-insert path before shipping, and if it registers, denormalize `Torneo.estado` onto `PARTIDOS` rather than accepting the join.
- Existing fixtures that seed a `Finalizado` tournament and then write matches or events will start failing once the guard lands. Audit `backend/tests/` for that pattern as part of the same change.
- Out-of-order leg finalisation with two concurrent mesa operators needs `SELECT ... FOR UPDATE` on the ida inside `fn_resolver_llave`'s read; the BEFORE-trigger guard alone does not serialize them.
- Tournaments already at `estado='Finalizado'` keep NULL podium columns. No backfill: their podium was never recorded and cannot be reconstructed reliably. They are reopenable via `reabrir_torneo` and closeable again if an organizer wants the podium filled in.
- Effort, stated once because the body disagrees with itself: base plan (Approach A, Fases A-F) is human ~1.5 weeks / CC ~3-4h. The review-accepted additions are human ~4-5 days / CC ~3h. Total human ~3 weeks / CC ~7h. The 16 implementation tasks cover review-surfaced work only; Fases A-F carry no task entries by design.
<!-- /autoplan-accepted:ceo -->


<!-- autoplan-accepted:design -->
- The podium renders ONCE, in `TorneoDashboard`'s header region beside `Estado:` (`TorneoDashboard.tsx:154`), visible from every tab; `MotorFormatosPanel` returns null when `torneo_cerrado`. This resolves hard rejection #7 (verified: four `<div className="card">` returns at `MotorFormatosPanel.tsx:96,111,130,144` plus `BracketView`, and plan E1+E4 would have added a sixth and seventh rendering the same three names). Verify: one podium per page.
- The podium is one block with three rows, never three cards: 1° at ~1.5rem weight 800 as the page's visual anchor, 2° and 3° at body weight beneath. Rank colors, if used, are `--podio-oro`/`--podio-plata`/`--podio-bronce` on `:root`, never hardcoded hex.
- A degenerate podium renders explicit copy, never a blank slot: "2 equipos — sin tercer puesto." in place of the third row when `Tercer_Puesto_Equipo_ID` is NULL.
- The primary button label is derived from `acciones_disponibles`, not hardcoded: both actions → "Configurar Siguiente Fase"; `cerrar_directo` alone → "Cerrar Torneo"; `generar_playoffs` alone → "Generar Playoffs". Per the plan's own C4 table a resolved final yields `["cerrar_directo"]`, where "Configurar Siguiente Fase" mislabels a tournament-ending action.
- `MotorFormatosPanel` gets one `<h3>` per state naming the area ("Fase de Grupos", "Fase Eliminatoria", "Resultado final"), then one line of state, then one action. Verified: the panel body currently has zero headings.
- Loading: the action zone renders a skeleton with reserved height so the button does not pop in and the panel does not shift when `GET /estado-fase` resolves. The plan converts a client-derived render into a network read and must not introduce layout shift doing it.
- Busy: both `POST /cerrar` and `POST /playoffs` disable their button, show a label ("Cerrando…" / "Generando llaves…") and guard against double submit. An 8-team two-legged bracket writes ~14 rows.
- Errors render inline inside the modal, never a toast, mapped per cause across all six 400s the plan defines. The user must be able to read the error and correct it without reopening the modal.
- `BracketView` renders four llave states, not one: unplayed; ida played and vuelta pending (the state a two-legged bracket spends most of its life in); blocked on an unresolved aggregate tie; and walkover on one leg. The blocked state gets a "Requiere desempate" badge and a CTA into the vuelta — without it the trigger silently stops propagating and the bracket freezes with no stated reason.
- One node = one llave. A card with two compact leg rows, a `border-top` divider, and the aggregate on its own row at weight 700. Column count and scroll model stay identical to `Unico`; `.bracket__columna` widens from 180px to 220px when a llave has legs (`.bracket` already scrolls horizontally).
- `.bracket__partido` gains a date header row (`tabular-nums`, `--text-muted`, same treatment as `.fila-partido__hora` at `index.css:2032`). Round spacing makes dates the thing organizers publish and there is currently no slot for them anywhere in the bracket.
- The desempate control is inline in the existing save flow, not a second modal: a required radio group above `.confirmar-evento__acciones` with the real team names, reusing the disabled-reason `<p className="muted">` slot that `ModalResultadoDirecto.tsx:772` already uses for incomplete goals. Radios, not a select.
- Tie resolution in the close modal is an ordered list using `.alineacion-fila` + `.alineacion-fila__mover` (verified 56×44px at `index.css:1625/1670`), NOT `CeldaOrdenManual`'s numeric input — a number field accepts 1/1/2 in a three-way tie and fails server-side after submit, while a reorder list cannot express an invalid order.
- The podium preview shows Pts · DG · GF per row and a per-row note whenever the position is decided below points ("Desempatado por diferencia de gol"). A title decided by `orden_manual` gets a prominent notice, not a footnote.
- The one-way confirm names the act: "Cerrar torneo y coronar a {Equipo}", never "Confirmar". The consequence line ("No vas a poder cargar mas resultados") sits in the step-1 radio itself, not only in step 2a.
- A closed tournament explains itself with `.banner-info-persistente` (`index.css:1824`, `--warning`, `aria-live="polite"`) on Partidos and Control de Mesa: "Torneo cerrado el {fecha}. Los resultados estan bloqueados." A lock with no stated cause reads as a broken app.
- Reabrir reuses `.boton-cierre-forzado` + `.cierre-forzado-confirmar` (`index.css:689/706`) — the app's established treatment for reversing a committed state, whose own comment requires it never look like a routine close. No new modal.
- The podium carries its provenance: "Podio confirmado el {Fecha_Cierre}". On divergence from the live table, a `--warning` strip NAMES the delta ("La tabla actual ya no coincide: 1° seria Leones. Reabri el torneo y volve a cerrarlo.") — never a generic "los datos cambiaron", never a silent re-snapshot, never two podiums side by side.
- "N de M resueltos" is replaced everywhere by the three-part count: "28 jugados · 2 cancelados · 0 pendientes". The corrected Finalizado-or-Cancelado rule must be visible; "30 de 30 resueltos" to someone with two cancellations reads as a system error.
- The incomplete phase is a first-class state, not an absence: the heading plus the three-part count as the stated reason the action is unavailable.
- The format selector shows consequence, not mechanics: a live computed line per option ("14 partidos · la final cae aprox. el {fecha}") plus "La vuelta se agenda 7 dias despues de la ida. Podes mover las fechas despues desde cada partido."
- `ModalSiguienteFase` gets a step model: "Paso 1 de 2 · Camino" / "Paso 2 de 2 · Playoffs", a "← Volver" in the action row, and `.modal-panel--ancho` (560px) for step 2 only. Returning to step 1 preserves step 2b's selections — losing them would regress the current `ModalClasificadosPorGrupo`.
- Focus management is added ONCE on the shared `.modal-panel`: focus trap, Escape to close, focus return to the trigger. Verified gap: `ModalClasificadosPorGrupo` sets `aria-modal="true"` today with none of the three, and the longer two-step flow would deepen it.
- Decision-critical copy moves off `.muted` (verified 0.85rem = 13.6px at `index.css:199`) onto a new `.muted--cuerpo { font-size: 1rem; color: var(--text-muted); }`. Applies to the format subtitles, the podium provenance date and every disabled-reason. `.muted` itself is unchanged — it is load-bearing across the app. Contrast already passes at ~6.3:1.
- Both the path choice and the format choice are radio groups, not selects: every option visible without a tap, keyboard and screen-reader native.
- On successful close the modal closes, the page scrolls to the podium, and there is exactly one reveal. It respects `prefers-reduced-motion`.
- Scores and dates added to the bracket and standings use `font-variant-numeric: tabular-nums`.
- The plan introduces no new color, shadow or font. Any new surface cites the existing `index.css` class it extends.
- NOT fixed here, flagged: `index.css:30` uses `system-ui` as the body voice (AI-slop blacklist #11) and browser surfaces (selection, caret, scrollbars, focus rings) are unthemed. Both are app-wide and pre-existing; they belong to `/design-consultation`, not this plan.
- Visual mockups were NOT generated despite `DESIGN_READY`, because the surface is OPERATE inside a fixed token system and every finding resolves to an existing class with a line number. Recorded as taste decision TD4 so the user can override at the gate.
- CRITICAL, from the second design pass over the amended plan: the closed-tournament write-guard trigger rejects writes on EVENTOS_PARTIDO, HITOS_PARTIDO and PARTIDOS — that is every scoring interaction in the product. A mesa operator would tap "gol" mid-match and get a raw 400 with no explanation. Scoring controls are DISABLED BEFORE the attempt, never failing after it: `Cronometro.tsx` and the resultado-directo surface render a locked state with the persistent cause banner, every control disabled, and a link to Reabrir for a `TorneoAdmin`. Verify: no scoring control is clickable on a closed tournament, and none produces a raw server error.
- Reabrir gets an explicit entry point in the closed-state panel next to the podium, with a confirm that names both consequences: "Se borra el podio registrado; el orden manual se conserva." A non-admin viewing a closed tournament sees the podium and no Reabrir control at all.
- The gf tie is DETECTED AT PREVIEW, not rejected after confirm. Step 2a already reads `tabla_posiciones`, so the tie is knowable before the user clicks: render the tied rows as tied and inline the ordering control before enabling confirm. The 400 stays as a server guard, never as the primary path. The same principle applies to `_cruzar_tabla_unica`: surface a tie straddling the qualification cut at preview time rather than rejecting afterwards.
- Two of the six `cerrar_torneo` rejections must never reach the user: fase-tipo-Grupos and already-closed are both knowable from `estado-fase`, so the control is ABSENT in those states rather than present-and-rejecting. The plan already states this invariant ("el modal nunca muestra una opcion que el servidor va a rechazar"); it is extended to every case. The remaining rejections get a copy table mapping each to user-facing text plus the recovery action.
- When `acciones_disponibles` has exactly one entry, step 1 of the modal is SKIPPED and the primary button is labelled for that action. A one-option radio screen is a dead step.
- Corrido (non-goal) disciplines get their own aggregate copy. "Global 2-1" is meaningless for Tenis or Ajedrez, where a llave is decided on leg wins with one-each falling through to `Ganador_Desempate_ID`. Second variant: "Ida: Equipo A · Vuelta: Equipo B · Definido por desempate: Equipo A", and the format radio subtitles say "cruce" rather than implying scorelines.
- `BracketView` specifies three explicit card variants, not one: the single-leg card (unchanged), the llave card (two result rows plus a global row, connectors anchored to the card), and the EMPTY-SHELL llave card — an unsorted `Ida_Vuelta` bracket is two empty cards per slot and doubles the visual noise of a bracket that has not started. Under `Mixto` the final column uses the single-leg variant inside a double-leg bracket, which makes that column asymmetric by design.
- The 375px check covers `BracketView` in all three formats and the tie-ordering interaction, not only the radio selector and podium preview. Those are the two components that actually break at that width. Tie ordering uses up/down buttons, never drag — drag-to-reorder at 375px is a known trap.
- The podium divergence flag is ADMIN-ONLY and neutral in tone ("El podio registrado no coincide con la tabla actual — registrado el {fecha}") with Reabrir as the adjacent action. It never appears on the public portal: a public viewer told "this podium might be wrong" is worse off than one seeing a stale podium.
- Step 2a's confirm disables on submit with an in-button pending state and locks modal dismissal while in flight. It triggers a multi-write server operation; double-submit on a slow connection produces a confusing "ya esta cerrado" 400 from the user's own second click.
<!-- /autoplan-accepted:design -->
## Review record

## Phase 1 — CEO Review (SELECTIVE EXPANSION, /autoplan auto-decided)

Run: autoplan-20260915-230236-566 · branch main · base main · 2026-09-16

### Pre-review system audit

- Clean tree except `database/README.md` (+1 line). No stashes. Two branches
  (`main`, `feat/equipos-jugadores-plan`, both pushed).
- Hot files last 30 days: `index.css` (17), `TODOS.md` (17), `schema.d.ts` (15),
  `01_schema.sql` / `02_constraints.sql` (14), `App.tsx` (13),
  `06_triggers.sql` (11), `services/torneo.py` / `services/partido.py` (9),
  `test_scripts_sql.py` (9). The schema + trigger layer this plan rewrites is
  the most-churned part of the repo. Review it harder.
- No real `TODO`/`FIXME`/`HACK` markers in project source — every hit is the
  Spanish word "TODO"/"TODOS" or a reference to `TODOS.md`. Clean.
- Design doc: `docs/designs/frontend-inicial-dashboard-mesa-en-vivo.md`
  (different feature, no constraints on this one).
- `TODOS.md`: triaged 2026-09-01 into `cierre-backlog-todos-plan.md`. It parks
  penalties/extra-time on the premise that "un torneo que los usa hoy los
  resuelve como ya lo hace (`Ganador_Desempate_ID`)". **That premise is false**
  — see Finding 1.
- Retrospective: `control-mesa-reactividad-playoffs-plan.md` and
  `motor-formatos-plantillas-navegacion-plan.md` already reworked this exact
  area. Third pass over the same code. Recurring area → reviewed adversarially.
- Taste references: `motor_formatos.py` (dense but well-commented, every edge
  case named with its EC-number), `06_triggers.sql` (business rules stated once
  in SQL with the rationale inline). Anti-pattern to avoid: the `PARTIDOS.fase`
  (text) / `PARTIDOS.fase_id` duality that the motor de formatos left behind —
  two sources of truth for the same fact.

### 0A. Premise challenge

| # | Premise | Verdict |
|---|---|---|
| P1 | "El sistema debe detectar cuándo el 100% de los partidos estén Finalizado" | **WRONG AS STATED.** A `Cancelado` match never reaches `Finalizado`. Taken literally, one cancellation deadlocks the tournament forever. `generar_playoffs` already uses `Finalizado OR Cancelado` (`motor_formatos.py:412`). Queued as a Gate item. |
| P2 | "Definir campeones (1ro, 2do, 3ro) basándose estrictamente en la tabla final" | **WRONG IN A WAY THAT CROWNS THE WRONG TEAM.** Verified: `vw_tabla_posiciones` joins `GRUPO_EQUIPO ON ge.Grupo_ID = l.Grupo_ID` (`04_views.sql:319`); a Liga has `Grupo_ID IS NULL`, so `orden_manual` is **always NULL** there. Two teams level on pts/dg/gf are separated by `ORDER BY ... Equipo` — alphabetically. "Estrictamente la tabla" has no tiebreak of last resort in Liga. Finding 2. |
| P3 | "Al terminar los grupos, obligar a transicionar a Playoffs" | **VALID.** A group table produces no global ordering, so a direct podium is meaningless. The plan encodes it server-side, not as a UI branch. Accepted. |
| P4 | Implicit: a bracket match produces a winner from goals | **WRONG FOR MOST OF THE CATALOG.** `11_catalogo_disciplinas.sql` ships 28 disciplines (Tenis, Ajedrez, LoL, Natación…). `Ganador_Corrido_ID` exists for them, but `fn_propagar_ganador_bracket` never reads it. Finding 3. |
| P5 | Implicit: closing a tournament is safe because it is final | **WRONG.** `TORNEO.estado` is read by zero services (verified). Closing locks nothing, and nothing reopens. Finding 4. |
| P6 | Doing nothing is not an option | **VALID.** A tournament today has no ending: the last match finishes and the app just stops. No champion, no state change, no artifact. Real pain, not hypothetical. |

### 0B. Existing code leverage map

| Sub-problem | Existing code | Reuse? |
|---|---|---|
| Detect phase complete | `generar_playoffs` guard, `motor_formatos.py:409-413` | Yes — promote to `estado-fase`, single source |
| Standings for podium | `EstadisticasRepository.tabla_posiciones` + `vw_tabla_posiciones` | Yes, with the Liga tiebreak gap fixed |
| Bracket generation | `_sortear_bracket`, byes, Tercer Lugar wiring | Yes — extended, not rebuilt |
| Cross groups → bracket | `_cruzar_grupos` (EC-50) | Yes for Grupos; Liga needs `_cruzar_tabla_unica` |
| Round-robin inside a group | `algoritmo_fixture_liga(ids, ida_vuelta)` — already parameterised | Yes — requirement 3 is unhardcoding one `False` |
| Winner propagation | `fn_propagar_ganador_bracket` | Yes — extended with the aggregate branch |
| Walkover scoring | `Es_Walkover` branch in the same trigger | Yes — extracted to `fn_marcador_partido` |
| Modal pattern | `ModalClasificadosPorGrupo` (`.modal-panel`, no `window.prompt`) | Yes — absorbed into `ModalSiguienteFase` |
| Blocking writes on a frozen tournament | `PartidoService` archived-guard, `services/partido.py:212` | **Not reused by the plan — should be.** Finding 4 |
| Manual tiebreak | `GRUPO_EQUIPO.orden_manual` + its PATCH | **Unreachable from Liga.** Finding 2 |
| Non-goal winner | `Ganador_Corrido_ID` + its validator (`06_triggers.sql:752`) | **Not reused by the plan — must be.** Finding 3 |

Nothing in the plan rebuilds something that exists. The failure is the
opposite: three existing mechanisms the plan walks past.

### 0C. Dream state

```
  CURRENT STATE                    THIS PLAN                    12-MONTH IDEAL
  Tournaments have no        --->  Tournaments end.       --->  A tournament ends in a
  ending. Last match              Champion persisted.          shareable artifact: public
  finishes, app stops.            Brackets can be two-         champion page, palmares
  Bracket = single match          legged. Groups can be        across editions of a
  only. Liga cannot reach         double round-robin.          TORNEO_GRUPO, every
  a playoff. Champion is          Closing still does not       discipline finishable,
  something the organizer         lock results (unless         results correctable after
  knows and the app does          Finding 4 is accepted).      the fact without surgery.
  not.
```

### 0C-bis. Implementation alternatives

```
APPROACH A: Self-referential Partido_Ida_ID (the plan as written)
  Summary: one nullable self-FK on PARTIDOS; the vuelta carries the chaining
           and resolves the tie from the aggregate of both legs.
  Effort:  L (human ~1.5 weeks / CC ~3-4h)   Risk: Med
  Pros:    reuses the exact pattern the bracket already uses; no new table;
           BracketView keeps its shape; single-leg path byte-identical.
  Cons:    two live triggers rewritten; "es ida" is a derived fact (a
           reverse lookup), not a stored one.
  Reuses:  Partido_Siguiente_ID pattern, fn_propagar_ganador_bracket.

APPROACH B: LLAVE table (the ideal-architecture option)
  Summary: a tie is a first-class row; chaining moves from PARTIDOS to LLAVE.
  Effort:  XL (human ~3 weeks / CC ~8h)      Risk: High
  Pros:    models the domain honestly; extends to 3-leg ties and to
           per-round leg counts for free.
  Cons:    rewrites _sortear_bracket, both triggers, bracket(), BracketView
           entirely; every existing single-leg bracket needs migrating.
  Reuses:  little.

APPROACH C: No engine — manual second leg (the minimal-viable option)
  Summary: build nothing for requirement 2. The organizer already creates a
           second match by hand and records the winner.
  Effort:  S (human ~1 day / CC ~20min)      Risk: Low
  Pros:    ships requirement 1 and 3 immediately; reversible.
  Cons:    no aggregate anywhere, no propagation — the organizer computes the
           global in their head; AND it is blocked by the same missing
           desempate UI as A and B (Finding 1), so it is not actually zero-cost.
  Reuses:  everything.
```

**RECOMMENDATION: Approach A** — it is the only option that delivers the
requested feature without a rewrite, and B's extra power (3-leg ties,
per-round leg counts) serves no stated need. Maps to "right-sized diff" and
"explicit over clever". C is not viable on its own because the tie it leaves
to the organizer cannot be recorded (Finding 1) — but C's slicing insight is
adopted in the resequencing (Finding 5).

Auto-decided: A. Approach B is the close runner-up on the "per-round leg
count" axis only; that axis resurfaces as Taste Decision T2.

### 0F. Mode

**SELECTIVE EXPANSION** — /autoplan override, and the context default anyway
(feature enhancement on an existing system).

### 0D. Selective-expansion analysis

Complexity check: the plan touches ~18 files across 5 layers (SQL schema,
SQL triggers, Python service, API schemas, React). Over the 8-file smell
threshold. Challenged, and the answer is that it is genuinely three
independent features bundled by the request, not one feature spread thin —
which is exactly why Finding 5 slices it.

Minimum set that achieves the stated goal:
- Requirement 3 = 2 lines (`_validar_parametros_formato:222`,
  `motor_formatos.py:221`).
- Requirement 1 = 4 nullable columns + one service method + one endpoint +
  one modal.
- Requirement 2 = everything else, ~80% of the risk.

Expansion candidates surfaced (cherry-pick ceremony, auto-decided):

| # | Candidate | Effort | Decision | Why |
|---|---|---|---|---|
| E1 | `reabrir_torneo` + write-lock behind `estado='Finalizado'` | S (human ~4h / CC ~20min) | **ACCEPTED** | In blast radius, both voices rated it critical, and the lock is the thing that makes closing mean anything |
| E2 | Desempate UI (`ganador_desempate_id`) | S (human ~4h / CC ~20min) | **ACCEPTED as Phase 0** | Hard prerequisite: without it no tied knockout can be resolved, so requirement 2 is unshippable |
| E3 | `fn_marcador_partido` resolves winner-of-match, not goals | S (human ~3h / CC ~15min) | **ACCEPTED** | Same cost as the goals-only version and fixes an existing critical bug in 20+ disciplines |
| E4 | Real round spacing for bracket dates | S (human ~2h / CC ~10min) | **ACCEPTED** | The plan claimed a +7d criterion that does not exist; the fixture list is the deliverable organizers send out |
| E5 | `formato_eliminatoria` in tournament creation (pure `Eliminacion`) | XS (human ~30min / CC ~5min) | **ACCEPTED** | One schema line; without it the most obvious consumer of the feature cannot reach it |
| E6 | Public "Campeón" page — shareable URL, podium, top scorer, OG tags | M (human ~2d / CC ~1h) | **QUEUED AS USER CHALLENGE** | Both voices independently argued this is the only part that could acquire users, not just retain them. Beyond what was asked. |
| E7 | Palmares across editions of a `TORNEO_GRUPO` | M (human ~2d / CC ~1h) | **DEFERRED to TODOS.md** | Outside blast radius, no stated need, depends on E6 landing first |
| E8 | Extend `orden_manual` to Liga via `INSCRIPCIONES_TORNEO` | M (human ~1d / CC ~40min) | **SKIPPED — superseded** | The root-cause fix for Finding 2, but the explicit-podium modal covers the same failure for a fraction of the cost. Recorded as Taste Decision T1. |

### 0E. Temporal interrogation

```
  HOUR 1 (foundations)   Where does "es ida" live? Derived (reverse lookup on
                         Partido_Ida_ID) — decided, do not add Es_Vuelta.
                         ON DELETE SET NULL on the new self-FK, matching
                         02_constraints.sql:249-250. Not delete ordering.
  HOUR 2-3 (core logic)  Which leg carries partido_perdedor_siguiente_id for
                         Tercer Lugar? The VUELTA — decided.
                         What does fn_marcador_partido return for a Corrido
                         match? Ganador_Corrido_ID, not 0-0 — decided.
                         Aggregate tied => Ganador_Desempate_ID of the vuelta.
  HOUR 4-5 (integration) Byes: con_bye = ids[:byes_n] assigns byes by list
                         position, not seed. With _cruzar_tabla_unica that
                         hands the 6th seed a bye. Fix before wiring Liga.
                         Splitting _validar_parametros_formato's combined
                         equipos_por_grupo/clasificados_por_grupo condition.
  HOUR 6+ (polish/tests) Rehacer-sorteo with two-legged ties.
                         A Liga with fewer than 3 teams in the table.
                         A group where every match was cancelled.
                         Corrido + Ida_Vuelta together.
```

### 0.5 Dual voices

Codex: **unavailable** (CLI not installed; `CODEX_MODE: not_installed`).
Both voices are therefore fresh-context Claude subagents in the same harness;
model identity unknown. Tagged `[subagent-only]` per the degradation matrix.
Their agreement is weaker evidence than a true cross-model agreement would be
— which is why every load-bearing claim below was re-verified against the
code by the primary reviewer before acceptance.

```
CEO DUAL VOICES — CONSENSUS TABLE:
═══════════════════════════════════════════════════════════════
  Dimension                             Native  Outside  Consensus
  ───────────────────────────────────── ─────── ──────── ─────────
  1. Premises valid?                    NO      NO       N/A (no outside model)
  2. Right problem to solve?            YES*    NO*      N/A
  3. Scope calibration correct?         NO      NO       N/A
  4. Alternatives sufficiently explored?NO      NO       N/A
  5. Competitive/market risks covered?  NO      NO       N/A
  6. 6-month trajectory sound?          PARTIAL NO       N/A
═══════════════════════════════════════════════════════════════
Consensus cells are N/A, never CONFIRMED: outside coverage is unavailable,
and a native fallback cannot supply it. Both voices are native.
* Both say requirement 1 is right and requirement 2 is over-invested relative
  to evidence; they differ on how hard to push back.
```

Independent agreement between the two native voices (still only one model
family, so treat as corroboration, not confirmation):

- `reabrir_torneo` is missing and is critical (native #1, outside #2).
- The plan's sequencing buries the valuable part behind the risky part
  (native #2, outside #5).
- The public champion artifact is the reframe the plan misses
  (native #4, outside #12).
- The three `Preguntas abiertas` are decisions wearing questions' clothes
  (native #10, outside #13).
- Stored podium will silently drift from live standings (native #5, outside #2).

Findings unique to one voice, all verified before acceptance:

- Outside only: missing desempate UI (Finding 1), Liga alphabetical champion
  (Finding 2), Corrido unfinishable (Finding 3), bye-by-position (Finding 6),
  `ON DELETE SET NULL` already the convention (Finding 8), cancelled-match
  standings holes (Finding 9), fictional calendar (Finding 10).
- Native only: B1 should land as its own no-op refactor commit first;
  format-distribution query as cheapest de-risking.

The outside voice carried the heavier load here. Every one of its critical
claims reproduced.

### Sections 1-11

**Section 1 — Architecture.** Findings 1-4, 6. Dependency graph, state
machine and the four data paths are in the Diagrams section below. Coupling:
`estado-fase` introduces one new frontend→backend read that *removes* a
duplicated rule from the client, so net coupling drops. Scaling: `estado-fase`
is one count query per dashboard open; `tabla_posiciones` is already the
heaviest view and is unchanged. SPOF: `fn_propagar_ganador_bracket` — every
bracket advance flows through it, and this plan doubles its branches.
Rollback: `git revert` + `ALTER TABLE ... DROP COLUMN`; the four podium
columns and `Partido_Ida_ID` are additive and nullable, so a revert of the
code alone is safe and leaves orphan columns. Stated in Deploy below.

**Section 2 — Error & rescue.** Registry below. Two GAPs found, both fixed
by accepted items (empty standings, closed-tournament writes).

**Section 3 — Security.** Reviewed: the three new endpoints. `estado-fase`
and `cerrar` both carry `require_roles("TorneoAdmin")` +
`require_torneo_access()`, matching every other motor-de-formatos route —
no new authorization surface. `POST /cerrar` takes no body, so no input
validation surface. The podium FKs are written by the server from its own
query, never from client input — unless Taste Decision T1 resolves toward the
explicit-podium modal, in which case the server MUST validate that each
submitted team is inscribed in the tournament and is tied on pts/dg/gf with
the team it displaces. That validation is recorded as an accepted obligation.
`reabrir_torneo` is a privileged state reversal → must write to the existing
`AUDITORIA` table (already automatic via `core/auditoria.py`'s flush hook, so
this is free — verified, no action needed). No new secrets, no new
dependencies, no PII. No injection surface: everything is parameterised
SQLAlchemy or a plpgsql function over integers.

**Section 4 — Data flow & interaction edge cases.** Findings 9, 10. Async
ordering: two legs of a tie can be finalised concurrently by two mesa
operators. `fn_resolver_llave` reads the ida's goals at vuelta-finalise time;
if the ida is finalised *after* the vuelta (out of order — legal today,
nothing enforces leg order), the vuelta's propagation computes an aggregate
against an unfinished ida and advances the wrong team. **Unhandled in the
plan.** Accepted obligation: the vuelta refuses to finalise while its ida is
not `Finalizado`/`Cancelado`, enforced in the same BEFORE trigger.
Double-click on "Cerrar torneo": `cerrar_torneo` is already specified
idempotent-or-reject, which covers it. Navigate-away mid-close: the write is
a single transaction, no partial state.

**Section 5 — Code quality.** Finding 8 (B5 invents a solved problem) and
Finding 7 (B1 mis-sequenced) are both quality findings. DRY: the plan is
strong here — it correctly refuses a second `Grupos_Ida_Vuelta` column and
correctly extracts `fn_marcador_partido`. Cyclomatic complexity:
`_sortear_bracket` already branches 6 times; adding three leg-count formats
pushes it past 10. Accepted obligation: extract leg generation into a helper
(`_crear_llave(padre, slot, formato, ronda_es_final) -> list[Partido]`) so
`_sortear_bracket` keeps one branch per concept, not one per combination.

**Section 6 — Tests.** The plan's Fase F is unusually complete for a first
draft. Gaps found, all accepted: out-of-order leg finalisation; Corrido +
Ida_Vuelta; a Liga tie through gf; a group with every match cancelled; bye
assignment across 2/4/6/8 qualifiers; `reabrir` then re-close. The 2am-Friday
test: "8-team Liga → liguilla of 4 → Ida_Vuelta bracket → champion persisted
→ reopen → correct a result → re-close → podium changed". The hostile-QA
test: finalise the vuelta first. Flakiness risk: `_sortear_bracket` uses
`random.Random(semilla)`; every new test must pass an explicit `semilla`.

**Section 7 — Performance.** No N+1 introduced. `estado-fase` is one
aggregate over `PARTIDOS` filtered by `fase_id` — `03_indexes.sql` already
indexes `Fase_ID` (verified present in the motor-de-formatos migration).
Ida_Vuelta doubles bracket rows: an 8-team bracket goes 7→13 matches, a
32-team one 31→61. Irrelevant at this scale. `fn_resolver_llave` adds one
extra `vw_goles_acreditados` scan per bracket finalise — that view is already
scanned once per finalise today, so it is 2x on a path that runs a handful of
times per tournament. No caching needed.

**Section 8 — Observability.** Gaps found. The plan ships no logging for the
two irreversible operations. Accepted obligation: `cerrar_torneo` and
`reabrir_torneo` each emit a structured log line naming torneo_id, usuario_id,
the resolved podium and the fase transition. `AUDITORIA` already captures the
row diff automatically (`core/auditoria.py` after_flush_postexec hook), so the
durable trail is free — the log line is for the live tail. Runbook for the
one failure mode an operator will actually hit: "podium looks wrong" →
reopen, correct the result, re-close.

**Section 9 — Deployment.** All schema changes are additive and nullable, so
old code runs against the new schema unchanged — deploy order is
migrate-then-deploy with no window. The one non-additive change is the
trigger rewrite: `CREATE OR REPLACE FUNCTION` is atomic in Postgres, but
between the migration and the code deploy, `fn_propagar_ganador_bracket`
already understands `Partido_Ida_ID` while no match has one — which is the
no-op path. Safe. Rollback: revert the code, leave the columns. The columns
are inert to old code. No feature flag needed. Post-deploy check: finalise
one single-leg bracket match in staging and confirm it still propagates
(the regression that matters).

**Section 10 — Long-term trajectory.** Reversibility 4/5 — additive schema,
revertible code, one-way only in the sense that a *closed* tournament's
podium is data a revert would strand (mitigated by `reabrir_torneo`). Debt
introduced: the `clasificados_por_grupo` semantic overload (T3) and the
three-value enum's rigidity (T2). Path dependency: choosing the enum over the
threshold means preset four costs a migration. The 1-year question: a new
engineer reading `Partido_Ida_ID` will understand it in 30 seconds;
`clasificados_por_grupo` meaning two different cardinalities will cost them
an hour. That is the plan's weakest long-term choice.

**Section 11 — Design & UX.** UI scope detected. Information architecture:
"Configurar Siguiente Fase" is correctly a single primary action rather than
two competing buttons. Interaction state coverage:

```
  FEATURE              | LOADING | EMPTY | ERROR | SUCCESS | PARTIAL
  ---------------------|---------|-------|-------|---------|--------
  estado-fase panel    | spec'd  | GAP   | GAP   | spec'd  | spec'd
  ModalSiguienteFase   | spec'd  | n/a   | GAP   | spec'd  | n/a
  Podio card           | GAP     | GAP   | GAP   | spec'd  | n/a
  BracketView (llaves) | spec'd  | n/a   | n/a   | spec'd  | GAP
```

Gaps, all accepted: the empty state when the standings table has fewer rows
than podium slots (Finding 9's UI face); the error state when `cerrar` 400s
on an unresolved tie (Finding 2); `BracketView`'s partial state when the ida
is played and the vuelta is not ("Ida 1-0 · Vuelta pendiente"), which is the
most common state a two-legged bracket is ever in and the plan does not
mention it. AI-slop risk: low — the plan reuses an established modal pattern
and explicitly forbids `window.prompt`. Responsive: not mentioned anywhere.
Accepted obligation: the three-radio format selector and the podium preview
must be checked at 375px, where three radios with subtitles is the layout most
likely to break. Accessibility: radios are the right control (keyboard and
screen-reader native); the podium card needs real text, not medal emoji alone.

### Findings (auto-decided)

| # | Finding | Severity | Decision | Principle |
|---|---|---|---|---|
| 1 | `ganador_desempate_id` has no frontend UI (verified: absent from all of `frontend/src` except generated `schema.d.ts`). Any tied knockout match is unresolvable in the app today, and Ida_Vuelta multiplies those matches. | CRITICAL | **ACCEPTED** — desempate UI becomes Phase 0, modelled on the existing `ganador_corrido_id` control in `Cronometro.tsx:350-365` | P1, P2 |
| 2 | Liga podium can be decided alphabetically. Verified: `04_views.sql:319` joins on `ge.Grupo_ID = l.Grupo_ID`, always NULL in Liga, so `orden_manual` never applies and `ORDER BY ... Equipo` breaks the tie. | CRITICAL | **ACCEPTED** — `cerrar_torneo` rejects with a specific 400 when podium slots are tied through `gf`, and the close modal lets the admin order the tied teams explicitly (server validates they are genuinely tied). Recorded as Taste Decision T1. | P1, P5 |
| 3 | `fn_marcador_partido` as specified is goals-only. Verified: `Ganador_Corrido_ID` appears nowhere in `fn_propagar_ganador_bracket`, so a Corrido knockout (Tenis, Ajedrez, LoL — 28-discipline catalog) is already unfinishable, and B1 would canonicalise that. | CRITICAL | **ACCEPTED** — the helper resolves winner-of-match: walkover → present team; Corrido → `Ganador_Corrido_ID`; else goals. Same cost, fixes an existing bug. | P1, P4 |
| 4 | Closing locks nothing and cannot be undone. Verified: `TORNEO.estado` is read by zero services; no reopen exists anywhere. | CRITICAL | **ACCEPTED** — `POST /torneos/{id}/reabrir`, plus a write-guard on results reusing the archived-tournament pattern at `services/partido.py:212` | P1, P2 |
| 5 | Sequencing buries the value. Requirement 3 is 2 lines and requirement 1 is ~1 day, but both sit behind the llaves engine, declared "un bloque atómico". | HIGH | **QUEUED AS USER CHALLENGE UC1** — both voices recommend splitting delivery | — |
| 6 | Byes assigned by cross-list position, not seed (`con_bye = ids[:byes_n]`). With `_cruzar_tabla_unica` producing `[1, N, 2, N-1…]`, 6 qualifiers hands byes to seeds 1 and 6. | HIGH | **ACCEPTED** — assign byes by seed rank; test at 2/4/6/8 qualifiers. Also fixes the latent case in `_cruzar_grupos`. | P1, P2 |
| 7 | B1 rewrites two live triggers in the same phase as the new feature — a regression cannot be told from the feature. | MEDIUM | **ACCEPTED** — B1 lands as its own commit, existing trigger tests green, zero behavior change, before any `Partido_Ida_ID` work | P5 |
| 8 | B5 offers delete-ordering as an equal alternative to `ON DELETE SET NULL`. Verified: both existing self-FKs already use `ON DELETE SET NULL` (`02_constraints.sql:249-250`). | MEDIUM | **ACCEPTED** — B5 collapses to following the convention. Delete ordering is not an option. | P3, P4 |
| 9 | Cancelled matches hole. Verified: `vw_tabla_posiciones` unions only `Estado='Finalizado'`, so a team with no played match is absent from the table entirely — a 3-team Liga can return 2 rows for a "top 3", and an all-cancelled group yields zero qualifiers into a silently short bracket. | MEDIUM | **ACCEPTED** — `cerrar_torneo` validates the table has at least as many rows as podium slots and each podium team has PJ > 0; `generar_playoffs` validates the qualifier count before `_sortear_bracket` | P1 |
| 10 | The +7-day vuelta claims a criterion that does not exist. Verified: every bracket match is created at `fecha_base`, rounds included. | MEDIUM | **ACCEPTED** — give the bracket real spacing (round R at base + 7·R, vuelta at +3) | P1 |
| 11 | Stored podium drifts from live standings with no UI story. | MEDIUM | **ACCEPTED** — render "Podio confirmado el {Fecha_Cierre}", and `estado-fase` flags when the computed top-3 differs from the stored podium | P1 |
| 12 | Out-of-order leg finalisation: nothing stops the vuelta being finalised before the ida, which makes `fn_resolver_llave` aggregate against an unfinished ida. | HIGH | **ACCEPTED** — the vuelta refuses to finalise while its ida is not resolved, same BEFORE trigger | P1 |
| 13 | `_sortear_bracket` past 10 branches once three leg formats land. | MEDIUM | **ACCEPTED** — extract `_crear_llave(...)`; one branch per concept | P5 |
| 14 | Which leg carries `partido_perdedor_siguiente_id` is unspecified. | LOW | **AUTO-DECIDED (mechanical)** — the VUELTA | P5 |
| 15 | `formato_eliminatoria` unreachable for a pure `Eliminacion` tournament. | MEDIUM | **ACCEPTED** — expose it at tournament creation (one schema line) | P1, P2 |
| 16 | `_validar_parametros_formato` rejects `equipos_por_grupo` and `clasificados_por_grupo` in one combined condition (`services/torneo.py:225`) — relaxing one requires splitting the check and its message. | LOW | **ACCEPTED** — split the condition, per-format error text | P5 |
| 17 | Public champion artifact is the missed reframe. | HIGH | **QUEUED AS USER CHALLENGE UC2** | — |
| 18 | Drop `Mixto` from the generator (native voice #6). | — | **REJECTED** — the user named all three formats explicitly. Completeness is cheap; cutting a requested format is not a reviewer's call. | P1 |
| 19 | Format-distribution query before coding (native voice #3). | LOW | **ACCEPTED** — `SELECT formato, estado, COUNT(*) FROM TORNEO GROUP BY 1,2` as step one; it costs nothing and settles how much the llaves engine is worth | P6 |
| 20 | Three `Preguntas abiertas` are decisions wearing questions' clothes (both voices). | LOW | **ACCEPTED** — resolved in-plan: Tercer Lugar always single; `clasificados_por_grupo` reused (T3); `formato_eliminatoria` at creation (Finding 15). Section removed. | P3 |

### Taste decisions (surfaced at the Final Gate)

- **T1 — Liga tie resolution.** Recommended: explicit podium ordering in the
  close modal, server-validated to only reorder genuinely tied teams.
  Alternative: extend `orden_manual` to Liga by moving it to
  `INSCRIPCIONES_TORNEO` — the root-cause fix, reusable outside the close
  flow, but it touches `vw_tabla_posiciones`, the PATCH endpoint and the
  standings UI (human ~1d / CC ~40min vs ~3h / ~15min).
- **T2 — `Formato_Eliminatoria` representation.** Recommended: the three-value
  enum, matching the request 1:1 and readable in 30 seconds. Alternative: an
  integer "double-leg from round N" with the three named presets rendered over
  it — same UI, no migration when a fourth preset arrives.
- **T3 — `clasificados_por_grupo` reuse.** Recommended: reuse, with a
  `COMMENT ON COLUMN`, a per-format API label and a per-format validator
  message. Alternative: a separate `clasificados_a_playoffs` column, because
  the two meanings differ in cardinality (N per group vs N total), not just
  in context.

### NOT in scope

- Away-goals rule for aggregate ties — dropped by UEFA in 2021, and the system
  records who won, not how.
- Llaves to 3+ legs (triangulares, Apertura/Clausura).
- Tercer Lugar to two legs — always a single match, all three formats.
- Per-leg date rescheduling beyond the round spacing in Finding 10.
- Changing `formato_eliminatoria` after a bracket has results — rehacer sorteo
  already covers the no-results case.
- Palmares across editions of a `TORNEO_GRUPO` (E7) — deferred to TODOS.md.
- Penalties/extra-time detail beyond "who won" — already parked in TODOS.md,
  and Finding 1's desempate UI is the piece that premise depended on.

### What already exists

See the 0B leverage map. The short version: the plan reuses nine existing
mechanisms correctly and walks past three (`PartidoService`'s archived guard,
`Ganador_Corrido_ID`, `GRUPO_EQUIPO.orden_manual`). All three are now accepted
obligations.

### Dream state delta

This plan gets tournaments an ending and brackets a second leg. Against the
12-month ideal it leaves two gaps: the champion is a database row rather than
a shareable artifact (UC2), and results across editions of a `TORNEO_GRUPO`
still do not accumulate into a palmares (E7, deferred). With the accepted
findings it also closes a gap the ideal assumed was already closed — that
every discipline in the catalog can actually finish a knockout (Finding 3).

### Error & Rescue Registry

```
  METHOD/CODEPATH                    | WHAT CAN GO WRONG                      | EXCEPTION
  -----------------------------------|----------------------------------------|------------------
  cerrar_torneo                      | tournament already closed              | DomainRuleError
                                     | fase incompleta                        | DomainRuleError
                                     | formato Grupos (Opcion A prohibida)    | DomainRuleError
                                     | podium slots tied through gf           | DomainRuleError
                                     | standings shorter than podium slots    | DomainRuleError
                                     | submitted podium team not tied         | DomainRuleError
  reabrir_torneo                     | tournament not closed                  | DomainRuleError
  generar_playoffs (Liga)            | fewer qualifiers than the cross needs  | DomainRuleError
                                     | clasificados < 1                       | DomainRuleError
  _sortear_bracket (Ida_Vuelta)      | rehacer with results present           | DomainRuleError
  fn_resolver_llave                  | ida not resolved when vuelta finalises | RAISE EXCEPTION
                                     | aggregate tied, no Ganador_Desempate   | RAISE EXCEPTION
  fn_marcador_partido                | Corrido match with no Ganador_Corrido  | RAISE EXCEPTION (existing trigger)
  estado-fase                        | torneo has no fase yet                 | returns acciones: []
  -----------------------------------|----------------------------------------|------------------

  EXCEPTION                          | RESCUED? | RESCUE ACTION            | USER SEES
  -----------------------------------|----------|--------------------------|---------------------------
  DomainRuleError (all)              | Y        | handlers.py -> 400       | the specific Spanish message
  RAISE EXCEPTION (plpgsql)          | Y        | handlers.py maps DBAPI   | 400 with the raised name
  partido_vuelta_ida_sin_resolver    | Y        | BEFORE trigger rejects   | "Falta cerrar el partido de ida"
  podio_empate_sin_resolver          | Y        | 400 from cerrar_torneo   | "Hay un empate en el podio: ordenalos antes de cerrar"
  tabla_mas_corta_que_podio          | Y        | 400 from cerrar_torneo   | "No hay suficientes equipos con partidos jugados"
  -----------------------------------|----------|--------------------------|---------------------------
```

No GAPs remain: the two the review found (writes after close, empty standings)
are covered by accepted Findings 4 and 9.

Note on the existing mapping: `exceptions/handlers.py` maps every `DBAPIError`
to 400, not 500 — which previously hid an `UndefinedColumn` as a validation
error (recorded learning, 2026-09-16). The new plpgsql `RAISE EXCEPTION`
names ride that same path intentionally, but it means a genuine schema drift
in this feature will also surface as a 400. Accepted obligation: the migration
must be applied before the code deploy, and the post-deploy smoke check
(Section 9) exists precisely to catch that.

### Failure Modes Registry

```
  CODEPATH                        | FAILURE MODE                      | RESCUED? | TEST? | USER SEES        | LOGGED?
  --------------------------------|-----------------------------------|----------|-------|------------------|--------
  cerrar_torneo (Liga)            | crowns alphabetical winner on tie | Y (F2)   | Y     | 400 + tie shown  | Y
  cerrar_torneo                   | podium from a 2-row table         | Y (F9)   | Y     | 400              | Y
  result edit after close         | podium silently drifts            | Y (F4)   | Y     | 400              | Y
  no reopen path                  | wrong podium is permanent         | Y (F4)   | Y     | reopen button    | Y
  bracket, Corrido discipline     | knockout cannot be finished       | Y (F3)   | Y     | winner recorded  | Y
  tied knockout, any discipline   | no way to record the winner       | Y (F1)   | Y     | desempate control| Y
  vuelta finalised before ida     | wrong team advances               | Y (F12)  | Y     | 400              | Y
  liguilla byes                   | 6th seed skips a round            | Y (F6)   | Y     | correct bracket  | n/a
  rehacer sorteo con llaves       | FK violation on delete            | Y (F8)   | Y     | nothing (works)  | n/a
  group, all matches cancelled    | silently short bracket            | Y (F9)   | Y     | 400              | Y
  --------------------------------|-----------------------------------|----------|-------|------------------|--------
```

**0 CRITICAL GAPS** after the accepted findings. Before them: 5 (F1, F2, F3,
F4, F12 all shipped silent or unfixable).

### Diagrams

**Architecture (new components against existing)**

```
  ┌──────────────────────── FRONTEND ────────────────────────┐
  │ MotorFormatosPanel ──reads──> GET /estado-fase  [NEW]    │
  │        │                                                  │
  │        ├─ ModalSiguienteFase [NEW]                        │
  │        │     ├─ paso 2a ──> POST /cerrar        [NEW]     │
  │        │     └─ paso 2b ──> POST /playoffs      [EXTENDED]│
  │        ├─ PodioCard [NEW] ──> POST /reabrir     [NEW]     │
  │        └─ BracketView [EXTENDED: agrupa por llave]        │
  │ Cronometro / ModalResultadoDirecto [EXTENDED: desempate]  │
  └──────────────────────────┬────────────────────────────────┘
  ┌──────────────────────── SERVICE ─────────────────────────┐
  │ MotorFormatosService                                      │
  │   estado_fase()       [NEW]                               │
  │   cerrar_torneo()     [NEW] ──> tabla_posiciones (reuse)  │
  │   reabrir_torneo()    [NEW]                               │
  │   generar_playoffs()  [EXTENDED: + Liga]                  │
  │     └─ _cruzar_tabla_unica() [NEW]                        │
  │   _sortear_bracket()  [EXTENDED: + formato_eliminatoria]  │
  │     └─ _crear_llave() [NEW]                               │
  │ PartidoService [EXTENDED: write-guard on closed torneo]   │
  └──────────────────────────┬────────────────────────────────┘
  ┌────────────────────────── SQL ───────────────────────────┐
  │ fn_marcador_partido()            [NEW, shared]            │
  │   └── used by ──┬── fn_propagar_ganador_bracket [EXTENDED]│
  │                 ├── fn_validar_..._desempate    [EXTENDED]│
  │                 └── fn_resolver_llave           [NEW]     │
  │ TORNEO  + Campeon/Subcampeon/Tercero/Fecha_Cierre         │
  │         + Formato_Eliminatoria                            │
  │ PARTIDOS + Partido_Ida_ID (self-FK, ON DELETE SET NULL)   │
  └───────────────────────────────────────────────────────────┘
```

> **Diagrama superado (2026-09-17):** `fn_validar_..._desempate` volvió a
> extenderse (`desempate-tiempo-extra-penales-plan.md` Fase 2, más 5
> columnas en PARTIDOS y 1 en TORNEO) — ver ese plan para el estado real.

**State machine — a two-legged tie**

```
      ┌──────────────┐  ida Finalizado   ┌──────────────┐
      │ AMBAS         │──────────────────>│ IDA CERRADA  │
      │ PROGRAMADAS   │                   │ vuelta abierta│
      └──────────────┘                    └───────┬──────┘
             │                                    │ vuelta Finalizado
             │ vuelta Finalizado                  v
             │ (fuera de orden)           ┌───────────────┐
             v                            │ GLOBAL        │
      ┌──────────────┐                    │ CALCULADO     │
      │ RECHAZADO     │<── F12 guard       └───┬───────┬───┘
      │ 400           │                        │       │
      └──────────────┘             global != 0 │       │ global == 0
                                               v       v
                                    ┌──────────────┐ ┌────────────────────┐
                                    │ GANADOR      │ │ EXIGE              │
                                    │ PROPAGADO    │ │ Ganador_Desempate  │
                                    └──────────────┘ │ (F1: ahora hay UI) │
                                                     └────────────────────┘
```

> **Diagrama superado (2026-09-17):** "EXIGE Ganador_Desempate" ya no es el
> final del camino — `desempate-tiempo-extra-penales-plan.md` Fase 2 le
> suma el CÓMO (`Metodo_Desempate`/`Penales_*`/`Hubo_Tiempo_Extra`) a esa
> misma resolución.

**Data flow — cerrar_torneo, all four paths**

```
  POST /cerrar ──> validar fase ──> tabla_posiciones ──> resolver podio ──> persistir
       │               │                   │                   │               │
       v               v                   v                   v               v
  [nil torneo]   [fase incompleta]   [tabla vacia]        [empate pts/dg/gf]  [ya cerrado]
   404 get_or_404  400 DomainRule      400 F9              400 F2              400 idempotente
                                      [tabla < 3 filas]    [PJ == 0 en podio]
                                       400 F9               400 F9
```

**Error flow / rollback**

```
  deploy: migracion 32 (aditiva, nullable) ──> codigo ──> smoke: finalizar
                                                          un bracket de 1 partido
        │                                          │
        │ falla                                    │ falla
        v                                          v
   no hay nada que revertir              git revert del codigo;
   (solo columnas nuevas inertes)        columnas quedan inertes, sin drop
```

### Stale diagram audit

`motor_formatos.py` carries no ASCII diagrams — only prose docstrings, and
those stay accurate except `_sortear_bracket`'s, which documents the
"bye en semifinal deja el Tercer Lugar a medio cablear" edge case. Two legs
double that case; the docstring must be updated in the same commit rather than
left describing the single-leg shape. `06_triggers.sql` comments on
`fn_propagar_ganador_bracket` state "No dispara para partidos de Liga/Grupos
(ambas columnas de siguiente son NULL ahi)" — still true, but the new
`Partido_Ida_ID` branch needs its own sentence there. Both recorded as
accepted obligations.

### Implementation Tasks (CEO phase)

- [ ] **T1 (P1, human: ~4h / CC: ~20min)** — frontend/control-mesa — Build the desempate control for `ganador_desempate_id`
  - Surfaced by: Finding 1 — verified absent from all of `frontend/src`
  - Files: `frontend/src/pages/control-mesa/ModalResultadoDirecto.tsx`, `frontend/src/components/Cronometro.tsx`, tests
  - Verify: `cd frontend && npm run verify`; a tied elimination match can be closed from the UI
- [ ] **T2 (P1, human: ~3h / CC: ~15min)** — database/triggers — `fn_marcador_partido` resolves winner-of-match, not goals
  - Surfaced by: Finding 3 — `Ganador_Corrido_ID` unread by `fn_propagar_ganador_bracket`
  - Files: `database/06_triggers.sql`, `database/32_migracion_cierre_fase_y_llaves.sql`, `backend/tests/test_db_triggers_motor_formatos.py`
  - Verify: `cd backend && pytest tests/test_db_triggers_motor_formatos.py`; a Corrido bracket advances
- [ ] **T3 (P1, human: ~4h / CC: ~20min)** — backend/services — `reabrir_torneo` + write-guard on a closed tournament
  - Surfaced by: Finding 4 — `TORNEO.estado` read by zero services
  - Files: `backend/app/services/motor_formatos.py`, `backend/app/services/partido.py`, `backend/app/api/routes/motor_formatos.py`, `backend/tests/test_cierre_torneo.py`
  - Verify: `cd backend && pytest tests/test_cierre_torneo.py`
- [ ] **T4 (P1, human: ~3h / CC: ~15min)** — backend/services — Block closing on an unresolved podium tie; explicit ordering in the modal
  - Surfaced by: Finding 2 — `orden_manual` always NULL in Liga (`04_views.sql:319`)
  - Files: `backend/app/services/motor_formatos.py`, `frontend/src/pages/torneo-admin/torneo-dashboard/ModalSiguienteFase.tsx`
  - Verify: two teams level on pts/dg/gf cannot be closed silently
- [ ] **T5 (P1, human: ~2h / CC: ~10min)** — database/triggers — Vuelta cannot finalise before its ida
  - Surfaced by: Finding 12 — out-of-order finalisation aggregates against an open ida
  - Files: `database/06_triggers.sql`, `backend/tests/test_db_triggers_motor_formatos.py`
  - Verify: finalising the vuelta first returns 400
- [ ] **T6 (P2, human: ~2h / CC: ~10min)** — backend/services — Assign byes by seed rank
  - Surfaced by: Finding 6 — `con_bye = ids[:byes_n]` hands the 6th seed a bye
  - Files: `backend/app/services/motor_formatos.py`, `backend/tests/test_motor_formatos_llaves.py`
  - Verify: 2/4/6/8 qualifiers each give byes to the top seeds
- [ ] **T7 (P2, human: ~2h / CC: ~10min)** — backend/services — Validate standings depth before building a podium or a cross
  - Surfaced by: Finding 9 — `vw_tabla_posiciones` omits teams with no finished match
  - Files: `backend/app/services/motor_formatos.py`, `backend/tests/test_cierre_torneo.py`
  - Verify: a 3-team Liga with one unplayed team returns 400, not a 2-team podium
- [ ] **T8 (P2, human: ~2h / CC: ~10min)** — backend/services — Real round spacing for bracket dates
  - Surfaced by: Finding 10 — every bracket match currently sits at `fecha_base`
  - Files: `backend/app/services/motor_formatos.py`, `backend/tests/test_motor_formatos_llaves.py`
  - Verify: round R at base + 7·R, vuelta at +3
- [ ] **T9 (P2, human: ~1h / CC: ~5min)** — database — B1 as an isolated no-op refactor commit
  - Surfaced by: Finding 7 — refactor and feature in one phase hides regressions
  - Files: `database/06_triggers.sql`
  - Verify: existing trigger tests pass with zero behavior change before `Partido_Ida_ID` exists
- [ ] **T10 (P2, human: ~1h / CC: ~5min)** — backend/services — Extract `_crear_llave`; keep `_sortear_bracket` under 10 branches
  - Surfaced by: Finding 13 — cyclomatic complexity
  - Files: `backend/app/services/motor_formatos.py`
  - Verify: `cd backend && pytest tests/test_motor_formatos_algoritmos.py`
- [ ] **T11 (P2, human: ~1h / CC: ~5min)** — frontend — Podium snapshot semantics and divergence flag
  - Surfaced by: Finding 11 — stored podium drifts from live standings
  - Files: `frontend/src/pages/torneo-admin/torneo-dashboard/`, `backend/app/services/motor_formatos.py`
  - Verify: "Podio confirmado el {fecha}" renders; `estado-fase` reports divergence
- [ ] **T12 (P2, human: ~1h / CC: ~5min)** — frontend — Missing UI states: empty standings, close error, ida-played/vuelta-pending
  - Surfaced by: Section 11 coverage map
  - Files: `MotorFormatosPanel.tsx`, `ModalSiguienteFase.tsx`, `BracketView.tsx`
  - Verify: `cd frontend && npm run verify`; checked at 375px
- [ ] **T13 (P3, human: ~30min / CC: ~5min)** — backend/schemas — `formato_eliminatoria` at tournament creation
  - Surfaced by: Finding 15
  - Files: `backend/app/schemas/torneo.py`, `backend/app/services/torneo.py`
  - Verify: a pure `Eliminacion` tournament can be created two-legged
- [ ] **T14 (P3, human: ~30min / CC: ~5min)** — backend/services — Split the combined format-parameter validation
  - Surfaced by: Finding 16 — `services/torneo.py:225`
  - Files: `backend/app/services/torneo.py`, `backend/tests/test_torneos.py`
  - Verify: `ida_vuelta` accepted in Grupos_Playoffs; `clasificados_por_grupo` accepted in Liga
- [ ] **T15 (P3, human: ~10min / CC: ~2min)** — ops — Format-distribution query before coding
  - Surfaced by: Finding 19 — how much the llaves engine is worth is currently assumed
  - Files: none (a read-only query against the live DB)
  - Verify: `SELECT formato, estado, COUNT(*) FROM TORNEO GROUP BY 1,2`
- [ ] **T16 (P3, human: ~20min / CC: ~5min)** — docs — Refresh the docstrings two legs invalidate
  - Surfaced by: Stale diagram audit
  - Files: `backend/app/services/motor_formatos.py`, `database/06_triggers.sql`
  - Verify: the `_sortear_bracket` docstring and the `fn_propagar_ganador_bracket` comment describe the two-legged shape

### TODOS.md (proposed, auto-decided)

- **Palmares across editions of a `TORNEO_GRUPO`** — What: aggregate podiums
  across `numero_edicion` into a history view. Why: a champion that
  accumulates is worth more than a champion that resets. Pros: strongest
  retention hook this data model can produce cheaply. Cons: depends on UC2
  landing first, and on enough closed tournaments existing to be worth
  rendering. Context: `TORNEO.torneo_grupo_id` + `numero_edicion` already
  model editions (`torneos-admin-plan.md`); once the podium columns exist this
  is a view plus a page. Effort: M → CC S. Priority: P3. Depends on: the
  podium columns from this plan, and UC2.
  **Decision: ADD to TODOS.md.**

### Completion Summary

```
  +====================================================================+
  |            MEGA PLAN REVIEW — COMPLETION SUMMARY                   |
  +====================================================================+
  | Mode selected        | SELECTIVE EXPANSION                         |
  | System Audit         | schema+triggers = most-churned area; 3rd    |
  |                      | pass over motor de formatos; no real TODOs  |
  | Step 0               | Approach A; 6 premises challenged, 4 wrong  |
  | Section 1  (Arch)    | 5 issues found                              |
  | Section 2  (Errors)  | 17 error paths mapped, 2 GAPS (both fixed)  |
  | Section 3  (Security)| 1 issue found, 0 High severity              |
  | Section 4  (Data/UX) | 12 edge cases mapped, 2 unhandled (fixed)   |
  | Section 5  (Quality) | 3 issues found                              |
  | Section 6  (Tests)   | Diagram produced, 6 gaps                    |
  | Section 7  (Perf)    | 0 issues found                              |
  | Section 8  (Observ)  | 2 gaps found                                |
  | Section 9  (Deploy)  | 1 risk flagged (migrate-before-deploy)      |
  | Section 10 (Future)  | Reversibility: 4/5, debt items: 2           |
  | Section 11 (Design)  | 4 issues                                    |
  +--------------------------------------------------------------------+
  | NOT in scope         | written (7 items)                           |
  | What already exists  | written                                     |
  | Dream state delta    | written                                     |
  | Error/rescue registry| 8 methods, 0 CRITICAL GAPS                  |
  | Failure modes        | 10 total, 0 CRITICAL GAPS (5 before review) |
  | TODOS.md updates     | 1 item proposed                             |
  | Scope proposals      | 8 proposed, 5 accepted, 1 deferred,         |
  |                      | 1 skipped, 1 queued as user challenge       |
  | CEO plan             | written                                     |
  | Outside voice        | codex unavailable (not installed);          |
  |                      | 2 native Claude subagents [subagent-only]   |
  | Lake Score           | 6/6 recommendations chose the complete option|
  | Diagrams produced    | 4 (architecture, state machine, data flow,  |
  |                      | error/rollback)                             |
  | Stale diagrams found | 2 (both docstrings/comments, T16)           |
  | Unresolved decisions | 0 (3 taste + 3 user challenges go to gate)  |
  +====================================================================+
```

## Phase 2 — Design Review (/autoplan auto-decided)

Run: autoplan-20260915-230236-566 · branch main · 2026-09-16

### Pre-review system audit

UI scope confirmed: `MotorFormatosPanel.tsx` (233 lines), `BracketView.tsx`,
`TorneoDashboard.tsx`, `DetalleTorneoPublico.tsx`, plus a new
`ModalSiguienteFase`. Prior design review cycles touched this exact area —
`index.css:1376` (`.bracket`) and `index.css:983` (`.modal-overlay`) both
carry comments citing earlier Pass 6 responsive findings. Third pass over the
same surfaces, reviewed harder.

### 0A. Initial design rating: 2/10

Not because the visual system is wrong — it is genuinely good — but because
the plan specifies the *resolved* state of every screen and none of the
states the user actually lives in. One sentence per surface. A 10 for THIS
plan means: every one of the four llave states drawn, the incomplete-phase
state designed as a first-class state rather than an absence, loading and
error surfaces named, and the one-way door labelled as one.

### 0B. DESIGN.md status

**No DESIGN.md.** But a real design system exists in `frontend/src/index.css`
(2118 lines) and every decision below calibrates against it:

```
  --bg #0f1420   --surface #171f30   --surface-alt #1f2a40   --border #2b3654
  --text #e6ebf5 --text-muted #93a0bd --accent #4fd1c5 --accent-strong #38b2ac
  --danger #ef6a6a --warning #e0b23a --radius 10px   color-scheme: dark
```

Border-and-surface based, no shadows, one accent. Recommend
`/design-consultation` to formalize it into DESIGN.md — flagged, not blocking.

### 0C. Existing design leverage (verified in index.css)

| Need | Existing pattern | Line |
|---|---|---|
| Modal shell | `.modal-overlay` / `.modal-panel` (max-width 480px) | 983 / 995 |
| Reverse a committed state | `.boton-cierre-forzado` + `.cierre-forzado-confirmar` — danger outline, its own comment says "nunca se confunda con un cierre de rutina" | 689 / 706 |
| Persistent cause banner | `.banner-info-persistente` (`--warning`, never dismiss-once) | 1824 |
| Reorderable rows, touch-sized | `.alineacion-fila` + `__mover` (56×44px) | 1625 / 1670 |
| Scrolling list inside a modal | `.modal-panel__checklist` (max-height 40vh) | 1023 |
| Bracket | `.bracket` (h-scroll), `.bracket__columna` (min-width 180px) | 1376 / 1387 |
| Disabled-with-reason | the `<p className="muted">` reason slot in `ModalResultadoDirecto` | :772 |

Every design obligation below reuses one of these. The plan introduces no new
color, no shadow, no font, and should keep it that way.

### 0D. Focus areas

All 7 passes (P1 — auto-decided, no reduction).

### Step 0.5: Visual mockups — NOT generated (deviation, declared)

`DESIGN_READY` printed, so the designer was available. Mockups were skipped
anyway, and this is a deliberate deviation from the skill's default:

- The surface is OPERATE (back-office admin) inside a fixed token system. The
  visual direction is not in question; both voices independently concluded the
  problem is missing specification, not missing visual direction.
- Every finding below resolves to an existing CSS class with a line number. A
  generated mockup would not match `--surface #171f30` / `.modal-panel` and
  would compete with the system rather than inform it.

Recorded as a taste call so it can be overridden: TD4 at the gate.

### Step 0.5b: Dual voices

Codex: **unavailable** (CLI not installed). Both voices are fresh-context
Claude subagents in the same harness; model identity unknown.
Tagged `[subagent-only]`.

```
DESIGN OUTSIDE VOICES — LITMUS SCORECARD:
═══════════════════════════════════════════════════════════════
  Check                                    Native  Outside  Consensus
  ─────────────────────────────────────── ─────── ──────── ─────────
  1. Brand unmistakable in first screen?   n/e     YES      N/A
  2. One strong visual anchor?             NO      NO       N/A
  3. Scannable by headlines only?          NO      NO       N/A
  4. Each section has one job?             NO      NO       N/A
  5. Cards actually necessary?             NO      NO       N/A
  6. Motion improves hierarchy?            NOT SPEC'D NO    N/A
  7. Premium without decorative shadows?   n/e     YES      N/A
  ─────────────────────────────────────── ─────── ──────── ─────────
  Hard rejections triggered:               0       1 (#7)   N/A
═══════════════════════════════════════════════════════════════
Consensus cells are N/A, never CONFIRMED: outside coverage is unavailable and
a native fallback cannot supply it. n/e = not evaluated by that voice.
```

**HARD REJECTION #7 — App UI made of stacked cards instead of layout.**
Verified: `MotorFormatosPanel.tsx` returns `<div className="card
motor-formatos-panel">` at four separate returns (:96, :111, :130, :144) and
`BracketView` adds a fifth. Plan E1 puts the podium inside that card and E4
puts it *again* in `TorneoDashboard` — two cards, same three team names,
stacked, on one tab. Raised first in Pass 1 per the pass-integration rule.

Independent agreement between the two native voices (corroboration, not
cross-model confirmation): the one-way door has no consequence copy and no
reverse; loading/error/busy are absent everywhere; the partial llave state
(ida played, vuelta pending) is undesigned and is the state a two-legged
bracket spends most of its life in; the incomplete-phase state does not exist;
"Configurar Siguiente Fase" mislabels a tournament-ending action; the podium
appears on two surfaces with one sentence of spec between them.

### Pass 1: Information Architecture — 3/10 → 8/10

**3/10** because the plan never says what the user sees first on a closed
tournament, duplicates the podium across two surfaces, and hardcodes a button
label that is wrong in two of the four states its own C4 table defines.

Findings, all accepted:

- **[HARD REJECTION]** Podium rendered twice (E1 + E4). Fix: it is
  tournament-level state, so it lives **once**, in `TorneoDashboard`'s header
  region beside `Estado: {torneo.estado}` (`TorneoDashboard.tsx:154`), visible
  from every tab. `MotorFormatosPanel` returns `null` when `torneo_cerrado`.
  It is **one block with three rows**, not three cards: 1° at ~1.5rem/800
  (this is the visual anchor Litmus 2 is missing), 2° and 3° at body weight
  beneath.
- Button label is derived, not hardcoded: both actions → "Configurar
  Siguiente Fase"; `cerrar_directo` alone → "Cerrar Torneo";
  `generar_playoffs` alone → "Generar Playoffs". `acciones_disponibles`
  already carries the fact; use it for the label too, not only for visibility.
- `MotorFormatosPanel` has zero headings in its body (verified: its only
  `<h*>` is the modal title). Each state gets one `<h3>` naming the area —
  "Fase de Grupos", "Fase Eliminatoria", "Resultado final" — then one line of
  state, then one action.
- Podium rank colors, if wanted, are `--podio-oro` / `--podio-plata` /
  `--podio-bronce` on `:root`. A hardcoded `#d4af37` at implementation time is
  the predictable failure.

Still not 10: the Partidos tab keeps four card-shaped returns where a single
panel with a state machine would read better. Out of this plan's blast radius.

### Pass 2: Interaction State Coverage — 2/10 → 9/10

**2/10.** The plan specifies zero loading, busy, or error states anywhere, and
converts `MotorFormatosPanel` from a client-derived render (instant, data
already present) to a network read (`GET /estado-fase`), introducing a latency
window it does not design for.

```
  FEATURE              | LOADING              | EMPTY                  | ERROR                       | SUCCESS            | PARTIAL
  ---------------------|----------------------|------------------------|-----------------------------|--------------------|--------------------------
  estado-fase panel    | skeleton, height     | "Sin fase todavia"     | inline, retry              | action button      | "22 jugados · 2 cancelados
                       | reserved (no shift)  |                        |                             |                    |  · 6 pendientes"
  ModalSiguienteFase   | disabled + spinner   | n/a                    | inline in modal, by cause  | closes, scrolls    | step 1 of 2 indicator
   paso 2a (cerrar)    | "Cerrando…"          | table shorter than 3   | "Resolve el empate entre   | podium reveal      | n/a
                       |                      | slots -> named copy    |  Tigres y Leones"           |                    |
   paso 2b (playoffs)  | "Generando llaves…"  | n/a                    | inline, by cause           | bracket renders    | n/a
  Podio card           | skeleton 3 rows      | "2 equipos — sin       | divergence strip           | static             | 2 steps when tercero NULL
                       |                      |  tercer puesto."       |                             |                    |
  BracketView llave    | n/a                  | n/a                    | "Requiere desempate" badge | global + winner    | "IDA 10/03 1-0 · VTA pend."
  Closed tournament    | n/a                  | n/a                    | persistent cause banner    | n/a                | n/a
```

Accepted obligations from this pass:

- Skeleton in the action zone with reserved height, so the button does not pop
  in and the panel does not shift.
- Busy state on both POSTs with a double-submit guard. Generating an 8-team
  two-legged bracket writes ~14 rows; it is not instant.
- Errors render **inline inside the modal**, never a toast that disappears, and
  are mapped per cause — the plan defines at least six distinct 400s (fase
  Grupos, fase incompleta, ya cerrado, empate sin resolver, tabla más corta que
  el podio, equipo no empatado). The user must be able to read the error and
  fix it without reopening the modal.
- **The blocked llave state is a real state, not an error.** Aggregate level
  with no `Ganador_Desempate_ID`: the trigger does not propagate and the
  bracket silently stops. It needs a "Requiere desempate" badge and a CTA into
  the vuelta. Without it the user sees a frozen bracket and no reason.
- "N de M resueltos" is replaced everywhere by the three-part count —
  "28 jugados · 2 cancelados · 0 pendientes". The corrected Finalizado-or-
  Cancelado rule has to be visible; "30 de 30 resueltos" to someone with two
  cancellations reads as a bug.

### Pass 3: User Journey & Emotional Arc — 3/10 → 8/10

```
  STEP | USER DOES                     | USER FEELS              | PLAN SPECIFIES?
  -----|-------------------------------|-------------------------|------------------------------
  1    | Last match of the phase ends  | "is that it?"           | NO -> now: panel flips to
       |                               |                         | "Resultado final" + action
  2    | Sees "Cerrar Torneo"          | mild dread, it is final | NO -> now: consequence line
       |                               |                         | in the radio, not the subtitle
  3    | Opens the modal               | checking, not browsing  | partly -> now: step indicator
  4    | Reads the podium preview      | "is this right?"        | NO -> now: Pts·DG·GF per row
       |                               |                         | + why each tie broke
  5    | Resolves a tie                | responsible             | NO -> now: reorder list
  6    | Confirms                      | commitment              | NO -> now: button names the
       |                               |                         | act: "Cerrar torneo y coronar
       |                               |                         | a Tigres"
  7    | Sees the champion             | THE payoff              | NO -> now: modal closes,
       |                               |                         | scroll to podium, one reveal
  8    | Realises a result was wrong   | panic                   | NO -> now: "Reabrir torneo"
```

Time horizons: 5 seconds — the champion name is the largest thing on screen.
5 minutes — the admin can verify every tiebreak without leaving the modal.
5 years — the podium is a snapshot with a date on it, so a tournament from two
seasons ago still explains itself.

Accepted: the coronation is the product's emotional peak and the plan renders
it as a state change. On success the modal closes, the page scrolls to the
podium, and there is one reveal. Once, not an entrance on every section.

### Pass 4: AI Slop Risk — 4/10 → 8/10

Classifier: **OPERATE (APP UI)**, with one READ surface
(`DetalleTorneoPublico`). Landing-page rules do not apply.

Hard rejections: **1 of 7 fires** — #7, stacked cards instead of layout
(evidence above). Resolved by the single-podium-block fix in Pass 1, which is
what lifts this pass from 4 to 8.

Blacklist scan of what the plan introduces: no purple gradients, no 3-column
feature grid, no icons in circles, no centered-everything, no decorative
blobs, no emoji as design elements, no colored left-borders, no generic hero
copy, no carousels. The plan is clean here.

One blacklist hit is **pre-existing and out of scope**: `index.css:30` sets
`font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif` as the
body voice — blacklist #11, the "gave up on typography" signal. App-wide, not
introduced by this plan. Flagged for `/design-consultation`, not fixed here.

Judgment tells checked by hand: browser surfaces (selection color, caret,
focus rings, scrollbars) are unthemed app-wide — again pre-existing. Depth:
no shadows anywhere, so no zero-offset halos. Tabular numerals: the plan adds
scores and dates to the bracket and standings, so
`font-variant-numeric: tabular-nums` is an accepted obligation on those —
`.fila-partido__hora` (`index.css:2032`) already establishes the treatment.

Still not 10: the podium is the one place this app could earn a moment of
character and the plan treats it as three rows of data. Left at 8 deliberately
rather than inventing a visual direction the token system has not asked for.

### Pass 5: Design System Alignment — 6/10 → 9/10

No DESIGN.md, so this rates the plan's explicit token and component
specification. **6/10**: the plan introduces no new color, shadow or font
(genuinely good, and the reason the visual risk here is low), but it names no
tokens either — "muestra el podio arriba" is the entire spec for the one new
visual element.

Accepted: every new surface cites the existing class it extends (table in 0C);
new rank colors, if any, become `:root` variables; and one new class
`.muted--cuerpo { font-size: 1rem; color: var(--text-muted); }` is added rather
than redefining `.muted`, which is load-bearing across the app.

### Pass 6: Responsive & Accessibility — 2/10 → 8/10

**2/10.** Responsive appears once in the whole plan (the 375px check inherited
from Phase 1) and accessibility appears nowhere.

Accepted obligations:

- **Decision-critical copy below 16px.** Verified: `.muted` is `0.85rem` =
  13.6px (`index.css:199`). The plan routes the podium provenance date, the
  three `formato_eliminatoria` subtitles and the disabled-reason text into it.
  The text explaining an irreversible choice must not be the smallest on
  screen. Use `.muted--cuerpo` (1rem) for all three. Contrast is fine:
  `--text-muted #93a0bd` on `--surface #171f30` measures ~6.3:1, over the 4.5:1
  floor.
- **Modal overload at 480px.** `.modal-panel` is `max-width: 480px`
  (`index.css:1001`) and step 2b now carries clasificados + three radios with
  subtitles, while step 2a carries a reorder list. Add `.modal-panel--ancho`
  (560px) for step 2 only. The overlay already scrolls (`index.css:983`).
- **Focus management.** `ModalClasificadosPorGrupo` sets `aria-modal="true"`
  with no focus trap, no Escape handler and no focus return. Absorbing it into
  a longer two-step flow makes that materially worse. Add all three **once, on
  the shared panel**, so the app's other modals inherit it. This is a
  pre-existing gap the plan would otherwise deepen.
- **Radios, not selects**, for both the path choice and the format choice: all
  options visible without a tap, keyboard and screen-reader native.
- **Touch targets**: the tie-reorder control reuses `.alineacion-fila__mover`
  (56×44px, verified `index.css:1670`), already above the 44px floor.
- **Step model**: "Paso 1 de 2 · Camino" / "Paso 2 de 2 · Playoffs" at the top
  of the panel and a "← Volver" in the action row. Returning to step 1 must
  preserve step 2b's selections — losing them would be a regression on the
  current `ModalClasificadosPorGrupo`.
- The podium reveal respects `prefers-reduced-motion`.

Still not 10: the bracket's horizontal scroll on a phone is a pre-existing
ergonomics problem that two-legged ties make denser. Mitigated by the
one-node-per-llave rule below, not solved.

### Pass 7: Unresolved Design Decisions

```
  DECISION NEEDED                          | IF DEFERRED, WHAT HAPPENS
  -----------------------------------------|------------------------------------------
  Llave = one node or two?                 | RESOLVED: one node = one llave. A card with
                                           | two compact leg rows, a border-top divider,
                                           | and the aggregate on its own row at weight
                                           | 700. Column count and scroll model stay
                                           | identical to Unico. Two independent nodes
                                           | would turn 7 boxes into 14 and stop the
                                           | bracket reading as a bracket.
  Bracket column width with legs?          | RESOLVED: raise .bracket__columna to 220px
                                           | when any llave has legs. .bracket already
                                           | scrolls horizontally; widening is free.
  Where do the new round dates render?     | RESOLVED: a header row on .bracket__partido,
                                           | tabular-nums, --text-muted, same treatment
                                           | as .fila-partido__hora (index.css:2032).
                                           | Round spacing makes dates the thing
                                           | organizers publish; today there is no slot.
  How is the desempate recorded?           | RESOLVED: inline in the existing save flow,
                                           | not a second modal. A required radio group
                                           | above .confirmar-evento__acciones, reusing
                                           | the disabled-reason <p className="muted">
                                           | slot that ModalResultadoDirecto:772 already
                                           | uses for incomplete goals.
  How does a closed tournament explain     | RESOLVED: .banner-info-persistente
  itself?                                  | (index.css:1824, --warning, aria-live) on
                                           | Partidos and Control de Mesa: "Torneo
                                           | cerrado el {fecha}. Los resultados estan
                                           | bloqueados." A lock with no stated cause is
                                           | a bug to the user.
  What does Reabrir look like?             | RESOLVED: .boton-cierre-forzado +
                                           | .cierre-forzado-confirmar (index.css:689/706)
                                           | — the app's established "reverse a committed
                                           | state" treatment, whose own comment says it
                                           | must never look like a routine close. No new
                                           | modal.
  Does the tie preview show WHY?           | RESOLVED: Pts · DG · GF per row, plus a
                                           | per-row note when the position is decided
                                           | below points. An orden_manual-decided title
                                           | gets a prominent notice, not a footnote.
  Calendar consequence of Ida_Vuelta?      | RESOLVED: a live computed line under the
                                           | format radios — "14 partidos · la final cae
                                           | aprox. el 12/11" — plus "La vuelta se agenda
                                           | 7 dias despues de la ida. Podes mover las
                                           | fechas despues desde cada partido."
  Generate mockups?                        | DEFERRED to the gate as TD4.
  Formalize DESIGN.md?                     | DEFERRED: /design-consultation, own scope.
  -----------------------------------------|------------------------------------------
```

### NOT in scope (design)

- Formalizing `index.css` into a DESIGN.md — recommend `/design-consultation`.
- Replacing the app-wide `system-ui` body font (blacklist #11, pre-existing).
- Theming browser surfaces (selection, caret, scrollbars, focus rings)
  app-wide — pre-existing, worth its own pass.
- Redesigning the Partidos tab's four card-shaped returns into one panel.
- Mobile-first rework of the bracket's horizontal scroll.
- Visual mockups (TD4).

### What already exists (design)

The 0C table. The headline: this plan needs no new visual vocabulary. Every
obligation maps to a class already in `index.css`, including the two hardest
ones — reversing a committed state (`.boton-cierre-forzado`, whose comment
already reasons about exactly this problem) and reorderable touch-sized rows
(`.alineacion-fila__mover`).

### Implementation Tasks (design phase)

- [ ] **D1 (P1, human: ~3h / CC: ~15min)** — frontend/control-mesa — Inline desempate radio group in the existing save flow
  - Surfaced by: Pass 7 / outside voice Finding 1 — no `ganador_desempate` control exists in `frontend/src`
  - Files: `frontend/src/pages/control-mesa/ModalResultadoDirecto.tsx`, `frontend/src/components/Cronometro.tsx`
  - Verify: a level knockout score reveals a required "¿Quién avanza?" radio group; save stays disabled with a stated reason
- [ ] **D2 (P1, human: ~2h / CC: ~10min)** — frontend/torneo-dashboard — Loading, busy and inline-error states for the whole flow
  - Surfaced by: Pass 2 — zero loading/busy/error states specified anywhere
  - Files: `MotorFormatosPanel.tsx`, `ModalSiguienteFase.tsx`
  - Verify: no layout shift on first paint; both POSTs show a busy label and reject double submit; each 400 renders inline by cause
- [ ] **D3 (P1, human: ~2h / CC: ~10min)** — frontend/BracketView — Four llave states including the blocked one
  - Surfaced by: Pass 2 / native voice D3 — only the resolved state is specified
  - Files: `frontend/src/pages/torneo-admin/torneo-dashboard/BracketView.tsx`
  - Verify: unplayed, ida-played/vuelta-pending, blocked-needs-desempate (badge + CTA), and walkover all render distinctly
- [ ] **D4 (P1, human: ~2h / CC: ~10min)** — frontend/torneo-dashboard — Single podium block in TorneoDashboard; panel returns null
  - Surfaced by: Pass 1 HARD REJECTION #7 — podium specified twice (E1 and E4)
  - Files: `TorneoDashboard.tsx`, `MotorFormatosPanel.tsx`, `DetalleTorneoPublico.tsx`
  - Verify: one podium per page; 1° is the largest element; 2-step render when tercero is NULL
- [ ] **D5 (P1, human: ~2h / CC: ~10min)** — frontend/ModalSiguienteFase — Tie-resolution reorder list, not a numeric input
  - Surfaced by: Pass 7 / outside voice Finding 3 — `CeldaOrdenManual` accepts 1/1/2 and fails server-side after submit
  - Files: `ModalSiguienteFase.tsx`
  - Verify: a 3-way tie cannot express an invalid order; confirm disabled with the reason named
- [ ] **D6 (P2, human: ~1h / CC: ~5min)** — frontend/torneo-dashboard — Incomplete-phase state with the three-part count
  - Surfaced by: Pass 2 / native voice D7 — the 95% state is undesigned
  - Files: `MotorFormatosPanel.tsx`, `backend/app/services/motor_formatos.py`
  - Verify: "28 jugados · 2 cancelados · 6 pendientes" renders under the heading as the reason the action is unavailable
- [ ] **D7 (P2, human: ~1h / CC: ~5min)** — frontend/torneo-dashboard — Derive the primary button label from `acciones_disponibles`
  - Surfaced by: Pass 1 / outside voice Finding 8 — the label mislabels a tournament-ending action as configuration
  - Files: `MotorFormatosPanel.tsx`
  - Verify: all three label variants render for the three action sets
- [ ] **D8 (P2, human: ~1h / CC: ~5min)** — frontend — Closed-tournament cause banner and Reabrir affordance
  - Surfaced by: Pass 7 / outside voice Finding 2 — a lock with no stated cause reads as a broken app
  - Files: `MotorFormatosPanel.tsx`, `ControlDeMesa.tsx`, `TorneoDashboard.tsx`
  - Verify: banner names the close date; Reabrir uses `.boton-cierre-forzado` + inline confirm, not a new modal
- [ ] **D9 (P2, human: ~1h / CC: ~5min)** — frontend/ModalSiguienteFase — Step model, back navigation, 560px step 2, focus management
  - Surfaced by: Pass 6 — no step indicator, no back, no focus trap, no Escape, no focus return
  - Files: `ModalSiguienteFase.tsx`, `index.css`
  - Verify: back preserves step 2b selections; Escape closes; focus returns to the trigger; checked at 375px
- [ ] **D10 (P2, human: ~1h / CC: ~5min)** — frontend/ModalSiguienteFase — Tiebreak transparency and calendar consequence
  - Surfaced by: Pass 3 / native voice D6, D9 — the preview hides why a tie broke and how long Ida_Vuelta makes the season
  - Files: `ModalSiguienteFase.tsx`
  - Verify: Pts·DG·GF per row, a per-row note when decided below points, and a live "N partidos · la final cae aprox. el {fecha}" line
- [ ] **D11 (P2, human: ~1h / CC: ~5min)** — frontend/BracketView — Bracket anatomy: date header, leg rows, aggregate row, 220px columns
  - Surfaced by: Pass 7 / outside voice Finding 5 — round spacing has nowhere to render and the leg string wraps
  - Files: `BracketView.tsx`, `index.css`
  - Verify: one node per llave; aggregate separated by a border-top at weight 700; tabular-nums on dates and scores
- [ ] **D12 (P3, human: ~30min / CC: ~5min)** — frontend — `.muted--cuerpo` for decision-critical copy
  - Surfaced by: Pass 6 — `.muted` is 13.6px and carries the copy explaining an irreversible choice
  - Files: `index.css`, `ModalSiguienteFase.tsx`, podium block
  - Verify: format subtitles, podium date and disabled reasons all render at 1rem; `.muted` itself unchanged
- [ ] **D13 (P3, human: ~30min / CC: ~5min)** — frontend — Podium reveal on success, reduced-motion respected
  - Surfaced by: Pass 3 — the product's emotional peak is currently a re-render
  - Files: `ModalSiguienteFase.tsx`, `TorneoDashboard.tsx`
  - Verify: modal closes, page scrolls to the podium, one reveal; nothing animates under `prefers-reduced-motion`

### Completion Summary

```
  +====================================================================+
  |         DESIGN PLAN REVIEW — COMPLETION SUMMARY                    |
  +====================================================================+
  | System Audit         | No DESIGN.md; real token system in          |
  |                      | index.css. UI scope: 5 surfaces.            |
  | Step 0               | 2/10 initial; all 7 passes                  |
  | Pass 1  (Info Arch)  | 3/10 → 8/10 after fixes                     |
  | Pass 2  (States)     | 2/10 → 9/10 after fixes                     |
  | 2nd native pass      | ran against the AMENDED plan; found the     |
  |                      | write-guard UI gap the 1st pass could not   |
  | Pass 3  (Journey)    | 3/10 → 8/10 after fixes                     |
  | Pass 4  (AI Slop)    | 4/10 → 8/10 after fixes (1 hard rejection)  |
  | Pass 5  (Design Sys) | 6/10 → 9/10 after fixes                     |
  | Pass 6  (Responsive) | 2/10 → 8/10 after fixes                     |
  | Pass 7  (Decisions)  | 8 resolved, 2 deferred                      |
  +--------------------------------------------------------------------+
  | NOT in scope         | written (6 items)                           |
  | What already exists  | written (7 reusable patterns, verified)     |
  | TODOS.md updates     | 0 items proposed (all in-scope)             |
  | Approved Mockups     | 0 generated, 0 approved (TD4 — declared)    |
  | Decisions made       | 23 added to plan (13 first pass + 10 from   |
  |                      | the second pass over the amended plan)      |
  | Decisions deferred   | 2 (TD4 mockups, DESIGN.md formalization)    |
  | Overall design score | 2/10 → 8/10                                 |
  +====================================================================+
```

Overall is the lowest rated pass, before and after. All six rated passes land
at 8+, so the plan is design-complete for implementation. Run `/design-review`
on the live site after implementation for visual QA.

### Unresolved Decisions (design)

- **TD4 — generate visual mockups?** Recommended: no, for the reasons in
  Step 0.5. The user can override at the gate.
- DESIGN.md formalization via `/design-consultation` — out of scope, not a
  blocker.

<!-- autoplan-accepted:ceo -->
- Desempate UI for `ganador_desempate_id` ships as Phase 0, before any two-legged work, modelled on the existing `ganador_corrido_id` control in `Cronometro.tsx`. Verify: a tied elimination match can be closed from the UI (`npm run verify` + a control-mesa test).
- `fn_marcador_partido` resolves winner-of-match, not goals: walkover to the present team, Corrido to `Ganador_Corrido_ID`, otherwise goals. Verify: `test_db_triggers_motor_formatos.py` proves a Corrido bracket advances.
- `POST /torneos/{id}/reabrir` ships in the same release as `cerrar_torneo`, clearing the three podium FKs and `Fecha_Cierre` and restoring `TORNEO.estado` and `FASE.estado`. Verify: `test_cierre_torneo.py` close-reopen-reclose round trip.
- Result writes are rejected on a closed tournament, reusing the archived-tournament guard pattern at `services/partido.py:212`. Verify: a mesa write against a closed tournament returns 400.
- `cerrar_torneo` rejects with a specific 400 when podium slots are tied through `gf`, and the close modal lets the admin order the tied teams explicitly. The server validates each submitted team is inscribed and is genuinely tied with the team it displaces. Verify: `test_cierre_torneo.py` tie cases.
- `cerrar_torneo` validates the standings table has at least as many rows as podium slots and that every podium team has PJ > 0; `generar_playoffs` validates the qualifier count before `_sortear_bracket`. Verify: a 3-team Liga with one unplayed team returns 400; an all-cancelled group returns 400.
- A vuelta cannot be finalised while its ida is not `Finalizado` or `Cancelado`, enforced in the same BEFORE trigger. Verify: finalising the vuelta first returns 400.
- Byes are assigned by seed rank, not by cross-list position, fixing the latent case in `_cruzar_grupos` as well. Verify: 2/4/6/8 qualifiers each give byes to the top seeds.
- B5 collapses to `ON DELETE SET NULL` on `Partido_Ida_ID`, matching `02_constraints.sql:249-250`. Delete ordering is not an alternative. Verify: rehacer sorteo with two-legged ties.
- B1 lands as its own commit with zero behavior change and existing trigger tests green, before any `Partido_Ida_ID` work.
- Bracket dates get real round spacing: round R at `fecha_base + 7*R`, vuelta at +3 days. Verify: `test_motor_formatos_llaves.py` date assertions.
- The stored podium renders as a snapshot ("Podio confirmado el {Fecha_Cierre}") and `estado-fase` flags when the computed top-3 differs from it.
- `_sortear_bracket` extracts `_crear_llave(padre, slot, formato, es_final)` so it keeps one branch per concept. Verify: `test_motor_formatos_algoritmos.py`.
- The VUELTA carries `partido_perdedor_siguiente_id` / `slot_perdedor_siguiente` for the Tercer Lugar hookup.
- `formato_eliminatoria` is exposed at tournament creation so a pure `Eliminacion` tournament can be two-legged.
- `_validar_parametros_formato`'s combined `equipos_por_grupo`/`clasificados_por_grupo` condition is split, with per-format error text.
- `Mixto` stays in the generator and the UI. The user named all three formats; cutting one is not a reviewer's call.
- Missing UI states ship: empty standings, close-rejected-on-tie, and ida-played/vuelta-pending in `BracketView`. The three-radio selector and the podium preview are checked at 375px.
- `cerrar_torneo` and `reabrir_torneo` each emit a structured log line naming torneo_id, usuario_id, resolved podium and fase transition.
- The `_sortear_bracket` docstring and the `fn_propagar_ganador_bracket` comment are updated to describe the two-legged shape in the same commit.
- The format-distribution query runs before coding: `SELECT formato, estado, COUNT(*) FROM TORNEO GROUP BY 1,2`.
- The `Preguntas abiertas` section is resolved in-plan and removed: Tercer Lugar always single; `clasificados_por_grupo` reused (pending Taste Decision T3); `formato_eliminatoria` at creation.
- Palmares across editions is deferred to TODOS.md, not built here.
- Bracket date spacing is exactly: round R at `fecha_base + 7*R`, vuelta at ida + 3 days. This supersedes the "+7 dias" wording in Implementation plan C1, which is struck.
- The alphabetical-tie defect is NOT fully covered by the close modal. `_cruzar_tabla_unica` must reject or surface a gf-level tie that straddles the qualification cut, because seeding a liguilla off an alphabetically-broken tie is the same defect one step earlier. `EstadisticasDelTorneo.tsx` and the public standings must render tied teams as tied rather than implying a ranking the data does not support. Taste Decision TD1 is restated accordingly: the close modal covers the podium write only.
- The closed-tournament write-guard is enforced in the trigger layer, not at one call site. Verified: the archived-tournament pattern needed two guards (`services/partido.py:211` and `services/hito_partido.py:144`, invoked at :315 and :362) and `services/evento_partido.py` has none at all, so a single-site lock would leave goals and cards writable on a closed tournament and the standings would keep moving. A BEFORE trigger rejecting writes when `TORNEO.estado = 'Finalizado'` covers PARTIDOS, EVENTOS_PARTIDO and HITOS_PARTIDO at once, and every future path. Verify: a goal recorded against a closed tournament returns 400.
- Manual podium ordering from the tie-resolution modal persists across `reabrir_torneo` and re-close: `reabrir` clears the three podium FKs, so the chosen order of tied teams is stored separately and re-offered as the default on re-close, never silently discarded.
- Taste decisions are labelled TD1/TD2/TD3 so they stop colliding with implementation tasks T1/T2/T3.
- PRE-EXISTING BUG, flagged not fixed here: `services/evento_partido.py` has no archived-tournament guard, so goals and cards can be recorded against an archived tournament today. `services/partido.py:197-198` calls that exact case "un agujero" and plugged it only for `registrar_resultado_directo`. CORRECTION to the earlier claim in this block that the closed-tournament trigger fixes it for free: it does not. Verified `chk_torneo_estado` is `Activo|Inactivo|Finalizado` (`02_constraints.sql:53`) while archived is `TORNEO_GRUPO.estado IN ('Activo','Archivado')` (`:38`) — different table. Covering archived needs a `TORNEO -> TORNEO_GRUPO` join in the same trigger. Do that, or the hole gets its own TODO; it does not come for free either way.
- PRECEDENCE: where this accepted block and the Implementation plan body disagree, this block wins. Specifically superseded and no longer authoritative in the body: the `Preguntas abiertas` section, the "a decidir en el gate" deferrals for `formato_eliminatoria` at creation and for Tercer Lugar, the "+7 dias" vuelta wording in C1, and the T1/T2/T3 taste-decision labels (now TD1/TD2/TD3).
- `fn_marcador_partido` return contract, stated once: it returns `(ganador_equipo_id, goles_local, goles_visitante)`. B1's "devuelve (goles_local, goles_visitante)" is superseded. `fn_resolver_llave` sums goals for goal-scored disciplines; for a Corrido llave it counts leg wins. Corrido rule: one win each is a tie and falls through to `Ganador_Desempate_ID` of the vuelta, same as a goal tie.
- A `Cancelado` leg contributes 0-0 and no leg win to the aggregate. It never blocks the vuelta (F12's guard accepts `Finalizado` or `Cancelado` on the ida).
- `POST /torneos/{id}/cerrar` takes `CerrarTorneoRequest { orden_podio: list[int] | None }` — the admin's explicit ordering of teams tied through gf, or null to take the table as-is. Section 3's "takes no body, so no input validation surface" is superseded: the server validates every submitted id is inscribed in the tournament and is genuinely tied with the team it displaces.
- Manual podium ordering needs storage, which Fase A1 does not define. Add `TORNEO.Orden_Podio_Manual JSONB NULL` in A1 — unless TD1 resolves toward `INSCRIPCIONES_TORNEO.orden_manual`, which subsumes it and is then the only place the order lives.
- `POST /torneos/{id}/reabrir` is missing from the Fase D table. Add it: `require_roles("TorneoAdmin")` + `require_torneo_access()`, no body, 400 if the tournament is not closed. It sets `TORNEO.estado = 'Activo'`, returns the last `FASE` to `En_Curso`, clears the three podium FKs and `Fecha_Cierre`, and leaves `Orden_Podio_Manual` intact so the admin does not redo it.
- The direct-close rejection keys on the CURRENT FASE tipo, never on `Torneo.formato`. C4's prose says "Formato Grupos" and the API table says "fase Grupos"; the formato reading would make every `Grupos_Playoffs` tournament permanently unclosable, including after its playoffs finish. Fase tipo is the rule.
- `cerrar_torneo` REJECTS with 400 when the tournament is already closed. It is not idempotent. The "idempotente y rechazado" wording in C3, the "400 idempotente" in the data-flow diagram and "idempotent-or-reject" in Section 4 all collapse to: reject with 400.
- `estado-fase` computes the podium-divergence flag only when `torneo_cerrado` is true. Section 7's "one count query" holds for the open-tournament path, which is the one that gets polled; a closed tournament adds one `tabla_posiciones` call per dashboard open.
- The write-guard trigger ships in the SAME release as `reabrir_torneo`, never before it. Section 9's "nothing to revert" is too optimistic otherwise: migration 32 alone would freeze every already-`Finalizado` tournament with no escape hatch.
- Write-guard trigger scope, stated explicitly: INSERT/UPDATE/DELETE on `EVENTOS_PARTIDO` and `HITOS_PARTIDO`, UPDATE on `PARTIDOS`. Exempt: the writes `cerrar_torneo` and `reabrir_torneo` make themselves. `_preparar_rehacer_si_corresponde` needs no exemption because it cannot run on a closed tournament. Cost is a 2-hop lookup on the hottest write path in the app — measure it against the existing evento-insert path before shipping, and if it registers, denormalize `Torneo.estado` onto `PARTIDOS` rather than accepting the join.
- Existing fixtures that seed a `Finalizado` tournament and then write matches or events will start failing once the guard lands. Audit `backend/tests/` for that pattern as part of the same change.
- Out-of-order leg finalisation with two concurrent mesa operators needs `SELECT ... FOR UPDATE` on the ida inside `fn_resolver_llave`'s read; the BEFORE-trigger guard alone does not serialize them.
- Tournaments already at `estado='Finalizado'` keep NULL podium columns. No backfill: their podium was never recorded and cannot be reconstructed reliably. They are reopenable via `reabrir_torneo` and closeable again if an organizer wants the podium filled in.
- Effort, stated once because the body disagrees with itself: base plan (Approach A, Fases A-F) is human ~1.5 weeks / CC ~3-4h. The review-accepted additions are human ~4-5 days / CC ~3h. Total human ~3 weeks / CC ~7h. The 16 implementation tasks cover review-surfaced work only; Fases A-F carry no task entries by design.
<!-- /autoplan-accepted:ceo -->

<!-- autoplan-accepted:design -->
- The podium renders ONCE, in `TorneoDashboard`'s header region beside `Estado:` (`TorneoDashboard.tsx:154`), visible from every tab; `MotorFormatosPanel` returns null when `torneo_cerrado`. This resolves hard rejection #7 (verified: four `<div className="card">` returns at `MotorFormatosPanel.tsx:96,111,130,144` plus `BracketView`, and plan E1+E4 would have added a sixth and seventh rendering the same three names). Verify: one podium per page.
- The podium is one block with three rows, never three cards: 1° at ~1.5rem weight 800 as the page's visual anchor, 2° and 3° at body weight beneath. Rank colors, if used, are `--podio-oro`/`--podio-plata`/`--podio-bronce` on `:root`, never hardcoded hex.
- A degenerate podium renders explicit copy, never a blank slot: "2 equipos — sin tercer puesto." in place of the third row when `Tercer_Puesto_Equipo_ID` is NULL.
- The primary button label is derived from `acciones_disponibles`, not hardcoded: both actions → "Configurar Siguiente Fase"; `cerrar_directo` alone → "Cerrar Torneo"; `generar_playoffs` alone → "Generar Playoffs". Per the plan's own C4 table a resolved final yields `["cerrar_directo"]`, where "Configurar Siguiente Fase" mislabels a tournament-ending action.
- `MotorFormatosPanel` gets one `<h3>` per state naming the area ("Fase de Grupos", "Fase Eliminatoria", "Resultado final"), then one line of state, then one action. Verified: the panel body currently has zero headings.
- Loading: the action zone renders a skeleton with reserved height so the button does not pop in and the panel does not shift when `GET /estado-fase` resolves. The plan converts a client-derived render into a network read and must not introduce layout shift doing it.
- Busy: both `POST /cerrar` and `POST /playoffs` disable their button, show a label ("Cerrando…" / "Generando llaves…") and guard against double submit. An 8-team two-legged bracket writes ~14 rows.
- Errors render inline inside the modal, never a toast, mapped per cause across all six 400s the plan defines. The user must be able to read the error and correct it without reopening the modal.
- `BracketView` renders four llave states, not one: unplayed; ida played and vuelta pending (the state a two-legged bracket spends most of its life in); blocked on an unresolved aggregate tie; and walkover on one leg. The blocked state gets a "Requiere desempate" badge and a CTA into the vuelta — without it the trigger silently stops propagating and the bracket freezes with no stated reason.
- One node = one llave. A card with two compact leg rows, a `border-top` divider, and the aggregate on its own row at weight 700. Column count and scroll model stay identical to `Unico`; `.bracket__columna` widens from 180px to 220px when a llave has legs (`.bracket` already scrolls horizontally).
- `.bracket__partido` gains a date header row (`tabular-nums`, `--text-muted`, same treatment as `.fila-partido__hora` at `index.css:2032`). Round spacing makes dates the thing organizers publish and there is currently no slot for them anywhere in the bracket.
- The desempate control is inline in the existing save flow, not a second modal: a required radio group above `.confirmar-evento__acciones` with the real team names, reusing the disabled-reason `<p className="muted">` slot that `ModalResultadoDirecto.tsx:772` already uses for incomplete goals. Radios, not a select.
- Tie resolution in the close modal is an ordered list using `.alineacion-fila` + `.alineacion-fila__mover` (verified 56×44px at `index.css:1625/1670`), NOT `CeldaOrdenManual`'s numeric input — a number field accepts 1/1/2 in a three-way tie and fails server-side after submit, while a reorder list cannot express an invalid order.
- The podium preview shows Pts · DG · GF per row and a per-row note whenever the position is decided below points ("Desempatado por diferencia de gol"). A title decided by `orden_manual` gets a prominent notice, not a footnote.
- The one-way confirm names the act: "Cerrar torneo y coronar a {Equipo}", never "Confirmar". The consequence line ("No vas a poder cargar mas resultados") sits in the step-1 radio itself, not only in step 2a.
- A closed tournament explains itself with `.banner-info-persistente` (`index.css:1824`, `--warning`, `aria-live="polite"`) on Partidos and Control de Mesa: "Torneo cerrado el {fecha}. Los resultados estan bloqueados." A lock with no stated cause reads as a broken app.
- Reabrir reuses `.boton-cierre-forzado` + `.cierre-forzado-confirmar` (`index.css:689/706`) — the app's established treatment for reversing a committed state, whose own comment requires it never look like a routine close. No new modal.
- The podium carries its provenance: "Podio confirmado el {Fecha_Cierre}". On divergence from the live table, a `--warning` strip NAMES the delta ("La tabla actual ya no coincide: 1° seria Leones. Reabri el torneo y volve a cerrarlo.") — never a generic "los datos cambiaron", never a silent re-snapshot, never two podiums side by side.
- "N de M resueltos" is replaced everywhere by the three-part count: "28 jugados · 2 cancelados · 0 pendientes". The corrected Finalizado-or-Cancelado rule must be visible; "30 de 30 resueltos" to someone with two cancellations reads as a system error.
- The incomplete phase is a first-class state, not an absence: the heading plus the three-part count as the stated reason the action is unavailable.
- The format selector shows consequence, not mechanics: a live computed line per option ("14 partidos · la final cae aprox. el {fecha}") plus "La vuelta se agenda 7 dias despues de la ida. Podes mover las fechas despues desde cada partido."
- `ModalSiguienteFase` gets a step model: "Paso 1 de 2 · Camino" / "Paso 2 de 2 · Playoffs", a "← Volver" in the action row, and `.modal-panel--ancho` (560px) for step 2 only. Returning to step 1 preserves step 2b's selections — losing them would regress the current `ModalClasificadosPorGrupo`.
- Focus management is added ONCE on the shared `.modal-panel`: focus trap, Escape to close, focus return to the trigger. Verified gap: `ModalClasificadosPorGrupo` sets `aria-modal="true"` today with none of the three, and the longer two-step flow would deepen it.
- Decision-critical copy moves off `.muted` (verified 0.85rem = 13.6px at `index.css:199`) onto a new `.muted--cuerpo { font-size: 1rem; color: var(--text-muted); }`. Applies to the format subtitles, the podium provenance date and every disabled-reason. `.muted` itself is unchanged — it is load-bearing across the app. Contrast already passes at ~6.3:1.
- Both the path choice and the format choice are radio groups, not selects: every option visible without a tap, keyboard and screen-reader native.
- On successful close the modal closes, the page scrolls to the podium, and there is exactly one reveal. It respects `prefers-reduced-motion`.
- Scores and dates added to the bracket and standings use `font-variant-numeric: tabular-nums`.
- The plan introduces no new color, shadow or font. Any new surface cites the existing `index.css` class it extends.
- NOT fixed here, flagged: `index.css:30` uses `system-ui` as the body voice (AI-slop blacklist #11) and browser surfaces (selection, caret, scrollbars, focus rings) are unthemed. Both are app-wide and pre-existing; they belong to `/design-consultation`, not this plan.
- Visual mockups were NOT generated despite `DESIGN_READY`, because the surface is OPERATE inside a fixed token system and every finding resolves to an existing class with a line number. Recorded as taste decision TD4 so the user can override at the gate.
- CRITICAL, from the second design pass over the amended plan: the closed-tournament write-guard trigger rejects writes on EVENTOS_PARTIDO, HITOS_PARTIDO and PARTIDOS — that is every scoring interaction in the product. A mesa operator would tap "gol" mid-match and get a raw 400 with no explanation. Scoring controls are DISABLED BEFORE the attempt, never failing after it: `Cronometro.tsx` and the resultado-directo surface render a locked state with the persistent cause banner, every control disabled, and a link to Reabrir for a `TorneoAdmin`. Verify: no scoring control is clickable on a closed tournament, and none produces a raw server error.
- Reabrir gets an explicit entry point in the closed-state panel next to the podium, with a confirm that names both consequences: "Se borra el podio registrado; el orden manual se conserva." A non-admin viewing a closed tournament sees the podium and no Reabrir control at all.
- The gf tie is DETECTED AT PREVIEW, not rejected after confirm. Step 2a already reads `tabla_posiciones`, so the tie is knowable before the user clicks: render the tied rows as tied and inline the ordering control before enabling confirm. The 400 stays as a server guard, never as the primary path. The same principle applies to `_cruzar_tabla_unica`: surface a tie straddling the qualification cut at preview time rather than rejecting afterwards.
- Two of the six `cerrar_torneo` rejections must never reach the user: fase-tipo-Grupos and already-closed are both knowable from `estado-fase`, so the control is ABSENT in those states rather than present-and-rejecting. The plan already states this invariant ("el modal nunca muestra una opcion que el servidor va a rechazar"); it is extended to every case. The remaining rejections get a copy table mapping each to user-facing text plus the recovery action.
- When `acciones_disponibles` has exactly one entry, step 1 of the modal is SKIPPED and the primary button is labelled for that action. A one-option radio screen is a dead step.
- Corrido (non-goal) disciplines get their own aggregate copy. "Global 2-1" is meaningless for Tenis or Ajedrez, where a llave is decided on leg wins with one-each falling through to `Ganador_Desempate_ID`. Second variant: "Ida: Equipo A · Vuelta: Equipo B · Definido por desempate: Equipo A", and the format radio subtitles say "cruce" rather than implying scorelines.
- `BracketView` specifies three explicit card variants, not one: the single-leg card (unchanged), the llave card (two result rows plus a global row, connectors anchored to the card), and the EMPTY-SHELL llave card — an unsorted `Ida_Vuelta` bracket is two empty cards per slot and doubles the visual noise of a bracket that has not started. Under `Mixto` the final column uses the single-leg variant inside a double-leg bracket, which makes that column asymmetric by design.
- The 375px check covers `BracketView` in all three formats and the tie-ordering interaction, not only the radio selector and podium preview. Those are the two components that actually break at that width. Tie ordering uses up/down buttons, never drag — drag-to-reorder at 375px is a known trap.
- The podium divergence flag is ADMIN-ONLY and neutral in tone ("El podio registrado no coincide con la tabla actual — registrado el {fecha}") with Reabrir as the adjacent action. It never appears on the public portal: a public viewer told "this podium might be wrong" is worse off than one seeing a stale podium.
- Step 2a's confirm disables on submit with an in-button pending state and locks modal dismissal while in flight. It triggers a multi-write server operation; double-submit on a slow connection produces a confusing "ya esta cerrado" 400 from the user's own second click.
<!-- /autoplan-accepted:design -->
