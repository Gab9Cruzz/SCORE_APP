"""Desempate de eliminatoria: tiempo extra y penales — FASE 2
(docs/plans/desempate-tiempo-extra-penales-plan.md, §13 "Verificación").

Mismos helpers de armado que test_db_triggers_motor_formatos.py
(_crear_torneo_con_equipos, etc.), reescritos acá en vez de importados —
sin precedente en esta suite de importar entre módulos de test (mismo
criterio que test_desempate_manual.py).

Disciplina 1 = Fútbol, Modalidad 1 = Fútbol 11 (05_seed.sql).
"""
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.configuracion_tiempo_torneo import ConfiguracionTiempoTorneo
from app.models.convocado_a_partido import ConvocadoAPartido
from app.models.equipo import Equipo
from app.models.evento import Evento
from app.models.evento_partido import EventoPartido
from app.models.fase import Fase
from app.models.hito_partido import HitoPartido
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
    # PartidoService.registrar_resultado_directo/HitoPartidoService exigen
    # CONFIGURACION_TIEMPO_TORNEO — a diferencia de test_db_triggers_motor_
    # formatos.py (que opera 100% vía db_session, sin pasar por esos
    # servicios), estos tests SÍ pegan contra /resultado-directo y /hitos.
    db_session.add(
        ConfiguracionTiempoTorneo(
            torneo_id=torneo.id, tipo_cronometro="Periodos", cantidad_periodos=2, duracion_periodo_minutos=45
        )
    )
    await db_session.flush()
    return torneo, equipo_ids


async def _registrar_jugador_en_equipo(
    db_session: AsyncSession,
    torneo_id: int,
    equipo_id: int,
    nombre: str,
    cedula: str,
    convocar_a_partido_id: int | None = None,
) -> int:
    """`convocar_a_partido_id` (opcional): además de darlo de alta en el
    roster del torneo, lo marca TITULAR de ese partido puntual —
    HitoPartidoService.registrar exige convocatoria antes de
    Inicio_Partido (gestionar-partido-alineaciones-plan.md, D1); los tests
    que solo operan vía db_session directo (sin pasar por ese servicio)
    no lo necesitan."""
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
    if convocar_a_partido_id is not None:
        db_session.add(ConvocadoAPartido(partido_id=convocar_a_partido_id, jugador_perfil_id=perfil.id, titular=True))
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


async def _armar_partido_unico_1v1(db_session: AsyncSession, nombre: str) -> tuple[Torneo, Partido, dict[int, int]]:
    """Bracket de 2 equipos, `Formato_Eliminatoria='Unico'` — la Final ES
    el único partido (EC-58, tamano < 4)."""
    torneo, equipos = await _crear_torneo_con_equipos(db_session, nombre, 2)
    fase = Fase(torneo_id=torneo.id, nombre="Eliminatoria", tipo="Eliminacion", orden=1, estado="Pendiente")
    db_session.add(fase)
    await db_session.flush()
    usuario = await _crear_usuario_admin(db_session, f"{nombre.lower().replace(' ', '_')}_admin")
    await db_session.commit()

    await MotorFormatosService(db_session).sortear(torneo.id, usuario.id, semilla="fija")

    final = (
        await db_session.execute(select(Partido).where(Partido.fase_id == fase.id, Partido.ronda_nombre == "Final"))
    ).scalar_one()

    # D1 (gestionar-partido-alineaciones-plan.md): 1 titular alcanza para
    # arrancar — sin bajar esto, Inicio_Partido exigiría los 11 de Fútbol 11.
    torneo.minimo_jugadores_para_iniciar = 1
    await db_session.flush()

    jugadores: dict[int, int] = {}
    for equipo_id in equipos:
        jugadores[equipo_id] = await _registrar_jugador_en_equipo(
            db_session, torneo.id, equipo_id, f"Jugador {equipo_id}", f"CEDPEN{equipo_id}", convocar_a_partido_id=final.id
        )
    await db_session.commit()
    return torneo, final, jugadores


async def _armar_llave_2_equipos(
    db_session: AsyncSession, nombre: str, formato_eliminatoria: str = "Ida_Vuelta"
) -> tuple[Torneo, Partido, Partido, dict[int, int]]:
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

    jugadores: dict[int, int] = {}
    for equipo_id in equipos:
        jugadores[equipo_id] = await _registrar_jugador_en_equipo(
            db_session, torneo.id, equipo_id, f"Jugador {equipo_id}", f"CEDLL{equipo_id}"
        )
    await db_session.commit()
    return torneo, ida, vuelta, jugadores


