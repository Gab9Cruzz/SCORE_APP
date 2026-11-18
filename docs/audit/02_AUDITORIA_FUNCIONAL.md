# 02 — Auditoría funcional

Fase II: cada módulo visto desde el usuario y desde las reglas de negocio.

> **Nivel de evidencia.** El backend no pudo ejecutarse (sin PostgreSQL en la máquina de auditoría), así que los hallazgos de este documento son **confirmados por análisis estático** salvo que se indique otra cosa: se deducen de forma directa del código citado, pero ninguno se reprodujo contra una base real. Antes de corregir cada uno conviene escribir primero la prueba que lo reproduce (así está planteado en el backlog).

## 1. Matriz por módulo

Estados: Correcto · Parcial · Incorrecto · No implementado · No verificable.

### 1.1 Autenticación, usuarios y permisos

| Módulo | Funcionalidad | Estado | Problema | Impacto | Recomendación |
|---|---|---|---|---|---|
| Auth | Login con JWT, bitácora de accesos | Correcto | — | — | — |
| Auth | Límite de intentos fallidos | Parcial | Se puede eludir variando el nombre de usuario o una cabecera (`SEC-01`) | Fuerza bruta sin freno | `TASK-004` |
| Auth | Cierre de sesión | Parcial | Solo borra el token en el navegador; el token sigue válido hasta expirar (decisión documentada) | Token robado útil hasta 120 min | `TASK-033` |
| Auth | Cambio de contraseña propio / recuperación | No implementado | No hay endpoint ni pantalla; solo AdminGeneral puede cambiarla (`FUN-13`) | Contraseñas iniciales que nunca se cambian | `TASK-033` |
| Usuarios | Alta, edición, baja lógica, guardas de auto-bloqueo | Correcto | — | — | — |
| Usuarios | Licencia (revocación inmediata) | Correcto | — | — | — |
| Permisos | Alcance por torneo del TorneoAdmin en escritura | Correcto | — | — | — |
| Permisos | Catálogos globales | Parcial | Cualquier TorneoAdmin modifica equipos, jugadores, eventos, disciplinas y grupos de torneo ajenos (`SEC-04`) | Un administrador puede afectar torneos de otro | `TASK-013` |
| Permisos | Árbitro limitado a su partido | Parcial | En su partido puede cambiar fecha, fase y hasta el árbitro asignado (`FUN-22`) | Cambios no previstos por un rol operativo | `TASK-021` |
| Auditoría | Registro de altas, cambios y bajas | Correcto | No cubre escrituras hechas por triggers ni por SQL directo | Informativo | — |

### 1.2 Catálogo, torneos y ediciones

| Módulo | Funcionalidad | Estado | Problema | Impacto | Recomendación |
|---|---|---|---|---|---|
| Catálogo | Disciplinas y modalidades (activar/desactivar) | Correcto | Alta de disciplinas solo por SQL (decisión documentada) | — | — |
| Catálogo | Tipos de evento | Parcial | Editables por nombre, y el marcador depende de ese nombre (`FUN-14`) | Renombrar "Gol" deja todos los marcadores en cero | `TASK-019` |
| Torneos | Crear torneo o nueva edición, fase y configuración inicial | Parcial | Cuatro `commit` separados (`FUN-18`) | Torneo a medio crear si falla un paso | `TASK-022` |
| Torneos | Editar torneo | Incorrecto | `PATCH` acepta `estado`, `disciplina_id` y `modalidad_id` sin guardas (`FUN-04`) | Cierre sin podio, baja masiva de plantillas, torneo con equipos de otra disciplina | `TASK-010` |
| Torneos | Cerrar torneo y podio | Correcto | — | — | — |
| Torneos | Reabrir torneo | Incorrecto | No restaura las plantillas que el cierre dio de baja (`FUN-01`) | Tras reabrir no se puede cargar ningún evento | `TASK-007` |
| Torneos | Publicar / despublicar | Correcto | Sub-recursos siguen visibles por ID (`SEC-07`) | Bajo | `TASK-014` |
| Torneos | Archivar grupo de torneos | Parcial | Sin control de a quién pertenece (`SEC-04`) | Un TorneoAdmin archiva torneos ajenos | `TASK-013` |
| Torneos | Modalidad individual | No implementado | Se inscriben jugadores pero no hay partidos posibles (`FUN-16`) | Módulo incompleto para deportes individuales | Decisión de producto |

