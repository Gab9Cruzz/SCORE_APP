"""Desempate manual en la tabla de posiciones (3A-12,
docs/plans/cierre-backlog-todos-plan.md — EC-51 de
motor-formatos-plantillas-navegacion-plan.md): "enfrentamiento directo
primero; si persiste el empate, resolución manual del admin". Mismos
helpers de armado que test_motor_formatos.py (_torneo_con_equipos, etc.),
reescritos acá en vez de importados — sin precedente en esta suite de
importar entre módulos de test.

Disciplina 1 = Fútbol, Modalidad 1 = Fútbol 11 (05_seed.sql).
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


async def _crear_equipos(client: AsyncClient, headers: dict[str, str], nombres: list[str]) -> list[int]:
    ids = []
    for nombre in nombres:
        resp = await client.post(
            "/api/v1/equipos",
            json={"nombre": nombre, "disciplina_id": DISCIPLINA_FUTBOL, "modalidad_id": MODALIDAD_FUTBOL_11},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        ids.append(resp.json()["id"])
    return ids


async def _torneo_grupos_de_3(client: AsyncClient, headers: dict[str, str]) -> tuple[int, dict[str, int]]:
    """Alfa/Beta/Charlie, un solo grupo de 3 (round robin: A-B, A-C, B-C)."""
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "torneo_grupo_nombre": "Desempate Manual",
            "disciplina_id": DISCIPLINA_FUTBOL,
            "modalidad_id": MODALIDAD_FUTBOL_11,
            "fecha_inicio": "2026-04-01",
            "fecha_fin": "2026-06-30",
            "formato": "Grupos_Playoffs",
            "equipos_por_grupo": 3,
            "clasificados_por_grupo": 1,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    torneo_id = resp.json()["id"]

    ids = await _crear_equipos(client, headers, ["Alfa", "Beta", "Charlie"])
    equipo_id_por_nombre = dict(zip(["Alfa", "Beta", "Charlie"], ids, strict=True))
    for equipo_id in ids:
        resp = await client.post(
            "/api/v1/inscripciones", json={"torneo_id": torneo_id, "equipo_id": equipo_id}, headers=headers
        )
        assert resp.status_code == 201, resp.text

    resp = await client.post(f"/api/v1/torneos/{torneo_id}/sorteo", json={"semilla": "desempate-fijo"}, headers=headers)
    assert resp.status_code == 200, resp.text

    return torneo_id, equipo_id_por_nombre


async def _finalizar(
    db_session: AsyncSession, partido_id: int, equipo_local_id: int, equipo_visitante_id: int, goles_local: int, goles_visitante: int
) -> None:
    """Cierra un partido con el marcador exacto pedido (a diferencia del
    helper de test_motor_formatos.py, que siempre da 1-0 al ganador) —
    acá hace falta un 0-0 real para armar el empate."""
    evento_gol_id = (await db_session.execute(select(Evento.id).where(Evento.nombre == "Gol"))).scalar_one()
    for equipo_id, goles in ((equipo_local_id, goles_local), (equipo_visitante_id, goles_visitante)):
        for i in range(goles):
            jugador = Jugador(
                nombre=f"J{equipo_id}-{i}",
                cedula=f"CEDDM{equipo_id}-{partido_id}-{i}",
                correo_electronico=f"dm{equipo_id}{partido_id}{i}@test.com",
            )
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
                EventoPartido(partidos_id=partido_id, jugador_id=jugador.id, equipo_id=equipo_id, eventos_id=evento_gol_id, minuto=10 + i)
            )
            await db_session.flush()
    partido = await db_session.get(Partido, partido_id)
    partido.estado = "Finalizado"
    await db_session.commit()


async def test_orden_automatico_desempata_alfabetico_sin_override(
    client: AsyncClient, torneo_admin_headers: dict[str, str], db_session: AsyncSession
):
    """Escenario: Alfa 0-0 Beta, Charlie gana los otros dos 1-0 — Charlie
    queda primero por puntos, Alfa/Beta empatados abajo (mismos PTS/DG/GF)
    y sin ningún orden_manual seteado, el fallback alfabético de
    vw_tabla_posiciones decide: Alfa antes que Beta."""
    torneo_id, equipos = await _torneo_grupos_de_3(client, torneo_admin_headers)

    resp = await client.get("/api/v1/partidos", params={"torneo_id": torneo_id})
    partidos = resp.json()
    assert len(partidos) == 3

    def _partido_entre(a: str, b: str) -> dict:
        ids = {equipos[a], equipos[b]}
        return next(p for p in partidos if {p["equipos_id_local"], p["equipos_id_visitante"]} == ids)

    p_ab = _partido_entre("Alfa", "Beta")
    p_ac = _partido_entre("Alfa", "Charlie")
    p_bc = _partido_entre("Beta", "Charlie")

    await _finalizar(db_session, p_ab["id"], p_ab["equipos_id_local"], p_ab["equipos_id_visitante"], 0, 0)
    # Charlie gana los otros dos, sea local o visitante en cada uno.
    for p in (p_ac, p_bc):
        if p["equipos_id_local"] == equipos["Charlie"]:
            await _finalizar(db_session, p["id"], p["equipos_id_local"], p["equipos_id_visitante"], 1, 0)
        else:
            await _finalizar(db_session, p["id"], p["equipos_id_local"], p["equipos_id_visitante"], 0, 1)

    grupo_id = p_ab["grupo_id"]
    resp = await client.get(f"/api/v1/estadisticas/torneos/{torneo_id}/posiciones", params={"grupo_id": grupo_id})
    tabla = resp.json()
    assert [f["equipo"] for f in tabla] == ["Charlie", "Alfa", "Beta"]
    assert tabla[0]["pts"] == 6
    assert tabla[1]["pts"] == tabla[2]["pts"] == 1
    # Los tres tienen grupo_equipo_id (es una Fase de Grupos) y ninguno
    # tiene override todavía.
    assert all(f["grupo_equipo_id"] is not None for f in tabla)
    assert all(f["orden_manual"] is None for f in tabla)


async def test_definir_orden_manual_desempata_dentro_del_empate_pero_nunca_por_encima_de_mas_puntos(
    client: AsyncClient, torneo_admin_headers: dict[str, str], db_session: AsyncSession
):
    """El corazón de EC-51: el admin puede reordenar Alfa/Beta (empatados)
    entre sí, pero ponerle a Charlie un orden_manual "de último lugar" (99)
    no lo saca del primer puesto — sigue arriba por PTS, el override es
    el desempate de ÚLTIMA instancia, no un ranking absoluto."""
    torneo_id, equipos = await _torneo_grupos_de_3(client, torneo_admin_headers)

    resp = await client.get("/api/v1/partidos", params={"torneo_id": torneo_id})
    partidos = resp.json()

    def _partido_entre(a: str, b: str) -> dict:
        ids = {equipos[a], equipos[b]}
        return next(p for p in partidos if {p["equipos_id_local"], p["equipos_id_visitante"]} == ids)

    p_ab = _partido_entre("Alfa", "Beta")
    p_ac = _partido_entre("Alfa", "Charlie")
    p_bc = _partido_entre("Beta", "Charlie")

    await _finalizar(db_session, p_ab["id"], p_ab["equipos_id_local"], p_ab["equipos_id_visitante"], 0, 0)
    for p in (p_ac, p_bc):
        if p["equipos_id_local"] == equipos["Charlie"]:
            await _finalizar(db_session, p["id"], p["equipos_id_local"], p["equipos_id_visitante"], 1, 0)
        else:
            await _finalizar(db_session, p["id"], p["equipos_id_local"], p["equipos_id_visitante"], 0, 1)

    grupo_id = p_ab["grupo_id"]
    resp = await client.get(f"/api/v1/estadisticas/torneos/{torneo_id}/posiciones", params={"grupo_id": grupo_id})
    grupo_equipo_id_por_equipo = {f["equipo"]: f["grupo_equipo_id"] for f in resp.json()}

    # Beta primero dentro del empate (orden_manual=1), Alfa segundo (=2) —
    # y a Charlie (líder claro por puntos) se le intenta poner último
    # (=99) a propósito, para probar que NO lo degrada.
    resp = await client.patch(
        f"/api/v1/grupos/equipos/{grupo_equipo_id_por_equipo['Beta']}",
        json={"orden_manual": 1},
        headers=torneo_admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["orden_manual"] == 1

    resp = await client.patch(
        f"/api/v1/grupos/equipos/{grupo_equipo_id_por_equipo['Alfa']}",
        json={"orden_manual": 2},
        headers=torneo_admin_headers,
    )
    assert resp.status_code == 200, resp.text

    resp = await client.patch(
        f"/api/v1/grupos/equipos/{grupo_equipo_id_por_equipo['Charlie']}",
        json={"orden_manual": 99},
        headers=torneo_admin_headers,
    )
    assert resp.status_code == 200, resp.text

    resp = await client.get(f"/api/v1/estadisticas/torneos/{torneo_id}/posiciones", params={"grupo_id": grupo_id})
    tabla = resp.json()
    assert [f["equipo"] for f in tabla] == ["Charlie", "Beta", "Alfa"], (
        "Charlie debía seguir primero por puntos pese a orden_manual=99; "
        "Beta/Alfa debían reordenarse ENTRE ELLOS según su orden_manual"
    )


async def test_orden_manual_invalido_o_de_otro_rol_es_rechazado(
    client: AsyncClient, torneo_admin_headers: dict[str, str], arbitro_headers: dict[str, str], db_session: AsyncSession
):
    torneo_id, equipos = await _torneo_grupos_de_3(client, torneo_admin_headers)
    resp = await client.get("/api/v1/partidos", params={"torneo_id": torneo_id})
    partidos = resp.json()
    # Cualquier partido alcanza — solo hace falta un grupo_equipo_id real,
    # pero vw_tabla_posiciones solo lista equipos con algún partido
    # Finalizado (PJ > 0), así que hay que cerrar uno primero.
    p = partidos[0]
    await _finalizar(db_session, p["id"], p["equipos_id_local"], p["equipos_id_visitante"], 0, 0)
    resp = await client.get(
        f"/api/v1/estadisticas/torneos/{torneo_id}/posiciones", params={"grupo_id": p["grupo_id"]}
    )
    grupo_equipo_id = resp.json()[0]["grupo_equipo_id"]

    # 0 o negativo: rechazado por el schema (422), ni siquiera llega a la DB.
    resp = await client.patch(
        f"/api/v1/grupos/equipos/{grupo_equipo_id}", json={"orden_manual": 0}, headers=torneo_admin_headers
    )
    assert resp.status_code == 422

    # Árbitro no puede definir el desempate — es una decisión de admin.
    resp = await client.patch(
        f"/api/v1/grupos/equipos/{grupo_equipo_id}", json={"orden_manual": 1}, headers=arbitro_headers
    )
    assert resp.status_code == 403


async def test_quitar_el_orden_manual_vuelve_al_automatico(
    client: AsyncClient, torneo_admin_headers: dict[str, str], db_session: AsyncSession
):
    torneo_id, equipos = await _torneo_grupos_de_3(client, torneo_admin_headers)
    resp = await client.get("/api/v1/partidos", params={"torneo_id": torneo_id})
    partidos = resp.json()

    def _partido_entre(a: str, b: str) -> dict:
        ids = {equipos[a], equipos[b]}
        return next(p for p in partidos if {p["equipos_id_local"], p["equipos_id_visitante"]} == ids)

    p_ab = _partido_entre("Alfa", "Beta")
    await _finalizar(db_session, p_ab["id"], p_ab["equipos_id_local"], p_ab["equipos_id_visitante"], 0, 0)

    grupo_id = p_ab["grupo_id"]
    resp = await client.get(f"/api/v1/estadisticas/torneos/{torneo_id}/posiciones", params={"grupo_id": grupo_id})
    filas_por_equipo = {f["equipo"]: f for f in resp.json() if f["equipo"] in ("Alfa", "Beta")}

    # Fuerza a Beta primero.
    resp = await client.patch(
        f"/api/v1/grupos/equipos/{filas_por_equipo['Beta']['grupo_equipo_id']}",
        json={"orden_manual": 1},
        headers=torneo_admin_headers,
    )
    assert resp.status_code == 200, resp.text

    resp = await client.get(f"/api/v1/estadisticas/torneos/{torneo_id}/posiciones", params={"grupo_id": grupo_id})
    tabla = [f for f in resp.json() if f["equipo"] in ("Alfa", "Beta")]
    assert [f["equipo"] for f in tabla] == ["Beta", "Alfa"]

    # {"orden_manual": null} explícito saca el override — None es un valor
    # válido, no "no toques nada" (ver GrupoEquipoRepository.set_orden_manual).
    resp = await client.patch(
        f"/api/v1/grupos/equipos/{filas_por_equipo['Beta']['grupo_equipo_id']}",
        json={"orden_manual": None},
        headers=torneo_admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["orden_manual"] is None

    resp = await client.get(f"/api/v1/estadisticas/torneos/{torneo_id}/posiciones", params={"grupo_id": grupo_id})
    tabla = [f for f in resp.json() if f["equipo"] in ("Alfa", "Beta")]
    # Vuelve al fallback alfabético — Alfa antes que Beta.
    assert [f["equipo"] for f in tabla] == ["Alfa", "Beta"]
