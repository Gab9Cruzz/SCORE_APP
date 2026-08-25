from httpx import AsyncClient


async def test_registrar_gol_valido(client: AsyncClient, arbitro_headers: dict[str, str]):
    # Partido 3 (05_seed.sql): torneo 1, Halcones(3) vs Tiburones(1), sin
    # eventos aún. Andrés Vera (jugador 5) pertenece al equipo 3 desde
    # 2026-01-01 (jugador_equipo), fecha del partido 2026-01-29.
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
    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 1, "equipo_id": 3, "eventos_id": 1, "minuto": 40},
        headers=arbitro_headers,
    )
    assert resp.status_code == 400


async def test_minuto_fuera_de_rango_es_rechazado(client: AsyncClient, arbitro_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": 1, "minuto": 200},
        headers=arbitro_headers,
    )
    assert resp.status_code == 422


async def test_anular_evento(client: AsyncClient, arbitro_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 6, "equipo_id": 3, "eventos_id": 3, "minuto": 60},
        headers=arbitro_headers,
    )
    evento_id = resp.json()["id"]

    resp = await client.post(f"/api/v1/eventos-partido/{evento_id}/anular", headers=arbitro_headers)
    assert resp.status_code == 200
    assert resp.json()["estado"] == "Anulado"
