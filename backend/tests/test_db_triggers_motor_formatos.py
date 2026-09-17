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


# ------------------------------------------------------------
# Cierre de Fase Regular + Llaves + Playoffs
# (docs/plans/cierre-fase-regular-llaves-playoffs-plan.md, Fase B)
# ------------------------------------------------------------


async def _armar_llave_2_equipos(
    db_session: AsyncSession, nombre: str, formato_eliminatoria: str = "Ida_Vuelta"
) -> tuple[Torneo, Partido, Partido, dict[int, int]]:
    """Bracket de 2 equipos bajo un `formato_eliminatoria` a dos piernas:
    la Final ES la única llave, `_sortear_bracket` la arma directo (EC-58,
    tamano < 4, sin shells)."""
    torneo, equipos = await _crear_torneo_con_equipos(
        db_session, nombre, 2, formato="Eliminacion", formato_eliminatoria=formato_eliminatoria
    )
    fase = Fase(torneo_id=torneo.id, nombre="Eliminatoria", tipo="Eliminacion", orden=1, estado="Pendiente")
    db_session.add(fase)
    await db_session.flush()
    usuario = await _crear_usuario_admin(db_session, f"{nombre.lower().replace(' ', '_')}_admin")
    await db_session.commit()

    await MotorFormatosService(db_session).sortear(torneo.id, usuario.id, semilla="fija")

    partidos = (
        (await db_session.execute(select(Partido).where(Partido.fase_id == fase.id, Partido.ronda_nombre == "Final")))
        .scalars()
        .all()
    )
    vuelta = next(p for p in partidos if p.partido_ida_id is not None)
    ida = next(p for p in partidos if p.id == vuelta.partido_ida_id)

    jugadores_por_equipo: dict[int, int] = {}
    for equipo_id in equipos:
        jugadores_por_equipo[equipo_id] = await _registrar_jugador_en_equipo(
            db_session, torneo.id, equipo_id, f"Jugador {equipo_id}", f"CL{equipo_id}"
        )
    await db_session.commit()
    return torneo, ida, vuelta, jugadores_por_equipo


async def test_trigger_ida_0_0_es_legal(db_session: AsyncSession):
    """B4: un 0-0 en la IDA nunca exige desempate — la validación de
    empate se corre recién sobre el GLOBAL, al finalizar la VUELTA."""
    torneo, ida, vuelta, jugadores = await _armar_llave_2_equipos(db_session, "Llave Ida 0-0")
    ida.estado = "Finalizado"
    await db_session.commit()  # no debe lanzar
    assert ida.estado == "Finalizado"
    await db_session.rollback()


async def test_trigger_vuelta_exige_desempate_si_agregado_empatado(db_session: AsyncSession):
    """B4: ida 1-0, vuelta 0-1 -> global 1-1, sin Ganador_Desempate_ID en
    la vuelta -> rechazado, aunque NINGUNO de los dos partidos por
    separado esté empatado."""
    torneo, ida, vuelta, jugadores = await _armar_llave_2_equipos(db_session, "Llave Global Empate")
    local_ida = ida.equipos_id_local
    visit_ida = ida.equipos_id_visitante
    await _registrar_goles(db_session, ida.id, jugadores[local_ida], local_ida, 1)
    ida.estado = "Finalizado"
    await db_session.commit()

    # La vuelta invierte localía: visit_ida juega de LOCAL acá. Si gana la
    # vuelta 1-0, el agregado queda 1-1 (cada equipo ganó su partido de
    # local) — el caso clásico que ninguno de los 2 marcadores individuales
    # deja ver por separado.
    await _registrar_goles(db_session, vuelta.id, jugadores[visit_ida], visit_ida, 1)
    vuelta.estado = "Finalizado"
    with pytest.raises((IntegrityError, DBAPIError)) as exc_info:
        await db_session.flush()
    assert "llave_empatada_en_global_sin_desempate" in str(exc_info.value)
    await db_session.rollback()


async def test_trigger_vuelta_acepta_agregado_empatado_con_desempate(db_session: AsyncSession):
    """Contraparte: mismo 1-1 global, pero con Ganador_Desempate_ID en la
    vuelta -> acepta, y el campeón resuelto es el desempatado (no hay
    'próxima ronda' acá — bracket de 2, la Final es el único partido)."""
    torneo, ida, vuelta, jugadores = await _armar_llave_2_equipos(db_session, "Llave Global Empate OK")
    local_ida = ida.equipos_id_local
    visit_ida = ida.equipos_id_visitante
    await _registrar_goles(db_session, ida.id, jugadores[local_ida], local_ida, 1)
    ida.estado = "Finalizado"
    await db_session.commit()

    await _registrar_goles(db_session, vuelta.id, jugadores[visit_ida], visit_ida, 1)
    vuelta.estado = "Finalizado"
    vuelta.ganador_desempate_id = visit_ida
    await db_session.commit()  # no debe lanzar
    await db_session.rollback()


