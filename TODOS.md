# TODOS

**Estado de esta lista, al día:** todo lo que seguía genuinamente
pendiente al 2026-09-01 fue triado en
`docs/plans/cierre-backlog-todos-plan.md` — cada ítem quedó en uno de 3
estados: **hecho** (retirado de acá), **en curso** (con tarea y fase
concreta dentro de ese plan) o **aparcado a propósito** (su propia
sección más abajo, con la razón). Si algo de lo que sigue en esta lista
ya se resolvió y no se actualizó, es la lista la que está desactualizada,
no el código — verificar contra el repo antes de asumir que falta algo
(dos secciones enteras de esta misma lista estaban así de desactualizadas
la última vez que se auditó).

## Auditoría de cambios (tabla `AUDITORIA`) — implementado

Plan en `docs/plans/auditoria-cambios-plan.md`. Alta/modificación/baja de
cualquier entidad del sistema, quién la hizo y qué cambió, retenida 1 mes.
Se consulta en `/admin/auditoria`, solo `AdminGeneral`.

Deferido desde ese plan — **en curso** (accionable, sin decisión de
producto pendiente, ver `docs/plans/cierre-backlog-todos-plan.md` §3A):

- **Filtro por tabla en la UI es texto exacto**, sin autocomplete de las 18
  tablas posibles — 3A-1.
- **Sin filtro de `registro_id` en la pantalla** (sí existe en `GET
  /auditoria?registro_id=`) — 3A-2.
- **Sin export/descarga** (CSV u otro formato) de la bitácora — 3A-3.

## Roles y 3 módulos (Admin General / Torneo Admin / Árbitro) — implementado

Plan fase por fase en `docs/plans/roles-3-modulos-plan.md`. **Las 4 fases
están completas y committeadas** (58/58 tareas `[x]`, verificado con
`.\verificar.ps1` en verde: 237 tests backend + 148 frontend). Roles
reales (`AdminGeneral`/`TorneoAdmin`/`Arbitro`/`Publico`), asignación
árbitro↔partido, y las 3 pantallas (`/torneo-admin`, `/arbitro`,
`/admin/usuarios`) están en producción sobre esta rama.

Riesgo aceptado documentado por su propio Eng Review, nunca listado acá
hasta ahora — **en curso**, ver `cierre-backlog-todos-plan.md` §3A-8:

- **`MesaPanel` no valida `partido.estado` antes de aceptar un evento.**
  La protección hoy vive solo en el filtro de la lista
  (`ControlDeMesaPage` solo deja *seleccionar* partidos Programado/En
  curso), no en el panel — "Mis partidos" es un segundo camino de entrada
  al mismo componente que no pasa por ese filtro. Aceptado como riesgo en
  su momento (decisión D6), con la recomendación explícita de agregarlo
  acá si se volvía relevante.

## Gestión Avanzada de Equipos + Control de Mesa — implementado

Plan en `docs/plans/gestion-avanzada-equipos-control-mesa-plan.md`.
Plantilla Base de equipo (jugadores de un club antes de cualquier
torneo, con alerta de multimilitancia no bloqueante), cronómetro
configurable por torneo (Períodos/Corrido) con hitos auditables, y
corrección de minuto tanto en hitos de tiempo como en eventos de
gol/tarjeta ya cargados. Verificado en verde junto con el resto del
sistema (ver arriba). Resuelve, de otras secciones de este archivo:

- La necesidad funcional de "jugador del club antes de un torneo" —
  vía `EQUIPO_JUGADOR_BASE` (Decisión D1-C), una tabla delgada y
  **no autoritativa**, no la alternativa completa que se había evaluado
  y rechazado antes (ver "Equipo con roster autoritativo permanente" más
  abajo, que sigue aparcada — D1-C no es esa alternativa, es una más
  liviana).
- La falta de `PATCH /eventos-partido/{id}` para corregir el minuto de un
  gol/tarjeta ya cargado.

Deferido desde ese mismo plan:

- **Offline-first en Control de Mesa — alcance reducido, sigue sin UI
  dedicada.** El estado del cronómetro ya sobrevive una desconexión (se
  recalcula del último Hito guardado en el servidor al reconectar), pero
  no hay indicador de "sin conexión" en pantalla ni cola de reintento
  para el evento que se estaba cargando justo al cortarse — **en curso**,
  ver `cierre-backlog-todos-plan.md` §3B-1 (recomendación con default
  seguro, procede salvo objeción).
