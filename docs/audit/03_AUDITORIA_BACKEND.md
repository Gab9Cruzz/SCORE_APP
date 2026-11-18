# 03 — Auditoría del backend

Fase III: FastAPI y Python. Análisis estático sobre `backend/app` (155 archivos); la suite de pruebas no pudo ejecutarse (ver `QA-03`).

## 1. Arquitectura

### Lo que está bien

- **Separación de responsabilidades real.** Los 21 routers son finos: declaran ruta, dependencias y delegan. Los servicios no importan FastAPI. Los repositorios encapsulan SQLAlchemy.
- **Permisos como dependencias componibles.** `require_roles`, `require_torneo_access` y `require_torneo_access_de(resolver)` (`backend/app/api/deps.py:118-212`) resuelven el torneo desde la ruta, el cuerpo o un recurso intermedio, con un único punto donde vive la regla. El chequeo de licencia va antes que cualquier otro.
- **Excepciones de dominio** (`exceptions/errors.py`) traducidas en un solo lugar, con matices útiles: 412 para conflicto optimista con el estado actual en el cuerpo, 409 con código estable para contención, 429 con `Retry-After`, 403 con cabecera para licencia.
- **Reglas extraídas a módulos puros** cuando se repetían: `reglamento_torneo.py`, `reglas_cambio.py`, `reglas_tarjetas.py`, `desempate.py`, `minuto_partido.py`.
- **Concurrencia en el camino caliente**: `EventoPartidoService.create` (`services/evento_partido.py:99-218`) es un buen ejemplo de transacción única con bloqueo, tiempo máximo de espera, clasificación de errores y reintento acotado.
- **Tipado completo** con anotaciones modernas; sin `Any` gratuito.

### Hallazgos

#### BE-01 — Consultas N+1 en listados

- **Tipo:** Confirmado (estático). **Severidad:** Medio.
- **Ubicación:** `backend/app/services/partido.py:85` y `:380-433`; `services/traspaso.py:56,58-72`; `repositories/usuario.py:16-19`.
- **Descripción:** `PartidoService.list` llama a `_a_salida` por cada partido, y este hace hasta cuatro consultas (fase, "¿es ida de otro?", configuración de tiempo, goles de la ida). `TraspasoService.list` hace dos por traspaso. `UsuarioRepository.count` trae todas las filas para contarlas.
- **Impacto:** `GET /partidos?limit=200` puede lanzar varios cientos de consultas. Es el endpoint que usan Control de Mesa, el panel de partidos y, sin sesión, el portal.
- **Recomendación:** resolver en lote (una consulta por dato para toda la página) o mover el cálculo a una vista. `TASK-023`.

#### BE-02 — Operaciones de varios pasos que no son atómicas

- **Tipo:** Confirmado (estático). **Severidad:** Medio.
- **Ubicación:** `backend/app/repositories/base.py:61,81` (commit dentro de `create` y `save_changes`); casos: `services/hito_partido.py:404,448,456` (escribe ganador o desempate en el partido y después crea el hito), `services/torneo.py:195-198` (torneo, fase, asignación y configuración), `services/inscripcion_torneo.py:119-120` (inscripción y luego copia de plantilla), `services/usuario.py:64,74` (cambio de rol y luego baja de asignaciones).
- **Impacto:** si el segundo paso falla, el primero ya está guardado. Ejemplo: el hito de fin se rechaza por un trigger y el partido queda con `ganador_desempate_id` escrito.
- **Recomendación:** que los repositorios no hagan `commit`; una unidad de trabajo por caso de uso. El patrón correcto ya existe en `registrar_resultado_directo` y en `_crear_bajo_lock`. `TASK-022`.

#### BE-03 — Carreras conocidas sin cerrar

- **Tipo:** Riesgo potencial (una de ellas reconocida en `TODOS.md`). **Severidad:** Medio.
- **Ubicación y detalle:**
  - Tope de titulares: `services/convocado_a_partido.py:308-317` cuenta sin bloqueo, y el trigger `fn_validar_tope_titulares` (`database/06_triggers.sql:141-153`) también. Dos altas simultáneas pueden superar el máximo. Pendiente como T23.
  - Doble inicio de partido: `services/hito_partido.py:360-463` no bloquea el partido; el trigger detecta duplicados con un `COUNT` (`06_triggers.sql:1068-1078`) que no ve la transacción concurrente. Solo el fin de partido tiene índice único (`database/03_indexes.sql`, `uq_hitos_partido_fin_unico`).
  - Sorteo concurrente: `services/motor_formatos.py:217-236` no serializa; dos sorteos a la vez pueden generar dos cuadros.
