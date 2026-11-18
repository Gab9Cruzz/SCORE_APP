# 01 — Análisis de arquitectura

Fase I de la auditoría: qué es el sistema, cómo está armado y cómo fluyen los datos. Todo lo descrito se verificó en el código, no en la documentación (donde difieren, se anota en `ARQ-05`).

## 1. Qué es SCORE_APP

Sistema de gestión de torneos deportivos con tres superficies:

- **Back-office** para administradores de torneo: catálogo de disciplinas, equipos, jugadores, torneos y ediciones, inscripciones, plantillas, traspasos, fixture y cierre.
- **Control de Mesa** para operadores y árbitros, pensado para el celular: alineaciones, cronómetro, goles, tarjetas, cambios, cierre del partido.
- **Portal público** sin sesión: feed de partidos por día y deporte, detalle de torneo (posiciones, resultados, goleadores, llaves) y partido en vivo.

## 2. Stack verificado

| Capa | Tecnología (versión instalada o declarada) | Evidencia |
|---|---|---|
| API | Python 3.12, FastAPI 0.141.1, Starlette 1.10.0, Uvicorn 0.52.4 | `backend/requirements.txt`, `pip list` del venv |
| ORM / driver | SQLAlchemy 2.0.52 async, psycopg 3.3.4 (asyncpg solo en tests) | `backend/app/db/database.py`, `.env.example` |
| Validación / config | Pydantic 2.13.4, pydantic-settings 2.15.0 | `backend/app/core/config.py` |
| Autenticación | JWT HS256 con python-jose 3.5.0, bcrypt 5.0.0 | `backend/app/core/security.py` |
| Base de datos | PostgreSQL 16 (imagen `postgres:16-alpine`), esquema en SQL puro, **sin Alembic** | `database/`, `infrastructure/docker-compose.yml` |
| Frontend | React 19.2, React Router 7, TanStack Query 5, TypeScript 6.0, Vite 8.2 | `frontend/package.json` |
| Contrato | `openapi-typescript` genera `src/api/schema.d.ts` (7.274 líneas); `openapi-fetch` como cliente | `frontend/package.json` (script `gen:api`) |
| Pruebas | pytest 9 + pytest-asyncio + httpx; Vitest 4 + Testing Library + MSW | `backend/pytest.ini`, `frontend/vite.config.ts` |
| Lint | oxlint (frontend). No hay linter ni formateador configurado para Python | `frontend/.oxlintrc.json` |
| Infra | Docker Compose con dos servicios (`postgres`, `api`) | `infrastructure/docker-compose.yml` |

No hay integraciones externas: ni correo, ni almacenamiento de archivos, ni pasarelas. Las imágenes (escudos, fotos) son URLs de texto.

## 3. Tamaño del repositorio

421 archivos versionados, unas 62.000 líneas en `backend/app`, `backend/tests` y `frontend/src` (7.274 son el esquema generado).

| Área | Archivos | Observación |
|---|---:|---|
| `backend/app` | 155 | 21 routers, 30 servicios, 28 repositorios (incluido el base), 25 modelos, 28 schemas |
| `backend/tests` | 53 | 51 archivos de test, 505 funciones `test_` |
| `frontend/src` | 120 | 38 archivos de test, 344 casos |
| `database/` | 34 `.sql` | 6 de esquema "vigente" (`01`–`06`), 25 migraciones, 3 de datos |
| `docs/plans` | 21 | un plan por módulo |

## 4. Diagrama de componentes

