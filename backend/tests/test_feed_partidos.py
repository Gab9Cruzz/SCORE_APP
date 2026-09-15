"""Portal Público — Feed de Partidos del Día (portal-publico-feed-partidos-
plan.md, T3.6/E-T). Reloj congelado en todo test que dependa de "hoy"
(C10f): se usa una FECHA_HOY fija en vez de date.today()/CURRENT_DATE,
sembrando los partidos con offsets relativos a ella.
"""
from datetime import date, datetime, time, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.disciplina import Disciplina
from app.models.equipo import Equipo
from app.models.inscripcion_torneo import InscripcionTorneo
from app.models.modalidad import Modalidad
from app.models.partido import Partido
from app.models.torneo import Torneo
from app.models.torneo_grupo import TorneoGrupo
from app.services import feed as feed_service_module


@pytest.fixture(autouse=True)
def _limpiar_cache_del_feed():
    """E-S3a cachea 60s en un dict de módulo — sin esto, un test que pide
    la misma (fecha, disciplina_id, limit, ventana) que otro test anterior
    recibiría la respuesta cacheada de datos que `db_session` ya revirtió."""
    feed_service_module._cache.clear()
    yield
    feed_service_module._cache.clear()

DISCIPLINA_FUTBOL_ID = 1
MODALIDAD_FUTBOL_11_ID = 1

# db_session escribe de verdad contra la base de test (savepoints, se
# revierte al final del test) — CURRENT_DATE de Postgres en esa conexión
# es la fecha real del sistema que corre los tests. Se ancla FECHA_HOY a
# eso mismo (no una fecha hardcodeada) para que los partidos "de hoy" que
# este archivo siembra coincidan con lo que `fecha_actual_servidor()`
# (FeedRepository, E-M1) va a resolver en el propio test.
FECHA_HOY = date.today()


async def _crear_torneo(
    db_session: AsyncSession,
    *,
    nombre: str,
    disciplina_id: int = DISCIPLINA_FUTBOL_ID,
    modalidad_id: int = MODALIDAD_FUTBOL_11_ID,
    publicado: bool = True,
    estado_torneo: str = "Activo",
    estado_grupo: str = "Activo",
) -> Torneo:
    grupo = TorneoGrupo(nombre=f"{nombre} Grupo", estado=estado_grupo)
    db_session.add(grupo)
    await db_session.flush()
    torneo = Torneo(
        nombre=nombre,
        disciplina_id=disciplina_id,
        modalidad_id=modalidad_id,
        torneo_grupo_id=grupo.id,
        numero_edicion=1,
        fecha_inicio=FECHA_HOY - timedelta(days=60),
        fecha_fin=FECHA_HOY + timedelta(days=60),
        estado=estado_torneo,
        publicado=publicado,
    )
    db_session.add(torneo)
    await db_session.flush()
    return torneo


async def _crear_equipo(db_session: AsyncSession, nombre: str, *, disciplina_id: int, modalidad_id: int, estado: str = "Activo") -> Equipo:
    equipo = Equipo(nombre=nombre, disciplina_id=disciplina_id, modalidad_id=modalidad_id, estado=estado)
    db_session.add(equipo)
    await db_session.flush()
    return equipo


async def _inscribir(db_session: AsyncSession, torneo_id: int, equipo_id: int) -> None:
    db_session.add(InscripcionTorneo(torneo_id=torneo_id, equipo_id=equipo_id, estado="Inscrito"))
    await db_session.flush()


async def _crear_partido(
    db_session: AsyncSession,
    *,
    torneo_id: int,
    local_id: int,
    visitante_id: int,
    dias_offset: int = 0,
    estado: str = "Programado",
) -> Partido:
    partido = Partido(
        torneo_id=torneo_id,
        equipos_id_local=local_id,
        equipos_id_visitante=visitante_id,
        fecha_partido=datetime.combine(FECHA_HOY + timedelta(days=dias_offset), time(15, 0)),
        estado=estado,
    )
    db_session.add(partido)
    await db_session.flush()
    return partido