- **Recomendación:** bloquear la fila del partido (ya hay `get_or_404_bloqueado`) e índice único parcial para el inicio; bloqueo consultivo por fase en el sorteo. `TASK-024`.

#### BE-04 — Manejo de errores y registro insuficientes

- **Tipo:** Confirmado (estático). **Severidad:** Medio.
- **Ubicación:** `backend/app/exceptions/handlers.py:21-39,108-117`; `backend/app/main.py:38-43,74-81` (`print`).
- **Descripción:** todo `DBAPIError` se responde como 400 con la primera línea del mensaje de PostgreSQL, sea una regla de negocio, una desconexión o un error de sintaxis. No hay manejador para excepciones no previstas, ni configuración de logging, ni identificador de petición. El único logger real es el de contención (`app.concurrencia`) y el de métricas.
- **Impacto:** fallos de infraestructura llegan al usuario como "error de validación" y no dejan rastro en el servidor. Diagnosticar un incidente en producción sería a ciegas. Ver también `SEC-06`.
- **Recomendación:** distinguir por SQLSTATE (`P0001` regla de negocio, clase 23 integridad, el resto 500 genérico con registro), manejador global y logging estructurado. `TASK-015`.

#### BE-05 — Fechas sin zona horaria y dos relojes

- **Tipo:** Riesgo potencial. **Severidad:** Bajo hoy, Medio al desplegar.
- **Ubicación:** todas las columnas son `TIMESTAMP` sin zona (`database/01_schema.sql`); `datetime.now()` de la aplicación se compara con `CURRENT_TIMESTAMP` de la base en `services/evento_partido.py:262` (minuto de juego), `services/hito_partido.py:593` (ventana de 5 s para deshacer), `services/usuario.py:138` (ventana del límite de login), `repositories/acceso.py:77` (purga); `services/motor_formatos.py:881` guarda `fecha_cierre` en UTC.
- **Impacto:** funciona mientras aplicación y base compartan zona (como en el compose, ambas en UTC). Con la base en UTC y la aplicación en hora local, el minuto de juego se desplaza horas. El frontend, además, interpreta esas fechas como hora local del navegador.
- **Recomendación:** `TIMESTAMPTZ` y UTC de extremo a extremo, o como mínimo usar siempre el reloj de la base. `TASK-028`.

#### BE-06 — API: paginación y parámetros inconsistentes

- **Tipo:** Confirmado (estático). **Severidad:** Medio.
- **Detalle:**
  - Cuatro listados no exponen `skip`/`limit` y cortan en 100 (`FUN-05`).
  - Los que sí paginan no devuelven el total ni enlaces; el cliente no puede saber si hay más.
  - `skip: int = 0` y `limit: int = Query(default=100, le=200)` no tienen mínimo (por ejemplo `routes/torneos.py:23-24`): un valor negativo llega a PostgreSQL y vuelve como 400 con el mensaje crudo.
  - Orden fijo por ID; no hay parámetro de ordenación. Para partidos el orden útil es la fecha.
  - Estilo mixto en acciones: `POST /plantillas/{id}/baja?fecha_fin=…` lleva el dato en la query, `POST /partidos/{id}/walkover` en el cuerpo.
- **Recomendación:** convención única de paginación con envoltorio `{items, total}` o cabecera `X-Total-Count`, `ge=0`/`ge=1`, y `orden`. `TASK-011`, `TASK-029`.

#### BE-07 — Validación de entrada laxa en los schemas

- **Tipo:** Confirmado (estático). **Severidad:** Bajo.
- **Ubicación:** `schemas/equipo.py:9-10`, `schemas/jugador.py:9-16`, `schemas/evento.py:9-11`, `schemas/registro_lote.py:12-27`, `schemas/partido.py:194-201`, `schemas/convocado_a_partido.py:14-23`, `schemas/torneo.py:145-191`.
- **Detalle:** cadenas sin longitud mínima ni máxima (se acepta un nombre vacío; uno demasiado largo vuelve como error crudo de PostgreSQL); correo sin formato; enteros sin rango (`equipos_por_grupo`, `clasificados_por_grupo`, `dorsal`, `cupo_maximo_inscripciones`); listas sin tope (`filas`, `eventos`, `convocados`); `foto_url` sin la exigencia de `https://` que sí tienen los logos.
- **Recomendación:** `Field(min_length, max_length)`, `EmailStr`, `conint`, `conlist(max_length=…)`. `TASK-029`.

