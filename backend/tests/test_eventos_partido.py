import logging

import pytest
from httpx import AsyncClient
from psycopg import errors as psycopg_errors
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.partido import Partido
from app.repositories.partido import PartidoRepository


async def _empezar_partido(client: AsyncClient, headers: dict[str, str], convocar_titulares, partido_id: int = 3) -> None:
    """3A-8 (docs/plans/cierre-backlog-todos-plan.md): EventoPartidoService.create
    ahora exige partido.estado == 'En curso' (antes, el único guard vivía en
    el filtro de la lista de ControlDeMesaPage, no en el service — ver el
    comentario de _verificar_partido_en_curso). El partido 3 nace
    'Programado' en 05_seed.sql, así que todo test de este archivo que
    registra un evento nuevo necesita este paso primero, igual que el flujo
    real (botón "Empezar Partido" antes de poder cargar nada).

    B.2 (fixes-datos-traspasos-control-mesa-plan.md, D4): "Inicio_Partido"
    ahora exige titulares completos en ambos equipos — `convocar_titulares`
    (conftest.py) completa el roster/convocatoria de este partido antes de
    intentarlo, no es el foco de los tests de este archivo."""
    await convocar_titulares(partido_id)
    resp = await client.post(
        f"/api/v1/partidos/{partido_id}/hitos", json={"tipo_hito": "Inicio_Partido"}, headers=headers
    )
    assert resp.status_code == 201, resp.text


async def test_registrar_gol_valido(client: AsyncClient, arbitro_headers: dict[str, str], convocar_titulares):
    # Partido 3 (05_seed.sql): torneo 1, Halcones(3) vs Tiburones(1), sin
    # eventos aún. Andrés Vera (jugador 5) pertenece al equipo 3 desde
    # 2026-01-01 (jugador_equipo), fecha del partido 2026-01-29.
    await _empezar_partido(client, arbitro_headers, convocar_titulares)
    resp = await client.post(
        "/api/v1/eventos-partido",
        json={
            "partidos_id": 3,
            "jugador_id": 5,
            "equipo_id": 3,
            "eventos_id": 1,  # Gol
            "minuto": 30,
        },
        headers=arbitro_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["estado"] == "Registrado"


async def test_jugador_ajeno_al_equipo_es_rechazado(
    client: AsyncClient, arbitro_headers: dict[str, str], convocar_titulares
):
    # fn_validar_jugador_partido (06_triggers.sql): Carlos Pérez (jugador 1)
    # pertenece al equipo 1, no al 3.
    await _empezar_partido(client, arbitro_headers, convocar_titulares)
    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 1, "equipo_id": 3, "eventos_id": 1, "minuto": 40},
        headers=arbitro_headers,
    )
    assert resp.status_code == 400


async def test_minuto_fuera_de_rango_es_rechazado(
    client: AsyncClient, arbitro_headers: dict[str, str], convocar_titulares
):
    await _empezar_partido(client, arbitro_headers, convocar_titulares)
    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": 1, "minuto": 200},
        headers=arbitro_headers,
    )
    assert resp.status_code == 422


async def test_anular_evento(client: AsyncClient, arbitro_headers: dict[str, str], convocar_titulares):
    await _empezar_partido(client, arbitro_headers, convocar_titulares)
    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 6, "equipo_id": 3, "eventos_id": 3, "minuto": 60},
        headers=arbitro_headers,
    )
    evento_id = resp.json()["id"]

    resp = await client.post(f"/api/v1/eventos-partido/{evento_id}/anular", headers=arbitro_headers)
    assert resp.status_code == 200
    assert resp.json()["estado"] == "Anulado"


async def test_arbitro_no_asignado_no_puede_registrar_evento(
    client: AsyncClient,
    arbitro_headers: dict[str, str],
    arbitro_no_asignado_headers: dict[str, str],
    convocar_titulares,
):
    # D5/D6 (roles-3-modulos-plan.md, Fase 1): el ownership-check rechaza a
    # un Árbitro válido que no es el asignado al partido 3. "Empezar
    # Partido" lo hace el árbitro asignado (el no asignado no podría ni
    # eso) — el 403 de ownership debe ganarle al guard de estado igual, así
    # que el partido queda 'En curso' antes de este intento.
    await _empezar_partido(client, arbitro_headers, convocar_titulares)
    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": 1, "minuto": 30},
        headers=arbitro_no_asignado_headers,
    )
    assert resp.status_code == 403
    assert "asignado" in resp.json()["detail"].lower()


