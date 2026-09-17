"""Cierre de Fase Regular + Llaves + Playoffs
(docs/plans/cierre-fase-regular-llaves-playoffs-plan.md, Fase F) —
generación de bracket en los 3 formatos de eliminatoria, byes por seed,
Tercer Lugar siempre único, y rehacer sorteo con llaves.

Los triggers puros (fn_marcador_partido, fn_resolver_llave, guards) viven
en test_db_triggers_motor_formatos.py — acá se prueba el ALGORITMO de
generación (Python), sin necesidad de jugar los partidos."""
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.equipo import Equipo
from app.models.fase import Fase
from app.models.inscripcion_torneo import InscripcionTorneo
from app.models.partido import Partido
from app.models.torneo import Torneo
from app.models.torneo_grupo import TorneoGrupo
from app.models.usuario import Usuario
from app.services.motor_formatos import MotorFormatosService

DISCIPLINA_FUTBOL = 1
MODALIDAD_FUTBOL_11 = 1


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


async def _crear_usuario_admin(db_session: AsyncSession, username: str) -> Usuario:
    usuario = Usuario(username=username, nombre=username, password_hash=hash_password("x"), rol="TorneoAdmin")
    db_session.add(usuario)
    await db_session.flush()
    return usuario


async def _sortear(
    db_session: AsyncSession, torneo: Torneo, n_equipos: int, nombre_fase: str = "sortear"
) -> tuple[Fase, list[Partido], Usuario]:
    fase = Fase(torneo_id=torneo.id, nombre="Eliminatoria", tipo="Eliminacion", orden=1, estado="Pendiente")
    db_session.add(fase)
    await db_session.flush()
    usuario = await _crear_usuario_admin(db_session, f"{nombre_fase}_{torneo.id}_admin")
    await db_session.commit()

    await MotorFormatosService(db_session).sortear(torneo.id, usuario.id, semilla="fija")
    partidos = (await db_session.execute(select(Partido).where(Partido.fase_id == fase.id))).scalars().all()
    return fase, list(partidos), usuario


def _es_llave(p: Partido) -> bool:
    return p.partido_ida_id is not None


def _es_ida(p: Partido, todos: list[Partido]) -> bool:
    return any(otro.partido_ida_id == p.id for otro in todos)


async def test_unico_4_equipos_un_partido_por_cruce(db_session: AsyncSession):
    torneo, equipos = await _crear_torneo_con_equipos(db_session, "Unico4", 4, formato_eliminatoria="Unico")
    fase, partidos, _ = await _sortear(db_session, torneo, 4)
    # 2 semifinales + 1 final + 1 tercer lugar, todos partido único.
    assert len(partidos) == 4
    assert all(not _es_llave(p) for p in partidos)
    assert not any(_es_ida(p, partidos) for p in partidos)


async def test_ida_vuelta_4_equipos_dos_partidos_por_cruce_todas_las_rondas(db_session: AsyncSession):
    torneo, equipos = await _crear_torneo_con_equipos(db_session, "IV4", 4, formato_eliminatoria="Ida_Vuelta")
    fase, partidos, _ = await _sortear(db_session, torneo, 4)
    semis = [p for p in partidos if p.ronda_nombre == "Semifinal"]
    finales = [p for p in partidos if p.ronda_nombre == "Final"]
    terceros = [p for p in partidos if p.ronda_nombre == "Tercer Lugar"]
    assert len(semis) == 4       # 2 llaves x 2 piernas
    assert len(finales) == 2     # 1 llave x 2 piernas — Ida_Vuelta incluye la Final
    assert len(terceros) == 1    # Tercer Lugar SIEMPRE único, en los 3 formatos
    assert len(partidos) == 7
    assert not _es_llave(terceros[0])


