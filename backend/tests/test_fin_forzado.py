"""Área 4 (modo-vivo-sustituciones-cierre-plan.md, T6/T15/T17): "Fin de
Partido forzado" — override global permitido en CUALQUIER
`acciones_permitidas` mientras el partido esté iniciado y no finalizado,
más el deshacer con ventana de gracia real en el servidor.

No incluye los 2 tests de concurrencia real con 2 transacciones DB
simultáneas (T23/T24 — doble Fin_Partido y crash durante la ventana de
undo) — quedan anotados en TODOS.md como pendientes de infraestructura de
test (requieren 2 sesiones de DB genuinamente paralelas, no 2 llamadas HTTP
secuenciales)."""
from datetime import date, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.configuracion_tiempo_torneo import ConfiguracionTiempoTorneo
from app.models.disciplina import Disciplina
from app.models.equipo import Equipo
from app.models.hito_partido import HitoPartido
from app.models.inscripcion_torneo import InscripcionTorneo
from app.models.modalidad import Modalidad
from app.models.partido import Partido
from app.models.torneo import Torneo
from app.models.torneo_grupo import TorneoGrupo
from tests.test_titulares_inicio_partido import _agregar_jugador_activo, _convocar


async def _armar(db_session: AsyncSession, nombre: str, tipo_cronometro: str = "Corrido") -> dict:
    disciplina = Disciplina(nombre=f"Disc {nombre}")
    db_session.add(disciplina)
    await db_session.flush()
    modalidad = Modalidad(disciplina_id=disciplina.id, nombre=f"Mod {nombre}", tamano_equipo=1)
    db_session.add(modalidad)
    await db_session.flush()
    grupo = TorneoGrupo(nombre=f"Grupo {nombre}")
    db_session.add(grupo)
    await db_session.flush()
    torneo = Torneo(
        nombre=f"Torneo {nombre}", disciplina_id=disciplina.id, modalidad_id=modalidad.id,
        torneo_grupo_id=grupo.id, numero_edicion=1, fecha_inicio=date(2026, 7, 1), fecha_fin=date(2026, 8, 1),
    )
    db_session.add(torneo)
    await db_session.flush()
    if tipo_cronometro == "Corrido":
        db_session.add(ConfiguracionTiempoTorneo(torneo_id=torneo.id, tipo_cronometro="Corrido"))
    else:
        db_session.add(
            ConfiguracionTiempoTorneo(
                torneo_id=torneo.id,
                tipo_cronometro="Periodos",
                cantidad_periodos=2,
                duracion_periodo_minutos=45,
                duracion_descanso_minutos=15,
            )
        )
    eq_l = Equipo(nombre=f"{nombre} L", disciplina_id=disciplina.id, modalidad_id=modalidad.id)
    eq_v = Equipo(nombre=f"{nombre} V", disciplina_id=disciplina.id, modalidad_id=modalidad.id)
    db_session.add_all([eq_l, eq_v])
    await db_session.flush()
    insc_l = InscripcionTorneo(torneo_id=torneo.id, equipo_id=eq_l.id)
    insc_v = InscripcionTorneo(torneo_id=torneo.id, equipo_id=eq_v.id)
    db_session.add_all([insc_l, insc_v])
    await db_session.flush()
    partido = Partido(
        torneo_id=torneo.id, equipos_id_local=eq_l.id, equipos_id_visitante=eq_v.id,
        fecha_partido=datetime(2026, 7, 5, 10, 0, 0), estado="Programado",
    )
    db_session.add(partido)
    await db_session.commit()

    p_l = await _agregar_jugador_activo(db_session, disciplina.id, insc_l.id, f"{nombre}L0")
    p_v = await _agregar_jugador_activo(db_session, disciplina.id, insc_v.id, f"{nombre}V0")
    await _convocar(db_session, partido.id, p_l, titular=True)
    await _convocar(db_session, partido.id, p_v, titular=True)

    return {"partido_id": partido.id, "equipo_local_id": eq_l.id}


async def test_fin_forzado_exige_motivo(client: AsyncClient, db_session: AsyncSession, admin_general_headers):
    ctx = await _armar(db_session, "SinMotivo")
    await client.post(f"/api/v1/partidos/{ctx['partido_id']}/hitos", json={"tipo_hito": "Inicio_Partido"}, headers=admin_general_headers)

    resp = await client.post(
        f"/api/v1/partidos/{ctx['partido_id']}/hitos",
        json={"tipo_hito": "Fin_Partido", "forzado": True},
        headers=admin_general_headers,
    )
    assert resp.status_code == 422, resp.text


