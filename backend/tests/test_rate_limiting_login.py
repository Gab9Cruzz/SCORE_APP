"""Rate limiting de login (3B-14, docs/plans/cierre-backlog-todos-plan.md):
5 fallos de credenciales (settings.login_rate_limit_intentos, default) por
(username, IP) en los últimos 15 minutos (settings.login_rate_limit_ventana_minutos)
bloquea el siguiente intento con 429."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.usuario as usuario_service
from app.core.config import get_settings
from app.models.acceso import Acceso

UMBRAL = get_settings().login_rate_limit_intentos
UMBRAL_CUENTA = get_settings().login_rate_limit_intentos_cuenta

# ASGITransport presenta toda petición de prueba como 127.0.0.1. Las
# pruebas que necesitan IPs distintas las eligen con X-Forwarded-For, y eso
# solo vale si 127.0.0.1 es un proxy de confianza (TASK-004, SEC-01). Las
# que prueban el caso sin proxy lo apagan de nuevo con `sin_proxies`.
pytestmark = pytest.mark.usefixtures("proxy_de_confianza_local")


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


# --- TASK-004 (SEC-01, SEC-13): el contador no se puede reiniciar desde
# afuera variando el nombre de usuario ni la cabecera X-Forwarded-For. ---


async def test_variar_mayusculas_y_espacios_no_reinicia_el_contador(client: AsyncClient):
    for _ in range(UMBRAL):
        await _fallar_login(client, "rl_normaliza", "203.0.113.60")

    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "  RL_Normaliza ", "password": "lo-que-sea-mal"},
        headers={"X-Forwarded-For": "203.0.113.60"},
    )
    assert resp.status_code == 429, resp.text


async def test_el_nombre_queda_normalizado_en_accesos(client: AsyncClient, db_session: AsyncSession):
    await _fallar_login(client, "  RL_Bitacora ", "203.0.113.61")

    result = await db_session.execute(select(Acceso.username).where(Acceso.ip == "203.0.113.61"))
    assert list(result.scalars().all()) == ["rl_bitacora"]


async def test_sin_proxy_de_confianza_cambiar_x_forwarded_for_no_evita_el_bloqueo(
    client: AsyncClient, sin_proxies: None
):
    for i in range(UMBRAL):
        await _fallar_login(client, "rl_xff_falsa", f"198.51.100.{i + 1}")

    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "rl_xff_falsa", "password": "lo-que-sea-mal"},
        headers={"X-Forwarded-For": "198.51.100.200"},
    )
    assert resp.status_code == 429, resp.text


async def test_sin_proxy_de_confianza_se_registra_la_ip_de_la_conexion(
    client: AsyncClient, db_session: AsyncSession, sin_proxies: None
):
    await _fallar_login(client, "rl_ip_conexion", "198.51.100.50")

    result = await db_session.execute(select(Acceso.ip).where(Acceso.username == "rl_ip_conexion"))
    assert list(result.scalars().all()) == ["127.0.0.1"]


async def test_tope_por_cuenta_frena_un_ataque_desde_muchas_ips(client: AsyncClient):
    """Por (usuario, IP) un atacante con muchas IPs nunca llega a 5; el tope
    por cuenta, más alto, lo frena igual."""
    for i in range(UMBRAL_CUENTA):
        await _fallar_login(client, "rl_distribuido", f"192.0.2.{i + 1}")

    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "rl_distribuido", "password": "lo-que-sea-mal"},
        headers={"X-Forwarded-For": "192.0.2.250"},
    )
    assert resp.status_code == 429, resp.text


async def test_por_debajo_del_tope_por_cuenta_otra_ip_no_queda_bloqueada(client: AsyncClient):
    for i in range(UMBRAL_CUENTA - 1):
        await _fallar_login(client, "rl_distribuido_casi", f"192.0.2.{i + 1}")

    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "rl_distribuido_casi", "password": "lo-que-sea-mal"},
        headers={"X-Forwarded-For": "192.0.2.250"},
    )
    assert resp.status_code == 401, resp.text


async def test_cuenta_inexistente_tambien_verifica_un_hash(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    """Sin esto, "no existe" responde sin calcular bcrypt y es medible por
    tiempo frente a "contraseña incorrecta" (SEC-13)."""
    llamadas: list[str] = []
    original = usuario_service.verify_password

    def espia(plain: str, hashed: str) -> bool:
        llamadas.append(hashed)
        return original(plain, hashed)

    monkeypatch.setattr(usuario_service, "verify_password", espia)
    await _fallar_login(client, "rl_no_existe_nunca", "203.0.113.70")
    assert len(llamadas) == 1