### 1.3 Equipos, jugadores, inscripciones, plantillas y traspasos

| Módulo | Funcionalidad | Estado | Problema | Impacto | Recomendación |
|---|---|---|---|---|---|
| Equipos | Alta, edición, plantilla base, multimilitancia | Correcto | — | — | — |
| Equipos | Baja de equipo | Parcial | Sin comprobar inscripciones ni partidos pendientes (`FUN-21`) | Sus partidos desaparecen del portal | `TASK-016` |
| Jugadores | Alta, búsqueda, perfil por disciplina | Correcto | Búsqueda pública también por cédula (`SEC-05`) | Privacidad | `TASK-014` |
| Jugadores | Baja de jugador | Correcto | Bloquea si tiene membresías activas | — | — |
| Inscripciones | Inscribir equipo, cupo máximo, copia de plantilla base | Parcial | No valida estado del torneo ni del equipo, ni modalidad (`FUN-07`) | Inscripciones incoherentes | `TASK-016` |
| Inscripciones | Cancelar / reactivar | Incorrecto | Sin efectos sobre plantilla ni partidos; reactivar salta el cupo (`FUN-07`) | Jugadores bloqueados, cupo excedido | `TASK-016` |
| Plantillas | Alta individual | Parcial | No aplica tope de plantilla ni suspensión (`FUN-08`) | La regla vale en un camino y no en otro | `TASK-017` |
| Plantillas | Registro por lote | Correcto | — | — | — |
| Plantillas | Listado del torneo | Incorrecto | El servidor corta en 100 filas sin avisar (`FUN-05`) | Jugadores que "no aparecen" a partir de unos 7 equipos | `TASK-011` |
| Plantillas | Editar vínculo | Parcial | Permite fijar cualquier estado y fechas sin validar (`FUN-20`) | Estados incoherentes | `TASK-017` |
| Traspasos | Crear y anular con reversión real | Correcto | — | — | — |
| Traspasos | Eventos de partidos previos al traspaso | Incorrecto | La base rechaza al jugador con su equipo anterior (`FUN-02`) | No se puede completar un acta atrasada | `TASK-008` |
| Notificaciones | Correo al jugador | No implementado | Bloqueado por decisión de proveedor (documentado) | — | — |

### 1.4 Motor de formatos

| Módulo | Funcionalidad | Estado | Problema | Impacto | Recomendación |
|---|---|---|---|---|---|
| Liga | Fixture todos contra todos, ida y vuelta | Correcto | Fechas a las 00:00, una jornada por semana (`UX-08`) | Reprogramación manual, partido por partido | Mejora P3, fuera de este ciclo |
| Eliminación | Sorteo, byes, tercer puesto, ida y vuelta, mixto | Correcto | — | — | — |
| Grupos + playoffs | Sorteo de grupos, cruces, clasificados | Correcto | — | — | — |
| Sorteo | Rehacer sorteo | Parcial | Borra partidos en curso con sus eventos (`FUN-11`) | Pérdida de datos | `TASK-018` |
| Llaves | Avance automático del ganador | Parcial | No se recalcula si el resultado cambia después (`FUN-03`); partido cancelado bloquea la llave (`FUN-19`) | Cuadro incoherente | `TASK-009` |
| Desempate | Manual, penales, tiempo extra | Correcto | — | — | — |

### 1.5 Partidos y Control de Mesa

