"""POST /partidos/{id}/resultado-directo (control-mesa-centralizacion-
fixture-plan.md, Sección 5 — Alternativa A): "Cargar resultado directo"
desde Control de Mesa, sin pasar por el cronómetro en vivo.

05_seed.sql: Partido 3 (Halcones=equipo 3 vs Tiburones=equipo 1, Torneo 1,
Fútbol → CONFIGURACION_TIEMPO_TORNEO Periodos) está 'Programado', sin
eventos ni hitos. Jugadores 5/6 pertenecen a Halcones (equipo 3); 1/2 a
Tiburones (equipo 1) — ver JUGADOR_EQUIPO en el seed. Eventos catálogo:
1=Gol, 2=Autogol, 3=Tarjeta Amarilla, 4=Tarjeta Roja, 5=Cambio.
"""
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evento_partido import EventoPartido
from app.models.hito_partido import HitoPartido
from app.models.partido import Partido
from app.models.usuario import Usuario


async def _hitos_de(db_session: AsyncSession, partido_id: int) -> list[HitoPartido]:
    stmt = select(HitoPartido).where(HitoPartido.partido_id == partido_id)
    return list((await db_session.execute(stmt)).scalars().all())


async def _eventos_de(db_session: AsyncSession, partido_id: int) -> list[EventoPartido]:
    stmt = select(EventoPartido).where(EventoPartido.partidos_id == partido_id)
    return list((await db_session.execute(stmt)).scalars().all())


