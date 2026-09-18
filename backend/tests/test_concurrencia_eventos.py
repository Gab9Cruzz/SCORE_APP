"""A2/A3 (docs/plans/cierre-pendientes-todos-plan.md) — tests de
concurrencia REAL, con dos conexiones DB genuinamente paralelas
(`sesiones_paralelas`, backend/tests/conftest.py), contra su propia base
(`torneos_mvp_test_concurrencia`). No corren en `pytest -q` por default
(`@pytest.mark.concurrencia`, ver `pytest.ini` y `verificar.ps1
-Concurrencia`).

A3 llama a los SERVICIOS directo, no por las rutas: la fixture `client`
sobreescribe `get_db` con la `db_session` única y compartida del harness
normal, así que dos sesiones genuinamente independientes no pueden pasar
por ella. Esto prueba el invariante del SERVICIO (el lock, la transacción
única); `verificar_arbitro_asignado`/`require_roles`/el mapeo del handler a
409 quedan cubiertos aparte por `test_eventos_partido.py` (fixture `client`,
vía monkeypatch — ver A1)."""
import asyncio
import logging

import pytest

from app.models.usuario import Usuario
from app.core.security import hash_password
from app.services.evento_partido import EventoPartidoService
from app.schemas.evento_partido import EventoPartidoCreate


async def _crear_arbitro_asignado(session, partido_id: int = 3) -> Usuario:
    """Mismo patrón que `arbitro_headers` en conftest.py, pero contra
    `sesiones_paralelas` (esa fixture usa `db_session`, esta base es
    otra) — un árbitro nuevo, asignado al partido `partido_id` del seed."""
    from app.models.partido import Partido

    usuario = Usuario(
        username="arbitro_concurrencia",
        nombre="Arbitro Concurrencia",
        password_hash=hash_password("arbitropass123"),
        rol="Arbitro",
    )
    session.add(usuario)
    await session.flush()
    partido = await session.get(Partido, partido_id)
    partido.arbitro_id = usuario.id
    await session.commit()
    await session.refresh(usuario)
    return usuario


async def _empezar_partido(session, partido_id: int = 3) -> None:
    """Arranca el partido `partido_id` con lo mínimo que
    `EventoPartidoService.create` exige: Inicio_Partido + convocatoria de
    titulares completa (D4, HitoPartidoService.registrar). Reconstruye a
    mano lo que `convocar_titulares`/`_empezar_partido` hacen en
    conftest.py/test_eventos_partido.py contra `db_session` — acá no
    aplica, la base es otra."""
    from datetime import date

    from sqlalchemy import select

    from app.models.convocado_a_partido import ConvocadoAPartido
    from app.models.hito_partido import HitoPartido
    from app.models.inscripcion_torneo import InscripcionTorneo
    from app.models.jugador import Jugador
    from app.models.jugador_equipo import JugadorEquipo
    from app.models.jugador_perfil_disciplina import JugadorPerfilDisciplina
    from app.models.modalidad import Modalidad
    from app.models.partido import Partido
    from app.models.torneo import Torneo

    partido = await session.get(Partido, partido_id)
    torneo = await session.get(Torneo, partido.torneo_id)
    modalidad = await session.get(Modalidad, torneo.modalidad_id)
    requeridos = modalidad.tamano_equipo

    contador = 0
    for equipo_id in (partido.equipos_id_local, partido.equipos_id_visitante):
        inscripcion = (
            await session.execute(
                select(InscripcionTorneo).where(
                    InscripcionTorneo.torneo_id == torneo.id, InscripcionTorneo.equipo_id == equipo_id
                )
            )
        ).scalars().first()
        roster = list(
            (
                await session.execute(
                    select(JugadorEquipo).where(
                        JugadorEquipo.inscripcion_torneo_id == inscripcion.id, JugadorEquipo.estado == "Activo"
                    )
                )
            ).scalars().all()
        )
        for _ in range(max(requeridos - len(roster), 0)):
            contador += 1
            jugador = Jugador(
                nombre=f"Titular Concurrencia {contador}",
                cedula=f"8888{contador:06d}",
                correo_electronico=f"titular.concurrencia.{contador}@example.com",
            )
            session.add(jugador)
            await session.flush()
            perfil = JugadorPerfilDisciplina(jugador_id=jugador.id, disciplina_id=torneo.disciplina_id)
            session.add(perfil)
            await session.flush()
            vinculo = JugadorEquipo(
                jugador_perfil_id=perfil.id,
                inscripcion_torneo_id=inscripcion.id,
                fecha_inicio=date(2026, 1, 1),
                estado="Activo",
            )
            session.add(vinculo)
            roster.append(vinculo)
        await session.flush()
        for v in roster:
            session.add(ConvocadoAPartido(partido_id=partido_id, jugador_perfil_id=v.jugador_perfil_id, titular=True))

    session.add(HitoPartido(partido_id=partido_id, tipo_hito="Inicio_Partido", registrado_por=1))
    await session.commit()


