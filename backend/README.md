# Torneo MVP — API

FastAPI + SQLAlchemy (async) + PostgreSQL. El esquema (tablas, constraints,
vistas, triggers) vive en [`/database`](../database) y se aplica con SQL
puro — esta API no crea tablas ni usa Alembic, solo mapea lo que ya existe.

## Arquitectura

```
app/
├── api/
│   ├── routes/       # un router por recurso, fino: valida y delega
│   └── deps.py        # get_db, get_current_user, require_roles(...)
├── core/
│   ├── config.py       # Settings (pydantic-settings, lee .env)
│   └── security.py     # hash de password, JWT
├── db/
│   ├── database.py      # engine async + Base declarativa
│   └── session.py       # get_db() -> AsyncSession por request
├── models/       # ORM (SQLAlchemy 2.0), un archivo por tabla
├── schemas/       # Pydantic (Create/Update/Out), un archivo por recurso
├── repositories/  # acceso a datos: CRUD + borrado lógico + vistas
├── services/       # lógica de aplicación: arma la respuesta, orquesta repos
├── exceptions/     # excepciones de dominio + traducción a JSON
└── main.py          # arma la app, CORS, bootstrap del Admin
```

`routes` → `services` → `repositories` → `models`. Las reglas de negocio
"duras" (un jugador solo anota si pertenecía al equipo en la fecha del
partido, ambos equipos deben estar inscritos para jugar, etc.) **no están
duplicadas en Python**: viven en los triggers de `/database/06_triggers.sql`
y la API deja que Postgres las haga cumplir. `exceptions/handlers.py`
traduce el mensaje del trigger a un 400 legible.

## Requisitos

- Python 3.12+
- PostgreSQL 16 o 17 con el esquema de `/database` ya aplicado (ver el
  README de esa carpeta) en una base llamada `torneos_mvp`. Una base que ya
  existía se pone al día con `python -m scripts.migrar --aplicar`.

## Correr local (sin Docker)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

