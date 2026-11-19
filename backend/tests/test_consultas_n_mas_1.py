"""TASK-023 (BE-01, DB-08): listar partidos y traspasos ejecuta un número de
consultas constante por página, no proporcional a las filas. Antes cada
partido de eliminación hacía hasta cuatro consultas y cada traspaso dos."""
from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fase import Fase
from app.models.partido import Partido
from app.models.traspaso import Traspaso
from app.models.usuario import Usuario


@contextmanager
def contar_consultas(engine):
    contador = {"n": 0}

    def _antes(*_args, **_kwargs):
        contador["n"] += 1

    event.listen(engine.sync_engine, "before_cursor_execute", _antes)
    try:
        yield contador
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _antes)


@pytest.fixture
async def eliminatoria_de_50(db_session: AsyncSession) -> None:
    """50 partidos de eliminación en el torneo 1 (05_seed.sql: equipos 1-3
    inscriptos), la mitad en llaves de ida y vuelta."""
    fase = Fase(torneo_id=1, nombre="Eliminatoria Carga", tipo="Eliminacion", orden=2, estado="En_Curso")
    db_session.add(fase)
    await db_session.flush()
    base = datetime(2026, 6, 1, 16, 0)
    cruces = [(1, 2), (2, 3), (3, 1)]
    for i in range(25):
        local, visitante = cruces[i % 3]
        ida = Partido(torneo_id=1, equipos_id_local=local, equipos_id_visitante=visitante,
                      fecha_partido=base + timedelta(days=2 * i), fase_id=fase.id, ronda_nombre="Octavos")
        db_session.add(ida)
        await db_session.flush()
        db_session.add(Partido(torneo_id=1, equipos_id_local=visitante, equipos_id_visitante=local,
                               fecha_partido=base + timedelta(days=2 * i + 1), fase_id=fase.id,
                               ronda_nombre="Octavos", partido_ida_id=ida.id))
    await db_session.commit()


async def _consultas_al_listar(client, engine, ruta: str, limit: int) -> tuple[int, int]:
    # Calentamiento: la primera petición de la sesión hace consultas de una
    # sola vez (tipos de Postgres) que no tienen que ver con la página.
    await client.get(ruta, params={"torneo_id": 1, "limit": 1})
    with contar_consultas(engine) as c:
        resp = await client.get(ruta, params={"torneo_id": 1, "limit": limit})
    assert resp.status_code == 200, resp.text
    return c["n"], len(resp.json())


async def test_listar_partidos_no_crece_con_la_pagina(client: AsyncClient, engine, eliminatoria_de_50):
    pocas, filas_pocas = await _consultas_al_listar(client, engine, "/api/v1/partidos", 5)
    muchas, filas_muchas = await _consultas_al_listar(client, engine, "/api/v1/partidos", 50)
    assert (filas_pocas, filas_muchas) == (5, 50)
    assert muchas == pocas


async def test_la_salida_del_listado_es_la_misma_que_la_del_detalle(
    client: AsyncClient, eliminatoria_de_50
):
    """Cargar en lote no puede cambiar lo que se devuelve."""
    listado = (await client.get("/api/v1/partidos", params={"torneo_id": 1, "limit": 60})).json()
    for p in listado[::7]:
        assert (await client.get(f"/api/v1/partidos/{p['id']}")).json() == p


async def test_listar_traspasos_no_crece_con_la_pagina(
    client: AsyncClient, engine, db_session: AsyncSession
):
    usuario_id = (await db_session.execute(Usuario.__table__.select().limit(1))).first()
    if usuario_id is None:
        u = Usuario(username="n1_traspasos", nombre="n", password_hash="x" * 60, rol="AdminGeneral")
        db_session.add(u)
        await db_session.flush()
        realizado_por = u.id
    else:
        realizado_por = usuario_id.id
    for i in range(30):
        db_session.add(Traspaso(jugador_perfil_id=1 + i % 6, inscripcion_origen_id=1 + i % 3,
                                inscripcion_destino_id=1 + (i + 1) % 3, realizado_por=realizado_por))
    await db_session.commit()

    pocas, filas_pocas = await _consultas_al_listar(client, engine, "/api/v1/traspasos", 5)
    muchas, filas_muchas = await _consultas_al_listar(client, engine, "/api/v1/traspasos", 30)
    assert (filas_pocas, filas_muchas) == (5, 30)
    assert muchas == pocas
