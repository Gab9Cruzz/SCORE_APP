"""TASK-024 (BE-03, BE-09, DB-05): carreras de inicio de partido y de sorteo,
y bloqueos consultivos con espacio de claves propio.

Las de concurrencia real usan `sesiones_paralelas` (dos conexiones de
verdad) y llaman a los servicios directo, como test_concurrencia_convocados.
"""
import asyncio
import pathlib
import re

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.equipo import Equipo
from app.models.fase import Fase
from app.models.inscripcion_torneo import InscripcionTorneo
from app.models.partido import Partido
from app.models.torneo import Torneo
from app.models.usuario import Usuario
from app.schemas.hito_partido import HitoPartidoCreate
from app.services.hito_partido import HitoPartidoService
from app.services.motor_formatos import MotorFormatosService
from tests.test_concurrencia_convocados import _crear_arbitro_asignado
from tests.test_titulares_inicio_partido import (
    _agregar_jugador_activo,
    _armar_torneo_con_partido,
    _convocar,
)

APP = pathlib.Path(__file__).resolve().parents[1] / "app"


def test_ningun_bloqueo_consultivo_usa_una_sola_clave():
    """Todos pasan por app/core/bloqueos.py, con la forma (espacio, id)."""
    usos = []
    for archivo in APP.rglob("*.py"):
        for linea in archivo.read_text(encoding="utf-8").splitlines():
            if "pg_advisory" in linea and not linea.strip().startswith("#"):
                usos.append((archivo.relative_to(APP).as_posix(), linea.strip()))
    llamadas = [u for u in usos if re.search(r"SELECT\s+pg_advisory", u[1])]
    assert llamadas == [("core/bloqueos.py", 'text("SELECT pg_advisory_xact_lock(:espacio, :id)"), {"espacio": int(espacio), "id": id_}')]


async def test_existe_el_indice_unico_de_inicio_partido(db_session: AsyncSession):
    indice = (
        await db_session.execute(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = 'uq_hitos_partido_inicio_unico'")
        )
    ).scalar_one_or_none()
    assert indice is not None and "UNIQUE" in indice and "Inicio_Partido" in indice


async def _como_request(sesion, coro):
    """Como get_db: si el caso de uso falla, rollback (libera los bloqueos)."""
    try:
        return await coro
    except Exception as exc:  # noqa: BLE001 - se clasifica en la prueba
        await sesion.rollback()
        return exc


async def _resultado(coro):
    try:
        return await coro
    except Exception as exc:  # noqa: BLE001 - se clasifica en la prueba
        return exc


@pytest.mark.concurrencia
async def test_dos_inicio_partido_simultaneos_registran_uno_solo(sesiones_paralelas):
    """PR-051."""
    sesion_a, sesion_b = sesiones_paralelas
    ctx = await _armar_torneo_con_partido(sesion_a, tamano_equipo=1, nombre="PR051")
    local = await _agregar_jugador_activo(sesion_a, ctx["disciplina_id"], ctx["insc_local_id"], "PR051L")
    visitante = await _agregar_jugador_activo(sesion_a, ctx["disciplina_id"], ctx["insc_visitante_id"], "PR051V")
    await _convocar(sesion_a, ctx["partido_id"], local, titular=True)
    await _convocar(sesion_a, ctx["partido_id"], visitante, titular=True)
    usuario_a = await _crear_arbitro_asignado(sesion_a, ctx["partido_id"], "pr051")
    await sesion_a.commit()
    usuario_b = await sesion_b.get(type(usuario_a), usuario_a.id)
    data = HitoPartidoCreate(tipo_hito="Inicio_Partido")

    async with asyncio.timeout(15):
        a, b = await asyncio.gather(
            _como_request(sesion_a, HitoPartidoService(sesion_a).registrar(ctx["partido_id"], data, usuario_a)),
            _como_request(sesion_b, HitoPartidoService(sesion_b).registrar(ctx["partido_id"], data, usuario_b)),
        )
    exitosos = [r for r in (a, b) if not isinstance(r, Exception)]
    assert len(exitosos) == 1, (a, b)
    for sesion in (sesion_a, sesion_b):
        try:
            await sesion.rollback()
        except Exception:  # noqa: BLE001
            pass
    inicios = (
        await sesion_a.execute(
            text("SELECT COUNT(*) FROM HITOS_PARTIDO WHERE Partido_ID = :p AND Tipo_Hito = 'Inicio_Partido'"),
            {"p": ctx["partido_id"]},
        )
    ).scalar_one()
    assert inicios == 1


@pytest.mark.concurrencia
async def test_dos_sorteos_simultaneos_dejan_una_sola_llave(sesiones_paralelas):
    """PR-053: el torneo del helper (2 equipos) pasa a Eliminación y se
    sortea dos veces a la vez. Sin serializar, cada uno veía la fase vacía y
    se creaban dos finales."""
    sesion_a, sesion_b = sesiones_paralelas
    ctx = await _armar_torneo_con_partido(sesion_a, tamano_equipo=1, nombre="PR053")
    await sesion_a.execute(text("DELETE FROM PARTIDOS WHERE Torneo_ID = :t"), {"t": ctx["torneo_id"]})
    sesion_a.add(Fase(torneo_id=ctx["torneo_id"], nombre="Llave", tipo="Eliminacion", orden=1, estado="En_Curso"))
    # Cuatro equipos: con dos, el índice único de PARTIDOS ya rechazaba el
    # segundo cuadro (idéntico). Con cuatro, cada sorteo empareja al azar
    # distinto y solo la serialización evita dos cuadros.
    modalidad_id = (await sesion_a.get(Torneo, ctx["torneo_id"])).modalidad_id
    for i in range(2):
        equipo = Equipo(nombre=f"PR053 extra {i}", disciplina_id=ctx["disciplina_id"], modalidad_id=modalidad_id)
        sesion_a.add(equipo)
        await sesion_a.flush()
        sesion_a.add(InscripcionTorneo(torneo_id=ctx["torneo_id"], equipo_id=equipo.id))
    torneo = await sesion_a.get(Torneo, ctx["torneo_id"])
    torneo.formato = "Eliminacion"
    usuario = Usuario(username="admin_pr053", nombre="Admin", password_hash="x" * 60, rol="AdminGeneral")
    sesion_a.add(usuario)
    await sesion_a.flush()
    usuario_id = usuario.id
    await sesion_a.commit()

    async with asyncio.timeout(15):
        a, b = await asyncio.gather(
            _como_request(sesion_a, MotorFormatosService(sesion_a).sortear(ctx["torneo_id"], usuario_id)),
            _como_request(sesion_b, MotorFormatosService(sesion_b).sortear(ctx["torneo_id"], usuario_id)),
        )
    for sesion in (sesion_a, sesion_b):
        try:
            await sesion.rollback()
        except Exception:  # noqa: BLE001
            pass
    finales = (
        await sesion_a.execute(
            select(func.count()).select_from(Partido).where(
                Partido.torneo_id == ctx["torneo_id"], Partido.ronda_nombre == "Final"
            )
        )
    ).scalar_one()
    assert finales == 1, (a, b)
