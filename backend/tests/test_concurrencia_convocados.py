"""T23/T24 (TODOS.md, revisión de cierre 2026-09-18) — tests de concurrencia
REAL (dos conexiones DB genuinamente paralelas, `sesiones_paralelas` en
conftest.py) para el tope de titulares y el doble `Fin_Partido`.

Corrección importante sobre la premisa original de TODOS.md: ninguno de los
dos invariantes necesitaba un fix nuevo de Python. Ambos ya estaban cerrados
a nivel de base de datos ANTES de este archivo:

- Tope de titulares: `fn_validar_tope_titulares` (06_triggers.sql) toma
  `FOR UPDATE` sobre la fila de PARTIDOS antes de contar — el mismo patrón
  de lock de fila que A1 (Resuelto 2026-09-18) usa en
  `EventoPartidoService`, solo que acá vive en el trigger, no en Python,
  porque el tope es un número (no una unicidad) y no se puede cerrar con un
  índice único simple.
- Doble `Fin_Partido`: `uq_hitos_partido_fin_unico` (03_indexes.sql), un
  índice único parcial, mismo patrón que T15.

El `SELECT` sin lock que hace `ConvocadoAPartidoService._validar_tope_titulares`
en Python es solo el chequeo de UX rápido (mensaje claro antes del round-trip
del trigger) — la fuente de verdad final es la DB. Lo que faltaba de verdad
era la prueba con conexiones reales, no el fix.

Sigue el mismo patrón que `test_concurrencia_eventos.py` (A2/A3): llama a los
SERVICIOS directo, no por las rutas (`client` comparte una única `db_session`,
que no sirve para dos transacciones genuinamente paralelas)."""
import asyncio

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.core.security import hash_password
from app.models.convocado_a_partido import ConvocadoAPartido
from app.models.hito_partido import HitoPartido
from app.models.partido import Partido
from app.models.usuario import Usuario
from app.schemas.convocado_a_partido import ConvocadoAgregarRequest
from app.schemas.hito_partido import HitoPartidoCreate
from app.services.convocado_a_partido import ConvocadoAPartidoService
from app.services.hito_partido import HitoPartidoService
from tests.test_titulares_inicio_partido import (
    _agregar_jugador_activo,
    _armar_torneo_con_partido,
    _convocar,
)


