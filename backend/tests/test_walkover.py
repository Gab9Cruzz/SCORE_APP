"""Walkover/retiro (3B-13, docs/plans/cierre-backlog-todos-plan.md).
Disciplina 1 = Fútbol, Modalidad 1 = Fútbol 11 (05_seed.sql)."""
from httpx import AsyncClient

DISCIPLINA_FUTBOL = 1
MODALIDAD_FUTBOL_11 = 1


async def _crear_equipos(client: AsyncClient, headers: dict[str, str], cantidad: int, prefijo: str) -> list[int]:
    ids = []
    for i in range(cantidad):
        resp = await client.post(
            "/api/v1/equipos",
            json={"nombre": f"{prefijo} {i + 1}", "disciplina_id": DISCIPLINA_FUTBOL, "modalidad_id": MODALIDAD_FUTBOL_11},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        ids.append(resp.json()["id"])
    return ids


async def _torneo_con_equipos(
    client: AsyncClient, headers: dict[str, str], n: int, formato: str, nombre: str, **extra
) -> tuple[int, list[int]]:
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "torneo_grupo_nombre": nombre,
            "disciplina_id": DISCIPLINA_FUTBOL,
            "modalidad_id": MODALIDAD_FUTBOL_11,
            "fecha_inicio": "2026-04-01",
            "fecha_fin": "2026-06-30",
            "formato": formato,
            **extra,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    torneo_id = resp.json()["id"]
    equipo_ids = await _crear_equipos(client, headers, n, prefijo=nombre)
    for equipo_id in equipo_ids:
        resp = await client.post(
            "/api/v1/inscripciones", json={"torneo_id": torneo_id, "equipo_id": equipo_id}, headers=headers
        )
        assert resp.status_code == 201, resp.text
    return torneo_id, equipo_ids


async def test_walkover_en_eliminacion_siempre_permitido_y_avanza_al_ganador(
    client: AsyncClient, torneo_admin_headers: dict[str, str]
):
    torneo_id, equipos = await _torneo_con_equipos(
        client, torneo_admin_headers, 4, formato="Eliminacion", nombre="Walkover Eliminacion"
    )
    assert (
        await client.post(f"/api/v1/torneos/{torneo_id}/sorteo", json={"semilla": "walkover-fijo"}, headers=torneo_admin_headers)
    ).status_code == 200

    resp = await client.get(f"/api/v1/torneos/{torneo_id}/bracket")
    bracket = resp.json()
    primera_ronda = [p for p in bracket if p["partido_siguiente_id"] is not None]
    partido = primera_ronda[0]
    ausente = partido["equipos_id_local"]
    presente = partido["equipos_id_visitante"]

    # Torneo Eliminacion puro nunca seteó Permite_Walkover_Grupos — igual
    # tiene que andar, la Eliminación no depende de ese flag.
    resp = await client.post(
        f"/api/v1/partidos/{partido['id']}/walkover",
        json={"equipo_ausente_id": ausente},
        headers=torneo_admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["estado"] == "Finalizado"
    assert body["es_walkover"] is True
    assert body["walkover_equipo_ausente_id"] == ausente

    # El PRESENTE avanzó al partido siguiente, no un empate ni el ausente.
    resp = await client.get(f"/api/v1/torneos/{torneo_id}/bracket")
    siguiente = next(p for p in resp.json() if p["id"] == partido["partido_siguiente_id"])
    assert presente in (siguiente["equipos_id_local"], siguiente["equipos_id_visitante"])
    assert ausente not in (siguiente["equipos_id_local"], siguiente["equipos_id_visitante"])


async def test_walkover_en_liga_sin_habilitar_es_rechazado(client: AsyncClient, torneo_admin_headers: dict[str, str]):
    torneo_id, equipos = await _torneo_con_equipos(
        client, torneo_admin_headers, 4, formato="Liga", nombre="Walkover Liga Sin Habilitar"
    )
    assert (
        await client.post(f"/api/v1/torneos/{torneo_id}/fixture", headers=torneo_admin_headers)
    ).status_code == 200

    resp = await client.get("/api/v1/partidos", params={"torneo_id": torneo_id})
    partido = resp.json()[0]

    resp = await client.post(
        f"/api/v1/partidos/{partido['id']}/walkover",
        json={"equipo_ausente_id": partido["equipos_id_local"]},
        headers=torneo_admin_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "walkover" in resp.json()["detail"].lower()


async def test_walkover_en_liga_habilitado_deja_3_0_en_la_tabla(
    client: AsyncClient, torneo_admin_headers: dict[str, str]
):
    torneo_id, equipos = await _torneo_con_equipos(
        client,
        torneo_admin_headers,
        4,
        formato="Liga",
        nombre="Walkover Liga Habilitada",
        permite_walkover_grupos=True,
    )
    assert (
        await client.post(f"/api/v1/torneos/{torneo_id}/fixture", headers=torneo_admin_headers)
    ).status_code == 200

    resp = await client.get("/api/v1/partidos", params={"torneo_id": torneo_id})
    partido = resp.json()[0]
    ausente = partido["equipos_id_local"]
    presente = partido["equipos_id_visitante"]

    resp = await client.post(
        f"/api/v1/partidos/{partido['id']}/walkover",
        json={"equipo_ausente_id": ausente},
        headers=torneo_admin_headers,
    )
    assert resp.status_code == 200, resp.text

    resp = await client.get(f"/api/v1/estadisticas/torneos/{torneo_id}/posiciones")
    tabla = {f["equipo_id"]: f for f in resp.json()}
    assert tabla[presente]["gf"] == 3
    assert tabla[presente]["gc"] == 0
    assert tabla[presente]["pts"] == 3
    assert tabla[ausente]["gf"] == 0
    assert tabla[ausente]["gc"] == 3
    assert tabla[ausente]["pts"] == 0


async def test_walkover_equipo_ausente_debe_ser_uno_de_los_dos(
    client: AsyncClient, torneo_admin_headers: dict[str, str]
):
    torneo_id, equipos = await _torneo_con_equipos(
        client,
        torneo_admin_headers,
        4,
        formato="Liga",
        nombre="Walkover Equipo Invalido",
        permite_walkover_grupos=True,
    )
    await client.post(f"/api/v1/torneos/{torneo_id}/fixture", headers=torneo_admin_headers)
    resp = await client.get("/api/v1/partidos", params={"torneo_id": torneo_id})
    partido = resp.json()[0]
    otro_torneo_equipo = (await _crear_equipos(client, torneo_admin_headers, 1, "Ajeno"))[0]

    resp = await client.post(
        f"/api/v1/partidos/{partido['id']}/walkover",
        json={"equipo_ausente_id": otro_torneo_equipo},
        headers=torneo_admin_headers,
    )
    assert resp.status_code == 400, resp.text


async def test_walkover_sobre_partido_ya_finalizado_es_rechazado(
    client: AsyncClient, torneo_admin_headers: dict[str, str]
):
    torneo_id, equipos = await _torneo_con_equipos(
        client,
        torneo_admin_headers,
        4,
        formato="Liga",
        nombre="Walkover Ya Finalizado",
        permite_walkover_grupos=True,
    )
    await client.post(f"/api/v1/torneos/{torneo_id}/fixture", headers=torneo_admin_headers)
    resp = await client.get("/api/v1/partidos", params={"torneo_id": torneo_id})
    partido = resp.json()[0]

    resp = await client.post(
        f"/api/v1/partidos/{partido['id']}/walkover",
        json={"equipo_ausente_id": partido["equipos_id_local"]},
        headers=torneo_admin_headers,
    )
    assert resp.status_code == 200, resp.text

    resp = await client.post(
        f"/api/v1/partidos/{partido['id']}/walkover",
        json={"equipo_ausente_id": partido["equipos_id_visitante"]},
        headers=torneo_admin_headers,
    )
    assert resp.status_code == 400, resp.text


async def test_walkover_sin_auth_falla(client: AsyncClient):
    resp = await client.post("/api/v1/partidos/1/walkover", json={"equipo_ausente_id": 1})
    assert resp.status_code == 401
