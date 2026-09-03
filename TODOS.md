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
Se consulta en `/admin/auditoria`, solo `AdminGeneral` — con autocomplete
de tabla (nombres reales de `__tablename__`, no un texto libre), filtro
por `registro_id` y export CSV client-side con aviso si hay más de 200
filas (3A-1/3A-2/3A-3, `docs/plans/cierre-backlog-todos-plan.md`, hecho el
2026-09-01).

## Roles y 3 módulos (Admin General / Torneo Admin / Árbitro) — implementado

Plan fase por fase en `docs/plans/roles-3-modulos-plan.md`. **Las 4 fases
están completas y committeadas** (58/58 tareas `[x]`, verificado con
`.\verificar.ps1` en verde: 237 tests backend + 148 frontend). Roles
reales (`AdminGeneral`/`TorneoAdmin`/`Arbitro`/`Publico`), asignación
árbitro↔partido, y las 3 pantallas (`/torneo-admin`, `/arbitro`,
`/admin/usuarios`) están en producción sobre esta rama.

Riesgo aceptado documentado por su propio Eng Review (decisión D6) —
**resuelto:**

- ~~`MesaPanel` no valida `partido.estado` antes de aceptar un evento~~ —
  **hecho.** El guard vive ahora en `EventoPartidoService.create`
  (backend) y en `MesaPanel` (frontend) — "Mis partidos" (segundo camino
  de entrada al mismo componente) ya no puede esquivarlo (3A-8,
  `docs/plans/cierre-backlog-todos-plan.md`, hecho el 2026-09-01).

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

- ~~Offline-first en Control de Mesa — alcance reducido~~ — **hecho.**
  Indicador de "sin conexión" (`useOnlineStatus`) + cola de UN evento
  pendiente por partido en `localStorage` — un fallo de RED (no un
  rechazo real del backend) lo encola en vez de perderlo, con reintento
  automático (evento `online` del navegador + intervalo de respaldo cada
  15s, para wifi de cancha intermitente que no siempre dispara ese
  evento) y "Reintentar ahora"/"Descartar" manuales (3B-1,
  `docs/plans/cierre-backlog-todos-plan.md`, hecho el 2026-09-01).
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

- ~~El modelo de datos no distingue titular/suplente ni "convocado a este
  partido". El flujo de Cambio usa toda la plantilla vigente como
  candidatos a entrar/salir~~ — **hecho.** Tabla `CONVOCADO_A_PARTIDO`
  (delgada, no autoritativa, mismo patrón que `EQUIPO_JUGADOR_BASE`) +
  panel "Convocados" opt-in en Control de Mesa (`Convocatoria.tsx`) para
  definir titular/suplente por partido — sin convocatoria guardada, el
  comportamiento no cambia (toda la plantilla vigente sigue siendo
  candidata); con una guardada, `CargaEvento` filtra a solo los convocados
  (3B-2, `docs/plans/cierre-backlog-todos-plan.md`, hecho el 2026-09-02).

## Deferido desde el plan de Equipos y Jugadores (`docs/plans/equipos-jugadores-plan.md`)

- ~~Desactivación de una persona~~ (`JUGADORES.Estado → Inactivo`) que
  tiene perfiles de disciplina o membresías de equipo activas — **hecho.**
  Bloqueada con 409 (no cascada silenciosa) si el jugador tiene alguna
  `JUGADOR_EQUIPO` en estado Activo — recomendación del plan tomada
  literal (3B-3, `docs/plans/cierre-backlog-todos-plan.md`, hecho el
  2026-09-02).
- ~~Límite de tamaño de plantilla~~ para disciplinas de equipo grande
  (Fútbol) — **hecho.** `Modalidad.Tamano_Plantilla_Max` (nullable, solo
  seteado para Fútbol 11 = 25 jugadores; el resto de las modalidades de
  fútbol y todo lo demás queda sin techo), validado en
  `RegistroLoteService` junto al resto de las reglas de cupo (3B-4,
  `docs/plans/cierre-backlog-todos-plan.md`, hecho el 2026-09-02).
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
- ~~Archivar/eliminar un `TORNEO_GRUPO` completo~~ con todas sus
  ediciones — **hecho.** Baja lógica (`Estado` Activo/Archivado), nunca
  DELETE, sin cascada a las ediciones existentes — oculto de `GET
  /torneo-grupos` por default, botón Archivar/Reactivar + toggle "Ver
  archivados" en la UI (3B-7, `docs/plans/cierre-backlog-todos-plan.md`,
  hecho el 2026-09-01).
- ~~Traspasos entre ediciones distintas~~ del mismo grupo — **hecho.**
  `TraspasoService.crear` rechaza un origen/destino de ediciones
  distintas y dirige a dar de alta en la edición destino en vez de un
  traspaso — sin cambio de esquema (3B-8,
  `docs/plans/cierre-backlog-todos-plan.md`, hecho el 2026-09-01).
