from httpx import AsyncClient


async def test_listar_torneos_es_publico(client: AsyncClient):
    # 05_seed.sql carga "Copa Ecotec 2026".
    resp = await client.get("/api/v1/torneos")
    assert resp.status_code == 200
    nombres = [t["nombre"] for t in resp.json()]
    assert "Copa Ecotec 2026" in nombres


async def test_crear_torneo_sin_auth_falla(client: AsyncClient):
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "nombre": "Liga Test",
            "disciplina": "Fútbol",
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-06-01",
        },
    )
    assert resp.status_code == 401


async def test_admin_crea_torneo(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "nombre": "Liga Test",
            "disciplina": "Fútbol",
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-06-01",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["estado"] == "Activo"

    resp = await client.get(f"/api/v1/torneos/{body['id']}")
    assert resp.status_code == 200


async def test_fecha_fin_anterior_a_inicio_es_rechazada(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "nombre": "Torneo Invalido",
            "disciplina": "Fútbol",
            "fecha_inicio": "2026-06-01",
            "fecha_fin": "2026-05-01",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 422


async def test_baja_logica_de_torneo(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "nombre": "Torneo A Borrar",
            "disciplina": "Fútbol",
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-06-01",
        },
        headers=admin_general_headers,
    )
    torneo_id = resp.json()["id"]

    resp = await client.delete(f"/api/v1/torneos/{torneo_id}", headers=admin_general_headers)
    assert resp.status_code == 200
    assert resp.json()["estado"] == "Inactivo"

    # Sigue existiendo (borrado lógico, no físico).
    resp = await client.get(f"/api/v1/torneos/{torneo_id}")
    assert resp.status_code == 200
    assert resp.json()["estado"] == "Inactivo"


async def test_torneo_inexistente_da_404(client: AsyncClient):
    resp = await client.get("/api/v1/torneos/999999")
    assert resp.status_code == 404
