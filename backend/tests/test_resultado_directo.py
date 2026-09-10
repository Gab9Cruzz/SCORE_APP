"""POST /partidos/{id}/resultado-directo (control-mesa-centralizacion-
fixture-plan.md, Sección 5 — Alternativa A): "Cargar resultado directo"
desde Control de Mesa, sin pasar por el cronómetro en vivo.

05_seed.sql: Partido 3 (Halcones=equipo 3 vs Tiburones=equipo 1, Torneo 1,
Fútbol → CONFIGURACION_TIEMPO_TORNEO Periodos) está 'Programado', sin
eventos ni hitos. Jugadores 5/6 pertenecen a Halcones (equipo 3); 1/2 a
Tiburones (equipo 1) — ver JUGADOR_EQUIPO en el seed. Eventos catálogo:
1=Gol, 2=Autogol, 3=Tarjeta Amarilla, 4=Tarjeta Roja, 5=Cambio.
"""
import asyncio

from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.security import hash_password
from app.models.evento_partido import EventoPartido
from app.models.hito_partido import HitoPartido
from app.models.partido import Partido
from app.models.usuario import Usuario
from app.schemas.partido import ResultadoDirectoCreate, ResultadoDirectoEvento
from app.services.partido import PartidoService


async def _hitos_de(db_session: AsyncSession, partido_id: int) -> list[HitoPartido]:
    stmt = select(HitoPartido).where(HitoPartido.partido_id == partido_id)
    return list((await db_session.execute(stmt)).scalars().all())


async def _eventos_de(db_session: AsyncSession, partido_id: int) -> list[EventoPartido]:
    stmt = select(EventoPartido).where(EventoPartido.partidos_id == partido_id)
    return list((await db_session.execute(stmt)).scalars().all())


