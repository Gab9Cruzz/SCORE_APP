# Plan: Cierre de la deuda pendiente en TODOS.md

Generado con `/autoplan` (revisión CEO → Design → Eng). Codex no está
disponible en esta máquina (`codex` no está en PATH) — corrió en modo
`[subagent-only]`, consistente con el precedente ya sentado en
`docs/plans/equipos-jugadores-plan.md` y
`docs/plans/gestion-avanzada-equipos-control-mesa-plan.md` para este mismo
repo.

**Solo documento — sin implementación.** El usuario pidió explícitamente el
plan, no código. Este documento reemplaza, para cada ítem de `TODOS.md`
que sigue realmente pendiente, la ambigüedad de "algún día" por una
decisión (tomada o a tomar) y una tarea concreta.

---

## Hallazgo central (léase antes que nada)

**La premisa que motivó este plan — "hay cosas sin hacer en `TODOS.md`" —
es cierta, pero la lista de `TODOS.md` está desactualizada en los dos
sentidos posibles: sobreestima Y subestima lo pendiente.** (Nota: la
primera versión de este documento afirmaba que el trabajo de "Roles y 3
módulos" también estaba sin commitear — **eso era incorrecto**, corregido
tras verificar `git show HEAD:...` directamente; ver el detalle exacto
abajo. Queda documentado en el Decision Audit Trail para que no se repita
el error si alguien retoma este análisis.)

1. **Sobreestima**: `TODOS.md` describe como "no empezado, bloquea las
   fases 2-4" un trabajo que en realidad **ya está implementado Y ya está
   committeado** en esta misma rama:
   - **"Roles y 3 módulos"** (`TODOS.md` líneas 19-24, remite a
     `docs/plans/roles-3-modulos-plan.md`): las 4 fases están `[x]`
     completas — verificado con `git show HEAD:database/02_constraints.sql`
     (roles reales `AdminGeneral`/`TorneoAdmin`/`Arbitro`/`Publico` ya en
     el `CHECK`), `git show HEAD:backend/app/models/partido.py`
     (`arbitro_id` ya presente) y `git show HEAD:frontend/src/App.tsx`
     (rutas `/arbitro` y `/admin/usuarios` ya presentes). Este trabajo se
     committeó en un commit anterior de esta rama (`22dfd67` y
     subsiguientes) — `TODOS.md` simplemente nunca se actualizó después.
     **No hace falta commitear nada para este ítem, solo corregir el
     texto de `TODOS.md`.**
   - **"Filtro `?torneo_id=` real en `/plantillas`, `/traspasos`,
     `/partidos`"** (`TODOS.md` líneas 67-70): también ya committeado —
     `plantillas.py` y `traspasos.py` ni siquiera aparecen en
     `git status` (cero cambios locales), y el `torneo_id` que filtra de
     verdad ya está en `git show HEAD:backend/app/api/routes/partidos.py`.
     **Mismo caso: solo corregir el texto de `TODOS.md`.**
   - Lo que **sí sigue sin commitear** es un tercer plan, más reciente y
     **tampoco referenciado en `TODOS.md`**:
     `docs/plans/gestion-avanzada-equipos-control-mesa-plan.md` (Plantilla
     Base de equipo, cronómetro Períodos/Corrido, hitos de partido,
     corrección de minuto), generado el 2026-08-31. Es el único que
     aparece en `git status --porcelain` (55 entradas, todas atribuibles a
     este plan — confirmado archivo por archivo, no hay mezcla con otro
     plan) y está 100% implementado: los 12 ítems de su checklist están
     construidos (migraciones `19_`/`20_`, rutas, servicios,
     `DetalleEquipo.tsx`, `Cronometro.tsx`, tests dedicados).
   - **Verificado ahora mismo**: `.\verificar.ps1` completo sobre el
     working tree tal cual está — 237 tests backend + 148 tests frontend +
     lint + typecheck + build — **TODO VERDE**. El trabajo de gestión
     avanzada no es un borrador a medio hacer: es código terminado
     esperando un solo `git commit`.
   - **Nota de higiene de rama** (no es una tarea de este plan, pero
     conviene decirlo): esta rama (`feat/equipos-jugadores-plan`) ya
     acumula 5 planes de features distintos sin mergear a `main`
     (`git diff --stat main...HEAD`: 175 archivos, +17.8k/-1.3k líneas).
     El nombre de la rama quedó desactualizado hace varios planes. Este
     documento no decide cuándo/cómo esa rama llega a `main` — es una
     pregunta de release, no de backlog — pero se señala para que no
     sorprenda a quien la vea crecer más.
2. **Subestima**: ninguna sección de `TODOS.md` menciona el único gap
   real que el propio Eng Review de `roles-3-modulos-plan.md` dejó
   documentado — `MesaPanel` no valida `partido.estado` antes de aceptar
   un evento (decisión D6, aceptada como riesgo, con la recomendación
   explícita de "candidato para TODOS.md si se vuelve un problema real").
   Nunca llegó a esa lista.

**Consecuencia para este plan:** la Fase 0 no es una tarea de ingeniería,
es **commitear el único trabajo terminado que sigue sin commitear
(gestión avanzada) y corregir `TODOS.md` para que deje de mentir** — antes
de eso, cualquier plan sobre "lo que falta" parte de datos falsos. Las
fases siguientes cubren lo que, verificado contra el código real (no
contra lo que dice el documento), **sigue genuinamente sin hacerse**.

---

## Fase 0 — Housekeeping (prerrequisito, no planificación)

No es parte del ciclo CEO/Design/Eng — es la corrección de estado que hace
que el resto del plan sea correcto.

- [ ] Revisar y commitear el working tree actual en **un solo commit**
      (los 55 archivos de `git status --porcelain` pertenecen enteros a
      un solo plan, no hay mezcla que separar):
      `feat: gestion avanzada de equipos + control de mesa (docs/plans/gestion-avanzada-equipos-control-mesa-plan.md)`
      (`.\verificar.ps1` ya corrió en verde sobre este mismo working tree
      — no hace falta re-verificar antes de commitear).
      "Roles y 3 módulos" **no necesita commit** — ya está committeado
      desde antes; ver "Hallazgo central" arriba.
- [ ] Aplicar la actualización de `TODOS.md` de este plan (sección final)
      — ya redactada más abajo, lista para pegar.
- [ ] Agregar el gap de `MesaPanel`/`partido.estado` (encontrado en el
      Eng Review de `roles-3-modulos-plan.md`, decisión D6) como ítem
      nuevo de `TODOS.md` — es información real que existía pero nunca
      llegó a la lista.