async def test_resultado_directo_happy_path_dos_goles_y_una_tarjeta(
    client: AsyncClient, db_session: AsyncSession, arbitro_headers: dict[str, str]
):
    resp = await client.post(
        "/api/v1/partidos/3/resultado-directo",
        json={
            "eventos": [
                {"jugador_id": 5, "equipo_id": 3, "eventos_id": 1, "minuto": 10},  # Gol Halcones
                {"jugador_id": 1, "equipo_id": 1, "eventos_id": 1, "minuto": 30},  # Gol Tiburones
                {"jugador_id": 6, "equipo_id": 3, "eventos_id": 3, "minuto": 40},  # Amarilla Halcones
            ]
        },
        headers=arbitro_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["estado"] == "Finalizado"

    hitos = await _hitos_de(db_session, 3)
    tipos = sorted(h.tipo_hito for h in hitos)
    assert tipos == ["Fin_Partido", "Inicio_Partido"]

    eventos = await _eventos_de(db_session, 3)
    assert len(eventos) == 3
    assert all(e.estado == "Registrado" for e in eventos)


async def test_resultado_directo_sin_eventos_deja_0_0(
    client: AsyncClient, db_session: AsyncSession, arbitro_headers: dict[str, str]
):
    resp = await client.post("/api/v1/partidos/3/resultado-directo", json={"eventos": []}, headers=arbitro_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["estado"] == "Finalizado"
    assert await _eventos_de(db_session, 3) == []
    hitos = await _hitos_de(db_session, 3)
    assert len(hitos) == 2


async def test_resultado_directo_evento_invalido_a_mitad_revierte_todo(
    client: AsyncClient, db_session: AsyncSession, arbitro_headers: dict[str, str]
):
    """CRÍTICO (Sección 9/11 del plan): un evento inválido (jugador_id=3
    pertenece al equipo 2 — Águilas —, ajeno a este partido) a mitad de la
    lista debe revertir la transacción COMPLETA — ni el primer evento
    (válido) ni el Hito Inicio_Partido pueden quedar persistidos."""
    resp = await client.post(
        "/api/v1/partidos/3/resultado-directo",
        json={
            "eventos": [
                {"jugador_id": 5, "equipo_id": 3, "eventos_id": 1, "minuto": 10},  # válido
                {"jugador_id": 3, "equipo_id": 3, "eventos_id": 1, "minuto": 20},  # jugador ajeno al equipo
            ]
        },
        headers=arbitro_headers,
    )
    assert resp.status_code == 400, resp.text

    # Nada quedó persistido: ni el evento válido, ni el Hito de inicio.
    assert await _eventos_de(db_session, 3) == []
    assert await _hitos_de(db_session, 3) == []
    resp_partido = await client.get("/api/v1/partidos/3")
    assert resp_partido.json()["estado"] == "Programado"


async def test_resultado_directo_partido_finalizado_es_rechazado(
    client: AsyncClient, db_session: AsyncSession, arbitro_headers: dict[str, str]
):
    # Partido 1 (seed) ya está 'Finalizado' — sin árbitro asignado en el
    # seed, se lo asigna acá para aislar el chequeo de estado del de ownership.
    partido = await db_session.get(Partido, 1)
    arbitro = (
        await db_session.execute(select(Usuario).where(Usuario.username == "arbitro_test"))
    ).scalars().first()
    partido.arbitro_id = arbitro.id
    await db_session.commit()

    resp = await client.post("/api/v1/partidos/1/resultado-directo", json={"eventos": []}, headers=arbitro_headers)
    assert resp.status_code == 400, resp.text
    assert "Finalizado" in resp.json()["detail"]


async def test_resultado_directo_partido_sin_los_dos_equipos_definidos_es_rechazado(
    client: AsyncClient, db_session: AsyncSession, torneo_admin_con_torneo_headers: dict[str, str]
):
    # Un partido de bracket con equipos_id_local/visitante en NULL ("TBD")
    # — mismo criterio que marcar_walkover. Se arma un torneo de Eliminación
    # aparte en vez de tocar el seed, para no interferir con otros tests.
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "torneo_grupo_nombre": "Torneo Eliminacion Resultado Directo",
            "disciplina_id": 1,
            "modalidad_id": 1,
            "fecha_inicio": "2026-07-01",
            "fecha_fin": "2026-08-01",
            "formato": "Eliminacion",
        },
        headers=torneo_admin_con_torneo_headers,
    )
    torneo_id = resp.json()["id"]
    equipos = []
    for i in range(4):
        r = await client.post(
            "/api/v1/equipos",
            json={"nombre": f"Equipo Bracket RD {i}", "disciplina_id": 1, "modalidad_id": 1},
            headers=torneo_admin_con_torneo_headers,
        )
        equipos.append(r.json()["id"])
    for equipo_id in equipos:
        r = await client.post(
            "/api/v1/inscripciones",
            json={"torneo_id": torneo_id, "equipo_id": equipo_id},
            headers=torneo_admin_con_torneo_headers,
        )
        assert r.status_code == 201, r.text
    resp = await client.post(
        f"/api/v1/torneos/{torneo_id}/sorteo", json={}, headers=torneo_admin_con_torneo_headers
    )
    assert resp.status_code in (200, 201), resp.text

    resp_partidos = await client.get("/api/v1/partidos", params={"torneo_id": torneo_id})
    partido_tbd = next(
        p for p in resp_partidos.json() if p["equipos_id_local"] is None or p["equipos_id_visitante"] is None
    )

    resp = await client.post(
        f"/api/v1/partidos/{partido_tbd['id']}/resultado-directo",
        json={"eventos": []},
        headers=torneo_admin_con_torneo_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "equipos" in resp.json()["detail"].lower()


async def test_resultado_directo_requiere_asignacion_de_torneo(
    client: AsyncClient, torneo_admin_headers: dict[str, str]
):
    resp = await client.post(
        "/api/v1/partidos/3/resultado-directo", json={"eventos": []}, headers=torneo_admin_headers
    )
    assert resp.status_code == 403


async def test_resultado_directo_arbitro_no_asignado_es_rechazado(
    client: AsyncClient, arbitro_no_asignado_headers: dict[str, str]
):
    resp = await client.post(
        "/api/v1/partidos/3/resultado-directo", json={"eventos": []}, headers=arbitro_no_asignado_headers
    )
    assert resp.status_code == 403
