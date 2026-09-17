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
  DELETE — oculto de `GET /torneo-grupos` por default, botón
  Archivar/Reactivar + toggle "Ver archivados" en la UI (3B-7,
  `docs/plans/cierre-backlog-todos-plan.md`, hecho el 2026-09-01).
  **Extendido el 2026-09-07** (`docs/plans/cascada-archivado-alineaciones-
  traspasos-plan.md`): archivar un grupo ahora también saca sus ediciones
  de `GET /torneos` (menú público, selector de Control de Mesa) y sus
  partidos `Programado` de `GET /partidos` — salvo acceso directo/scoped
  (`torneo_grupo_id` explícito sigue trayéndolas, mismo criterio que
  `/torneo-grupos/{id}`). Partidos `En curso`/`Finalizado` de un grupo
  archivado nunca se ocultan. Defensa en profundidad en
  `HitoPartidoService.registrar()`: rechaza `Inicio_Partido` de un torneo
  archivado con 400 aunque alguien lo intente por API directa.
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

## Fixes de datos (Alta Local + Traspasos) + Control de Mesa (Titulares) — implementado

Plan en `docs/plans/fixes-datos-traspasos-control-mesa-plan.md`,
implementado el 2026-09-04 (326 tests backend + 198 frontend, todos
verdes; `tsc -b`/`oxlint`/`vite build` en verde).

- ~~Bug 1: "Crear equipo nuevo" perdía la plantilla tipeada en el
  modal~~ — **hecho.** `filasIniciales` viaja del modal a Registro por
  Lote (`ModalAgregarInscripcion.tsx` → `RegistroLoteAdmin.tsx`); la
  pantalla dividida arranca con esas filas ya cargadas.
- ~~Bug 2: nombres reales invisibles detrás de "Equipo #ID"/"Perfil #ID"
  cuando el ID cae fuera de la ventana de `LIMITE_LISTA`~~ — **hecho,
  mitigado.** Resolución dirigida por ID (`useFetchFaltantes`,
  `useNombrePorIdConFaltantes`, `useEtiquetaJugadorPorPerfil`) aplicada en
  los 7 lugares identificados (`EquiposDelTorneo.tsx`,
  `PlantillasDelTorneo.tsx`, `TraspasosDelTorneo.tsx`,
  `MotorFormatosPanel.tsx`, `RegistroLoteAdmin.tsx`, `ControlDeMesa.tsx`,
  `ModalGestionarPlantilla.tsx`) + filtro por `disciplina_id` donde no
  existía. **No** es la paginación real con cursor de 3B-9 (arriba) —
  sigue pendiente con su propio ciclo; esto resuelve el síntoma visible,
  no el techo de 200 filas al LISTAR.
  **Corrección (docs/plans/control-mesa-centralizacion-fixture-plan.md,
  2026-09-04):** faltaba una 8va pantalla —
  `PartidosDelTorneo.tsx` (`torneo-admin/torneos/{id}/partidos`) seguía
  resolviendo `nombreEquipo` sin el hook, reportado por el usuario como
  "?" en el fixture. Mismo parche aplicado ahí.
- ~~Traspasos: dropdown crudo de IDs, sin búsqueda, sin autocompletado de
  origen ni sugerencia de dorsal~~ — **hecho.** `SelectorJugadorBuscable`
  (componente compartido, extraído de `ModalBuscarAgregarJugador`) +
  `useDebouncedValue` (hook compartido, extraído de `useDebouncedEffect`)
  + autocompletado de "Equipo de origen"/"Agencia Libre"
  (`useOrigenActualDelPerfil`) + chips de dorsal histórico
  (`useDorsalesHistoricos`), ambos sobre `GET /plantillas?jugador_perfil_id=`
  ya existente, sin backend nuevo.
- ~~Control de Mesa: "Empezar Partido" no validaba titulares~~ —
  **hecho.** `HitoPartidoService._validar_titulares` (backend, fuente de
  verdad, 409→400 `DomainRuleError` con el equipo y los números exactos)
  + `useTitularesCompletos`/`BotonEmpezarPartido` (frontend, deshabilita
  el botón antes de que el admin lo intente). Usa
  `Modalidad.tamano_equipo` como fuente de "cuántos titulares exige esta
  modalidad" — sin catálogo nuevo. Cubre Pareja (=2) y Conjunto (>2) con
  el mismo cálculo genérico.
