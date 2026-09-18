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
- PostgreSQL con el esquema de `/database` ya aplicado (ver el README de esa
  carpeta) en una base llamada `torneos_mvp`.

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
sola un usuario Admin con `ADMIN_USERNAME` / `ADMIN_PASSWORD` de `.env`
(por defecto `admin` / `admin1234` — **cambiar antes de un entorno real**).

## Correr con Docker

Ver [`/infrastructure`](../infrastructure). La API corre en contenedor y se
conecta al Postgres que ya tenés corriendo en el host:

```bash
cd infrastructure
docker compose up --build
```

## Autenticación

`POST /api/v1/auth/login` (form `username`/`password`, estilo OAuth2)
devuelve un JWT. Mandarlo como `Authorization: Bearer <token>`.

Roles (`usuarios.rol`, ver `database/02_constraints.sql`):

| Rol       | Puede |
|-----------|-------|
| `Admin`   | Todo: torneos, equipos, jugadores, plantillas, inscripciones, catálogo de eventos, usuarios |
| `Arbitro` | Programar/actualizar partidos, registrar y anular eventos de partido (goles, tarjetas, cambios) |
| `Publico` | Solo lectura (igual que un visitante sin login) |

Todos los `GET` son públicos, sin token — es lo que ve cualquier
espectador. Escribir (`POST`/`PATCH`/`DELETE`) requiere login y el rol
adecuado.

**No hay `DELETE` físico.** El comentario en `02_constraints.sql` es
explícito: 6 FK tienen `ON DELETE CASCADE`, así que un `DELETE` real sobre
`torneo` arrastraría inscripciones, partidos y eventos. Los endpoints
`DELETE` de esta API hacen borrado lógico (`estado='Inactivo'` o
`'Cancelado'` según la tabla).

## Endpoints principales

- `/torneos`, `/equipos`, `/jugadores`, `/eventos` (catálogo) — CRUD + baja lógica
- `/partidos` — programar partidos (valida inscripción de ambos equipos)
- `/inscripciones` — inscribir/cancelar un equipo en un torneo
- `/plantillas` — altas/bajas de jugadores en un equipo (dorsal)
- `/eventos-partido` — goles, tarjetas, cambios dentro de un partido
- `/usuarios` — gestión de cuentas (solo Admin)
- `/estadisticas/torneos/{id}/posiciones` — tabla de posiciones
- `/estadisticas/torneos/{id}/goleadores` — goleadores
- `/estadisticas/torneos/{id}/resultados` — resultados de partidos
- `/estadisticas/proximos-partidos` — próximos partidos programados
- `/estadisticas/equipos/{id}/plantilla` — plantilla vigente de un equipo

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
