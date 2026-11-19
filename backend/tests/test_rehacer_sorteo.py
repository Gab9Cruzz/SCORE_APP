"""TASK-018 (FUN-11): rehacer un sorteo nunca borra actividad registrada.
Antes alcanzaba con que no hubiera partidos Finalizado: uno En curso con
eventos, hitos o convocados se borraba entero."""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hito_partido import HitoPartido
from app.models.partido import Partido
from app.models.usuario import Usuario
from tests.test_motor_formatos import _torneo_con_equipos


async def _copa_sorteada(client: AsyncClient, headers: dict[str, str], nombre: str) -> tuple[int, list[dict]]:
    torneo_id, _ = await _torneo_con_equipos(client, headers, 4, formato="Eliminacion", nombre=nombre)
    resp = await client.post(f"/api/v1/torneos/{torneo_id}/sorteo", json={}, headers=headers)
    assert resp.status_code == 200, resp.text
    bracket = (await client.get(f"/api/v1/torneos/{torneo_id}/bracket", headers=headers)).json()
    return torneo_id, bracket


async def test_con_un_partido_en_curso_rehacer_se_rechaza_y_no_borra_nada(
    client: AsyncClient, torneo_admin_headers: dict[str, str], db_session: AsyncSession
):
    """PR-022."""
    torneo_id, bracket = await _copa_sorteada(client, torneo_admin_headers, "Copa No Rehacer")
    semi = next(p for p in bracket if p["partido_siguiente_id"] is not None)
    partido = await db_session.get(Partido, semi["id"])
    partido.estado = "En curso"
    await db_session.commit()

    resp = await client.post(f"/api/v1/torneos/{torneo_id}/sorteo", json={}, headers=torneo_admin_headers)
    assert resp.status_code == 400, resp.text
    assert f"#{semi['id']}" in resp.json()["detail"]

    despues = (await client.get(f"/api/v1/torneos/{torneo_id}/bracket", headers=torneo_admin_headers)).json()
    assert sorted(p["id"] for p in despues) == sorted(p["id"] for p in bracket)


async def test_un_partido_programado_con_hitos_tambien_lo_impide(
    client: AsyncClient, torneo_admin_headers: dict[str, str], db_session: AsyncSession
):
    torneo_id, bracket = await _copa_sorteada(client, torneo_admin_headers, "Copa Con Hitos")
    semi = next(p for p in bracket if p["partido_siguiente_id"] is not None)
    usuario_id = (await db_session.execute(select(Usuario.id).limit(1))).scalar_one()
    db_session.add(HitoPartido(partido_id=semi["id"], tipo_hito="Inicio_Partido", minuto_reloj=0, registrado_por=usuario_id))
    await db_session.commit()

    resp = await client.post(f"/api/v1/torneos/{torneo_id}/sorteo", json={}, headers=torneo_admin_headers)
    assert resp.status_code == 400, resp.text
    assert f"#{semi['id']}" in resp.json()["detail"]


@pytest.mark.parametrize("veces", [1, 2])
async def test_sin_actividad_rehacer_sigue_funcionando(
    client: AsyncClient, torneo_admin_headers: dict[str, str], veces: int
):
    torneo_id, _ = await _copa_sorteada(client, torneo_admin_headers, f"Copa Rehacer Libre {veces}")
    for _ in range(veces):
        resp = await client.post(f"/api/v1/torneos/{torneo_id}/sorteo", json={}, headers=torneo_admin_headers)
        assert resp.status_code == 200, resp.text
    assert len((await client.get(f"/api/v1/torneos/{torneo_id}/bracket", headers=torneo_admin_headers)).json()) == 4