```
                         ┌──────────────────────────────────────────┐
                         │                Navegador                 │
                         │  SPA React (Vite) — una sola aplicación  │
                         │                                          │
   Público (sin sesión)  │  /            FeedPartidos               │
                         │  /torneos/:id DetalleTorneoPublico       │
                         │  /partido/:id PartidoEnVivo (polling 5s) │
                         │  ───────────────────────────────────────  │
   Árbitro / Mesa        │  /control-de-mesa, /arbitro              │
                         │  MesaPanel · Cronometro · AlineacionEditor│
                         │  ───────────────────────────────────────  │
   TorneoAdmin           │  /torneo-admin/* (torneos, equipos,      │
                         │  jugadores, catálogo, dashboard de torneo)│
   AdminGeneral          │  /admin/usuarios · accesos · auditoría   │
                         │                                          │
                         │  AuthContext ── localStorage (JWT + rol) │
                         │  TanStack Query ── openapi-fetch (tipado)│
                         └───────────────────┬──────────────────────┘
                                             │ HTTP JSON, Bearer JWT
                                             │ (CORS, sin proxy inverso)
                         ┌───────────────────▼──────────────────────┐
                         │        FastAPI  /api/v1  (1 proceso)     │
                         │                                          │
                         │  routes ──► services ──► repositories    │
                         │    │           │              │          │
                         │  deps.py    reglas de      BaseRepository│
                         │  (JWT, rol, aplicación     (commit por   │
                         │  licencia,                  operación)   │
                         │  acceso a torneo)                        │
                         │                                          │
                         │  core/auditoria.py: listener de flush    │
                         │  exceptions/handlers.py: errores → JSON  │
                         └───────────────────┬──────────────────────┘
                                             │ psycopg async
                         ┌───────────────────▼──────────────────────┐
                         │              PostgreSQL 16               │
                         │  25 tablas · 10 vistas · 20 funciones    │
                         │  Triggers = reglas de negocio "duras"    │
                         │  Vistas   = estadísticas y feed público  │
                         └──────────────────────────────────────────┘
```

## 5. Mapa de módulos

### 5.1 Backend (`backend/app`)

| Capa | Carpeta | Responsabilidad |
|---|---|---|
| Entrada | `api/routes/` | Un router por recurso: declara ruta, dependencias de permiso y delega |
| Permisos | `api/deps.py`, `services/permisos.py` | Usuario del token, licencia, rol, asignación de torneo, "¿es tu partido?" |
| Aplicación | `services/` | Orquestación, validaciones legibles, transacciones compuestas |
| Datos | `repositories/` | CRUD genérico con baja lógica, consultas propias, bloqueos |
| Mapeo | `models/` | Un archivo por tabla; no crea tablas |
| Contrato | `schemas/` | Pydantic `Create/Update/Out` |
| Transversal | `core/` | Configuración, JWT/bcrypt, auditoría de cambios, métricas por log |
| Errores | `exceptions/` | Excepciones de dominio y su traducción a HTTP |

### 5.2 Módulos funcionales y sus piezas

| Módulo | Routers | Servicios principales | Tablas |
|---|---|---|---|
| Autenticación y usuarios | `auth`, `usuarios`, `accesos` | `usuario`, `asignacion_torneo_admin` | `USUARIOS`, `ACCESOS`, `ASIGNACION_TORNEO_ADMIN` |
| Catálogo | `disciplinas`, `modalidades`, `eventos` | `disciplina`, `modalidad`, `evento` | `DISCIPLINA`, `MODALIDAD`, `EVENTOS` |
| Torneos y ediciones | `torneos`, `torneo_grupos` | `torneo`, `torneo_grupo`, `reglamento_torneo` | `TORNEO_GRUPO`, `TORNEO`, `CONFIGURACION_TIEMPO_TORNEO`, `FASE` |
| Equipos y jugadores | `equipos`, `jugadores`, `perfiles` | `equipo`, `jugador`, `jugador_perfil_disciplina`, `perfil_jugador`, `plantilla_base` | `EQUIPOS`, `JUGADORES`, `JUGADOR_PERFIL_DISCIPLINA`, `EQUIPO_JUGADOR_BASE` |
| Inscripciones y plantillas | `inscripciones`, `plantillas`, `registro_lote` | `inscripcion_torneo`, `jugador_equipo`, `registro_lote` | `INSCRIPCIONES_TORNEO`, `JUGADOR_EQUIPO` |
| Traspasos | `traspasos` | `traspaso` | `TRASPASOS` |
| Motor de formatos | `motor_formatos`, `grupos` | `motor_formatos`, `grupo_equipo`, `desempate` | `FASE`, `GRUPO`, `GRUPO_EQUIPO`, `SORTEOS`, `PARTIDOS` |
| Partidos y mesa | `partidos`, `eventos_partido` | `partido`, `hito_partido`, `evento_partido`, `convocado_a_partido`, `minuto_partido`, `reglas_cambio`, `reglas_tarjetas` | `PARTIDOS`, `HITOS_PARTIDO`, `EVENTOS_PARTIDO`, `CONVOCADO_A_PARTIDO` |
| Estadísticas y portal | `estadisticas`, `partidos` (`/feed`), `disciplinas` (`/con-partidos`) | `estadisticas`, `feed` | vistas `vw_*` |
| Auditoría | `auditoria` | listener en `core/auditoria.py` | `AUDITORIA` |

