"""TASK-017 (FUN-08, FUN-15, FUN-20): una sola regla de alta en plantilla
para el alta individual, el traspaso, la copia de plantilla base y el lote
(perfil de la disciplina, no suspendido, jugador activo, tope de la
modalidad); la edición de vínculos solo cambia el dorsal; y en vivo no se
cargan eventos de un jugador expulsado o que ya salió por cambio.

05_seed.sql: torneo 1 (Fútbol 11, modalidad 1). Tiburones = inscripción 1
(jugadores 1 y 2), Águilas = inscripción 2 (3 y 4), Halcones = 3 (5 y 6).
Eventos: 1 Gol, 3 Amarilla, 4 Roja, 5 Cambio.
"""
from datetime import date

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.jugador import Jugador
from app.models.jugador_equipo import JugadorEquipo
from app.models.jugador_perfil_disciplina import JugadorPerfilDisciplina
from app.models.modalidad import Modalidad
from tests.test_eventos_partido import _empezar_partido

TIBURONES = 1
AGUILAS = 2


async def _perfil_libre(db_session: AsyncSession, cedula: str, suspendido: bool = False, activo: bool = True) -> int:
    jugador = Jugador(
        nombre=f"Libre {cedula}", cedula=cedula, correo_electronico=f"{cedula}@test.com",
        estado="Activo" if activo else "Inactivo",
    )
    db_session.add(jugador)
    await db_session.flush()
    perfil = JugadorPerfilDisciplina(jugador_id=jugador.id, disciplina_id=1, suspendido=suspendido)
    db_session.add(perfil)
    await db_session.commit()
    return perfil.id


async def _alta(client: AsyncClient, headers: dict[str, str], perfil_id: int, inscripcion_id: int = TIBURONES):
    return await client.post(
        "/api/v1/plantillas",
        json={
            "jugador_perfil_id": perfil_id,
            "inscripcion_torneo_id": inscripcion_id,
            "dorsal": 70 + perfil_id % 20,
            "fecha_inicio": date.today().isoformat(),
        },
        headers=headers,
    )


TOPE = 11  # chk_modalidad_plantilla_max: el tope no baja de tamano_equipo (11)


async def _tope_con_ocupados(db_session: AsyncSession, inscripcion_id: int, ocupados: int) -> None:
    """Fija el tope de Fútbol 11 en TOPE y completa la plantilla de la
    inscripción hasta `ocupados` jugadores activos."""
    modalidad = await db_session.get(Modalidad, 1)
    modalidad.tamano_plantilla_max = TOPE
    actuales = len(
        (
            await db_session.execute(
                select(JugadorEquipo.id).where(
                    JugadorEquipo.inscripcion_torneo_id == inscripcion_id, JugadorEquipo.estado == "Activo"
                )
            )
        ).all()
    )
    for i in range(ocupados - actuales):
        jugador = Jugador(nombre=f"Relleno {inscripcion_id}-{i}", cedula=f"REL{inscripcion_id}{i:03d}", correo_electronico=f"rel{inscripcion_id}{i}@t.com")
        db_session.add(jugador)
        await db_session.flush()
        perfil = JugadorPerfilDisciplina(jugador_id=jugador.id, disciplina_id=1)
        db_session.add(perfil)
        await db_session.flush()
        db_session.add(JugadorEquipo(jugador_perfil_id=perfil.id, inscripcion_torneo_id=inscripcion_id, fecha_inicio="2026-01-01"))
    await db_session.commit()


# ---------- Alta: misma regla por todos los caminos ----------


