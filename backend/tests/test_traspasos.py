from httpx import AsyncClient

# 05_seed.sql: inscripcion 1 = Tiburones FC (torneo 1), inscripcion 2 =
# Águilas del Sur (torneo 1). Carlos Pérez (perfil 1, jugador 1) está
# Activo en la inscripcion 1, dorsal 10.
INSCRIPCION_TIBURONES = 1
INSCRIPCION_AGUILAS = 2


async def _perfil_de_carlos(client: AsyncClient) -> int:
    resp = await client.get("/api/v1/perfiles", params={"jugador_id": 1, "disciplina_id": 1})
    return resp.json()[0]["id"]


async def test_traspaso_normal_cierra_origen_y_abre_destino(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    perfil_id = await _perfil_de_carlos(client)

    resp = await client.post(
        "/api/v1/traspasos",
        json={
            "jugador_perfil_id": perfil_id,
            "inscripcion_origen_id": INSCRIPCION_TIBURONES,
            "inscripcion_destino_id": INSCRIPCION_AGUILAS,
            "dorsal_nuevo": 99,
            "motivo": "Prueba de traspaso",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["estado"] == "Completado"
    assert body["inscripcion_origen_id"] == INSCRIPCION_TIBURONES
    assert body["inscripcion_destino_id"] == INSCRIPCION_AGUILAS

    resp = await client.get("/api/v1/plantillas", params={"inscripcion_torneo_id": INSCRIPCION_TIBURONES})
    fila_origen = next(f for f in resp.json() if f["jugador_perfil_id"] == perfil_id)
    assert fila_origen["estado"] == "Traspasado"
    assert fila_origen["fecha_fin"] is not None

    resp = await client.get("/api/v1/plantillas", params={"inscripcion_torneo_id": INSCRIPCION_AGUILAS})
    fila_destino = next(f for f in resp.json() if f["jugador_perfil_id"] == perfil_id)
    assert fila_destino["estado"] == "Activo"
    assert fila_destino["dorsal"] == 99


async def test_filtrar_traspasos_por_torneo(client: AsyncClient, admin_general_headers: dict[str, str]):
    # torneo_id filtra por el torneo del equipo DESTINO (D-Eng-3 del plan:
    # el GET no filtraba nada antes de esto).
    perfil_id = await _perfil_de_carlos(client)
    resp = await client.post(
        "/api/v1/traspasos",
        json={
            "jugador_perfil_id": perfil_id,
            "inscripcion_origen_id": INSCRIPCION_TIBURONES,
            "inscripcion_destino_id": INSCRIPCION_AGUILAS,
            "dorsal_nuevo": 55,
            "motivo": "Prueba filtro por torneo",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    traspaso_id = resp.json()["id"]

    # Águilas del Sur (destino) es del torneo 1, igual que Tiburones (05_seed.sql).
    resp = await client.get("/api/v1/traspasos", params={"torneo_id": 1})
    assert resp.status_code == 200
    assert any(t["id"] == traspaso_id for t in resp.json())

    resp = await client.get("/api/v1/traspasos", params={"torneo_id": 999999})
    assert resp.status_code == 200
    assert resp.json() == []


async def test_traspaso_desde_libre_sin_origen(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/jugadores",
        json={"nombre": "Libre Traspaso", "cedula": "0966000001", "correo_electronico": "lt@example.com"},
        headers=admin_general_headers,
    )
    jugador_id = resp.json()["id"]
    resp = await client.post(
        "/api/v1/perfiles", json={"jugador_id": jugador_id, "disciplina_id": 1}, headers=admin_general_headers
    )
    perfil_id = resp.json()["id"]

    resp = await client.post(
        "/api/v1/traspasos",
        json={
            "jugador_perfil_id": perfil_id,
            "inscripcion_origen_id": None,
            "inscripcion_destino_id": INSCRIPCION_TIBURONES,
            "dorsal_nuevo": 88,
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["inscripcion_origen_id"] is None


async def test_origen_sin_membresia_activa_es_rechazado(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    # Mateo Salcedo (jugador 3) está en Águilas (inscripcion 2), no en
    # Tiburones (inscripcion 1) — declarar Tiburones como origen es falso.
    resp = await client.get("/api/v1/perfiles", params={"jugador_id": 3, "disciplina_id": 1})
    perfil_id = resp.json()[0]["id"]

    resp = await client.post(
        "/api/v1/traspasos",
        json={
            "jugador_perfil_id": perfil_id,
            "inscripcion_origen_id": INSCRIPCION_TIBURONES,
            "inscripcion_destino_id": INSCRIPCION_AGUILAS,
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "no tiene una membresía activa" in resp.json()["detail"]


async def test_fichaje_desde_libre_con_membresia_activa_es_rechazado(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    # Carlos Pérez ya está Activo en Tiburones — declarar el fichaje como
    # "desde libre" (sin origen) es incoherente.
    perfil_id = await _perfil_de_carlos(client)

    resp = await client.post(
        "/api/v1/traspasos",
        json={
            "jugador_perfil_id": perfil_id,
            "inscripcion_origen_id": None,
            "inscripcion_destino_id": INSCRIPCION_AGUILAS,
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "ya tiene una membresía activa" in resp.json()["detail"]


async def test_anular_no_toca_jugador_equipo(client: AsyncClient, admin_general_headers: dict[str, str]):
    perfil_id = await _perfil_de_carlos(client)
    resp = await client.post(
        "/api/v1/traspasos",
        json={
            "jugador_perfil_id": perfil_id,
            "inscripcion_origen_id": INSCRIPCION_TIBURONES,
            "inscripcion_destino_id": INSCRIPCION_AGUILAS,
        },
        headers=admin_general_headers,
    )
    traspaso_id = resp.json()["id"]

    resp = await client.post(f"/api/v1/traspasos/{traspaso_id}/anular", headers=admin_general_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["estado"] == "Anulado"

    # El roster sigue reflejando el traspaso real — anular es solo una
    # anotación (EC-20), no revierte nada.
    resp = await client.get("/api/v1/plantillas", params={"inscripcion_torneo_id": INSCRIPCION_AGUILAS})
    fila_destino = next(f for f in resp.json() if f["jugador_perfil_id"] == perfil_id)
    assert fila_destino["estado"] == "Activo"


async def test_anular_dos_veces_es_rechazado(client: AsyncClient, admin_general_headers: dict[str, str]):
    perfil_id = await _perfil_de_carlos(client)
    resp = await client.post(
        "/api/v1/traspasos",
        json={
            "jugador_perfil_id": perfil_id,
            "inscripcion_origen_id": INSCRIPCION_TIBURONES,
            "inscripcion_destino_id": INSCRIPCION_AGUILAS,
        },
        headers=admin_general_headers,
    )
    traspaso_id = resp.json()["id"]

    resp = await client.post(f"/api/v1/traspasos/{traspaso_id}/anular", headers=admin_general_headers)
    assert resp.status_code == 200, resp.text

    resp = await client.post(f"/api/v1/traspasos/{traspaso_id}/anular", headers=admin_general_headers)
    assert resp.status_code == 400, resp.text


async def test_arbitro_no_puede_crear_traspaso(client: AsyncClient, arbitro_headers: dict[str, str]):
    perfil_id = await _perfil_de_carlos(client)
    resp = await client.post(
        "/api/v1/traspasos",
        json={
            "jugador_perfil_id": perfil_id,
            "inscripcion_origen_id": INSCRIPCION_TIBURONES,
            "inscripcion_destino_id": INSCRIPCION_AGUILAS,
        },
        headers=arbitro_headers,
    )
    assert resp.status_code == 403


async def test_arbitro_no_puede_anular_traspaso(client: AsyncClient, arbitro_headers: dict[str, str]):
    resp = await client.post("/api/v1/traspasos/1/anular", headers=arbitro_headers)
    assert resp.status_code == 403


async def test_traspaso_con_destino_inexistente(client: AsyncClient, admin_general_headers: dict[str, str]):
    perfil_id = await _perfil_de_carlos(client)
    resp = await client.post(
        "/api/v1/traspasos",
        json={
            "jugador_perfil_id": perfil_id,
            "inscripcion_origen_id": INSCRIPCION_TIBURONES,
            "inscripcion_destino_id": 999999,
        },
        headers=admin_general_headers,
    )
    # inscripcion_repo.get_or_404 (para el lock de exclusividad) resuelve el
    # destino antes de intentar el insert — 404 limpio, no un 500/409 crudo
    # de una FK violation.
    assert resp.status_code == 404, resp.text