async def test_mixto_4_equipos_final_a_un_partido(db_session: AsyncSession):
    torneo, equipos = await _crear_torneo_con_equipos(db_session, "Mixto4", 4, formato_eliminatoria="Mixto")
    fase, partidos, _ = await _sortear(db_session, torneo, 4)
    semis = [p for p in partidos if p.ronda_nombre == "Semifinal"]
    finales = [p for p in partidos if p.ronda_nombre == "Final"]
    terceros = [p for p in partidos if p.ronda_nombre == "Tercer Lugar"]
    assert len(semis) == 4       # Mixto: 2 piernas en todo menos la Final
    assert len(finales) == 1     # ... la Final es 1 partido bajo Mixto
    assert len(terceros) == 1
    assert not _es_llave(finales[0])
    assert len(partidos) == 6


async def test_ida_vuelta_2_equipos_final_unica_llave_a_dos_partidos(db_session: AsyncSession):
    """EC-58: rondas <= 1 (n==2) — bajo Ida_Vuelta son 2 partidos, sin
    shells ni Tercer Lugar."""
    torneo, equipos = await _crear_torneo_con_equipos(db_session, "IV2", 2, formato_eliminatoria="Ida_Vuelta")
    fase, partidos, _ = await _sortear(db_session, torneo, 2)
    assert len(partidos) == 2
    assert all(p.ronda_nombre == "Final" for p in partidos)
    vuelta = next(p for p in partidos if _es_llave(p))
    ida = next(p for p in partidos if p.id == vuelta.partido_ida_id)
    # Localía invertida entre las dos piernas.
    assert vuelta.equipos_id_local == ida.equipos_id_visitante
    assert vuelta.equipos_id_visitante == ida.equipos_id_local


async def test_mixto_2_equipos_final_unica_un_solo_partido(db_session: AsyncSession):
    torneo, equipos = await _crear_torneo_con_equipos(db_session, "Mixto2", 2, formato_eliminatoria="Mixto")
    fase, partidos, _ = await _sortear(db_session, torneo, 2)
    assert len(partidos) == 1
    assert not _es_llave(partidos[0])


async def test_ida_vuelta_8_equipos_conteo_exacto_por_ronda(db_session: AsyncSession):
    torneo, equipos = await _crear_torneo_con_equipos(db_session, "IV8", 8, formato_eliminatoria="Ida_Vuelta")
    fase, partidos, _ = await _sortear(db_session, torneo, 8)
    por_ronda: dict[str, int] = {}
    for p in partidos:
        por_ronda[p.ronda_nombre] = por_ronda.get(p.ronda_nombre, 0) + 1
    assert por_ronda == {"Cuartos de Final": 8, "Semifinal": 4, "Final": 2, "Tercer Lugar": 1}
    assert len(partidos) == 15


async def test_byes_por_seed_no_por_posicion_de_cruce(db_session: AsyncSession):
    """Finding 6: con 6 clasificados (tamano=8, 2 byes), los byes tienen
    que caer en los 2 MEJORES seeds, no en los 2 primeros del cruce
    entrelazado (que puede incluir al peor)."""
    torneo, equipos = await _crear_torneo_con_equipos(db_session, "Byes6", 6, formato_eliminatoria="Unico")
    fase = Fase(torneo_id=torneo.id, nombre="Eliminatoria", tipo="Eliminacion", orden=1, estado="Pendiente")
    db_session.add(fase)
    await db_session.flush()
    usuario = await _crear_usuario_admin(db_session, "byes6_admin")
    await db_session.commit()

    # 6 seeds (equipos[0] = seed 1, el mejor) y un cruce ENTRELAZADO
    # deliberadamente adverso: el peor seed (equipos[5], seed 6) queda
    # primero en el cruce, junto al mejor — exactamente el caso que
    # `equipo_ids[:byes_n]` rompía antes de la corrección.
    seeds = equipos
    cruce_adverso = [equipos[0], equipos[5], equipos[1], equipos[4], equipos[2], equipos[3]]
    await MotorFormatosService(db_session)._sortear_bracket(
        torneo, fase, usuario.id, semilla=None, equipo_ids=cruce_adverso, barajar=False,
        formato_eliminatoria="Unico", seeds=seeds,
    )
    await db_session.commit()

    partidos = (await db_session.execute(select(Partido).where(Partido.fase_id == fase.id))).scalars().all()
    cuartos = [p for p in partidos if p.ronda_nombre == "Cuartos de Final"]
    semis = [p for p in partidos if p.ronda_nombre == "Semifinal"]
    # Los 2 mejores seeds (equipos[0], equipos[1]) no juegan Cuartos —
    # entran directo con un bye ya sentado en una Semifinal.
    equipos_en_cuartos = {e for p in cuartos for e in (p.equipos_id_local, p.equipos_id_visitante)}
    assert equipos[0] not in equipos_en_cuartos
    assert equipos[1] not in equipos_en_cuartos
    equipos_con_bye = {e for p in semis for e in (p.equipos_id_local, p.equipos_id_visitante) if e is not None}
    assert equipos[0] in equipos_con_bye
    assert equipos[1] in equipos_con_bye


