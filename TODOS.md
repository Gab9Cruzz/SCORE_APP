# TODOS

## Roles y 3 módulos (Admin General / Torneo Admin / Árbitro)

Plan fase por fase en `docs/plans/roles-3-modulos-plan.md`. Vista al ingresar
para el frontend actual: confirmada sin cambios (Admin y Árbitro comparten
`/dashboard` hasta la Fase 2/3). Empezar por la Fase 1 (backend: roles +
asignación árbitro↔partido) cuando se retome — bloquea a las fases 2-4.

## Frontend — deferido desde el design doc de Dashboard/Control de Mesa/Partido en Vivo

- Qué pasa cuando el árbitro pierde conectividad a mitad de un partido en
  Control de Mesa (offline-first, reintentos, cola local). No definido —
  candidato para `/plan-eng-review` cuando se retome esta área.
- El modelo de datos no distingue titular/suplente. El flujo de Cambio usa
  toda la plantilla vigente como candidatos a entrar/salir (ver limitación
  documentada en `frontend/README.md`). Si se vuelve un problema real en uso,
  evaluar agregar el concepto de "convocados a este partido" en el backend.

## Deferido desde el plan de Equipos y Jugadores (`docs/plans/equipos-jugadores-plan.md`)

- Desactivación de una persona (`JUGADORES.Estado → Inactivo`) que tiene
  perfiles de disciplina o membresías de equipo activas. No definido qué pasa
  con esas membresías (¿se fuerza cierre? ¿se anonimiza?) — es una decisión
  de producto, no solo técnica. Candidato para `/plan-eng-review` cuando se
  retome.
- Límite de tamaño de plantilla para disciplinas de equipo (Fútbol). El plan
  sí limita pareja/individual vía `Modalidad.Tamano_Equipo`, pero no pone
  techo a un roster de fútbol.
- Notificación por correo al jugador cuando es traspasado o pasa a jugador
  libre. El campo `Correo_Electronico` se captura en este módulo pero
  enviarlo es un módulo de notificaciones aparte.
- Importación masiva desde CSV/Excel para el registro por lote. El plan
  asume formulario multi-fila en la UI; si se necesita carga de archivo, es
  una extensión sobre el mismo endpoint de validación.

## Deferido desde el plan de Administración de Torneos (`docs/plans/torneos-admin-plan.md`)

- Vista consolidada de estadísticas cruzando **todas las ediciones** de un
  mismo `TORNEO_GRUPO` (ej. goleador histórico de "Liga Relámpago" sumando
  Edición 1 + 2). El selector de edición de ese plan solo cambia de
  contexto, no fusiona números — mezclar jugadores que cambiaron de equipo
  entre ediciones es una decisión de producto propia.
- Clonar la plantilla de una edición a la siguiente al crear una edición
  nueva (fichajes que se repiten de temporada a temporada). No pedido;
  cada edición nace con roster vacío.
- Archivar/eliminar un `TORNEO_GRUPO` completo con todas sus ediciones.
- Traspasos entre ediciones distintas del mismo grupo (`TRASPASOS` asume
  origen/destino dentro del mismo torneo; mover a un jugador a otra
  edición sería un alta nueva, no un traspaso).
- Filtro `?torneo_id=` real en `/plantillas`, `/traspasos`, `/partidos`
  (hoy devuelven el sistema completo sin filtrar) — es trabajo de
  implementación necesario para que el dashboard scoped por torneo
  muestre solo lo de ese torneo, no un nice-to-have.

## Deferido desde el `/review` de equipos-jugadores-plan.md (Fase 3)

- **Cupo de modalidad (EC-6) sin lock.** `RegistroLoteService._validar_lote`
  calcula `cupo_restante` leyendo el conteo de activos una sola vez, sin
  `SELECT ... FOR UPDATE` ni advisory lock — dos `/confirmar` verdaderamente
  simultáneos contra la misma inscripción podrían hacer que un roster de
  modalidad "Dobles" (tope 2) termine con 3 jugadores. Requiere el mismo
  patrón de `pg_advisory_xact_lock` que ya se agregó para la exclusividad
  por torneo (`JugadorEquipoRepository.lock_exclusividad_torneo`), pero
  keyeado por `inscripcion_torneo_id` en vez de `(perfil, torneo)`.