**Este plan (Fases 1-3 más abajo) asume que la Fase 0 ya corrió.** Si no
corre, cualquier trabajo nuevo sobre roles/plantilla base/cronómetro
arriesga chocar contra 175 archivos sin commitear.

---

## Fase 1 — CEO Review (Estrategia y Alcance)

### Premisas

| # | Premisa | Veredicto |
|---|---------|-----------|
| P1 | `TODOS.md` es la fuente de verdad de lo pendiente. | **Refutada parcialmente** — ver "Hallazgo central". Es la fuente de intención, no de estado; el estado real hay que verificarlo contra el código en cada ítem, no asumirlo. |
| P2 | El usuario quiere que **todo** lo que hoy aparece como pendiente en `TODOS.md`, sin excepción, se implemente a través de este plan. | **Cuestionada — ver D-SCOPE (User Challenge) más abajo.** Varios ítems son módulos nuevos de alcance grande, nunca pedidos explícitamente, rechazados repetidas veces en planes anteriores (motor de resultados para combate/marca/tiempo, brackets de eSports, notificaciones por correo, importación CSV, CI). Tratarlos igual que un fix de 2 líneas ("cerrar todo") vs. mantenerlos como límites de alcance explícitos y documentados ("cerrar lo accionable, decidir lo que necesita decisión, dejar aparcado lo que es scope nuevo real") es la decisión de mayor impacto de este plan — vuelve al usuario en la Fase 4. |
| P3 | Ningún ítem de `TODOS.md` tiene ya una implementación resuelta que el propio `TODOS.md` no refleja. | **Refutada** — ver Hallazgo central: 2 secciones completas ya resueltas (y ya committeadas), 1 plan completo committeable sin referencia en `TODOS.md`. |
| P4 | El patrón DRY para bloqueos de concurrencia (`pg_advisory_xact_lock`) ya existe en el repo y se puede reutilizar tal cual para el EC-6 de cupo de modalidad. | Confirmado — `backend/app/repositories/jugador_equipo.py` (`lock_exclusividad_torneo`) y `backend/app/repositories/torneo_grupo.py` (lock de forma de un solo argumento) son los dos templates disponibles. |
| P5 | No hay superficie de API/CLI para terceros — es un módulo interno de un sistema de torneos ya autenticado. | Confirmado — igual que los 2 planes anteriores, Fase DX se omite. |

### D-SCOPE — Decisión de alcance central (User Challenge)

**Lo que el usuario pidió:** "Todo lo que ha quedado sin hacerse en
TODOS.md necesito irlo terminando... que no aparezca nada que no se ha
hecho."

**Lo que este plan (Claude + revisión adversarial, ver Fase 1.5)
recomienda en cambio:** no tratar como "trabajo pendiente a cerrar" a los
ítems que son, en los hechos, **módulos de producto completos nunca
pedidos y rechazados explícitamente varias veces** — motor de resultados
para disciplinas de marca/tiempo/combate/mente, brackets + APIs de
eSports, notificación por correo, importación masiva CSV/Excel, CI en
GitHub Actions, categorías de peso/cinturón reales de federación, CRUD de
catálogo maestro fuera de migración SQL. Meterlos en "cosas a terminar"
los transforma silenciosamente de decisiones de producto explícitas en
deuda técnica implícita — exactamente lo opuesto de lo que un `TODOS.md`
limpio debería transmitir.

**Por qué importa la diferencia:** un ítem "pendiente" invita a
implementarlo la próxima vez que alguien (humano o agente) lea el archivo.
Un módulo nuevo de varios días de trabajo, nunca solicitado, con su propio
diseño de producto por resolver (¿qué tabla de categorías de peso? ¿qué
proveedor de correo? ¿qué formato de CSV?) no debería competir por
atención con un `SELECT ... FOR UPDATE` de 10 líneas — y no debería
desaparecer de la vista tampoco.

**Alternativas:**

| Alternativa | Completeness | Veredicto |
|---|---|---|
| **A. Boil the ocean literal** — meter los ~10 módulos grandes (S-EE en el inventario de la Fase 3) como fases de implementación de este mismo plan. | 10/10 en papel | Rechazada como default — son semanas de trabajo con decisiones de producto propias no tomadas (proveedor de correo, formato de import, categorías de una federación real), y ninguno fue pedido en ningún momento por el usuario; forzarlos acá sería la clase de "nueva implementación" que el usuario pidió explícitamente evitar en este mensaje. |
| **B. Dejarlos exactamente como están** — no tocar `TODOS.md` en esas líneas. | 3/10 | Rechazada — no cumple "que no aparezca nada que no se ha hecho"; el usuario fue explícito en que el propósito de este plan es que `TODOS.md` deje de listar cosas sueltas. |
| **C. Cerrar lo accionable + decidir lo que necesita decisión + re-clasificar lo grande como "Alcance futuro — explícitamente aparcado, no deuda"** (elegida) | 9/10 | `TODOS.md` deja de tener una sección "por hacer" ambigua: cada ítem queda en uno de 3 estados inequívocos — **hecho** (retirado de la lista), **en este plan** (con tarea y fase concretas), o **aparcado a propósito** (su propia sección, con la razón de por qué no está en este plan, no mezclado con lo demás). Nada "desaparece" ni queda pendiente sin dueño. |

**Decisión: C — confirmada con el usuario (2026-09-01), eligió la opción
recomendada** en el Gate de Aprobación (Fase 4) de este mismo plan.
`TODOS.md` ya se actualizó con los 3 estados (hecho / en curso / aparcado)
sobre esta base.

### Qué ya existe (leverage map)

| Sub-problema | Ya cubierto por | Qué falta |
|---|---|---|
| Bloqueo de concurrencia por fila | `lock_exclusividad_torneo` (`jugador_equipo.py`), lock de `torneo_grupo.py` | Extender el mismo patrón a cupo de modalidad (EC-6) |
| Filtro server-side por torneo | `plantillas.py`, `traspasos.py`, `partidos.py` (ya filtran) | Nada — ya está |
| Banner de "primeros 200" | `useResourceCrud.truncado` + `LIMITE_LISTA` | Conectarlo en `SimpleResourceAdminPage.tsx` (arregla Jugadores + Usuarios de una vez) y en las 5 grillas del dashboard de torneo |
| Alias de tipos generados (`components["schemas"]`) | `frontend/src/api/schema.d.ts` (ya generado) | Un módulo central de alias + reemplazar 12 declaraciones ad-hoc (`EquipoRow` x8, `ModalidadRow` x4) |
| Auditoría — backend de filtros | `GET /auditoria` ya acepta `tabla` y `registro_id` | Exponerlos en `AuditoriaAdmin.tsx` (falta el input de `registro_id` y el autocomplete de `tabla`) + botón de export CSV (no existe en ningún lado) |
| Roles y permisos | `roles-3-modulos-plan.md` completo (ver Fase 0) | Nada nuevo — ya está, solo falta commitear |
| Plantilla previa a torneo / cronómetro | `gestion-avanzada-equipos-control-mesa-plan.md` completo (ver Fase 0) | Nada nuevo — ya está, solo falta commitear |

