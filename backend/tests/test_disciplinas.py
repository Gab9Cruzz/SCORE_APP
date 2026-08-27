from httpx import AsyncClient


async def test_catalogo_de_disciplinas_es_publico(client: AsyncClient):
    # 05_seed.sql carga "Fútbol" (Tipo=Equipo).
    resp = await client.get("/api/v1/disciplinas")
    assert resp.status_code == 200
    nombres = {d["nombre"] for d in resp.json()}
    assert "Fútbol" in nombres


async def test_admin_crea_disciplina(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/disciplinas",
        json={"nombre": "Tenis", "tipo": "Individual"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["tipo"] == "Individual"


async def test_nombre_de_disciplina_duplicado_es_rechazado(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    # unique_disciplina_nombre (02_constraints.sql)
    resp = await client.post(
        "/api/v1/disciplinas",
        json={"nombre": "Fútbol", "tipo": "Equipo"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 409


async def test_arbitro_no_puede_crear_disciplina(client: AsyncClient, arbitro_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/disciplinas", json={"nombre": "Rugby", "tipo": "Equipo"}, headers=arbitro_headers
    )
    assert resp.status_code == 403