### 5.3 Frontend (`frontend/src`)

| Carpeta | Contenido |
|---|---|
| `api/` | Cliente tipado, interceptor de token, manejo de 401 y de licencia revocada, traducción de códigos de error |
| `auth/` | `AuthContext` (sesión en `localStorage`), `useAuth` |
| `components/` | `MesaPanel`, `Cronometro`, `ModalSustitucion`, `NavBar`, `RequireRole`; `admin/` (tabla, formulario y filtros genéricos); `publico/` |
| `hooks/` | `useResourceCrud` (CRUD genérico sobre TanStack Query), `useCatalogo`, `useModalFocusTrap`, `useOnlineStatus`, `useFetchFaltantes` |
| `lib/` | Lógica pura con pruebas: cola offline de eventos, desempate, reconciliación de marcador |
| `pages/` | `publico/`, `control-mesa/`, `arbitro/`, `torneo-admin/` (con `torneo-dashboard/`), `admin/` |
| `index.css` | Hoja de estilos global única (2.452 líneas), tema oscuro con variables CSS |

## 6. Relaciones entre módulos

```
DISCIPLINA ─< MODALIDAD
     │            │
     └──────┬─────┘
            ▼
     TORNEO_GRUPO ─< TORNEO (edición) ─1─ CONFIGURACION_TIEMPO_TORNEO
                        │   └─< FASE ─< GRUPO ─< GRUPO_EQUIPO
                        │
   EQUIPOS ─< INSCRIPCIONES_TORNEO >─ TORNEO
                        │   (o inscripción individual: JUGADOR_PERFIL_DISCIPLINA)
                        ▼
   JUGADORES ─< JUGADOR_PERFIL_DISCIPLINA ─< JUGADOR_EQUIPO   (plantilla del torneo)
                        │                         ▲
                        └─< TRASPASOS ────────────┘  (cierra una membresía, abre otra)

   TORNEO ─< PARTIDOS ─< HITOS_PARTIDO        (cronómetro y estado)
                  ├──< EVENTOS_PARTIDO        (goles, tarjetas, cambios)
                  └──< CONVOCADO_A_PARTIDO    (titulares y suplentes)

   USUARIOS ─< ASIGNACION_TORNEO_ADMIN >─ TORNEO     (alcance del TorneoAdmin)
   USUARIOS ─1< PARTIDOS.ARBITRO_ID                  (alcance del Árbitro)
```

Dependencias que conviene tener presentes porque cruzan módulos:

- **El estado del partido no se escribe directamente**: lo mueve un trigger al insertar un hito de inicio o fin (`fn_hito_sincroniza_estado_partido`). Walkover es la excepción reconocida.
- **El marcador no se guarda**: se calcula en vistas a partir de eventos cuyo tipo se identifica por el **nombre** del evento en el catálogo (`'Gol'`, `'Autogol'`). Esto acopla Estadísticas, Motor de formatos y Portal al catálogo de eventos (ver `FUN-14`).
- **Cerrar un torneo** dispara un trigger que da de baja todas las membresías de sus plantillas, lo que a su vez condiciona la validación de eventos (ver `FUN-01`).
- **El portal público** depende de `TORNEO.Publicado` y del estado del `TORNEO_GRUPO`; el gate vive en dependencias del backend y en la vista `vw_feed_partidos`.

## 7. Flujos de datos

### 7.1 Petición autenticada típica