async def test_fin_forzado_no_permitido_antes_de_arrancar(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers
):
    ctx = await _armar(db_session, "NoArranco")
    resp = await client.post(
        f"/api/v1/partidos/{ctx['partido_id']}/hitos",
        json={"tipo_hito": "Fin_Partido", "forzado": True, "motivo_cierre": "Incidente"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "arrancó" in resp.json()["detail"]


async def test_fin_forzado_corrido_exige_ganador(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers
):
    """Un cierre forzado no es una excepción a la integridad de datos de un
    torneo Corrido — fn_validar_ganador_corrido igual exige el ganador."""
    ctx = await _armar(db_session, "CorridoGanador", tipo_cronometro="Corrido")
    await client.post(f"/api/v1/partidos/{ctx['partido_id']}/hitos", json={"tipo_hito": "Inicio_Partido"}, headers=admin_general_headers)

    resp = await client.post(
        f"/api/v1/partidos/{ctx['partido_id']}/hitos",
        json={"tipo_hito": "Fin_Partido", "forzado": True, "motivo_cierre": "Clima"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "ganador" in resp.json()["detail"].lower()

    resp = await client.post(
        f"/api/v1/partidos/{ctx['partido_id']}/hitos",
        json={
            "tipo_hito": "Fin_Partido",
            "forzado": True,
            "motivo_cierre": "Clima",
            "ganador_corrido_id": ctx["equipo_local_id"],
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["deshacer_disponible_hasta"] is not None


async def test_fin_forzado_periodos_permitido_en_pleno_primer_tiempo(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers
):
    """El caso central del pedido: cerrar aunque el gate normal
    (`acciones_permitidas`) no incluya Fin_Partido todavía — acá ni
    siquiera arrancó el primer período."""
    ctx = await _armar(db_session, "PeriodosMitad", tipo_cronometro="Periodos")
    pid = ctx["partido_id"]
    await client.post(f"/api/v1/partidos/{pid}/hitos", json={"tipo_hito": "Inicio_Partido"}, headers=admin_general_headers)
    await client.post(
        f"/api/v1/partidos/{pid}/hitos", json={"tipo_hito": "Inicio_Periodo", "numero_periodo": 1}, headers=admin_general_headers
    )

    # El gate normal NO permitiría Fin_Partido acá (falta cerrar el 2do
    # tiempo) — el override sí.
    cronometro = await client.get(f"/api/v1/partidos/{pid}/cronometro")
    assert "Fin_Partido" not in cronometro.json()["acciones_permitidas"]

    resp = await client.post(
        f"/api/v1/partidos/{pid}/hitos",
        json={"tipo_hito": "Fin_Partido", "forzado": True, "motivo_cierre": "Orden_Seguridad"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text

    partido = await client.get(f"/api/v1/partidos/{pid}", headers=admin_general_headers)
    assert partido.json()["estado"] == "Finalizado"


async def test_fin_forzado_motivo_otro_exige_detalle(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers
):
    ctx = await _armar(db_session, "OtroSinDetalle")
    await client.post(f"/api/v1/partidos/{ctx['partido_id']}/hitos", json={"tipo_hito": "Inicio_Partido"}, headers=admin_general_headers)

    resp = await client.post(
        f"/api/v1/partidos/{ctx['partido_id']}/hitos",
        json={"tipo_hito": "Fin_Partido", "forzado": True, "motivo_cierre": "Otro"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 422, resp.text


async def test_deshacer_fuera_de_la_ventana_es_rechazado(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers
):
    """La ventana es server-side, no del cliente (T17) — un Hito con
    Timestamp_Real viejo (simulado acá corrigiéndolo directo en la sesión,
    sin esperar los 5s reales) ya no se puede deshacer."""
    ctx = await _armar(db_session, "VentExp", tipo_cronometro="Periodos")
    pid = ctx["partido_id"]
    await client.post(f"/api/v1/partidos/{pid}/hitos", json={"tipo_hito": "Inicio_Partido"}, headers=admin_general_headers)
    resp = await client.post(
        f"/api/v1/partidos/{pid}/hitos",
        json={"tipo_hito": "Fin_Partido", "forzado": True, "motivo_cierre": "Clima"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text

    # Retrocede el reloj del Hito 30s — más allá de VENTANA_DESHACER_SEGUNDOS.
    from sqlalchemy import select, update

    hito_id = (
        await db_session.execute(
            select(HitoPartido.id).where(HitoPartido.partido_id == pid, HitoPartido.tipo_hito == "Fin_Partido")
        )
    ).scalar_one()
    await db_session.execute(
        update(HitoPartido).where(HitoPartido.id == hito_id).values(timestamp_real=datetime.now() - timedelta(seconds=30))
    )
    await db_session.commit()

    resp = await client.post(f"/api/v1/partidos/{pid}/deshacer-cierre-forzado", headers=admin_general_headers)
    assert resp.status_code == 400, resp.text
    assert "ventana" in resp.json()["detail"].lower()
