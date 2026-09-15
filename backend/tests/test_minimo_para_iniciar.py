"""Mínimo reglamentario para iniciar un partido
(docs/plans/gestionar-partido-alineaciones-plan.md, D1).

`Torneo.minimo_jugadores_para_iniciar` permite arrancar con MENOS jugadores que
los que la modalidad pone en cancha (ej. Fútbol 11 con 7). `NULL` = exigir el
equipo completo, que es el comportamiento previo a esta columna — por eso la
migración no hace backfill.

Mismo patrón ad-hoc que `test_titulares_inicio_partido.py`: cada test arma su
torneo para controlar exactamente cuántos jugadores tiene cada lado.
"""
from datetime import date, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.configuracion_tiempo_torneo import ConfiguracionTiempoTorneo
from app.models.convocado_a_partido import ConvocadoAPartido
from app.models.disciplina import Disciplina
from app.models.equipo import Equipo
from app.models.inscripcion_torneo import InscripcionTorneo
from app.models.jugador import Jugador
from app.models.jugador_equipo import JugadorEquipo
from app.models.jugador_perfil_disciplina import JugadorPerfilDisciplina
from app.models.modalidad import Modalidad
from app.models.partido import Partido
from app.models.torneo import Torneo
from app.models.torneo_grupo import TorneoGrupo


async def _armar(
    db_session: AsyncSession, tamano_equipo: int, nombre: str, minimo: int | None = None
) -> dict:
    disciplina = Disciplina(nombre=f"Disciplina {nombre}")
    db_session.add(disciplina)
    await db_session.flush()
    modalidad = Modalidad(disciplina_id=disciplina.id, nombre=f"Mod {nombre}", tamano_equipo=tamano_equipo)
    db_session.add(modalidad)
    await db_session.flush()

    grupo = TorneoGrupo(nombre=f"Grupo {nombre}")
    db_session.add(grupo)
    await db_session.flush()
    torneo = Torneo(
        nombre=f"Torneo {nombre}",
        disciplina_id=disciplina.id,
        modalidad_id=modalidad.id,
        torneo_grupo_id=grupo.id,
        numero_edicion=1,
        fecha_inicio=date(2026, 7, 1),
        fecha_fin=date(2026, 8, 1),
        minimo_jugadores_para_iniciar=minimo,
    )
    db_session.add(torneo)
    await db_session.flush()
    db_session.add(ConfiguracionTiempoTorneo(torneo_id=torneo.id, tipo_cronometro="Corrido"))

    local = Equipo(nombre=f"{nombre} L", disciplina_id=disciplina.id, modalidad_id=modalidad.id)
    visitante = Equipo(nombre=f"{nombre} V", disciplina_id=disciplina.id, modalidad_id=modalidad.id)
    db_session.add_all([local, visitante])
    await db_session.flush()

    insc_l = InscripcionTorneo(torneo_id=torneo.id, equipo_id=local.id)
    insc_v = InscripcionTorneo(torneo_id=torneo.id, equipo_id=visitante.id)
    db_session.add_all([insc_l, insc_v])
    await db_session.flush()

    partido = Partido(
        torneo_id=torneo.id,
        equipos_id_local=local.id,
        equipos_id_visitante=visitante.id,
        fecha_partido=datetime(2026, 7, 5, 10, 0, 0),
        estado="Programado",
    )
    db_session.add(partido)
    await db_session.commit()
    return {
        "torneo_id": torneo.id,
        "modalidad_id": modalidad.id,
        "disciplina_id": disciplina.id,
        "insc_local_id": insc_l.id,
        "insc_visitante_id": insc_v.id,
        "partido_id": partido.id,
    }


