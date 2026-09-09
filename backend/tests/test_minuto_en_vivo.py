"""Área 2 (T7, orden cronológico) y Área 3 (T3/T22, minuto en vivo
calculado server-side, ignorando lo que mande el cliente) —
modo-vivo-sustituciones-cierre-plan.md."""
from httpx import AsyncClient


async def test_minuto_de_evento_en_vivo_lo_calcula_el_servidor_no_el_cliente(
    client: AsyncClient, arbitro_headers: dict[str, str], convocar_titulares
):
    """Partido 3 (05_seed.sql) recién arrancado (Inicio_Partido, sin
    período abierto todavía si el torneo es 'Periodos') — el cliente manda
    minuto=77 (a propósito, un valor que NO puede ser el real: el partido
    recién arrancó) y el servidor lo ignora: guarda el que calculó desde
    los Hitos, siempre un entero razonable (0..pocos minutos), nunca el
    que mandó el cliente."""
    await convocar_titulares(3)
    resp = await client.post("/api/v1/partidos/3/hitos", json={"tipo_hito": "Inicio_Partido"}, headers=arbitro_headers)
    assert resp.status_code == 201, resp.text

    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": 1, "minuto": 77},
        headers=arbitro_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["minuto"] != 77
    assert 0 <= resp.json()["minuto"] < 5


async def test_minuto_de_evento_en_vivo_funciona_sin_mandar_minuto(
    client: AsyncClient, arbitro_headers: dict[str, str], convocar_titulares
):
    """El schema hace opcional `minuto` (T22) — un cliente nuevo puede
    directamente omitirlo."""
    await convocar_titulares(3)
    await client.post("/api/v1/partidos/3/hitos", json={"tipo_hito": "Inicio_Partido"}, headers=arbitro_headers)

    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": 1},
        headers=arbitro_headers,
    )
    assert resp.status_code == 201, resp.text
    assert isinstance(resp.json()["minuto"], int)


async def test_eventos_partido_se_listan_en_orden_cronologico(
    client: AsyncClient, arbitro_headers: dict[str, str]
):
    """T7 — EventoPartidoRepository.list ordena por (minuto, id), no por
    orden de inserción: se carga primero el minuto 40 y después el 2 (como
    pasaría con "Cargar resultado directo", que no exige orden de carga) y
    el GET los devuelve YA ordenados 2 antes que 40.

    Partido 3 (05_seed.sql, torneo 1): Andrés Vera (jugador 5) pertenece al
    equipo 3 — mismo par ya usado en test_eventos_partido.py."""
    resp = await client.post(
        "/api/v1/partidos/3/resultado-directo",
        json={
            "eventos": [
                {"jugador_id": 5, "equipo_id": 3, "eventos_id": 1, "minuto": 40},
                {"jugador_id": 5, "equipo_id": 3, "eventos_id": 1, "minuto": 2},
            ]
        },
        headers=arbitro_headers,
    )
    assert resp.status_code == 200, resp.text

    resp = await client.get("/api/v1/eventos-partido", params={"partidos_id": 3})
    minutos = [e["minuto"] for e in resp.json()]
    assert minutos == [2, 40]
