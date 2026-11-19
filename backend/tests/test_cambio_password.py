"""TASK-033 (FUN-13, SEC-03, SEC-14): cambio de contraseña propio e
invalidación de sesiones."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.reloj import ahora_negocio
from app.core.security import marca_en_ms, token_revocado
from app.models.acceso import Acceso
from tests.conftest import _crear_usuario, _login_headers

RUTA = "/api/v1/auth/cambiar-password"


async def _login(client: AsyncClient, username: str, password: str) -> int:
    resp = await client.post("/api/v1/auth/login", data={"username": username, "password": password})
    return resp.status_code


async def test_cambia_su_password_conociendo_la_actual(client: AsyncClient, db_session: AsyncSession):
    await _crear_usuario(db_session, "cambia_ok", "clave-vieja-123", "Arbitro")
    headers = await _login_headers(client, "cambia_ok", "clave-vieja-123")

    resp = await client.post(
        RUTA, json={"password_actual": "clave-vieja-123", "password_nueva": "clave-nueva-456"}, headers=headers
    )

    assert resp.status_code == 200, resp.text
    nuevo = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    me = await client.get("/api/v1/auth/me", headers=nuevo)
    assert me.status_code == 200
    assert me.json()["username"] == "cambia_ok"
    assert await _login(client, "cambia_ok", "clave-nueva-456") == 200
    assert await _login(client, "cambia_ok", "clave-vieja-123") == 401


async def test_token_anterior_al_cambio_devuelve_401(client: AsyncClient, db_session: AsyncSession):
    await _crear_usuario(db_session, "cambia_sesiones", "clave-vieja-123", "TorneoAdmin")
    otra_sesion = await _login_headers(client, "cambia_sesiones", "clave-vieja-123")
    esta_sesion = await _login_headers(client, "cambia_sesiones", "clave-vieja-123")

    resp = await client.post(
        RUTA, json={"password_actual": "clave-vieja-123", "password_nueva": "clave-nueva-456"}, headers=esta_sesion
    )
    assert resp.status_code == 200

    assert (await client.get("/api/v1/auth/me", headers=otra_sesion)).status_code == 401
    # La sesión desde la que se cambió también: el cliente reemplaza su token
    # por el que devuelve el cambio.
    assert (await client.get("/api/v1/auth/me", headers=esta_sesion)).status_code == 401


async def test_actual_incorrecta_da_400_y_queda_en_accesos(client: AsyncClient, db_session: AsyncSession):
    usuario_id = (await _crear_usuario(db_session, "cambia_mal", "clave-vieja-123", "Publico")).id
    headers = await _login_headers(client, "cambia_mal", "clave-vieja-123")

    resp = await client.post(
        RUTA, json={"password_actual": "no-es-esta-123", "password_nueva": "clave-nueva-456"}, headers=headers
    )

    assert resp.status_code == 400
    assert "actual" in resp.json()["detail"]
    db_session.expire_all()
    accesos = (
        (await db_session.execute(select(Acceso).where(Acceso.username == "cambia_mal").order_by(Acceso.id)))
        .scalars()
        .all()
    )
    assert [(a.exitoso, a.motivo, a.usuario_id) for a in accesos][-1] == (False, "cambio_password", usuario_id)
    # No cambió nada: la sesión sigue y la contraseña vieja sirve.
    assert (await client.get("/api/v1/auth/me", headers=headers)).status_code == 200
    assert await _login(client, "cambia_mal", "clave-vieja-123") == 200


async def test_el_admin_general_cambia_su_propia_password(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.post(
        RUTA,
        json={"password_actual": "adminpass123", "password_nueva": "otra-clave-del-admin"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["rol"] == "AdminGeneral"
    assert await _login(client, "admin_general_test", "otra-clave-del-admin") == 200


async def test_sin_sesion_da_401(client: AsyncClient):
    resp = await client.post(RUTA, json={"password_actual": "x", "password_nueva": "clave-nueva-456"})
    assert resp.status_code == 401


async def test_politica_de_password_nueva(client: AsyncClient, db_session: AsyncSession):
    await _crear_usuario(db_session, "cambia_politica", "clave-vieja-123", "Publico")
    headers = await _login_headers(client, "cambia_politica", "clave-vieja-123")

    for nueva in ("corta123", "1234567890", "Contraseña123"):
        resp = await client.post(RUTA, json={"password_actual": "clave-vieja-123", "password_nueva": nueva}, headers=headers)
        assert resp.status_code == 422, nueva

    igual = await client.post(
        RUTA, json={"password_actual": "clave-vieja-123", "password_nueva": "clave-vieja-123"}, headers=headers
    )
    assert igual.status_code == 400


async def test_alta_y_edicion_aplican_la_misma_politica(client: AsyncClient, admin_general_headers: dict[str, str]):
    for password in ("nueve1234", "qwertyuiop"):
        resp = await client.post(
            "/api/v1/usuarios",
            json={"username": "politica_alta", "nombre": "P", "password": password, "rol": "Publico"},
            headers=admin_general_headers,
        )
        assert resp.status_code == 422, password


async def test_admin_cambia_la_password_de_otro_y_cierra_sus_sesiones(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    otro = await _crear_usuario(db_session, "reseteado", "clave-vieja-123", "Arbitro")
    sesion_del_otro = await _login_headers(client, "reseteado", "clave-vieja-123")

    resp = await client.patch(
        f"/api/v1/usuarios/{otro.id}", json={"password": "clave-nueva-456"}, headers=admin_general_headers
    )
    assert resp.status_code == 200

    assert (await client.get("/api/v1/auth/me", headers=sesion_del_otro)).status_code == 401
    assert await _login(client, "reseteado", "clave-nueva-456") == 200


async def test_desactivar_y_reactivar_no_revive_tokens_viejos(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    otro = await _crear_usuario(db_session, "desactivado", "clave-vieja-123", "Arbitro")
    sesion_vieja = await _login_headers(client, "desactivado", "clave-vieja-123")

    assert (await client.delete(f"/api/v1/usuarios/{otro.id}", headers=admin_general_headers)).status_code == 200
    reactivar = await client.patch(
        f"/api/v1/usuarios/{otro.id}", json={"estado": "Activo"}, headers=admin_general_headers
    )
    assert reactivar.status_code == 200

    assert (await client.get("/api/v1/auth/me", headers=sesion_vieja)).status_code == 401
    assert await _login(client, "desactivado", "clave-vieja-123") == 200


async def test_editar_otro_campo_no_cierra_sesiones(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    otro = await _crear_usuario(db_session, "renombrado", "clave-vieja-123", "Arbitro")
    sesion = await _login_headers(client, "renombrado", "clave-vieja-123")

    resp = await client.patch(f"/api/v1/usuarios/{otro.id}", json={"nombre": "Otro Nombre"}, headers=admin_general_headers)
    assert resp.status_code == 200
    assert (await client.get("/api/v1/auth/me", headers=sesion)).status_code == 200


def _payload(**extra) -> dict:
    return {"sub": "x", "rol": "Publico", **extra}


def test_token_revocado_reglas():
    ahora = ahora_negocio()
    ahora_ms = int(datetime.now(UTC).timestamp() * 1000)
    # Sin marca: todo token sirve, incluso uno sin iat (anterior a TASK-033).
    assert token_revocado(_payload(), None) is False
    # Con marca: un token sin iat no sirve.
    assert token_revocado(_payload(), ahora) is True
    # Emitido antes / después de la marca.
    assert token_revocado(_payload(iat_ms=ahora_ms - 60_000), ahora) is True
    # Mismo milisegundo que la marca: el reloj avanza a saltos y un login y
    # una baja seguidos pueden coincidir. Ese token tiene que caer.
    assert token_revocado(_payload(iat_ms=marca_en_ms(ahora)), ahora) is True
    assert token_revocado(_payload(iat_ms=marca_en_ms(ahora) + 1), ahora) is False
    assert token_revocado(_payload(iat_ms=ahora_ms + 60_000), ahora) is False
    # Solo iat (segundos), sin iat_ms.
    assert token_revocado(_payload(iat=ahora_ms // 1000 - 60), ahora) is True
    assert token_revocado(_payload(iat=ahora_ms // 1000 + 60), ahora) is False


def test_el_token_lleva_iat():
    from app.core.security import create_access_token

    settings = get_settings()
    claims = jwt.decode(
        create_access_token("x", "Publico"), settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
    )
    ahora = datetime.now(UTC)
    assert abs(claims["iat"] - ahora.timestamp()) < 5
    assert abs(claims["iat_ms"] / 1000 - ahora.timestamp()) < 5
    assert isinstance(claims["iat"], int)
    assert timedelta(seconds=claims["exp"] - claims["iat"]) > timedelta(0)