async def test_arbitro_no_asignado_no_puede_anular_evento(
    client: AsyncClient,
    arbitro_headers: dict[str, str],
    arbitro_no_asignado_headers: dict[str, str],
    convocar_titulares,
):
    # El evento lo carga el árbitro asignado; el intento de anularlo viene
    # de un árbitro distinto, sin asignación al partido 3.
    await _empezar_partido(client, arbitro_headers, convocar_titulares)
    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": 1, "minuto": 15},
        headers=arbitro_headers,
    )
    evento_id = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/eventos-partido/{evento_id}/anular", headers=arbitro_no_asignado_headers
    )
    assert resp.status_code == 403
    assert "asignado" in resp.json()["detail"].lower()


async def test_torneo_admin_sin_asignacion_no_puede_registrar_ni_anular_evento(
    client: AsyncClient,
    torneo_admin_con_torneo_headers: dict[str, str],
    torneo_admin_headers: dict[str, str],
    convocar_titulares,
):
    """rbac-licencias-torneos-plan.md, Fase 2 — distinto del
    ownership-check de Árbitro (D5): acá el chequeo es de TorneoAdmin
    contra ASIGNACION_TORNEO_ADMIN, resuelto vía partidos_id -> Partido.torneo_id."""
    await _empezar_partido(client, torneo_admin_con_torneo_headers, convocar_titulares)
    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": 1, "minuto": 20},
        headers=torneo_admin_headers,
    )
    assert resp.status_code == 403
    assert "asignado" in resp.json()["detail"]

    # Evento real lo carga la cuenta asignada, para probar anular contra ella.
    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": 1, "minuto": 21},
        headers=torneo_admin_con_torneo_headers,
    )
    evento_id = resp.json()["id"]

    resp = await client.post(f"/api/v1/eventos-partido/{evento_id}/anular", headers=torneo_admin_headers)
    assert resp.status_code == 403


async def test_torneo_admin_puede_registrar_y_anular_evento(
    client: AsyncClient, torneo_admin_con_torneo_headers: dict[str, str], convocar_titulares
):
    # TorneoAdmin no pasa por el ownership-check de Árbitro (D5) — pero SÍ
    # necesita asignación al torneo del partido (rbac-licencias-torneos-plan.md,
    # Fase 2) — torneo_admin_con_torneo_headers está asignado al Torneo 1
    # (partido 3 pertenece a ese torneo, 05_seed.sql).
    await _empezar_partido(client, torneo_admin_con_torneo_headers, convocar_titulares)
    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": 1, "minuto": 45},
        headers=torneo_admin_con_torneo_headers,
    )
    assert resp.status_code == 201, resp.text
    evento_id = resp.json()["id"]

    resp = await client.post(
        f"/api/v1/eventos-partido/{evento_id}/anular", headers=torneo_admin_con_torneo_headers
    )
    assert resp.status_code == 200
    assert resp.json()["estado"] == "Anulado"


async def test_registrar_evento_en_partido_programado_es_rechazado(
    client: AsyncClient, arbitro_headers: dict[str, str]
):
    """3A-8: sin "Empezar Partido" primero, el partido 3 sigue 'Programado'
    (05_seed.sql) — el guard nuevo debe rechazar el alta ANTES de tocar
    fn_validar_jugador_partido, no solo confiar en el filtro de la UI."""
    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": 1, "minuto": 30},
        headers=arbitro_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "en curso" in resp.json()["detail"].lower()


async def test_registrar_evento_en_partido_finalizado_es_rechazado(
    client: AsyncClient, db_session: AsyncSession, torneo_admin_con_torneo_headers: dict[str, str]
):
    """Alta NUEVA sigue bloqueada incluso después de Finalizado — distinto
    de corregir_minuto/anular sobre un evento YA cargado (EC-15), que este
    test no toca.

    modo-vivo-sustituciones-cierre-plan.md (Bloque 0, T1/T14): `estado` ya
    no es un campo aceptado del PATCH — mismo criterio que
    test_motor_formatos.py/test_desempate_manual.py para dejar un partido
    'Finalizado' en un test (setearlo directo en la sesión), no vía API."""
    partido = await db_session.get(Partido, 3)
    partido.estado = "Finalizado"
    await db_session.commit()

    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": 1, "minuto": 30},
        headers=torneo_admin_con_torneo_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "en curso" in resp.json()["detail"].lower()


