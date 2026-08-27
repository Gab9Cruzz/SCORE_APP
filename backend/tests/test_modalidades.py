from httpx import AsyncClient

DISCIPLINA_FUTBOL_ID = 1


async def test_listar_modalidades_es_publico(client: AsyncClient):
    # 05_seed.sql no carga ninguna modalidad (Fútbol es Tipo=Equipo, no
    # las necesita) — solo confirma que el endpoint responde 200 vacío.
    resp = await client.get("/api/v1/modalidades")
    assert resp.status_code == 200


async def test_admin_crea_modalidad(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/disciplinas",
        json={"nombre": "Pádel", "tipo": "Individual"},
        headers=admin_general_headers,
    )
    disciplina_id = resp.json()["id"]

    resp = await client.post(
        "/api/v1/modalidades",
        json={"disciplina_id": disciplina_id, "nombre": "Dobles", "tamano_equipo": 2},
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["tamano_equipo"] == 2


async def test_tamano_equipo_no_positivo_es_rechazado(client: AsyncClient, admin_general_headers: dict[str, str]):
    # chk_modalidad_tamano: CHECK (Tamano_Equipo > 0) — validado también en
    # el schema de Pydantic, así que esto da 422, no 400.
    resp = await client.post(
        "/api/v1/modalidades",
        json={"disciplina_id": DISCIPLINA_FUTBOL_ID, "nombre": "Inválida", "tamano_equipo": 0},
        headers=admin_general_headers,
    )
    assert resp.status_code == 422


async def test_arbitro_no_puede_crear_modalidad(client: AsyncClient, arbitro_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/modalidades",
        json={"disciplina_id": DISCIPLINA_FUTBOL_ID, "nombre": "Individual", "tamano_equipo": 1},
        headers=arbitro_headers,
    )
    assert resp.status_code == 403