async def _jugador(db_session: AsyncSession, disciplina_id: int, insc_id: int, sufijo: str) -> int:
    jugador = Jugador(
        nombre=f"Jug {sufijo}", cedula=f"777{sufijo}", correo_electronico=f"j{sufijo}@example.com"
    )
    db_session.add(jugador)
    await db_session.flush()
    perfil = JugadorPerfilDisciplina(jugador_id=jugador.id, disciplina_id=disciplina_id)
    db_session.add(perfil)
    await db_session.flush()
    db_session.add(
        JugadorEquipo(
            jugador_perfil_id=perfil.id,
            inscripcion_torneo_id=insc_id,
            fecha_inicio=date(2026, 1, 1),
            estado="Activo",
        )
    )
    await db_session.commit()
    return perfil.id


async def _convocar_n(db_session: AsyncSession, ctx: dict, cantidad_titulares: int, prefijo: str) -> None:
    """Deja `cantidad_titulares` titulares en CADA equipo."""
    for lado, insc in (("L", ctx["insc_local_id"]), ("V", ctx["insc_visitante_id"])):
        for i in range(cantidad_titulares):
            perfil = await _jugador(db_session, ctx["disciplina_id"], insc, f"{prefijo}{lado}{i}")
            db_session.add(
                ConvocadoAPartido(partido_id=ctx["partido_id"], jugador_perfil_id=perfil, titular=True)
            )
    await db_session.commit()


async def _empezar(client: AsyncClient, partido_id: int, headers: dict[str, str]):
    return await client.post(
        f"/api/v1/partidos/{partido_id}/hitos", json={"tipo_hito": "Inicio_Partido"}, headers=headers
    )


# ---------------------------------------------------------------- el mínimo