- **Tiempo extra / prórroga / penales** como estructura de cronómetro
  propia — no pedido; un torneo que los usa hoy los resuelve como ya lo
  hace (`Ganador_Desempate_ID`), sin cronómetro dedicado.

## Equipo con roster autoritativo permanente — aparcado

Evaluado y rechazado dos veces (primero en
`equipos-disciplina-navegacion-plan.md`, reabierto y vuelto a acotar en
`gestion-avanzada-equipos-control-mesa-plan.md` — ver sección anterior).
Es la versión "grande" de un equipo como entidad rica: roster estable,
escudo, sede, palmarés, staff — con su propia noción de vigencia que
habría que conciliar con la vigencia real de `JUGADOR_EQUIPO` (por
torneo). La necesidad funcional que la motivaba ya está cubierta por
`EQUIPO_JUGADOR_BASE` (no autoritativo). Si en algún momento el equipo
necesita existir como entidad con socios estables, es un plan aparte —
dos fuentes de verdad de "quién es del equipo" que `fn_validar_jugador_partido`
y `fn_validar_exclusividad_torneo` hoy no saben conciliar.

## Frontend — deferido desde el design doc de Dashboard/Control de Mesa/Partido en Vivo

- El modelo de datos no distingue titular/suplente ni "convocado a este
  partido". El flujo de Cambio usa toda la plantilla vigente como
  candidatos a entrar/salir (ver limitación documentada en
  `frontend/README.md`). **En curso** (necesita confirmar si el problema
  ya duele en uso real antes de construirse), ver
  `cierre-backlog-todos-plan.md` §3B-2.

## Deferido desde el plan de Equipos y Jugadores (`docs/plans/equipos-jugadores-plan.md`)

- **Desactivación de una persona** (`JUGADORES.Estado → Inactivo`) que
  tiene perfiles de disciplina o membresías de equipo activas. **En
  curso** (necesita confirmar el default — bloquear vs. cascada — antes
  de implementar), ver `cierre-backlog-todos-plan.md` §3B-3, que ya trae
  una recomendación (bloquear con 409, no cascada silenciosa).
- **Límite de tamaño de plantilla** para disciplinas de equipo grande
  (Fútbol). El plan sí limita pareja/individual vía
  `Modalidad.Tamano_Equipo`, pero no pone techo a un roster de fútbol.
  **En curso** (falta el número real, competitivo/reglamentario, no
  técnico), ver `cierre-backlog-todos-plan.md` §3B-4.
- **Notificación por correo** al jugador cuando es traspasado o pasa a
  jugador libre — **aparcado**. Módulo de notificaciones aparte, requiere
  decidir proveedor de correo primero (decisión de infraestructura, no de
  este archivo).
- **Importación masiva desde CSV/Excel** para el registro por lote — **aparcado**.
  No pedido; formato/validación de archivo es diseño propio si se pide.

## Deferido desde el plan de Administración de Torneos (`docs/plans/torneos-admin-plan.md`)

- **Vista consolidada de estadísticas cruzando todas las ediciones** de un
  mismo `TORNEO_GRUPO`. **En curso** (recomendación: no construir todavía
  — mezclar jugadores que cambiaron de equipo entre ediciones necesita
  una regla de negocio antes que una respuesta técnica), ver
  `cierre-backlog-todos-plan.md` §3B-5.
- **Clonar la plantilla de una edición a la siguiente** al crear una
  edición nueva. **En curso** (recomendación: no implementar, sigue sin
  pedirse), ver `cierre-backlog-todos-plan.md` §3B-6.
- **Archivar/eliminar un `TORNEO_GRUPO` completo** con todas sus
  ediciones. **En curso** (recomendación: baja lógica, sin cascada a las
  ediciones), ver `cierre-backlog-todos-plan.md` §3B-7.
- **Traspasos entre ediciones distintas** del mismo grupo. **En curso**
  (recomendación: alta nueva en la edición destino, no traspaso, sin
  cambio de esquema), ver `cierre-backlog-todos-plan.md` §3B-8.
- ~~Filtro `?torneo_id=` real en `/plantillas`, `/traspasos`,
  `/partidos`~~ — **hecho.** Los 3 endpoints ya filtran de verdad
  (verificado contra el código el 2026-09-01, no solo contra este
  archivo, que decía lo contrario).

## Deferido desde el `/review` de equipos-jugadores-plan.md (Fase 3)

