from httpx import AsyncClient

DISCIPLINA_FUTBOL_ID = 1


async def test_listar_perfiles_es_publico(client: AsyncClient):
    # 05_seed.sql crea un perfil de Fútbol para cada uno de los 6 jugadores.
    resp = await client.get("/api/v1/perfiles")
    assert resp.status_code == 200
    assert len(resp.json()) >= 6


async def test_admin_crea_perfil(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/jugadores",
        json={"nombre": "Jugador Perfil", "cedula": "0977000001", "correo_electronico": "jp@example.com"},
        headers=admin_general_headers,
    )
    jugador_id = resp.json()["id"]

    resp = await client.post(
        "/api/v1/perfiles",
        json={"jugador_id": jugador_id, "disciplina_id": DISCIPLINA_FUTBOL_ID},
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["suspendido"] is False


async def test_perfil_duplicado_en_misma_disciplina_es_rechazado(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    # unique_perfil_por_disciplina (02_constraints.sql): el jugador 1 ya
    # tiene perfil de Fútbol (05_seed.sql).
    resp = await client.post(
        "/api/v1/perfiles",
        json={"jugador_id": 1, "disciplina_id": DISCIPLINA_FUTBOL_ID},
        headers=admin_general_headers,
    )
    assert resp.status_code == 409


async def test_admin_suspende_un_perfil(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.patch(
        "/api/v1/perfiles/1",
        json={"suspendido": True},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["suspendido"] is True


async def test_arbitro_no_puede_crear_perfil(client: AsyncClient, arbitro_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/perfiles", json={"jugador_id": 1, "disciplina_id": DISCIPLINA_FUTBOL_ID}, headers=arbitro_headers
    )
    assert resp.status_code == 403