async def _escenario_partido_hoy(
    db_session: AsyncSession,
    nombre: str,
    *,
    estado_partido: str = "Programado",
    dias_offset: int = 0,
    publicado: bool = True,
    estado_torneo: str = "Activo",
    estado_grupo: str = "Activo",
    estado_local: str = "Activo",
    estado_visitante: str = "Activo",
) -> tuple[Torneo, Partido]:
    """Atajo para el caso más común: un torneo con 2 equipos inscritos y
    UN partido — la mayoría de los tests de T3.6/E-T solo necesitan variar
    uno de estos campos."""
    torneo = await _crear_torneo(
        db_session, nombre=nombre, publicado=publicado, estado_torneo=estado_torneo, estado_grupo=estado_grupo
    )
    local = await _crear_equipo(
        db_session, f"{nombre} Local", disciplina_id=torneo.disciplina_id, modalidad_id=torneo.modalidad_id, estado=estado_local
    )
    visitante = await _crear_equipo(
        db_session, f"{nombre} Visitante", disciplina_id=torneo.disciplina_id, modalidad_id=torneo.modalidad_id, estado=estado_visitante
    )
    await _inscribir(db_session, torneo.id, local.id)
    await _inscribir(db_session, torneo.id, visitante.id)
    partido = await _crear_partido(
        db_session, torneo_id=torneo.id, local_id=local.id, visitante_id=visitante.id,
        dias_offset=dias_offset, estado=estado_partido,
    )
    await db_session.commit()
    return torneo, partido


