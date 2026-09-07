# Plan: Cascada de Archivado de Torneos + Corrección de "Datos Fantasma" en Traspasos

Generado con `/autoplan` (revisión CEO → Design → Eng). Codex no está
disponible en esta máquina (`codex` no está en PATH) — las 3 fases
corrieron en modo `[subagent-only]`, una sola voz revisora (Claude), mismo
precedente que `docs/plans/equipos-jugadores-plan.md`,
`docs/plans/fixes-datos-traspasos-control-mesa-plan.md` y
`docs/plans/control-mesa-centralizacion-fixture-plan.md` para este mismo
repo. Cada hallazgo de este documento cita archivo:línea — ninguno se
apoya en "debería ser así".

**Solo documento — sin implementación.** El usuario pidió explícitamente
el plan, no código.

---

## 0. Resumen ejecutivo (para no perderse en el documento)

El pedido llega dividido en 3 áreas. Verificado contra el código real,
son en realidad **2 gaps reales + 1 documento de "esto ya existe"**:

| # | Área pedida | Es... | Alcance de este plan |
|---|---|---|---|
| 1 | Archivado de torneos en cascada (ocultar del menú público + de Control de Mesa; reactivar los devuelve) | **Gap real, confirmado.** 3B-7 (`TODOS.md:132-136`) documentó explícitamente que Archivar es "sin cascada a las ediciones existentes" — fue una decisión de alcance deliberada en su momento, no un bug. Este plan la **extiende** a pedido del usuario. | Cambios acotados en 2 repositorios backend, 0 cambios de esquema |
| 2 | Convocados/Titulares/Suplentes en Control de Mesa + "converge toda la configuración de un partido ahí" + alineaciones en la vista pública | **Ya implementado por completo**, verificado línea por línea (ver Sección 1.2). Nada que construir. | **Cero código** — este documento cita dónde vivo cada pieza |
| 3 | Bug de "datos fantasma" al anular un traspaso | **Bug real, causa raíz confirmada — una sola pantalla, un filtro faltante.** No es el modelo de datos (que es intencional: nunca borra historial), es que una pantalla no filtra ese historial al mostrar la plantilla vigente. | Fix de 1 archivo frontend, sin backend nuevo |

El trabajo real de este plan es la cascada de archivado (Área 1) y el fix
del bug de traspasos (Área 3). El Área 2 es, en los hechos, un reporte de
"esto que pedís ya está en producción" — como pasó con la mitad de
"Parte B" en `fixes-datos-traspasos-control-mesa-plan.md`.

---

## Fase 1 — CEO Review (Estrategia y Alcance)

### 1.1 — Área 1: Archivado en cascada — premisas

| # | Premisa | Veredicto |
|---|---|---|
| P1 | El botón "Archivar" de `/torneo-admin/torneos` (`TorneosAdmin.tsx:679-691`) dispara `PATCH /torneo-grupos/{id} {estado: "Archivado"}` (`torneo_grupos.py:45-56` → `TorneoGrupoService.update`, `torneo_grupo.py:32-36`), que hace un `UPDATE` de una sola columna sobre `TORNEO_GRUPO`. **No toca ninguna fila de `TORNEO` ni de `PARTIDOS`.** | Confirmado leyendo el código — comportamiento actual verificado. |
| P2 | Esto **no es un bug**: `TODOS.md:132-136` documenta 3B-7 explícitamente como "Baja lógica..., sin cascada a las ediciones existentes — oculto de `GET /torneo-grupos` por default". Fue una decisión de alcance consciente cuando se implementó. | Confirmado — el pedido del usuario es una **extensión** de un alcance ya cerrado a propósito, no la corrección de una regresión. |
| P3 | `GET /torneos` (`torneos.py:14-41`, `TorneoRepository.list`, `torneo.py:46-68`) no tiene ningún `JOIN` ni filtro contra `TORNEO_GRUPO.estado` — devuelve TODAS las ediciones de un grupo archivado exactamente igual que las de uno activo. Este endpoint alimenta el menú público (`DashboardPage`, `Dashboard.tsx:10`, `GET /torneos?estado=Activo` — sin auth) y el selector de torneo de `/control-de-mesa` (`ControlDeMesa.tsx:243-245`, `GET /torneos?solo_mios=true`). | Confirmado — es el gap exacto que describe el pedido: "el menú principal" y el selector de Control de Mesa muestran ediciones de un grupo archivado sin distinción. |
| P4 | `GET /partidos` (`partidos.py:54-85`, `PartidoRepository.list`, `partido.py:13-35`) tampoco tiene ningún `JOIN` contra `TORNEO_GRUPO` — la lista que alimenta `/control-de-mesa` (`ControlDeMesaPage`, `ControlDeMesa.tsx:263-272`, `GET /partidos?solo_mios=true&torneo_id=...`) no distingue si el torneo del partido pertenece a un grupo archivado. | Confirmado — segundo gap exacto que describe el pedido ("partidos pendientes... en el dashboard de /control-de-mesa"). |
| P5 | `TORNEO.estado` (Activo/Inactivo/Finalizado — ciclo de vida de la EDICIÓN, 3A-9) y `TORNEO_GRUPO.estado` (Activo/Archivado — ciclo de vida del GRUPO, 3B-7) son dos campos independientes en dos tablas distintas. Una edición puede tener `estado='Activo'` con su grupo `Archivado` — el filtro de `?estado=Activo` del Dashboard NO alcanza a resolver esto por casualidad. | Confirmado — el fix necesita un `JOIN` nuevo, no reusar el filtro `estado` existente. |
| P6 | Un consumidor SÍ necesita ver las ediciones de un grupo archivado sin el filtro nuevo: el selector de ediciones de la pestaña Estadísticas dentro de un torneo YA ABIERTO (`EstadisticasDelTorneo.tsx:74`, `GET /torneos?torneo_grupo_id=X`) — si un admin navega directo a un torneo cuyo grupo está archivado (vía URL, o desde "Ver Torneo" en la propia `TorneosAdminPage` con "Ver archivados" activado), ese selector se rompería si el filtro nuevo aplicara siempre. | Confirmado — mismo criterio que ya usa `/torneo-grupos/{id}`: "sigue siendo consultable... directo, sin filtro" (comentario en `torneo_grupos.py:26-28`). El filtro nuevo debe aplicar SOLO cuando `torneo_grupo_id` no viene explícito en la consulta (listado general/de navegación), nunca cuando se pide un grupo puntual ya conocido. |
| P7 | `HitoPartidoService.registrar()` (`hito_partido.py:173-186`) ya es el único punto por el que pasa cualquier intento de `Inicio_Partido` (dashboard de Control de Mesa o `Cronometro.tsx`), y ya resuelve `torneo = await self.torneo_repo.get_or_404(partido.torneo_id)` dentro de `_validar_titulares` (`hito_partido.py:143`). Es el lugar natural para una defensa en profundidad contra arrancar un partido de un torneo archivado si alguien lo intenta vía API directa, evitando la UI que ya lo oculta. | Confirmado — mismo patrón ya usado para B.2 (validación de titulares), mismo archivo, mismo método. |

