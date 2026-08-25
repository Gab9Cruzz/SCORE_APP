"""Login y /auth/me. El primer Admin de estos tests lo crea el fixture
admin_headers (conftest.py), no el bootstrap de app/main.py: ASGITransport
no dispara el lifespan de la app salvo que se pida explícitamente."""
from httpx import AsyncClient


async def test_login_credenciales_invalidas(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/login", data={"username": "no-existe", "password": "lo-que-sea"}
    )
    assert resp.status_code == 401


async def test_login_ok_y_me(client: AsyncClient, admin_headers: dict[str, str]):
    resp = await client.get("/api/v1/auth/me", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "admin_test"
    assert body["rol"] == "Admin"


async def test_me_sin_token(client: AsyncClient):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