| Módulo | Funcionalidad | Estado | Problema | Impacto | Recomendación |
|---|---|---|---|---|---|
| Partidos | Programar, reprogramar, cancelar | Parcial | No se puede quitar el árbitro ni vaciar campos (`FUN-10`) | La API responde 200 sin hacer nada | `TASK-020` |
| Mesa | Lista de partidos a operar | Incorrecto | Pide 100 partidos sin filtrar estado (`FUN-06`) | Partidos pendientes invisibles en torneos medianos | `TASK-012` |
| Mesa | Convocatoria, titulares, llegadas tardías | Correcto | Carrera conocida en el tope de titulares (`BE-03`) | Bajo | `TASK-024` |
| Mesa | Cronómetro y máquina de estados | Correcto | — | — | — |
| Mesa | Goles, tarjetas, cambios en vivo | Correcto | No impide eventos de un expulsado o sustituido (`FUN-15`) | Datos inverosímiles | `TASK-017` |
| Mesa | Resultado directo (todo o nada) | Correcto | — | — | — |
| Mesa | Corregir minuto / anular evento | Parcial | En partido finalizado no recalcula consecuencias (`FUN-03`) | Llave y podio desactualizados | `TASK-009` |
| Mesa | Walkover, cierre forzado, deshacer | Correcto | — | — | — |
| Mesa | Cola offline de un evento | Correcto | Alcance reducido a propósito | — | — |

### 1.6 Estadísticas y portal público

| Módulo | Funcionalidad | Estado | Problema | Impacto | Recomendación |
|---|---|---|---|---|---|
| Estadísticas | Tabla de posiciones | Parcial | Sin equipos que aún no jugaron; ignora al ganador declarado en cronómetro corrido (`FUN-09`) | Tabla vacía al inicio; puntos mal contados | `TASK-025` |
| Estadísticas | Goleadores, resultados, próximos | Correcto | — | — | — |
| Portal | Feed por día y deporte | Correcto | Aritmética de fechas dependiente de la zona horaria (`FUN-17`) | Bajo en América; navegación rota en UTC+ | `TASK-040` |
| Portal | Detalle de torneo y partido en vivo | No verificable | No se pudo recorrer sin backend | — | `TASK-042` |
| Navegación | Enlace "Portal público" con sesión | Incorrecto | Redirige al dashboard (`FUN-12`) | Enlace que no hace nada | `TASK-040` |

## 2. Escenarios analizados

| Escenario | Qué hace el sistema | Veredicto |
|---|---|---|
| Registrar un equipo sin jugadores | Lo permite. Puede inscribirse; el partido no arranca sin el mínimo de titulares (preflight) | Correcto |
| Inscribir un equipo en un torneo | Valida disciplina, cupo con bloqueo y duplicado. No valida estado del torneo, estado del equipo ni modalidad | Parcial (`FUN-07`) |
| Inscribir dos veces el mismo equipo | 409 por restricción de unicidad, con mensaje genérico | Correcto |
| Transferir un jugador entre equipos | Una sola transacción, exclusividad con bloqueo, reversible mientras el destino no haya jugado | Correcto |
| Cargar después el acta de un partido anterior al traspaso | La base rechaza al jugador con su equipo de entonces | Incorrecto (`FUN-02`) |
| Eliminar un jugador que participa en partidos | No hay borrado físico; la baja lógica se bloquea si tiene membresías activas | Correcto |
| Registrar un resultado dos veces | Resultado directo bloquea la fila y exige `Programado`; el segundo recibe 400. Doble fin de partido: índice único | Correcto |
| Modificar un partido finalizado | El estado no es editable. Sí se pueden corregir minutos y anular eventos sin recalcular nada | Parcial (`FUN-03`) |
| Registrar estadísticas sin partido válido | Clave foránea, partido "En curso" y trigger de jugador–equipo | Correcto |
| Acceder sin permisos | 401 sin token, 403 por rol, 403 por torneo no asignado, 404 para torneo no publicado | Correcto, con las excepciones de `SEC-04` |
| Cerrar un torneo, descubrir un error y reabrirlo | El podio se limpia, pero las plantillas quedaron de baja | Incorrecto (`FUN-01`) |
| Poner un torneo en "Finalizado" desde su edición | Se acepta sin validar fase ni calcular podio | Incorrecto (`FUN-04`) |
| Dos operadores cargan la segunda amarilla a la vez | Bloqueo de fila; se genera una sola roja automática | Correcto |
| Torneo con 8 equipos de 15 jugadores | El listado de plantillas devuelve solo 100 de 120 | Incorrecto (`FUN-05`) |

## 3. Hallazgos funcionales

### FUN-01 — Reabrir un torneo no restaura las plantillas

