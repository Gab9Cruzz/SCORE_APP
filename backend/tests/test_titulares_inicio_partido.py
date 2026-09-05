"""B.2 (fixes-datos-traspasos-control-mesa-plan.md, D4): validación de
titulares al registrar el hito Inicio_Partido — HitoPartidoService.
_validar_titulares. Cada test arma su propio torneo/equipos/roster (mismo
patrón ad-hoc que test_finalizar_corrido_sin_ganador_es_rechazado en
test_control_mesa_tiempos.py) para controlar exactamente cuántos jugadores
activos/convocados tiene cada lado, sin depender del roster fijo del seed.
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


async def _armar_torneo_con_partido(
    db_session: AsyncSession, tamano_equipo: int, nombre: str
) -> dict:
    """Torneo nuevo con una Modalidad ad-hoc de `tamano_equipo` (no reusa
    Fútbol 11 del seed, para poder probar Pareja=2 sin catálogo nuevo) +
    2 equipos inscritos + 1 partido 'Programado' entre ambos."""
    disciplina = Disciplina(nombre=f"Disciplina {nombre}")
    db_session.add(disciplina)
    await db_session.flush()
    modalidad = Modalidad(disciplina_id=disciplina.id, nombre=f"Modalidad {nombre}", tamano_equipo=tamano_equipo)
    db_session.add(modalidad)
    await db_session.flush()

    grupo = TorneoGrupo(nombre=f"Torneo {nombre}")
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
    )
    db_session.add(torneo)
    await db_session.flush()
    # HitoPartidoService._cargar_contexto exige config de tiempos antes de
    # cualquier otra validación (incluida la de titulares) — sin esto el
    # 400 sería "sin configuración de tiempos", no el que este archivo prueba.
    db_session.add(ConfiguracionTiempoTorneo(torneo_id=torneo.id, tipo_cronometro="Corrido"))

    equipo_local = Equipo(nombre=f"{nombre} Local", disciplina_id=disciplina.id, modalidad_id=modalidad.id)
    equipo_visitante = Equipo(nombre=f"{nombre} Visitante", disciplina_id=disciplina.id, modalidad_id=modalidad.id)
    db_session.add_all([equipo_local, equipo_visitante])
    await db_session.flush()

    insc_local = InscripcionTorneo(torneo_id=torneo.id, equipo_id=equipo_local.id)
    insc_visitante = InscripcionTorneo(torneo_id=torneo.id, equipo_id=equipo_visitante.id)
    db_session.add_all([insc_local, insc_visitante])
    await db_session.flush()

    partido = Partido(
        torneo_id=torneo.id,
        equipos_id_local=equipo_local.id,
        equipos_id_visitante=equipo_visitante.id,
        fecha_partido=datetime(2026, 7, 5, 10, 0, 0),
        estado="Programado",
    )
    db_session.add(partido)
    await db_session.commit()

    return {
        "torneo_id": torneo.id,
        "disciplina_id": disciplina.id,
        "equipo_local_id": equipo_local.id,
        "equipo_visitante_id": equipo_visitante.id,
        "insc_local_id": insc_local.id,
        "insc_visitante_id": insc_visitante.id,
        "partido_id": partido.id,
    }


async def _agregar_jugador_activo(
    db_session: AsyncSession, disciplina_id: int, inscripcion_torneo_id: int, cedula_sufijo: str, estado: str = "Activo"
) -> int:
    """Crea Jugador + Perfil + JugadorEquipo, devuelve el jugador_perfil_id."""
    jugador = Jugador(
        nombre=f"Jugador {cedula_sufijo}",
        cedula=f"8888{cedula_sufijo}",
        correo_electronico=f"jugador.{cedula_sufijo}@example.com",
    )
    db_session.add(jugador)
    await db_session.flush()
    perfil = JugadorPerfilDisciplina(jugador_id=jugador.id, disciplina_id=disciplina_id)
    db_session.add(perfil)
    await db_session.flush()
    vinculo = JugadorEquipo(
        jugador_perfil_id=perfil.id,
        inscripcion_torneo_id=inscripcion_torneo_id,
        fecha_inicio=date(2026, 1, 1),
        estado=estado,
    )
    db_session.add(vinculo)
    await db_session.commit()
    return perfil.id


async def _convocar(db_session: AsyncSession, partido_id: int, jugador_perfil_id: int, titular: bool) -> None:
    db_session.add(ConvocadoAPartido(partido_id=partido_id, jugador_perfil_id=jugador_perfil_id, titular=titular))
    await db_session.commit()


async def _empezar(client: AsyncClient, partido_id: int, headers: dict[str, str]):
    return await client.post(
        f"/api/v1/partidos/{partido_id}/hitos", json={"tipo_hito": "Inicio_Partido"}, headers=headers
    )


async def test_bloquea_inicio_sin_convocatoria(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    ctx = await _armar_torneo_con_partido(db_session, tamano_equipo=2, nombre="SinConvocatoria")
    resp = await _empezar(client, ctx["partido_id"], admin_general_headers)
    assert resp.status_code == 400, resp.text
    assert "titular" in resp.json()["detail"].lower()


async def test_bloquea_con_titulares_parciales_y_nombra_el_equipo(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    ctx = await _armar_torneo_con_partido(db_session, tamano_equipo=2, nombre="Parcial")
    # Local: 2 titulares completos. Visitante: 1 solo — el mensaje debe
    # nombrar específicamente al equipo que falta, no un genérico.
    for i in range(2):
        perfil_id = await _agregar_jugador_activo(db_session, ctx["disciplina_id"], ctx["insc_local_id"], f"L{i}")
        await _convocar(db_session, ctx["partido_id"], perfil_id, titular=True)
    perfil_visitante = await _agregar_jugador_activo(db_session, ctx["disciplina_id"], ctx["insc_visitante_id"], "V0")
    await _convocar(db_session, ctx["partido_id"], perfil_visitante, titular=True)

    resp = await _empezar(client, ctx["partido_id"], admin_general_headers)
    assert resp.status_code == 400, resp.text
    detalle = resp.json()["detail"]
    assert "Parcial Visitante" in detalle
    assert "Parcial Local" not in detalle
    assert "1 titular" in detalle
    assert "exige 2" in detalle


async def test_permite_inicio_con_titulares_exactos(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    ctx = await _armar_torneo_con_partido(db_session, tamano_equipo=2, nombre="Exacto")
    for lado, insc_id in (("L", ctx["insc_local_id"]), ("V", ctx["insc_visitante_id"])):
        for i in range(2):
            perfil_id = await _agregar_jugador_activo(db_session, ctx["disciplina_id"], insc_id, f"{lado}{i}")
            await _convocar(db_session, ctx["partido_id"], perfil_id, titular=True)

    resp = await _empezar(client, ctx["partido_id"], admin_general_headers)
    assert resp.status_code == 201, resp.text


async def test_modalidad_pareja_exige_exactamente_dos(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    # tamano_equipo=2 (Pareja, P11/EC-CM1): un solo titular por lado no
    # alcanza — mismo cálculo genérico que Conjunto, sin rama especial.
    ctx = await _armar_torneo_con_partido(db_session, tamano_equipo=2, nombre="Pareja")
    for lado, insc_id in (("L", ctx["insc_local_id"]), ("V", ctx["insc_visitante_id"])):
        perfil_id = await _agregar_jugador_activo(db_session, ctx["disciplina_id"], insc_id, f"{lado}0")
        await _convocar(db_session, ctx["partido_id"], perfil_id, titular=True)

    resp = await _empezar(client, ctx["partido_id"], admin_general_headers)
    assert resp.status_code == 400, resp.text
    assert "exige 2" in resp.json()["detail"]


async def test_titular_dado_de_baja_despues_de_convocarlo_no_cuenta(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """Edge case de integridad (Diagrama de pruebas del plan): un
    ConvocadoAPartido.titular=True de un jugador que YA NO está en el
    roster activo (dado de baja después de convocarlo) no debe contar —
    se intersecta contra el roster VIGENTE, no se confía en la
    convocatoria sola."""
    ctx = await _armar_torneo_con_partido(db_session, tamano_equipo=2, nombre="Baja")
    perfil_activo = await _agregar_jugador_activo(db_session, ctx["disciplina_id"], ctx["insc_local_id"], "L0")
    perfil_dado_de_baja = await _agregar_jugador_activo(
        db_session, ctx["disciplina_id"], ctx["insc_local_id"], "L1", estado="Inactivo"
    )
    await _convocar(db_session, ctx["partido_id"], perfil_activo, titular=True)
    await _convocar(db_session, ctx["partido_id"], perfil_dado_de_baja, titular=True)
    for i in range(2):
        perfil_id = await _agregar_jugador_activo(db_session, ctx["disciplina_id"], ctx["insc_visitante_id"], f"V{i}")
        await _convocar(db_session, ctx["partido_id"], perfil_id, titular=True)

    resp = await _empezar(client, ctx["partido_id"], admin_general_headers)
    assert resp.status_code == 400, resp.text
    assert "Baja Local" in resp.json()["detail"]
    assert "1 titular" in resp.json()["detail"]


async def test_partido_sin_los_dos_equipos_definidos_es_rechazado(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """Bracket en curso (equipos_id_local/visitante NULL, motor-formatos-
    plantillas-navegacion-plan.md) — mensaje distinto del de titulares,
    ninguno de los dos lados existe todavía."""
    ctx = await _armar_torneo_con_partido(db_session, tamano_equipo=2, nombre="SinEquipos")
    partido = await db_session.get(Partido, ctx["partido_id"])
    partido.equipos_id_visitante = None
    await db_session.commit()

    resp = await _empezar(client, ctx["partido_id"], admin_general_headers)
    assert resp.status_code == 400, resp.text
    assert "no tiene los dos equipos definidos" in resp.json()["detail"]