async def test_arranca_con_menos_que_el_equipo_completo(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """El caso que pidió el usuario: la modalidad pone 5 en cancha, el
    reglamento del torneo deja arrancar con 3, y hay 3."""
    ctx = await _armar(db_session, tamano_equipo=5, nombre="MinBaja", minimo=3)
    await _convocar_n(db_session, ctx, cantidad_titulares=3, prefijo="mb")

    resp = await _empezar(client, ctx["partido_id"], admin_general_headers)
    assert resp.status_code == 201, resp.text


async def test_rechaza_por_debajo_del_minimo_del_torneo(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    ctx = await _armar(db_session, tamano_equipo=5, nombre="MinFalta", minimo=3)
    await _convocar_n(db_session, ctx, cantidad_titulares=2, prefijo="mf")

    resp = await _empezar(client, ctx["partido_id"], admin_general_headers)
    assert resp.status_code == 400, resp.text
    detalle = resp.json()["detail"]
    # El mensaje dice de dónde sale el número: con un mínimo propio del torneo,
    # "esta modalidad exige N" sería mentira.
    assert "reglamento de este torneo" in detalle
    assert "3" in detalle


async def test_minimo_null_reproduce_el_comportamiento_de_siempre(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """No-regresión: sin mínimo configurado se sigue exigiendo el equipo
    completo. Es lo que hace que la migración no necesite backfill."""
    ctx = await _armar(db_session, tamano_equipo=3, nombre="MinNull", minimo=None)
    await _convocar_n(db_session, ctx, cantidad_titulares=2, prefijo="mn")

    resp = await _empezar(client, ctx["partido_id"], admin_general_headers)
    assert resp.status_code == 400, resp.text
    assert "esta modalidad exige" in resp.json()["detail"]


# ------------------------------------------------------- validación del campo


async def test_rechaza_minimo_mayor_que_el_tamano_del_equipo(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """El techo cruza tablas (TORNEO -> MODALIDAD), así que no puede ser un
    CHECK: lo valida TorneoService con un mensaje que dice el número real."""
    ctx = await _armar(db_session, tamano_equipo=5, nombre="MinAlto")

    resp = await client.patch(
        f"/api/v1/torneos/{ctx['torneo_id']}",
        json={"minimo_jugadores_para_iniciar": 12},
        headers=admin_general_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "5" in resp.json()["detail"]


async def test_rechaza_minimo_cero(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """Un mínimo de 0 convertiría "Empezar Partido" en un botón sin validación,
    que es el estado del que se salió a propósito."""
    ctx = await _armar(db_session, tamano_equipo=5, nombre="MinCero")

    resp = await client.patch(
        f"/api/v1/torneos/{ctx['torneo_id']}",
        json={"minimo_jugadores_para_iniciar": 0},
        headers=admin_general_headers,
    )
    assert resp.status_code in (400, 409, 422), resp.text


async def test_el_minimo_se_puede_volver_a_null(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """`BaseRepository.save_changes` descarta todo valor None, así que por la
    vía normal este campo sería imposible de limpiar una vez seteado — y todo el
    diseño depende de que NULL ("exigir el equipo completo") sea alcanzable."""
    ctx = await _armar(db_session, tamano_equipo=5, nombre="MinReset", minimo=3)

    resp = await client.patch(
        f"/api/v1/torneos/{ctx['torneo_id']}",
        json={"minimo_jugadores_para_iniciar": None},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["minimo_jugadores_para_iniciar"] is None

    resp = await client.get(f"/api/v1/torneos/{ctx['torneo_id']}", headers=admin_general_headers)
    assert resp.json()["minimo_jugadores_para_iniciar"] is None


async def test_no_tocar_el_campo_lo_deja_como_estaba(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """`exclude_unset` distingue "ausente del payload" de "presente y null":
    un PATCH de otro campo no puede borrar el mínimo por accidente."""
    ctx = await _armar(db_session, tamano_equipo=5, nombre="MinIntacto", minimo=3)

    resp = await client.patch(
        f"/api/v1/torneos/{ctx['torneo_id']}",
        json={"nombre": "Torneo Renombrado"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["minimo_jugadores_para_iniciar"] == 3


# ------------------------------------------------------------------ preflight


async def test_preflight_publica_el_veredicto_y_el_motivo(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """El frontend no reimplementa la regla: consume este veredicto, que sale
    del mismo código que aplica el gate real."""
    ctx = await _armar(db_session, tamano_equipo=5, nombre="Preflight", minimo=3)
    await _convocar_n(db_session, ctx, cantidad_titulares=2, prefijo="pf")

    resp = await client.get(
        f"/api/v1/partidos/{ctx['partido_id']}/preflight-inicio", headers=admin_general_headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["minimo_para_iniciar"] == 3
    assert body["puede_iniciar"] is False
    assert body["motivo_bloqueo"] is not None
    assert {t["titulares"] for t in body["titulares_por_equipo"]} == {2}


async def test_preflight_coincide_con_lo_que_permite_el_gate(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """Si divergieran, el botón se habilitaría y el POST devolvería 400."""
    ctx = await _armar(db_session, tamano_equipo=5, nombre="PreflightOk", minimo=3)
    await _convocar_n(db_session, ctx, cantidad_titulares=3, prefijo="po")

    resp = await client.get(
        f"/api/v1/partidos/{ctx['partido_id']}/preflight-inicio", headers=admin_general_headers
    )
    assert resp.json()["puede_iniciar"] is True

    assert (await _empezar(client, ctx["partido_id"], admin_general_headers)).status_code == 201


async def test_preflight_exige_autenticacion(client: AsyncClient, db_session: AsyncSession):
    """Endpoint propio y autenticado, no un campo de `/cronometro`: ese es
    público y se pollea cada 5s de forma anónima, así que meterle el cálculo de
    titulares (~7 queries + roster completo por equipo) lo volvería el endpoint
    más caro del sistema."""
    ctx = await _armar(db_session, tamano_equipo=5, nombre="PreflightAuth")

    resp = await client.get(f"/api/v1/partidos/{ctx['partido_id']}/preflight-inicio")
    assert resp.status_code in (401, 403), resp.text

    # El cronómetro sigue siendo público y NO expone el veredicto.
    resp = await client.get(f"/api/v1/partidos/{ctx['partido_id']}/cronometro")
    assert resp.status_code == 200, resp.text
    assert "puede_iniciar" not in resp.json()