- ~~Filtro `?torneo_id=` real en `/plantillas`, `/traspasos`,
  `/partidos`~~ — **hecho.** Los 3 endpoints ya filtran de verdad
  (verificado contra el código el 2026-09-01, no solo contra este
  archivo, que decía lo contrario).

## Deferido desde el `/review` de equipos-jugadores-plan.md (Fase 3) — implementado

- ~~Cupo de modalidad (EC-6) sin lock~~ — **hecho.**
  `InscripcionTorneoRepository.lock_cupo_inscripcion` (mismo patrón
  `pg_advisory_xact_lock` que `lock_exclusividad_torneo`), verificado con
  un test de concurrencia REAL (dos conexiones/transacciones
  independientes, no la sesión compartida del harness de tests) — 3A-4,
  `docs/plans/cierre-backlog-todos-plan.md`, hecho el 2026-09-01.
- ~~Migración `08_migracion_equipos_jugadores.sql`, Parte E, sin rastro de
  auditoría~~ — **hecho.** Las filas ambiguas se vuelcan a
  `migracion_08_jugador_equipo_ambiguos` antes del `DROP COLUMN` que se
  llevaba la única evidencia (`Jugador_ID`/`Equipo_ID` originales) — 3A-11,
  `docs/plans/cierre-backlog-todos-plan.md`, hecho el 2026-09-01.

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
- ~~Límite superior de inscripciones por torneo~~ (cuántos Equipos/Jugadores
  caben en un bracket) — **hecho.** `Torneo.Cupo_Maximo_Inscripciones`
  (nullable = sin límite, decisión tomada), con lock
  `pg_advisory_xact_lock` propio (mismo patrón que el cupo de modalidad,
  EC-6) contra la carrera de dos inscripciones simultáneas llegando juntas
  al límite (3B-10, `docs/plans/cierre-backlog-todos-plan.md`, hecho el
  2026-09-02).
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
- ~~Filtro por Estado del torneo en la barra de disciplinas~~ — **hecho**
  (3A-9, `docs/plans/cierre-backlog-todos-plan.md`, hecho el 2026-09-01).
- ~~Persistir el filtro elegido en la URL~~ en `TorneosAdminPage` —
  **hecho.** Los tres filtros (disciplina, modalidad, estado) se leen Y
  se escriben en la URL — "Ver todos" limpia los tres a la vez (3A-10,
  `docs/plans/cierre-backlog-todos-plan.md`, hecho el 2026-09-01).
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
  mostrar el aviso sin repetir el número. El resto de las grillas
  (Jugadores, Usuarios, los 5 listados del dashboard de torneo) ya lo
  muestran también (3A-5, `docs/plans/cierre-backlog-todos-plan.md`,
  hecho el 2026-09-01).
- Los tipos de fila del frontend se declaraban a mano en cada componente
  (`EquipoRow` en 8 archivos, `ModalidadRow` en 4). Ahora
  `frontend/src/api/types.ts` centraliza `Equipo`/`Modalidad` como alias
  de `components["schemas"]` (el contrato generado del backend) — las 12
  declaraciones ad-hoc quedaron reemplazadas por un import (3A-6,
  `docs/plans/cierre-backlog-todos-plan.md`, hecho el 2026-09-01).
- La demo `10_demo_torneos_admin.sql` ya no usa el patrón viejo para Copa
  Raíces (Tenis Individual) — dejó de crear un `EQUIPOS` fantasma llamado
  "Micky Fernández" e inscribe directo por `Jugador_Perfil_ID` (Decisión
  B1), como cualquier inscripción individual real (3A-7,
  `docs/plans/cierre-backlog-todos-plan.md`, hecho el 2026-09-01).

**No hay CI** — `verificar.ps1` corre todo local. **Aparcado**: mover a
GitHub Actions es infraestructura nueva, no deuda de producto.

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
- ~~Nada alerta sobre N fallos seguidos~~ — **hecho.** 5 fallos de
  CREDENCIALES (no `inactivo`/`bloqueado`, para no auto-extender el
  bloqueo) por (usuario, IP) en 15 minutos bloquea el siguiente intento
  con 429 + `Retry-After` (`login_rate_limit_intentos`/
  `_ventana_minutos` en `.env`, `0` = apagado) — 3B-14,
  `docs/plans/cierre-backlog-todos-plan.md`, hecho el 2026-09-01.

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
- ~~Desempate en la tabla de posiciones de un grupo (EC-51)~~ — **hecho.**
  Botón "Definir manualmente" + columna de override en
  `EstadisticasDelTorneoPage`, solo para equipos realmente empatados
  (PTS/DG/GF idénticos) — el desempate manual es el desempate de ÚLTIMA
  instancia, nunca puede promover a un equipo por encima de otro con más
  puntos (3A-12, `docs/plans/cierre-backlog-todos-plan.md`, hecho el
  2026-09-01).