### 1.2 — Área 2: Control de Mesa + Alineaciones — verificación de "qué ya existe"

**Principio aplicado: Claimed Limitations Need Evidence.** Antes de
planear una sola línea de código para esta área, se verificó cada pieza
del pedido contra el código real. El resultado: **el pedido ya está
implementado por completo**, en su mayoría por
`docs/plans/fixes-datos-traspasos-control-mesa-plan.md` (Requerimiento
B.1/B.2, implementado 2026-09-04) y
`docs/plans/control-mesa-centralizacion-fixture-plan.md` (implementado en
el commit `4108858 Centralizar Control Mesa - Correcciones`, HEAD actual
de esta rama).

| Sub-pedido del usuario | Estado | Evidencia (archivo:línea) |
|---|---|---|
| "Configuración de Convocados y Titulares" habilitada | ✅ Ya existe | `Convocatoria.tsx` — checkbox "Convocado" + checkbox "Titular" por jugador de cada plantel (`Convocatoria.tsx:160-176`), `PUT /partidos/{id}/convocados` |
| "Seleccionar y modificar titulares y suplentes ANTES de Empezar Partido" | ✅ Ya existe | `<Convocatoria .../>` se renderiza sin ninguna condición de `partido.estado` (`ControlDeMesa.tsx:1124-1130`) — siempre visible, incluso con el partido en "Programado" (antes de arrancar) |
| "Todo lo que le pueda hacer a un partido debe converger en Control de Mesa" | ✅ Ya existe | `PartidosDelTorneo.tsx:48-49`: *"es de SOLO LECTURA para la operación del partido en curso: 'editar'... y 'Walkover' se mudaron a Control de Mesa"* (línea 140: *"Solo lectura — la carga de resultados, convocatoria y cronómetro se hacen desde Control de Mesa"*). `ControlDeMesa.tsx` ya tiene: Cronómetro (`Cronometro.tsx`), Convocatoria, Carga de eventos en vivo (`CargaEvento`), **y** "Cargar resultado directo" sin cronómetro (`ControlDeMesa.tsx:423`, `ModalResultadoDirecto`, `POST /partidos/{id}/resultado-directo`, `ControlDeMesa.tsx:623`) |
| Bloquear "Empezar Partido" sin titulares completos | ✅ Ya existe | `useTitularesCompletos` + `BotonEmpezarPartido` (`ControlDeMesa.tsx:130-224`) — botón deshabilitado con el detalle "{equipo}: N/M titulares" hasta que ambos planteles cumplen `Modalidad.tamano_equipo`; backend replica el mismo chequeo (`hito_partido.py:120-171`, `_validar_titulares`) como fuente de verdad |
| Vista pública — alineaciones, Local a la izquierda / Visitante a la derecha, Titulares arriba, Suplentes abajo | ✅ Ya existe | `PartidoEnVivo.tsx:224-243` — sección "Alineaciones" con `.convocatoria-equipos` (grid de 2 columnas, mismo layout que `Convocatoria.tsx`), local primero y visitante segundo (`AlineacionEquipo` × 2, líneas 229-240) |
| Suplentes ordenados por dorsal | ✅ Ya existe | `titulares`/`suplentes` se derivan con `.filter()` (`PartidoEnVivo.tsx:286-287`) sobre `plantilla`, que llega ya ordenada por dorsal desde el backend: `ORDER BY dorsal NULLS LAST, jugador` (`estadisticas.py` repo, `vw_jugadores_activos_por_equipo`) — `.filter()` preserva el orden de origen, así que Titulares y Suplentes salen ordenados por dorsal sin código adicional |

**Conclusión del Área 2: no hay tarea de implementación.** El único
entregable de esta área en este plan es esta tabla — para que quede
registrado con evidencia que el pedido ya está resuelto, en vez de
reconstruir algo que funciona.

### 1.3 — Área 3: Bug de traspasos — premisas

