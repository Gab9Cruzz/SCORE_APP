from httpx import AsyncClient


async def test_catalogo_de_eventos_es_publico(client: AsyncClient):
    # 05_seed.sql carga: Gol, Autogol, Tarjeta Amarilla, Tarjeta Roja, Cambio.
    resp = await client.get("/api/v1/eventos")
    assert resp.status_code == 200
    nombres = {e["nombre"] for e in resp.json()}
    assert {"Gol", "Autogol", "Tarjeta Amarilla", "Tarjeta Roja", "Cambio"} <= nombres


async def test_admin_agrega_tipo_de_evento(client: AsyncClient, admin_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/eventos",
        json={"nombre": "Lesión", "descripcion": "Jugador debe salir por lesión"},
        headers=admin_headers,
    )
    assert resp.status_code == 201