- **Migrar `DetalleEquipo.tsx`/`ModalIndividual` al `SelectorJugadorBuscable`
  compartido** — no hecho, mejora recomendada por el plan (D3) pero no
  pedida explícitamente. Ambos quedarían gratis arreglados del mismo techo
  de 200 que afecta al Bug 2.
- **Tope de titulares por ENCIMA de `tamano_equipo`** — fuera de alcance
  a propósito (Decisión Audit #12 del plan): la validación nueva exige el
  mínimo al iniciar, no bloquea un exceso marcado en Convocatoria.

**Post-implementación (2026-09-04), encontrado usando la feature real, no
en el plan original:**

- ~~Bug real: `JugadorEquipoService.list` descartaba `jugador_perfil_id`
  en cuanto se le pasaba `torneo_id` junto~~ — **hecho.**
  `GET /plantillas?jugador_perfil_id=X&torneo_id=Y` devolvía TODO el
  roster del torneo sin filtrar por jugador — `useOrigenActualDelPerfil`
  (Traspasos) hace exactamente esa combinación para autocompletar "Equipo
  de origen", así que mostraba siempre el mismo equipo (el primero de la
  lista sin filtrar) para cualquier jugador. Corregido en
  `JugadorEquipoRepository.listar_por_torneo` (ahora combina los 3
  filtros en una sola consulta) + test de regresión en `test_plantillas.py`.
- ~~"Anular" un traspaso era solo una anotación visual (EC-20 original),
  no revertía el roster~~ — **hecho, decisión explícita del usuario
  (cambia el diseño original del plan equipos-jugadores-plan.md).**
  `TraspasoService.anular` ahora reactiva la membresía de origen y da de
  baja la de destino — el jugador vuelve al club donde estaba. Deja de
  ofrecerse (`TraspasoOut.puede_anularse`, botón oculto en el frontend)
  en cuanto el club DESTINO ya arrancó un partido desde el traspaso
  (`HitoPartidoRepository.existe_inicio_desde`) — a partir de ahí
  corresponde un traspaso nuevo en sentido inverso, no un "deshacer".
- ~~"Datos fantasma" en Plantillas: anular un traspaso (o un traspaso
  normal sin anular) dejaba filas `Inactivo`/`Traspasado` visibles como si
  fueran jugadores vigentes del roster~~ — **hecho, 2026-09-07**
  (`docs/plans/cascada-archivado-alineaciones-traspasos-plan.md`, Área 3).
  El modelo de datos era correcto a propósito (`anular()` nunca borra
  historial, EC-20); el bug era que `PlantillasDelTorneo.tsx` era la única
  de 3 pantallas hermanas que no filtraba `GET /plantillas` a
  `estado === "Activo"` antes de agrupar por equipo — mismo patrón ya
  usado en `ModalGestionarPlantilla.tsx`/`EquiposDelTorneo.tsx`. Fix
  100% client-side, sin tocar el endpoint (los 2 consumidores que sí
  necesitan el historial completo — Traspasos, Perfil de Jugador — no se
  tocaron).

## Centralización operativa en Control de Mesa + fix del fixture — implementado

Plan en `docs/plans/control-mesa-centralizacion-fixture-plan.md`,
implementado el 2026-09-04 (339 tests backend + 213 frontend, todos
verdes; `tsc --noEmit`/`oxlint` en verde).

- ~~`GET /partidos` sin RBAC en Control de Mesa — mezclaba TODOS los
  torneos del sistema para cualquier TorneoAdmin~~ — **hecho.**
  `GET /partidos?solo_mios=true` (mismo mecanismo que `/torneos?solo_mios=true`,
  E1) — `PartidoRepository.list` override calca el patrón de
  `TorneoRepository.list`. Selector de torneo en `ControlDeMesaPage`
  (visible solo con 2+ torneos) + nombre del torneo por fila.