#### BE-08 — Caché del feed sin límite

- **Tipo:** Confirmado (estático). **Severidad:** Medio.
- **Ubicación:** `backend/app/services/feed.py:22-23,64-68,92`.
- **Descripción:** diccionario a nivel de módulo con clave `(fecha, disciplina, limit, ventana)`. Las entradas vencidas nunca se eliminan; solo se pisan si se repite la misma clave. El endpoint es público.
- **Impacto:** un visitante que itere fechas hace crecer la memoria del proceso sin techo. Con varios workers, además, cada uno tendría su copia.
- **Recomendación:** caché con tamaño máximo y expiración (LRU con TTL), o cabeceras HTTP de caché delante de un proxy. `TASK-030`.

#### Hallazgos menores

| ID | Tipo | Severidad | Hallazgo | Evidencia | Tarea |
|---|---|---|---|---|---|
| BE-09 | Riesgo potencial | Bajo | Los bloqueos consultivos de una sola clave comparten espacio: `pg_advisory_xact_lock(:id)` se usa con `torneo_id`, `torneo_grupo_id` e `inscripcion_torneo_id`; operaciones sin relación con el mismo número se esperan entre sí | `repositories/torneo.py:32-34`, `repositories/torneo_grupo.py:33-36`, `repositories/inscripcion_torneo.py:53-56` | `TASK-024` |
| BE-10 | Confirmado (estático) | Bajo | Ciclo de vida de la aplicación: tareas de arranque lanzadas con `create_task` sin guardar referencia; purgas que solo corren al iniciar; el motor no se cierra al apagar; pool con valores por defecto; `/health` responde "ok" sin consultar la base | `backend/app/main.py:106-113,135-137`, `backend/app/db/database.py:18-24` | `TASK-052`, `TASK-053` |
| BE-11 | Mejora | Bajo | Sin linter, formateador ni chequeo de tipos para Python (ni `ruff` ni `mypy` en dependencias ni en `verificar.ps1`) | `backend/requirements.txt`, `verificar.ps1` | `TASK-003` |
| BE-12 | Mejora | Bajo | Dependencias de prueba mezcladas con las de ejecución en un único `requirements.txt`; terminan en la imagen de producción | `backend/requirements.txt:11-19`, `backend/Dockerfile:6-7` | `TASK-049` |
| BE-13 | Mejora | Bajo | Funciones largas con varias responsabilidades: `registrar_resultado_directo` (unas 210 líneas), `HitoPartidoService.registrar`, `_sortear_bracket`; bloques duplicados entre `registrar` y `_registrar_fin_forzado` para el desempate | `services/partido.py:168-378`, `services/hito_partido.py:406-454` frente a `:517-545` | Refactor oportunista |
| BE-14 | Informativo | — | `/docs`, `/redoc` y `/openapi.json` quedan públicos por defecto | `backend/app/main.py:116-121` | `TASK-050` |

## 2. API

### Convenciones REST

| Aspecto | Evaluación |
|---|---|
| Recursos y verbos | Coherentes: `GET` lectura, `POST` alta y acciones, `PATCH` edición parcial, `DELETE` como baja lógica que devuelve el recurso |
| Códigos | 201 en altas; 400 regla de negocio, 401, 403, 404, 409, 412, 422, 429 bien diferenciados. Excepción: errores de infraestructura como 400 (`BE-04`) |
| Versionado | Prefijo `/api/v1` configurable |
| Nombres | Recursos y campos en español; `skip`, `limit`, `q` en inglés, regla documentada |
| Errores | Siempre `{"detail": …}`. Mezcla mensajes legibles y códigos `snake_case`; el frontend traduce 12 de estos (`frontend/src/api/client.ts:72-93`). Falta un envoltorio con código estable (reconocido en `TODOS.md`) |
| OpenAPI | Completo y consumido por el frontend. Tres `GET` de jugadores declaran la unión de respuestas a mano porque usan `response_model=None` (bien resuelto) |
| Filtros | Por igualdad en casi todo; búsqueda de texto solo en jugadores (`q`) y accesos |
| Ordenación | No configurable |

