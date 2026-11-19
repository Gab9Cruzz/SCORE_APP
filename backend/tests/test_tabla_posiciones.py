"""TASK-025 (FUN-09): la tabla de posiciones parte de los participantes
(inscriptos en una liga, miembros de cada grupo) y no solo de quien ya
jugó; y en cronómetro corrido usa el ganador declarado (3 puntos, sin
empates), porque esos partidos no tienen goles."""
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.partido import Partido


async def _liga(client: AsyncClient, headers: dict[str, str], nombre: str, equipos: int, **extra) -> tuple[int, list[int]]:
    resp = await client.post(
        "/api/v1/torneos",
        json={"torneo_grupo_nombre": nombre, "disciplina_id": 1, "modalidad_id": 1,
              "fecha_inicio": "2026-05-01", "fecha_fin": "2026-08-01", "formato": "Liga", **extra},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    torneo_id = resp.json()["id"]
    ids = []
    for i in range(equipos):
        eq = await client.post(
            "/api/v1/equipos", json={"nombre": f"{nombre} {i}", "disciplina_id": 1, "modalidad_id": 1}, headers=headers
        )
        ids.append(eq.json()["id"])
        resp = await client.post("/api/v1/inscripciones", json={"torneo_id": torneo_id, "equipo_id": ids[-1]}, headers=headers)
        assert resp.status_code == 201, resp.text
    resp = await client.post(f"/api/v1/torneos/{torneo_id}/fixture", headers=headers)
    assert resp.status_code in (200, 201), resp.text
    return torneo_id, ids


async def _tabla(client: AsyncClient, torneo_id: int, headers: dict[str, str]) -> dict[int, dict]:
    resp = await client.get(f"/api/v1/estadisticas/torneos/{torneo_id}/posiciones", headers=headers)
    assert resp.status_code == 200, resp.text
    return {fila["equipo_id"]: fila for fila in resp.json()}


async def test_liga_recien_generada_muestra_a_todos_con_ceros(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    """PR-019."""
    torneo_id, equipos = await _liga(client, admin_general_headers, "Liga Ceros", 4)
    tabla = await _tabla(client, torneo_id, admin_general_headers)
    assert set(tabla) == set(equipos)
    for fila in tabla.values():
        assert (fila["pj"], fila["pg"], fila["pe"], fila["pp"], fila["gf"], fila["gc"], fila["pts"]) == (0,) * 7


async def test_equipo_cancelado_sin_partidos_no_aparece(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    torneo_id, equipos = await _liga(client, admin_general_headers, "Liga Con Baja", 3)
    inscripciones = (await client.get("/api/v1/inscripciones", params={"torneo_id": torneo_id}, headers=admin_general_headers)).json()
    cancelada = next(i for i in inscripciones if i["equipo_id"] == equipos[0])
    resp = await client.patch(f"/api/v1/inscripciones/{cancelada['id']}", json={"estado": "Cancelado"}, headers=admin_general_headers)
    assert resp.status_code == 200, resp.text
    assert equipos[0] not in await _tabla(client, torneo_id, admin_general_headers)


async def test_en_cronometro_corrido_el_ganador_declarado_suma_3(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """PR-020."""
    torneo_id, (a, b) = await _liga(
        client, admin_general_headers, "Liga Corrida", 2, config_tiempo={"tipo_cronometro": "Corrido"}
    )
    partido_id = (await client.get("/api/v1/partidos", params={"torneo_id": torneo_id}, headers=admin_general_headers)).json()[0]["id"]
    partido = await db_session.get(Partido, partido_id)
    partido.ganador_corrido_id = a
    partido.estado = "Finalizado"
    await db_session.commit()

    tabla = await _tabla(client, torneo_id, admin_general_headers)
    assert (tabla[a]["pj"], tabla[a]["pg"], tabla[a]["pe"], tabla[a]["pts"]) == (1, 1, 0, 3)
    assert (tabla[b]["pj"], tabla[b]["pp"], tabla[b]["pe"], tabla[b]["pts"]) == (1, 1, 0, 0)


async def test_la_tabla_del_torneo_por_periodos_no_cambia(client: AsyncClient):
    """05_seed.sql: torneo 1, Tiburones 1-1 Águilas y Águilas 1-1 Halcones
    (partidos 1 y 2); el 3 está programado. Valores tomados antes del cambio."""
    tabla = await _tabla(client, 1, {})
    resumen = {eid: (f["pj"], f["pg"], f["pe"], f["pp"], f["gf"], f["gc"], f["pts"]) for eid, f in tabla.items()}
    assert resumen == {1: (1, 0, 1, 0, 1, 1, 1), 2: (2, 0, 2, 0, 2, 2, 2), 3: (1, 0, 1, 0, 1, 1, 1)}