| # | Premisa | Veredicto |
|---|---|---|
| P8 | `TraspasoService.anular()` (`traspaso.py:151-221`) **nunca borra ninguna fila** de `JUGADOR_EQUIPO` — pone la membresía del destino en `estado='Inactivo'` (línea 199) y, si había origen, la reactiva a `'Activo'` (línea 215). Esto es **por diseño**, documentado explícitamente en el modelo (`jugador_equipo.py`, comentario de `Traspaso`) y coherente con "TRASPASOS... trayectoria inmutable" del plan original (`equipos-jugadores-plan.md`, EC-20: *"No se permite editar ni borrar... corregir un error es un traspaso nuevo"*). | Confirmado — el modelo de datos NO es el bug. Cambiar esto a un DELETE real rompería la trayectoria que usa `GET /jugadores/{id}/perfil` (Perfil de Jugador) y contradice un invariante ya establecido en 2 lugares del código. |
| P9 | `GET /plantillas?torneo_id=X` (`plantillas.py:34-45`, `JugadorEquipoRepository.listar_por_torneo`, `jugador_equipo.py` repo líneas 33-66) **no filtra por `estado`** — devuelve TODAS las filas de `JUGADOR_EQUIPO` de ese torneo, incluyendo `Inactivo` y `Traspasado`. Esto es correcto e intencional para sus otros consumidores (ver P10). | Confirmado — el endpoint es genérico a propósito, el problema está en quién lo consume sin filtrar después. |
| P10 | `PlantillasDelTorneo.tsx` (pantalla de "Plantillas" por torneo — donde viven las tarjetas de Snoopy FC / Aguilas del Sur / Tiburones FC del reporte) usa ese `GET /plantillas?torneo_id=X` sin filtrar por estado en el render: `gruposPorEquipo` (líneas 134-150) agrupa TODOS los vínculos por equipo, y el `.map()` que dibuja las tarjetas (líneas 313-358) itera `grupo.vinculos` — el array SIN filtrar — mostrando una tarjeta por cada fila `Inactivo`/`Traspasado` con un badge literal del estado (línea 342: `{v.estado !== "Activo" && <span className="badge badge--suspendido">{v.estado}</span>}`). | **Confirmado — esta es la causa raíz exacta del bug reportado.** Caso 1 (Gabriel C en Aguilas del Sur con "Inactivo"): es la fila que `anular()` dejó en `Inactivo` en el destino, nunca borrada, ahora renderizada como si fuera un jugador más de la plantilla. Caso 2 (Gabriel Soto duplicado "Traspasado" + "Inactivo" en Tiburones FC): dos filas históricas distintas del mismo perfil en el mismo roster — una que quedó `Traspasado` cuando salió, otra que quedó `Inactivo` cuando un traspaso posterior HACIA Tiburones fue anulado — ambas se acumulan sin límite porque nada las filtra. |
| P11 | El patrón correcto YA EXISTE en el propio código, en una pantalla hermana: `ModalGestionarPlantilla.tsx:98` — `const plantillaActiva = (plantillas.listQuery.data ?? []).filter((p) => p.estado === "Activo")`. Mismo endpoint (`GET /plantillas`), mismo shape de dato, filtro de una línea. | Confirmado — el fix no inventa nada, aplica un patrón ya probado en producción en un archivo hermano (P4 DRY). |
| P12 | Se revisaron los otros 2 consumidores de "roster actual" que también leen `GET /plantillas`: `EquiposDelTorneo.tsx:218-219` (`if (p.estado !== "Activo") continue`) y `useTitularesCompletos` en `ControlDeMesa.tsx:169-174` (`.filter((j) => j.estado === "Activo")`) — **ambos ya filtran correctamente.** `PlantillasDelTorneo.tsx` es la única pantalla con el defecto. | Confirmado por barrido completo (P1 completeness) — no es un patrón sistémico, es un archivo puntual que quedó afuera. Mismo tipo de hallazgo que ya documentó `fixes-datos-traspasos-control-mesa-plan.md` para el "Bug 2" de nombres (7 de 8 pantallas arregladas, una se saltó). |
| P13 | Los otros 2 consumidores de `GET /plantillas` que SÍ necesitan ver `Inactivo`/`Traspasado` — `TraspasosDelTorneo.tsx:62,88` (resuelve "equipo de origen"/dorsales históricos por `jugador_perfil_id`, necesita el historial completo) y el endpoint de Perfil de Jugador (trayectoria) — no se tocan en este plan: filtrarlos rompería su propósito. | Confirmado — el fix debe ser puntual a `PlantillasDelTorneo.tsx`, nunca al backend (ver D2). |

### Qué ya existe (leverage map)

| Sub-problema | Ya cubierto por | Qué falta |
|---|---|---|
| Ocultar `TORNEO_GRUPO` de sus propios listados | `GET /torneo-grupos` + `incluir_archivados` (3B-7) | Nada — no se toca |
| Patrón "listado general filtra, acceso directo/scoped no" | Ya establecido en `/torneo-grupos/{id}` (P6) | Replicar el mismo criterio en `/torneos` y `/partidos` |
| RBAC scoped de listas (`solo_mios`) | `TorneoRepository.list`/`PartidoRepository.list` (override `IN`, control-mesa-centralizacion-fixture-plan.md) | Nada — el filtro de archivado se agrega AL LADO de este mecanismo, no lo reemplaza |
| Convocatoria/Titulares/Suplentes en Control de Mesa | `Convocatoria.tsx`, `useTitularesCompletos`, `_validar_titulares` | Nada — Área 2 completa (Sección 1.2) |
| Alineaciones en vista pública, ordenadas por dorsal | `PartidoEnVivo.tsx`, `vw_jugadores_activos_por_equipo` | Nada — Área 2 completa |
| Filtrar plantilla vigente a solo `Activo` | `ModalGestionarPlantilla.tsx:98`, `EquiposDelTorneo.tsx:218-219`, `useTitularesCompletos` | Aplicar el mismo filtro en `PlantillasDelTorneo.tsx` (única pantalla que falta) |

### Alcance

