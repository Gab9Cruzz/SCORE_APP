from httpx import AsyncClient


async def test_listar_partidos_es_publico(client: AsyncClient):
    # 05_seed.sql carga 3 partidos para el torneo 1.
    resp = await client.get("/api/v1/partidos", params={"torneo_id": 1})
    assert resp.status_code == 200
    assert len(resp.json()) == 3


async def test_arbitro_no_puede_crear_partido(client: AsyncClient, arbitro_headers: dict[str, str]):
    # D4 (roles-3-modulos-plan.md, Fase 1): crear partidos es de
    # TorneoAdmin/AdminGeneral desde esta fase — Árbitro solo carga
    # partidos que ya le asignaron.
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
    assert resp.status_code == 403


# --- require_torneo_access_de (rbac-licencias-torneos-plan.md, Fase 2) ---


async def test_torneo_admin_sin_asignacion_no_puede_crear_actualizar_ni_cancelar_partido(
    client: AsyncClient, torneo_admin_headers: dict[str, str]
):
    resp = await client.post(
        "/api/v1/partidos",
        json={
            "torneo_id": 1,
            "equipos_id_local": 1,
            "equipos_id_visitante": 2,
            "fecha_partido": "2026-02-06T16:00:00",
            "jornada": 5,
        },
        headers=torneo_admin_headers,
    )
    assert resp.status_code == 403
    assert "asignado" in resp.json()["detail"]

    resp = await client.patch("/api/v1/partidos/1", json={"jornada": 2}, headers=torneo_admin_headers)
    assert resp.status_code == 403

    resp = await client.delete("/api/v1/partidos/1", headers=torneo_admin_headers)
    assert resp.status_code == 403


async def test_torneo_admin_puede_programar_partido_entre_inscritos(
    client: AsyncClient, torneo_admin_con_torneo_headers: dict[str, str]
):
    # Equipos 1 y 2 ya están inscritos en el torneo 1 (05_seed.sql).
    # torneo_admin_con_torneo_headers está asignado a ese torneo
    # (rbac-licencias-torneos-plan.md, Fase 2).
    resp = await client.post(
        "/api/v1/partidos",
        json={
            "torneo_id": 1,
            "equipos_id_local": 1,
            "equipos_id_visitante": 2,
            "fecha_partido": "2026-02-05T16:00:00",
            "jornada": 4,
        },
        headers=torneo_admin_con_torneo_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["estado"] == "Programado"


async def test_partido_con_equipo_no_inscrito_es_rechazado(
    client: AsyncClient, torneo_admin_con_torneo_headers: dict[str, str]
):
    # trg_partidos_validar_inscripcion (06_triggers.sql): un equipo recién
    # creado no está inscrito en el torneo 1, así que el partido debe fallar.
    resp = await client.post(
        "/api/v1/equipos", json={"nombre": "Equipo Sin Inscribir", "disciplina_id": 1, "modalidad_id": 1}, headers=torneo_admin_con_torneo_headers
    )
    equipo_id = resp.json()["id"]

    resp = await client.post(
        "/api/v1/partidos",
        json={
            "torneo_id": 1,
            "equipos_id_local": equipo_id,
            "equipos_id_visitante": 1,
            "fecha_partido": "2026-02-10T16:00:00",
        },
        headers=torneo_admin_con_torneo_headers,
    )
    assert resp.status_code == 400
    assert "inscrit" in resp.json()["detail"].lower()


async def test_mismo_equipo_local_y_visitante_es_rechazado(
    client: AsyncClient, torneo_admin_headers: dict[str, str]
):
    resp = await client.post(
        "/api/v1/partidos",
        json={
            "torneo_id": 1,
            "equipos_id_local": 1,
            "equipos_id_visitante": 1,
            "fecha_partido": "2026-02-11T16:00:00",
        },
        headers=torneo_admin_headers,
    )
    assert resp.status_code == 422


async def test_arbitro_puede_actualizar_su_partido_asignado(
    client: AsyncClient, arbitro_headers: dict[str, str]
):
    # arbitro_headers (conftest.py) queda asignado al partido 3.
    resp = await client.patch(
        "/api/v1/partidos/3", json={"estado": "En curso"}, headers=arbitro_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["estado"] == "En curso"


async def test_arbitro_no_puede_actualizar_partido_no_asignado(
    client: AsyncClient, arbitro_no_asignado_headers: dict[str, str]
):
    resp = await client.patch(
        "/api/v1/partidos/1", json={"estado": "En curso"}, headers=arbitro_no_asignado_headers
    )
    assert resp.status_code == 403
    assert "asignado" in resp.json()["detail"].lower()


async def test_torneo_admin_puede_actualizar_cualquier_partido(
    client: AsyncClient, torneo_admin_con_torneo_headers: dict[str, str]
):
    # TorneoAdmin no pasa por el ownership-check de Árbitro (D5) — pero SÍ
    # necesita asignación al torneo del partido (rbac-licencias-torneos-plan.md,
    # Fase 2); torneo_admin_con_torneo_headers está asignado al Torneo 1
    # (partido 1 pertenece a ese torneo).
    resp = await client.patch(
        "/api/v1/partidos/1", json={"jornada": 9}, headers=torneo_admin_con_torneo_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["jornada"] == 9


async def test_filtrar_partidos_por_arbitro_id(client: AsyncClient, arbitro_headers: dict[str, str]):
    # roles-3-modulos-plan.md Fase 3, D1: arbitro_headers (conftest.py)
    # queda asignado al partido 3, único de los 3 del seed con ese árbitro.
    me = await client.get("/api/v1/auth/me", headers=arbitro_headers)
    arbitro_id = me.json()["id"]

    resp = await client.get("/api/v1/partidos", params={"arbitro_id": arbitro_id})
    assert resp.status_code == 200, resp.text
    partidos = resp.json()
    assert len(partidos) == 1
    assert partidos[0]["id"] == 3
    assert partidos[0]["arbitro_id"] == arbitro_id

    # Público, sin auth — el filtro no exige estar logueado (D1).
    resp_sin_id = await client.get("/api/v1/partidos", params={"torneo_id": 1})
    assert len(resp_sin_id.json()) == 3  # sin arbitro_id, siguen los 3 del seed


async def test_filtrar_partidos_por_arbitro_id_y_estado_combinados(
    client: AsyncClient, arbitro_headers: dict[str, str]
):
    # BaseRepository.list combina todos los filtros con AND — el partido 3
    # (seed) nace en Estado='Programado'.
    me = await client.get("/api/v1/auth/me", headers=arbitro_headers)
    arbitro_id = me.json()["id"]

    resp = await client.get(
        "/api/v1/partidos", params={"arbitro_id": arbitro_id, "estado": "Programado"}
    )
    assert resp.status_code == 200, resp.text
    assert [p["id"] for p in resp.json()] == [3]

    resp_vacio = await client.get(
        "/api/v1/partidos", params={"arbitro_id": arbitro_id, "estado": "Finalizado"}
    )
    assert resp_vacio.json() == []
