from httpx import AsyncClient


async def _empezar_partido(client: AsyncClient, headers: dict[str, str], partido_id: int = 3) -> None:
    """3A-8 (docs/plans/cierre-backlog-todos-plan.md): EventoPartidoService.create
    ahora exige partido.estado == 'En curso' (antes, el único guard vivía en
    el filtro de la lista de ControlDeMesaPage, no en el service — ver el
    comentario de _verificar_partido_en_curso). El partido 3 nace
    'Programado' en 05_seed.sql, así que todo test de este archivo que
    registra un evento nuevo necesita este paso primero, igual que el flujo
    real (botón "Empezar Partido" antes de poder cargar nada)."""
    resp = await client.post(
        f"/api/v1/partidos/{partido_id}/hitos", json={"tipo_hito": "Inicio_Partido"}, headers=headers
    )
    assert resp.status_code == 201, resp.text


async def test_registrar_gol_valido(client: AsyncClient, arbitro_headers: dict[str, str]):
    # Partido 3 (05_seed.sql): torneo 1, Halcones(3) vs Tiburones(1), sin
    # eventos aún. Andrés Vera (jugador 5) pertenece al equipo 3 desde
    # 2026-01-01 (jugador_equipo), fecha del partido 2026-01-29.
    await _empezar_partido(client, arbitro_headers)
    resp = await client.post(
        "/api/v1/eventos-partido",
        json={
            "partidos_id": 3,
            "jugador_id": 5,
            "equipo_id": 3,
            "eventos_id": 1,  # Gol
            "minuto": 30,
        },
        headers=arbitro_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["estado"] == "Registrado"


async def test_jugador_ajeno_al_equipo_es_rechazado(client: AsyncClient, arbitro_headers: dict[str, str]):
    # fn_validar_jugador_partido (06_triggers.sql): Carlos Pérez (jugador 1)
    # pertenece al equipo 1, no al 3.
    await _empezar_partido(client, arbitro_headers)
    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 1, "equipo_id": 3, "eventos_id": 1, "minuto": 40},
        headers=arbitro_headers,
    )
    assert resp.status_code == 400


async def test_minuto_fuera_de_rango_es_rechazado(client: AsyncClient, arbitro_headers: dict[str, str]):
    await _empezar_partido(client, arbitro_headers)
    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": 1, "minuto": 200},
        headers=arbitro_headers,
    )
    assert resp.status_code == 422


async def test_anular_evento(client: AsyncClient, arbitro_headers: dict[str, str]):
    await _empezar_partido(client, arbitro_headers)
    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 6, "equipo_id": 3, "eventos_id": 3, "minuto": 60},
        headers=arbitro_headers,
    )
    evento_id = resp.json()["id"]

    resp = await client.post(f"/api/v1/eventos-partido/{evento_id}/anular", headers=arbitro_headers)
    assert resp.status_code == 200
    assert resp.json()["estado"] == "Anulado"


async def test_arbitro_no_asignado_no_puede_registrar_evento(
    client: AsyncClient, arbitro_headers: dict[str, str], arbitro_no_asignado_headers: dict[str, str]
):
    # D5/D6 (roles-3-modulos-plan.md, Fase 1): el ownership-check rechaza a
    # un Árbitro válido que no es el asignado al partido 3. "Empezar
    # Partido" lo hace el árbitro asignado (el no asignado no podría ni
    # eso) — el 403 de ownership debe ganarle al guard de estado igual, así
    # que el partido queda 'En curso' antes de este intento.
    await _empezar_partido(client, arbitro_headers)
    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": 1, "minuto": 30},
        headers=arbitro_no_asignado_headers,
    )
    assert resp.status_code == 403
    assert "asignado" in resp.json()["detail"].lower()


async def test_arbitro_no_asignado_no_puede_anular_evento(
    client: AsyncClient, arbitro_headers: dict[str, str], arbitro_no_asignado_headers: dict[str, str]
):
    # El evento lo carga el árbitro asignado; el intento de anularlo viene
    # de un árbitro distinto, sin asignación al partido 3.
    await _empezar_partido(client, arbitro_headers)
    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": 1, "minuto": 15},
        headers=arbitro_headers,
    )
    evento_id = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/eventos-partido/{evento_id}/anular", headers=arbitro_no_asignado_headers
    )
    assert resp.status_code == 403
    assert "asignado" in resp.json()["detail"].lower()


async def test_torneo_admin_sin_asignacion_no_puede_registrar_ni_anular_evento(
    client: AsyncClient, torneo_admin_con_torneo_headers: dict[str, str], torneo_admin_headers: dict[str, str]
):
    """rbac-licencias-torneos-plan.md, Fase 2 — distinto del
    ownership-check de Árbitro (D5): acá el chequeo es de TorneoAdmin
    contra ASIGNACION_TORNEO_ADMIN, resuelto vía partidos_id -> Partido.torneo_id."""
    await _empezar_partido(client, torneo_admin_con_torneo_headers)
    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": 1, "minuto": 20},
        headers=torneo_admin_headers,
    )
    assert resp.status_code == 403
    assert "asignado" in resp.json()["detail"]

    # Evento real lo carga la cuenta asignada, para probar anular contra ella.
    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": 1, "minuto": 21},
        headers=torneo_admin_con_torneo_headers,
    )
    evento_id = resp.json()["id"]

    resp = await client.post(f"/api/v1/eventos-partido/{evento_id}/anular", headers=torneo_admin_headers)
    assert resp.status_code == 403


async def test_torneo_admin_puede_registrar_y_anular_evento(
    client: AsyncClient, torneo_admin_con_torneo_headers: dict[str, str]
):
    # TorneoAdmin no pasa por el ownership-check de Árbitro (D5) — pero SÍ
    # necesita asignación al torneo del partido (rbac-licencias-torneos-plan.md,
    # Fase 2) — torneo_admin_con_torneo_headers está asignado al Torneo 1
    # (partido 3 pertenece a ese torneo, 05_seed.sql).
    await _empezar_partido(client, torneo_admin_con_torneo_headers)
    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": 1, "minuto": 45},
        headers=torneo_admin_con_torneo_headers,
    )
    assert resp.status_code == 201, resp.text
    evento_id = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/eventos-partido/{evento_id}/anular", headers=torneo_admin_con_torneo_headers
    )
    assert resp.status_code == 200
    assert resp.json()["estado"] == "Anulado"


async def test_registrar_evento_en_partido_programado_es_rechazado(
    client: AsyncClient, arbitro_headers: dict[str, str]
):
    """3A-8: sin "Empezar Partido" primero, el partido 3 sigue 'Programado'
    (05_seed.sql) — el guard nuevo debe rechazar el alta ANTES de tocar
    fn_validar_jugador_partido, no solo confiar en el filtro de la UI."""
    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": 1, "minuto": 30},
        headers=arbitro_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "en curso" in resp.json()["detail"].lower()


async def test_registrar_evento_en_partido_finalizado_es_rechazado(
    client: AsyncClient, torneo_admin_con_torneo_headers: dict[str, str]
):
    """Alta NUEVA sigue bloqueada incluso después de Finalizado — distinto
    de corregir_minuto/anular sobre un evento YA cargado (EC-15), que este
    test no toca."""
    resp = await client.patch(
        "/api/v1/partidos/3", json={"estado": "Finalizado"}, headers=torneo_admin_con_torneo_headers
    )
    assert resp.status_code == 200, resp.text

    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": 1, "minuto": 30},
        headers=torneo_admin_con_torneo_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "en curso" in resp.json()["detail"].lower()