- **Cupo de modalidad (EC-6) sin lock.** `RegistroLoteService._validar_lote`
  calcula `cupo_restante` leyendo el conteo de activos una sola vez, sin
  `SELECT ... FOR UPDATE` ni advisory lock. **En curso** (accionable,
  patrón de lock ya existe en el repo para copiar), ver
  `cierre-backlog-todos-plan.md` §3A-4.
- **Migración `08_migracion_equipos_jugadores.sql`, Parte E, sin rastro de
  auditoría.** Cuando una fila vieja de `JUGADOR_EQUIPO` tiene más de una
  `INSCRIPCIONES_TORNEO` candidata, el script elige la más antigua y solo
  deja un `RAISE WARNING` — no los IDs de las filas ambiguas — antes de
  dropear `JUGADOR_ID`/`EQUIPO_ID`. **En curso** (accionable, mismo
  criterio de blindaje que el resto de la deuda técnica de este archivo,
  no hace falta esperar a que se re-corra), ver
  `cierre-backlog-todos-plan.md` §3A-11.

## Deferido desde el plan de Catálogo Maestro de Disciplinas (`docs/plans/ediciones-catalogo-disciplinas-plan.md`)

- **Registro de resultados/estadísticas para disciplinas de marca y tiempo**
  (Atletismo, Natación, Ciclismo), **combate** (MMA, Boxeo, Judo, Taekwondo,
  Karate) o **mente** (Ajedrez) — **aparcado**. `PARTIDOS`/`EVENTOS_PARTIDO`
  asumen siempre dos equipos y goles; merece su propio diseño de producto
  (¿"partido" = combate/carrera? ¿cómo se registra un tiempo o un ganador
  por sumisión?), rechazado explícitamente de re-abrirse en 2 planes
  posteriores.
- **Categorías de peso/cinturón reales de una federación** para las
  disciplinas de Combate — **aparcado**. El catálogo precarga 3
  categorías genéricas como placeholder editable solo por migración SQL —
  no la tabla oficial de cada federación (varía por región/edad/género),
  y no es una decisión técnica.
- **Límite superior de inscripciones por torneo** (cuántos Equipos/Jugadores
  caben en un bracket). **En curso** (falta el número, depende del
  torneo), ver `cierre-backlog-todos-plan.md` §3B-10.
- **eSports — brackets y estadísticas** — **aparcado**. El catálogo cubre
  inscripción (equipos de 5, parejas, 1v1), no brackets de doble
  eliminación ni integración con APIs de plataformas (Riot, Steam) — es
  un módulo de "sistema de brackets" aparte, integración externa.
- **Ajustar el catálogo maestro fuera de una migración SQL manual** (EC-32).
  Bajo la Decisión C1 (catálogo inmutable, solo toggle de Estado) un admin
  no tiene forma de agregar/corregir una disciplina desde la UI. **En
  curso, pero con ciclo propio** (toca el `CHECK` de roles y cada
  `require_roles(...)` del código, mismo orden de magnitud que la
  paginación con cursor de abajo — no es una decisión rápida), ver
  `cierre-backlog-todos-plan.md` §3B-11.

## Deferido desde el plan de Equipos con Disciplina + Navegación (`docs/plans/equipos-disciplina-navegacion-plan.md`)

Implementado con las opciones recomendadas: **A1** (plantilla derivada,
sin tabla de roster permanente — superada por D1-C, ver sección de
"Gestión Avanzada" arriba), **B1** (Categoría = Modalidad), **C2**
(backfill + `NOT NULL`), **EC-44** literal y las **4 mejoras**
propuestas. Lo que quedó afuera:

- **Catálogo de categorías etarias/de género** (`Sub-13`, `Libre`,
  `Femenino`, `Mixto`...) — **aparcado**. La columna "Categoría" de la
  grilla muestra la Modalidad; si tiene que significar edad/género es un
  módulo propio (tabla, seed, UI de catálogo, reglas de elegibilidad).
- **Iconos SVG propios por disciplina** — **aparcado**. `iconosDisciplina.ts`
  mapea las 28 disciplinas a emoji con inicial como fallback; es trabajo
  de diseño gráfico, no de ingeniería.
- **Paginación real con cursor en `/equipos` (y ahora también
  `/jugadores`).** El banner de "primeros 200" ya avisa cuando trunca; el
  cursor real (y la búsqueda `?nombre=`/`?q=` server-side) siguen
  pendientes. **En curso, pero con ciclo propio** (cambio de contrato de
  API — rompe cualquier cliente que asuma offset, no es un fix acotado),
  ver `cierre-backlog-todos-plan.md` §3B-9.
