"""TASK-008 (FUN-02): un jugador es válido en un partido si su membresía
cubría la FECHA del partido, aunque hoy ya no esté 'Activo' (traspasado o
dado de baja después). Antes `fn_validar_jugador_partido` exigía además
`Estado = 'Activo'` hoy, y no se podía completar el acta de un partido
anterior a un traspaso.

05_seed.sql: partido 3 (2026-01-29, Halcones=equipo 3 vs Tiburones=equipo
1) está 'Programado'. Jugadores 5 y 6 están en Halcones (inscripción 3)
desde 2026-01-01; Águilas es la inscripción 2. Evento 1 = Gol.
"""
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.jugador import Jugador
from app.models.jugador_equipo import JugadorEquipo
from app.models.jugador_perfil_disciplina import JugadorPerfilDisciplina

PARTIDO = 3
HALCONES_EQUIPO = 3
HALCONES_INSCRIPCION = 3
AGUILAS_INSCRIPCION = 2
GOL = 1


async def _vinculo_de(db_session: AsyncSession, jugador_id: int) -> JugadorEquipo:
    stmt = (
        select(JugadorEquipo)
        .join(JugadorPerfilDisciplina, JugadorPerfilDisciplina.id == JugadorEquipo.jugador_perfil_id)
        .where(
            JugadorPerfilDisciplina.jugador_id == jugador_id,
            JugadorEquipo.inscripcion_torneo_id == HALCONES_INSCRIPCION,
        )
    )
    return (await db_session.execute(stmt)).scalars().one()


async def _gol_de(client: AsyncClient, headers: dict[str, str], jugador_id: int):
    return await client.post(
        f"/api/v1/partidos/{PARTIDO}/resultado-directo",
        json={"eventos": [{"jugador_id": jugador_id, "equipo_id": HALCONES_EQUIPO, "eventos_id": GOL, "minuto": 10}]},
        headers=headers,
    )


async def test_tras_un_traspaso_se_carga_un_partido_anterior_con_el_equipo_de_origen(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_general_headers: dict[str, str],
    arbitro_headers: dict[str, str],
):
    """PR-003: el traspaso cierra la membresía de origen hoy; el partido es
    de enero, cuando el jugador sí estaba en Halcones."""
    vinculo = await _vinculo_de(db_session, 5)
    resp = await client.post(
        "/api/v1/traspasos",
        json={
            "jugador_perfil_id": vinculo.jugador_perfil_id,
            "inscripcion_origen_id": HALCONES_INSCRIPCION,
            "inscripcion_destino_id": AGUILAS_INSCRIPCION,
            "dorsal_nuevo": 77,
            "motivo": "TASK-008",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text

    resp = await _gol_de(client, arbitro_headers, 5)
    assert resp.status_code == 200, resp.text


async def test_tras_una_baja_posterior_al_partido_se_carga_el_partido(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_general_headers: dict[str, str],
    arbitro_headers: dict[str, str],
):
    """PR-004."""
    vinculo = await _vinculo_de(db_session, 6)
    resp = await client.post(
        f"/api/v1/plantillas/{vinculo.id}/baja",
        params={"fecha_fin": "2026-02-15"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text

    resp = await _gol_de(client, arbitro_headers, 6)
    assert resp.status_code == 200, resp.text


async def test_baja_anterior_al_partido_sigue_rechazando(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_general_headers: dict[str, str],
    arbitro_headers: dict[str, str],
):
    vinculo = await _vinculo_de(db_session, 6)
    resp = await client.post(
        f"/api/v1/plantillas/{vinculo.id}/baja",
        params={"fecha_fin": "2026-01-20"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text

    resp = await _gol_de(client, arbitro_headers, 6)
    assert resp.status_code == 400, resp.text
    assert "fecha" in resp.json()["detail"].lower()


async def test_membresia_que_empieza_despues_del_partido_sigue_rechazando(
    client: AsyncClient, db_session: AsyncSession, arbitro_headers: dict[str, str]
):
    """PR-005."""
    jugador = Jugador(nombre="Llegó Tarde", cedula="TASK008-01", correo_electronico="tarde@test.com")
    db_session.add(jugador)
    await db_session.flush()
    perfil = JugadorPerfilDisciplina(jugador_id=jugador.id, disciplina_id=1)
    db_session.add(perfil)
    await db_session.flush()
    db_session.add(
        JugadorEquipo(
            jugador_perfil_id=perfil.id,
            inscripcion_torneo_id=HALCONES_INSCRIPCION,
            fecha_inicio="2026-02-01",
            estado="Activo",
        )
    )
    await db_session.commit()

    resp = await _gol_de(client, arbitro_headers, jugador.id)
    assert resp.status_code == 400, resp.text
    assert "fecha" in resp.json()["detail"].lower()


async def test_jugador_suspendido_sigue_rechazado(
    client: AsyncClient, db_session: AsyncSession, arbitro_headers: dict[str, str]
):
    vinculo = await _vinculo_de(db_session, 5)
    vinculo.estado = "Suspendido"
    await db_session.commit()

    resp = await _gol_de(client, arbitro_headers, 5)
    assert resp.status_code == 400, resp.text


async def test_membresia_cerrada_sin_fecha_de_fin_no_vale_para_siempre(
    client: AsyncClient, db_session: AsyncSession, arbitro_headers: dict[str, str]
):
    """Defensa: una fila 'Inactivo' sin Fecha_Fin no tiene vigencia
    conocida, así que no habilita al jugador en ningún partido."""
    vinculo = await _vinculo_de(db_session, 5)
    await db_session.execute(
        text("UPDATE JUGADOR_EQUIPO SET Estado = 'Inactivo', Fecha_Fin = NULL WHERE ID = :id"), {"id": vinculo.id}
    )
    await db_session.commit()

    resp = await _gol_de(client, arbitro_headers, 5)
    assert resp.status_code == 400, resp.text


async def test_convocatoria_ofrece_al_jugador_traspasado_para_un_partido_anterior(
    db_session: AsyncSession,
):
    """`plantilla_equipo_en_fecha` aplica el mismo criterio que el trigger:
    lo que ofrece la convocatoria es lo que el trigger acepta."""
    from app.repositories.estadisticas import EstadisticasRepository

    vinculo = await _vinculo_de(db_session, 5)
    await db_session.execute(
        text("UPDATE JUGADOR_EQUIPO SET Estado = 'Traspasado', Fecha_Fin = '2026-03-01' WHERE ID = :id"),
        {"id": vinculo.id},
    )
    await db_session.commit()

    filas = await EstadisticasRepository(db_session).plantilla_equipo_en_fecha(HALCONES_EQUIPO, 1, "2026-01-29")
    assert 5 in [f["jugador_id"] for f in filas]