async def test_rehacer_sorteo_con_llaves_ida_vuelta(db_session: AsyncSession):
    """B5: rehacer el sorteo con Partido_Ida_ID ya seteado no debe violar
    la FK autorreferencial (ON DELETE SET NULL la resuelve sola)."""
    torneo, equipos = await _crear_torneo_con_equipos(db_session, "RehacerIV", 4, formato_eliminatoria="Ida_Vuelta")
    fase, partidos1, usuario = await _sortear(db_session, torneo, 4)
    assert len(partidos1) == 7

    await MotorFormatosService(db_session).sortear(torneo.id, usuario.id, semilla="otra")
    partidos2 = (await db_session.execute(select(Partido).where(Partido.fase_id == fase.id))).scalars().all()
    assert len(partidos2) == 7
    # Los partidos viejos ya no existen (se borraron y recrearon).
    assert {p.id for p in partidos2}.isdisjoint({p.id for p in partidos1})


async def test_liguilla_de_liga_cruza_1_vs_n(db_session: AsyncSession):
    """C2: _cruzar_tabla_unica se invoca correctamente desde el servicio —
    verificado ya a nivel unitario en test_motor_formatos_algoritmos.py;
    acá se confirma que el bracket resultante tiene los equipos
    correctos (sin depender de resultados de partidos, con seeds
    explícitos vía _sortear_bracket directo)."""
    torneo, equipos = await _crear_torneo_con_equipos(
        db_session, "Liguilla4", 4, formato="Liga", formato_eliminatoria="Unico"
    )
    fase = Fase(torneo_id=torneo.id, nombre="Eliminatoria", tipo="Eliminacion", orden=1, estado="Pendiente")
    db_session.add(fase)
    await db_session.flush()
    usuario = await _crear_usuario_admin(db_session, "liguilla4_admin")
    await db_session.commit()

    servicio = MotorFormatosService(db_session)
    cruce, seeds = servicio._cruzar_tabla_unica(equipos)
    assert cruce == [equipos[0], equipos[3], equipos[1], equipos[2]]
    await servicio._sortear_bracket(
        torneo, fase, usuario.id, semilla=None, equipo_ids=cruce, barajar=False,
        formato_eliminatoria="Unico", seeds=seeds,
    )
    await db_session.commit()
    partidos = (await db_session.execute(select(Partido).where(Partido.fase_id == fase.id))).scalars().all()
    semis = [p for p in partidos if p.ronda_nombre == "Semifinal"]
    # 1 vs 4to, 2do vs 3ro — siembra estándar, sin byes (4 clasificados == tamano 4).
    parejas = {frozenset((p.equipos_id_local, p.equipos_id_visitante)) for p in semis}
    assert frozenset((equipos[0], equipos[3])) in parejas
    assert frozenset((equipos[1], equipos[2])) in parejas
