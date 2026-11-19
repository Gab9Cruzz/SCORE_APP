"""TASK-016 (FUN-07, FUN-21): transiciones de inscripción con reglas
explícitas y baja de equipo con guarda.

05_seed.sql: torneo 1 (Activo) con Tiburones (inscripción 1), Águilas (2)
y Halcones (3). Jugadores 5 y 6 en Halcones; partido 3 (Halcones vs
Tiburones) Programado.
"""
from datetime import date

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.equipo import Equipo
from app.models.jugador_equipo import JugadorEquipo
from app.models.partido import Partido
from app.models.torneo import Torneo

HALCONES = 3
TIBURONES = 1


async def _membresias(db_session: AsyncSession, inscripcion_id: int) -> list[JugadorEquipo]:
    db_session.expire_all()
    stmt = select(JugadorEquipo).where(JugadorEquipo.inscripcion_torneo_id == inscripcion_id)
    return list((await db_session.execute(stmt)).scalars().all())


async def _crear_torneo(client: AsyncClient, headers: dict[str, str], nombre: str, **extra) -> int:
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "torneo_grupo_nombre": nombre,
            "disciplina_id": 1,
            "modalidad_id": 1,
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-06-01",
            **extra,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _crear_equipo(client: AsyncClient, headers: dict[str, str], nombre: str) -> int:
    resp = await client.post(
        "/api/v1/equipos", json={"nombre": nombre, "disciplina_id": 1, "modalidad_id": 1}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ---------- Cancelar ----------


async def test_cancelar_cierra_las_membresias_y_libera_a_los_jugadores(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """PR-014."""
    resp = await client.patch(
        f"/api/v1/inscripciones/{HALCONES}", json={"estado": "Cancelado"}, headers=admin_general_headers
    )
    assert resp.status_code == 200, resp.text

    membresias = await _membresias(db_session, HALCONES)
    assert membresias and all(m.estado == "Inactivo" and m.fecha_fin == date.today() for m in membresias)

    # El jugador queda libre para otro equipo del mismo torneo.
    resp = await client.post(
        "/api/v1/plantillas",
        json={
            "jugador_perfil_id": membresias[0].jugador_perfil_id,
            "inscripcion_torneo_id": TIBURONES,
            "dorsal": 88,
            "fecha_inicio": date.today().isoformat(),
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text


async def test_no_se_cancela_con_un_partido_en_curso(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    partido = await db_session.get(Partido, 3)
    partido.estado = "En curso"
    await db_session.commit()

    resp = await client.patch(
        f"/api/v1/inscripciones/{HALCONES}", json={"estado": "Cancelado"}, headers=admin_general_headers
    )
    assert resp.status_code == 400, resp.text
    assert "en curso" in resp.json()["detail"].lower()
    assert all(m.estado == "Activo" for m in await _membresias(db_session, HALCONES))


# ---------- Reactivar ----------


async def test_reactivar_con_el_cupo_lleno_se_rechaza(client: AsyncClient, admin_general_headers: dict[str, str]):
    """PR-015."""
    h = admin_general_headers
    torneo_id = await _crear_torneo(client, h, "Copa Cupo Dos", cupo_maximo_inscripciones=2)
    inscripciones = []
    for i in range(2):
        equipo = await _crear_equipo(client, h, f"Cupo {i}")
        resp = await client.post("/api/v1/inscripciones", json={"torneo_id": torneo_id, "equipo_id": equipo}, headers=h)
        assert resp.status_code == 201, resp.text
        inscripciones.append(resp.json()["id"])

    resp = await client.patch(f"/api/v1/inscripciones/{inscripciones[0]}", json={"estado": "Cancelado"}, headers=h)
    assert resp.status_code == 200, resp.text
    tercero = await _crear_equipo(client, h, "Cupo 2")
    resp = await client.post("/api/v1/inscripciones", json={"torneo_id": torneo_id, "equipo_id": tercero}, headers=h)
    assert resp.status_code == 201, resp.text

    resp = await client.patch(f"/api/v1/inscripciones/{inscripciones[0]}", json={"estado": "Inscrito"}, headers=h)
    assert resp.status_code == 400, resp.text
    assert "cupo" in resp.json()["detail"].lower()


async def test_reactivar_con_cupo_disponible_funciona(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.patch(
        f"/api/v1/inscripciones/{HALCONES}", json={"estado": "Cancelado"}, headers=admin_general_headers
    )
    assert resp.status_code == 200, resp.text
    resp = await client.patch(
        f"/api/v1/inscripciones/{HALCONES}", json={"estado": "Confirmado"}, headers=admin_general_headers
    )
    assert resp.status_code == 200, resp.text


# ---------- Alta ----------


async def test_no_se_inscribe_en_un_torneo_que_no_esta_activo(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """PR-016."""
    h = admin_general_headers
    torneo_id = await _crear_torneo(client, h, "Copa Inactiva")
    torneo = await db_session.get(Torneo, torneo_id)
    torneo.estado = "Inactivo"
    await db_session.commit()

    equipo = await _crear_equipo(client, h, "Llega Tarde")
    resp = await client.post("/api/v1/inscripciones", json={"torneo_id": torneo_id, "equipo_id": equipo}, headers=h)
    assert resp.status_code == 400, resp.text
    assert "torneo" in resp.json()["detail"].lower()


async def test_no_se_inscribe_un_equipo_inactivo(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """PR-016."""
    h = admin_general_headers
    torneo_id = await _crear_torneo(client, h, "Copa Equipo Inactivo")
    equipo_id = await _crear_equipo(client, h, "Dado De Baja")
    equipo = await db_session.get(Equipo, equipo_id)
    equipo.estado = "Inactivo"
    await db_session.commit()

    resp = await client.post("/api/v1/inscripciones", json={"torneo_id": torneo_id, "equipo_id": equipo_id}, headers=h)
    assert resp.status_code == 400, resp.text
    assert "equipo" in resp.json()["detail"].lower()


# ---------- Baja de equipo ----------


async def test_no_se_da_de_baja_un_equipo_con_inscripcion_activa(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    resp = await client.delete(f"/api/v1/equipos/{TIBURONES}", headers=admin_general_headers)
    assert resp.status_code == 409, resp.text
    assert "inscrip" in resp.json()["detail"].lower()


async def test_equipo_con_la_inscripcion_cancelada_si_se_da_de_baja(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    h = admin_general_headers
    resp = await client.patch(f"/api/v1/inscripciones/{HALCONES}", json={"estado": "Cancelado"}, headers=h)
    assert resp.status_code == 200, resp.text
    resp = await client.delete(f"/api/v1/equipos/{HALCONES}", headers=h)
    assert resp.status_code == 200, resp.text
