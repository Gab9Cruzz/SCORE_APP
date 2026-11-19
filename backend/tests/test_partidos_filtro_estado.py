"""TASK-012 (FUN-06): GET /partidos filtra por varios estados en el
servidor, ordena por fecha y devuelve el total. Control de Mesa y "Mis
partidos" pedían los 100 primeros por ID y filtraban en el navegador: con
más de 100 partidos jugados la lista quedaba vacía aunque hubiera
pendientes."""
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fase import Fase
from app.models.partido import Partido

TORNEO = 1  # 05_seed.sql: Tiburones(1), Águilas(2) y Halcones(3) inscriptos
PENDIENTES = 20
FINALIZADOS = 110


@pytest.fixture
async def torneo_con_130_partidos(db_session: AsyncSession) -> None:
    fase_id = (await db_session.execute(select(Fase.id).where(Fase.torneo_id == TORNEO))).scalars().first()
    base = datetime(2026, 2, 1, 16, 0)
    cruces = [(1, 2), (2, 3), (3, 1)]
    for i in range(FINALIZADOS + PENDIENTES):
        local, visitante = cruces[i % 3]
        pendiente = i >= FINALIZADOS
        db_session.add(
            Partido(
                torneo_id=TORNEO,
                equipos_id_local=local,
                equipos_id_visitante=visitante,
                # Los pendientes se crean en orden de fecha DESCENDENTE: si
                # la respuesta saliera por ID, no quedaría ordenada por fecha.
                fecha_partido=base + timedelta(days=(400 - i) if pendiente else i),
                jornada=i + 10,
                estado=("En curso" if i == FINALIZADOS else "Programado") if pendiente else "Finalizado",
                fase_id=fase_id,
            )
        )
    await db_session.commit()


async def test_varios_estados_traen_todos_los_pendientes_ordenados_por_fecha(
    client: AsyncClient, torneo_con_130_partidos: None
):
    """PR-013."""
    resp = await client.get(
        "/api/v1/partidos",
        params=[("torneo_id", TORNEO), ("estado", "Programado"), ("estado", "En curso"), ("orden", "fecha")],
    )
    assert resp.status_code == 200, resp.text
    partidos = resp.json()
    # + el partido 3 del seed, que también está Programado.
    assert len(partidos) == PENDIENTES + 1
    assert {p["estado"] for p in partidos} == {"Programado", "En curso"}
    fechas = [p["fecha_partido"] for p in partidos]
    assert fechas == sorted(fechas)
    assert resp.headers["X-Total-Count"] == str(PENDIENTES + 1)


async def test_un_solo_estado_sigue_funcionando(client: AsyncClient, torneo_con_130_partidos: None):
    resp = await client.get("/api/v1/partidos", params={"torneo_id": TORNEO, "estado": "En curso"})
    assert resp.status_code == 200, resp.text
    assert [p["estado"] for p in resp.json()] == ["En curso"]


async def test_el_total_avisa_cuando_hay_mas_que_la_pagina(client: AsyncClient, torneo_con_130_partidos: None):
    resp = await client.get("/api/v1/partidos", params={"torneo_id": TORNEO, "limit": 50})
    assert len(resp.json()) == 50
    assert int(resp.headers["X-Total-Count"]) == FINALIZADOS + PENDIENTES + 3


async def test_orden_por_defecto_sigue_siendo_por_id(client: AsyncClient):
    resp = await client.get("/api/v1/partidos", params={"torneo_id": TORNEO})
    ids = [p["id"] for p in resp.json()]
    assert ids == sorted(ids)


@pytest.mark.parametrize("params", [{"orden": "otro"}, {"estado": "Inventado"}, {"skip": -1}, {"limit": 0}])
async def test_parametros_invalidos_devuelven_422(client: AsyncClient, params: dict):
    resp = await client.get("/api/v1/partidos", params=params)
    assert resp.status_code == 422, resp.text