- **Categoría:** integridad de datos / ciclo de vida. **Tipo:** Confirmado (estático). **Severidad:** Alto.
- **Ubicación:** `database/06_triggers.sql:520-537` (`fn_cerrar_torneo_libera_jugadores`), `backend/app/services/motor_formatos.py:894-920` (`reabrir_torneo`), `database/06_triggers.sql:226-241` (`fn_validar_jugador_partido`).
- **Descripción:** al pasar un torneo a `Finalizado`, un trigger pone todas sus membresías activas en `Inactivo` con `Fecha_Fin` de hoy. `reabrir_torneo` limpia el podio y devuelve el estado a `Activo`, pero no toca las membresías. La validación de eventos exige una membresía `Activo`.
- **Evidencia:** en `reabrir_torneo` no hay ninguna escritura sobre `JUGADOR_EQUIPO`; la única prueba (`backend/tests/test_cierre_torneo.py:322`) comprueba el podio y volver a cerrar.
- **Impacto:** el motivo habitual para reabrir es corregir un resultado. Tras reabrir, cargar un gol o una tarjeta falla para cualquier jugador con "El jugador no pertenecía a ese equipo en la fecha del partido". La única salida sería volver a dar de alta a mano a cada jugador con una fecha de inicio anterior al partido, y eso choca con la restricción de unicidad `(perfil, inscripción, fecha de inicio)` si se usa la fecha original.
- **Recomendación:** que el cierre no destruya información (ver `FUN-02`) o que la reapertura revierta exactamente lo que el cierre cambió. `TASK-007`.

### FUN-02 — La validez de un jugador en un partido depende de su estado actual, no de la fecha

- **Categoría:** regla de negocio. **Tipo:** Confirmado (estático). **Severidad:** Alto.
- **Ubicación:** `database/06_triggers.sql:235` y `:259` (condición `je.Estado = 'Activo'`), `backend/app/services/traspaso.py:119-120`, `backend/app/services/jugador_equipo.py:97`, `backend/app/repositories/estadisticas.py:123`.
- **Descripción:** el trigger ya compara fechas de vigencia contra la fecha del partido, pero además exige que la membresía esté `Activo` hoy. Un traspaso la deja en `Traspasado` y una baja en `Inactivo`.
- **Impacto:** el "resultado directo" existe para cargar actas de partidos ya jugados. Si entre el partido y la carga hubo un traspaso o una baja, ese jugador no puede figurar con el equipo con el que jugó, y el mensaje afirma algo falso. La misma condición está en el editor de alineaciones.
- **Recomendación:** validar solo por rango de fechas, admitiendo los estados que representan una membresía que existió (`Activo`, `Inactivo`, `Traspasado`). `TASK-008`.

### FUN-03 — Anular o corregir eventos en un partido finalizado no recalcula las consecuencias

- **Categoría:** integridad de la competición. **Tipo:** Confirmado (estático). **Severidad:** Alto.
- **Ubicación:** `backend/app/services/evento_partido.py:307-342` (`anular`, sin comprobar el estado del partido), `database/06_triggers.sql:967` (el avance en la llave solo ocurre en la transición a `Finalizado`), `backend/app/services/motor_formatos.py:962-976`.
- **Descripción:** se permite anular un evento con el partido finalizado (decisión documentada como EC-15). Si el evento era un gol decisivo, cambia el ganador, pero el equipo que ya avanzó sigue en el partido siguiente y nadie exige un desempate si ahora quedó empatado. El podio guardado no se actualiza; la bandera `diverge_de_tabla_actual` solo cubre torneos de liga.
- **Impacto:** un cuadro de eliminación puede mostrar avanzando a un equipo que, según el marcador vigente, perdió.
- **Recomendación:** impedir la anulación que cambie el resultado si el partido siguiente ya tiene actividad, y recalcular el avance cuando no la tenga. `TASK-009`.

### FUN-04 — Editar un torneo permite cambiar estado, disciplina y modalidad sin guardas

