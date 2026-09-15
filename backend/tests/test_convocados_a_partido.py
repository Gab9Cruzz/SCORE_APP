"""Titular/suplente/convocados a un partido (3B-2,
docs/plans/cierre-backlog-todos-plan.md). Partido 3 (05_seed.sql): torneo
1, Halcones(3) vs Tiburones(1), árbitro_test asignado. Andrés Vera
(jugador 5) está en Halcones; Carlos Pérez (jugador 1) está en Tiburones.
"""
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

PARTIDO_3 = 3


async def _perfil_de(client: AsyncClient, jugador_id: int, disciplina_id: int = 1) -> int:
    resp = await client.get("/api/v1/perfiles", params={"jugador_id": jugador_id, "disciplina_id": disciplina_id})
    return resp.json()[0]["id"]


async def test_definir_convocatoria_y_listarla(client: AsyncClient, arbitro_headers: dict[str, str]):
    perfil_andres = await _perfil_de(client, 5)  # Halcones
    perfil_carlos = await _perfil_de(client, 1)  # Tiburones

    resp = await client.put(
        f"/api/v1/partidos/{PARTIDO_3}/convocados",
        json={
            "convocados": [
                {"jugador_perfil_id": perfil_andres, "titular": True},
                {"jugador_perfil_id": perfil_carlos, "titular": False},
            ]
        },
        headers=arbitro_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 2
    titulares = {c["jugador_perfil_id"] for c in body if c["titular"]}
    assert titulares == {perfil_andres}

    resp = await client.get(f"/api/v1/partidos/{PARTIDO_3}/convocados")
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == 2


async def test_reemplazar_convocatoria_pisa_la_lista_anterior(client: AsyncClient, arbitro_headers: dict[str, str]):
    perfil_andres = await _perfil_de(client, 5)
    perfil_carlos = await _perfil_de(client, 1)

    await client.put(
        f"/api/v1/partidos/{PARTIDO_3}/convocados",
        json={"convocados": [{"jugador_perfil_id": perfil_andres, "titular": True}]},
        headers=arbitro_headers,
    )
    resp = await client.put(
        f"/api/v1/partidos/{PARTIDO_3}/convocados",
        json={"convocados": [{"jugador_perfil_id": perfil_carlos, "titular": True}]},
        headers=arbitro_headers,
    )
    assert resp.status_code == 200, resp.text

    resp = await client.get(f"/api/v1/partidos/{PARTIDO_3}/convocados")
    body = resp.json()
    assert len(body) == 1
    assert body[0]["jugador_perfil_id"] == perfil_carlos


async def test_convocatoria_vacia_saca_todo(client: AsyncClient, arbitro_headers: dict[str, str]):
    perfil_andres = await _perfil_de(client, 5)
    await client.put(
        f"/api/v1/partidos/{PARTIDO_3}/convocados",
        json={"convocados": [{"jugador_perfil_id": perfil_andres, "titular": True}]},
        headers=arbitro_headers,
    )

    resp = await client.put(
        f"/api/v1/partidos/{PARTIDO_3}/convocados", json={"convocados": []}, headers=arbitro_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == []

    resp = await client.get(f"/api/v1/partidos/{PARTIDO_3}/convocados")
    assert resp.json() == []


async def test_jugador_ajeno_a_ambos_equipos_es_rechazado(client: AsyncClient, arbitro_headers: dict[str, str]):
    # Jugador 3 — Activo en Águilas (Equipo_ID=2, 05_seed.sql), el TERCER
    # equipo del torneo que no juega este partido (Halcones=3 vs
    # Tiburones=1).
    perfil_ajeno = await _perfil_de(client, 3)

    resp = await client.put(
        f"/api/v1/partidos/{PARTIDO_3}/convocados",
        json={"convocados": [{"jugador_perfil_id": perfil_ajeno, "titular": False}]},
        headers=arbitro_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "no pertenece" in resp.json()["detail"].lower()


async def test_mismo_jugador_dos_veces_en_la_lista_es_rechazado(
    client: AsyncClient, arbitro_headers: dict[str, str]
):
    perfil_andres = await _perfil_de(client, 5)

    resp = await client.put(
        f"/api/v1/partidos/{PARTIDO_3}/convocados",
        json={
            "convocados": [
                {"jugador_perfil_id": perfil_andres, "titular": True},
                {"jugador_perfil_id": perfil_andres, "titular": False},
            ]
        },
        headers=arbitro_headers,
    )
    assert resp.status_code == 400, resp.text


async def test_arbitro_no_asignado_no_puede_definir_convocatoria(
    client: AsyncClient, arbitro_no_asignado_headers: dict[str, str]
):
    resp = await client.put(
        f"/api/v1/partidos/{PARTIDO_3}/convocados", json={"convocados": []}, headers=arbitro_no_asignado_headers
    )
    assert resp.status_code == 403, resp.text


async def test_torneo_admin_puede_definir_convocatoria(client: AsyncClient, torneo_admin_con_torneo_headers: dict[str, str]):
    resp = await client.put(
        f"/api/v1/partidos/{PARTIDO_3}/convocados", json={"convocados": []}, headers=torneo_admin_con_torneo_headers
    )
    assert resp.status_code == 200, resp.text


async def test_definir_convocatoria_sin_auth_falla(client: AsyncClient):
    resp = await client.put(f"/api/v1/partidos/{PARTIDO_3}/convocados", json={"convocados": []})
    assert resp.status_code == 401


async def test_jugador_traspasado_despues_de_la_fecha_del_partido_es_rechazado(
    client: AsyncClient, db_session: AsyncSession, arbitro_headers: dict[str, str]
):
    """control-mesa-reactividad-playoffs-plan.md, Fase 3 §4 — bug de
    "date-effective": Partido 3 (05_seed.sql) es Halcones(3) vs
    Tiburones(1), fecha 2026-01-29. Carlos Pérez (jugador 1, perfil ya
    existente) está en Tiburones desde 2026-01-01. Acá se lo suma a
    Halcones con Fecha_Inicio POSTERIOR a la fecha de Partido 3
    (2026-02-15) — mismo perfil, transferido "hoy" pero recién a partir de
    una fecha futura respecto de este partido. Antes de este fix,
    `plantilla_equipo` (vw_jugadores_activos_por_equipo, "vigente hoy") lo
    ofrecía igual como candidato de Halcones para Partido 3 — exactamente
    el bug reportado ("convocó a un jugador que no pertenecía a ese equipo
    en la fecha de ese partido")."""
    perfil_carlos = await _perfil_de(client, 1)  # Tiburones desde 2026-01-01

    # fn_validar_exclusividad_torneo prohíbe 2 membresías ACTIVAS del mismo
    # perfil en el mismo torneo a la vez — se cierra la de Tiburones antes
    # de abrir la de Halcones, como haría un traspaso real.
    await db_session.execute(
        text(
            "UPDATE jugador_equipo SET fecha_fin = '2026-02-10', estado = 'Traspasado' "
            "WHERE jugador_perfil_id = :perfil_id AND estado = 'Activo'"
        ),
        {"perfil_id": perfil_carlos},
    )
    insc_halcones = await db_session.execute(
        text("SELECT id FROM inscripciones_torneo WHERE torneo_id = 1 AND equipo_id = 3")
    )
    insc_halcones_id = insc_halcones.scalar_one()
    await db_session.execute(
        text(
            "INSERT INTO jugador_equipo (jugador_perfil_id, inscripcion_torneo_id, dorsal, fecha_inicio) "
            "VALUES (:perfil_id, :insc_id, 99, '2026-02-15')"
        ),
        {"perfil_id": perfil_carlos, "insc_id": insc_halcones_id},
    )
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/partidos/{PARTIDO_3}/convocados",
        json={"convocados": [{"jugador_perfil_id": perfil_carlos, "titular": False}]},
        headers=arbitro_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "no pertenece" in resp.json()["detail"].lower()
