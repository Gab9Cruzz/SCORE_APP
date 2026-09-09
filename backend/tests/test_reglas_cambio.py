"""Área 3 (modo-vivo-sustituciones-cierre-plan.md, T5): tope de cambios +
no-retorno, gobernados por Torneo.maximo_cambios_por_equipo /
Torneo.permite_cambios_ilimitados."""
from httpx import AsyncClient


async def _iniciar_partido_3(client, arbitro_headers, convocar_titulares):
    await convocar_titulares(3)
    resp = await client.post("/api/v1/partidos/3/hitos", json={"tipo_hito": "Inicio_Partido"}, headers=arbitro_headers)
    assert resp.status_code == 201, resp.text


async def _patch_torneo_1(client, headers, **campos):
    resp = await client.patch("/api/v1/torneos/1", json=campos, headers=headers)
    assert resp.status_code == 200, resp.text


async def test_tope_de_cambios_por_equipo_rechaza_el_excedente(
    client: AsyncClient, arbitro_headers: dict[str, str], torneo_admin_con_torneo_headers: dict[str, str], convocar_titulares
):
    await _patch_torneo_1(client, torneo_admin_con_torneo_headers, maximo_cambios_por_equipo=1)
    await _iniciar_partido_3(client, arbitro_headers, convocar_titulares)

    cambio_id = (await client.get("/api/v1/eventos")).json()
    cambio_id = next(e["id"] for e in cambio_id if e["nombre"] == "Cambio")

    # 1er cambio: aceptado.
    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": cambio_id, "jugador_id_entra": 6},
        headers=arbitro_headers,
    )
    assert resp.status_code == 201, resp.text

    # 2do cambio del MISMO equipo: rechazado (tope=1).
    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 6, "equipo_id": 3, "eventos_id": cambio_id, "jugador_id_entra": 7},
        headers=arbitro_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "cambios" in resp.json()["detail"].lower()


async def test_no_retorno_rechaza_que_reingrese_quien_ya_salio(
    client: AsyncClient, arbitro_headers: dict[str, str], torneo_admin_con_torneo_headers: dict[str, str], convocar_titulares
):
    """Default del torneo (permite_cambios_ilimitados=False): un jugador
    que salió por Cambio no puede volver a entrar."""
    await _iniciar_partido_3(client, arbitro_headers, convocar_titulares)
    cambio_id = next(e["id"] for e in (await client.get("/api/v1/eventos")).json() if e["nombre"] == "Cambio")

    # Sale 5, entra 6.
    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": cambio_id, "jugador_id_entra": 6},
        headers=arbitro_headers,
    )
    assert resp.status_code == 201, resp.text

    # Ahora sale otro jugador y se intenta que vuelva a entrar el 5
    # (que ya salió antes) — rechazado por no-retorno.
    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 6, "equipo_id": 3, "eventos_id": cambio_id, "jugador_id_entra": 5},
        headers=arbitro_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "reingres" in resp.json()["detail"].lower()


async def test_permite_cambios_ilimitados_desactiva_la_regla_de_no_retorno(
    client: AsyncClient, arbitro_headers: dict[str, str], torneo_admin_con_torneo_headers: dict[str, str], convocar_titulares
):
    await _patch_torneo_1(client, torneo_admin_con_torneo_headers, permite_cambios_ilimitados=True)
    await _iniciar_partido_3(client, arbitro_headers, convocar_titulares)
    cambio_id = next(e["id"] for e in (await client.get("/api/v1/eventos")).json() if e["nombre"] == "Cambio")

    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": cambio_id, "jugador_id_entra": 6},
        headers=arbitro_headers,
    )
    assert resp.status_code == 201, resp.text

    # Con cambios ilimitados, 5 puede reingresar sin problema.
    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 6, "equipo_id": 3, "eventos_id": cambio_id, "jugador_id_entra": 5},
        headers=arbitro_headers,
    )
    assert resp.status_code == 201, resp.text