1. El interceptor de `api/client.ts` añade `Authorization: Bearer <token>` leyendo `localStorage`.
2. `get_current_user` decodifica el JWT, **relee el usuario en la base** en cada petición (estado y licencia siempre frescos) y deja el actor en un `contextvar` para la auditoría.
3. `require_roles(...)` comprueba el rol (AdminGeneral pasa siempre) y `require_torneo_access(...)` comprueba que el TorneoAdmin tenga asignado el torneo, resolviéndolo desde la ruta, el cuerpo o un recurso intermedio.
4. El servicio aplica validaciones legibles y delega en repositorios.
5. Al hacer `flush`, el listener de `core/auditoria.py` fotografía altas, cambios y bajas y las inserta en `AUDITORIA` dentro de la misma transacción.
6. Los triggers de PostgreSQL validan las reglas duras; si rechazan, `exceptions/handlers.py` convierte el mensaje en 400 o 409.
7. El frontend traduce códigos conocidos (`CODIGOS_ERROR_TRADUCIDOS`) y TanStack Query invalida las consultas afectadas.

### 7.2 Partido en vivo

```
Convocatoria (PUT /partidos/{id}/convocados, con control de versión → 412 si cambió)
   → preflight (GET /preflight-inicio)
   → POST /hitos {Inicio_Partido}      ── trigger ──► PARTIDOS.Estado = 'En curso'
   → POST /eventos-partido             (SELECT … FOR UPDATE del partido, lock_timeout,
                                        minuto calculado en servidor, roja automática
                                        por doble amarilla en la misma transacción)
   → POST /hitos {Fin_Partido}         ── trigger ──► 'Finalizado'
                                       ── trigger ──► avanza al ganador en la llave
Público: GET /partidos/{id}/cronometro y /eventos-partido cada 5 s
```

Si la red falla o hay contención (409 con código estable), el evento queda en una cola local de un elemento por partido (`lib/colaOfflineEventos.ts`) para reintentar.

### 7.3 Persistencia

- Una `AsyncSession` por petición (`db/session.py`), con `rollback` si la petición termina en excepción.
- `BaseRepository.create` y `save_changes` hacen `commit` cada uno. Los servicios que necesitan atomicidad lo evitan a mano con `session.add` + `flush` y un único `commit` final (resultado directo, eventos en vivo, traspasos, sorteos).
- Sin borrado físico desde la API: baja lógica por columna `Estado`. Dos excepciones deliberadas: rehacer un sorteo y deshacer un cierre forzado.

## 8. Autenticación y autorización

| Rol | Alcance real en el código |
|---|---|
| `AdminGeneral` | Todo. Único que gestiona usuarios, licencias, asignaciones, accesos y auditoría |
| `TorneoAdmin` | Crea torneos (se autoasigna). Escribe solo en torneos asignados. Catálogos globales (equipos, jugadores, perfiles, eventos, disciplinas, grupos de torneo) sin acotar — ver `SEC-04` |
| `Arbitro` | Opera los partidos donde figura como `ARBITRO_ID` |
| `Publico` | Cuenta sin permisos de escritura |
| Anónimo | Lectura de torneos publicados; jugadores sin cédula ni correo |

Elementos destacables: licencia revocable con efecto inmediato (se comprueba en cada petición, no vive en el token), 403 distinguible por cabecera `X-License-Revoked`, límite de intentos de login, guardas de auto-bloqueo del administrador.

## 9. Configuración y despliegue

- Configuración por variables de entorno (`.env`), con `JWT_SECRET_KEY` obligatorio.
- `infrastructure/docker-compose.yml` levanta PostgreSQL y la API. **El frontend no tiene contenedor**: se sirve con `npm run dev`.
- En Windows la API se arranca con `python run.py` (bucle de eventos Selector) por incompatibilidad del driver con el bucle Proactor.
- Verificación local con `verificar.ps1` (PowerShell). No hay CI.

## 10. Fortalezas arquitectónicas