- **Filtro por Estado del torneo en la barra de disciplinas.** **En
  curso**, ver `cierre-backlog-todos-plan.md` §3A-9.
- **Persistir el filtro elegido en la URL** en `TorneosAdminPage`. **En
  curso**, ver `cierre-backlog-todos-plan.md` §3A-10.
- **`UNIQUE (Nombre, Disciplina_ID)` en `EQUIPOS`** (EC-43) — **aparcado**.
  Rompería datos existentes sin que nadie lo haya pedido.
- **Las inscripciones cruzadas PREEXISTENTES no se cancelan solas** — es
  limpieza de datos puntual, no una tarea de código; el caso conocido ya
  se resolvió a mano.

## Deuda técnica cerrada al finalizar ese plan (contexto, no pendiente)

- Los 3 GET de `/jugadores` con proyección dual (con/sin PII) tenían
  `response_model=None` y por eso su respuesta era `unknown` en el OpenAPI
  — todo consumidor generado quedaba sin tipo. Se documentó la unión real
  con `responses={200: ...}` sin tocar el runtime. Si mañana se agrega otra
  ruta con proyección dual, **copiar ese patrón**: `response_model=None`
  para el runtime + `responses=` para el contrato.
- `AuthContext.tsx` exportaba `AuthProvider` junto con `useAuth`/`Rol`, lo
  que desactivaba Fast Refresh para ese módulo. Ahora el componente vive
  solo en `AuthContext.tsx`; el hook en `useAuth.ts` y el contexto/tipos en
  `authContextValue.ts`. **Regla para nuevos contextos:** el archivo del
  provider exporta el componente y nada más.
- `10_demo_torneos_admin.sql` insertaba equipos solo con `Nombre` y quedó
  roto cuando `EQUIPOS` ganó dos columnas `NOT NULL`. Nadie se enteró
  porque ningún test tocaba los scripts numerados 10+. Arreglado, y ahora
  lo cubre `backend/tests/test_scripts_sql.py` — que además verifica que
  esos scripts sigan siendo re-ejecutables. **Regla:** si cambiás el
  esquema, ese test es el que avisa si rompiste el seed o la demo.
- El techo de 200 filas estaba hardcodeado en `useResourceCrud` y repetido
  a mano en `EquiposAdmin`. Ahora el hook exporta `LIMITE_LISTA` y
  devuelve `truncado` ya calculado; cualquier página que liste puede
  mostrar el aviso sin repetir el número. **Las demás grillas todavía no
  lo muestran** — en curso, ver `cierre-backlog-todos-plan.md` §3A-5.

## Ideas para cuando se retome (no bloquean nada)

- **Las otras grillas no avisan cuando truncan.** `useResourceCrud` ya
  expone `truncado`; falta usarlo en Jugadores, Usuarios y los 5
  listados del dashboard de torneo. **En curso**, ver
  `cierre-backlog-todos-plan.md` §3A-5.
- **Los tipos de fila del frontend se declaran a mano en cada componente**
  (`EquipoRow` existe en 8 archivos, no 3 — creció desde que se escribió
  esta nota — `ModalidadRow` en 4). `schema.d.ts` ya tiene la forma real
  generada del backend. **En curso**, ver
  `cierre-backlog-todos-plan.md` §3A-6.
- **No hay CI.** `verificar.ps1` corre todo local — **aparcado**, mover a
  GitHub Actions es infraestructura nueva, no deuda de producto.
- **La demo `10_*.sql` sigue usando el patrón viejo para Copa Raíces**
  (Tenis Individual): crea un EQUIPOS fantasma llamado "Micky Fernández" e
  inscribe por `Equipo_ID`, en vez de inscripción individual por
  `Jugador_Perfil_ID` (Decisión B1). **En curso**, ver
  `cierre-backlog-todos-plan.md` §3A-7.

## Auditoría de accesos (tabla `ACCESOS`) — implementado

Cada intento de inicio de sesión queda registrado, exitoso o fallido:
usuario, fecha, IP, user-agent y el motivo del fallo (`credenciales` vs
`inactivo`, que son dos historias distintas para quien audita). Se consulta
en `/admin/accesos`, solo `AdminGeneral`.

Decisiones que conviene no deshacer sin pensarlo:

