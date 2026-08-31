"""Motor de Formatos de Competición (motor-formatos-plantillas-navegacion-
plan.md, requerimiento #4) — Diagrama de pruebas T33-T51 (lo que corre a
nivel API/servicio; los triggers puros viven en
test_db_triggers_motor_formatos.py).

Disciplina 1 = Fútbol, Modalidad 1 = Fútbol 11 (05_seed.sql) — se reusan
para no tener que armar un catálogo nuevo en cada test.
"""
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evento import Evento
from app.models.evento_partido import EventoPartido
from app.models.inscripcion_torneo import InscripcionTorneo
from app.models.jugador import Jugador
from app.models.jugador_equipo import JugadorEquipo
from app.models.jugador_perfil_disciplina import JugadorPerfilDisciplina
from app.models.partido import Partido

DISCIPLINA_FUTBOL = 1
MODALIDAD_FUTBOL_11 = 1


async def _crear_equipos(client: AsyncClient, headers: dict[str, str], cantidad: int, prefijo: str = "Equipo") -> list[int]:
    ids = []
    for i in range(cantidad):
        resp = await client.post(
            "/api/v1/equipos",
            json={"nombre": f"{prefijo} {i + 1}", "disciplina_id": DISCIPLINA_FUTBOL, "modalidad_id": MODALIDAD_FUTBOL_11},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        ids.append(resp.json()["id"])
    return ids


async def _crear_torneo(
    client: AsyncClient, headers: dict[str, str], nombre: str, formato: str = "Liga", **extra
) -> dict:
    body = {
        "torneo_grupo_nombre": nombre,
        "disciplina_id": DISCIPLINA_FUTBOL,
        "modalidad_id": MODALIDAD_FUTBOL_11,
        "fecha_inicio": "2026-04-01",
        "fecha_fin": "2026-06-30",
        "formato": formato,
        **extra,
    }
    resp = await client.post("/api/v1/torneos", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _inscribir(client: AsyncClient, headers: dict[str, str], torneo_id: int, equipo_ids: list[int]) -> None:
    for equipo_id in equipo_ids:
        resp = await client.post(
            "/api/v1/inscripciones", json={"torneo_id": torneo_id, "equipo_id": equipo_id}, headers=headers
        )
        assert resp.status_code == 201, resp.text


async def _torneo_con_equipos(
    client: AsyncClient, headers: dict[str, str], n: int, formato: str = "Liga", nombre: str = "Torneo Motor", **extra
) -> tuple[int, list[int]]:
    torneo = await _crear_torneo(client, headers, nombre, formato=formato, **extra)
    equipo_ids = await _crear_equipos(client, headers, n, prefijo=nombre)
    await _inscribir(client, headers, torneo["id"], equipo_ids)
    return torneo["id"], equipo_ids


# ---------- T33: coherencia de parámetros según Formato ----------


async def test_crear_torneo_eliminacion_con_parametros_de_liga_es_rechazado(
    client: AsyncClient, torneo_admin_headers: dict[str, str]
):
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "torneo_grupo_nombre": "Copa Rechazada",
            "disciplina_id": DISCIPLINA_FUTBOL,
            "modalidad_id": MODALIDAD_FUTBOL_11,
            "fecha_inicio": "2026-04-01",
            "fecha_fin": "2026-06-30",
            "formato": "Eliminacion",
            "ida_vuelta": True,
        },
        headers=torneo_admin_headers,
    )
    assert resp.status_code == 400, resp.text


async def test_crear_torneo_liga_con_parametros_de_grupos_es_rechazado(
    client: AsyncClient, torneo_admin_headers: dict[str, str]
):
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "torneo_grupo_nombre": "Liga Rechazada",
            "disciplina_id": DISCIPLINA_FUTBOL,
            "modalidad_id": MODALIDAD_FUTBOL_11,
            "fecha_inicio": "2026-04-01",
            "fecha_fin": "2026-06-30",
            "formato": "Liga",
            "equipos_por_grupo": 4,
        },
        headers=torneo_admin_headers,
    )
    assert resp.status_code == 400, resp.text


async def test_crear_torneo_arma_su_fase_inicial_sola(client: AsyncClient, torneo_admin_headers: dict[str, str]):
    torneo = await _crear_torneo(client, torneo_admin_headers, "Torneo Con Fase", formato="Liga")
    resp = await client.get("/api/v1/torneos", params={"torneo_grupo_id": torneo["torneo_grupo_id"]})
    assert resp.status_code == 200


