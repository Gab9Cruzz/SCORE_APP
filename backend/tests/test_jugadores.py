from httpx import AsyncClient


async def test_listar_jugadores_es_publico(client: AsyncClient):
    # 05_seed.sql carga 6 jugadores.
    resp = await client.get("/api/v1/jugadores")
    assert resp.status_code == 200
    assert len(resp.json()) >= 6


async def test_admin_crea_jugador(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.post("/api/v1/jugadores", json={"nombre": "Jugador Nuevo"}, headers=admin_general_headers)
    assert resp.status_code == 201
    assert resp.json()["estado"] == "Activo"
