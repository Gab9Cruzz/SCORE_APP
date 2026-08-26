"""Infra de tests.

Reconstruye una base torneos_mvp_test corriendo los mismos .sql de /database
(una vez por sesión) y envuelve cada test en una transacción con savepoints
que se revierte al final (join_transaction_mode="create_savepoint") — así
un `session.commit()` dentro de un repositorio no persiste nada de verdad.
Nunca toca torneos_mvp.
"""
import asyncio
import pathlib
import sys
from collections.abc import AsyncGenerator

if sys.platform == "win32":
    # El driver de la app es psycopg (async) — ver el comentario largo en
    # .env.example sobre por qué no es asyncpg. psycopg async se niega
    # directamente a correr sobre ProactorEventLoop (el default de asyncio
    # en Windows); esto tiene que fijarse ANTES de que pytest-asyncio cree
    # el primer event loop, por eso va arriba de todo en este archivo.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import asyncpg
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import get_db
from app.main import app
from app.models.partido import Partido
from app.models.usuario import Usuario

settings = get_settings()

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DATABASE_DIR = REPO_ROOT / "database"
SQL_FILES = [
    "01_schema.sql",
    "02_constraints.sql",
    "03_indexes.sql",
    "04_views.sql",
    "05_seed.sql",
    "06_triggers.sql",
]

_test_db_url_str = settings.test_database_url or (
    settings.database_url.rsplit("/", 1)[0] + "/torneos_mvp_test"
)
_url = make_url(_test_db_url_str)
TEST_DB_NAME = _url.database
TEST_DATABASE_URL = _test_db_url_str


async def _connect(database: str) -> asyncpg.Connection:
    return await asyncpg.connect(
        host=_url.host or "localhost",
        port=_url.port or 5432,
        user=_url.username,
        password=_url.password,
        database=database,
    )


async def _recreate_test_database() -> None:
    maint = await _connect("postgres")
    try:
        await maint.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = $1 AND pid <> pg_backend_pid()",
            TEST_DB_NAME,
        )
        await maint.execute(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}"')
        await maint.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
    finally:
        await maint.close()

    test_conn = await _connect(TEST_DB_NAME)
    try:
        for filename in SQL_FILES:
            sql = (DATABASE_DIR / filename).read_text(encoding="utf-8")
            await test_conn.execute(sql)
    finally:
        await test_conn.close()


@pytest_asyncio.fixture(scope="session")
async def _test_db_ready() -> None:
    await _recreate_test_database()


@pytest_asyncio.fixture(scope="session")
async def engine(_test_db_ready):
    eng = create_async_engine(TEST_DATABASE_URL, future=True)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    connection = await engine.connect()
    trans = await connection.begin()
    session_factory = async_sessionmaker(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    session = session_factory()
    try:
        yield session
    finally:
        await session.close()
        await trans.rollback()
        await connection.close()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def _crear_usuario(session: AsyncSession, username: str, password: str, rol: str) -> Usuario:
    usuario = Usuario(
        username=username, nombre=username.title(), password_hash=hash_password(password), rol=rol
    )
    session.add(usuario)
    await session.commit()
    await session.refresh(usuario)
    return usuario


async def _login_headers(client: AsyncClient, username: str, password: str) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/login", data={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest_asyncio.fixture
async def admin_general_headers(db_session: AsyncSession, client: AsyncClient) -> dict[str, str]:
    await _crear_usuario(db_session, "admin_general_test", "adminpass123", "AdminGeneral")
    return await _login_headers(client, "admin_general_test", "adminpass123")


@pytest_asyncio.fixture
async def torneo_admin_headers(db_session: AsyncSession, client: AsyncClient) -> dict[str, str]:
    await _crear_usuario(db_session, "torneo_admin_test", "torneopass123", "TorneoAdmin")
    return await _login_headers(client, "torneo_admin_test", "torneopass123")


@pytest_asyncio.fixture
async def arbitro_headers(db_session: AsyncSession, client: AsyncClient) -> dict[str, str]:
    """Árbitro asignado al partido 3 (05_seed.sql) — el que ya usan los
    tests de eventos-partido. Para un árbitro SIN partido asignado, usar
    arbitro_no_asignado_headers (prueba el 403 del ownership-check)."""
    usuario = await _crear_usuario(db_session, "arbitro_test", "arbitropass123", "Arbitro")
    partido = await db_session.get(Partido, 3)
    partido.arbitro_id = usuario.id
    await db_session.commit()
    return await _login_headers(client, "arbitro_test", "arbitropass123")


@pytest_asyncio.fixture
async def arbitro_no_asignado_headers(db_session: AsyncSession, client: AsyncClient) -> dict[str, str]:
    """Árbitro válido pero sin ningún partido asignado."""
    await _crear_usuario(db_session, "arbitro_sin_asignar_test", "arbitropass123", "Arbitro")
    return await _login_headers(client, "arbitro_sin_asignar_test", "arbitropass123")