async def test_segunda_amarilla_en_vivo_autogenera_roja(
    client: AsyncClient, arbitro_headers: dict[str, str], convocar_titulares
):
    """control-mesa-reactividad-playoffs-plan.md, Fase 3 §3 — el mismo
    listener que resultado-directo, pero en el camino EN VIVO
    (EventoPartidoService.create): 2 tarjetas amarillas seguidas para el
    mismo jugador deben autogenerar 1 sola Tarjeta Roja."""
    await _empezar_partido(client, arbitro_headers, convocar_titulares)

    resp1 = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": 3, "minuto": 10},
        headers=arbitro_headers,
    )
    assert resp1.status_code == 201, resp1.text

    resp2 = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": 3, "minuto": 20},
        headers=arbitro_headers,
    )
    assert resp2.status_code == 201, resp2.text

    resp = await client.get("/api/v1/eventos-partido", params={"partidos_id": 3})
    eventos = resp.json()
    amarillas = [e for e in eventos if e["eventos_id"] == 3 and e["jugador_id"] == 5]
    rojas = [e for e in eventos if e["eventos_id"] == 4 and e["jugador_id"] == 5]
    assert len(amarillas) == 2
    assert len(rojas) == 1
    assert rojas[0]["equipo_id"] == 3


# --- A1 (docs/plans/cierre-pendientes-todos-plan.md) --------------------
#
# EventoPartidoService.create() se reestructuró a una sola transacción con
# lock_timeout sobre el `SELECT ... FOR UPDATE` del partido, para cerrar la
# carrera de la doble amarilla simultánea. La contención y el deadlock
# REALES (dos conexiones genuinamente paralelas) se prueban en A3, sobre
# la fixture de A2 — acá se simula el punto exacto donde Postgres los
# levantaría (parcheando `PartidoRepository.get_or_404_bloqueado`), para
# probar de forma determinista la clasificación del error, el reintento y
# el mapeo a 409, sin depender de esa infraestructura todavía inexistente.


async def test_fallo_en_roja_automatica_revierte_tambien_la_segunda_amarilla(
    client: AsyncClient, arbitro_headers: dict[str, str], convocar_titulares, monkeypatch
):
    """REGRESIÓN obligatoria: antes de A1, `EventoPartidoService.create()`
    commiteaba el evento con `self.repo.create()` y DESPUÉS procesaba la
    roja automática con su propio `commit()` aparte — si el segundo commit
    fallaba, la amarilla ya persistida quedaba escrita igual. Ahora todo es
    una sola transacción: si falla el insert de la roja automática, la
    segunda amarilla (que iba en la MISMA transacción) tampoco debe
    persistir."""
    await _empezar_partido(client, arbitro_headers, convocar_titulares)

    resp1 = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": 3, "minuto": 10},
        headers=arbitro_headers,
    )
    assert resp1.status_code == 201, resp1.text

    import app.services.evento_partido as evento_partido_module

    async def _procesar_doble_amarilla_falla(*args, **kwargs):
        raise RuntimeError("fallo forzado — test de atomicidad de A1")

    monkeypatch.setattr(evento_partido_module, "procesar_doble_amarilla", _procesar_doble_amarilla_falla)

    with pytest.raises(RuntimeError):
        await client.post(
            "/api/v1/eventos-partido",
            json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": 3, "minuto": 20},
            headers=arbitro_headers,
        )

    monkeypatch.undo()
    resp = await client.get("/api/v1/eventos-partido", params={"partidos_id": 3})
    amarillas = [e for e in resp.json() if e["eventos_id"] == 3 and e["jugador_id"] == 5]
    # Solo la primera amarilla (commiteada ANTES del monkeypatch) persiste
    # — la segunda, que iba en la misma transacción que la roja fallida,
    # se revierte junto con ella.
    assert len(amarillas) == 1


async def test_contencion_de_lock_devuelve_409_con_codigo_estable(
    client: AsyncClient, arbitro_headers: dict[str, str], convocar_titulares, monkeypatch
):
    """LockNotAvailable/QueryCanceled (lock_timeout agotado) se mapean a
    409 con el código estable `evento_conflicto_concurrente`, SIN
    reintento — ya esperamos lo que había que esperar."""
    await _empezar_partido(client, arbitro_headers, convocar_titulares)

    async def _lock_agotado(self, id_):
        raise OperationalError("SET LOCAL lock_timeout", {}, psycopg_errors.LockNotAvailable("lock timeout"))

    monkeypatch.setattr(PartidoRepository, "get_or_404_bloqueado", _lock_agotado)

    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": 1, "minuto": 30},
        headers=arbitro_headers,
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"] == "evento_conflicto_concurrente"


