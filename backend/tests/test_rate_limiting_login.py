"""Rate limiting de login (3B-14, docs/plans/cierre-backlog-todos-plan.md):
5 fallos de credenciales (settings.login_rate_limit_intentos, default) por
(username, IP) en los últimos 15 minutos (settings.login_rate_limit_ventana_minutos)
bloquea el siguiente intento con 429."""
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.acceso import Acceso

UMBRAL = get_settings().login_rate_limit_intentos


async def _fallar_login(client: AsyncClient, username: str, ip: str) -> None:
    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": "lo-que-sea-mal"},
        headers={"X-Forwarded-For": ip},
    )
    assert resp.status_code == 401, resp.text


async def test_bloquea_tras_el_umbral_de_fallos(client: AsyncClient):
    for _ in range(UMBRAL):
        await _fallar_login(client, "rl_bloqueo", "203.0.113.10")

    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "rl_bloqueo", "password": "lo-que-sea-mal"},
        headers={"X-Forwarded-For": "203.0.113.10"},
    )
    assert resp.status_code == 429, resp.text
    assert "Retry-After" in resp.headers
    assert int(resp.headers["Retry-After"]) > 0
    assert "intentos" in resp.json()["detail"].lower()


async def test_bloquea_incluso_con_la_contrasena_correcta(
    client: AsyncClient, admin_general_headers: dict[str, str], db_session: AsyncSession
):
    """El bloqueo es por (username, IP), no por si la contraseña de ESTE
    intento en particular era correcta — si no, alcanzaría con probar la
    contraseña real al final para saltarse el rate limit."""
    # admin_general_test ya existe (fixture) — se agotan sus intentos con
    # contraseña mala y después se prueba con la que SÍ es válida.
    for _ in range(UMBRAL):
        await _fallar_login(client, "admin_general_test", "203.0.113.11")

    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "admin_general_test", "password": "adminpass123"},
        headers={"X-Forwarded-For": "203.0.113.11"},
    )
    assert resp.status_code == 429, resp.text


async def test_no_bloquea_otra_ip_con_el_mismo_username(client: AsyncClient):
    for _ in range(UMBRAL):
        await _fallar_login(client, "rl_otra_ip", "203.0.113.20")

    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "rl_otra_ip", "password": "lo-que-sea-mal"},
        headers={"X-Forwarded-For": "203.0.113.21"},
    )
    assert resp.status_code == 401, resp.text  # credenciales, no 429


async def test_no_bloquea_otro_username_desde_la_misma_ip(client: AsyncClient):
    for _ in range(UMBRAL):
        await _fallar_login(client, "rl_un_username", "203.0.113.30")

    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "rl_otro_username", "password": "lo-que-sea-mal"},
        headers={"X-Forwarded-For": "203.0.113.30"},
    )
    assert resp.status_code == 401, resp.text


async def test_intento_bloqueado_no_extiende_el_bloqueo_a_si_mismo(
    client: AsyncClient, db_session: AsyncSession
):
    """El intento que llega DURANTE el bloqueo se registra con
    motivo='bloqueado', no 'credenciales' — si contara para el umbral, el
    bloqueo se extendería solo cada vez que alguien reintenta."""
    for _ in range(UMBRAL):
        await _fallar_login(client, "rl_no_se_extiende", "203.0.113.40")

    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "rl_no_se_extiende", "password": "x"},
        headers={"X-Forwarded-For": "203.0.113.40"},
    )
    assert resp.status_code == 429

    result = await db_session.execute(
        select(Acceso).where(Acceso.username == "rl_no_se_extiende").order_by(Acceso.id)
    )
    filas = list(result.scalars().all())
    assert len(filas) == UMBRAL + 1
    assert [f.motivo for f in filas] == ["credenciales"] * UMBRAL + ["bloqueado"]


async def test_menos_del_umbral_no_bloquea(client: AsyncClient):
    for _ in range(UMBRAL - 1):
        await _fallar_login(client, "rl_casi", "203.0.113.50")

    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "rl_casi", "password": "x"},
        headers={"X-Forwarded-For": "203.0.113.50"},
    )
    assert resp.status_code == 401, resp.text  # todavía credenciales, no 429
