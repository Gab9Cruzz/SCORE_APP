"""Tests a nivel de base de datos para el motor de formatos (T37-T39,
T48-T49 del Diagrama de pruebas, motor-formatos-plantillas-navegacion-
plan.md) — mismo criterio que test_db_triggers_equipos_jugadores.py:
INSERT/UPDATE directo contra Postgres (vía el ORM, sin pasar por
MotorFormatosService salvo para armar el bracket en sí, que es la unidad
que se está probando), para confirmar que la BASE propaga/rechaza por sí
sola.

Cada test termina en `rollback()` sin seguir usando la sesión después de
un `flush()` que se espera que falle — mismo criterio que el resto de este
archivo hermano: seguir consultando la conexión después de una excepción
de Postgres dentro de la MISMA sesión no es un patrón que este harness
(psycopg async + savepoints anidados) sostenga con confiabilidad, así que
"falla sin desempate" y "cierra con desempate" son tests separados en vez
de un solo test que reintenta.
"""
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.equipo import Equipo
from app.models.evento import Evento
from app.models.evento_partido import EventoPartido
from app.models.fase import Fase
from app.models.grupo import Grupo
from app.models.grupo_equipo import GrupoEquipo
from app.models.inscripcion_torneo import InscripcionTorneo
from app.models.jugador import Jugador
from app.models.jugador_equipo import JugadorEquipo
from app.models.jugador_perfil_disciplina import JugadorPerfilDisciplina
from app.models.partido import Partido
from app.models.torneo import Torneo
from app.models.torneo_grupo import TorneoGrupo
from app.models.usuario import Usuario
from app.services.motor_formatos import MotorFormatosService

DISCIPLINA_FUTBOL = 1
MODALIDAD_FUTBOL_11 = 1


async def _crear_usuario_admin(db_session: AsyncSession, username: str) -> Usuario:
    usuario = Usuario(username=username, nombre=username, password_hash=hash_password("x"), rol="TorneoAdmin")
    db_session.add(usuario)
    await db_session.flush()
    return usuario


async def _crear_torneo_con_equipos(
    db_session: AsyncSession, nombre: str, n_equipos: int, formato: str = "Eliminacion", **extra
) -> tuple[Torneo, list[int]]:
    grupo = TorneoGrupo(nombre=nombre)
    db_session.add(grupo)
    await db_session.flush()
    torneo = Torneo(
        nombre=nombre,
        disciplina_id=DISCIPLINA_FUTBOL,
        modalidad_id=MODALIDAD_FUTBOL_11,
        torneo_grupo_id=grupo.id,
        numero_edicion=1,
        fecha_inicio=date(2026, 4, 1),
        fecha_fin=date(2026, 6, 30),
        formato=formato,
        **extra,
    )
    db_session.add(torneo)
    await db_session.flush()

    equipo_ids = []
    for i in range(n_equipos):
        equipo = Equipo(nombre=f"{nombre} Equipo {i + 1}", disciplina_id=DISCIPLINA_FUTBOL, modalidad_id=MODALIDAD_FUTBOL_11)
        db_session.add(equipo)
        await db_session.flush()
        db_session.add(InscripcionTorneo(torneo_id=torneo.id, equipo_id=equipo.id, estado="Inscrito"))
        equipo_ids.append(equipo.id)
    await db_session.flush()
    return torneo, equipo_ids


async def _registrar_jugador_en_equipo(db_session: AsyncSession, torneo_id: int, equipo_id: int, nombre: str, cedula: str) -> int:
    jugador = Jugador(nombre=nombre, cedula=cedula, correo_electronico=f"{cedula}@test.com")
    db_session.add(jugador)
    await db_session.flush()
    perfil = JugadorPerfilDisciplina(jugador_id=jugador.id, disciplina_id=DISCIPLINA_FUTBOL)
    db_session.add(perfil)
    await db_session.flush()
    inscripcion = (
        await db_session.execute(
            select(InscripcionTorneo).where(
                InscripcionTorneo.torneo_id == torneo_id, InscripcionTorneo.equipo_id == equipo_id
            )
        )
    ).scalar_one()
    db_session.add(
        JugadorEquipo(
            jugador_perfil_id=perfil.id,
            inscripcion_torneo_id=inscripcion.id,
            fecha_inicio=date(2026, 1, 1),
            estado="Activo",
        )
    )
    await db_session.flush()
    return jugador.id


async def _registrar_goles(db_session: AsyncSession, partido_id: int, jugador_id: int, equipo_id: int, cantidad: int) -> None:
    evento_gol_id = (await db_session.execute(select(Evento.id).where(Evento.nombre == "Gol"))).scalar_one()
    for minuto in range(cantidad):
        db_session.add(
            EventoPartido(
                partidos_id=partido_id, jugador_id=jugador_id, equipo_id=equipo_id, eventos_id=evento_gol_id, minuto=minuto + 1
            )
        )
    await db_session.flush()