- **Bracket visual** — **aparcado**. `GET /torneos/{id}/bracket` +
  `MotorFormatosPanel` muestran las rondas en columnas sin las líneas de
  conexión del árbol — es pieza de diseño gráfico (SVG/canvas), no
  bloqueaba la funcionalidad.
- ~~Walkover/retiro a mitad de una fase de Eliminación.~~ — **hecho** para
  disciplinas de equipo. `PARTIDOS.Es_Walkover`/`Walkover_Equipo_Ausente_ID`
  + botón "Walkover" en `PartidosDelTorneo` (TorneoAdmin/Árbitro): marca
  3-0 contra el ausente, propaga el ganador al siguiente partido del
  bracket igual que un resultado normal. En fase de Eliminación siempre
  disponible (el bracket necesita un ganador para avanzar); en Liga/Grupos
  requiere `Torneo.Permite_Walkover_Grupos` (opt-in al crear el torneo, tal
  como se pidió) — sin ese flag, un walkover en fase de grupos se
  rechaza con 409 (3B-13, `docs/plans/cierre-backlog-todos-plan.md`, hecho
  el 2026-09-02). **Queda afuera:** el escenario de abandono en
  disciplinas individuales (Tenis) — el Motor de Formatos hoy no genera
  `PARTIDOS` para inscripciones individuales en absoluto (filtra
  `equipo_id IS NOT NULL`), es la limitación aparte de "Registro de
  resultados para disciplinas individuales" más abajo, no algo que este
  ítem pueda resolver sin ese trabajo previo.

---

Para el detalle de cada decisión "en curso" (recomendación, alternativas
consideradas, edge cases, tests) — no repetido acá para que esta lista no
vuelva a desincronizarse del documento que sí lo mantiene — ver
`docs/plans/cierre-backlog-todos-plan.md`.

## Deferido desde el plan de RBAC — Asignación de Torneos + Licenciamiento (`docs/plans/rbac-licencias-torneos-plan.md`)

Fases 1, 2 y 3 del plan **implementadas** el 2026-09-02 (320 tests backend
+ 196 frontend, todos verdes; migración 26 aplicada a `torneos_mvp`). Ver
el plan, §12, para el detalle exacto de qué se scoped y qué quedó afuera
a propósito.

- ~~Rollout de `require_torneo_access` a los routers restantes~~ —
  **hecho.** 8 de los 15 routers gateados a TorneoAdmin tenían un
  `torneo_id` real resoluble (directo o vía 1-3 hops de join):
  `inscripciones`, `partidos`, `motor_formatos`, `plantillas`,
  `traspasos`, `registro_lote`, `grupos`, `eventos_partido` — todos
  scoped, con test de "TorneoAdmin sin asignación recibe 403" propio.
  **Decisión explícita del usuario:** los otros 7 (`equipos`, `jugadores`,
  `perfiles`, `disciplinas`, `modalidades`, `eventos`-catálogo,
  `torneo_grupos`) quedan **sin scoping, a propósito** — son catálogos
  globales o un pool compartido sin torneo único (`equipos.py` documenta
  esto mismo en su propio código: "pool compartido, sin dueño"); forzar
  un `torneo_id` ahí rompería ese diseño en vez de completarlo.
- ~~Filtrar los listados de `torneo-admin/*`~~ — **hecho** para
  `TorneosAdminPage` (el listado principal): filtro "mis torneos" vía
  `GET /torneos?solo_mios=true` (E1), resuelto en el cliente porque
  `torneo_grupos.py` (el endpoint que esa pantalla consulta) queda fuera
  del scoping por la misma razón que el punto anterior (una franquicia de
  ediciones no tiene un `torneo_id` único — ver plan §12.3). Las
  pantallas de sub-recursos (equipos/jugadores/partidos dentro de un
  torneo específico) no se tocaron — heredan la protección de escritura
  de los 8 routers ya scoped, pero sus LISTADOS siguen sin filtrar por
  asignación (mismo criterio que el resto del pool compartido). Prioridad
  P3 si se quiere profundizar ahí, no bloqueante.
- **Métricas/alertas dedicadas de revocación de licencia** (contador de
  licencias otorgadas/revocadas por día, alerta de pico anómalo de 403 por
  licencia en una ventana corta — señal de un token comprometido siendo
  reusado post-revocación). Hoy `AUDITORIA` cubre el "qué pasó" pero no
  hay dashboard ni alerta activa sobre ese dato. Prioridad: P3.
- ~~Índice compuesto `(Usuario_ID, Torneo_ID, Estado)` en
  `ASIGNACION_TORNEO_ADMIN`~~ — **retirado**, no era un gap real: el
  `UNIQUE(Usuario_ID, Torneo_ID)` que Fase 1 ya especifica es el índice
  que hace falta para el lookup de `require_torneo_access` (probe de una
  sola fila, no un scan) — verificado en la revisión de Eng (voz
  externa), la propuesta original era ruido de proceso, no una
  optimización real.