**Dentro de este plan:**
- Cascada de archivado: `GET /torneos` y `GET /partidos` excluyen por
  default las ediciones/partidos cuyo `TORNEO_GRUPO.estado='Archivado'`,
  **excepto** cuando la consulta pide un `torneo_grupo_id` puntual (P6) —
  reactivar el grupo revierte el filtro sin código adicional (estado
  derivado, no una bandera a mantener sincronizada).
- Defensa en profundidad: `HitoPartidoService.registrar()` rechaza
  `Inicio_Partido` con 409 si el torneo pertenece a un grupo archivado.
- Fix del bug de traspasos: `PlantillasDelTorneo.tsx` filtra sus
  tarjetas a `estado === "Activo"`, mismo patrón que sus 2 archivos
  hermanos.
- Documentar (sin tocar código) que Convocados/Titulares/Suplentes y
  Alineaciones públicas ya están completos.

**Fuera de este plan (→ `TODOS.md`):**
- Ocultar partidos `En curso`/`Finalizado` de un torneo archivado en
  Control de Mesa — el pedido dice explícitamente "partidos
  **pendientes**"; un partido ya arrancado en un torneo que se archiva a
  mitad de camino debe poder seguir operándose hasta terminarlo, no
  quedar huérfano (ver D1 y EC-A4).
- Un toggle "Ver archivados" dentro de Control de Mesa — no hace falta:
  la pantalla de solo-lectura `PartidosDelTorneo.tsx` (ya existe, ver
  Área 2) sigue mostrando el fixture completo de cualquier torneo,
  archivado o no, sin este cambio — es el escape hatch natural para
  revisión histórica.
- Migrar `PlantillasDelTorneo.tsx` a un filtro **server-side**
  (`GET /plantillas?estado=Activo`) — el patrón establecido en este
  repo para "solo activos" es cliente-side (3 de 3 pantallas hermanas lo
  hacen así); cambiar el contrato del endpoint es una superficie mayor
  para el mismo resultado (P3 pragmatismo).
- Cualquier cambio al modelo de `TRASPASOS`/`JUGADOR_EQUIPO` o a
  `TraspasoService.anular()` — el modelo actual es correcto y ya está
  documentado como intencional (P8); el bug era 100% de lectura.

### Dream state

```
ACTUAL                              ESTE PLAN                          IDEAL 12 MESES
──────────────────────              ──────────────────────             ──────────────────────
Archivar un torneo lo saca de        GET /torneos y GET /partidos       + Un solo helper de
la Pestaña Torneos, pero sigue       excluyen por default las           repositorio compartido
apareciendo en el menú público       ediciones/partidos de un           ("scope activo vs.
y en el selector de Control          grupo archivado — salvo            archivado + torneo_ids_
de Mesa como si nada.                acceso directo/scoped              permitidos") si aparece
                                      (Estadísticas de un torneo         un tercer recurso que
                                      ya abierto sigue andando).         necesite el mismo patrón.

Convocados/Titulares/Suplentes      (sin cambios — ya está           + Un badge visual
y alineaciones públicas: ya          completo, se documenta)            "Suplente" explícito en
completo, pero nadie lo había                                           Convocatoria.tsx (hoy es
verificado contra el pedido                                             "convocado sin marcar
actual del usuario.                                                     Titular", correcto pero
                                                                         implícito).

Anular un traspaso deja una          PlantillasDelTorneo.tsx           + Si algún día se agrega
fila "fantasma" visible en la        filtra a Activo, igual que         un tab de "Historial del
plantilla del club destino           sus 2 hermanas — la fila           equipo" a propósito,
(Inactivo/Traspasado mezclados       Inactiva sigue en la base          reusa exactamente estas
con jugadores activos).              (trayectoria intacta), solo        mismas filas Inactivo/
                                      deja de mostrarse donde no         Traspasado que hoy
                                      corresponde.                      ensucian la vista.
```

---

## Fase 2 — Design Review (UX)

Aplica parcialmente — Área 2 no tiene cambios visuales (ya existe). Área
1 y Área 3 son comportamiento de listas existentes que cambia de qué
filas trae, no una pantalla nueva.

### Flujo 1 — Archivar/Reactivar (comportamiento en cascada)

```
[/torneo-admin/torneos] click "Archivar" en un grupo
        │
        ▼
PATCH /torneo-grupos/{id} {estado: "Archivado"}   (sin cambios — ya existe)
        │
        ├──▶ Pestaña Torneos: el grupo desaparece de la lista (ya existía, 3B-7)
        │
        ├──▶ NUEVO: Menú público (Dashboard.tsx) — sus ediciones dejan de
        │     aparecer en el selector "Torneo:" — GET /torneos ya no las trae
        │
        └──▶ NUEVO: /control-de-mesa — sus partidos "Programado" dejan de
              aparecer en la lista — GET /partidos ya no los trae.
              Si alguien intenta arrancar uno igual por API directa,
              HitoPartidoService.registrar() rechaza con 409.
              Partidos ya "En curso"/"Finalizado" de ese torneo NO se
              tocan — siguen visibles y operables (ver EC-A4).

[/torneo-admin/torneos] click "Reactivar"
        │
        ▼
PATCH /torneo-grupos/{id} {estado: "Activo"}
        │
        └──▶ Los 3 puntos de arriba se revierten automáticamente — el
              filtro nuevo es sobre TORNEO_GRUPO.estado en tiempo real,
              no una bandera copiada que haya que sincronizar de vuelta.
```

### Estados de interacción — Área 1