async def _armar_bracket_4_con_jugadores(db_session: AsyncSession, nombre: str) -> tuple[Torneo, Fase, list[Partido], dict[int, int]]:
    """Bracket de 4 equipos, sin byes: 2 semifinales reales, ambas
    encadenadas a la Final (ganador) y al Tercer Lugar (perdedor)."""
    torneo, equipos = await _crear_torneo_con_equipos(db_session, nombre, 4)
    fase = Fase(torneo_id=torneo.id, nombre="Eliminatoria", tipo="Eliminacion", orden=1, estado="Pendiente")
    db_session.add(fase)
    await db_session.flush()
    usuario = await _crear_usuario_admin(db_session, f"{nombre.lower().replace(' ', '_')}_admin")
    await db_session.commit()

    await MotorFormatosService(db_session).sortear(torneo.id, usuario.id, semilla="fija")

    semifinales = (
        (await db_session.execute(select(Partido).where(Partido.fase_id == fase.id, Partido.ronda_nombre == "Semifinal")))
        .scalars()
        .all()
    )
    jugadores_por_equipo: dict[int, int] = {}
    for equipo_id in equipos:
        jugadores_por_equipo[equipo_id] = await _registrar_jugador_en_equipo(
            db_session, torneo.id, equipo_id, f"Jugador {equipo_id}", f"CED{equipo_id}"
        )
    await db_session.commit()
    return torneo, fase, list(semifinales), jugadores_por_equipo


async def test_trigger_propaga_ganador_y_perdedor_a_final_y_tercer_lugar(db_session: AsyncSession):
    """T37 (propagación) + T48 (perdedores de semifinal al Tercer Lugar) —
    "el corazón del motor" (prioridad explícita del plan)."""
    torneo, fase, semifinales, jugadores_por_equipo = await _armar_bracket_4_con_jugadores(
        db_session, "Trigger Bracket 4"
    )

    ganadores = []
    perdedores = []
    for semi in semifinales:
        local_id, visitante_id = semi.equipos_id_local, semi.equipos_id_visitante
        # Local gana 2-0 — sin ambigüedad de empate acá (eso es T38/T49).
        await _registrar_goles(db_session, semi.id, jugadores_por_equipo[local_id], local_id, 2)
        semi.estado = "Finalizado"
        await db_session.commit()
        ganadores.append(local_id)
        perdedores.append(visitante_id)

    final = (
        await db_session.execute(select(Partido).where(Partido.fase_id == fase.id, Partido.ronda_nombre == "Final"))
    ).scalar_one()
    assert {final.equipos_id_local, final.equipos_id_visitante} == set(ganadores)

    tercer_lugar = (
        await db_session.execute(select(Partido).where(Partido.fase_id == fase.id, Partido.ronda_nombre == "Tercer Lugar"))
    ).scalar_one()
    assert {tercer_lugar.equipos_id_local, tercer_lugar.equipos_id_visitante} == set(perdedores)

    await db_session.rollback()


async def test_trigger_rechaza_tercer_lugar_empatado_sin_desempate(db_session: AsyncSession):
    """T49 — el Tercer Lugar exige desempate si termina empatado, mismo
    criterio que la Final (EC-59), aunque sea un partido terminal (sin
    Partido_Siguiente_ID) — separado en su propio test porque, una vez
    cerradas las 2 semifinales, éste es el único caso borde que le falta a
    T37/T48 sin reutilizar una sesión que ya vio una excepción."""
    torneo, fase, semifinales, jugadores_por_equipo = await _armar_bracket_4_con_jugadores(
        db_session, "Trigger Tercer Lugar Empate"
    )
    for semi in semifinales:
        local_id = semi.equipos_id_local
        await _registrar_goles(db_session, semi.id, jugadores_por_equipo[local_id], local_id, 2)
        semi.estado = "Finalizado"
    await db_session.commit()

    tercer_lugar = (
        await db_session.execute(select(Partido).where(Partido.fase_id == fase.id, Partido.ronda_nombre == "Tercer Lugar"))
    ).scalar_one()
    await _registrar_goles(
        db_session, tercer_lugar.id, jugadores_por_equipo[tercer_lugar.equipos_id_local], tercer_lugar.equipos_id_local, 1
    )
    await _registrar_goles(
        db_session, tercer_lugar.id, jugadores_por_equipo[tercer_lugar.equipos_id_visitante], tercer_lugar.equipos_id_visitante, 1
    )
    tercer_lugar.estado = "Finalizado"
    with pytest.raises((IntegrityError, DBAPIError)) as exc_info:
        await db_session.flush()
    assert "empatado_sin_desempate" in str(exc_info.value)
    await db_session.rollback()