async def _crear_arbitro_asignado(session, partido_id: int, sufijo: str) -> Usuario:
    """Mismo patrón que `_crear_arbitro_asignado` en
    test_concurrencia_eventos.py, pero con username parametrizado — cada
    test de este archivo arma su propio torneo/partido (a diferencia de
    A2/A3, que reusan el partido_id=3 del seed), así que no hace falta un
    árbitro distinto por partido, pero sí un username distinto por test para
    no chocar contra `unique_username` si algún día corren en la misma base
    sin reconstruirla entre tests (no es el caso hoy — `sesiones_paralelas`
    es function-scoped — pero es gratis evitarlo)."""
    usuario = Usuario(
        username=f"arbitro_concurrencia_{sufijo}",
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


@pytest.mark.concurrencia
async def test_dos_altas_de_titulares_distintos_al_tope_no_lo_exceden(sesiones_paralelas):
    """T23: dos POST /convocados con `titular=True` para DOS jugadores
    DISTINTOS del mismo equipo, al mismo tiempo, contra un tope de 1
    titular (`tamano_equipo=1`). El `SELECT` de Python en
    `ConvocadoAPartidoService._validar_tope_titulares` no tiene lock: las
    dos lecturas ven 0 titulares y las dos pasan ese chequeo. Sin el lock
    real (el trigger), las dos altas se insertarían y el equipo terminaría
    con 2 titulares para un tope de 1. Con el lock, exactamente una gana la
    carrera contra `PARTIDOS ... FOR UPDATE` y la otra choca con el
    trigger."""
    sesion_a, sesion_b = sesiones_paralelas
    ctx = await _armar_torneo_con_partido(sesion_a, tamano_equipo=1, nombre="T23")
    p1 = await _agregar_jugador_activo(sesion_a, ctx["disciplina_id"], ctx["insc_local_id"], "T23A")
    p2 = await _agregar_jugador_activo(sesion_a, ctx["disciplina_id"], ctx["insc_local_id"], "T23B")
    usuario_a = await _crear_arbitro_asignado(sesion_a, ctx["partido_id"], "t23")
    usuario_b = await sesion_b.get(Usuario, usuario_a.id)

    data_1 = ConvocadoAgregarRequest(jugador_perfil_id=p1, titular=True)
    data_2 = ConvocadoAgregarRequest(jugador_perfil_id=p2, titular=True)

    # Fuerza el solape real. Sin esto, las dos altas son tan rápidas contra
    # Postgres local que `asyncio.gather` las corre una atrás de la otra sin
    # pisarse nunca (se probó: la perdedora terminaba viendo el estado YA
    # commiteado por la ganadora en su propio SELECT de Python, un
    # DomainRuleError normal — no ejercita la carrera, ninguna prueba real
    # de que el trigger hace falta). Acá sesion_a toma el lock de fila del
    # PARTIDO — el mismo recurso que bloquea `fn_validar_tope_titulares` —
    # ANTES de que exista ningún titular todavía, así que el `SELECT` sin
    # lock de sesion_b sigue viendo 0 titulares (reproduce la ventana TOCTOU
    # real) y su INSERT se bloquea de verdad esperando a sesion_a.
    await sesion_a.execute(text("SELECT 1 FROM partidos WHERE id = :id FOR UPDATE"), {"id": ctx["partido_id"]})

    tarea_b = asyncio.create_task(
        ConvocadoAPartidoService(sesion_b).agregar(ctx["partido_id"], data_2, usuario_b)
    )
    # Le da tiempo a sesion_b de correr sus SELECTs previos (ve 0 titulares,
    # como sesion_a) y quedar genuinamente bloqueada en el INSERT — de sobra
    # frente a un puñado de queries locales de submilisegundo cada una.
    await asyncio.sleep(0.2)

    async with asyncio.timeout(15):
        try:
            resultado_a = await ConvocadoAPartidoService(sesion_a).agregar(ctx["partido_id"], data_1, usuario_a)
        except Exception as exc:  # noqa: BLE001 - se clasifica más abajo
            resultado_a = exc
        try:
            resultado_b = await tarea_b
        except Exception as exc:  # noqa: BLE001
            resultado_b = exc

    resultados = [resultado_a, resultado_b]
    exitosos = [r for r in resultados if not isinstance(r, Exception)]
    fallidos = [r for r in resultados if isinstance(r, Exception)]
    assert len(exitosos) == 1, (
        f"esperaba exactamente 1 alta exitosa de las 2 concurrentes, hubo {len(exitosos)} "
        "— el trigger no cerró la carrera del tope de titulares"
    )
    assert len(fallidos) == 1, f"esperaba exactamente 1 falla, hubo {len(fallidos)}: {fallidos}"
    assert isinstance(fallidos[0], DBAPIError), f"esperaba un DBAPIError del trigger, fue {type(fallidos[0])}"

    for sesion in (sesion_a, sesion_b):
        try:
            await sesion.rollback()
        except Exception:
            pass

    filas = (
        await sesion_a.execute(
            select(ConvocadoAPartido).where(ConvocadoAPartido.partido_id == ctx["partido_id"])
        )
    ).scalars().all()
    titulares = [f for f in filas if f.titular]
    assert len(titulares) == 1, f"esperaba 1 solo titular tras resolverse la carrera, hay {len(titulares)}"


@pytest.mark.concurrencia
async def test_doble_fin_partido_simultaneo_cierra_uno_solo(sesiones_paralelas):
    """T24: dos hitos `Fin_Partido` para el MISMO partido en curso, al
    mismo tiempo (torneo 'Corrido', cierre normal — no forzado). El chequeo
    de Python (`estado['acciones_permitidas']`, vía `_calcular_estado`) lee
    los hitos ya existentes sin lock: las dos lecturas ven "todavía no hay
    Fin_Partido" y las dos pasan. Hay DOS defensas en la DB detrás de eso —
    `fn_validar_hito_partido` (un `SELECT COUNT(*)` previo al INSERT, con la
    misma ventana TOCTOU que el chequeo de Python) y, si esa también se
    solapa mal, el índice único parcial `uq_hitos_partido_fin_unico` como
    backstop final (03_indexes.sql lo documenta así). Cuál de las dos
    termina rechazando a la perdedora depende del orden exacto de la
    carrera — lo que importa acá es que exactamente una de las dos
    escrituras concurrentes gana, nunca las dos."""
    sesion_a, sesion_b = sesiones_paralelas
    ctx = await _armar_torneo_con_partido(sesion_a, tamano_equipo=1, nombre="T24")
    titular_local = await _agregar_jugador_activo(sesion_a, ctx["disciplina_id"], ctx["insc_local_id"], "T24L")
    titular_visitante = await _agregar_jugador_activo(
        sesion_a, ctx["disciplina_id"], ctx["insc_visitante_id"], "T24V"
    )
    await _convocar(sesion_a, ctx["partido_id"], titular_local, titular=True)
    await _convocar(sesion_a, ctx["partido_id"], titular_visitante, titular=True)
    usuario_a = await _crear_arbitro_asignado(sesion_a, ctx["partido_id"], "t24")
    usuario_b = await sesion_b.get(Usuario, usuario_a.id)

    await HitoPartidoService(sesion_a).registrar(
        ctx["partido_id"], HitoPartidoCreate(tipo_hito="Inicio_Partido"), usuario_a
    )

    data = HitoPartidoCreate(tipo_hito="Fin_Partido", ganador_corrido_id=ctx["equipo_local_id"])

    # Mismo motivo que en el test de titulares (ver comentario ahí): sin
    # forzar el solape, las dos altas corren una atrás de la otra y la
    # perdedora choca contra el gate de Python (`acciones_permitidas`, ya
    # actualizado por el cierre de la otra), no contra el índice único —
    # no prueba nada sobre la carrera real. `registrar()` en la rama
    # Fin_Partido/Corrido hace un UPDATE de Ganador_Corrido_ID sobre el
    # PARTIDO antes del INSERT del Hito, así que el mismo lock de fila
    # alcanza para forzar que sesion_b se quede esperando de verdad.
    await sesion_a.execute(text("SELECT 1 FROM partidos WHERE id = :id FOR UPDATE"), {"id": ctx["partido_id"]})

    tarea_b = asyncio.create_task(HitoPartidoService(sesion_b).registrar(ctx["partido_id"], data, usuario_b))
    await asyncio.sleep(0.2)

    async with asyncio.timeout(15):
        try:
            resultado_a = await HitoPartidoService(sesion_a).registrar(ctx["partido_id"], data, usuario_a)
        except Exception as exc:  # noqa: BLE001 - se clasifica más abajo
            resultado_a = exc
        try:
            resultado_b = await tarea_b
        except Exception as exc:  # noqa: BLE001
            resultado_b = exc

    resultados = [resultado_a, resultado_b]
    exitosos = [r for r in resultados if not isinstance(r, Exception)]
    fallidos = [r for r in resultados if isinstance(r, Exception)]
    assert len(exitosos) == 1, (
        f"esperaba exactamente 1 cierre exitoso de los 2 concurrentes, hubo {len(exitosos)} "
        "— el índice único no cerró la carrera del doble Fin_Partido"
    )
    assert len(fallidos) == 1, f"esperaba exactamente 1 falla, hubo {len(fallidos)}: {fallidos}"
    assert isinstance(fallidos[0], DBAPIError), (
        f"esperaba un DBAPIError (fn_validar_hito_partido o uq_hitos_partido_fin_unico), fue {type(fallidos[0])}"
    )

    for sesion in (sesion_a, sesion_b):
        try:
            await sesion.rollback()
        except Exception:
            pass

    hitos_fin = (
        await sesion_a.execute(
            select(HitoPartido).where(
                HitoPartido.partido_id == ctx["partido_id"], HitoPartido.tipo_hito == "Fin_Partido"
            )
        )
    ).scalars().all()
    assert len(hitos_fin) == 1, f"esperaba 1 solo Fin_Partido tras resolverse la carrera, hay {len(hitos_fin)}"

    partido_final = await sesion_a.get(Partido, ctx["partido_id"])
    assert partido_final.estado == "Finalizado"
