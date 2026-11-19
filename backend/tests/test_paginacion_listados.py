"""TASK-011 (FUN-05, BE-06, UX-05): los listados de plantillas,
inscripciones, traspasos y eventos de partido aceptan `skip`/`limit` y
devuelven el total en la cabecera `X-Total-Count`. Antes no declaraban los
parámetros: FastAPI ignoraba el `limit=200` del frontend y el servicio
cortaba en 100 sin que nadie se enterara."""
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inscripcion_torneo import InscripcionTorneo
from app.models.jugador import Jugador
from app.models.jugador_equipo import JugadorEquipo
from app.models.jugador_perfil_disciplina import JugadorPerfilDisciplina

DISCIPLINA_FUTBOL_ID = 1
TOTAL_PLANTILLA = 150


@pytest.fixture
async def torneo_1_con_150_vinculos(db_session: AsyncSession) -> int:
    """Completa la plantilla del torneo 1 (05_seed.sql trae 6) hasta 150
    vínculos, repartidos entre sus tres equipos inscriptos."""
    inscripciones = list(
        (
            await db_session.execute(
                select(InscripcionTorneo.id).where(InscripcionTorneo.torneo_id == 1).order_by(InscripcionTorneo.id)
            )
        ).scalars()
    )
    existentes = (
        await db_session.execute(
            select(func.count())
            .select_from(JugadorEquipo)
            .join(InscripcionTorneo, InscripcionTorneo.id == JugadorEquipo.inscripcion_torneo_id)
            .where(InscripcionTorneo.torneo_id == 1)
        )
    ).scalar_one()
    for i in range(TOTAL_PLANTILLA - existentes):
        jugador = Jugador(nombre=f"Pag {i}", cedula=f"PAG{i:05d}", correo_electronico=f"pag{i}@test.com")
        db_session.add(jugador)
        await db_session.flush()
        perfil = JugadorPerfilDisciplina(jugador_id=jugador.id, disciplina_id=DISCIPLINA_FUTBOL_ID)
        db_session.add(perfil)
        await db_session.flush()
        db_session.add(
            JugadorEquipo(
                jugador_perfil_id=perfil.id,
                inscripcion_torneo_id=inscripciones[i % len(inscripciones)],
                fecha_inicio="2026-01-01",
                estado="Activo",
            )
        )
    await db_session.commit()
    return 1


async def test_plantilla_con_limit_200_devuelve_todo_y_el_total(
    client: AsyncClient, torneo_1_con_150_vinculos: int
):
    """PR-011."""
    resp = await client.get("/api/v1/plantillas", params={"torneo_id": torneo_1_con_150_vinculos, "limit": 200})
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == TOTAL_PLANTILLA
    assert resp.headers["X-Total-Count"] == str(TOTAL_PLANTILLA)


async def test_plantilla_sin_limit_devuelve_100_y_avisa_el_total(
    client: AsyncClient, torneo_1_con_150_vinculos: int
):
    """PR-012: el cliente puede saber que hay más de lo que recibió."""
    resp = await client.get("/api/v1/plantillas", params={"torneo_id": torneo_1_con_150_vinculos})
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 100
    assert resp.headers["X-Total-Count"] == str(TOTAL_PLANTILLA)


async def test_plantilla_skip_trae_la_pagina_siguiente_sin_solaparse(
    client: AsyncClient, torneo_1_con_150_vinculos: int
):
    primera = await client.get("/api/v1/plantillas", params={"torneo_id": 1, "limit": 100})
    segunda = await client.get("/api/v1/plantillas", params={"torneo_id": 1, "skip": 100, "limit": 100})
    ids_primera = {f["id"] for f in primera.json()}
    ids_segunda = {f["id"] for f in segunda.json()}
    assert len(ids_segunda) == TOTAL_PLANTILLA - 100
    assert ids_primera.isdisjoint(ids_segunda)
    assert segunda.headers["X-Total-Count"] == str(TOTAL_PLANTILLA)


async def test_plantilla_sin_torneo_tambien_informa_el_total(client: AsyncClient):
    """La rama sin `torneo_id` (filtro genérico) también cuenta."""
    resp = await client.get("/api/v1/plantillas", params={"inscripcion_torneo_id": 1})
    assert resp.status_code == 200
    assert resp.headers["X-Total-Count"] == str(len(resp.json()))


async def test_inscripciones_informan_el_total(client: AsyncClient):
    resp = await client.get("/api/v1/inscripciones", params={"torneo_id": 1, "limit": 2})
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 2
    assert resp.headers["X-Total-Count"] == "3"  # 05_seed.sql: 3 equipos en el torneo 1


async def test_traspasos_informan_el_total(client: AsyncClient):
    resp = await client.get("/api/v1/traspasos", params={"torneo_id": 1})
    assert resp.status_code == 200, resp.text
    assert resp.headers["X-Total-Count"] == str(len(resp.json()))


async def test_eventos_de_un_partido_informan_el_total_y_admiten_hasta_500(client: AsyncClient):
    """Un partido no se pagina: el tope sube a 500 para traerlo entero."""
    resp = await client.get("/api/v1/eventos-partido", params={"partidos_id": 1, "limit": 500})
    assert resp.status_code == 200, resp.text
    assert resp.headers["X-Total-Count"] == str(len(resp.json()))

    resp = await client.get("/api/v1/eventos-partido", params={"partidos_id": 1, "limit": 501})
    assert resp.status_code == 422


@pytest.mark.parametrize(
    "ruta", ["/api/v1/plantillas", "/api/v1/inscripciones", "/api/v1/traspasos", "/api/v1/eventos-partido"]
)
@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": -1}, {"skip": -1}])
async def test_parametros_de_paginacion_invalidos_devuelven_422(client: AsyncClient, ruta: str, params: dict):
    resp = await client.get(ruta, params=params)
    assert resp.status_code == 422, resp.text


@pytest.mark.parametrize("ruta", ["/api/v1/plantillas", "/api/v1/inscripciones", "/api/v1/traspasos"])
async def test_limit_por_encima_de_200_devuelve_422(client: AsyncClient, ruta: str):
    resp = await client.get(ruta, params={"limit": 201})
    assert resp.status_code == 422, resp.text


async def test_cors_expone_x_total_count(client: AsyncClient):
    """Sin `expose_headers`, el navegador oculta la cabecera al frontend."""
    resp = await client.get(
        "/api/v1/inscripciones", params={"torneo_id": 1}, headers={"Origin": "http://localhost:5173"}
    )
    assert "x-total-count" in resp.headers.get("access-control-expose-headers", "").lower()
