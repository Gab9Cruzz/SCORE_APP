"""TASK-021 (SEC-09, FUN-22): el árbitro solo edita de su partido lo que su
papel necesita (desempate y ganador de un partido corrido), y como árbitro
solo se asigna una cuenta activa con rol Arbitro.

`arbitro_headers` (conftest) es el árbitro asignado al partido 3."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import _crear_usuario


@pytest.mark.parametrize(
    "cuerpo",
    [{"arbitro_id": None}, {"fecha_partido": "2026-02-01T16:00:00"}, {"jornada": 9}, {"fase": "Final"}],
)
async def test_el_arbitro_no_cambia_datos_de_organizacion(
    client: AsyncClient, arbitro_headers: dict[str, str], cuerpo: dict
):
    """PR-040."""
    resp = await client.patch("/api/v1/partidos/3", json=cuerpo, headers=arbitro_headers)
    assert resp.status_code == 403, resp.text


async def test_el_arbitro_si_carga_el_desempate(client: AsyncClient, arbitro_headers: dict[str, str]):
    resp = await client.patch("/api/v1/partidos/3", json={"hubo_tiempo_extra": False}, headers=arbitro_headers)
    assert resp.status_code == 200, resp.text


async def test_el_torneo_admin_si_cambia_fecha_y_arbitro(
    client: AsyncClient, torneo_admin_con_torneo_headers: dict[str, str], arbitro_headers: dict[str, str]
):
    h = torneo_admin_con_torneo_headers
    resp = await client.patch("/api/v1/partidos/3", json={"fecha_partido": "2026-02-02T18:00:00"}, headers=h)
    assert resp.status_code == 200, resp.text
    resp = await client.patch("/api/v1/partidos/3", json={"arbitro_id": None}, headers=h)
    assert resp.status_code == 200, resp.text


async def test_asignar_como_arbitro_a_quien_no_lo_es_es_400(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    otro = await _crear_usuario(db_session, "no_es_arbitro", "nopass12345", "TorneoAdmin")
    resp = await client.patch("/api/v1/partidos/3", json={"arbitro_id": otro.id}, headers=admin_general_headers)
    assert resp.status_code == 400, resp.text
    assert "árbitro" in resp.json()["detail"].lower()


async def test_asignar_un_arbitro_inactivo_es_400(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    arbitro = await _crear_usuario(db_session, "arbitro_de_baja", "arbpass12345", "Arbitro")
    arbitro.estado = "Inactivo"
    await db_session.commit()
    resp = await client.patch("/api/v1/partidos/3", json={"arbitro_id": arbitro.id}, headers=admin_general_headers)
    assert resp.status_code == 400, resp.text


async def test_asignar_un_arbitro_valido_funciona(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    arbitro = await _crear_usuario(db_session, "arbitro_nuevo", "arbpass12345", "Arbitro")
    resp = await client.patch("/api/v1/partidos/3", json={"arbitro_id": arbitro.id}, headers=admin_general_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["arbitro_id"] == arbitro.id