async def test_deadlock_se_reintenta_una_vez_y_no_duplica_el_evento(
    client: AsyncClient, arbitro_headers: dict[str, str], convocar_titulares, monkeypatch
):
    """DeadlockDetected SÍ se reintenta una vez (defensa en profundidad) —
    el intento completo se rehace desde el lock, así que un evento a medio
    insertar en el intento fallido no debe sobrevivir ni duplicarse."""
    await _empezar_partido(client, arbitro_headers, convocar_titulares)

    original = PartidoRepository.get_or_404_bloqueado
    llamadas = {"n": 0}

    async def _falla_una_vez(self, id_):
        llamadas["n"] += 1
        if llamadas["n"] == 1:
            raise OperationalError("FOR UPDATE", {}, psycopg_errors.DeadlockDetected("simulado"))
        return await original(self, id_)

    monkeypatch.setattr(PartidoRepository, "get_or_404_bloqueado", _falla_una_vez)

    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": 1, "minuto": 30},
        headers=arbitro_headers,
    )
    assert resp.status_code == 201, resp.text
    assert llamadas["n"] == 2

    resp = await client.get("/api/v1/eventos-partido", params={"partidos_id": 3})
    eventos = [e for e in resp.json() if e["jugador_id"] == 5]
    assert len(eventos) == 1


async def test_deadlock_persistente_agota_el_reintento_y_devuelve_409(
    client: AsyncClient, arbitro_headers: dict[str, str], convocar_titulares, monkeypatch
):
    await _empezar_partido(client, arbitro_headers, convocar_titulares)

    async def _siempre_falla(self, id_):
        raise OperationalError("FOR UPDATE", {}, psycopg_errors.DeadlockDetected("simulado"))

    monkeypatch.setattr(PartidoRepository, "get_or_404_bloqueado", _siempre_falla)

    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": 1, "minuto": 30},
        headers=arbitro_headers,
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"] == "evento_conflicto_concurrente"


async def test_anular_toma_lock_solo_si_el_evento_es_una_tarjeta(
    client: AsyncClient, arbitro_headers: dict[str, str], convocar_titulares, monkeypatch
):
    """`anular()` solo necesita el lock del partido cuando el evento
    objetivo es una tarjeta (amarilla o roja) — es la columna que cuenta
    `procesar_doble_amarilla`. Un gol no participa de esa carrera."""
    await _empezar_partido(client, arbitro_headers, convocar_titulares)

    resp_amarilla = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": 3, "minuto": 10},
        headers=arbitro_headers,
    )
    amarilla_id = resp_amarilla.json()["id"]

    resp_gol = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": 1, "minuto": 15},
        headers=arbitro_headers,
    )
    gol_id = resp_gol.json()["id"]

    original = PartidoRepository.get_or_404_bloqueado
    llamadas: list[int] = []

    async def _spy(self, id_):
        llamadas.append(id_)
        return await original(self, id_)

    monkeypatch.setattr(PartidoRepository, "get_or_404_bloqueado", _spy)

    resp = await client.post(f"/api/v1/eventos-partido/{gol_id}/anular", headers=arbitro_headers)
    assert resp.status_code == 200, resp.text
    assert llamadas == []

    resp = await client.post(f"/api/v1/eventos-partido/{amarilla_id}/anular", headers=arbitro_headers)
    assert resp.status_code == 200, resp.text
    assert llamadas == [3]


async def test_espera_larga_de_for_update_se_loguea_con_partido_y_usuario(
    client: AsyncClient, arbitro_headers: dict[str, str], convocar_titulares, monkeypatch, caplog
):
    """El log de contención solo puede dispararse DESPUÉS de que la espera
    termina — acá se fuerza bajando el umbral a 0 para que cualquier
    espera (aunque sea rápida) lo dispare, sin depender de contención real
    de dos conexiones (eso lo prueba A3)."""
    settings = get_settings()
    monkeypatch.setattr(settings, "evento_lock_log_umbral_ms", 0)

    await _empezar_partido(client, arbitro_headers, convocar_titulares)

    with caplog.at_level(logging.WARNING, logger="app.concurrencia"):
        resp = await client.post(
            "/api/v1/eventos-partido",
            json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": 1, "minuto": 30},
            headers=arbitro_headers,
        )
    assert resp.status_code == 201, resp.text
    assert any(
        "Espera larga por FOR UPDATE" in r.getMessage() and "Partido id=3" in r.getMessage()
        for r in caplog.records
    )