- ~~Sin ingreso manual de resultado — solo cronómetro en vivo~~ —
  **hecho.** `POST /partidos/{id}/resultado-directo` (`PartidoService.
  registrar_resultado_directo`, nuevo): orquesta Hito Inicio_Partido + N
  eventos + Hito Fin_Partido en una transacción atómica (sin commits
  intermedios — mismo criterio que `InscripcionTorneoService.
  _crear_individual`), reusando las mismas tablas/triggers que el
  cronómetro en vivo. `ModalResultadoDirecto` en Control de Mesa.
- ~~`PartidosDelTorneo.tsx` permitía crear/editar/cancelar/asignar
  árbitro/walkover — superficie operativa duplicada con Control de
  Mesa~~ — **hecho.** Ahora es de solo lectura para la operación del
  partido: se quitaron "editar" (fecha/fase/grupo/estado libre) y
  "Walkover" (mudado a Control de Mesa, junto a "Cargar resultado
  directo" — ambos cierran el partido sin cronómetro en vivo). Se
  mantienen "+ Nuevo" (crear partido) y "Asignar árbitro" — son
  planificación de calendario, no gestión del partido en curso (Taste
  Decision resuelta por el usuario, Sección 16 del plan).
- ~~Bug "?" en el fixture: `PartidosDelTorneo.tsx` era la 8va pantalla que
  le faltaba el parche del Bug 2 (ver sección de arriba)~~ — **hecho.**
  `useNombrePorIdConFaltantes` aplicado ahí (lista + selector de equipos
  al crear).
- ~~`/partido/:id/en-vivo` solo mostraba eventos, sin alineaciones, y su
  copy/ruta eran específicamente "en vivo"~~ — **hecho.** Generalizada a
  "Detalle del Partido": sirve para cualquier estado del partido, con
  una sección nueva de Alineaciones (titulares/suplentes por equipo,
  reusa `GET /partidos/{id}/convocados` + `GET /estadisticas/equipos/{id}/plantilla`,
  ambos ya públicos). Nueva ruta `/partidos/:partidoId` — la vieja
  `/partido/:id/en-vivo` se mantiene tal cual (Dashboard.tsx la linkea).
- **Migrar `DetalleEquipo.tsx`/`ModalIndividual` al hook de resolución de
  nombres** — no hecho, ya registrado como mejora no pedida (ver sección
  de arriba); sigue fuera del blast radius de este plan.
- **Paginación real con cursor en `/equipos`/`/jugadores` (3B-9)** — no
  hecho, sigue con su propio ciclo; el fix del fixture es el mismo parche
  de síntoma que las otras 7 pantallas, no el techo real de 200 filas.

## Deferido desde el plan de Modo en Vivo, Sustituciones y Cierre (`docs/plans/modo-vivo-sustituciones-cierre-plan.md`)

Plan revisado vía `/autoplan` el 2026-09-08 (CEO + Design + Eng, `[subagent-only]`,
Codex no disponible en esta máquina). Reversión explícita de la Decisión Audit #12
del plan anterior (tope de titulares) — documentada como reversión, no como bugfix.
Corrección crítica en Fase 3 (Eng): el mecanismo de "deshacer" de Fin de Partido
forzado pasó de commit diferido 100% cliente a soft-commit server-side + endpoint
compensatorio, porque el diseño original no protegía contra el escenario que decía
proteger (dispositivo del operador cae durante la ventana de 5s).

- **Badge visual de sanción pendiente en convocatoria** — depende de un concepto de
  "sanciones" inexistente en el modelo hoy (`JUGADOR_PERFIL_DISCIPLINA` no tiene
  estado de suspensión). Efort: S una vez que exista el modelo de sanciones.
- **Exportar resultado directo cargado a texto plano (para pegar en WhatsApp del
  torneo)** — fuera de blast radius de gestión de partido, es comunicación externa.
  Efort: S.
- **Motor de reglamento de torneo genérico (`ReglamentoTorneo`)** — unificaría
  mínimo/máximo de titulares, tope de cambios, tiempo extra/prórroga en un solo
  objeto de dominio en vez de columnas sueltas en `TORNEO`. Refactor estructural,
  Effort: L, excede 1 día CC — se revisita si aparece un tercer campo de
  reglamento además de `minimo_jugadores_para_iniciar`/`maximo_titulares_permitido`/
  `permite_cambios_ilimitados`.
- **Mecanismo genérico de "operación reversible con ventana de gracia"** — el
  patrón construido para `deshacer-cierre-forzado` (insertar de inmediato + endpoint
  compensatorio con ventana server-side) es candidato a generalizarse si aparece una
  segunda necesidad similar (ej. deshacer un walkover marcado por error). No se
  construye ahora (un solo caso de uso no justifica la abstracción); depende de
  `backend/app/services/hito_partido.py::deshacer_forzado` como precedente.
- **`PartidoService.marcar_walkover` sigue escribiendo `Estado` directamente**, sin
  pasar por Hito — excepción reconocida (tiene sus propios guards), fuera de
  alcance de este plan. Si en el futuro se decide que TODA escritura de `Estado`
  debe pasar por Hito, este método necesita revisarse.

### Estado de implementación (2026-09-09)

Implementado y con tests pasando (404 backend + 241 frontend, suite completa
verde) — T1/T2/T3/T4/T5/T6/T7/T8/T14/T15/T16/T17/T18/T21/T22/T25 del artefacto de
tareas (`~/.gstack/projects/Score-App/tasks-*-2026090[89]*.jsonl`):

- Bloque 0: `PartidoUpdate` sin `estado` + `extra="forbid"` (422 real, no
  `extra=ignore` silencioso).
- Área 1: tope de titulares — guard en `ConvocadoAPartidoService` (Python) +
  trigger `fn_validar_tope_titulares` (DB, con lock de fila) + rechazo
  client-side en `AlineacionEditor`/`alineacion.ts` (mensaje inline, sin toast
  porque el repo no tiene ese componente — mismo criterio que
  `ModalPerfilJugador.tsx`).
- Área 2: `EventoPartidoRepository.list` ordena `(minuto, id)`; `MesaPanel`
  dejó de reordenar client-side (solo invierte para mostrar lo más reciente
  arriba).
- Área 3: minuto en vivo calculado server-side
  (`app/services/minuto_partido.py`, ignora lo que mande el cliente) +
  `Cronometro` expone `onMinutoActual` + `ModalSustitucion.tsx` (nuevo,
  contextual desde una sección "Alineación en vivo" agregada a `MesaPanel`) +
  reglas de cambio (`Torneo.permite_cambios_ilimitados`/
  `maximo_cambios_por_equipo`) + contador "cambios usados X/Y".
- Área 4: `Fin_Partido(forzado=true, motivo_cierre, motivo_cierre_detalle)`
  reusa `POST /partidos/{id}/hitos`; `POST /partidos/{id}/deshacer-cierre-forzado`
  (`HitoPartidoService.deshacer_fin_forzado`) con ventana server-side de 5s
  (`VENTANA_DESHACER_SEGUNDOS`), banner de countdown derivado 100% de
  `GET /cronometro` (sobrevive un F5 sin estado propio del cliente). Incluye
  el caso no cubierto por la Fase 1/2 del `/autoplan`: un torneo `Corrido`
  sigue exigiendo `ganador_corrido_id` incluso en un cierre forzado
  (`fn_validar_ganador_corrido` no hace excepciones) — el service lo valida
  antes de insertar el Hito, mismo criterio que el Fin_Partido normal.

Genuinamente pendiente (no implementado en esta pasada):

- **T23/T24 — tests de concurrencia real** (2 transacciones DB simultáneas: tope
  de titulares y doble `Fin_Partido`). Los tests nuevos
  (`test_tope_titulares.py`, `test_fin_forzado.py`) cubren el caso secuencial y
  la defensa en profundidad a nivel DB (INSERT directo que dispara el trigger/
  índice único), pero no un escenario de 2 sesiones genuinamente paralelas —
  requiere infraestructura de test que este repo no tiene todavía (2 engines/
  conexiones abiertas a la vez contra la misma fila).
- **`ModalSustitucion`/alineación en vivo con reemplazo del cálculo heurístico
  de `MesaPanel.tsx`** — el modal nuevo reusa `calcularElegibilidadCambios`
  (extraído a `eventos.ts` para no duplicarlo), pero el formulario de Cambio
  YA EXISTENTE dentro de `CargaEvento` no se retiró (Sección 5 del plan pedía
  "eliminar y reemplazar, no duplicar" la heurística de elegibilidad — quedó
  compartida, no duplicada, pero el segundo CAMINO de UI para cargar un Cambio
  sigue existiendo en paralelo al modal nuevo). Retirarlo requiere revisar
  `MesaPanel.test.tsx` con más cuidado del que alcanzó esta pasada.
- **Wireframe de 3 zonas (Design Fase 2, Pass 1) literal** — el panel en vivo
  no se reorganizó en 3 franjas fijas (primaria/secundaria/terciaria) como el
  ASCII del plan; el botón de cierre forzado y la alineación en vivo se
  agregaron como secciones nuevas de `MesaPanel`/`Cronometro` sin rehacer el
  layout general de la página.

## Deferido desde el plan de Goles por Marcador + Quick Action Bar + Timeline
(`docs/plans/goles-por-marcador-slots-plan.md`)

- **Fusión completa de Modo en Vivo + Resultado Directo en un único motor de
  eventos parametrizado por modo** — el reframe de mayor apalancamiento que
  señaló la voz externa (Eng subagent) de ese plan: hoy son 2 máquinas de
  estado de `Partido` genuinamente distintas (`'Programado'` con persistencia
  atómica al final vs. `'En curso'` con persistencia inmediata por evento).
  Fusionarlas de verdad excede blast radius de ese plan (>1 día CC, introduce
  un concepto de dominio nuevo — "modo de carga"). Candidata fuerte para una
  futura sesión, idealmente con datos reales de qué fracción de partidos
  cargados como "resultado directo" tienen convocatoria guardada (esa métrica
  no existe hoy y hubiera evitado tener que asumir el caso feliz/degradado a
  ciegas).
- **Restaurar un batch local de Resultado Directo no guardado desde
  `localStorage`** tras un refresh accidental de la página — hoy el estado
  vive 100% en memoria del componente (`eventos[]`), se pierde con cualquier
  cierre/refresh de pestaña antes de guardar. Requiere diseño de persistencia
  local no pedido por ese plan.
- **`/design-consultation` para un DESIGN.md formal del proyecto** — deuda de
  diseño conocida y recomendada por 5 planes consecutivos de este repo
  (incluido este), nunca ejecutada. No específica de ninguna feature puntual.

## Deferido desde el plan de Reactividad en Control de Mesa + Playoffs en Estadísticas
(`docs/plans/control-mesa-reactividad-playoffs-plan.md`) — implementado
2026-09-14 (T1-T11 del plan; T12 abajo queda pendiente)

- **Row-locking en `EventoPartidoService.create` (camino en vivo) para 2
  tarjetas simultáneas del mismo jugador** — gap de concurrencia preexistente
  (no introducido por este plan): `registrar_resultado_directo` ya usa
  `get_or_404_bloqueado` para el mismo problema, pero el alta de evento en
  vivo no tiene un lock de fila equivalente. Race extrema (2 amarillas para
  el mismo jugador llegando al servidor casi al mismo tiempo, antes de que
  el dedup de `reglas_tarjetas.procesar_doble_amarilla` corra) podría
  producir 2 rojas automáticas. Cherry-pick evaluado y diferido en la Fase 1
  de ese plan (0D, cherry-pick #2) — fuera del blast radius directo del
  pedido, riesgo bajo, sin bloquear el resto del plan.
- **Sanciones disciplinarias que acumulan tarjetas ENTRE partidos** (ej. 3
  amarillas en el torneo = suspensión para el próximo) — explícitamente
  fuera de alcance de ese plan (el pedido pedía "en el mismo partido", no
  acumulación por torneo). Candidato a un plan propio si surge demanda real
  de un torneo que lo necesite.

## Deferido desde el plan de Portal Público: Navbar de Disciplinas + Feed
de Partidos del Día (`docs/plans/portal-publico-feed-partidos-plan.md`) —
implementado 2026-09-15 (R1+R2+R3 completos)

- **Auto-refresh en vivo del feed** (polling o WebSocket) — C14. El feed
  no se actualiza solo; el rótulo "Actualizado HH:MM" + botón "Recargar"
  (D9) es la mitigación barata que sí entró.
- **Uploader de imágenes para escudos/logos** — C14. `Logo_URL` acepta una
  URL de texto (mismo criterio que `JUGADORES.Foto_URL`), sin subida de
  archivos.
- **Preview de Open Graph POR torneo/partido** (exige SSR o un endpoint
  de prerender) — C14/C4. Los meta tags OG son estáticos (mismo preview
  "Score-App" para todo link); el botón "Compartir" es el que entrega el
  valor real de distribución.
- **Query params `fecha`/`disciplina_id` en `GET /api/v1/partidos`** —
  C5b, hueco #5 del plan original. Ningún consumidor de esta entrega los
  necesita (el feed usa su propio endpoint, `GET /partidos/feed`);
  agregarlos ahora sería el segundo camino paralelo que el plan marcó
  como riesgo. Diferido hasta que aparezca un consumidor real.
- **`tz` como parámetro del feed** (F8) — la cabecera rotula la fecha
  explícita del servidor (C15), que alcanza para el wedge de una liga
  local, pero un consumidor en otro huso horario no tiene salida
  programática. Reentra si aparece un torneo fuera del huso del servidor.
- **Flag para forzar la barra de deportes con una sola disciplina**
  (F19a) — hoy la barra se oculta con ≤1 disciplina con contenido (C8,
  deliberado: "27 pills muertas son peores que ninguna barra"). Reentra
  si hace falta demostrar el requerimiento #2 (navbar de disciplinas)
  antes de tener una segunda disciplina activa con partidos.
- **Envelope de error con código estable** (`{detail, codigo, sugerencia}`,
  F9) — se simplificó: los 404 nuevos (torneo despublicado, disciplina
  inexistente) reusan el `NotFoundError` genérico ya existente en el
  repo, que de por sí no filtra si un torneo despublicado existe (la
  propiedad de seguridad que F9 pedía). No se construyó el envelope
  `codigo`/`sugerencia` nuevo por no tener otro consumidor en el repo.
- **Selector de fecha como tira de fechas reales** (D3) — se implementó
  como flechas día anterior/siguiente sobre `fecha_efectiva` en vez de una
  tira scrolleable de fechas; cumple la garantía real de D3 (la fecha
  seleccionada nunca miente) con menos superficie.
- **Minuto en vivo en la fila del feed** (D2 lo mencionaba) — el feed
  muestra un indicador "EN VIVO" en vez del minuto real: pedirlo exigiría
  una consulta de cronómetro por fila (N+1), el mismo costo que
  `preflight-inicio` ya evita a propósito en el resto del repo.

## Palmarés por grupo de torneos (aparcado — /autoplan 2026-09-16)

- **Palmarés a través de las ediciones de un `TORNEO_GRUPO`** — agregar los
  podios de cada `numero_edicion` en una vista de historial. `TORNEO.torneo_grupo_id`
  + `numero_edicion` ya modelan las ediciones (`torneos-admin-plan.md`), así
  que una vez que existan las columnas de podio de
  `cierre-fase-regular-llaves-playoffs-plan.md` esto es una vista más una
  página. **Por qué:** un campeón que se acumula vale más que uno que se
  resetea cada edición — es el gancho de retención más barato que este modelo
  de datos permite. **Contra:** no hay consumidor todavía y depende de que
  primero exista la página pública de campeón (UC2 de ese plan, sin resolver).
  **Esfuerzo:** M → con CC, S. **Prioridad:** P3. **Bloqueado por:** las
  columnas de podio de ese plan, y UC2.