async def test_trigger_rechaza_final_empatada_sin_desempate(db_session: AsyncSession):
    """T38 — un partido de Eliminación no puede quedar 'Finalizado'
    empatado sin Ganador_Desempate_ID (EC-48). Bracket de 2 equipos: la
    Final es el único partido, ambos equipos ya definidos desde el sorteo."""
    torneo, equipos = await _crear_torneo_con_equipos(db_session, "Trigger Empate Final", 2)
    fase = Fase(torneo_id=torneo.id, nombre="Eliminatoria", tipo="Eliminacion", orden=1, estado="Pendiente")
    db_session.add(fase)
    await db_session.flush()
    usuario = await _crear_usuario_admin(db_session, "motor_test_admin2")
    await db_session.commit()

    await MotorFormatosService(db_session).sortear(torneo.id, usuario.id, semilla="fija")
    final = (
        await db_session.execute(select(Partido).where(Partido.fase_id == fase.id, Partido.ronda_nombre == "Final"))
    ).scalar_one()

    j1 = await _registrar_jugador_en_equipo(db_session, torneo.id, final.equipos_id_local, "J1", "CEDF1")
    j2 = await _registrar_jugador_en_equipo(db_session, torneo.id, final.equipos_id_visitante, "J2", "CEDF2")
    await db_session.commit()

    await _registrar_goles(db_session, final.id, j1, final.equipos_id_local, 1)
    await _registrar_goles(db_session, final.id, j2, final.equipos_id_visitante, 1)
    final.estado = "Finalizado"
    with pytest.raises((IntegrityError, DBAPIError)) as exc_info:
        await db_session.flush()
    assert "empatado_sin_desempate" in str(exc_info.value)
    await db_session.rollback()


async def test_trigger_acepta_final_empatada_con_desempate_registrado(db_session: AsyncSession):
    """Contraparte de T38: con Ganador_Desempate_ID en el MISMO UPDATE que
    cierra el partido, el trigger no tiene nada que objetar."""
    torneo, equipos = await _crear_torneo_con_equipos(db_session, "Trigger Empate Final OK", 2)
    fase = Fase(torneo_id=torneo.id, nombre="Eliminatoria", tipo="Eliminacion", orden=1, estado="Pendiente")
    db_session.add(fase)
    await db_session.flush()
    usuario = await _crear_usuario_admin(db_session, "motor_test_admin3")
    await db_session.commit()

    await MotorFormatosService(db_session).sortear(torneo.id, usuario.id, semilla="fija")
    final = (
        await db_session.execute(select(Partido).where(Partido.fase_id == fase.id, Partido.ronda_nombre == "Final"))
    ).scalar_one()

    j1 = await _registrar_jugador_en_equipo(db_session, torneo.id, final.equipos_id_local, "J1", "CEDF1OK")
    j2 = await _registrar_jugador_en_equipo(db_session, torneo.id, final.equipos_id_visitante, "J2", "CEDF2OK")
    await db_session.commit()

    await _registrar_goles(db_session, final.id, j1, final.equipos_id_local, 1)
    await _registrar_goles(db_session, final.id, j2, final.equipos_id_visitante, 1)
    final.estado = "Finalizado"
    final.ganador_desempate_id = final.equipos_id_local
    await db_session.commit()  # no debe lanzar
    assert final.estado == "Finalizado"

    await db_session.rollback()


async def test_trigger_rechaza_equipo_en_dos_grupos_de_la_misma_fase(db_session: AsyncSession):
    """T39 — fn_validar_equipo_un_grupo_por_fase."""
    torneo, equipos = await _crear_torneo_con_equipos(db_session, "Trigger Grupos", 2, formato="Grupos_Playoffs")
    fase = Fase(torneo_id=torneo.id, nombre="Fase de Grupos", tipo="Grupos", orden=1, estado="Pendiente")
    db_session.add(fase)
    await db_session.flush()
    grupo_a = Grupo(fase_id=fase.id, nombre="A")
    grupo_b = Grupo(fase_id=fase.id, nombre="B")
    db_session.add_all([grupo_a, grupo_b])
    await db_session.flush()
    inscripcion = (
        await db_session.execute(
            select(InscripcionTorneo).where(
                InscripcionTorneo.torneo_id == torneo.id, InscripcionTorneo.equipo_id == equipos[0]
            )
        )
    ).scalar_one()
    db_session.add(GrupoEquipo(grupo_id=grupo_a.id, inscripcion_torneo_id=inscripcion.id))
    await db_session.commit()

    db_session.add(GrupoEquipo(grupo_id=grupo_b.id, inscripcion_torneo_id=inscripcion.id))
    with pytest.raises((IntegrityError, DBAPIError)) as exc_info:
        await db_session.flush()
    assert "ya_asignado_a_otro_grupo" in str(exc_info.value)
    await db_session.rollback()