1. **Decisiones documentadas.** 21 planes en `docs/plans/` con alternativas descartadas, casos borde numerados y revisiones. Los comentarios del código remiten al plan que justifica cada decisión. Es el mayor activo de mantenibilidad del proyecto.
2. **Capas limpias y consistentes.** `routes → services → repositories → models` se respeta en los 21 routers; los servicios no dependen de FastAPI.
3. **La base como última línea de defensa.** 20 funciones y sus triggers hacen cumplir exclusividad de jugador por torneo, coherencia disciplina–modalidad, validez de jugador en partido, máquina de estados del cronómetro, desempates y bloqueo de torneo cerrado. Un `psql` directo no puede saltárselas.
4. **Contrato generado.** El frontend no escribe tipos de API a mano; un cambio de schema rompe la compilación del otro lado.
5. **Auditoría transversal bien resuelta.** Listener de sesión que captura cualquier escritura del ORM, atómico con el cambio auditado, con redacción del hash de contraseña.
6. **Concurrencia tratada en serio donde más duele.** Bloqueo de fila con `lock_timeout`, clasificación de errores, reintento de deadlock, bloqueos consultivos para cupos y numeración, control de versión optimista en la convocatoria, e infraestructura de pruebas con conexiones reales.
7. **Privacidad pensada.** Proyecciones `*PublicOut` sin cédula ni correo para anónimos; torneos no publicados devuelven 404 en vez de 403.
8. **Sin deuda de tipos.** Cero `any`, cero `@ts-ignore` relevantes, cero `console.log`, cero `dangerouslySetInnerHTML`.

## 11. Riesgos iniciales

| ID | Tipo | Severidad | Hallazgo | Evidencia | Recomendación |
|---|---|---|---|---|---|
| ARQ-01 | Mejora | Medio | El esquema tiene dos representaciones que hay que mantener a mano: `01`–`06` ("estado final") y las migraciones `07`–`33`. No hay tabla de versiones ni herramienta; nada registra qué migración se aplicó en qué base | `database/README.md` (secciones "Las tres familias" y la nota del 2026-09-14 sobre un índice que quedó desactualizado) | Runner mínimo con tabla `schema_migrations` (`TASK-031`) |
| ARQ-02 | Confirmado (estático) | Medio | `BaseRepository` hace `commit` en cada `create`/`save_changes`; los servicios que encadenan varios quedan sin atomicidad salvo que lo eviten a mano | `backend/app/repositories/base.py:61,81`; casos en `BE-02` | Unidad de trabajo por caso de uso (`TASK-022`) |
| ARQ-03 | Mejora | Bajo | Reglas repartidas entre Python, triggers y vistas, enlazadas por cadenas: nombres de eventos del catálogo y códigos de error en `RAISE EXCEPTION` que el frontend traduce con un mapa | `database/04_views.sql:18-44`, `frontend/src/api/client.ts:72-93` | Identificadores estables en el catálogo (`TASK-019`); catálogo de códigos de error compartido |
| ARQ-04 | Mejora | Bajo | Archivos muy grandes que concentran varios casos de uso: `motor_formatos.py` (1.000 líneas), `hito_partido.py` (664), `MesaPanel.tsx` (1.088), `TorneosAdmin.tsx` (987), `ModalResultadoDirecto.tsx` (912), `Cronometro.tsx` (880), `index.css` (2.452) | recuento de líneas del repositorio | Extraer por caso de uso al tocarlos; no reescribir |
| ARQ-05 | Confirmado (estático) | Bajo | Documentación que ya no describe el código: `backend/README.md` lista tres roles (`Admin`, `Arbitro`, `Publico`) y dice que "todos los GET son públicos"; `frontend/README.md` cita `Convocatoria.tsx`, que no existe, y solo tres páginas; el `Dockerfile` comenta que usa asyncpg; el comentario del compose dice que la API "necesita las migraciones 07-33" y `database/README.md` dice que `01`–`06` ya son el estado final; `Enceder.txt` trae rutas de otra máquina | archivos citados; `backend/app/schemas/usuario.py:6` (cuatro roles) | Actualizar en una pasada (`TASK-055`) |
| ARQ-06 | Riesgo potencial | Medio | Un solo proceso de API con estado en memoria (caché del feed) y tareas de mantenimiento que solo corren al arrancar; no está pensado para varios workers ni para servicio permanente | `backend/app/services/feed.py:22-23`, `backend/app/main.py:46-113` | Ver `BE-08`, `BE-10`, `OPS-07` |

Los riesgos funcionales, de seguridad y de operación se desarrollan en los documentos 02 a 08.