- **Categoría:** validación / transiciones de estado. **Tipo:** Confirmado (estático). **Severidad:** Alto.
- **Ubicación:** `backend/app/schemas/torneo.py:145-191` (campos `estado`, `disciplina_id`, `modalidad_id`), `backend/app/services/torneo.py:281-360`.
- **Descripción:** el servicio solo protege el cambio de formato. Enviar `{"estado": "Finalizado"}` evita `cerrar_torneo` (sin comprobar que la fase terminó y sin podio) y dispara la baja masiva de plantillas. Enviar otra `disciplina_id` deja inscritos equipos de la disciplina anterior. La regla "fecha de fin no anterior a la de inicio" solo existe al crear (`schemas/torneo.py:97-103`) y no hay restricción equivalente en la base.
- **Impacto:** estados imposibles alcanzables con una sola petición.
- **Recomendación:** sacar `estado` del `PATCH` (cierre, reapertura y baja ya tienen sus endpoints) y bloquear disciplina y modalidad cuando existan inscripciones o partidos. `TASK-010`.

### FUN-05 — Listados que se cortan en 100 filas sin avisar

- **Categoría:** función incompleta. **Tipo:** Confirmado (estático). **Severidad:** Alto.
- **Ubicación:** `backend/app/api/routes/plantillas.py:36-61`, `inscripciones.py:31-54`, `traspasos.py:33-52`, `eventos_partido.py:32-36` (ninguna declara `skip` ni `limit`); servicios con `limit: int = 100` por defecto (`services/jugador_equipo.py:25-33`, `inscripcion_torneo.py:52-66`, `traspaso.py:33-56`, `evento_partido.py:94-97`); `frontend/src/hooks/useResourceCrud.ts` (envía `limit: 200` y calcula `truncado` contra 200).
- **Descripción:** el frontend pide 200 filas, pero estas rutas no declaran el parámetro, así que FastAPI lo ignora y el servicio aplica 100. El aviso de "lista truncada" del frontend se activa al llegar a 200, cosa que nunca ocurre.
- **Impacto:** un torneo con más de 100 vínculos jugador–equipo (ocho equipos de trece jugadores) muestra una plantilla incompleta en `PlantillasDelTorneo`, `EquiposDelTorneo` y `TraspasosDelTorneo`, sin ninguna señal. Es el tipo de fallo que el usuario percibe como "se perdieron jugadores".
- **Recomendación:** declarar `skip` y `limit` en esas rutas, devolver el total y paginar en la interfaz. `TASK-011`.

### FUN-06 — Control de Mesa y "Mis partidos" no muestran partidos pendientes en torneos medianos

- **Categoría:** función incompleta. **Tipo:** Confirmado (estático). **Severidad:** Alto.
- **Ubicación:** `frontend/src/pages/control-mesa/ControlDeMesa.tsx:43-44,89`, `frontend/src/pages/arbitro/MisPartidos.tsx:23-24`, `backend/app/repositories/partido.py:80` (orden por ID).
- **Descripción:** la pantalla pide los primeros 100 partidos por ID, de cualquier estado, y filtra en el navegador los `Programado` y `En curso`.
- **Impacto:** una liga de 12 equipos a ida y vuelta genera 132 partidos. Cuando los 100 primeros estén finalizados, la lista de la mesa aparece vacía aunque queden 32 por jugar.
- **Recomendación:** filtrar por estado en el servidor, ordenar por fecha y paginar. `TASK-012`.

### FUN-07 — Inscripciones: cancelar y reactivar sin guardas ni efectos

- **Categoría:** regla de negocio. **Tipo:** Confirmado (estático). **Severidad:** Medio.
- **Ubicación:** `backend/app/services/inscripcion_torneo.py:294-295` (`update` sin validación), `:74-87` y `:107` (cupo solo en el alta), `:110-117` (solo compara disciplina).
- **Descripción y efectos:** (a) cancelar no toca la plantilla, así que los jugadores siguen "activos en este torneo" y no pueden pasar a otro equipo; (b) cancelar no revisa partidos pendientes; (c) reactivar con un `PATCH` no vuelve a comprobar el cupo; (d) al inscribir no se mira si el torneo está finalizado o inactivo, si el equipo está inactivo ni si su modalidad coincide.
- **Recomendación:** transiciones explícitas con sus reglas. `TASK-016`.

### FUN-08 — El tope de plantilla solo se aplica en el registro por lote