@pytest.mark.concurrencia
async def test_smoke_sesiones_paralelas_son_conexiones_independientes(sesiones_paralelas):
    """A2: sanity check del fixture en sí — dos sesiones, cada una ve lo
    que la otra commiteó (base compartida, real), y ninguna comparte
    conexión (si compartieran, esto no probaría nada sobre concurrencia)."""
    sesion_a, sesion_b = sesiones_paralelas
    usuario = await _crear_arbitro_asignado(sesion_a)

    visto_por_b = await sesion_b.get(Usuario, usuario.id)
    assert visto_por_b is not None
    assert visto_por_b.username == "arbitro_concurrencia"


@pytest.mark.concurrencia
async def test_doble_amarilla_simultanea_autogenera_una_sola_roja(sesiones_paralelas):
    """A1/A3: el test real de lo que Track A vino a arreglar — dos
    sesiones insertan la Tarjeta Amarilla #2 del MISMO jugador AL MISMO
    TIEMPO. Sin el lock de A1, las dos cuentan 1 amarilla cada una y
    ninguna dispara la roja automática. Con el lock, una se serializa
    detrás de la otra (mismo recurso, mismo orden = contención, no
    deadlock) y exactamente una ve el conteo correcto."""
    sesion_a, sesion_b = sesiones_paralelas
    usuario_a = await _crear_arbitro_asignado(sesion_a)
    await _empezar_partido(sesion_a)
    # `usuario_a` fue commiteado por sesion_a — visible para sesion_b vía
    # su propia fila (misma base real), no el mismo objeto Python.
    usuario_b = await sesion_b.get(type(usuario_a), usuario_a.id)

    data = EventoPartidoCreate(partidos_id=3, jugador_id=5, equipo_id=3, eventos_id=3)  # Tarjeta Amarilla

    async with asyncio.timeout(15):
        await asyncio.gather(
            EventoPartidoService(sesion_a).create(data, usuario_a),
            EventoPartidoService(sesion_b).create(data, usuario_b),
        )

    from sqlalchemy import select

    from app.models.evento_partido import EventoPartido

    eventos = (
        await sesion_a.execute(
            select(EventoPartido).where(EventoPartido.partidos_id == 3, EventoPartido.jugador_id == 5)
        )
    ).scalars().all()
    amarillas = [e for e in eventos if e.eventos_id == 3]
    rojas = [e for e in eventos if e.eventos_id == 4]
    assert len(amarillas) == 2, f"esperaba 2 amarillas, hay {len(amarillas)}"
    assert len(rojas) == 1, f"esperaba exactamente 1 roja automática, hay {len(rojas)} — A1 no cerró la carrera"


@pytest.mark.concurrencia
async def test_contencion_real_de_lock_devuelve_409_y_loguea(sesiones_paralelas, caplog):
    """A1/A3: contención REAL (no simulada) — sesion_a mantiene el lock
    del partido abierto (no commitea todavía) mientras sesion_b intenta
    tomarlo; sesion_b tiene que vencer `evento_lock_timeout_ms` y recibir
    ConcurrencyConflictError, con el log de espera larga."""
    from app.core.config import get_settings
    from app.exceptions.errors import ConcurrencyConflictError
    from app.repositories.partido import PartidoRepository

    settings = get_settings()
    umbral_original = settings.evento_lock_timeout_ms
    settings.evento_lock_timeout_ms = 500  # acota el test a ~0.5s de espera real
    try:
        sesion_a, sesion_b = sesiones_paralelas
        usuario_a = await _crear_arbitro_asignado(sesion_a)
        await _empezar_partido(sesion_a)
        usuario_b = await sesion_b.get(type(usuario_a), usuario_a.id)

        # sesion_a toma el lock del partido y lo retiene sin commitear.
        await PartidoRepository(sesion_a).get_or_404_bloqueado(3)

        data = EventoPartidoCreate(partidos_id=3, jugador_id=5, equipo_id=3, eventos_id=1)  # Gol

        with caplog.at_level(logging.WARNING, logger="app.concurrencia"):
            async with asyncio.timeout(10):
                with pytest.raises(ConcurrencyConflictError) as excinfo:
                    await EventoPartidoService(sesion_b).create(data, usuario_b)

        assert excinfo.value.detail == "evento_conflicto_concurrente"
        assert any("Espera larga por FOR UPDATE" in r.getMessage() for r in caplog.records)

        await sesion_a.rollback()
    finally:
        settings.evento_lock_timeout_ms = umbral_original


# A1/A2 (docs/plans/cierre-pendientes-todos-plan.md) — guard de nombre de
# base ante operación destructiva. Sin marker `concurrencia` ni fixture: no
# toca ninguna base real, el guard levanta ANTES de `_connect` siquiera.
async def test_guard_de_nombre_de_base_rechaza_una_base_que_no_es_de_test():
    from tests.conftest import NombreDeBaseNoEsDeTestError, _recrear_base

    with pytest.raises(NombreDeBaseNoEsDeTestError):
        await _recrear_base("torneos_mvp")