| Estado | Comportamiento |
|---|---|
| Grupo archivado, admin navega directo a una de sus ediciones (URL, o "Ver Torneo" con "Ver archivados" activado en la Pestaña Torneos) | El dashboard de esa edición sigue funcionando entero — `GET /torneos/{id}` (get puntual) y `GET /torneos?torneo_grupo_id=X` (selector de Estadísticas) no llevan el filtro nuevo (P6). Solo el listado GENERAL (sin `torneo_grupo_id`) lo aplica. |
| Grupo archivado con un partido `En curso` en el momento de archivar | El partido sigue apareciendo y operable en Control de Mesa hasta que se finalice — solo los `Programado` se ocultan (alcance explícito, ver "Fuera de este plan"). |
| TorneoAdmin sin acceso a ningún torneo (`solo_mios=true`, sin asignaciones) | Sin cambios — sigue viendo 0 filas, el filtro de archivado es adicional, no interfiere con ese caso ya cubierto. |
| Admin intenta `POST /partidos/{id}/hitos {Inicio_Partido}` por API directa sobre un partido de un torneo archivado | 409 con mensaje explícito ("Este torneo está archivado — reactivalo antes de operar sus partidos.") — la UI nunca ofrece el botón porque el partido ni siquiera aparece en la lista, este es solo el resguardo de backend. |

### Flujo 2 — Plantilla del equipo (fix del bug de traspasos)

```
[/torneo-admin/torneos/{id}/plantillas] tarjeta de "Aguilas del Sur"
        │
        │  ANTES: gruposPorEquipo agrupa TODOS los vínculos (Activo +
        │  Inactivo + Traspasado) → la tarjeta muestra a Gabriel C con
        │  badge "Inactivo" aunque ya no juegue ahí (fantasma).
        │
        │  DESPUÉS: gruposPorEquipo filtra a estado === "Activo" antes
        │  de agrupar → la tarjeta solo muestra quién juega ahí AHORA.
        ▼
Tarjeta "Aguilas del Sur (N jugadores)" — N = solo activos, sin
duplicados, sin badges de estados terminales colándose entre jugadores
vigentes.
```

### Estados de interacción — Área 3

| Estado | Comportamiento |
|---|---|
| Traspaso anulado, jugador vuelve al origen | Origen: reaparece activo (sin cambios, ya funcionaba). Destino: la fila `Inactivo` deja de renderizarse como tarjeta — desaparece de la plantilla visual del club destino (el registro sigue existiendo en la base, ver Fase 3). |
| Jugador con múltiples ciclos traspaso/anulación en el mismo equipo | Todas las filas terminales (`Inactivo`/`Traspasado`) de ese perfil en ese roster quedan ocultas de la tarjeta por igual — nunca aparece más de una vez a la vez (solo su fila `Activo` actual, si la tiene). |
| Equipo con 0 jugadores activos pero con historial (todos traspasados/dados de baja) | La tarjeta pasa a mostrar "Sin jugadores todavía" (rama ya existente, `PlantillasDelTorneo.tsx:319-323`) en vez de una lista de fantasmas — comportamiento nuevo correcto, sin caso especial de código (la lista filtrada simplemente queda vacía). |
| Historial completo del jugador (Perfil de Jugador, Traspasos) | Sin cambios — esas pantallas siguen leyendo el mismo `GET /plantillas` sin el filtro nuevo, porque el filtro se aplica solo dentro de `PlantillasDelTorneo.tsx`, nunca en el backend (P13). |

### Litmus scorecard (resumen)

| Dimensión | Score |
|---|---|
| Estados especificados (cascada: 4 estados de la tabla de Área 1; bug: 4 estados de la tabla de Área 3) | 9/10 |
| Especificidad (mensaje 409 de "Empezar Partido" en torneo archivado nombra la causa, no un error genérico) | 9/10 |
| Alineación con patrones existentes (reusa el criterio de `/torneo-grupos/{id}` para el filtro scoped-vs-general; reusa el filtro de `ModalGestionarPlantilla.tsx` tal cual) | 9/10 — cero UI nueva, cero componente nuevo |
| Reversibilidad (Reactivar deshace todo sin estado adicional que sincronizar) | 10/10 — filtro derivado, no una copia de bandera |

---

## Fase 3 — Eng Review (Arquitectura, Datos, Edge Cases, Tests)

### Arquitectura

```
Frontend (sin cambios de UI)                Backend (FastAPI)                         DB (Postgres)
─────────────────────────────                ──────────────────────                    ─────────────
DashboardPage (menú público)                                                            (sin cambios de
  GET /torneos?estado=Activo      ──────▶   TorneoRepository.list()                     esquema)
                                              NUEVO: LEFT JOIN TorneoGrupo
ControlDeMesaPage (selector)                 WHERE torneo_grupo_id explícito
  GET /torneos?solo_mios=true     ──────▶      → sin filtro extra (P6)
                                              WHERE torneo_grupo_id ausente
EstadisticasDelTorneo (selector              (listado general)
  de ediciones YA ABIERTO)                     → excluye TorneoGrupo.estado
  GET /torneos?torneo_grupo_id=X  ──────▶        = 'Archivado' salvo
                                                  incluir_archivados=true (NUEVO)

ControlDeMesaPage (lista de partidos)
  GET /partidos?solo_mios=true    ──────▶   PartidoRepository.list()
                                              NUEVO: mismo JOIN vía Partido
                                              .torneo_id → Torneo
                                              .torneo_grupo_id → TorneoGrupo,
                                              excluye Partido.estado='Programado'
                                              de un grupo archivado

(sin UI nueva — resguardo de                 HitoPartidoService.registrar()
 backend, invisible en el                     NUEVO: si data.tipo_hito ==
 camino feliz porque la UI ya                 "Inicio_Partido", chequea
 no ofrece el partido)            ──────▶     TorneoGrupo.estado antes de
                                               _validar_titulares() — 409
                                               DomainRuleError si Archivado


PlantillasDelTorneoPage
  gruposPorEquipo (useMemo)
    ANTES: agrupa TODOS los
      vinculos de crud.listQuery
    DESPUÉS: filtra a
      estado === "Activo"        (cero red nueva — mismo GET /plantillas
      ANTES de agrupar             ?torneo_id=X que ya se pedía, el fix
                                    es 100% client-side)
```