- **Tipo:** Confirmado (estático). **Severidad:** Medio.
- **Ubicación:** regla en `backend/app/services/registro_lote.py:25-37,202-211,294-316`; ausente en `services/jugador_equipo.py:63-90` (alta individual), `services/traspaso.py:139-146` y `services/inscripcion_torneo.py:183-231` (copia de plantilla base). El alta individual tampoco comprueba suspensión del perfil, estado del jugador ni que el perfil sea de la disciplina del torneo.
- **Impacto:** el mismo límite se cumple o no según la pantalla usada.
- **Recomendación:** una única función de "alta en plantilla" usada por los cuatro caminos. `TASK-017`.

### FUN-09 — Tabla de posiciones incompleta en dos casos

- **Tipo:** Confirmado (estático). **Severidad:** Medio.
- **Ubicación:** `database/04_views.sql:289-350` (`vw_tabla_posiciones`), `:176-239` (`vw_resultados_partidos`).
- **Descripción:** (a) la tabla parte de los partidos finalizados, así que un equipo que no jugó no aparece: al empezar el torneo la tabla está vacía; (b) la vista cuenta goles y no conoce `Ganador_Corrido_ID`: en torneos con cronómetro corrido, donde el ganador se declara, un partido sin goles cargados cuenta como empate para ambos.
- **Recomendación:** partir de los equipos inscritos (o del grupo) y unir resultados; usar el ganador declarado cuando el torneo es de cronómetro corrido. `TASK-025`.

### FUN-10 — No se puede vaciar un campo por `PATCH`

- **Tipo:** Confirmado (estático). **Severidad:** Medio.
- **Ubicación:** `backend/app/repositories/base.py:77-79` (`if valor is not None`).
- **Descripción:** un `null` explícito se descarta. No se puede quitar el árbitro de un partido, ni borrar `grupo`, `jornada`, `foto_url`, `logo_url`, `dorsal` o `motivo`. El propio código lo reconoce y lo resuelve a mano para tres campos de torneo (`services/torneo.py:334-344`).
- **Impacto:** la API devuelve 200 y el dato no cambia.
- **Recomendación:** distinguir "ausente" de "nulo" con `exclude_unset` en todos los servicios. `TASK-020`.

### FUN-11 — Rehacer el sorteo puede borrar partidos en curso

- **Tipo:** Confirmado (estático). **Severidad:** Medio.
- **Ubicación:** `backend/app/services/motor_formatos.py:159-178`.
- **Descripción:** la guarda solo rechaza si hay algún partido `Finalizado`. Un partido `En curso` con goles, hitos y convocatoria se borra físicamente, y las claves foráneas en cascada se llevan sus eventos.
- **Recomendación:** rechazar si algún partido tiene hitos o eventos. `TASK-018`.

### FUN-12 — El enlace "Portal público" no funciona con sesión iniciada

- **Tipo:** Confirmado (estático). **Severidad:** Medio.
- **Ubicación:** `frontend/src/components/NavBar.tsx:50`, `frontend/src/App.tsx:56`.
- **Descripción:** el enlace apunta a `/`, y `/` redirige a `/dashboard` cuando hay sesión. El comentario del propio `NavBar` explica que el enlace se añadió para que un administrador pudiera ver el feed; la ruta lo impide. La prueba existente solo verifica que el enlace esté en pantalla (`App.routing.test.tsx:173`).
- **Recomendación:** dar al feed una ruta propia. `TASK-040`.

### FUN-13 — Sin cambio de contraseña propio ni recuperación

- **Tipo:** Confirmado (estático). **Severidad:** Medio.
- **Ubicación:** `backend/app/api/routes/auth.py` (solo `login` y `me`), `routes/usuarios.py:69-80`.
- **Impacto:** quien recibe una contraseña inicial no puede cambiarla; el administrador creado al arrancar conserva la suya salvo que se cambie a sí mismo desde la pantalla de usuarios.
- **Recomendación:** `POST /auth/cambiar-password` y su pantalla. `TASK-033`.

### FUN-14 — El marcador depende del nombre de los tipos de evento, que es editable