### Inventario de endpoints (69 rutas en el OpenAPI generado)

| Grupo | Lectura pública | Escritura |
|---|---|---|
| `/auth` | — | `login`; `me` autenticado |
| `/usuarios`, `/accesos`, `/auditoria` | No | AdminGeneral (lectura de usuarios también TorneoAdmin, recortada a árbitros) |
| `/disciplinas`, `/modalidades`, `/eventos` | Sí | TorneoAdmin, sin alcance |
| `/torneos`, `/torneo-grupos` | Sí (torneos filtrados por `publicado`; grupos sin filtrar) | TorneoAdmin con alcance en torneos; sin alcance en grupos |
| `/torneos/{id}/fixture, sorteo, playoffs, cerrar, reabrir, estado-fase` | Solo `bracket` | TorneoAdmin con alcance |
| `/equipos`, `/jugadores`, `/perfiles` | Sí (jugadores sin datos personales) | TorneoAdmin, sin alcance |
| `/inscripciones`, `/plantillas`, `/traspasos`, `/plantillas/lote` | Sí | TorneoAdmin con alcance |
| `/partidos` y sub-recursos | Sí | TorneoAdmin con alcance, o árbitro asignado |
| `/eventos-partido` | Sí | Ídem |
| `/estadisticas/*` | Sí (por torneo, con `publicado`) | — |

## 3. Rendimiento

| Punto | Evaluación |
|---|---|
| Async de extremo a extremo | Correcto; no se encontraron llamadas bloqueantes. `bcrypt` se ejecuta en el bucle de eventos (unos 100–300 ms por login), aceptable a este volumen |
| N+1 | `BE-01` |
| Consultas sobre vistas | Las estadísticas agregan sobre todos los partidos del torneo en cada petición (`DB-11`); aceptable hoy |
| Sondeo del partido en vivo | El endpoint público del cronómetro hace 3 consultas por llamada cada 5 s por espectador; sin caché. Aceptable para decenas de espectadores, a vigilar |
| Preflight de inicio | Unas 7 consultas; correctamente separado del endpoint público |
| Conexiones | Pool por defecto de SQLAlchemy (5 + 10), `pool_pre_ping` activo. Sin configuración explícita |
| Caché | Solo el feed, con el problema de `BE-08` |

## 4. Calidad de código

| Aspecto | Evaluación |
|---|---|
| Legibilidad | Alta. Los comentarios explican el porqué y remiten al plan. En algunos archivos el comentario supera al código, lo que encarece la lectura lineal |
| Tipado | Completo |
| Duplicación | Baja; lo repetido se ha ido extrayendo. Queda el bloque de desempate en `hito_partido.py` |
| Complejidad | Concentrada en `motor_formatos.py`, `hito_partido.py` y `partido.py` |
| Testabilidad | Buena: servicios instanciables con una sesión, reglas puras separadas |
| Logging | Insuficiente (`BE-04`) |
| Configuración | Centralizada y cacheada; valores por defecto inseguros (`SEC-02`) |

## 5. Resumen de hallazgos del backend

| ID | Severidad | Tipo | Resumen |
|---|---|---|---|
| BE-01 | Medio | Confirmado (estático) | N+1 en listados de partidos y traspasos |
| BE-02 | Medio | Confirmado (estático) | Varios `commit` por caso de uso |
| BE-03 | Medio | Riesgo potencial | Carreras: titulares, inicio de partido, sorteo |
| BE-04 | Medio | Confirmado (estático) | Errores de infraestructura como 400; sin logging |
| BE-05 | Bajo/Medio | Riesgo potencial | Fechas sin zona y dos relojes |
| BE-06 | Medio | Confirmado (estático) | Paginación y parámetros inconsistentes |
| BE-07 | Bajo | Confirmado (estático) | Schemas sin límites |
| BE-08 | Medio | Confirmado (estático) | Caché del feed sin techo |
| BE-09 | Bajo | Riesgo potencial | Bloqueos consultivos con claves que colisionan |
| BE-10 | Bajo | Confirmado (estático) | Arranque, apagado y `/health` |
| BE-11 | Bajo | Mejora | Sin lint ni tipos para Python |
| BE-12 | Bajo | Mejora | Dependencias de prueba en producción |
| BE-13 | Bajo | Mejora | Funciones largas y un bloque duplicado |
| BE-14 | Informativo | — | Documentación de la API pública |

La seguridad del backend se trata en el documento 06.
