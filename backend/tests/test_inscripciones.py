from httpx import AsyncClient


async def test_listar_inscripciones_es_publico(client: AsyncClient):
    resp = await client.get("/api/v1/inscripciones", params={"torneo_id": 1})
    assert resp.status_code == 200
    assert len(resp.json()) == 3  # 05_seed.sql inscribe a los 3 equipos


async def test_admin_inscribe_equipo_nuevo(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.post("/api/v1/equipos", json={"nombre": "Equipo Nuevo Inscripcion"}, headers=admin_general_headers)
    equipo_id = resp.json()["id"]

    resp = await client.post(
        "/api/v1/inscripciones", json={"torneo_id": 1, "equipo_id": equipo_id}, headers=admin_general_headers
    )
    assert resp.status_code == 201
    assert resp.json()["estado"] == "Inscrito"


async def test_doble_inscripcion_es_rechazada(client: AsyncClient, admin_general_headers: dict[str, str]):
    # unique_inscripcion (02_constraints.sql): el equipo 1 ya está inscrito
    # en el torneo 1 por 05_seed.sql.
    resp = await client.post(
        "/api/v1/inscripciones", json={"torneo_id": 1, "equipo_id": 1}, headers=admin_general_headers
    )
    assert resp.status_code == 409