### Modelo de datos

**Sin cambios de esquema en todo este plan.** Las 3 áreas se resuelven
con datos que ya existen (`TORNEO_GRUPO.Estado`, `TORNEO.Torneo_Grupo_ID`,
`PARTIDOS.Torneo_ID`, `JUGADOR_EQUIPO.Estado`) — ninguna necesitaba una
tabla, columna ni migración nueva, solo conectar/filtrar con lo que el
sistema ya guarda.

### Cambios por archivo

**Área 1 — Cascada de archivado:**
- `backend/app/repositories/torneo.py` (`TorneoRepository.list`,
  líneas 46-68): reescribir el `SELECT` para hacer siempre
  `join(TorneoGrupo, TorneoGrupo.id == Torneo.torneo_grupo_id)` (en las
  dos ramas — con y sin `torneo_ids_permitidos`, hoy divergen en
  líneas 60-68). Agregar parámetro `incluir_archivados: bool = False` y
  `torneo_grupo_id: int | None` explícito (ya llega hoy dentro de
  `**filtros`, pasa a tratarse aparte): si `torneo_grupo_id` viene
  informado, NO aplicar el filtro de archivado (P6); si no viene, filtrar
  `TorneoGrupo.estado != 'Archivado'` salvo `incluir_archivados=True`.
- `backend/app/services/torneo.py` (`TorneoService.list`): agregar
  `incluir_archivados: bool = False`, pasarlo a `self.repo.list(...)`.
- `backend/app/api/routes/torneos.py` (`listar_torneos`, líneas 14-41):
  agregar query param `incluir_archivados: bool = False`, pasarlo al
  service. Ningún consumidor actual necesita pasarlo `True` (Dashboard.tsx
  y `ControlDeMesa.tsx` quedan con el default correcto sin tocarlos).
- `backend/app/repositories/partido.py` (`PartidoRepository.list`,
  líneas 13-35): mismo `join` — `Partido → Torneo → TorneoGrupo` (2
  hops) — filtrando `NOT (TorneoGrupo.estado = 'Archivado' AND
  Partido.estado = 'Programado')` salvo `incluir_archivados=True`. Sin
  excepción por `torneo_id` explícito (a diferencia de P6/torneos): un
  `torneo_id` puntual en `/partidos` no es "ya sé que es un grupo
  archivado y quiero verlo igual", es solo el selector normal de Control
  de Mesa — debe seguir ocultando los partidos pendientes igual.
- `backend/app/services/partido.py` (`PartidoService.list`): mismo
  parámetro `incluir_archivados: bool = False`, threading a través.
- `backend/app/api/routes/partidos.py` (`listar_partidos`, líneas
  54-85): mismo query param nuevo.
- `backend/app/services/hito_partido.py`:
  - Agregar `self.torneo_grupo_repo = TorneoGrupoRepository(session)` al
    `__init__` (línea 30-42).
  - Nuevo método privado `_validar_torneo_no_archivado(torneo: Torneo) ->
    None`, llamado desde `registrar()` (línea 184-185, junto a
    `_validar_titulares`) solo para `tipo_hito == "Inicio_Partido"`:
    resuelve el grupo (`torneo_grupo_repo.get_or_404(torneo.torneo_grupo_id)`)
    y levanta `DomainRuleError` si `estado == "Archivado"`. Se llama
    ANTES de `_validar_titulares` (fail-fast más barato: no tiene sentido
    calcular titulares de un torneo que ni siquiera puede operarse). Para
    no resolver `torneo` dos veces, `_validar_titulares` puede recibirlo
    ya resuelto como parámetro en vez de volver a pedirlo — pequeño
    refactor interno, sin cambiar su contrato externo.

**Área 3 — Fix del bug de traspasos:**
- `frontend/src/pages/torneo-admin/torneo-dashboard/PlantillasDelTorneo.tsx`:
  - `gruposPorEquipo` (líneas 134-150): antes de construir
    `vinculosPorInscripcion`, filtrar `crud.listQuery.data` a
    `estado === "Activo"` (una línea, mismo patrón textual que
    `ModalGestionarPlantilla.tsx:98`). El campo `activos` (línea 147) se
    simplifica a `vinculos.length` porque `vinculos` ya viene
    pre-filtrado — elimina el `.filter()` duplicado que hoy repite el
    mismo chequeo dos veces en el mismo archivo.

### Edge cases

