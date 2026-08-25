from httpx import AsyncClient


async def test_listar_partidos_es_publico(client: AsyncClient):
    # 05_seed.sql carga 3 partidos para el torneo 1.
    resp = await client.get("/api/v1/partidos", params={"torneo_id": 1})
    assert resp.status_code == 200
    assert len(resp.json()) == 3


async def test_arbitro_puede_programar_partido_entre_inscritos(
    client: AsyncClient, arbitro_headers: dict[str, str]
):
    # Equipos 1 y 2 ya están inscritos en el torneo 1 (05_seed.sql).
    resp = await client.post(
        "/api/v1/partidos",
        json={
            "torneo_id": 1,
            "equipos_id_local": 1,
            "equipos_id_visitante": 2,
            "fecha_partido": "2026-02-05T16:00:00",
            "jornada": 4,
        },
        headers=arbitro_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["estado"] == "Programado"


async def test_partido_con_equipo_no_inscrito_es_rechazado(
    client: AsyncClient, admin_headers: dict[str, str]
):
    # trg_partidos_validar_inscripcion (06_triggers.sql): un equipo recién
    # creado no está inscrito en el torneo 1, así que el partido debe fallar.
    resp = await client.post("/api/v1/equipos", json={"nombre": "Equipo Sin Inscribir"}, headers=admin_headers)
    equipo_id = resp.json()["id"]

    resp = await client.post(
        "/api/v1/partidos",
        json={
            "torneo_id": 1,
            "equipos_id_local": equipo_id,
            "equipos_id_visitante": 1,
            "fecha_partido": "2026-02-10T16:00:00",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 400
    assert "inscrit" in resp.json()["detail"].lower()


async def test_mismo_equipo_local_y_visitante_es_rechazado(
    client: AsyncClient, admin_headers: dict[str, str]
):
    resp = await client.post(
        "/api/v1/partidos",
        json={
            "torneo_id": 1,
            "equipos_id_local": 1,
            "equipos_id_visitante": 1,
            "fecha_partido": "2026-02-11T16:00:00",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 422