### Dream state

```
ACTUAL                           ESTE PLAN                        IDEAL (post-cierre)
──────────────────────           ──────────────────────           ──────────────────────
TODOS.md dice "pendiente"        Fase 0: se commitea lo que        TODOS.md tiene 3
en 2 secciones que ya             ya estaba hecho, TODOS.md         estados posibles por
están 100% implementadas          se actualiza a la realidad         ítem: hecho (retirado),
(roles, gestión avanzada) —       del código.                        en curso (con dueño y
175 archivos de trabajo                                              plan), o aparcado a
terminado esperando en el        Fase 1-3: cada ítem                propósito (con razón
working tree.                     genuinamente pendiente             explícita) — nunca
                                   queda con decisión tomada           "flotando" sin dueño.
Un cupo de modalidad puede         (o recomendación + pregunta
superarse con dos requests         al usuario) + tarea concreta.    Cualquier persona (o
simultáneos (EC-6).                                                  agente) que abra
                                  EC-6 cerrado con el mismo           TODOS.md sabe, en 30
12 archivos de frontend            patrón de lock ya usado.           segundos, exactamente
redeclaran a mano el tipo                                            qué hacer después —
de fila que `schema.d.ts` ya     Tipos centralizados,                sin tener que auditar
tiene generado.                   truncado en todas las              el código para saber
                                   grillas, auditoría con              si algo ya se hizo.
                                   los filtros que el
                                   backend ya soporta.
```

---

## Fase 1.5 — Revisión adversarial (voz secundaria)

Codex no disponible (`command -v codex` falla). Segunda voz: subagente
Claude, en foreground, con el borrador de este plan (secciones anteriores
+ inventario completo de la Fase 3) como insumo. Ver resumen de hallazgos
al final del documento, sección "Revisión cruzada" — se incorporaron antes
de cerrar este documento, no como anexo separado.

---

## Fase 2 — Design Review (UX)

Aplica — hay superficie de UI real en los ítems accionables (auditoría,
grillas, filtros persistentes) aunque de bajo riesgo de interacción (no
hay flujos nuevos complejos, a diferencia de los 2 planes anteriores).

### Ítems con UI nueva o modificada

| Ítem | Cambio de UI | Estados a cubrir |
|---|---|---|
| Auditoría — filtro `registro_id` | Input numérico nuevo junto a los filtros existentes de `AuditoriaAdmin.tsx` | Vacío = sin filtrar (comportamiento actual); valor no numérico deshabilita el submit, no un error post-fetch |
| Auditoría — autocomplete de tabla | Reemplaza el input de texto libre por un `<select>`/combobox con las ~18 tablas reales (`__tablename__`, no el nombre en pantalla) | Ninguna tabla seleccionada = sin filtrar; lista estática, no requiere endpoint nuevo |
| Auditoría — export CSV | Botón "Descargar CSV" junto al filtro, genera el archivo client-side a partir de las filas ya cargadas en pantalla (no un endpoint nuevo — ver Fase 3, Alternativas) | Sin filas cargadas → botón deshabilitado, no un CSV vacío que confunda |
| Banner de truncado en grillas faltantes | Mismo componente ya usado en `EquiposAdmin.tsx`/`AccesosAdmin.tsx`/`AuditoriaAdmin.tsx`, replicado en `SimpleResourceAdminPage.tsx` (Jugadores, Usuarios) y en las 5 páginas de `torneo-dashboard/` | Ninguno nuevo — reusa el mismo texto y umbral ya validados |
| Persistir filtro de disciplina/modalidad en URL | `TorneosAdminPage` escribe `?disciplina_id=`/`?modalidad_id=` al elegir un chip, además de leerlo | Navegar atrás/adelante del browser respeta el filtro; compartir el link reproduce la vista |
| Filtro por Estado del torneo en la barra de disciplinas | Chip adicional junto a los de Disciplina/Modalidad | Mismo patrón visual, sin chip = todos los estados (comportamiento actual) |

### Litmus scorecard

| Dimensión | Score |
|---|---|
| Jerarquía de información (filtros nuevos no compiten visualmente con los existentes — mismo nivel, mismo componente) | 8/10 |
| Estados especificados (tabla arriba) | 8/10 |
| Especificidad (autocomplete usa nombres reales de tabla, no una versión "amigable" que después no matchea la búsqueda) | 9/10 |
| Alineación con patrones existentes (100% reuso: `ResourceTable`, banner de truncado, chips de filtro ya construidos en `TorneosAdminPage`) | 10/10 — este plan no introduce ningún componente nuevo, solo replica los que ya pasaron por diseño en planes anteriores |
| Responsive | No evaluado a fondo — son extensiones de pantallas de escritorio (`/admin/*`, `/torneo-admin/*`) ya usadas solo desde desktop, sin el criterio "2-3 toques desde el celular" que sí aplica a Control de Mesa |

**Decisión de Design (Taste, auto-decidida por P5 — explícito sobre
clever):** el export CSV se genera client-side (Blob + `<a download>`) en
vez de un endpoint `GET /auditoria/export` nuevo — evita construir y
mantener un segundo formato de respuesta para el mismo dato que
`GET /auditoria` ya devuelve paginado en pantalla. Ver Fase 3 para el
único caso borde que esto introduce (CSV incompleto si hay más de
`LIMITE_LISTA` filas).

---

## Fase 3 — Eng Review (Arquitectura, Datos, Edge Cases, Tests)

### Inventario completo — cada ítem de `TODOS.md`, clasificado

**Leyenda de estado:** ✅ Ya hecho (retirar de `TODOS.md`) · 🔧 Accionable
en este plan (Fase A más abajo) · ❓ Necesita decisión de producto (Fase B)
· 🅿️ Aparcado a propósito (Fase C, condicionado a D-SCOPE)