- **Migración `08_migracion_equipos_jugadores.sql`, Parte E, sin rastro de
  auditoría.** Cuando una fila vieja de `JUGADOR_EQUIPO` tiene más de una
  `INSCRIPCIONES_TORNEO` candidata (mismo equipo en torneos solapados), el
  script elige la más antigua y solo deja un `RAISE WARNING` con un conteo
  — no los IDs de las filas ambiguas — y dos sentencias después dropea
  `JUGADOR_ID`/`EQUIPO_ID`, la única fuente que permitiría auditar/corregir
  eso a mano. Ya corrió una vez contra `torneos_mvp` con backup previo, así
  que el riesgo pasado está mitigado; si el script se vuelve a correr contra
  otra base con datos reales, conviene primero volcar los IDs ambiguos a una
  tabla de auditoría temporal (o abortar con `RAISE EXCEPTION` en vez de
  `WARNING` cuando `v_ambiguos > 0`) antes del `DROP COLUMN`.

## Deferido desde el plan de Catálogo Maestro de Disciplinas (`docs/plans/ediciones-catalogo-disciplinas-plan.md`)

- **Registro de resultados/estadísticas para disciplinas de marca y tiempo**
  (Atletismo, Natación, Ciclismo), **combate** (MMA, Boxeo, Judo, Taekwondo,
  Karate) o **mente** (Ajedrez). `PARTIDOS`/`EVENTOS_PARTIDO` asumen siempre
  dos equipos y goles — un tiempo de maratón o un resultado de combate no
  encajan ahí. Merece su propio diseño (¿"partido" = combate/carrera? ¿cómo
  se registra un tiempo o un ganador por sumisión?).
- **Categorías de peso/cinturón reales de una federación** para las
  disciplinas de Combate. El catálogo precarga 3 categorías genéricas por
  disciplina ("Peso Ligero/Medio/Pesado") como placeholder editable solo
  por migración SQL — no la tabla oficial de cada federación (varía por
  región/edad/género).
- **Límite superior de inscripciones por torneo** (cuántos Equipos/Jugadores
  caben en un bracket). No fue pedido en ese plan.
- **eSports — brackets y estadísticas.** El catálogo cubre inscripción
  (equipos de 5, parejas, 1v1), no brackets de doble eliminación ni
  integración con APIs de las plataformas (Riot, Steam) — es un módulo de
  "sistema de brackets" aparte.
- **Ajustar el catálogo maestro fuera de una migración SQL manual** (EC-32).
  Bajo la Decisión C1 (catálogo inmutable, solo toggle de Estado) un admin
  no tiene forma de agregar/corregir una disciplina o modalidad desde la UI
  — es la consecuencia esperada de "inmutable", no un bug, pero si en el
  futuro hace falta ajustar el catálogo con frecuencia, evaluar la
  Alternativa C3 del plan (ocultar el CRUD detrás de un rol "Superadmin" en
  vez de eliminarlo).

## Deferido desde el plan de Equipos con Disciplina + Navegación (`docs/plans/equipos-disciplina-navegacion-plan.md`)

Implementado con las opciones recomendadas: **A1** (plantilla derivada, sin
tabla de roster permanente), **B1** (Categoría = Modalidad), **C2**
(backfill + `NOT NULL`), **EC-44** literal (solo se valida la Disciplina al
inscribir, no la Modalidad) y las **4 mejoras** propuestas. Lo que quedó
afuera:

- **Tabla `EQUIPO_MIEMBRO` / roster permanente del equipo** (Alternativa A2).
  Hoy "la plantilla del equipo" es un dato derivado: perfiles distintos con
  membresía Activo en cualquiera de sus inscripciones. Un equipo creado
  desde `/torneo-admin/equipos` no tiene dónde colgar jugadores hasta que se
  inscribe a un torneo — la UI lo dice y ofrece el camino, pero no lo
  elimina. Si el equipo tiene que existir como entidad con socios estables
  (escudo, sede, palmarés, staff), es un plan aparte: dos fuentes de verdad
  de "quién es del equipo" que `fn_validar_jugador_partido` y
  `fn_validar_exclusividad_torneo` hoy no saben conciliar.
- **Catálogo de categorías etarias/de género** (`Sub-13`, `Libre`,
  `Femenino`, `Mixto`...) — Alternativa B2. La columna "Categoría" de la
  grilla muestra la Modalidad. Si "Categoría" tiene que significar la edad o
  el género, es un módulo propio: tabla, seed, UI de catálogo y reglas de
  elegibilidad (¿un Sub-15 puede jugar un torneo Libre?).
