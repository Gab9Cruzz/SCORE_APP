"""Tests a nivel de base de datos para equipos-jugadores-plan.md, Fase 3
(tabla "Diagrama de pruebas"). Estas filas de la tabla piden explícitamente
un INSERT/UPDATE directo contra Postgres, sin pasar por el service layer
(RegistroLoteService, TraspasoService, etc.): el objetivo no es repetir lo
que ya cubren test_registro_lote.py/test_traspasos.py (que prueban que la
APP rechaza estos casos), sino confirmar que la BASE los rechaza por sí
sola — un admin con acceso directo a SQL, o un script de seed futuro, no
puede saltárselos.

05_seed.sql: Carlos Pérez (jugador_id=1) está Activo en Tiburones FC
(inscripcion 1, torneo 1, Fútbol), dorsal 10. Luis Andrade (jugador_id=2)
está Activo en el mismo equipo, dorsal 7, y no tiene ninguna otra membresía.
"""
from datetime import date

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inscripcion_torneo import InscripcionTorneo
from app.models.jugador import Jugador
from app.models.jugador_equipo import JugadorEquipo
from app.models.jugador_perfil_disciplina import JugadorPerfilDisciplina
from app.models.torneo import Torneo
from app.models.torneo_grupo import TorneoGrupo

INSCRIPCION_TIBURONES = 1
INSCRIPCION_AGUILAS = 2


async def _perfil_id_de(db_session: AsyncSession, jugador_id: int) -> int:
    resultado = await db_session.execute(
        select(JugadorPerfilDisciplina.id).where(JugadorPerfilDisciplina.jugador_id == jugador_id)
    )
    return resultado.scalar_one()


async def _estado_perfil(db_session: AsyncSession, perfil_id: int) -> str:
    resultado = await db_session.execute(
        text("SELECT Estado FROM vw_estado_perfil_disciplina WHERE Jugador_Perfil_ID = :pid"),
        {"pid": perfil_id},
    )
    return resultado.scalar_one()


async def test_trigger_exclusividad_rechaza_insert_directo(db_session: AsyncSession):
    """fn_validar_exclusividad_torneo: un INSERT directo a JUGADOR_EQUIPO
    que activa al mismo perfil en dos equipos del MISMO torneo (Tiburones
    y Águilas, ambos torneo 1) debe fallar en la base, sin que
    RegistroLoteService medie."""
    perfil_id = await _perfil_id_de(db_session, jugador_id=1)  # Carlos Pérez, ya Activo en Tiburones

    db_session.add(
        JugadorEquipo(
            jugador_perfil_id=perfil_id,
            inscripcion_torneo_id=INSCRIPCION_AGUILAS,
            dorsal=99,
            fecha_inicio=date(2026, 2, 1),
        )
    )
    with pytest.raises((IntegrityError, DBAPIError)) as exc_info:
        await db_session.flush()
    assert "jugador_ya_activo_en_este_torneo" in str(exc_info.value)
    await db_session.rollback()


async def test_unique_dorsal_por_roster_rechaza_insert_directo(db_session: AsyncSession):
    """uq_dorsal_por_roster_vigente (03_indexes.sql): dos membresías
    vigentes del mismo roster no pueden compartir dorsal, incluso entre dos
    perfiles que no chocan por exclusividad entre sí (el perfil nuevo de
    este test no está activo en ningún otro roster de este torneo — el
    único conflicto en juego es el dorsal)."""
    jugador_nuevo = Jugador(
        nombre="Suplente Sin Equipo", cedula="0977900001", correo_electronico="suplente.db@example.com"
    )
    db_session.add(jugador_nuevo)
    await db_session.flush()

    perfil_nuevo = JugadorPerfilDisciplina(jugador_id=jugador_nuevo.id, disciplina_id=1)  # Fútbol
    db_session.add(perfil_nuevo)
    await db_session.flush()

    db_session.add(
        JugadorEquipo(
            jugador_perfil_id=perfil_nuevo.id,
            inscripcion_torneo_id=INSCRIPCION_TIBURONES,
            dorsal=10,  # Carlos Pérez ya lo tiene vigente en este mismo roster
            fecha_inicio=date(2026, 2, 1),
        )
    )
    with pytest.raises((IntegrityError, DBAPIError)) as exc_info:
        await db_session.flush()
    assert "uq_dorsal_por_roster_vigente" in str(exc_info.value)
    await db_session.rollback()


async def test_ec10_agencia_libre_no_afecta_membresia_activa_en_otro_torneo(db_session: AsyncSession):
    """EC-10, el caso crítico del plan: finalizar un torneo no debe dejar
    'Libre' a un perfil que sigue Activo en OTRO torneo de la misma
    disciplina. Se dispara el trigger crudo (UPDATE TORNEO ...
    Estado='Finalizado') en vez de pasar por un endpoint porque hoy no hay
    ninguno que exponga ese cambio de estado — el contrato es de la base."""
    perfil_id = await _perfil_id_de(db_session, jugador_id=1)  # Carlos Pérez, Activo en Tiburones/torneo 1

    grupo_2 = TorneoGrupo(nombre="Copa Paralela")
    db_session.add(grupo_2)
    await db_session.flush()

    torneo_2 = Torneo(
        nombre="Copa Paralela 2026",
        disciplina_id=1,
        torneo_grupo_id=grupo_2.id,
        fecha_inicio=date(2026, 2, 1),
        fecha_fin=date(2026, 4, 1),
    )
    db_session.add(torneo_2)
    await db_session.flush()

    inscripcion_2 = InscripcionTorneo(torneo_id=torneo_2.id, equipo_id=1)  # Tiburones también inscrito acá
    db_session.add(inscripcion_2)
    await db_session.flush()

    membresia_paralela = JugadorEquipo(
        jugador_perfil_id=perfil_id,
        inscripcion_torneo_id=inscripcion_2.id,
        dorsal=None,
        fecha_inicio=date(2026, 2, 1),
    )
    db_session.add(membresia_paralela)
    await db_session.flush()

    torneo_1 = await db_session.get(Torneo, 1)
    torneo_1.estado = "Finalizado"
    await db_session.flush()

    membresia_original = await db_session.get(JugadorEquipo, 1)  # seed: Carlos en Tiburones/torneo 1
    await db_session.refresh(membresia_original)
    assert membresia_original.estado == "Inactivo"
    assert membresia_original.fecha_fin == date.today()

    await db_session.refresh(membresia_paralela)
    assert membresia_paralela.estado == "Activo"

    assert await _estado_perfil(db_session, perfil_id) == "Activo"

    await db_session.rollback()


async def test_ec10_agencia_libre_deja_libre_si_no_hay_otro_torneo_activo(db_session: AsyncSession):
    """Contraparte de EC-10: sin ninguna membresía paralela, finalizar el
    único torneo donde el perfil estaba activo sí debe dejarlo Libre."""
    perfil_id = await _perfil_id_de(db_session, jugador_id=2)  # Luis Andrade, solo activo en torneo 1

    torneo_1 = await db_session.get(Torneo, 1)
    torneo_1.estado = "Finalizado"
    await db_session.flush()

    assert await _estado_perfil(db_session, perfil_id) == "Libre"

    await db_session.rollback()