async def test_trigger_rechaza_vuelta_si_ida_no_resuelta(db_session: AsyncSession):
    """F12: la VUELTA no puede finalizar mientras su IDA sigue
    Programado/En curso — dos operadores de mesa cerrando fuera de orden
    no deben poder hacer que fn_resolver_llave agregue contra una ida
    todavía abierta."""
    torneo, ida, vuelta, jugadores = await _armar_llave_2_equipos(db_session, "Llave Fuera De Orden")
    local_vta = vuelta.equipos_id_local
    await _registrar_goles(db_session, vuelta.id, jugadores[local_vta], local_vta, 1)
    vuelta.estado = "Finalizado"
    with pytest.raises((IntegrityError, DBAPIError)) as exc_info:
        await db_session.flush()
    assert "partido_vuelta_ida_sin_resolver" in str(exc_info.value)
    await db_session.rollback()


async def test_trigger_vuelta_acepta_ida_cancelada(db_session: AsyncSession):
    """F12 + Cancelado addendum: una IDA Cancelada (nunca Finalizado)
    igual habilita la vuelta — "Finalizado o Cancelado" resuelve, nunca
    bloquea para siempre."""
    torneo, ida, vuelta, jugadores = await _armar_llave_2_equipos(db_session, "Llave Ida Cancelada")
    ida.estado = "Cancelado"
    await db_session.commit()

    local_vta = vuelta.equipos_id_local
    await _registrar_goles(db_session, vuelta.id, jugadores[local_vta], local_vta, 1)
    vuelta.estado = "Finalizado"
    await db_session.commit()  # no debe lanzar — la ida cancelada aporta 0-0.
    await db_session.rollback()


