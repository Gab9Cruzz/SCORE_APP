"""Titular/suplente/convocados a un partido (3B-2,
docs/plans/cierre-backlog-todos-plan.md). Partido 3 (05_seed.sql): torneo
1, Halcones(3) vs Tiburones(1), árbitro_test asignado. Andrés Vera
(jugador 5) está en Halcones; Carlos Pérez (jugador 1) está en Tiburones.
"""
from httpx import AsyncClient

PARTIDO_3 = 3


async def _perfil_de(client: AsyncClient, jugador_id: int, disciplina_id: int = 1) -> int:
    resp = await client.get("/api/v1/perfiles", params={"jugador_id": jugador_id, "disciplina_id": disciplina_id})
    return resp.json()[0]["id"]


async def test_definir_convocatoria_y_listarla(client: AsyncClient, arbitro_headers: dict[str, str]):
    perfil_andres = await _perfil_de(client, 5)  # Halcones
    perfil_carlos = await _perfil_de(client, 1)  # Tiburones

    resp = await client.put(
        f"/api/v1/partidos/{PARTIDO_3}/convocados",
        json={
            "convocados": [
                {"jugador_perfil_id": perfil_andres, "titular": True},
                {"jugador_perfil_id": perfil_carlos, "titular": False},
            ]
        },
        headers=arbitro_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 2
    titulares = {c["jugador_perfil_id"] for c in body if c["titular"]}
    assert titulares == {perfil_andres}

    resp = await client.get(f"/api/v1/partidos/{PARTIDO_3}/convocados")
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 2


async def test_reemplazar_convocatoria_pisa_la_lista_anterior(client: AsyncClient, arbitro_headers: dict[str, str]):
    perfil_andres = await _perfil_de(client, 5)
    perfil_carlos = await _perfil_de(client, 1)

    await client.put(
        f"/api/v1/partidos/{PARTIDO_3}/convocados",
        json={"convocados": [{"jugador_perfil_id": perfil_andres, "titular": True}]},
        headers=arbitro_headers,
    )
    resp = await client.put(
        f"/api/v1/partidos/{PARTIDO_3}/convocados",
        json={"convocados": [{"jugador_perfil_id": perfil_carlos, "titular": True}]},
        headers=arbitro_headers,
    )
    assert resp.status_code == 200, resp.text

    resp = await client.get(f"/api/v1/partidos/{PARTIDO_3}/convocados")
    body = resp.json()
    assert len(body) == 1
    assert body[0]["jugador_perfil_id"] == perfil_carlos


async def test_convocatoria_vacia_saca_todo(client: AsyncClient, arbitro_headers: dict[str, str]):
    perfil_andres = await _perfil_de(client, 5)
    await client.put(
        f"/api/v1/partidos/{PARTIDO_3}/convocados",
        json={"convocados": [{"jugador_perfil_id": perfil_andres, "titular": True}]},
        headers=arbitro_headers,
    )

    resp = await client.put(
        f"/api/v1/partidos/{PARTIDO_3}/convocados", json={"convocados": []}, headers=arbitro_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == []

    resp = await client.get(f"/api/v1/partidos/{PARTIDO_3}/convocados")
    assert resp.json() == []


async def test_jugador_ajeno_a_ambos_equipos_es_rechazado(client: AsyncClient, arbitro_headers: dict[str, str]):
    # Jugador 3 — Activo en Águilas (Equipo_ID=2, 05_seed.sql), el TERCER
    # equipo del torneo que no juega este partido (Halcones=3 vs
    # Tiburones=1).
    perfil_ajeno = await _perfil_de(client, 3)

    resp = await client.put(
        f"/api/v1/partidos/{PARTIDO_3}/convocados",
        json={"convocados": [{"jugador_perfil_id": perfil_ajeno, "titular": False}]},
        headers=arbitro_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "no pertenece" in resp.json()["detail"].lower()


async def test_mismo_jugador_dos_veces_en_la_lista_es_rechazado(
    client: AsyncClient, arbitro_headers: dict[str, str]
):
    perfil_andres = await _perfil_de(client, 5)

    resp = await client.put(
        f"/api/v1/partidos/{PARTIDO_3}/convocados",
        json={
            "convocados": [
                {"jugador_perfil_id": perfil_andres, "titular": True},
                {"jugador_perfil_id": perfil_andres, "titular": False},
            ]
        },
        headers=arbitro_headers,
    )
    assert resp.status_code == 400, resp.text


async def test_arbitro_no_asignado_no_puede_definir_convocatoria(
    client: AsyncClient, arbitro_no_asignado_headers: dict[str, str]
):
    resp = await client.put(
        f"/api/v1/partidos/{PARTIDO_3}/convocados", json={"convocados": []}, headers=arbitro_no_asignado_headers
    )
    assert resp.status_code == 403, resp.text


async def test_torneo_admin_puede_definir_convocatoria(client: AsyncClient, torneo_admin_headers: dict[str, str]):
    resp = await client.put(
        f"/api/v1/partidos/{PARTIDO_3}/convocados", json={"convocados": []}, headers=torneo_admin_headers
    )
    assert resp.status_code == 200, resp.text


async def test_definir_convocatoria_sin_auth_falla(client: AsyncClient):
    resp = await client.put(f"/api/v1/partidos/{PARTIDO_3}/convocados", json={"convocados": []})
    assert resp.status_code == 401