# ---------- T34/T35: Generar Fixture (Liga) ----------


async def test_generar_fixture_liga_par(client: AsyncClient, torneo_admin_headers: dict[str, str]):
    torneo_id, equipos = await _torneo_con_equipos(client, torneo_admin_headers, 4, nombre="Liga Par")
    resp = await client.post(f"/api/v1/torneos/{torneo_id}/fixture", headers=torneo_admin_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["estado"] == "En_Curso"

    resp = await client.get("/api/v1/partidos", params={"torneo_id": torneo_id})
    partidos = resp.json()
    # 4 equipos: 3 jornadas, 2 partidos por jornada = 6 partidos.
    assert len(partidos) == 6
    jornadas = {p["jornada"] for p in partidos}
    assert jornadas == {1, 2, 3}
    # cada equipo juega como máximo 1 vez por jornada
    for j in jornadas:
        de_la_jornada = [p for p in partidos if p["jornada"] == j]
        vistos = [e for p in de_la_jornada for e in (p["equipos_id_local"], p["equipos_id_visitante"])]
        assert len(vistos) == len(set(vistos))


async def test_generar_fixture_liga_impar_tiene_bye_rotativo(
    client: AsyncClient, torneo_admin_headers: dict[str, str]
):
    torneo_id, equipos = await _torneo_con_equipos(client, torneo_admin_headers, 3, nombre="Liga Impar")
    resp = await client.post(f"/api/v1/torneos/{torneo_id}/fixture", headers=torneo_admin_headers)
    assert resp.status_code == 200, resp.text

    resp = await client.get("/api/v1/partidos", params={"torneo_id": torneo_id})
    partidos = resp.json()
    # 3 equipos: 3 jornadas, 1 partido por jornada (uno descansa siempre) = 3.
    assert len(partidos) == 3
    assert {p["jornada"] for p in partidos} == {1, 2, 3}


async def test_generar_fixture_ida_vuelta_duplica_con_local_visitante_invertido(
    client: AsyncClient, torneo_admin_headers: dict[str, str]
):
    torneo_id, equipos = await _torneo_con_equipos(
        client, torneo_admin_headers, 4, nombre="Liga Ida Vuelta", ida_vuelta=True
    )
    resp = await client.post(f"/api/v1/torneos/{torneo_id}/fixture", headers=torneo_admin_headers)
    assert resp.status_code == 200, resp.text

    resp = await client.get("/api/v1/partidos", params={"torneo_id": torneo_id})
    partidos = resp.json()
    assert len(partidos) == 12  # 6 ida + 6 vuelta
    pares_ida = {(p["equipos_id_local"], p["equipos_id_visitante"]) for p in partidos if p["jornada"] <= 3}
    pares_vuelta = {(p["equipos_id_local"], p["equipos_id_visitante"]) for p in partidos if p["jornada"] > 3}
    assert pares_vuelta == {(v, l) for (l, v) in pares_ida}


async def test_generar_fixture_dos_veces_es_rechazado(client: AsyncClient, torneo_admin_headers: dict[str, str]):
    torneo_id, _ = await _torneo_con_equipos(client, torneo_admin_headers, 4, nombre="Liga Doble")
    resp = await client.post(f"/api/v1/torneos/{torneo_id}/fixture", headers=torneo_admin_headers)
    assert resp.status_code == 200
    resp = await client.post(f"/api/v1/torneos/{torneo_id}/fixture", headers=torneo_admin_headers)
    assert resp.status_code == 400


# ---------- T36/T50: Sorteo de bracket (Eliminación) ----------


async def test_sorteo_bracket_con_byes(client: AsyncClient, torneo_admin_headers: dict[str, str]):
    # EC-49: 6 equipos -> bracket de 8, 2 byes avanzan directo a ronda 2.
    torneo_id, equipos = await _torneo_con_equipos(
        client, torneo_admin_headers, 6, formato="Eliminacion", nombre="Copa Byes"
    )
    resp = await client.post(
        f"/api/v1/torneos/{torneo_id}/sorteo", json={"semilla": "test-semilla"}, headers=torneo_admin_headers
    )
    assert resp.status_code == 200, resp.text

    resp = await client.get(f"/api/v1/torneos/{torneo_id}/bracket")
    assert resp.status_code == 200, resp.text
    partidos = resp.json()

    # 2 ronda1 + 2 semifinal + 1 final + 1 tercer lugar = 6.
    assert len(partidos) == 6
    ronda1 = [p for p in partidos if p["ronda_nombre"] == "Cuartos de Final"]
    assert len(ronda1) == 2
    for p in ronda1:
        assert p["equipos_id_local"] is not None and p["equipos_id_visitante"] is not None

    semis = [p for p in partidos if p["ronda_nombre"] == "Semifinal"]
    assert len(semis) == 2
    # exactamente 2 slots de semifinal ya vienen resueltos por un bye (uno
    # de los dos lados con equipo, el otro esperando al ganador de ronda1).
    slots_con_equipo = sum(1 for p in semis for lado in (p["equipos_id_local"], p["equipos_id_visitante"]) if lado is not None)
    assert slots_con_equipo == 2

    final = next(p for p in partidos if p["ronda_nombre"] == "Final")
    assert final["equipos_id_local"] is None and final["equipos_id_visitante"] is None

    tercer_lugar = next(p for p in partidos if p["ronda_nombre"] == "Tercer Lugar")
    assert tercer_lugar["partido_siguiente_id"] is None  # terminal


async def test_sorteo_bracket_2_equipos_sin_tercer_lugar(client: AsyncClient, torneo_admin_headers: dict[str, str]):
    # EC-58: tamano_bracket < 4 -> Incluye_Tercer_Lugar se ignora, sin error.
    torneo_id, equipos = await _torneo_con_equipos(
        client, torneo_admin_headers, 2, formato="Eliminacion", nombre="Copa Final Directa", incluye_tercer_lugar=True
    )
    resp = await client.post(f"/api/v1/torneos/{torneo_id}/sorteo", json={}, headers=torneo_admin_headers)
    assert resp.status_code == 200, resp.text

    resp = await client.get(f"/api/v1/torneos/{torneo_id}/bracket")
    partidos = resp.json()
    assert len(partidos) == 1
    assert partidos[0]["ronda_nombre"] == "Final"
    assert {partidos[0]["equipos_id_local"], partidos[0]["equipos_id_visitante"]} == set(equipos)


# ---------- T43/T44: rehacer sorteo (EC-52) ----------


async def test_rehacer_sorteo_sin_finalizados_regenera(client: AsyncClient, torneo_admin_headers: dict[str, str]):
    torneo_id, equipos = await _torneo_con_equipos(
        client, torneo_admin_headers, 4, formato="Eliminacion", nombre="Copa Rehacer"
    )
    resp = await client.post(f"/api/v1/torneos/{torneo_id}/sorteo", json={}, headers=torneo_admin_headers)
    assert resp.status_code == 200

    resp = await client.post(f"/api/v1/torneos/{torneo_id}/sorteo", json={}, headers=torneo_admin_headers)
    assert resp.status_code == 200, resp.text

    resp = await client.get(f"/api/v1/torneos/{torneo_id}/bracket")
    # 4 equipos, sin byes -> 2 semifinales + 1 final + 1 tercer lugar = 4.
    assert len(resp.json()) == 4


# ---------- T45: bloquear cambio de Formato con partidos ya creados ----------


async def test_cambiar_formato_con_partidos_existentes_es_rechazado(
    client: AsyncClient, torneo_admin_headers: dict[str, str]
):
    torneo_id, _ = await _torneo_con_equipos(client, torneo_admin_headers, 4, nombre="Liga Formato Fijo")
    resp = await client.post(f"/api/v1/torneos/{torneo_id}/fixture", headers=torneo_admin_headers)
    assert resp.status_code == 200

    resp = await client.patch(
        f"/api/v1/torneos/{torneo_id}", json={"formato": "Eliminacion"}, headers=torneo_admin_headers
    )
    assert resp.status_code == 400, resp.text


# ---------- T41/T42/T51: Grupos + Playoffs, de punta a punta ----------


async def _finalizar_con_resultado(
    db_session: AsyncSession, partido_id: int, equipo_ganador_id: int, equipo_perdedor_id: int
) -> None:
    """Registra un jugador de ocasión para cada equipo y cierra el
    partido 1-0 a favor de equipo_ganador_id — sin pasar por
    EventoPartidoService (no hace falta un árbitro asignado para este
    test, solo un resultado consistente que el trigger de propagación
    pueda leer de vw_goles_acreditados)."""
    evento_gol_id = (await db_session.execute(select(Evento.id).where(Evento.nombre == "Gol"))).scalar_one()
    for equipo_id, goles in ((equipo_ganador_id, 1), (equipo_perdedor_id, 0)):
        if goles == 0:
            continue
        jugador = Jugador(nombre=f"J{equipo_id}", cedula=f"CEDG{equipo_id}-{partido_id}", correo_electronico=f"g{equipo_id}{partido_id}@test.com")
        db_session.add(jugador)
        await db_session.flush()
        perfil = JugadorPerfilDisciplina(jugador_id=jugador.id, disciplina_id=DISCIPLINA_FUTBOL)
        db_session.add(perfil)
        await db_session.flush()
        inscripcion = (
            await db_session.execute(
                select(InscripcionTorneo).where(InscripcionTorneo.equipo_id == equipo_id).order_by(InscripcionTorneo.id.desc())
            )
        ).scalars().first()
        db_session.add(
            JugadorEquipo(jugador_perfil_id=perfil.id, inscripcion_torneo_id=inscripcion.id, fecha_inicio="2026-01-01", estado="Activo")
        )
        await db_session.flush()
        db_session.add(
            EventoPartido(partidos_id=partido_id, jugador_id=jugador.id, equipo_id=equipo_id, eventos_id=evento_gol_id, minuto=10)
        )
        await db_session.flush()
    partido = await db_session.get(Partido, partido_id)
    partido.estado = "Finalizado"
    await db_session.commit()


async def test_grupos_playoffs_de_punta_a_punta(client: AsyncClient, torneo_admin_headers: dict[str, str], db_session: AsyncSession):
    """T41 (tabla de posiciones separada por grupo) + T42 (cruce fijo,
    cubierto también a nivel unitario) + T51 (Tercer Lugar también en
    Grupos + Playoffs) — 4 equipos, 2 grupos de 2, 1 clasificado por
    grupo: el caso más chico que igual ejercita el flujo completo."""
    torneo_id, equipos = await _torneo_con_equipos(
        client,
        torneo_admin_headers,
        4,
        formato="Grupos_Playoffs",
        nombre="Mundialito Chico",
        equipos_por_grupo=2,
        clasificados_por_grupo=1,
    )

    resp = await client.post(f"/api/v1/torneos/{torneo_id}/sorteo", json={"semilla": "grupos-fijo"}, headers=torneo_admin_headers)
    assert resp.status_code == 200, resp.text

    resp = await client.get("/api/v1/partidos", params={"torneo_id": torneo_id})
    partidos_grupos = resp.json()
    assert len(partidos_grupos) == 2  # 2 grupos de 2 -> 1 partido cada uno
    grupo_ids = {p["grupo_id"] for p in partidos_grupos}
    assert len(grupo_ids) == 2  # cada partido quedó en un grupo distinto

    ganadores_por_grupo = {}
    for p in partidos_grupos:
        await _finalizar_con_resultado(db_session, p["id"], p["equipos_id_local"], p["equipos_id_visitante"])
        ganadores_por_grupo[p["grupo_id"]] = p["equipos_id_local"]

    # GET /grupos?fase_id= — nombres de grupo para la tabla de posiciones
    # por grupo (EC-54, consumido por EstadisticasDelTorneoPage).
    fase_id = partidos_grupos[0]["fase_id"]
    resp = await client.get("/api/v1/grupos", params={"fase_id": fase_id})
    assert resp.status_code == 200, resp.text
    nombres_grupo = {g["nombre"] for g in resp.json()}
    assert nombres_grupo == {"A", "B"}

    # T41: la tabla de posiciones separa por grupo — cada una tiene 1 solo
    # equipo con PJ=1 (el otro perdió, pero también jugó 1).
    for grupo_id in grupo_ids:
        resp = await client.get(f"/api/v1/estadisticas/torneos/{torneo_id}/posiciones", params={"grupo_id": grupo_id})
        tabla = resp.json()
        assert len(tabla) == 2
        assert all(fila["grupo_id"] == grupo_id for fila in tabla)
        assert tabla[0]["pts"] == 3  # el ganador queda primero

    resp = await client.post(f"/api/v1/torneos/{torneo_id}/playoffs", headers=torneo_admin_headers)
    assert resp.status_code == 200, resp.text

    resp = await client.get(f"/api/v1/torneos/{torneo_id}/bracket")
    bracket = resp.json()
    # 2 clasificados (1 por grupo) -> Final directa, sin Tercer Lugar
    # (tamano_bracket < 4, EC-58) — mismo criterio que T50.
    assert len(bracket) == 1
    assert {bracket[0]["equipos_id_local"], bracket[0]["equipos_id_visitante"]} == set(ganadores_por_grupo.values())
