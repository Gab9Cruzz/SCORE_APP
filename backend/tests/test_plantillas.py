from httpx import AsyncClient


async def test_listar_plantilla_de_equipo(client: AsyncClient):
    # 05_seed.sql pone a los jugadores 1 y 2 en el equipo 1.
    resp = await client.get("/api/v1/plantillas", params={"equipo_id": 1})
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_admin_da_de_alta_jugador_en_equipo(client: AsyncClient, admin_headers: dict[str, str]):
    resp = await client.post("/api/v1/jugadores", json={"nombre": "Fichaje Nuevo"}, headers=admin_headers)
    jugador_id = resp.json()["id"]

    resp = await client.post(
        "/api/v1/plantillas",
        json={"jugador_id": jugador_id, "equipo_id": 1, "dorsal": 99, "fecha_inicio": "2026-02-01"},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["dorsal"] == 99


async def test_dorsal_repetido_en_equipo_vigente_es_rechazado(
    client: AsyncClient, admin_headers: dict[str, str]
):
    # uq_dorsal_por_equipo_vigente (03_indexes.sql): el dorsal 10 en el
    # equipo 1 ya lo tiene Carlos Pérez (05_seed.sql).
    resp = await client.post("/api/v1/jugadores", json={"nombre": "Otro Jugador"}, headers=admin_headers)
    jugador_id = resp.json()["id"]

    resp = await client.post(
        "/api/v1/plantillas",
        json={"jugador_id": jugador_id, "equipo_id": 1, "dorsal": 10, "fecha_inicio": "2026-02-01"},
        headers=admin_headers,
    )
    assert resp.status_code == 409