async def test_alta_individual_que_supera_el_tope_usa_el_mensaje_del_lote(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """PR-017."""
    await _tope_con_ocupados(db_session, TIBURONES, TOPE)
    perfil = await _perfil_libre(db_session, "TOPE0001")
    resp = await _alta(client, admin_general_headers, perfil)
    assert resp.status_code == 400, resp.text
    assert resp.json()["detail"] == f"Esta modalidad admite máximo {TOPE} jugadores por equipo"


async def test_alta_individual_dentro_del_tope_funciona(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    await _tope_con_ocupados(db_session, TIBURONES, TOPE - 1)
    perfil = await _perfil_libre(db_session, "TOPE0002")
    assert (await _alta(client, admin_general_headers, perfil)).status_code == 201


async def test_perfil_suspendido_no_entra_por_alta_individual(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """PR-018."""
    perfil = await _perfil_libre(db_session, "SUSP0001", suspendido=True)
    resp = await _alta(client, admin_general_headers, perfil)
    assert resp.status_code == 400, resp.text
    assert "suspendido" in resp.json()["detail"].lower()


async def test_jugador_dado_de_baja_no_entra_por_alta_individual(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    perfil = await _perfil_libre(db_session, "BAJA0001", activo=False)
    resp = await _alta(client, admin_general_headers, perfil)
    assert resp.status_code == 400, resp.text


async def test_perfil_suspendido_no_entra_por_traspaso(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """PR-018: el jugador 1 está en Tiburones; se lo suspende y se intenta
    traspasarlo a Águilas."""
    perfil = (
        await db_session.execute(select(JugadorPerfilDisciplina).where(JugadorPerfilDisciplina.jugador_id == 1))
    ).scalar_one()
    perfil.suspendido = True
    await db_session.commit()

    resp = await client.post(
        "/api/v1/traspasos",
        json={"jugador_perfil_id": perfil.id, "inscripcion_origen_id": TIBURONES, "inscripcion_destino_id": AGUILAS},
        headers=admin_general_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "suspendido" in resp.json()["detail"].lower()


async def test_traspaso_que_supera_el_tope_del_destino_se_rechaza(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    await _tope_con_ocupados(db_session, AGUILAS, TOPE)
    perfil_id = (
        await db_session.execute(select(JugadorPerfilDisciplina.id).where(JugadorPerfilDisciplina.jugador_id == 1))
    ).scalar_one()
    resp = await client.post(
        "/api/v1/traspasos",
        json={"jugador_perfil_id": perfil_id, "inscripcion_origen_id": TIBURONES, "inscripcion_destino_id": AGUILAS},
        headers=admin_general_headers,
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["detail"] == f"Esta modalidad admite máximo {TOPE} jugadores por equipo"


# ---------- Edición de vínculos ----------


async def test_patch_de_vinculo_solo_cambia_el_dorsal(client: AsyncClient, admin_general_headers: dict[str, str]):
    h = admin_general_headers
    assert (await client.patch("/api/v1/plantillas/1", json={"estado": "Traspasado"}, headers=h)).status_code == 422
    assert (await client.patch("/api/v1/plantillas/1", json={"fecha_fin": "2026-01-02"}, headers=h)).status_code == 422
    resp = await client.patch("/api/v1/plantillas/1", json={"dorsal": 23}, headers=h)
    assert resp.status_code == 200, resp.text
    assert resp.json()["dorsal"] == 23


async def test_baja_con_fecha_anterior_al_inicio_se_rechaza(client: AsyncClient, admin_general_headers: dict[str, str]):
    # El vínculo 1 empieza el 2026-01-01.
    resp = await client.post("/api/v1/plantillas/1/baja", params={"fecha_fin": "2025-12-31"}, headers=admin_general_headers)
    assert resp.status_code == 400, resp.text


# ---------- Eventos en vivo ----------


async def _evento(client: AsyncClient, headers: dict[str, str], jugador_id: int, eventos_id: int, minuto: int, **extra):
    return await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": jugador_id, "equipo_id": 3, "eventos_id": eventos_id, "minuto": minuto, **extra},
        headers=headers,
    )


async def test_gol_de_un_expulsado_se_rechaza(
    client: AsyncClient, arbitro_headers: dict[str, str], convocar_titulares
):
    await _empezar_partido(client, arbitro_headers, convocar_titulares)
    assert (await _evento(client, arbitro_headers, 5, 4, 20)).status_code == 201
    resp = await _evento(client, arbitro_headers, 5, 1, 30)
    assert resp.status_code == 400, resp.text
    assert "expulsado" in resp.json()["detail"].lower()


async def test_gol_de_quien_salio_por_cambio_se_rechaza(
    client: AsyncClient, arbitro_headers: dict[str, str], convocar_titulares
):
    await _empezar_partido(client, arbitro_headers, convocar_titulares)
    resp = await _evento(client, arbitro_headers, 5, 5, 20, jugador_id_entra=6)
    assert resp.status_code == 201, resp.text
    resp = await _evento(client, arbitro_headers, 5, 1, 30)
    assert resp.status_code == 400, resp.text
    assert "salió" in resp.json()["detail"].lower()


async def test_quien_entra_por_cambio_puede_hacer_un_gol(
    client: AsyncClient, arbitro_headers: dict[str, str], convocar_titulares
):
    await _empezar_partido(client, arbitro_headers, convocar_titulares)
    assert (await _evento(client, arbitro_headers, 5, 5, 20, jugador_id_entra=6)).status_code == 201
    assert (await _evento(client, arbitro_headers, 6, 1, 30)).status_code == 201


async def test_una_amarilla_no_impide_seguir_jugando(
    client: AsyncClient, arbitro_headers: dict[str, str], convocar_titulares
):
    await _empezar_partido(client, arbitro_headers, convocar_titulares)
    assert (await _evento(client, arbitro_headers, 5, 3, 20)).status_code == 201
    assert (await _evento(client, arbitro_headers, 5, 1, 30)).status_code == 201