async def test_resultado_directo_happy_path_dos_goles_y_una_tarjeta(
    client: AsyncClient, db_session: AsyncSession, arbitro_headers: dict[str, str]
):
    resp = await client.post(
        "/api/v1/partidos/3/resultado-directo",
        json={
            "eventos": [
                {"jugador_id": 5, "equipo_id": 3, "eventos_id": 1, "minuto": 10},  # Gol Halcones
                {"jugador_id": 1, "equipo_id": 1, "eventos_id": 1, "minuto": 30},  # Gol Tiburones
                {"jugador_id": 6, "equipo_id": 3, "eventos_id": 3, "minuto": 40},  # Amarilla Halcones
            ]
        },
        headers=arbitro_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["estado"] == "Finalizado"

    hitos = await _hitos_de(db_session, 3)
    tipos = sorted(h.tipo_hito for h in hitos)
    assert tipos == ["Fin_Partido", "Inicio_Partido"]

    eventos = await _eventos_de(db_session, 3)
    assert len(eventos) == 3
    assert all(e.estado == "Registrado" for e in eventos)


async def test_resultado_directo_sin_eventos_deja_0_0(
    client: AsyncClient, db_session: AsyncSession, arbitro_headers: dict[str, str]
):
    resp = await client.post("/api/v1/partidos/3/resultado-directo", json={"eventos": []}, headers=arbitro_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["estado"] == "Finalizado"
    assert await _eventos_de(db_session, 3) == []
    hitos = await _hitos_de(db_session, 3)
    assert len(hitos) == 2


async def test_resultado_directo_evento_invalido_a_mitad_revierte_todo(
    client: AsyncClient, db_session: AsyncSession, arbitro_headers: dict[str, str]
):
    """CRÍTICO (Sección 9/11 del plan): un evento inválido (jugador_id=3
    pertenece al equipo 2 — Águilas —, ajeno a este partido) a mitad de la
    lista debe revertir la transacción COMPLETA — ni el primer evento
    (válido) ni el Hito Inicio_Partido pueden quedar persistidos."""
    resp = await client.post(
        "/api/v1/partidos/3/resultado-directo",
        json={
            "eventos": [
                {"jugador_id": 5, "equipo_id": 3, "eventos_id": 1, "minuto": 10},  # válido
                {"jugador_id": 3, "equipo_id": 3, "eventos_id": 1, "minuto": 20},  # jugador ajeno al equipo
            ]
        },
        headers=arbitro_headers,
    )
    assert resp.status_code == 400, resp.text

    # Nada quedó persistido: ni el evento válido, ni el Hito de inicio.
    assert await _eventos_de(db_session, 3) == []
    assert await _hitos_de(db_session, 3) == []
    resp_partido = await client.get("/api/v1/partidos/3")
    assert resp_partido.json()["estado"] == "Programado"


async def test_resultado_directo_partido_finalizado_es_rechazado(
    client: AsyncClient, db_session: AsyncSession, arbitro_headers: dict[str, str]
):
    # Partido 1 (seed) ya está 'Finalizado' — sin árbitro asignado en el
    # seed, se lo asigna acá para aislar el chequeo de estado del de ownership.
    partido = await db_session.get(Partido, 1)
    arbitro = (
        await db_session.execute(select(Usuario).where(Usuario.username == "arbitro_test"))
    ).scalars().first()
    partido.arbitro_id = arbitro.id
    await db_session.commit()

    resp = await client.post("/api/v1/partidos/1/resultado-directo", json={"eventos": []}, headers=arbitro_headers)
    assert resp.status_code == 400, resp.text
    assert "Finalizado" in resp.json()["detail"]


async def test_resultado_directo_partido_sin_los_dos_equipos_definidos_es_rechazado(
    client: AsyncClient, db_session: AsyncSession, torneo_admin_con_torneo_headers: dict[str, str]
):
    # Un partido de bracket con equipos_id_local/visitante en NULL ("TBD")
    # — mismo criterio que marcar_walkover. Se arma un torneo de Eliminación
    # aparte en vez de tocar el seed, para no interferir con otros tests.
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "torneo_grupo_nombre": "Torneo Eliminacion Resultado Directo",
            "disciplina_id": 1,
            "modalidad_id": 1,
            "fecha_inicio": "2026-07-01",
            "fecha_fin": "2026-08-01",
            "formato": "Eliminacion",
        },
        headers=torneo_admin_con_torneo_headers,
    )
    torneo_id = resp.json()["id"]
    equipos = []
    for i in range(4):
        r = await client.post(
            "/api/v1/equipos",
            json={"nombre": f"Equipo Bracket RD {i}", "disciplina_id": 1, "modalidad_id": 1},
            headers=torneo_admin_con_torneo_headers,
        )
        equipos.append(r.json()["id"])
    for equipo_id in equipos:
        r = await client.post(
            "/api/v1/inscripciones",
            json={"torneo_id": torneo_id, "equipo_id": equipo_id},
            headers=torneo_admin_con_torneo_headers,
        )
        assert r.status_code == 201, r.text
    resp = await client.post(
        f"/api/v1/torneos/{torneo_id}/sorteo", json={}, headers=torneo_admin_con_torneo_headers
    )
    assert resp.status_code in (200, 201), resp.text

    resp_partidos = await client.get("/api/v1/partidos", params={"torneo_id": torneo_id})
    partido_tbd = next(
        p for p in resp_partidos.json() if p["equipos_id_local"] is None or p["equipos_id_visitante"] is None
    )

    resp = await client.post(
        f"/api/v1/partidos/{partido_tbd['id']}/resultado-directo",
        json={"eventos": []},
        headers=torneo_admin_con_torneo_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "equipos" in resp.json()["detail"].lower()


async def test_resultado_directo_requiere_asignacion_de_torneo(
    client: AsyncClient, torneo_admin_headers: dict[str, str]
):
    resp = await client.post(
        "/api/v1/partidos/3/resultado-directo", json={"eventos": []}, headers=torneo_admin_headers
    )
    assert resp.status_code == 403


async def test_resultado_directo_arbitro_no_asignado_es_rechazado(
    client: AsyncClient, arbitro_no_asignado_headers: dict[str, str]
):
    resp = await client.post(
        "/api/v1/partidos/3/resultado-directo", json={"eventos": []}, headers=arbitro_no_asignado_headers
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# gestionar-partido-alineaciones-plan.md (H7 / D4): este endpoint inserta el
# HitoPartido a mano, así que NUNCA pasa por HitoPartidoService.registrar y se
# salteaba las dos validaciones que ese aplica. Una era un agujero; la otra es
# deliberada.
# ---------------------------------------------------------------------------


async def test_resultado_directo_en_torneo_archivado_es_rechazado(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """Cargar un resultado en un torneo archivado no tiene ninguna lectura
    legítima: era un agujero, no una decisión. El guard va ANTES del primer
    flush() — después del Inicio_Partido el trigger ya movió PARTIDOS.Estado en
    la base mientras el objeto Python sigue diciendo 'Programado'."""
    from app.models.torneo import Torneo
    from app.models.torneo_grupo import TorneoGrupo

    partido = await db_session.get(Partido, 3)
    torneo = await db_session.get(Torneo, partido.torneo_id)
    grupo = await db_session.get(TorneoGrupo, torneo.torneo_grupo_id)
    grupo.estado = "Archivado"
    await db_session.commit()

    resp = await client.post(
        "/api/v1/partidos/3/resultado-directo", json={"eventos": []}, headers=admin_general_headers
    )
    assert resp.status_code == 400, resp.text
    assert "archivado" in resp.json()["detail"].lower()

    # Nada quedó a medias.
    assert await _hitos_de(db_session, 3) == []


async def test_resultado_directo_no_exige_convocatoria(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """Decisión explícita (D4), y ahora con test que la fija por escrito: este
    camino existe para partidos que YA se jugaron y se registraron en papel,
    donde exigir una alineación sería pedir un dato que el operador no tiene.

    Antes era un comportamiento implícito —efecto colateral de que el hito se
    inserta a mano— que se podía romper sin que nadie se enterara."""
    convocados = await client.get("/api/v1/partidos/3/convocados")
    assert convocados.json() == []

    resp = await client.post(
        "/api/v1/partidos/3/resultado-directo", json={"eventos": []}, headers=admin_general_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["estado"] == "Finalizado"


# ---------------------------------------------------------------------------
# goles-por-marcador-slots-plan.md (Fase 1, hallazgo 6 / Fase 3 Eng, correcciones
# 1-2): antes de estas correcciones, este endpoint nunca validaba reglas de
# cambio (tope/no-retorno/doble-salida) y no tenía ningún lock contra 2
# requests concurrentes sobre el mismo partido 'Programado'.
# ---------------------------------------------------------------------------


async def test_resultado_directo_valida_tope_de_cambios(
    client: AsyncClient, db_session: AsyncSession, arbitro_headers: dict[str, str],
    torneo_admin_con_torneo_headers: dict[str, str],
):
    """Antes de la corrección (hallazgo 6): un resultado directo con más
    cambios que el tope del torneo se aceptaba sin aviso — `registrar_resultado_directo`
    nunca llamaba `validar_reglas_cambio`. Ahora sí, y la transacción
    completa se revierte (mismo criterio que cualquier evento inválido a
    mitad del batch)."""
    resp = await client.patch(
        "/api/v1/torneos/1", json={"maximo_cambios_por_equipo": 1}, headers=torneo_admin_con_torneo_headers
    )
    assert resp.status_code == 200, resp.text

    resp = await client.post(
        "/api/v1/partidos/3/resultado-directo",
        json={
            "eventos": [
                {"jugador_id": 5, "equipo_id": 3, "eventos_id": 5, "jugador_id_entra": 6, "minuto": 10},  # Cambio 1
                {"jugador_id": 6, "equipo_id": 3, "eventos_id": 5, "jugador_id_entra": 7, "minuto": 20},  # Cambio 2, excede tope=1
            ]
        },
        headers=arbitro_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "cambios" in resp.json()["detail"].lower()
    # Ninguno de los 2 eventos quedó persistido — atomicidad del batch.
    assert await _eventos_de(db_session, 3) == []
    assert await _hitos_de(db_session, 3) == []


async def test_resultado_directo_valida_doble_salida_del_mismo_jugador(
    client: AsyncClient, db_session: AsyncSession, arbitro_headers: dict[str, str]
):
    """Hallazgo 3 (Fase 1) — el mismo jugador (jugador_id) no puede "salir"
    dos veces en el mismo batch de resultado directo."""
    resp = await client.post(
        "/api/v1/partidos/3/resultado-directo",
        json={
            "eventos": [
                {"jugador_id": 5, "equipo_id": 3, "eventos_id": 5, "jugador_id_entra": 6, "minuto": 10},
                {"jugador_id": 5, "equipo_id": 3, "eventos_id": 5, "jugador_id_entra": 7, "minuto": 20},
            ]
        },
        headers=arbitro_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "volver a salir" in resp.json()["detail"].lower()
    assert await _eventos_de(db_session, 3) == []


async def test_resultado_directo_concurrencia_real_solo_uno_gana(engine: AsyncEngine):
    """Concurrencia REAL contra la base (mismo criterio que
    test_ec6_confirmar_concurrente_no_supera_el_cupo en test_registro_lote.py
    — el resto de este archivo comparte una única conexión/transacción con
    savepoints vía el fixture `client`/`db_session`, donde 2 tasks
    "concurrentes" se serializan solas sin ejercitar el lock de verdad).
    Este test abre conexiones propias y lanza 2
    `PartidoService.registrar_resultado_directo()` de verdad en paralelo
    (`asyncio.gather`) contra el MISMO partido 3 'Programado' — exactamente
    el escenario de la corrección 2 (Fase 3 Eng): doble-click antes de que
    React re-renderice `isPending`, o 2 pestañas. Sin `get_or_404_bloqueado`,
    las 2 transacciones podían leer `estado='Programado'` antes de que
    cualquiera hiciera commit, y las 2 insertar Inicio_Partido+Fin_Partido.

    Como este test hace commits reales (no la transacción de test que se
    revierte sola — a propósito, necesita conexiones independientes para que
    la concurrencia sea real), la limpieza de partido 3 es manual."""

    async def _sesion_real() -> tuple[AsyncSession, object]:
        connection = await engine.connect()
        return AsyncSession(bind=connection, expire_on_commit=False), connection

    async def _cargar(usuario_id: int) -> str:
        connection = await engine.connect()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            # No persistido — solo `.id`/`.rol` importan acá (`registrado_por`
            # necesita un id que exista de verdad en `usuarios`, por la FK;
            # `verificar_arbitro_asignado` solo lee `.rol`).
            usuario_actual = Usuario(id=usuario_id, rol="AdminGeneral")
            await PartidoService(session).registrar_resultado_directo(
                3,
                ResultadoDirectoCreate(eventos=[ResultadoDirectoEvento(jugador_id=5, equipo_id=3, eventos_id=1, minuto=10)]),
                usuario_actual,
            )
            return "gano"
        except Exception as exc:  # noqa: BLE001 — cualquier rechazo de dominio cuenta como "perdió la carrera"
            return f"rechazado: {exc}"
        finally:
            await session.close()
            await connection.close()

    setup, setup_conn = await _sesion_real()
    usuario_id: int | None = None
    try:
        # Usuario real y persistido (no el stand-in no-persistido de
        # test_registro_lote.py — ahí solo se leía `.rol`; acá
        # `registrado_por` es una FK real a `usuarios.id`).
        usuario = Usuario(
            username="concurrencia_rd_test",
            nombre="Concurrencia RD Test",
            password_hash=hash_password("x"),
            rol="AdminGeneral",
        )
        setup.add(usuario)
        await setup.commit()
        await setup.refresh(usuario)
        usuario_id = usuario.id

        resultados = await asyncio.gather(_cargar(usuario_id), _cargar(usuario_id))
        ganaron = [r for r in resultados if r == "gano"]
        rechazados = [r for r in resultados if r != "gano"]
        assert len(ganaron) == 1, f"el lock debía dejar pasar exactamente 1 carga, pasaron {len(ganaron)}: {resultados}"
        assert len(rechazados) == 1

        # La verdad de la base: exactamente 1 Hito Inicio_Partido, no 2.
        inicio = await setup.execute(
            text("SELECT COUNT(*) FROM hitos_partido WHERE partido_id = 3 AND tipo_hito = 'Inicio_Partido'")
        )
        assert inicio.scalar() == 1
    finally:
        # Reset manual de partido 3 a 'Programado' — este test no corre
        # dentro de la transacción que se revierte sola.
        await setup.execute(text("DELETE FROM eventos_partido WHERE partidos_id = 3"))
        await setup.execute(text("DELETE FROM hitos_partido WHERE partido_id = 3"))
        await setup.execute(
            text("UPDATE partidos SET estado = 'Programado', ganador_corrido_id = NULL WHERE id = 3")
        )
        if usuario_id is not None:
            await setup.execute(text("DELETE FROM usuarios WHERE id = :id"), {"id": usuario_id})
        await setup.commit()
        await setup.close()
        await setup_conn.close()
