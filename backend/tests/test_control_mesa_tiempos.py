"""Motor de Tiempos + Control de Mesa en vivo
(gestion-avanzada-equipos-control-mesa-plan.md, Fase 3).

05_seed.sql: Torneo 1 (Fútbol) tiene CONFIGURACION_TIEMPO_TORNEO
Periodos/2x45'/15' de descanso. Partido 3 (Halcones vs Tiburones) está
'Programado', sin eventos ni hitos, con el árbitro de prueba asignado vía
la fixture `arbitro_headers`.
"""
from datetime import datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hito_partido import HitoPartido
from app.models.usuario import Usuario


async def test_torneo_nuevo_recibe_config_tiempo_default_por_equipo(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "torneo_grupo_nombre": "Torneo Config Default Equipo",
            "disciplina_id": 1,
            "modalidad_id": 1,  # Fútbol 11, tamano_equipo=11
            "fecha_inicio": "2026-07-01",
            "fecha_fin": "2026-08-01",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    config = resp.json()["config_tiempo"]
    assert config["tipo_cronometro"] == "Periodos"
    assert config["cantidad_periodos"] == 2
    assert config["duracion_periodo_minutos"] == 45


async def test_torneo_nuevo_individual_recibe_config_tiempo_corrido(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    # Copa Raíces / Tenis-Individual no siempre existe en una base recién
    # provisionada solo con 05_seed.sql (10_demo_torneos_admin.sql es
    # aparte) — se crea la disciplina/modalidad individual acá directo,
    # mismo helper que test_equipos.py.
    from app.models.disciplina import Disciplina
    from app.models.modalidad import Modalidad

    d = Disciplina(nombre="Tenis Config Corrido")
    db_session.add(d)
    await db_session.flush()
    m = Modalidad(disciplina_id=d.id, nombre="Individual Config Corrido", tamano_equipo=1)
    db_session.add(m)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/torneos",
        json={
            "torneo_grupo_nombre": "Torneo Config Default Individual",
            "disciplina_id": d.id,
            "modalidad_id": m.id,
            "fecha_inicio": "2026-07-01",
            "fecha_fin": "2026-08-01",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    config = resp.json()["config_tiempo"]
    assert config["tipo_cronometro"] == "Corrido"
    assert config["cantidad_periodos"] is None


async def test_config_tiempo_explicita_al_crear_torneo(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "torneo_grupo_nombre": "Torneo Config Explicita",
            "disciplina_id": 1,
            "modalidad_id": 1,
            "fecha_inicio": "2026-07-01",
            "fecha_fin": "2026-08-01",
            "config_tiempo": {
                "tipo_cronometro": "Periodos",
                "cantidad_periodos": 4,
                "duracion_periodo_minutos": 12,
                "duracion_descanso_minutos": 3,
            },
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    config = resp.json()["config_tiempo"]
    assert config["cantidad_periodos"] == 4
    assert config["duracion_periodo_minutos"] == 12


async def test_patch_config_tiempo_de_periodos_a_corrido_limpia_los_campos(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "torneo_grupo_nombre": "Torneo Config Cambia Tipo",
            "disciplina_id": 1,
            "modalidad_id": 1,
            "fecha_inicio": "2026-07-01",
            "fecha_fin": "2026-08-01",
        },
        headers=admin_general_headers,
    )
    torneo_id = resp.json()["id"]
    assert resp.json()["config_tiempo"]["tipo_cronometro"] == "Periodos"

    resp = await client.patch(
        f"/api/v1/torneos/{torneo_id}",
        json={"config_tiempo": {"tipo_cronometro": "Corrido"}},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    config = resp.json()["config_tiempo"]
    assert config["tipo_cronometro"] == "Corrido"
    # BaseRepository.save_changes ignora None (PATCH parcial) — este
    # camino usa ConfiguracionTiempoTorneoRepository.reemplazar para poder
    # poner estos dos en NULL de verdad, o el CHECK cruzado los rechaza.
    assert config["cantidad_periodos"] is None
    assert config["duracion_periodo_minutos"] is None


async def test_config_tiempo_periodos_sin_cantidad_es_rechazada(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "torneo_grupo_nombre": "Torneo Config Invalida",
            "disciplina_id": 1,
            "modalidad_id": 1,
            "fecha_inicio": "2026-07-01",
            "fecha_fin": "2026-08-01",
            "config_tiempo": {"tipo_cronometro": "Periodos"},
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 422  # rechazado por Pydantic (coherencia_periodos)


async def test_estado_cronometro_inicial_solo_permite_inicio_partido(
    client: AsyncClient, arbitro_headers: dict[str, str]
):
    resp = await client.get("/api/v1/partidos/3/cronometro", headers=arbitro_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["tipo_cronometro"] == "Periodos"
    assert body["acciones_permitidas"] == ["Inicio_Partido"]
    assert body["partido_iniciado"] is False


async def test_secuencia_completa_de_periodos_sincroniza_estado_del_partido(
    client: AsyncClient, arbitro_headers: dict[str, str]
):
    async def _registrar(tipo_hito: str, **extra) -> dict:
        resp = await client.post(
            "/api/v1/partidos/3/hitos", json={"tipo_hito": tipo_hito, **extra}, headers=arbitro_headers
        )
        assert resp.status_code == 201, resp.text
        return resp.json()

    await _registrar("Inicio_Partido")
    resp = await client.get("/api/v1/partidos/3", headers=arbitro_headers)
    assert resp.json()["estado"] == "En curso"

    # Sin período abierto todavía, "Pausar" no tiene sentido (el reloj del
    # 1er Tiempo recién arranca con Inicio_Periodo) — el diagrama de
    # estados del plan dibuja Pausa/Reanuda como loop DENTRO de Periodo(1),
    # no antes.
    resp = await client.get("/api/v1/partidos/3/cronometro", headers=arbitro_headers)
    assert resp.json()["acciones_permitidas"] == ["Inicio_Periodo"]

    await _registrar("Inicio_Periodo", numero_periodo=1)
    resp = await client.get("/api/v1/partidos/3/cronometro", headers=arbitro_headers)
    assert set(resp.json()["acciones_permitidas"]) == {"Pausa", "Fin_Periodo"}

    await _registrar("Pausa")
    resp = await client.get("/api/v1/partidos/3/cronometro", headers=arbitro_headers)
    assert "Reanudacion" in resp.json()["acciones_permitidas"]
    assert "Pausa" not in resp.json()["acciones_permitidas"]

    await _registrar("Reanudacion")
    await _registrar("Fin_Periodo", numero_periodo=1)
    resp = await client.get("/api/v1/partidos/3/cronometro", headers=arbitro_headers)
    assert set(resp.json()["acciones_permitidas"]) == {"Inicio_Periodo"}

    await _registrar("Inicio_Periodo", numero_periodo=2)
    await _registrar("Fin_Periodo", numero_periodo=2)
    resp = await client.get("/api/v1/partidos/3/cronometro", headers=arbitro_headers)
    assert "Fin_Partido" in resp.json()["acciones_permitidas"]

    await _registrar("Fin_Partido")
    resp = await client.get("/api/v1/partidos/3", headers=arbitro_headers)
    assert resp.json()["estado"] == "Finalizado"

    resp = await client.get("/api/v1/partidos/3/cronometro", headers=arbitro_headers)
    assert resp.json()["acciones_permitidas"] == []
    assert resp.json()["partido_finalizado"] is True


# EC-9: doble tap del mismo hito — el segundo se rechaza (server-side,
# antes incluso de llegar al trigger de duplicados de la base).
async def test_hito_duplicado_es_rechazado(client: AsyncClient, arbitro_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/partidos/3/hitos", json={"tipo_hito": "Inicio_Partido"}, headers=arbitro_headers
    )
    assert resp.status_code == 201

    resp = await client.post(
        "/api/v1/partidos/3/hitos", json={"tipo_hito": "Inicio_Partido"}, headers=arbitro_headers
    )
    assert resp.status_code == 400


# EC-10/EC-11: Pausar sin haber iniciado / Reanudar sin haber pausado.
async def test_pausar_sin_iniciar_es_rechazado(client: AsyncClient, arbitro_headers: dict[str, str]):
    resp = await client.post("/api/v1/partidos/3/hitos", json={"tipo_hito": "Pausa"}, headers=arbitro_headers)
    assert resp.status_code == 400


async def test_reanudar_sin_pausar_es_rechazado(client: AsyncClient, arbitro_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/partidos/3/hitos", json={"tipo_hito": "Inicio_Partido"}, headers=arbitro_headers
    )
    assert resp.status_code == 201
    resp = await client.post(
        "/api/v1/partidos/3/hitos", json={"tipo_hito": "Reanudacion"}, headers=arbitro_headers
    )
    assert resp.status_code == 400


async def test_corregir_minuto_de_un_hito(client: AsyncClient, arbitro_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/partidos/3/hitos",
        json={"tipo_hito": "Inicio_Partido", "minuto_reloj": 0},
        headers=arbitro_headers,
    )
    hito_id = resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/partidos/3/hitos/{hito_id}", json={"minuto_reloj": 1}, headers=arbitro_headers
    )
    assert resp.status_code == 200
    assert resp.json()["minuto_reloj"] == 1


async def test_arbitro_no_asignado_no_puede_registrar_hito(
    client: AsyncClient, arbitro_no_asignado_headers: dict[str, str]
):
    resp = await client.post(
        "/api/v1/partidos/3/hitos", json={"tipo_hito": "Inicio_Partido"}, headers=arbitro_no_asignado_headers
    )
    assert resp.status_code == 403


# vw_duracion_partido: con una pausa en el medio, resta el tiempo pausado
# — se insertan los Hitos directo (db_session) para controlar
# Timestamp_Real de verdad, un test vía API con sleeps reales sería lento
# y flaky.
async def test_duracion_partido_resta_el_tiempo_pausado(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    resp = await db_session.execute(text("SELECT id FROM usuarios WHERE username = 'admin_general_test'"))
    usuario_id = resp.scalar_one()

    inicio = datetime(2026, 1, 29, 16, 0, 0)
    for tipo, delta_minutos in [
        ("Inicio_Partido", 0),
        ("Pausa", 10),
        ("Reanudacion", 15),  # 5 minutos pausados
        ("Fin_Partido", 40),
    ]:
        db_session.add(
            HitoPartido(
                partido_id=3,
                tipo_hito=tipo,
                timestamp_real=inicio + timedelta(minutes=delta_minutos),
                registrado_por=usuario_id,
            )
        )
    await db_session.commit()

    resp = await client.get("/api/v1/partidos/3/duracion")
    assert resp.status_code == 200
    body = resp.json()
    # 40 minutos totales - 5 minutos pausados = 35 minutos = 2100 segundos.
    assert body["duracion_segundos"] == 35 * 60


async def test_duracion_partido_sin_finalizar_no_tiene_dato(client: AsyncClient):
    resp = await client.get("/api/v1/partidos/3/duracion")
    assert resp.status_code == 200
    body = resp.json()
    assert body["duracion_segundos"] is None
    assert body["inicio"] is None


# EC-12: finalizar un partido Corrido sin elegir ganador se bloquea
# (fn_validar_ganador_corrido, defensa de última línea).
async def test_finalizar_corrido_sin_ganador_es_rechazado(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    from datetime import date

    from app.models.equipo import Equipo
    from app.models.inscripcion_torneo import InscripcionTorneo
    from app.models.partido import Partido
    from app.models.torneo import Torneo
    from app.models.torneo_grupo import TorneoGrupo

    grupo = TorneoGrupo(nombre="Torneo Corrido Sin Ganador")
    db_session.add(grupo)
    await db_session.flush()
    torneo = Torneo(
        nombre="Torneo Corrido Sin Ganador",
        disciplina_id=1,
        modalidad_id=1,
        torneo_grupo_id=grupo.id,
        numero_edicion=1,
        fecha_inicio=date(2026, 7, 1),
        fecha_fin=date(2026, 8, 1),
    )
    db_session.add(torneo)
    await db_session.flush()
    from app.models.configuracion_tiempo_torneo import ConfiguracionTiempoTorneo

    db_session.add(ConfiguracionTiempoTorneo(torneo_id=torneo.id, tipo_cronometro="Corrido"))

    equipo_a = Equipo(nombre="Corrido A", disciplina_id=1, modalidad_id=1)
    equipo_b = Equipo(nombre="Corrido B", disciplina_id=1, modalidad_id=1)
    db_session.add_all([equipo_a, equipo_b])
    await db_session.flush()
    insc_a = InscripcionTorneo(torneo_id=torneo.id, equipo_id=equipo_a.id)
    insc_b = InscripcionTorneo(torneo_id=torneo.id, equipo_id=equipo_b.id)
    db_session.add_all([insc_a, insc_b])
    await db_session.flush()
    partido = Partido(
        torneo_id=torneo.id,
        equipos_id_local=equipo_a.id,
        equipos_id_visitante=equipo_b.id,
        fecha_partido=datetime(2026, 7, 5, 10, 0, 0),
        estado="Programado",
    )
    db_session.add(partido)
    await db_session.commit()

    # Se capturan los IDs como int ANTES de cualquier request que pueda
    # fallar: el 400 esperado abajo hace rollback() sobre esta MISMA
    # sesión (client comparte db_session vía dependency override), y un
    # rollback expira los objetos ORM — tocar equipo_a.id después
    # dispararía un refresh síncrono fuera de un contexto async
    # (MissingGreenlet).
    partido_id, equipo_a_id = partido.id, equipo_a.id

    resp = await client.post(
        f"/api/v1/partidos/{partido_id}/hitos", json={"tipo_hito": "Inicio_Partido"}, headers=admin_general_headers
    )
    assert resp.status_code == 201, resp.text

    resp = await client.post(
        f"/api/v1/partidos/{partido_id}/hitos", json={"tipo_hito": "Fin_Partido"}, headers=admin_general_headers
    )
    assert resp.status_code == 400
    assert "ganador" in resp.json()["detail"].lower()

    resp = await client.post(
        f"/api/v1/partidos/{partido_id}/hitos",
        json={"tipo_hito": "Fin_Partido", "ganador_corrido_id": equipo_a_id},
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text

    # fn_hito_sincroniza_estado_partido corrige PARTIDOS.Estado con un
    # UPDATE crudo (disparado por el trigger, no por el ORM) — el objeto
    # `partido` de este test, creado directo con db_session, se refrescó
    # una vez de más arriba (save_changes del ganador) y quedó en el
    # identity map con el valor de ANTES del Fin_Partido. En producción
    # cada request tiene su propia sesión nueva y esto no aplica; acá,
    # con la sesión compartida del harness de tests, hace falta forzar el
    # re-fetch antes de verificar el estado final.
    db_session.expire_all()

    resp = await client.get(f"/api/v1/partidos/{partido_id}", headers=admin_general_headers)
    assert resp.json()["estado"] == "Finalizado"
    assert resp.json()["ganador_corrido_id"] == equipo_a_id


async def test_patch_eventos_partido_corrige_minuto(client: AsyncClient, arbitro_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": 1, "minuto": 23},
        headers=arbitro_headers,
    )
    assert resp.status_code == 201, resp.text
    evento_id = resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/eventos-partido/{evento_id}", json={"minuto": 32}, headers=arbitro_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["minuto"] == 32


async def test_patch_eventos_partido_arbitro_no_asignado_rechazado(
    client: AsyncClient, arbitro_headers: dict[str, str], arbitro_no_asignado_headers: dict[str, str]
):
    resp = await client.post(
        "/api/v1/eventos-partido",
        json={"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": 1, "minuto": 23},
        headers=arbitro_headers,
    )
    evento_id = resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/eventos-partido/{evento_id}", json={"minuto": 32}, headers=arbitro_no_asignado_headers
    )
    assert resp.status_code == 403