# ------------------------------------------------------------
# D5/§7 — TorneoService: Corrido => Manual (guardas 1 y 2 del plan)
# ------------------------------------------------------------


async def test_torneo_corrido_rechaza_metodo_no_manual_al_crear(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    from app.models.disciplina import Disciplina
    from app.models.modalidad import Modalidad

    d = Disciplina(nombre="Tenis Desempate Test")
    db_session.add(d)
    await db_session.flush()
    m = Modalidad(disciplina_id=d.id, nombre="Individual Desempate Test", tamano_equipo=1)
    db_session.add(m)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/torneos",
        json={
            "torneo_grupo_nombre": "Torneo Corrido Rechaza Penales",
            "disciplina_id": d.id,
            "modalidad_id": m.id,
            "fecha_inicio": "2026-07-01",
            "fecha_fin": "2026-08-01",
            "metodo_desempate_eliminatoria": "Penales_Directo",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "cronómetro corrido" in resp.json()["detail"]


async def test_torneo_update_a_penales_directo_en_corrido_es_rechazado(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    from app.models.disciplina import Disciplina
    from app.models.modalidad import Modalidad

    d = Disciplina(nombre="Ajedrez Desempate Test")
    db_session.add(d)
    await db_session.flush()
    m = Modalidad(disciplina_id=d.id, nombre="Individual Ajedrez Test", tamano_equipo=1)
    db_session.add(m)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/torneos",
        json={
            "torneo_grupo_nombre": "Torneo Corrido Update Rechaza",
            "disciplina_id": d.id,
            "modalidad_id": m.id,
            "fecha_inicio": "2026-07-01",
            "fecha_fin": "2026-08-01",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    torneo_id = resp.json()["id"]
    assert resp.json()["metodo_desempate_eliminatoria"] == "Manual"

    resp = await client.patch(
        f"/api/v1/torneos/{torneo_id}",
        json={"metodo_desempate_eliminatoria": "Penales_Directo"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 400, resp.text


async def test_torneo_update_a_corrido_baja_metodo_a_manual_solo(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    """Dirección inversa (S7/F2): un torneo Periodos con Penales_Directo
    ya elegido, al pasar Tipo_Cronometro a Corrido, se resuelve en Python
    bajando el método a 'Manual' EN SILENCIO — no un 400."""
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "torneo_grupo_nombre": "Torneo Penales A Corrido",
            "disciplina_id": DISCIPLINA_FUTBOL,
            "modalidad_id": MODALIDAD_FUTBOL_11,
            "fecha_inicio": "2026-07-01",
            "fecha_fin": "2026-08-01",
            "metodo_desempate_eliminatoria": "Penales_Directo",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    torneo_id = resp.json()["id"]
    assert resp.json()["metodo_desempate_eliminatoria"] == "Penales_Directo"

    resp = await client.patch(
        f"/api/v1/torneos/{torneo_id}",
        json={"config_tiempo": {"tipo_cronometro": "Corrido"}},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["metodo_desempate_eliminatoria"] == "Manual"


# ------------------------------------------------------------
# SPEC-REVIEW F1 — regresión: el radio Manual de siempre sigue funcionando
# ------------------------------------------------------------


async def test_resultado_directo_manual_sigue_funcionando_post_migracion(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    torneo, final, jugadores = await _armar_partido_unico_1v1(db_session, "RD Manual Post Migracion")
    local_id, visit_id = final.equipos_id_local, final.equipos_id_visitante

    resp = await client.post(
        f"/api/v1/partidos/{final.id}/resultado-directo",
        json={
            "eventos": [
                {"jugador_id": jugadores[local_id], "equipo_id": local_id, "eventos_id": 1, "minuto": 10},
                {"jugador_id": jugadores[visit_id], "equipo_id": visit_id, "eventos_id": 1, "minuto": 50},
            ],
            "ganador_desempate_id": local_id,
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["estado"] == "Finalizado"
    assert body["ganador_desempate_id"] == local_id
    assert body["metodo_desempate"] == "Manual"
    assert body["penales_local"] is None and body["penales_visitante"] is None


async def test_resultado_directo_no_tengo_marcador_cae_a_manual(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """E4: "no tengo el marcador de la tanda" — no manda penales_*, cae a
    Manual con ganador_desempate_id (mismo escape hatch de siempre)."""
    torneo, final, jugadores = await _armar_partido_unico_1v1(db_session, "RD Sin Marcador Tanda")
    local_id, visit_id = final.equipos_id_local, final.equipos_id_visitante

    resp = await client.post(
        f"/api/v1/partidos/{final.id}/resultado-directo",
        json={"eventos": [], "ganador_desempate_id": visit_id},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["metodo_desempate"] == "Manual"
    assert body["ganador_desempate_id"] == visit_id
    assert body["penales_local"] is None


# ------------------------------------------------------------
# D-D4/D3 — la tanda de penales deriva el ganador SIEMPRE del servidor
# ------------------------------------------------------------


async def test_resultado_directo_penales_deriva_ganador_y_metodo(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    torneo, final, jugadores = await _armar_partido_unico_1v1(db_session, "RD Penales Deriva Ganador")
    local_id, visit_id = final.equipos_id_local, final.equipos_id_visitante

    resp = await client.post(
        f"/api/v1/partidos/{final.id}/resultado-directo",
        json={"eventos": [], "penales_local": 4, "penales_visitante": 2},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["metodo_desempate"] == "Penales"
    assert body["penales_local"] == 4 and body["penales_visitante"] == 2
    assert body["ganador_desempate_id"] == local_id, "4>2: el ganador tiene que ser el LOCAL de este partido"


async def test_resultado_directo_penales_ignora_ganador_desempate_id_del_cliente(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """D-D4 (HIGH): aunque el cliente mande un ganador_desempate_id
    equivocado (invertido) junto con la tanda, el servidor lo DERIVA de
    los penales igual — nunca confía en el cálculo del cliente."""
    torneo, final, jugadores = await _armar_partido_unico_1v1(db_session, "RD Penales Ignora Cliente")
    local_id, visit_id = final.equipos_id_local, final.equipos_id_visitante

    resp = await client.post(
        f"/api/v1/partidos/{final.id}/resultado-directo",
        json={
            "eventos": [],
            "penales_local": 1,
            "penales_visitante": 3,
            "ganador_desempate_id": local_id,  # equivocado a propósito: 1 < 3
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ganador_desempate_id"] == visit_id, "el servidor deriva del marcador de la tanda, no del cliente"


async def test_resultado_directo_tanda_empatada_rechazada(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    torneo, final, jugadores = await _armar_partido_unico_1v1(db_session, "RD Tanda Empatada")
    resp = await client.post(
        f"/api/v1/partidos/{final.id}/resultado-directo",
        json={"eventos": [], "penales_local": 3, "penales_visitante": 3},
        headers=admin_general_headers,
    )
    # Rechazado en el schema (Pydantic, 422) — ResultadoDirectoCreate.
    # coherencia_penales corre antes de llegar al servicio/trigger (D-S1).
    assert resp.status_code == 422, resp.text
    assert "empatada" in resp.text


async def test_resultado_directo_tanda_fuera_de_rango_rechazada_por_pydantic(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    torneo, final, jugadores = await _armar_partido_unico_1v1(db_session, "RD Tanda Fuera De Rango")
    resp = await client.post(
        f"/api/v1/partidos/{final.id}/resultado-directo",
        json={"eventos": [], "penales_local": 100, "penales_visitante": 2},
        headers=admin_general_headers,
    )
    assert resp.status_code == 422, resp.text


# ------------------------------------------------------------
# SPEC-REVIEW F9 — checkbox "se jugó prórroga"
# ------------------------------------------------------------


async def test_resultado_directo_prorroga_con_marcador_no_empatado_marca_tiempo_extra(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    torneo, final, jugadores = await _armar_partido_unico_1v1(db_session, "RD Prorroga Tiempo Extra")
    local_id, visit_id = final.equipos_id_local, final.equipos_id_visitante

    resp = await client.post(
        f"/api/v1/partidos/{final.id}/resultado-directo",
        json={
            "eventos": [
                {"jugador_id": jugadores[local_id], "equipo_id": local_id, "eventos_id": 1, "minuto": 10},
                {"jugador_id": jugadores[local_id], "equipo_id": local_id, "eventos_id": 1, "minuto": 100},
            ],
            "hubo_tiempo_extra": True,
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["hubo_tiempo_extra"] is True
    assert body["metodo_desempate"] == "Tiempo_Extra"
    assert body["ganador_desempate_id"] is None, "el marcador ya decide — Ganador_Desempate_ID queda NULL"


async def test_resultado_directo_prorroga_con_marcador_empatado_no_alcanza_solo(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """F9: `hubo_tiempo_extra=True` con el marcador TODAVÍA empatado no
    resuelve nada por sí solo — sigue haciendo falta el desempate real
    (acá, Manual vía ganador_desempate_id)."""
    torneo, final, jugadores = await _armar_partido_unico_1v1(db_session, "RD Prorroga Sigue Empatado")
    local_id, visit_id = final.equipos_id_local, final.equipos_id_visitante

    resp = await client.post(
        f"/api/v1/partidos/{final.id}/resultado-directo",
        json={"eventos": [], "hubo_tiempo_extra": True, "ganador_desempate_id": local_id},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["hubo_tiempo_extra"] is True
    assert body["metodo_desempate"] == "Manual"
    assert body["ganador_desempate_id"] == local_id


# ------------------------------------------------------------
# D4/§6 — el desempate es de la VUELTA (o único), nunca de la IDA
# ------------------------------------------------------------


async def test_trigger_desempate_en_ida_no_permitido(db_session: AsyncSession):
    torneo, ida, vuelta, jugadores = await _armar_llave_2_equipos(db_session, "Llave Desempate En Ida")
    ida.estado = "Finalizado"
    ida.metodo_desempate = "Manual"
    ida.ganador_desempate_id = ida.equipos_id_local
    with pytest.raises(DBAPIError, match="desempate_en_ida_no_permitido"):
        await db_session.commit()
    await db_session.rollback()


# ------------------------------------------------------------
# SPEC-REVIEW S2 — deshacer un cierre forzado limpia las 5 columnas
# ------------------------------------------------------------


async def test_deshacer_fin_forzado_limpia_columnas_desempate(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    torneo, final, jugadores = await _armar_partido_unico_1v1(db_session, "Deshacer Forzado Penales")
    local_id, visit_id = final.equipos_id_local, final.equipos_id_visitante

    resp = await client.post(
        f"/api/v1/partidos/{final.id}/hitos", json={"tipo_hito": "Inicio_Partido"}, headers=admin_general_headers
    )
    assert resp.status_code == 201, resp.text

    resp = await client.post(
        f"/api/v1/partidos/{final.id}/hitos",
        json={
            "tipo_hito": "Fin_Partido",
            "forzado": True,
            "motivo_cierre": "Clima",
            "metodo_desempate": "Penales",
            "penales_local": 5,
            "penales_visitante": 4,
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text

    await db_session.refresh(final)
    assert final.metodo_desempate == "Penales"
    assert final.penales_local == 5
    assert final.ganador_desempate_id == local_id

    resp = await client.post(
        f"/api/v1/partidos/{final.id}/deshacer-cierre-forzado", headers=admin_general_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["estado"] == "En curso"

    await db_session.refresh(final)
    assert final.metodo_desempate is None
    assert final.penales_local is None
    assert final.penales_visitante is None
    assert final.ganador_desempate_id is None
    assert final.hubo_tiempo_extra is False


# ------------------------------------------------------------
# D-D1 — el paso de tanda de penales EN VIVO, fase 2 (no solo carga directa)
# ------------------------------------------------------------


async def test_hito_partido_penales_en_vivo_deriva_ganador(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    torneo, final, jugadores = await _armar_partido_unico_1v1(db_session, "Hito Penales En Vivo")
    local_id, visit_id = final.equipos_id_local, final.equipos_id_visitante
    final_id = final.id  # capturado ANTES de expire_all() más abajo

    resp = await client.post(
        f"/api/v1/partidos/{final.id}/hitos", json={"tipo_hito": "Inicio_Partido"}, headers=admin_general_headers
    )
    assert resp.status_code == 201, resp.text
    resp = await client.post(
        f"/api/v1/partidos/{final.id}/hitos", json={"tipo_hito": "Inicio_Periodo", "numero_periodo": 1}, headers=admin_general_headers
    )
    assert resp.status_code == 201, resp.text
    resp = await client.post(
        f"/api/v1/partidos/{final.id}/hitos", json={"tipo_hito": "Fin_Periodo", "numero_periodo": 1}, headers=admin_general_headers
    )
    assert resp.status_code == 201, resp.text
    resp = await client.post(
        f"/api/v1/partidos/{final.id}/hitos", json={"tipo_hito": "Inicio_Periodo", "numero_periodo": 2}, headers=admin_general_headers
    )
    assert resp.status_code == 201, resp.text
    resp = await client.post(
        f"/api/v1/partidos/{final.id}/hitos", json={"tipo_hito": "Fin_Periodo", "numero_periodo": 2}, headers=admin_general_headers
    )
    assert resp.status_code == 201, resp.text

    resp = await client.post(
        f"/api/v1/partidos/{final.id}/hitos",
        json={"tipo_hito": "Fin_Partido", "metodo_desempate": "Penales", "penales_local": 2, "penales_visitante": 5},
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text

    # fn_hito_sincroniza_estado_partido corre del lado del trigger, sin
    # pasar por el ORM — la instancia `final`, ya en el identity map de
    # `db_session` (misma sesión que usa `client` en este harness de
    # tests), no se entera sola de ese cambio (expire_on_commit=False,
    # db/database.py). Mismo criterio que test_control_mesa_tiempos.py:404.
    db_session.expire_all()

    resp = await client.get(f"/api/v1/partidos/{final_id}")
    body = resp.json()
    assert body["estado"] == "Finalizado"
    assert body["metodo_desempate"] == "Penales"
    assert body["ganador_desempate_id"] == visit_id


# ------------------------------------------------------------
# D6/§8 — snapshot de Metodo_Desempate_Aplicable al arrancar el partido
# ------------------------------------------------------------


async def test_metodo_desempate_aplicable_snapshot_en_inicio_partido(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    torneo, final, jugadores = await _armar_partido_unico_1v1(db_session, "Snapshot Metodo Aplicable")
    torneo.metodo_desempate_eliminatoria = "Penales_Directo"
    await db_session.commit()

    resp = await client.get(f"/api/v1/partidos/{final.id}")
    assert resp.json()["metodo_desempate_aplicable"] is None, "todavía no arrancó"

    resp = await client.post(
        f"/api/v1/partidos/{final.id}/hitos", json={"tipo_hito": "Inicio_Partido"}, headers=admin_general_headers
    )
    assert resp.status_code == 201, resp.text

    resp = await client.get(f"/api/v1/partidos/{final.id}")
    assert resp.json()["metodo_desempate_aplicable"] == "Penales_Directo"

    # Cambiar la regla del torneo DESPUÉS de arrancar no debe afectar a
    # este partido — ya tomó su snapshot (D6/§8).
    torneo.metodo_desempate_eliminatoria = "Manual"
    await db_session.commit()
    resp = await client.get(f"/api/v1/partidos/{final.id}")
    assert resp.json()["metodo_desempate_aplicable"] == "Penales_Directo"


# ------------------------------------------------------------
# Fase 1 (sin migración) — elegible_desempate / goles_previos_global_*
# ------------------------------------------------------------


async def test_elegible_desempate_excluye_la_ida_y_corrido(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    torneo, ida, vuelta, jugadores = await _armar_llave_2_equipos(db_session, "Elegible Desempate Ida Vuelta")

    resp = await client.get(f"/api/v1/partidos/{ida.id}")
    assert resp.json()["elegible_desempate"] is False, "una IDA nunca es elegible (D4/§6)"

    resp = await client.get(f"/api/v1/partidos/{vuelta.id}")
    assert resp.json()["elegible_desempate"] is True


async def test_elegible_desempate_global_previo_cruza_localia_de_la_ida(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """fn_resolver_llave invierte la ida: el LOCAL de la ida juega de
    VISITANTE en la vuelta — `goles_previos_global_*` tiene que reflejar
    esa inversión, no los goles crudos de la ida."""
    torneo, ida, vuelta, jugadores = await _armar_llave_2_equipos(db_session, "Global Previo Cruza Localia")
    local_ida, visit_ida = ida.equipos_id_local, ida.equipos_id_visitante

    await _registrar_goles(db_session, ida.id, jugadores[local_ida], local_ida, 2)
    ida.estado = "Finalizado"
    await db_session.commit()

    resp = await client.get(f"/api/v1/partidos/{vuelta.id}")
    body = resp.json()
    # local_ida es VISITANTE en la vuelta (fn_resolver_llave invierte).
    assert vuelta.equipos_id_visitante == local_ida
    assert body["goles_previos_global_visitante"] == 2
    assert body["goles_previos_global_local"] == 0
