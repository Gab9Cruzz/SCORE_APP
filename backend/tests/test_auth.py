"""Login y /auth/me. El primer AdminGeneral de estos tests lo crea el
fixture admin_general_headers (conftest.py), no el bootstrap de
app/main.py: ASGITransport no dispara el lifespan de la app salvo que se
pida explícitamente."""
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.acceso import Acceso
from app.models.usuario import Usuario


async def test_login_credenciales_invalidas(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/login", data={"username": "no-existe", "password": "lo-que-sea"}
    )
    assert resp.status_code == 401


async def test_login_ok_y_me(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.get("/api/v1/auth/me", headers=admin_general_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "admin_general_test"
    assert body["rol"] == "AdminGeneral"


async def test_me_sin_token(client: AsyncClient):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


# --- Licencia (rbac-licencias-torneos-plan.md, §4.2/§9) ---


async def test_login_con_licencia_revocada_es_rechazado(client: AsyncClient, db_session: AsyncSession):
    """403 (no 401): la contraseña es correcta, lo que falta es
    autorización de nivel superior — mismo criterio que separa AuthError
    de LicenseRevokedError en exceptions/errors.py. Clon estructural de
    test_login_credenciales_invalidas pero para el motivo 'inactivo'/
    'licencia_revocada', no 'credenciales'."""
    usuario = Usuario(
        username="sin_licencia_test",
        nombre="Sin Licencia",
        password_hash=hash_password("sinlicencia123"),
        rol="TorneoAdmin",
        licencia_activa=False,
    )
    db_session.add(usuario)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/auth/login", data={"username": "sin_licencia_test", "password": "sinlicencia123"}
    )
    assert resp.status_code == 403
    assert resp.headers.get("X-License-Revoked") == "true"
    assert "Licencia" in resp.json()["detail"]


async def test_login_con_licencia_revocada_queda_en_bitacora_de_accesos(
    client: AsyncClient, db_session: AsyncSession
):
    """Corrección post outside-voice (Eng review): el rechazo por licencia
    debe escribir en ACCESOS igual que 'credenciales'/'inactivo'/
    'bloqueado' — sin esto, el intento desaparecería silenciosamente de la
    bitácora de auditoría de accesos."""
    usuario = Usuario(
        username="sin_licencia_bitacora_test",
        nombre="Sin Licencia Bitacora",
        password_hash=hash_password("sinlicencia123"),
        rol="TorneoAdmin",
        licencia_activa=False,
    )
    db_session.add(usuario)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "sin_licencia_bitacora_test", "password": "sinlicencia123"},
    )
    assert resp.status_code == 403

    result = await db_session.execute(
        select(Acceso).where(Acceso.username == "sin_licencia_bitacora_test")
    )
    fila = result.scalar_one()
    assert fila.exitoso is False
    assert fila.motivo == "licencia_revocada"


async def test_sesion_activa_licencia_revocada_a_mitad_rechaza_de_inmediato(
    client: AsyncClient, admin_general_headers: dict[str, str], db_session: AsyncSession
):
    """El token JWT no lleva claim de licencia (core/security.py) — el
    próximo request de una cuenta ya logueada debe devolver 403 apenas se
    le revoca la licencia, SIN esperar a que el token expire. Prueba que
    `get_current_user` lee Licencia_Activa fresco en cada request, no
    desde el token."""
    resp = await client.get("/api/v1/auth/me", headers=admin_general_headers)
    assert resp.status_code == 200

    result = await db_session.execute(select(Usuario).where(Usuario.username == "admin_general_test"))
    usuario = result.scalar_one()
    usuario.licencia_activa = False
    await db_session.commit()

    resp = await client.get("/api/v1/auth/me", headers=admin_general_headers)
    assert resp.status_code == 403
    assert resp.headers.get("X-License-Revoked") == "true"
