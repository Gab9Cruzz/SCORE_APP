"""Verifica que la API expone bien las vistas de /database/04_views.sql
contra los datos de 05_seed.sql:

Partido 1 (Finalizado): Tiburones 1-1 Águilas (goles: Carlos min23, Mateo min55)
Partido 2 (Finalizado): Águilas 1-1 Halcones (goles: Andrés min12, Mateo min40)
Partido 3: Programado, no cuenta para la tabla de posiciones.
"""
from httpx import AsyncClient


async def test_tabla_posiciones(client: AsyncClient):
    resp = await client.get("/api/v1/estadisticas/torneos/1/posiciones")
    assert resp.status_code == 200
    tabla = {fila["equipo"]: fila for fila in resp.json()}

    assert tabla["Águilas del Sur"]["pj"] == 2
    assert tabla["Águilas del Sur"]["pts"] == 2  # dos empates
    assert tabla["Tiburones FC"]["pj"] == 1
    assert tabla["Tiburones FC"]["pts"] == 1
    assert tabla["Halcones United"]["pj"] == 1
    assert tabla["Halcones United"]["pts"] == 1


async def test_goleadores(client: AsyncClient):
    resp = await client.get("/api/v1/estadisticas/torneos/1/goleadores")
    assert resp.status_code == 200
    goles = {fila["jugador"]: fila["goles"] for fila in resp.json()}

    assert goles["Mateo Salcedo"] == 2
    assert goles["Carlos Pérez"] == 1
    assert goles["Andrés Vera"] == 1


async def test_proximos_partidos_no_incluye_partidos_pasados_finalizados(client: AsyncClient):
    # El partido 3 del seed está Programado pero con fecha en el pasado
    # (2026-01-29) respecto a "hoy" en un entorno normal — la vista solo
    # muestra Fecha_Partido >= CURRENT_TIMESTAMP, así que no debería
    # aparecer salvo que el test corra antes de esa fecha.
    resp = await client.get("/api/v1/estadisticas/proximos-partidos", params={"torneo_id": 1})
    assert resp.status_code == 200
    for partido in resp.json():
        assert partido["estado"] == "Programado"


async def test_resultados_partidos(client: AsyncClient):
    resp = await client.get("/api/v1/estadisticas/torneos/1/resultados")
    assert resp.status_code == 200
    resultados = resp.json()
    assert len(resultados) == 3
    finalizados = [r for r in resultados if r["estado"] == "Finalizado"]
    assert all(r["goles_local"] == 1 and r["goles_visitante"] == 1 for r in finalizados)


async def test_plantilla_equipo(client: AsyncClient):
    resp = await client.get("/api/v1/estadisticas/equipos/1/plantilla")
    assert resp.status_code == 200
    jugadores = {fila["jugador"]: fila["dorsal"] for fila in resp.json()}
    assert jugadores["Carlos Pérez"] == 10
    assert jugadores["Luis Andrade"] == 7