pip install -r requirements.txt
copy .env.example .env        # y ajustar si tu Postgres no es localhost:5432
uvicorn app.main:app --reload
```

Docs interactivas: http://localhost:8000/docs

### Windows: si `uvicorn app.main:app` no logra conectar a Postgres

En Windows, `uvicorn` fuerza `ProactorEventLoop` (lo necesita `--reload`).
Ahí, `asyncpg` no logra completar ninguna conexión — falla con `WinError 64`
apenas se intenta la primera query, tanto en el arranque como en cada
request, incluso con Postgres sano y escuchando. Por eso el driver de esta
API es `psycopg`, no `asyncpg` (ver `.env.example`); pero `psycopg` async
tampoco corre sobre `ProactorEventLoop` — lo rechaza directamente con un
error explícito, no hace falta adivinarlo.

Si te pasa igual (por ejemplo veías `Internal Server Error` en todos los
endpoints que tocan la base, con `/health` respondiendo bien), usá:

```bash
python run.py
```

en vez de `uvicorn app.main:app --reload`. `run.py` arranca el mismo server
pero con `SelectorEventLoop`, que sí es compatible. La única diferencia:
sin `--reload` (`SelectorEventLoop` no soporta subprocesos en Windows, y
`--reload` los necesita). Si preferís mantener `--reload`, corré la API con
Docker (ver [`/infrastructure`](../infrastructure)): ahí corre Linux adentro
del contenedor y este problema no existe, cualquiera de los dos drivers
funciona sin este workaround.

Al arrancar por primera vez, si la tabla `usuarios` está vacía, la API crea
sola un usuario `AdminGeneral` con `ADMIN_USERNAME` / `ADMIN_PASSWORD` de
`.env`. Con `ENTORNO=produccion` la API no arranca si `JWT_SECRET_KEY`,
`ADMIN_PASSWORD` o `CORS_ORIGINS` tienen los valores de ejemplo; el error
dice qué variable corregir (ver `.env.example`).

## Correr con Docker

Ver [`/infrastructure`](../infrastructure/README.md). El compose levanta
Postgres (con el esquema cargado la primera vez) y la API:

```bash
cd infrastructure
JWT_SECRET_KEY=... ADMIN_PASSWORD=... docker compose up --build
```

## Autenticación

`POST /api/v1/auth/login` (form `username`/`password`, estilo OAuth2)
devuelve un JWT. Mandarlo como `Authorization: Bearer <token>`.
`POST /auth/cambiar-password` cambia la propia contraseña y cierra las demás
sesiones de esa cuenta; `GET /auth/me` devuelve el usuario de la sesión.

Una cuenta con la licencia revocada recibe 403 con la cabecera
`X-License-Revoked: true` en cualquier ruta que exija sesión; el frontend
la usa para mostrar la pantalla de licencia revocada.

Roles (`usuarios.rol`, ver `app/schemas/usuario.py`):

| Rol | Puede |
|---|---|
| `AdminGeneral` | Todo. Pasa cualquier chequeo de rol y de torneo asignado (`require_roles`). Es el único que gestiona usuarios, licencias, la bitácora de accesos, la auditoría y los catálogos compartidos (disciplinas, modalidades, tipos de evento). |
| `TorneoAdmin` | Equipos, jugadores y perfiles; dentro de **los torneos que tiene asignados** (`ASIGNACION_TORNEO_ADMIN`): torneo, fixture, sorteo, inscripciones, plantillas, traspasos, partidos, cierre y reapertura. Otro torneo responde 403. |
| `Arbitro` | El partido que tiene asignado: datos y fecha, hitos del cronómetro, convocados, eventos (goles, tarjetas, cambios) y su anulación, walkover, resultado directo y deshacer un cierre forzado. No crea ni borra partidos ni presenta reclamos. |
| `Publico` | Solo lectura, como un visitante; con sesión ve además lo que se muestra solo a usuarios logueados. |

### Qué se lee sin sesión

La mayoría de los `GET` son públicos: es lo que ve un espectador en el
portal. Algunos cambian su respuesta según haya sesión
(`get_current_user_optional`):

- Un torneo con `Publicado=false` responde 404 a un anónimo, igual que uno
  inexistente; con sesión se ve. Lo mismo sus posiciones, goleadores y
  resultados.
- Los jugadores salen sin cédula ni correo para un anónimo.

Exigen sesión: `/auth/me`, `/usuarios/*`, `/accesos`, `/auditoria`,
`/equipos/{id}/plantilla-base*`, `/torneos/{id}/estado-fase`,
`/torneos/{id}/podio-llave` y `/partidos/{id}/preflight-inicio`.

Escribir (`POST`/`PUT`/`PATCH`/`DELETE`) siempre exige sesión y el rol de
la tabla. La matriz completa por rol y ruta la verifica
`tests/test_matriz_permisos.py`.

**No hay `DELETE` físico.** El comentario en `02_constraints.sql` es
explícito: 6 FK tienen `ON DELETE CASCADE`, así que un `DELETE` real sobre
`torneo` arrastraría inscripciones, partidos y eventos. Los endpoints
`DELETE` de esta API hacen borrado lógico (`estado='Inactivo'` o
`'Cancelado'` según la tabla).

## Endpoints

Todos bajo `/api/v1`. La referencia completa, con esquemas, está en
http://localhost:8000/docs.

| Grupo | Rutas | Escribe |
|---|---|---|
| Sesión | `/auth/login`, `/auth/me`, `/auth/cambiar-password` | cualquier usuario |
| Catálogos compartidos | `/disciplinas` (y `/con-modalidades`, `/con-partidos`), `/modalidades`, `/eventos` (tipos de evento) | AdminGeneral |
| Torneos | `/torneos`, `/torneo-grupos`, `/grupos/equipos/{id}` | TorneoAdmin |
| Motor de formatos | `/torneos/{id}/fixture`, `/sorteo`, `/playoffs`, `/bracket`, `/estado-fase`, `/podio-llave`, `/cerrar`, `/reabrir` | TorneoAdmin |
| Equipos y jugadores | `/equipos`, `/equipos/{id}/plantilla-base`, `/jugadores`, `/jugadores/{id}/perfil`, `/perfiles` | TorneoAdmin |
| Participación | `/inscripciones`, `/plantillas` (y `/plantillas/lote/validar`, `/confirmar`), `/traspasos` | TorneoAdmin |
| Partidos | `/partidos`, `/partidos/feed`; por partido: `/cronometro`, `/duracion`, `/hitos`, `/convocados`, `/preflight-inicio`, `/walkover`, `/resultado-directo`, `/reclamo`, `/deshacer-cierre-forzado` | TorneoAdmin; el Arbitro asignado todo salvo crear, borrar y `/reclamo` |
| Eventos de partido | `/eventos-partido`, `/eventos-partido/{id}/anular` | TorneoAdmin, Arbitro |
| Estadísticas | `/estadisticas/torneos/{id}/posiciones`, `/goleadores`, `/resultados`; `/estadisticas/proximos-partidos`; `/estadisticas/equipos/{id}/plantilla` | — (solo lectura) |
| Administración | `/usuarios` (y `/{id}/licencia`, `/{id}/torneos`), `/accesos`, `/auditoria` | AdminGeneral |
| Salud | `/health` (fuera de `/api/v1`) | — |

Los listados aceptan `skip`/`limit` y devuelven el total en la cabecera
`X-Total-Count`; varios aceptan `q` (búsqueda) e `ids=1,2,3` (hasta 200).

## Tests

```bash
pytest
```

`tests/conftest.py` crea (o recrea) una base `torneos_mvp_test` aplicando los
mismos `.sql` de `/database`, y corre cada test dentro de una transacción
que se revierte al final — nunca toca `torneos_mvp`.

### Tests de concurrencia real (A2, docs/plans/cierre-pendientes-todos-plan.md)

`pytest` por default corre con `-m "not concurrencia"` (ver `verificar.ps1`):
el harness de arriba envuelve cada test en una transacción con savepoints,
así que un `session.commit()` dentro de un repositorio **no persiste de
verdad** — imposible para probar algo como un `SELECT ... FOR UPDATE` con dos
conexiones genuinamente paralelas. Para eso existe el fixture
`sesiones_paralelas`: dos `AsyncSession` independientes contra su propia base
(`torneos_mvp_test_concurrencia`, reconstruida entera antes de cada test),
donde un `commit()` sí persiste. Correlos con `pytest -m concurrencia` o
`.\verificar.ps1 -Concurrencia` desde la raíz del repo.

Test de ejemplo, copiable entero — dos sesiones intentan lockear la misma
fila con `FOR UPDATE`, la segunda espera y recibe el resultado de la primera:

```python
import asyncio

import pytest

from app.repositories.partido import PartidoRepository


@pytest.mark.concurrencia
async def test_dos_sesiones_lockean_la_misma_fila_en_serie(sesiones_paralelas):
    sesion_a, sesion_b = sesiones_paralelas

    partido_a = await PartidoRepository(sesion_a).get_or_404_bloqueado(3)
    partido_a.jornada = 99
    # Con el lock tomado por sesion_a, sesion_b tiene que ESPERAR acá —
    # esto es lo que un test contra la base compartida no puede probar.
    async with asyncio.timeout(5):
        partido_b_fut = asyncio.ensure_future(
            PartidoRepository(sesion_b).get_or_404_bloqueado(3)
        )
        await asyncio.sleep(0.2)
        assert not partido_b_fut.done()  # sesion_b sigue esperando

        await sesion_a.commit()  # libera el lock
        partido_b = await partido_b_fut

    assert partido_b.jornada == 99  # ve el commit de sesion_a
    await sesion_b.commit()
```

Riesgo conocido: si las dos sesiones toman un lock en orden cruzado, el test
puede colgarse en vez de fallar — envolvé la mitad contenciosa en
`asyncio.wait_for`/`asyncio.timeout` explícito, como el ejemplo de arriba,
para que un deadlock salga como fallo con mensaje.

### Regla de nombres de parámetros de query

Sustantivos de dominio en español (`disciplina_id`, `estado`, `alcance`),
primitivas de paginación/búsqueda en inglés (`skip`, `limit`, `q`) — el repo
ya mezcla los dos por convención, no por descuido; el próximo parámetro
sigue la misma regla en vez de litigarla de nuevo.