| # | Ítem (sección original de `TODOS.md`) | Estado | Dónde se resuelve |
|---|---|---|---|
| 1 | Roles y 3 módulos — Fase 1-4 completas | ✅ | Fase 0 (commit) |
| 2 | Filtro `torneo_id` real en `/plantillas`, `/traspasos`, `/partidos` | ✅ | Fase 0 (commit) |
| 3 | Necesidad funcional de "jugador del club antes de un torneo" | ✅ (cubierta vía D1-C — `EQUIPO_JUGADOR_BASE`, más liviana que A2) | Fase 0 (commit de `gestion-avanzada...plan.md`) |
| 4 | Corrección de minuto de eventos/hitos | ✅ | Fase 0 (commit) |
| 5 | Filtro por tabla en auditoría sin autocomplete | 🔧 | 3A-1 |
| 6 | Sin filtro `registro_id` en la pantalla de auditoría | 🔧 | 3A-2 |
| 7 | Sin export/descarga de la bitácora de auditoría | 🔧 | 3A-3 |
| 8 | Cupo de modalidad (EC-6) sin lock | 🔧 | 3A-4 |
| 9 | Migración 08 Parte E sin rastro de auditoría | 🔧 (barato, mismo criterio de "reusar patrón existente" que el resto de 3A — no hace falta esperar a que se re-corra para blindarlo) | 3A-11 |
| 10 | Otras grillas no avisan truncado (Jugadores, Usuarios, dashboard torneo) | 🔧 | 3A-5 |
| 11 | Tipos de fila (`EquipoRow` x8, `ModalidadRow` x4) sin centralizar | 🔧 | 3A-6 |
| 12 | Sin CI | 🅿️ | Aparcado — infraestructura nueva, no deuda de producto |
| 13 | Demo `10_*.sql` con patrón viejo (Tenis Individual) | 🔧 (cosmético, barato) | 3A-7 |
| 14 | `MesaPanel` sin guard de `partido.estado` (hallazgo nuevo, ver Hallazgo central) | 🔧 | 3A-8 |
| 15 | Offline-first en Control de Mesa a mitad de partido | ❓ (alcance reducido — ver nota) | 3B-1 |
| 16 | Titular/suplente / convocados a un partido | ❓ | 3B-2 |
| 17 | Desactivación de persona con membresías activas | ❓ | 3B-3 |
| 18 | Límite de tamaño de plantilla para fútbol | ❓ | 3B-4 |
| 19 | Notificación por correo al jugador traspasado | 🅿️ | Aparcado — módulo de notificaciones aparte, requiere proveedor de correo (decisión de infraestructura, no de este plan) |
| 20 | Importación masiva CSV/Excel | 🅿️ | Aparcado — no pedido, formato/validación de archivo es diseño propio |
| 21 | Vista consolidada de estadísticas cruzando ediciones | ❓ | 3B-5 |
| 22 | Clonar plantilla de una edición a la siguiente | ❓ (confirmar que sigue sin pedirse) | 3B-6 |
| 23 | Archivar/eliminar `TORNEO_GRUPO` completo | ❓ | 3B-7 |
| 24 | Traspasos entre ediciones distintas | ❓ | 3B-8 |
| 25 | Paginación real con cursor en `/equipos` y `/jugadores` | ❓ (grande, no trivial) | 3B-9 |
| 26 | Motor de resultados marca/tiempo, combate, mente | 🅿️ | Aparcado — módulo de producto propio, rechazado 2 veces ya |
| 27 | Categorías de peso/cinturón reales de federación | 🅿️ | Aparcado — datos de una federación real, no es decisión técnica |
| 28 | Límite superior de inscripciones por torneo | ❓ | 3B-10 |
| 29 | eSports — brackets + APIs de plataformas | 🅿️ | Aparcado — integración externa, módulo propio |
| 30 | Ajustar catálogo maestro fuera de migración SQL | ❓ | 3B-11 |
| 31 | Equipo como entidad rica con roster **autoritativo** permanente (escudo, sede, staff — la versión completa que #3 explícitamente NO construyó) | 🅿️ | Sigue fuera de alcance — D1-C (ítem #3) cubrió la necesidad funcional con una tabla no-autoritativa; esta es la alternativa "grande" que D1 rechazó a propósito, no una duplicación de #3 |
| 32 | Catálogo de categorías etarias/de género | 🅿️ | Aparcado — mismo motivo que #27, catálogo de una realidad externa |
| 33 | Iconos SVG propios por disciplina | 🅿️ | Aparcado — trabajo de diseño gráfico, no de ingeniería |
| 34 | Filtro por Estado del torneo en barra de disciplinas | 🔧 | 3A-9 (Fase 2 ya lo diseñó) |
| 35 | Persistir filtro en URL (`TorneosAdminPage`) | 🔧 | 3A-10 (Fase 2 ya lo diseñó) |
| 36 | `UNIQUE(Nombre, Disciplina_ID)` en `EQUIPOS` | 🅿️ | Aparcado — rompería datos existentes, nunca pedido |
| 37 | Inscripciones cruzadas preexistentes sin cancelar | 🅿️ | Es limpieza de datos puntual (ya resuelta para el caso conocido), no una tarea de código |
| 38 | Desempate manual en tabla de posiciones (EC-51) | 🔧 (la decisión de producto **ya está confirmada** — `motor-formatos-plantillas-navegacion-plan.md` cita "la decisión confirmada con el usuario" — solo falta la UI) | 3A-12 |
| 39 | Bracket visual con líneas de conexión | 🅿️ | Aparcado — pieza de diseño gráfico/SVG grande, no bloqueaba funcionalidad según su propio plan |
| 40 | Walkover/retiro a mitad de fase de Eliminación | ❓ | 3B-13 |
| 41 | Rate limiting tras N fallos de login | ❓ | 3B-14 |
| 42 | Registro de logout (requiere revocación de tokens) | 🅿️ | Aparcado — rediseño de JWT a lista de revocación, alcance de seguridad propio |

### 3A — Tareas accionables (sin decisión de producto pendiente, van directo a implementación cuando se retome)

Cada una es un fix acotado (<1 día CC), con patrón ya existente en el repo
para copiar — la razón por la que P2 (boil lakes) las aprueba directo sin
pasar por pregunta.

- **3A-1 — Autocomplete de tabla en Auditoría.** `AuditoriaAdmin.tsx`:
  reemplazar el `<input>` de texto libre de `tablaFiltro` por un `<select>`
  con las tablas reales (lista estática de los `__tablename__` — no hay
  endpoint que las liste hoy, así que la lista vive en el frontend, igual
  que el resto de catálogos estáticos de la UI).
- **3A-2 — Filtro `registro_id` en Auditoría.** Un input numérico más,
  conectado al parámetro que `GET /auditoria?registro_id=` ya acepta
  (`backend/app/api/routes/auditoria.py:26`) — sin cambios de backend.
- **3A-3 — Export CSV de Auditoría.** Client-side (Blob + descarga), sobre
  las filas ya cargadas en pantalla (decisión de Fase 2). Edge case: si
  `truncado` es `true` (más de `LIMITE_LISTA` filas), el botón debe
  advertir "Descarga solo las primeras 200 filas — afiná el filtro para
  exportar menos" en vez de generar un CSV silenciosamente incompleto.
- **3A-4 — Lock de cupo de modalidad (EC-6).** Nuevo método en el
  repositorio de inscripciones (nombre sugerido:
  `lock_cupo_inscripcion(inscripcion_torneo_id)`), mismo patrón de un solo
  argumento que `torneo_grupo.py`, llamado al inicio de
  `RegistroLoteService._validar_lote` y otra vez dentro de la transacción
  de `confirmar()` antes de confiar en el conteo — ver hallazgo (b)/(c) de
  la investigación de este plan para el código exacto de referencia
  (`backend/app/services/registro_lote.py:57-62,174-183`,
  `backend/app/repositories/torneo_grupo.py:26-34`).
- **3A-5 — Banner de truncado en grillas faltantes.** Un bloque
  `{crud.truncado && ...}` en `SimpleResourceAdminPage.tsx` (arregla
  Jugadores + Usuarios de una vez, es la misma página genérica) y una
  línea por cada una de las 5 páginas de `torneo-dashboard/` que hoy no
  lo muestran.
- **3A-6 — Centralizar tipos de fila.** Módulo nuevo (ej.
  `frontend/src/api/types.ts`) con `type Equipo =
  components["schemas"]["EquipoOut"]` y equivalente para Modalidad;
  reemplazar las 12 declaraciones ad-hoc (`EquipoRow` en 8 archivos,
  `ModalidadRow` en 4) por el import. Mecánico, sin riesgo funcional —
  `tsc -b` es la única verificación necesaria.
- **3A-7 — Demo `10_*.sql`, Copa Raíces (Tenis Individual).** Migrar el
  seed de ese torneo del patrón viejo (equipo fantasma "Micky Fernández")
  al patrón real de inscripción individual por `Jugador_Perfil_ID`
  (Decisión B1 de `ediciones-catalogo-disciplinas-plan.md`), cubierto por
  `test_scripts_sql.py`.
- **3A-8 — Guard de `partido.estado` en `MesaPanel`.** Defensa en
  profundidad recomendada por la revisión cruzada del plan de roles (D6),
  aceptada como riesgo en su momento — hoy la protección vive solo en el
  filtro de la lista (`ControlDeMesaPage`), no en el panel. Agregar el
  chequeo directo en `MesaPanel`/`EventoPartidoService` para que "Mis
  partidos" (segundo camino de entrada al mismo componente) no lo
  esquive.
- **3A-9 / 3A-10 — Filtro de Estado + persistencia de URL en
  `TorneosAdminPage`.** Ya diseñados en la Fase 2 — implementación directa
  sobre el patrón de chips existente.
- **3A-11 — Guard en la migración 08, Parte E.** Hallazgo de la revisión
  adversarial de este mismo plan (no estaba en el borrador inicial): hoy,
  si `v_ambiguos > 0`, el script solo emite `RAISE WARNING` con un conteo
  y dos sentencias después dropea `Jugador_ID`/`Equipo_ID` — la única
  fuente que permitiría auditar/corregir a mano. Cambiar a volcar los IDs
  ambiguos a una tabla temporal (o `RAISE EXCEPTION` en vez de `WARNING`)
  **antes** del `DROP COLUMN` es un fix de patrón ya usado en el resto de
  migraciones de este repo (abortar en vez de continuar silenciosamente
  ante un dato ambiguo) — no hace falta esperar a que el script se vuelva
  a correr contra una base real para blindarlo, y es más barato hacerlo
  ahora que investigarlo bajo presión si algún día se re-corre.
- **3A-12 — UI de desempate manual en tabla de posiciones (EC-51).** La
  decisión de producto ya está tomada (confirmada en
  `motor-formatos-plantillas-navegacion-plan.md`): enfrentamiento directo
  y resolución manual del admin cuando PTS/DG/GF no alcanzan. Falta la
  pantalla — `vw_tabla_posiciones` ya expone el empate, falta el botón
  "Definir manualmente" + columna de override en el admin de grupos.

### 3B — Decisiones de producto pendientes (cada una con recomendación)

Revisión adversarial (Fase 1.5) marcó que agrupar los 14 ítems al mismo
nivel escondía dos categorías distintas: algunos tienen una recomendación
completa, segura y de bajo riesgo — no hay ambigüedad real de producto,
solo falta que alguien diga "sí, andá" — y otros genuinamente no tienen
una opción "obviamente correcta" sin una llamada humana. Separados:

#### 3B-i — Recomendación por defecto: procede salvo objeción explícita

Estas se implementan con el default recomendado si nadie dice lo
contrario — tratarlas como "bloqueadas" solo demoraría lo fácil al ritmo
de lo difícil.

- **3B-1 — Offline-first en Control de Mesa (alcance reducido).** Con
  `HITOS_PARTIDO` ya implementado (Fase 0), el estado del cronómetro
  sobrevive una desconexión — se recalcula del último Hito guardado en el
  servidor al reconectar. Lo que sigue faltando es acotado: un indicador
  de "sin conexión" en la UI y una cola local de reintento para el evento
  que se estaba cargando justo al cortarse. **Recomendación:** un
  `useOnlineStatus` + cola en `localStorage` (patrón estándar, sin
  infraestructura nueva) — completeness 7/10 (cubre el caso común, no un
  sync completo tipo CRDT). Alternativa 10/10 (cola persistente con
  reconciliación de conflictos) es sobre-ingeniería para un celular de
  árbitro con wifi de cancha.
- **3B-5 — Vista consolidada de estadísticas cruzando ediciones.**
  **Recomendación: no construirla todavía.** Mezclar jugadores que
  cambiaron de equipo entre ediciones (ya señalado en `TODOS.md` como el
  problema real) no tiene una respuesta técnica limpia sin antes decidir
  la regla de negocio ("¿el gol cuenta para el equipo de esa edición o el
  actual?"). Candidato a `/plan-eng-review` dedicado cuando haya un caso
  real que lo pida, no antes — la recomendación en sí ya es la acción
  (no hacer nada), así que no bloquea nada de este plan.
- **3B-6 — Clonar plantilla al crear edición nueva.** **Recomendación: no
  implementar** — sigue sin pedirse, cada edición nace con roster vacío a
  propósito. Mismo caso que 3B-5: la recomendación es la acción.
- **3B-7 — Archivar/eliminar `TORNEO_GRUPO` completo.**
  **Recomendación:** baja lógica (mismo patrón `Estado` que el resto del
  esquema), nunca `DELETE`, y "archivar" oculta el grupo de los selectores
  **sin** tocar sus ediciones existentes (no cascadea) — es el default más
  seguro (una edición archivada por error no arrastra nada).
- **3B-8 — Traspasos entre ediciones distintas.** **Recomendación:**
  tratarlo como alta nueva (no traspaso) en la edición destino, sin cambio
  de esquema — es la lectura más simple del propio dato (`TRASPASOS` ya
  asume origen/destino en el mismo torneo).
- **3B-14 — Rate limiting tras N fallos de login.** **Recomendación:**
  bloqueo temporal (ej. 5 intentos fallidos → 15 min de espera) por
  `usuario` + `IP`, usando `AccesoRepository` que ya registra cada intento
  — es una consulta agregada sobre datos que ya existen, no una tabla
  nueva.

#### 3B-ii — Bloquea: necesita una decisión real antes de poder construirse

Estas no tienen un default seguro que un agente deba elegir solo —
requieren un número, un criterio de negocio, o una sesión de diseño.

- **3B-2 — Titular/suplente / convocados a un partido.** Dirección técnica
  recomendada: **no** requiere tabla nueva de `JUGADOR_EQUIPO` — el
  aprendizaje ya registrado en este repo
  (`jugador-equipo-torneo-scoped`) más el `EQUIPO_JUGADOR_BASE` ya
  construido sugieren agregar `Convocado_A_Partido` como tabla delgada
  (`partido_id`, `jugador_perfil_id`, `titular: bool`) — mismo espíritu
  no-autoritativo que la Plantilla Base, no reemplaza `JUGADOR_EQUIPO`.
  Lo que sigue bloqueando: si esto se construye o se sigue viviendo sin
  el concepto (el propio `frontend/README.md` documenta la limitación
  actual como aceptada, no como bug) — es una pregunta de si el problema
  ya duele en uso real, no de cómo resolverlo si se decide que sí.
- **3B-4 — Límite de tamaño de plantilla para fútbol.** Dirección técnica
  recomendada: nueva columna `Modalidad.Tamano_Plantilla_Max` (nullable —
  solo aplica a disciplinas de equipo grande), reutilizando el mismo
  bloque de EC-6 en `registro_lote.py` que hoy solo corre para
  `tamano_equipo <= 2`. Lo que bloquea: el número real (¿23? ¿25?) — es
  competitivo/reglamentario, no técnico, no hay default razonable para
  inventar.
- **3B-10 — Límite superior de inscripciones por torneo.** Dirección
  técnica recomendada: columna `Torneo.Cupo_Maximo_Inscripciones`
  (nullable = sin límite, comportamiento actual), validado en
  `InscripcionTorneoService.create`, con el mismo patrón de lock que EC-6
  si el límite es bajo. Lo que bloquea: mismo motivo que 3B-4, el número
  depende del torneo.
- **3B-13 — Walkover/retiro a mitad de fase de Eliminación.** Sin
  dirección técnica recomendada todavía — requiere una sesión de diseño
  propia (¿el rival avanza automático? ¿se registra como partido jugado o
  anulado?). No tiene una opción "obviamente correcta".

#### 3B-iii — Ciclo propio, fuera de este plan de cierre

Blast radius o naturaleza de la decisión superan lo que un plan de cierre
de backlog debería absorber — quedan anotadas acá para que no se pierdan,
pero su implementación es un plan aparte, no una tarea de este documento.

- **3B-9 — Paginación real con cursor en `/equipos`/`/jugadores`.**
  Dirección técnica recomendada: keyset pagination
  (`?cursor=<último_id>`) sobre `BaseRepository.list`, reemplazando
  `skip/limit`. Por qué ciclo propio: es un cambio de **contrato de API**
  (rompe cualquier cliente que asuma offset), no un fix acotado — merece
  su propio `/plan-eng-review`, igual que cualquier breaking change.
- **3B-11 — Ajustar catálogo maestro fuera de migración SQL.** Dirección
  técnica recomendada: Alternativa C3 ya identificada en
  `ediciones-catalogo-disciplinas-plan.md` — CRUD completo detrás de un
  rol "Superadmin" nuevo (no `AdminGeneral`). Por qué ciclo propio
  (hallazgo de la revisión adversarial de este plan): un rol nuevo toca
  el `CHECK` de `chk_usuarios_rol` **y** cada `require_roles(...)` del
  código — mismo orden de magnitud que 3B-9, no un fix de un archivo.
  `docs/plans/roles-3-modulos-plan.md` (línea 76 y siguientes) ya señala
  ese patrón (`require_roles("X","Y")` declarativo, literal por endpoint,
  23 call-sites contados en su momento) como algo a revisar con cuidado
  antes de tocarlo de nuevo; agregar un rol más sin pasar por esa
  revisión repetiría el mismo trabajo de auditoría que esa fase ya hizo
  una vez, no lo evitaría.

### Edge cases (los ítems 3A con superficie de datos)

- **EC-A — Lock de cupo (3A-4) bajo `tamano_equipo=1` (individual).** El
  lock nunca debería dispararse para modalidades individuales (no hay
  "cupo de equipo" que proteger) — confirmar que el nuevo método solo se
  llama cuando `modalidad.tamano_equipo > 1`, para no tomar un advisory
  lock innecesario en el camino más frecuente del sistema (inscripción
  individual).
- **EC-B — Export CSV (3A-3) con caracteres especiales.** Nombres con
  comas/comillas (ej. `"Pérez, Juan"`) rompen un CSV naive — usar
  escaping estándar (RFC 4180), no `join(",")` a mano.
- **EC-C — Guard de `MesaPanel` (3A-8) durante un partido `Finalizado`.**
  El guard debe distinguir "no arrancó todavía" (Programado, bloquea) de
  "ya terminó" (Finalizado, sigue permitiendo corrección — ver EC-15 de
  `gestion-avanzada-equipos-control-mesa-plan.md`, que sí permite editar
  eventos de partidos finalizados a propósito). Solo `En curso` es el
  estado que habilita carga nueva sin restricciones.

### Diagrama de pruebas (ítems 3A)

| Ítem | Tipo de test | Prioridad |
|---|---|---|
| Lock de cupo bajo 2 requests concurrentes reales (no solo secuenciales) | Integración, concurrencia explícita (2 tareas async lanzadas juntas) | **Alta** — es exactamente el bug que EC-6 describe, un test que no fuerza concurrencia real no lo detecta |
| Filtro `registro_id` de auditoría, con/sin resultados | Integración (API, sin backend nuevo) | Baja |
| `MesaPanel` rechaza evento en partido `Programado`, acepta en `En curso` | Integración | Normal |
| `truncado` visible en cada una de las 7 pantallas que hoy no lo muestran | Frontend (componente) | Baja |
| Tipos centralizados — `tsc -b` sin errores tras el reemplazo | Typecheck (ya cubierto por `verificar.ps1`) | Baja |

---

## Revisión cruzada (voz secundaria, subagente Claude — Fase 1.5)

Ejecutada de verdad (no simulada): un subagente independiente, sin
contexto previo de este plan, leyó el documento completo + `TODOS.md` y
corrió sus propias verificaciones contra el repo (`git status`, `git diff
HEAD`, `git show HEAD:<archivo>`). Hallazgos, incorporados directamente al
cuerpo del documento:

- **[CRÍTICO, corregido]** El borrador inicial de este plan afirmaba que
  "Roles y 3 módulos" también estaba sin commitear, junto con "gestión
  avanzada", y proponía 2 commits separados. **Era falso** — verificado
  con `git show HEAD:database/02_constraints.sql`,
  `git show HEAD:backend/app/models/partido.py` y
  `git show HEAD:frontend/src/App.tsx`: ese trabajo ya estaba committeado
  desde antes. El número "175 archivos" citado como "working tree sin
  commitear" era en realidad `git diff --stat main...HEAD` (el diff
  acumulado de 5 planes ya committeados contra `main`), no
  `git status --porcelain` (55 entradas reales, las 55 pertenecientes
  únicamente a `gestion-avanzada-equipos-control-mesa-plan.md`). Corregido
  en "Hallazgo central" y en la Fase 0 (un solo commit, no dos) — este es
  el motivo por el que ambas secciones ya no coinciden con la primera
  versión que pudo haberse visto durante la sesión.
- Señaló una nota de higiene de rama que el borrador no mencionaba: la
  rama actual acumula 5 planes de feature sin mergear a `main` (175
  archivos de diff acumulado) — no es una tarea de este plan, pero se
  agregó como nota en "Hallazgo central" para que no sorprenda.
- Cuestionó que 3B-11 (rol Superadmin para el catálogo) estuviera al mismo
  nivel que ítems de una línea como 3B-6, cuando en los hechos tiene el
  mismo orden de magnitud que 3B-9 (toca un `CHECK` + cada
  `require_roles(...)` del código) — se le dio el mismo tratamiento de
  "ciclo propio" que a 3B-9 (ver 3B-iii).
- Señaló que agrupar los 14 ítems de 3B al mismo nivel escondía que
  varios tienen una recomendación completa y de bajo riesgo (sin
  ambigüedad real, solo falta "sí, andá") mientras otros genuinamente
  necesitan una decisión humana — se separó en 3B-i / 3B-ii / 3B-iii.
- Encontró que la migración 08 Parte E (ítem #9) cumplía el criterio de
  "accionable, <1 día, reusa un patrón ya existente" que este plan aplica
  en todo 3A, pero estaba aparcada como "sin acción" — se movió a 3A-11.
- Encontró que el desempate manual (ítem #38/EC-51) tenía la decisión de
  producto **ya confirmada** en otro plan (`motor-formatos-plantillas-
  navegacion-plan.md`) y solo le faltaba la UI — estaba mal clasificado
  como 3B (necesita decisión) cuando en realidad es 3A (accionable). Se
  reclasificó como 3A-12.
- Señaló que los ítems #3 y #31 reusaban la misma etiqueta "Alternativa
  A2" con veredictos opuestos (✅ vs. 🅿️), confuso para quien lea solo la
  tabla sin el texto — se renombraron para que cada uno describa lo que
  es, no el nombre de la alternativa original.
- Confirmó como correcto, sin cambios: el gap de `MesaPanel`/
  `partido.estado` (3A-8, verificado leyendo `evento_partido.py` y
  `ControlDeMesa.tsx`), el cierre de EC-6 vía `pg_advisory_xact_lock`
  (3A-4), los edge cases de CSV (EC-B), y el razonamiento central de
  D-SCOPE (no fue leído como una excusa para evitar trabajo pedido, sino
  como la alternativa correcta frente a inventar defaults para decisiones
  que no son técnicas — proveedor de correo, formato de CSV, categorías
  de una federación real).

---

## Decision Audit Trail

| # | Fase | Decisión | Clasificación | Principio | Racional |
|---|---|---|---|---|---|
| 1 | CEO | `TODOS.md` está desactualizado (sobreestima Y subestima) — Fase 0 de commit + corrección es prerrequisito | Mecánica (verificado con `.\verificar.ps1` en verde) | P1 (completeness) | No se puede planificar "lo pendiente" sobre datos que ya no son ciertos |
| 2 | CEO | D-SCOPE: separar "accionable" / "decisión de producto" / "aparcado a propósito" en vez de forzar todo a implementación | **User Challenge — confirmado con el usuario 2026-09-01**, eligió la opción recomendada (C) | P2 (boil lakes) vs. el pedido explícito del usuario de "cerrar todo" | Ítems de alcance de producto grande (motor de resultados, eSports, notificaciones, CSV, CI) no tienen decisiones tomadas y forzarlos infla este plan a semanas de trabajo no pedido — se prefiere dejarlos visibles y clasificados, no implementados a ciegas |
| 3 | Eng | EC-6 (cupo de modalidad) se cierra con `pg_advisory_xact_lock`, mismo patrón que `lock_exclusividad_torneo` | Mecánica | P4 (DRY) | El patrón ya existe en el repo, dos veces — no hay alternativa razonable |
| 4 | Eng | Export CSV de auditoría es client-side, no un endpoint nuevo | Taste (no elevada — bajo impacto) | P5 (explícito) | Evita mantener un segundo formato de respuesta para el mismo dato |
| 5 | Eng | 3B-9 (cursor real) queda fuera de este plan de cierre, con su propio ciclo de review futuro | Taste | P3 (scope — cambio de contrato de API, no un fix acotado) | Un cambio de contrato de API no es un "cierre de deuda", es una decisión de breaking-change que merece su propia revisión |
| 6 | Design | Todos los cambios de UI de este plan reusan componentes existentes, cero componentes nuevos | Mecánica | P4 (DRY) | Los 3 planes anteriores ya diseñaron y validaron `ResourceTable`, el banner de truncado, y los chips de filtro — repetirlos es lo correcto, no pereza |
| 7 | CEO | Corrección del borrador: "Roles y 3 módulos" NO estaba sin commitear (era la afirmación original de este plan, refutada por revisión adversarial vía `git show HEAD:...`) — Fase 0 pasa a un solo commit | Mecánica (error propio, corregido con evidencia) | P1 (completeness — mejor corregir antes del gate que dejarlo pasar) | Un plan que le pide al usuario "commitear roles" cuando no hay nada que commitear ahí generaría confusión real al ejecutarlo; se prefirió corregir antes de presentar el documento, documentando el error en vez de silenciarlo |
| 8 | Eng | Migración 08 Parte E (ítem #9) se mueve de "aparcada" a 3A-11 | Mecánica (hallazgo de revisión adversarial) | P2 (boil lakes — cumple el mismo criterio <1 día que el resto de 3A) | No hay razón para esperar a que el script se re-corra si el guard es barato de agregar ahora |
| 9 | Eng | Desempate manual (ítem #38) se mueve de 3B a 3A-12 | Mecánica (hallazgo de revisión adversarial — la decisión de producto ya estaba confirmada en `motor-formatos-plantillas-navegacion-plan.md`) | P1 (completeness) | Clasificarlo como "necesita decisión" cuando la decisión ya existe demoraría un ítem que podría implementarse ya |
| 10 | Eng | 3B-11 (rol Superadmin) se trata como "ciclo propio" (3B-iii), no como decisión rápida | Mecánica (hallazgo de revisión adversarial) | P3 (scope — mismo orden de magnitud que 3B-9) | Toca el `CHECK` de roles y cada `require_roles(...)` del código, no es una llamada de producto de bajo impacto |

---

## Tareas de implementación (agregadas, sin priorizar por sprint)

**Fase 0 (prerrequisito):**
- [ ] Commitear el working tree de `gestion-avanzada-equipos-control-mesa-plan.md` (un solo commit — "roles y 3 módulos" no necesita commit, ya está committeado).
- [ ] Aplicar la actualización de `TODOS.md` (sección siguiente de este documento).

**Fase 3A (accionable, sin decisión pendiente):**
- [ ] 3A-1 — Autocomplete de tabla en Auditoría.
- [ ] 3A-2 — Filtro `registro_id` en Auditoría.
- [ ] 3A-3 — Export CSV de Auditoría (client-side, con aviso de truncado).
- [ ] 3A-4 — Lock de cupo de modalidad (EC-6).
- [ ] 3A-5 — Banner de truncado en grillas faltantes (7 pantallas).
- [ ] 3A-6 — Centralizar tipos de fila (`EquipoRow`, `ModalidadRow`).
- [ ] 3A-7 — Demo Copa Raíces al patrón de inscripción individual real.
- [ ] 3A-8 — Guard de `partido.estado` en `MesaPanel`.
- [ ] 3A-9 — Filtro de Estado del torneo en la barra de disciplinas.
- [ ] 3A-10 — Persistir filtro de disciplina/modalidad en la URL.
- [ ] 3A-11 — Guard en migración 08 Parte E (volcar IDs ambiguos antes del `DROP COLUMN`).
- [ ] 3A-12 — UI de desempate manual en tabla de posiciones (EC-51).

**Fase 3B-i (recomendación por defecto — procede salvo objeción):**
- [ ] 3B-1, 3B-5 (no hacer nada), 3B-6 (no hacer nada), 3B-7, 3B-8, 3B-14.

**Fase 3B-ii (bloquea — necesita decisión real primero):**
- [ ] 3B-2, 3B-4, 3B-10, 3B-13 — ver recomendaciones técnicas en Fase 3, cada una espera un dato/criterio de negocio, no una opción técnica.

**Fase 3B-iii (ciclo propio, fuera de este plan):**
- [ ] 3B-9 (cursor real) y 3B-11 (rol Superadmin) — agendar como `/plan-eng-review` dedicado cuando se prioricen.

---

## `TODOS.md` actualizado

El contenido completo, listo para reemplazar el archivo, está en la
sección siguiente de este mismo documento tal como se aplicó en la Fase 0
— ver el diff aplicado directamente sobre `TODOS.md` en este commit/sesión
(no se duplica el archivo completo acá para evitar que las dos copias
diverjan con el tiempo; `TODOS.md` es la fuente viva, este plan es el
registro de por qué quedó así).

---

## GSTACK REVIEW REPORT

- **Modo**: SELECTIVE EXPANSION (housekeeping + cierre de deuda técnica
  acotada + inventario completo de decisiones de producto pendientes;
  ningún módulo nuevo de alcance grande se implementa en este plan).
- **Fases corridas**: CEO ✅ (incluye hallazgo de `TODOS.md` desactualizado
  y D-SCOPE como User Challenge), Design ✅ (scope UI detectado: filtros,
  export, banners — bajo riesgo de interacción), Eng ✅, DX — omitida
  (módulo interno, sin superficie de API/CLI para terceros, mismo
  criterio que los 2 planes anteriores).
- **Voces**: `[subagent-only]` — Codex no disponible en esta máquina
  (binario no encontrado en PATH). Investigación de estado real del
  código delegada a un subagente de exploración (grounding fase Eng);
  revisión adversarial del borrador delegada a un segundo subagente
  (Fase 1.5), corrida de verdad — no simulada — con verificación propia
  contra `git`. Encontró un error real en el primer borrador (ver
  "Revisión cruzada" y Decision Audit Trail #7) que se corrigió antes de
  cerrar este documento, no después.
- **Verificación empírica**: `.\verificar.ps1` corrido de punta a punta
  sobre el working tree actual **antes** de escribir este plan — 237
  tests backend + 148 tests frontend + lint + typecheck + build, **TODO
  VERDE**. La afirmación "gestión avanzada ya está implementada" no es
  una suposición, es un resultado verificado en esta misma sesión; la
  afirmación "roles y 3 módulos ya está implementado Y ya está
  committeado" está verificada con `git show HEAD:...` sobre 3 archivos
  distintos.
- **Gate**: **D-SCOPE** (Fase 1), User Challenge real — el usuario pidió
  cerrar todo `TODOS.md` sin excepción, este plan recomendó no incluir
  ~10 módulos de producto grandes nunca pedidos. **Confirmado por el
  usuario 2026-09-01, eligió la opción recomendada.** `TODOS.md` ya
  refleja los 3 estados resultantes, y la Fase 0 (commit del working tree
  de gestión avanzada) ya se ejecutó — ver commits de esta sesión.
- **No implementado**: cero código ni cambios de esquema — solo este
  documento y (pendiente de confirmación del usuario) la actualización de
  `TODOS.md`, como se pidió explícitamente ("no lo implementemos aún").
- **Siguiente paso sugerido**: confirmar D-SCOPE → aplicar Fase 0
  (commit + `TODOS.md`) → priorizar 3A antes que 3B (ninguna depende de
  una decisión de producto) → agendar la ronda de decisiones 3B-1 a
  3B-14 como una sesión corta de `/plan-eng-review` o respuestas directas,
  no una a la vez.

**STATUS: DONE — D-SCOPE confirmado, Fase 0 aplicada.**