| # | Caso | Resolución |
|---|---|---|
| EC-A1 | Grupo con 3 ediciones, se archiva estando la Edición 2 `estado='Activo'` (edición) | Las 3 desaparecen del menú público/Control de Mesa por igual — el filtro es por `TORNEO_GRUPO.estado`, no por `TORNEO.estado`; son campos independientes (P5), ninguna edición se salva por su propio estado. |
| EC-A2 | AdminGeneral navega a `/control-de-mesa` sin `solo_mios` (ve todo el sistema) | El filtro de archivado aplica igual — es independiente del scoping RBAC, se aplica siempre salvo `incluir_archivados=true` explícito (que hoy ningún caller pasa). |
| EC-A3 | Reactivar un grupo con un partido que quedó `Cancelado` mientras estaba archivado (si algo lo cancela por otra vía) | Sin caso especial — `Cancelado` no es `Programado`, nunca estuvo oculto por este filtro en primer lugar (solo se ocultan los `Programado`). |
| EC-A4 | Torneo con un partido `En curso` en el momento exacto de archivar | Ese partido NO se oculta (el filtro solo excluye `estado='Programado'`) — sigue operable en Control de Mesa hasta finalizarlo, decisión explícita de alcance (ver "Fuera de este plan"), evita dejarlo huérfano sin ninguna pantalla desde donde cerrarlo. |
| EC-A5 | `EstadisticasDelTorneo.tsx` pide `GET /torneos?torneo_grupo_id=X` para un grupo archivado | Devuelve las ediciones igual (P6) — el selector de Estadísticas de un torneo ya abierto sigue funcionando sin que el admin tenga que reactivar el grupo solo para consultar sus propias estadísticas. |
| EC-A6 | Carrera: dos pestañas, una archiva el grupo mientras la otra tiene `/control-de-mesa` abierto con la lista ya cargada | La lista vieja en memoria no desaparece sola (sin websockets en este proyecto) — el próximo refetch (`invalidateQueries` ya disparado por `cambiarEstadoGrupo` en `TorneosAdmin.tsx:276`, pero eso es OTRA pestaña/query key) la actualiza. Si el admin de la otra pestaña alcanza a hacer click en "Empezar Partido" antes del refetch, el 409 de `HitoPartidoService` (nuevo) lo bloquea igual — mismo criterio que la carrera EC-CM3 ya documentada en `fixes-datos-traspasos-control-mesa-plan.md`. |
| EC-T1 | Jugador con una sola fila `Activo` en un equipo, sin historial previo | Sin cambio de comportamiento — el filtro nuevo no afecta a quien ya tenía exactamente el caso simple. |
| EC-T2 | Jugador traspasado y el traspaso NO se anula nunca (caso normal, sin bug) | Sin cambio — la fila queda `Traspasado` en el equipo de origen (correcto, ya se ocultaba... **no**, este es el mismo bug: hoy también se muestra de más en el origen tras un traspaso normal, no solo tras anular uno. El fix de `PlantillasDelTorneo.tsx` lo corrige por igual — no es exclusivo del camino de "anular", es cualquier fila no-Activo. |
| EC-T3 | `ModalPerfilJugador` (se abre haciendo click en una tarjeta de `PlantillasDelTorneo.tsx`) | Sin cambios — sigue recibiendo `jugador.id`, no depende de `grupo.vinculos`; simplemente ya no hay tarjeta-fantasma desde la cual abrirlo por error. |
| EC-T4 | `crud.truncado` (banner de "Mostrando los primeros `LIMITE_LISTA` vínculos...", línea 304-306) | Sigue siendo sobre el total SIN filtrar que trae el backend (`crud.listQuery.data.length >= LIMITE_LISTA`, lógica de `useResourceCrud`, no tocada) — correcto: la ventana de 200 sigue siendo sobre filas totales del backend, no sobre las ya filtradas a Activo, así que el aviso de truncamiento no queda subestimado. |

### Diagrama de pruebas

| Flujo/rama nueva | Tipo de test | Prioridad |
|---|---|---|
| `TorneoRepository.list` — grupo archivado excluido del listado general (`torneo_grupo_id=None`) | DB/Integración (backend) | Alta |
| `TorneoRepository.list` — grupo archivado SÍ aparece cuando se pide `torneo_grupo_id` explícito (EC-A5) | DB/Integración (backend) | Alta — es la regresión más fácil de introducir sin querer |
| `TorneoRepository.list` — `incluir_archivados=true` trae todo (paridad con `/torneo-grupos`) | Integración | Media |
| `PartidoRepository.list` — partido `Programado` de un grupo archivado excluido | DB/Integración (backend) | Alta |
| `PartidoRepository.list` — partido `En curso`/`Finalizado` de un grupo archivado NO se excluye (EC-A4) | DB/Integración (backend) | Alta |
| `PartidoRepository.list` — sin cambio de comportamiento para grupos Activos (regresión) | Integración | Alta |
| `HitoPartidoService.registrar` — 409 al intentar `Inicio_Partido` de un torneo archivado, mensaje correcto | Integración (backend, pytest) | Alta |
| `HitoPartidoService.registrar` — sin cambio para torneos no archivados (regresión sobre `_validar_titulares` ya existente) | Integración | Alta |
| Reactivar un grupo — sus ediciones/partidos vuelven a aparecer sin ningún dato adicional que migrar | Integración end-to-end (backend) | Media |
| `PlantillasDelTorneoPage` — tarjeta de un equipo NO muestra una fila `Inactivo` tras anular un traspaso hacia ese equipo (reproduce el Caso 1 del reporte) | Integración (frontend, testing-library) | Alta — es la prueba de regresión exacta del bug reportado |
| `PlantillasDelTorneoPage` — jugador con fila `Traspasado` (origen) + fila `Activo` (destino tras un traspaso normal, sin anular) aparece UNA sola vez, en el equipo correcto | Integración (frontend) | Alta — reproduce el Caso 2 (duplicado) |
| `PlantillasDelTorneoPage` — equipo con 0 filas Activo (todo historial) muestra "Sin jugadores todavía", no una lista de fantasmas | Integración (frontend) | Media |
| `PlantillasDelTorneoPage` — contador "(N jugadores)" de la cabecera de cada tarjeta coincide con la cantidad de tarjetas renderizadas (antes podían divergir sutilmente) | Unit/integración (frontend) | Baja |

---

## Decision Audit Trail

| # | Fase | Decisión | Clasificación | Principio | Racional |
|---|---|---|---|---|---|
| 1 | CEO | Área 2 (Convocados/Titulares/Suplentes + Alineaciones) se documenta como ya implementada, cero código | Mecánica | Claimed Limitations Need Evidence | Verificado línea por línea contra `Convocatoria.tsx`, `ControlDeMesa.tsx`, `PartidoEnVivo.tsx`, `hito_partido.py` — todo el pedido ya existe en producción |
| 2 | CEO | La cascada de archivado excluye por default, con excepción cuando `torneo_grupo_id` viene explícito (P6) | Mecánica | Explícito + reuso de patrón ya establecido | Mismo criterio ya usado por `/torneo-grupos/{id}` — sin la excepción, la pestaña Estadísticas de un torneo ya abierto se rompería |
| 3 | CEO | El filtro de `/partidos` NO tiene la misma excepción por `torneo_id` explícito (a diferencia de `/torneos` por `torneo_grupo_id`) | Taste | P5 (explícito, caso por caso) | Un `torneo_id` puntual en Control de Mesa es navegación normal del selector, no "ya sé que está archivado y quiero verlo igual" — son casos de uso distintos aunque el mecanismo se parezca |
| 4 | CEO | Solo se ocultan partidos `Programado`; `En curso`/`Finalizado` de un torneo archivado quedan visibles | Taste (borderline scope) | P2 (boil lakes, límite explícito) + evitar dejar partidos huérfanos | El pedido dice literalmente "pendientes"; ocultar un partido en curso lo dejaría sin ninguna pantalla desde donde terminarlo |
| 5 | CEO | El bug de traspasos se resuelve en el frontend (`PlantillasDelTorneo.tsx`), nunca cambiando `TraspasoService.anular()` ni el modelo de `JUGADOR_EQUIPO` | Mecánica | Evidencia de código + invariante ya documentado (EC-20) | `anular()` es correcto por diseño (nunca borra trayectoria); el defecto es 100% de un consumidor que no filtra, confirmado comparando contra 2 pantallas hermanas que sí lo hacen bien |
| 6 | CEO | El filtro del bug de traspasos es client-side (mismo patrón que `ModalGestionarPlantilla.tsx`), no un query param nuevo en `GET /plantillas` | Taste | P3 (pragmatismo) + P4 (DRY, reusar patrón exacto ya probado) | Cambiar el contrato del endpoint arriesga a los 2 consumidores que SÍ necesitan ver todo el historial (Traspasos, Perfil de Jugador); el fix client-side no toca esa superficie en absoluto |
| 7 | Eng | Defensa en profundidad: `HitoPartidoService.registrar()` rechaza `Inicio_Partido` de un torneo archivado con 409 | Mecánica | P1 (completeness) | La UI ya lo oculta, pero el backend es la fuente de verdad establecida en todo el proyecto (mismo criterio que la validación de titulares, B.2) |
| 8 | Eng | Sin cambios de esquema en ninguna de las 3 áreas | Mecánica | P4 (DRY) + P5 (explícito) | Los 3 problemas se resuelven con columnas/relaciones que ya existen — señal de que ninguno necesitaba una tabla nueva |

---

## GSTACK REVIEW REPORT

- **Modo**: SELECTIVE EXPANSION (Área 1, cascada de archivado — extiende
  3B-7 a pedido explícito del usuario) + BUG FIX ACOTADO (Área 3) +
  VERIFICACIÓN SIN CAMBIOS (Área 2). Sin cambios de esquema en todo el
  plan.
- **Fases corridas**: CEO ✅ (13 premisas verificadas contra código real,
  8 decisiones registradas), Design ✅ (scope UI detectado: cambios de
  qué filas trae una lista existente, no pantallas nuevas), Eng ✅, DX —
  omitida (sin superficie de API/CLI para terceros, módulo interno).
- **Voces**: `[subagent-only]` — Codex no disponible en esta máquina
  (`codex` no encontrado en PATH, verificado con `command -v codex`).
  Mitigación: cada hallazgo de este documento cita archivo:línea, ninguno
  se aceptó por inferencia — incluyendo el hallazgo central del Área 2
  (que el pedido ya estaba resuelto), que se verificó leyendo 5 archivos
  completos antes de concluir "no hay tarea acá".
- **Gates**: 0 decisiones de arquitectura pendientes de confirmar con el
  usuario — ninguna decisión de este plan introduce una tabla nueva ni
  reabre un modelo de datos. El gate final de aprobación de `/autoplan`
  no aplica: documento pedido explícitamente, no implementación.
- **Decisiones registradas**: 8 (ver Decision Audit Trail). 0 taste
  decisions sin resolver, 0 user challenges — ninguna decisión de este
  plan contradice la dirección que pidió el usuario; el único ajuste real
  es que 1 de las 3 áreas pedidas no necesita código, lo cual se
  documenta con evidencia en vez de fingir una tarea que no existe.
- **Hallazgo más importante para priorizar la implementación:** el bug
  de traspasos (Área 3) y la cascada de archivado (Área 1) son
  independientes entre sí y de tamaño muy distinto — el fix de traspasos
  es 1 archivo, ~5 líneas; la cascada toca 6 archivos backend pero sin
  ningún cambio de esquema ni lógica de negocio compleja (son filtros de
  `JOIN`). Ninguno depende del otro, pueden implementarse y testearse en
  cualquier orden o en paralelo.
- **No implementado**: cero código ni cambios de esquema — solo este
  documento, como se pidió.
- **Siguiente paso sugerido**: implementar primero el fix de traspasos
  (Área 3) — es el de menor esfuerzo y el usuario lo reportó como el más
  visible/urgente ("datos fantasma" activamente confundiendo a los
  admins de club hoy). Después la cascada de archivado (Área 1). El Área
  2 no requiere ningún paso — si el usuario quiere confirmarlo
  personalmente, la Sección 1.2 de este documento es la guía exacta de
  dónde mirar en la UI (Convocatoria dentro de Control de Mesa, y la
  sección "Alineaciones" de `/partido/:id/en-vivo`).

**STATUS: DONE**