- **Iconos SVG propios por disciplina.** `iconosDisciplina.ts` mapea las 28
  disciplinas a emoji, con la inicial como fallback. Está en su propio
  módulo justamente para que cambiarlos sea reemplazar un archivo. 28 SVGs
  son trabajo de diseño.
- **Paginación real con cursor en `/equipos`.** El plan subió el techo y lo
  hizo VISIBLE (filtros server-side + banner "mostrando los primeros 200"),
  que era el bug: hasta ahora la fila 201 no existía para el frontend, sin
  aviso. El cursor sigue pendiente, y con él la búsqueda por nombre
  server-side (`?nombre=`) — hoy el texto se filtra en memoria sobre lo que
  la página ya trajo.
- **Filtro por Estado del torneo en la barra de disciplinas.** El pedido
  eran Disciplinas y Modalidades; un tercer eje es alcance nuevo.
- **Persistir el filtro elegido en la URL.** `TorneosAdminPage` LEE
  `?disciplina_id=` al entrar (para que "agregar plantilla" desde la grilla
  de Equipos caiga filtrado), pero no escribe de vuelta el filtro que el
  admin elige con los chips — un link compartible del listado filtrado es
  nice-to-have, no pedido.
- **`UNIQUE (Nombre, Disciplina_ID)` en `EQUIPOS`** (EC-43). Dos equipos con
  el mismo nombre en la misma disciplina siguen permitidos: hoy tampoco hay
  UNIQUE sobre `Nombre`, y agregarlo rompería datos existentes sin que nadie
  lo haya pedido.
- **`Equipo A` (id=271) se borró al migrar `torneos_mvp`.** Era el único
  equipo sin disciplina inferible (creado el 2026-08-27 probando el
  formulario viejo, sin inscripciones ni partidos). La migración frenó como
  está diseñada y se resolvió borrándolo. Si hacía falta, está en
  `database/backups/torneos_mvp_pre_equipos_disciplina_20260827_211414.dump`.
- **Las inscripciones cruzadas PREEXISTENTES no se cancelan solas.** Si en
  `torneos_mvp` hay un equipo inscrito en un torneo de otra disciplina (los
  "ambiguos" que reporta la PARTE D de `13_migracion_equipos_disciplina.sql`),
  la migración las deja donde están y la PARTE G las cuenta en un `NOTICE`.
  La API ya no permite crear nuevas; limpiarlas es una decisión de datos, no
  de esquema.

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
  lo muestran** — es una línea por página cuando haga falta.

## Ideas para cuando se retome (no bloquean nada)

- **Las otras grillas no avisan cuando truncan.** `useResourceCrud` ya
  expone `truncado`; falta usarlo en Jugadores, Usuarios y los listados
  del dashboard de torneo. Barato, y evita el mismo fallo silencioso que
  Equipos ya no tiene.
- **Los tipos de fila del frontend se declaran a mano en cada componente**
  (`EquipoRow` existe en 3 archivos con formas distintas, `ModalidadRow`
  en 4). `schema.d.ts` ya tiene la forma real generada del backend:
  centralizar alias del estilo
  `type Equipo = components["schemas"]["EquipoOut"]` en un solo módulo
  haría que un cambio de contrato se note en `tsc` en vez de pasar
  desapercibido en un componente que declaró el campo de más.
- **No hay CI.** `verificar.ps1` corre todo local; moverlo a un workflow de
  GitHub Actions es directo (necesita un servicio de PostgreSQL) y sacaría
  el "me acordé de correrlo" de la ecuación.
- **La demo `10_*.sql` sigue usando el patrón viejo para Copa Raíces**
  (Tenis Individual): crea un EQUIPOS fantasma llamado "Micky Fernández" e
  inscribe por `Equipo_ID`. Desde `ediciones-catalogo-disciplinas-plan.md`
  (Decisión B1) una inscripción individual va por `Jugador_Perfil_ID`
  directo, así que la pestaña "Jugadores inscritos" de ese torneo muestra
  "—" para el único participante. Los datos son válidos (no violan ninguna
  constraint), pero la demo muestra peor de lo que la app hace hoy.

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
- **No se registra el logout.** El token es JWT sin estado del lado del
  servidor, así que "cerró sesión" no es un evento que la API vea. Para
  tenerlo haría falta una lista de tokens revocados, que es otro diseño.
- **Nada alerta sobre N fallos seguidos.** Hoy el dato está y hay que ir a
  mirarlo. Un bloqueo temporal por intentos fallidos (rate limiting) sería
  el paso siguiente natural, y ahora tiene de dónde leer.