- **Tipo:** Confirmado (estático). **Severidad:** Medio.
- **Ubicación:** `database/04_views.sql:18-44` (`ev.Nombre IN ('Gol', 'Autogol')`), `database/06_triggers.sql:243`, `backend/app/services/evento_partido.py:117-119,277,328`, `backend/app/api/routes/eventos.py:27-41`, `backend/app/schemas/evento.py:18-21`, `database/02_constraints.sql` (tabla `EVENTOS` sin `UNIQUE (Nombre)`).
- **Descripción:** goles, tarjetas y cambios se reconocen por texto. El catálogo permite renombrar, dar de baja o duplicar esos tipos a cualquier TorneoAdmin.
- **Impacto:** renombrar "Gol" a "Gol ⚽" pone en cero el marcador de todos los partidos de todos los torneos, sin error.
- **Recomendación:** marcar los tipos de sistema como no editables y añadir unicidad. `TASK-019`.

### Hallazgos de severidad baja

| ID | Tipo | Hallazgo | Evidencia | Tarea |
|---|---|---|---|---|
| FUN-15 | Confirmado (estático) | No hay regla que impida registrar eventos de un jugador expulsado o ya sustituido | `services/evento_partido.py:172-218`, `services/reglas_cambio.py` (solo valida cambios) | `TASK-017` |
| FUN-16 | No implementado | Torneos de modalidad individual: hay inscripción pero no partidos (`PARTIDOS` solo referencia equipos y el motor filtra `equipo_id is not None`) | `services/motor_formatos.py:129-131`; descartado en `TODOS.md` para marca, tiempo y combate | Decisión de producto |
| FUN-17 | Confirmado (simulación) | Navegar de día en el feed usa `toISOString()`: en zonas UTC+ "día siguiente" devuelve el mismo día; en UTC−5 después de las 19:00 el "hoy" de respaldo es mañana | `frontend/src/pages/publico/FeedPartidos.tsx:17-21,87`; simulado con desplazamientos explícitos | `TASK-040` |
| FUN-18 | Confirmado (estático) | Crear un torneo son cuatro `commit` (torneo, fase, asignación, configuración de tiempo) | `services/torneo.py:195-198`, `repositories/base.py:61` | `TASK-022` |
| FUN-19 | Riesgo potencial | Cancelar un partido de llave no hace avanzar a nadie; la llave queda bloqueada salvo walkover | `database/06_triggers.sql:967` | `TASK-009` |
| FUN-20 | Confirmado (estático) | Editar un vínculo de plantilla permite fijar cualquier `estado` y una `fecha_fin` anterior a la de inicio | `schemas/jugador_equipo.py:18-21`, `routes/plantillas.py:102-114` | `TASK-017` |
| FUN-21 | Confirmado (estático) | Dar de baja un equipo no comprueba inscripciones ni partidos programados; esos partidos dejan de verse en el feed y en "próximos" | `services/equipo.py:75-77`, `database/04_views.sql:46-92,241-287` | `TASK-016` |
| FUN-22 | Confirmado (estático) | El árbitro puede cambiar `arbitro_id`, `fecha_partido`, `fase` y `grupo` de su partido | `schemas/partido.py:50-96`, `services/partido.py:95-111` | `TASK-021` |

## 4. Lo que funciona bien

No todo son defectos. Estas piezas están bien pensadas y bien defendidas:

- **Partido en vivo.** Máquina de estados calculada en servidor (`acciones_permitidas`), minuto calculado desde el cronómetro e ignorando el que mande el cliente, bloqueo de fila con tiempo máximo de espera, roja automática por doble amarilla en la misma transacción, cierre forzado con motivo y ventana para deshacer.
- **Resultado directo** atómico: inicio, eventos y fin en una sola transacción, con las mismas validaciones que el camino en vivo.
- **Traspasos** con reversión real y bloqueo en cuanto el equipo destino juega.
- **Registro por lote** en dos pasos (validar, confirmar) con revalidación en servidor y éxito parcial.
- **Motor de formatos**: liga por método del círculo, llaves con byes y siembra, ida y vuelta, formato mixto, tercer puesto, cruces entre grupos, detección de empates en el corte de clasificación.
- **Desempates** con coherencia verificada en la base (tanda no empatada, ganador que coincide con la tanda, sin desempate en la ida).
- **RBAC** por torneo, licencias con corte inmediato y guardas contra el auto-bloqueo del administrador.
- **Privacidad**: proyección sin datos personales para anónimos y 404 para torneos no publicados.