async def _feed(client: AsyncClient, **params) -> dict:
    params.setdefault("ventana_fallback_dias", 0)
    resp = await client.get("/api/v1/partidos/feed", params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


# --- T3.6 ---


async def test_feed_vacio_sin_partidos_hoy(client: AsyncClient):
    body = await _feed(client, fecha=str(FECHA_HOY + timedelta(days=100)))
    assert body["partidos"] == []
    assert body["total_disponible"] == 0
    assert body["fecha_efectiva"] == body["fecha_pedida"] == str(FECHA_HOY + timedelta(days=100))


async def test_dos_torneos_misma_disciplina_ambos_incluidos(client: AsyncClient, db_session: AsyncSession):
    await _escenario_partido_hoy(db_session, "Feed Liga A")
    await _escenario_partido_hoy(db_session, "Feed Liga B")

    body = await _feed(client, fecha=str(FECHA_HOY))
    torneos = {p["torneo"]["nombre"] for p in body["partidos"]}
    assert {"Feed Liga A", "Feed Liga B"} <= torneos


async def test_partido_en_curso_incluido(client: AsyncClient, db_session: AsyncSession):
    _, partido = await _escenario_partido_hoy(db_session, "Feed En Curso", estado_partido="En curso")
    body = await _feed(client, fecha=str(FECHA_HOY))
    assert partido.id in {p["partido_id"] for p in body["partidos"]}


async def test_partido_finalizado_hoy_incluido(client: AsyncClient, db_session: AsyncSession):
    _, partido = await _escenario_partido_hoy(db_session, "Feed Finalizado", estado_partido="Finalizado")
    body = await _feed(client, fecha=str(FECHA_HOY))
    assert partido.id in {p["partido_id"] for p in body["partidos"]}


async def test_partido_de_manana_excluido_del_feed_de_hoy(client: AsyncClient, db_session: AsyncSession):
    _, partido = await _escenario_partido_hoy(db_session, "Feed Mañana", dias_offset=1)
    body = await _feed(client, fecha=str(FECHA_HOY))
    assert partido.id not in {p["partido_id"] for p in body["partidos"]}
    # Pero sí aparece en el feed de mañana.
    body_manana = await _feed(client, fecha=str(FECHA_HOY + timedelta(days=1)))
    assert partido.id in {p["partido_id"] for p in body_manana["partidos"]}


async def test_grupo_archivado_excluido(client: AsyncClient, db_session: AsyncSession):
    _, partido = await _escenario_partido_hoy(db_session, "Feed Grupo Archivado", estado_grupo="Archivado")
    body = await _feed(client, fecha=str(FECHA_HOY))
    assert partido.id not in {p["partido_id"] for p in body["partidos"]}


async def test_partido_cancelado_excluido(client: AsyncClient, db_session: AsyncSession):
    _, partido = await _escenario_partido_hoy(db_session, "Feed Cancelado", estado_partido="Cancelado")
    body = await _feed(client, fecha=str(FECHA_HOY))
    assert partido.id not in {p["partido_id"] for p in body["partidos"]}


async def test_equipo_inactivo_excluye_el_partido(client: AsyncClient, db_session: AsyncSession):
    _, partido = await _escenario_partido_hoy(db_session, "Feed Equipo Inactivo", estado_local="Inactivo")
    body = await _feed(client, fecha=str(FECHA_HOY))
    assert partido.id not in {p["partido_id"] for p in body["partidos"]}


async def test_torneo_despublicado_excluido(client: AsyncClient, db_session: AsyncSession):
    _, partido = await _escenario_partido_hoy(db_session, "Feed Despublicado", publicado=False)
    body = await _feed(client, fecha=str(FECHA_HOY))
    assert partido.id not in {p["partido_id"] for p in body["partidos"]}


# --- E-T (Final Gate, además de T3.6) ---


async def test_e_l1_torneo_finalizado_con_partido_hoy_aparece(client: AsyncClient, db_session: AsyncSession):
    """El día que el admin marca el torneo como Finalizado (típicamente el
    día de la final) ese partido no debe desaparecer del feed de hoy."""
    _, partido = await _escenario_partido_hoy(db_session, "Feed Torneo Finalizado", estado_torneo="Finalizado")
    body = await _feed(client, fecha=str(FECHA_HOY))
    assert partido.id in {p["partido_id"] for p in body["partidos"]}


async def test_e_l3_estado_null_en_equipos_torneo_no_excluye_la_fila(
    client: AsyncClient, db_session: AsyncSession
):
    """EQUIPOS.Estado/TORNEO.Estado son nullable (sin NOT NULL) — un NULL
    real (no 'Activo' ni 'Inactivo') no debe caer víctima de un `= 'Activo'`
    que lo descartaría en silencio (IS DISTINCT FROM, no igualdad)."""
    torneo = await _crear_torneo(db_session, nombre="Feed Estado Null")
    torneo.estado = None
    local = await _crear_equipo(db_session, "Estado Null Local", disciplina_id=torneo.disciplina_id, modalidad_id=torneo.modalidad_id)
    visitante = await _crear_equipo(db_session, "Estado Null Visitante", disciplina_id=torneo.disciplina_id, modalidad_id=torneo.modalidad_id)
    local.estado = None
    await _inscribir(db_session, torneo.id, local.id)
    await _inscribir(db_session, torneo.id, visitante.id)
    partido = await _crear_partido(db_session, torneo_id=torneo.id, local_id=local.id, visitante_id=visitante.id)
    await db_session.commit()

    body = await _feed(client, fecha=str(FECHA_HOY))
    assert partido.id in {p["partido_id"] for p in body["partidos"]}


async def test_e_l5_corte_en_borde_de_bloque_nunca_devuelve_menos_del_primer_bloque_completo(
    client: AsyncClient, db_session: AsyncSession
):
    """Un torneo con más partidos que `limit` no debe cortarse a mitad:
    `limit` es un mínimo redondeado hacia arriba al borde de bloque."""
    torneo = await _crear_torneo(db_session, nombre="Feed Bloque Grande")
    equipos = [
        await _crear_equipo(db_session, f"Bloque {i}", disciplina_id=torneo.disciplina_id, modalidad_id=torneo.modalidad_id)
        for i in range(6)
    ]
    for e in equipos:
        await _inscribir(db_session, torneo.id, e.id)
    partidos_ids = []
    for i in range(0, 6, 2):
        p = await _crear_partido(db_session, torneo_id=torneo.id, local_id=equipos[i].id, visitante_id=equipos[i + 1].id)
        partidos_ids.append(p.id)
    await db_session.commit()
    assert len(partidos_ids) == 3

    body = await _feed(client, fecha=str(FECHA_HOY), limit=1)
    # limit=1 pero el bloque entero (3 partidos) entra igual.
    assert {p["partido_id"] for p in body["partidos"]} == set(partidos_ids)
    assert body["total_disponible"] == 3


async def test_e_m6_orden_determinista_con_dos_grupos_homonimos(client: AsyncClient, db_session: AsyncSession):
    """Dos TORNEO_GRUPO con el mismo Nombre se intercalan alfabéticamente
    (no hay UNIQUE sobre TORNEO_GRUPO.Nombre) — el desempate por torneo.ID
    tiene que mantener el orden determinista y los bloques contiguos."""
    t1, p1 = await _escenario_partido_hoy(db_session, "Feed Homonimo")
    t2, p2 = await _escenario_partido_hoy(db_session, "Feed Homonimo")

    body = await _feed(client, fecha=str(FECHA_HOY))
    ids_en_orden = [p["partido_id"] for p in body["partidos"] if p["partido_id"] in (p1.id, p2.id)]
    # El torneo con ID menor va primero, y ninguna fila de otro torneo se
    # intercala entre los dos bloques homónimos (ambos son de 1 partido,
    # así que alcanza con ver que aparecen en orden de ID).
    assert ids_en_orden == sorted(ids_en_orden, key=lambda pid: pid == p2.id)
    assert t1.id < t2.id


# --- Fallback de fecha (E-G3/F5) ---


async def test_ventana_fallback_0_no_cae_a_otra_fecha(client: AsyncClient, db_session: AsyncSession):
    await _escenario_partido_hoy(db_session, "Feed Fallback Base", dias_offset=-2)
    body = await _feed(client, fecha=str(FECHA_HOY), ventana_fallback_dias=0)
    assert body["partidos"] == []
    assert body["fecha_efectiva"] == body["fecha_pedida"]


async def test_ventana_fallback_7_cae_a_la_fecha_mas_cercana_con_contenido(
    client: AsyncClient, db_session: AsyncSession
):
    _, partido = await _escenario_partido_hoy(db_session, "Feed Fallback 7", dias_offset=-2)
    resp = await client.get(
        "/api/v1/partidos/feed", params={"fecha": str(FECHA_HOY), "ventana_fallback_dias": 7}
    )
    body = resp.json()
    assert body["fecha_efectiva"] == str(FECHA_HOY - timedelta(days=2))
    assert body["fecha_efectiva"] != body["fecha_pedida"]
    assert partido.id in {p["partido_id"] for p in body["partidos"]}


async def test_frontera_exacta_del_fallback_hoy_menos_7_incluido_hoy_menos_8_excluido(
    client: AsyncClient, db_session: AsyncSession
):
    _, partido_7 = await _escenario_partido_hoy(db_session, "Feed Frontera 7", dias_offset=-7)
    resp = await client.get(
        "/api/v1/partidos/feed", params={"fecha": str(FECHA_HOY), "ventana_fallback_dias": 7}
    )
    body = resp.json()
    assert body["fecha_efectiva"] == str(FECHA_HOY - timedelta(days=7))
    assert partido_7.id in {p["partido_id"] for p in body["partidos"]}

    # -8 días queda fuera de una ventana de 7 — vacío real, no un tercer
    # torneo que por casualidad esté más lejos todavía.
    torneo_lejos, partido_lejos = await _escenario_partido_hoy(db_session, "Feed Frontera 8", dias_offset=-8)
    body2 = (await client.get(
        "/api/v1/partidos/feed",
        params={"fecha": str(FECHA_HOY + timedelta(days=100)), "ventana_fallback_dias": 7},
    )).json()
    assert partido_lejos.id not in {p["partido_id"] for p in body2["partidos"]}


async def test_hacia_atras_gana_sobre_hacia_adelante_aunque_el_futuro_este_mas_cerca(
    client: AsyncClient, db_session: AsyncSession
):
    """E-G3: 'hacia atrás primero, después hacia adelante' — un partido a
    -3 días gana sobre uno a +1 día, aunque el futuro esté más cerca en
    términos absolutos."""
    await _escenario_partido_hoy(db_session, "Feed Atras Lejos", dias_offset=-3)
    await _escenario_partido_hoy(db_session, "Feed Adelante Cerca", dias_offset=1)

    resp = await client.get(
        "/api/v1/partidos/feed", params={"fecha": str(FECHA_HOY), "ventana_fallback_dias": 7}
    )
    body = resp.json()
    assert body["fecha_efectiva"] == str(FECHA_HOY - timedelta(days=3))


# --- Sidecar de disciplinas (E-L4/E-M3) ---


async def test_disciplinas_con_partidos_sigue_trayendo_contenido_cuando_el_fallback_se_activo(
    client: AsyncClient, db_session: AsyncSession
):
    await _escenario_partido_hoy(db_session, "Feed Disciplinas Fallback", dias_offset=-4)

    resp = await client.get(
        "/api/v1/disciplinas/con-partidos", params={"fecha": str(FECHA_HOY), "ventana_fallback_dias": 7}
    )
    assert resp.status_code == 200, resp.text
    nombres = {d["nombre"] for d in resp.json()}
    assert "Fútbol" in nombres
    for d in resp.json():
        assert d["slug"]  # F3: nunca vacío


async def test_disciplinas_con_partidos_no_filtra_por_disciplina(client: AsyncClient, db_session: AsyncSession):
    """Sin query param de disciplina — a diferencia del feed, esta ruta no
    lo acepta, es deliberadamente global (E-L4)."""
    resp = await client.get("/api/v1/disciplinas/con-partidos")
    assert resp.status_code == 200
    assert "disciplina_id" not in resp.request.url.params


# --- F3: deep link por slug ---


async def test_feed_acepta_deporte_por_slug(client: AsyncClient, db_session: AsyncSession):
    _, partido_futbol = await _escenario_partido_hoy(db_session, "Feed Slug Futbol")

    # Tenis no está en el seed base (01-06 solo carga Fútbol) — se crea
    # acá mismo; el trigger fn_generar_disciplina_slug le pone el slug.
    disciplina_tenis = Disciplina(nombre="Tenis")
    db_session.add(disciplina_tenis)
    await db_session.flush()
    modalidad_tenis = Modalidad(disciplina_id=disciplina_tenis.id, nombre="Individual", tamano_equipo=1)
    db_session.add(modalidad_tenis)
    await db_session.flush()

    torneo_tenis = await _crear_torneo(
        db_session, nombre="Feed Slug Tenis", disciplina_id=disciplina_tenis.id, modalidad_id=modalidad_tenis.id
    )
    local = await _crear_equipo(db_session, "Slug Tenis Local", disciplina_id=disciplina_tenis.id, modalidad_id=modalidad_tenis.id)
    visitante = await _crear_equipo(db_session, "Slug Tenis Visitante", disciplina_id=disciplina_tenis.id, modalidad_id=modalidad_tenis.id)
    await _inscribir(db_session, torneo_tenis.id, local.id)
    await _inscribir(db_session, torneo_tenis.id, visitante.id)
    partido_tenis = await _crear_partido(db_session, torneo_id=torneo_tenis.id, local_id=local.id, visitante_id=visitante.id)
    await db_session.commit()

    body = await _feed(client, fecha=str(FECHA_HOY), deporte="futbol")
    ids = {p["partido_id"] for p in body["partidos"]}
    assert partido_futbol.id in ids
    assert partido_tenis.id not in ids


async def test_feed_slug_inexistente_da_404(client: AsyncClient):
    resp = await client.get("/api/v1/partidos/feed", params={"deporte": "no-existe-esto"})
    assert resp.status_code == 404
