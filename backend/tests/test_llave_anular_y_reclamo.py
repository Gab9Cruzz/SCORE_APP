"""TASK-009 (FUN-03). Decisión del propietario (2026-11-18): cuando un
equipo ya avanzó de llave, el resultado no se cambia anulando eventos; si
corresponde, se resuelve por RECLAMO a favor del equipo que perdió, y ese
equipo pasa a avanzar en su lugar.

Escenario: copa de 4 equipos con tercer puesto. Una semifinal se cierra
1-0 o 2-0 (gana el local) y propaga: el local a la final, el visitante al
partido por el tercer puesto.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evento_partido import EventoPartido
from app.models.hito_partido import HitoPartido
from app.models.partido import Partido
from app.models.usuario import Usuario
from tests.test_cierre_torneo import _finalizar, _partidos_de, _torneo_con_equipos


async def _semi_cerrada(
    client: AsyncClient, headers: dict[str, str], db_session: AsyncSession, nombre: str, goles_local: int = 1
) -> tuple[dict, Partido]:
    torneo_id, _ = await _torneo_con_equipos(
        client, headers, 4, "Eliminacion", nombre, incluye_tercer_lugar=True
    )
    resp = await client.post(f"/api/v1/torneos/{torneo_id}/sorteo", json={}, headers=headers)
    assert resp.status_code == 200, resp.text
    semi = next(p for p in await _partidos_de(client, headers, torneo_id) if p["partido_siguiente_id"] is not None)
    assert semi["partido_perdedor_siguiente_id"] is not None
    await _finalizar(db_session, semi["id"], {semi["equipos_id_local"]: goles_local, semi["equipos_id_visitante"]: 0})
    final = await db_session.get(Partido, semi["partido_siguiente_id"])
    return semi, final


async def _goles_de(db_session: AsyncSession, partido_id: int) -> list[EventoPartido]:
    db_session.expire_all()
    stmt = select(EventoPartido).where(EventoPartido.partidos_id == partido_id).order_by(EventoPartido.id)
    return list((await db_session.execute(stmt)).scalars().all())


def _equipo_en_slot(partido: Partido, slot: str | None) -> int | None:
    return partido.equipos_id_local if slot == "Local" else partido.equipos_id_visitante


# ---------- Anular eventos en un partido de llave ya cerrado ----------


async def test_anular_el_gol_decisivo_de_una_llave_ya_avanzada_se_rechaza(
    client: AsyncClient, torneo_admin_headers: dict[str, str], db_session: AsyncSession
):
    """PR-006: el ganador ya avanzó; anular su único gol lo dejaría
    empatado. Se rechaza y se indica el camino del reclamo."""
    semi, _ = await _semi_cerrada(client, torneo_admin_headers, db_session, "Copa Anular Decisivo")
    (gol,) = await _goles_de(db_session, semi["id"])

    resp = await client.post(f"/api/v1/eventos-partido/{gol.id}/anular", headers=torneo_admin_headers)
    assert resp.status_code == 400, resp.text
    assert "reclamo" in resp.json()["detail"].lower()

    (gol,) = await _goles_de(db_session, semi["id"])
    assert gol.estado == "Registrado"
    final = await db_session.get(Partido, semi["partido_siguiente_id"])
    assert _equipo_en_slot(final, semi["slot_siguiente"]) == semi["equipos_id_local"]


async def test_anular_un_gol_que_no_cambia_el_ganador_sigue_permitido(
    client: AsyncClient, torneo_admin_headers: dict[str, str], db_session: AsyncSession
):
    """PR-007: 2-0 → 1-0, el ganador es el mismo."""
    semi, _ = await _semi_cerrada(client, torneo_admin_headers, db_session, "Copa Anular Inocuo", goles_local=2)
    gol = (await _goles_de(db_session, semi["id"]))[0]

    resp = await client.post(f"/api/v1/eventos-partido/{gol.id}/anular", headers=torneo_admin_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["estado"] == "Anulado"


async def test_en_liga_anular_tras_finalizar_no_cambia(
    client: AsyncClient, torneo_admin_headers: dict[str, str], db_session: AsyncSession
):
    torneo_id, equipos = await _torneo_con_equipos(client, torneo_admin_headers, 2, "Liga", "Liga Anular")
    resp = await client.post(f"/api/v1/torneos/{torneo_id}/fixture", headers=torneo_admin_headers)
    assert resp.status_code in (200, 201), resp.text
    partido = (await _partidos_de(client, torneo_admin_headers, torneo_id))[0]
    await _finalizar(db_session, partido["id"], {partido["equipos_id_local"]: 1, partido["equipos_id_visitante"]: 0})
    (gol,) = await _goles_de(db_session, partido["id"])

    resp = await client.post(f"/api/v1/eventos-partido/{gol.id}/anular", headers=torneo_admin_headers)
    assert resp.status_code == 200, resp.text


# ---------- Reclamo ----------


async def test_reclamo_a_favor_del_perdedor_lo_hace_avanzar(
    client: AsyncClient, torneo_admin_headers: dict[str, str], db_session: AsyncSession
):
    semi, _ = await _semi_cerrada(client, torneo_admin_headers, db_session, "Copa Reclamo")
    perdedor = semi["equipos_id_visitante"]
    ganador_en_cancha = semi["equipos_id_local"]

    resp = await client.post(
        f"/api/v1/partidos/{semi['id']}/reclamo",
        json={"equipo_id": perdedor, "motivo": "Alineación indebida del rival"},
        headers=torneo_admin_headers,
    )
    assert resp.status_code == 200, resp.text
    cuerpo = resp.json()
    assert cuerpo["ganador_reclamo_id"] == perdedor
    assert cuerpo["reclamo_motivo"] == "Alineación indebida del rival"

    db_session.expire_all()
    final = await db_session.get(Partido, semi["partido_siguiente_id"])
    tercero = await db_session.get(Partido, semi["partido_perdedor_siguiente_id"])
    assert _equipo_en_slot(final, semi["slot_siguiente"]) == perdedor
    assert _equipo_en_slot(tercero, semi["slot_perdedor_siguiente"]) == ganador_en_cancha

    # El marcador real no se toca: los goles siguen registrados.
    assert [g.estado for g in await _goles_de(db_session, semi["id"])] == ["Registrado"]


async def test_reclamo_a_favor_del_ganador_actual_se_rechaza(
    client: AsyncClient, torneo_admin_headers: dict[str, str], db_session: AsyncSession
):
    semi, _ = await _semi_cerrada(client, torneo_admin_headers, db_session, "Copa Reclamo Ganador")
    resp = await client.post(
        f"/api/v1/partidos/{semi['id']}/reclamo",
        json={"equipo_id": semi["equipos_id_local"], "motivo": "x" * 10},
        headers=torneo_admin_headers,
    )
    assert resp.status_code == 400, resp.text


async def test_reclamo_con_el_partido_siguiente_ya_empezado_se_rechaza(
    client: AsyncClient, torneo_admin_headers: dict[str, str], db_session: AsyncSession
):
    semi, final = await _semi_cerrada(client, torneo_admin_headers, db_session, "Copa Reclamo Tarde")
    usuario_id = (await db_session.execute(select(Usuario.id).limit(1))).scalar_one()
    db_session.add(
        HitoPartido(partido_id=final.id, tipo_hito="Inicio_Partido", minuto_reloj=0, registrado_por=usuario_id)
    )
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/partidos/{semi['id']}/reclamo",
        json={"equipo_id": semi["equipos_id_visitante"], "motivo": "Reclamo fuera de tiempo"},
        headers=torneo_admin_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "siguiente" in resp.json()["detail"].lower()


async def test_reclamo_en_un_partido_de_liga_se_rechaza(
    client: AsyncClient, torneo_admin_headers: dict[str, str], db_session: AsyncSession
):
    torneo_id, _ = await _torneo_con_equipos(client, torneo_admin_headers, 2, "Liga", "Liga Reclamo")
    resp = await client.post(f"/api/v1/torneos/{torneo_id}/fixture", headers=torneo_admin_headers)
    assert resp.status_code in (200, 201), resp.text
    partido = (await _partidos_de(client, torneo_admin_headers, torneo_id))[0]
    await _finalizar(db_session, partido["id"], {partido["equipos_id_local"]: 1, partido["equipos_id_visitante"]: 0})

    resp = await client.post(
        f"/api/v1/partidos/{partido['id']}/reclamo",
        json={"equipo_id": partido["equipos_id_visitante"], "motivo": "No aplica en liga"},
        headers=torneo_admin_headers,
    )
    assert resp.status_code == 400, resp.text


async def test_reclamo_en_un_partido_no_finalizado_se_rechaza(
    client: AsyncClient, torneo_admin_headers: dict[str, str], db_session: AsyncSession
):
    semi, final = await _semi_cerrada(client, torneo_admin_headers, db_session, "Copa Reclamo Abierto")
    # La final todavía no se jugó.
    resp = await client.post(
        f"/api/v1/partidos/{final.id}/reclamo",
        json={"equipo_id": semi["equipos_id_local"], "motivo": "Todavía no se jugó"},
        headers=torneo_admin_headers,
    )
    assert resp.status_code == 400, resp.text


async def test_arbitro_no_puede_resolver_un_reclamo(client: AsyncClient, arbitro_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/partidos/1/reclamo", json={"equipo_id": 2, "motivo": "Sin permiso"}, headers=arbitro_headers
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.parametrize("motivo", ["", "   ", None])
async def test_reclamo_exige_motivo(client: AsyncClient, admin_general_headers: dict[str, str], motivo):
    cuerpo = {"equipo_id": 2} if motivo is None else {"equipo_id": 2, "motivo": motivo}
    resp = await client.post("/api/v1/partidos/1/reclamo", json=cuerpo, headers=admin_general_headers)
    assert resp.status_code == 422, resp.text


async def test_tras_el_reclamo_anular_ya_no_mueve_la_llave(
    client: AsyncClient, torneo_admin_headers: dict[str, str], db_session: AsyncSession
):
    """Con el reclamo resuelto, el ganador ya no depende de los goles."""
    semi, _ = await _semi_cerrada(client, torneo_admin_headers, db_session, "Copa Reclamo Y Anular")
    await client.post(
        f"/api/v1/partidos/{semi['id']}/reclamo",
        json={"equipo_id": semi["equipos_id_visitante"], "motivo": "Alineación indebida"},
        headers=torneo_admin_headers,
    )
    (gol,) = await _goles_de(db_session, semi["id"])
    resp = await client.post(f"/api/v1/eventos-partido/{gol.id}/anular", headers=torneo_admin_headers)
    assert resp.status_code == 200, resp.text


async def test_un_partido_de_llave_no_se_cancela(
    client: AsyncClient, torneo_admin_headers: dict[str, str], db_session: AsyncSession
):
    """FUN-19: cancelar un partido de llave deja el cuadro sin ganador que
    propagar. Se resuelve por walkover."""
    semi, final = await _semi_cerrada(client, torneo_admin_headers, db_session, "Copa Cancelar Llave")
    resp = await client.delete(f"/api/v1/partidos/{final.id}", headers=torneo_admin_headers)
    assert resp.status_code in (200, 400), resp.text
    otra_semi = next(
        p for p in await _partidos_de(client, torneo_admin_headers, semi["torneo_id"])
        if p["partido_siguiente_id"] is not None and p["id"] != semi["id"]
    )
    resp = await client.delete(f"/api/v1/partidos/{otra_semi['id']}", headers=torneo_admin_headers)
    assert resp.status_code == 400, resp.text
    assert "walkover" in resp.json()["detail"].lower()
