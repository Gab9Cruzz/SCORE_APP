"""TASK-019 (FUN-14, DB-03, ARQ-03): goles, tarjetas y cambios se
reconocen por EVENTOS.Codigo, no por el nombre. Los tipos de sistema
(con código) no se renombran ni se dan de baja, y el nombre es único.

05_seed.sql: 1 Gol, 2 Autogol, 3 Tarjeta Amarilla, 4 Tarjeta Roja,
5 Cambio. Partido 1: Tiburones 1 - 1 Águilas.
"""
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

CODIGOS = {1: "GOL", 2: "AUTOGOL", 3: "TARJETA_AMARILLA", 4: "TARJETA_ROJA", 5: "CAMBIO"}


async def test_los_tipos_de_sistema_exponen_su_codigo(client: AsyncClient):
    eventos = {e["id"]: e for e in (await client.get("/api/v1/eventos")).json()}
    assert {i: eventos[i]["codigo"] for i in CODIGOS} == CODIGOS


async def test_renombrar_un_tipo_de_sistema_se_rechaza(client: AsyncClient, admin_general_headers: dict[str, str]):
    """PR-023."""
    resp = await client.patch("/api/v1/eventos/1", json={"nombre": "Gol ⚽"}, headers=admin_general_headers)
    assert resp.status_code == 400, resp.text


async def test_dar_de_baja_un_tipo_de_sistema_se_rechaza(client: AsyncClient, admin_general_headers: dict[str, str]):
    h = admin_general_headers
    assert (await client.delete("/api/v1/eventos/4", headers=h)).status_code == 400
    assert (await client.patch("/api/v1/eventos/4", json={"estado": "Inactivo"}, headers=h)).status_code == 400


async def test_la_descripcion_de_un_tipo_de_sistema_si_se_edita(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    resp = await client.patch("/api/v1/eventos/1", json={"descripcion": "Gol convertido"}, headers=admin_general_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["nombre"] == "Gol"


async def test_un_segundo_tipo_con_el_mismo_nombre_es_409(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.post("/api/v1/eventos", json={"nombre": "Gol"}, headers=admin_general_headers)
    assert resp.status_code == 409, resp.text


async def test_un_tipo_propio_se_renombra_y_se_da_de_baja(client: AsyncClient, admin_general_headers: dict[str, str]):
    h = admin_general_headers
    resp = await client.post("/api/v1/eventos", json={"nombre": "Falta"}, headers=h)
    assert resp.status_code == 201, resp.text
    assert resp.json()["codigo"] is None
    evento_id = resp.json()["id"]
    assert (await client.patch(f"/api/v1/eventos/{evento_id}", json={"nombre": "Falta grave"}, headers=h)).status_code == 200
    assert (await client.delete(f"/api/v1/eventos/{evento_id}", headers=h)).status_code == 200


async def test_el_marcador_no_depende_del_nombre(client: AsyncClient, db_session: AsyncSession):
    """Aunque alguien renombre "Gol" directo en la base, el marcador sigue."""
    await db_session.execute(text("UPDATE EVENTOS SET Nombre = 'Gol renombrado' WHERE ID = 1"))
    await db_session.commit()

    resultados = {r["partido_id"]: r for r in (await client.get("/api/v1/estadisticas/torneos/1/resultados")).json()}
    assert (resultados[1]["goles_local"], resultados[1]["goles_visitante"]) == (1, 1)
