from httpx import AsyncClient


async def test_listar_equipos_es_publico(client: AsyncClient):
    # 05_seed.sql carga 3 equipos.
    resp = await client.get("/api/v1/equipos")
    assert resp.status_code == 200
    assert len(resp.json()) >= 3


async def test_arbitro_no_puede_crear_equipo(client: AsyncClient, arbitro_headers: dict[str, str]):
    resp = await client.post("/api/v1/equipos", json={"nombre": "Nuevo FC"}, headers=arbitro_headers)
    assert resp.status_code == 403


async def test_admin_crea_actualiza_y_da_de_baja_equipo(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.post("/api/v1/equipos", json={"nombre": "Nuevo FC"}, headers=admin_general_headers)
    assert resp.status_code == 201
    equipo_id = resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/equipos/{equipo_id}", json={"nombre": "Nuevo FC Renombrado"}, headers=admin_general_headers
    )
    assert resp.status_code == 200
    assert resp.json()["nombre"] == "Nuevo FC Renombrado"

    resp = await client.delete(f"/api/v1/equipos/{equipo_id}", headers=admin_general_headers)
    assert resp.status_code == 200
    assert resp.json()["estado"] == "Inactivo"