- **El registro se commitea ANTES de lanzar `AuthError`.** `get_db()` hace
  rollback cuando una excepción sube por el request; anotar el fallo y
  lanzar sin commit de por medio borraría justo la fila que interesa. Está
  cubierto por `test_login_fallido_queda_registrado_pese_al_rollback`.
- **No hay POST/PATCH/DELETE sobre `/accesos`**, ni para `AdminGeneral`.
  Una bitácora que se puede escribir o borrar desde afuera no prueba nada.
- **Nunca se guarda la contraseña probada**, ni hasheada — un hash acá
  permitiría confirmar offline si una contraseña adivinada era la correcta.
  Hay un test de regresión explícito.
- **La IP sale de `X-Forwarded-For`** cuando está, porque detrás de un
  proxy `request.client.host` es siempre la misma IP interna. Ese header es
  falsificable si la app queda expuesta sin proxy: es dato indicativo para
  auditar, y **no se usa para ninguna decisión de autorización**.

Pendiente, si el volumen lo pide:

- ~~**Retención.**~~ Hecho: la API purga al arrancar lo que tenga más de
  `ACCESOS_RETENCION_DIAS` (30 por defecto, configurable en `.env`; `0` =
  no purgar). **Limitación conocida:** corre en el arranque, así que un
  servidor que queda semanas levantado sin reiniciar no purga. Alcanza para
  este proyecto (el backend se levanta a mano cada vez que se enciende la
  máquina), pero si pasa a correr como servicio permanente hay que mudar la
  purga a un scheduler real — pg_cron, o un cron del sistema llamando a
  `AccesoRepository.purgar_anteriores_a`.
- **No se registra el logout** — **aparcado**. El token es JWT sin estado
  del lado del servidor; tenerlo requiere una lista de tokens revocados,
  que es otro diseño de seguridad propio.
- **Nada alerta sobre N fallos seguidos.** Hoy el dato está y hay que ir a
  mirarlo. **En curso** (patrón estándar, procede salvo objeción), ver
  `cierre-backlog-todos-plan.md` §3B-14.

## Motor de Formatos + Plantillas + Navegación — implementado

Plan en `docs/plans/motor-formatos-plantillas-navegacion-plan.md`. Los
4 requerimientos están construidos y probados. Una decisión se apartó del
texto literal del plan, documentada acá porque un futuro "convergé esto"
no debería sorprender a nadie:

- **`PARTIDOS.Fase`/`Grupo` (texto libre) NO se soltaron, a diferencia de
  lo que decía el plan ("se sueltan tras el backfill").** El motor nuevo
  escribe `Fase_ID`/`Grupo_ID`/`Ronda_Nombre` (estructura real); el alta
  manual de partidos ya existente (`POST /partidos`, pantalla "Partidos"
  con el botón "+ Nuevo") sigue escribiendo `Fase`/`Grupo` como texto,
  sin tocar. Las dos formas conviven sin pisarse. Ver el comentario
  grande en `database/01_schema.sql` (`CREATE TABLE PARTIDOS`).
- **Convergerlas de verdad** — que "+ Nuevo" en la pestaña Partidos
  también arme/reutilice una `FASE`/`GRUPO` en vez de texto libre — es
  candidato a un plan aparte cuando haga falta (ej. si un admin empieza a
  mezclar alta manual con el motor en el MISMO torneo, caso hoy no
  ejercitado por ninguna pantalla).
- **Desempate en la tabla de posiciones de un grupo (EC-51).** La decisión
  de producto (enfrentamiento directo y resolución manual del admin) ya
  está confirmada — solo falta la UI. **En curso**, ver
  `cierre-backlog-todos-plan.md` §3A-12.
- **Bracket visual** — **aparcado**. `GET /torneos/{id}/bracket` +
  `MotorFormatosPanel` muestran las rondas en columnas sin las líneas de
  conexión del árbol — es pieza de diseño gráfico (SVG/canvas), no
  bloqueaba la funcionalidad.
- **Walkover/retiro a mitad de una fase de Eliminación.** **En curso**
  (necesita una sesión de diseño propia, sin opción "obviamente
  correcta" para recomendar todavía), ver
  `cierre-backlog-todos-plan.md` §3B-13.

---

Para el detalle de cada decisión "en curso" (recomendación, alternativas
consideradas, edge cases, tests) — no repetido acá para que esta lista no
vuelva a desincronizarse del documento que sí lo mantiene — ver
`docs/plans/cierre-backlog-todos-plan.md`.