async def test_trigger_propaga_agregado_y_completa_ambas_piernas_del_padre(db_session: AsyncSession):
    """B3/C1, el corazón del motor de llaves: en un bracket de 4 equipos a
    Ida_Vuelta, cuando una semifinal (llave a dos partidos) termina, el
    ganador del AGREGADO llega a la Final — y a las DOS piernas de la
    Final, en el slot invertido correspondiente, con un solo feeder
    (fn_propagar_ganador_bracket "espeja" a la ida del destino)."""
    torneo, equipos = await _crear_torneo_con_equipos(
        db_session, "Llave 4 Ida Vuelta", 4, formato="Eliminacion", formato_eliminatoria="Ida_Vuelta"
    )
    fase = Fase(torneo_id=torneo.id, nombre="Eliminatoria", tipo="Eliminacion", orden=1, estado="Pendiente")
    db_session.add(fase)
    await db_session.flush()
    usuario = await _crear_usuario_admin(db_session, "llave4_admin")
    await db_session.commit()

    await MotorFormatosService(db_session).sortear(torneo.id, usuario.id, semilla="fija")

    semis_vuelta = (
        (
            await db_session.execute(
                select(Partido).where(
                    Partido.fase_id == fase.id,
                    Partido.ronda_nombre == "Semifinal",
                    Partido.partido_ida_id.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(semis_vuelta) == 2  # las 2 semifinales son llaves a dos partidos.

    jugadores_por_equipo: dict[int, int] = {}
    for equipo_id in equipos:
        jugadores_por_equipo[equipo_id] = await _registrar_jugador_en_equipo(
            db_session, torneo.id, equipo_id, f"J{equipo_id}", f"CEDIV{equipo_id}"
        )
    await db_session.commit()

    ganadores = []
    for vuelta in semis_vuelta:
        ida = await db_session.get(Partido, vuelta.partido_ida_id)
        local_ida = ida.equipos_id_local
        # Gana el local de la ida en las dos piernas: 1-0 y (vuelta,
        # invertido) 0-1 a su favor -> agregado 2-0, sin ambigüedad.
        await _registrar_goles(db_session, ida.id, jugadores_por_equipo[local_ida], local_ida, 1)
        ida.estado = "Finalizado"
        await db_session.commit()

        await _registrar_goles(db_session, vuelta.id, jugadores_por_equipo[local_ida], local_ida, 1)
        vuelta.estado = "Finalizado"
        await db_session.commit()
        ganadores.append(local_ida)

    final_partidos = (
        (await db_session.execute(select(Partido).where(Partido.fase_id == fase.id, Partido.ronda_nombre == "Final")))
        .scalars()
        .all()
    )
    assert len(final_partidos) == 2  # la Final también es una llave a dos partidos.
    final_vuelta = next(p for p in final_partidos if p.partido_ida_id is not None)
    final_ida = next(p for p in final_partidos if p.id == final_vuelta.partido_ida_id)

    # Los dos ganadores de semifinal están sentados en AMBAS piernas de la
    # Final, con localía invertida entre ida y vuelta.
    assert {final_vuelta.equipos_id_local, final_vuelta.equipos_id_visitante} == set(ganadores)
    assert {final_ida.equipos_id_local, final_ida.equipos_id_visitante} == set(ganadores)
    assert final_ida.equipos_id_local == final_vuelta.equipos_id_visitante
    assert final_ida.equipos_id_visitante == final_vuelta.equipos_id_local

    await db_session.rollback()


async def test_trigger_walkover_en_una_pierna_suma_al_agregado(db_session: AsyncSession):
    """Accepted addendum: una pierna por walkover suma 3-0 al agregado
    como cualquier otro resultado — fn_marcador_partido unifica Walkover/
    Corrido/goles, fn_resolver_llave no necesita saber cuál fue cuál."""
    torneo, ida, vuelta, jugadores = await _armar_llave_2_equipos(db_session, "Llave Walkover Pierna")
    ausente = ida.equipos_id_visitante
    ida.estado = "Finalizado"
    ida.es_walkover = True
    ida.walkover_equipo_ausente_id = ausente
    await db_session.commit()

    # Vuelta: el mismo ausente de la ida marca 1 (invertido: es local acá).
    await _registrar_goles(db_session, vuelta.id, jugadores[ausente], ausente, 1)
    vuelta.estado = "Finalizado"
    await db_session.commit()  # agregado: 3 (presente) - 1 (ausente) = presente gana, sin empate.
    await db_session.rollback()


async def test_trigger_bloquea_update_partido_en_torneo_cerrado(db_session: AsyncSession):
    """Finding 4 / T3: una vez Torneo.Estado='Finalizado', ningún resultado
    se puede seguir modificando."""
    torneo, equipos = await _crear_torneo_con_equipos(db_session, "Torneo Cerrado Update", 2, formato="Liga")
    fase = Fase(torneo_id=torneo.id, nombre="Liga Regular", tipo="Liga", orden=1, estado="Finalizada")
    db_session.add(fase)
    partido = Partido(
        torneo_id=torneo.id,
        equipos_id_local=equipos[0],
        equipos_id_visitante=equipos[1],
        fecha_partido="2026-04-01",
        fase_id=None,
        estado="Programado",
    )
    db_session.add(partido)
    await db_session.flush()
    torneo.estado = "Finalizado"
    await db_session.commit()

    partido.jornada = 1
    with pytest.raises((IntegrityError, DBAPIError)) as exc_info:
        await db_session.flush()
    assert "torneo_cerrado_resultados_bloqueados" in str(exc_info.value)
    await db_session.rollback()


async def test_trigger_bloquea_evento_partido_en_torneo_cerrado(db_session: AsyncSession):
    torneo, equipos = await _crear_torneo_con_equipos(db_session, "Torneo Cerrado Evento", 2, formato="Liga")
    partido = Partido(
        torneo_id=torneo.id,
        equipos_id_local=equipos[0],
        equipos_id_visitante=equipos[1],
        fecha_partido="2026-04-01",
        estado="Programado",
    )
    db_session.add(partido)
    await db_session.flush()
    jugador_id = await _registrar_jugador_en_equipo(db_session, torneo.id, equipos[0], "JC", "CEDCERRADO1")
    await db_session.commit()

    torneo.estado = "Finalizado"
    await db_session.commit()

    evento_gol_id = (await db_session.execute(select(Evento.id).where(Evento.nombre == "Gol"))).scalar_one()
    db_session.add(
        EventoPartido(partidos_id=partido.id, jugador_id=jugador_id, equipo_id=equipos[0], eventos_id=evento_gol_id, minuto=5)
    )
    with pytest.raises((IntegrityError, DBAPIError)) as exc_info:
        await db_session.flush()
    assert "torneo_cerrado_resultados_bloqueados" in str(exc_info.value)
    await db_session.rollback()
    await db_session.rollback()
