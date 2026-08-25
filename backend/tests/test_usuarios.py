from httpx import AsyncClient


async def test_listar_usuarios_requiere_admin(client: AsyncClient):
    resp = await client.get("/api/v1/usuarios")
    assert resp.status_code == 401


async def test_arbitro_no_puede_gestionar_usuarios(client: AsyncClient, arbitro_headers: dict[str, str]):
    resp = await client.get("/api/v1/usuarios", headers=arbitro_headers)
    assert resp.status_code == 403


async def test_admin_crea_y_lista_usuarios(client: AsyncClient, admin_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/usuarios",
        json={"username": "Nuevo_Arbitro", "nombre": "Nuevo Árbitro", "password": "clave12345", "rol": "Arbitro"},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    # chk_usuarios_username_lower: se normaliza a minúsculas antes de guardar.
    assert body["username"] == "nuevo_arbitro"
    assert "password" not in body
    assert "password_hash" not in body

    resp = await client.get("/api/v1/usuarios", headers=admin_headers)
    assert resp.status_code == 200
    usernames = [u["username"] for u in resp.json()]
    assert "nuevo_arbitro" in usernames


async def test_password_corta_es_rechazada(client: AsyncClient, admin_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/usuarios",
        json={"username": "corto", "nombre": "Corto", "password": "123", "rol": "Publico"},
        headers=admin_headers,
    )
    assert resp.status_code == 422
