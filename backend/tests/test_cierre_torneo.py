"""Cierre de Fase Regular + Llaves + Playoffs
(docs/plans/cierre-fase-regular-llaves-playoffs-plan.md, Fase F) —
`cerrar_torneo`/`reabrir_torneo`/`estado-fase` a nivel API, mismo patrón
que test_motor_formatos.py (HTTP + un helper directo a la base para
cerrar partidos con un resultado consistente)."""
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


async def _crear_equipos(client: AsyncClient, headers: dict[str, str], cantidad: int, prefijo: str) -> list[int]:
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


async def _crear_torneo(client: AsyncClient, headers: dict[str, str], nombre: str, formato: str, **extra) -> dict:
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
    client: AsyncClient, headers: dict[str, str], n: int, formato: str, nombre: str, **extra
) -> tuple[int, list[int]]:
    torneo = await _crear_torneo(client, headers, nombre, formato=formato, **extra)
    equipo_ids = await _crear_equipos(client, headers, n, prefijo=nombre)
    await _inscribir(client, headers, torneo["id"], equipo_ids)
    return torneo["id"], equipo_ids


async def _finalizar(
    db_session: AsyncSession, partido_id: int, goles: dict[int, int], ganador_desempate_id: int | None = None
) -> None:
    """Cierra un partido directo por ORM, con `goles[equipo_id]` goles
    reales para cada equipo — 0 se omite (0-0 sin eventos es válido)."""
    evento_gol_id = (await db_session.execute(select(Evento.id).where(Evento.nombre == "Gol"))).scalar_one()
    for equipo_id, cantidad in goles.items():
        if cantidad == 0:
            continue
        jugador = Jugador(
            nombre=f"J{equipo_id}", cedula=f"CEDCT{equipo_id}-{partido_id}", correo_electronico=f"ct{equipo_id}{partido_id}@test.com"
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
        for minuto in range(cantidad):
            db_session.add(
                EventoPartido(
                    partidos_id=partido_id, jugador_id=jugador.id, equipo_id=equipo_id, eventos_id=evento_gol_id, minuto=minuto + 1
                )
            )
        await db_session.flush()
    partido = await db_session.get(Partido, partido_id)
    partido.estado = "Finalizado"
    if ganador_desempate_id is not None:
        partido.ganador_desempate_id = ganador_desempate_id
    await db_session.commit()


async def _partidos_de(client: AsyncClient, headers: dict[str, str], torneo_id: int) -> list[dict]:
    resp = await client.get("/api/v1/partidos", params={"torneo_id": torneo_id}, headers=headers)
    assert resp.status_code == 200
    return resp.json()


# ---------- Liga: podio por tabla ----------


async def test_cerrar_liga_corona_por_tabla(client: AsyncClient, torneo_admin_headers: dict[str, str], db_session: AsyncSession):
    torneo_id, equipos = await _torneo_con_equipos(client, torneo_admin_headers, 3, "Liga", "Liga Cierre")
    resp = await client.post(f"/api/v1/torneos/{torneo_id}/fixture", headers=torneo_admin_headers)
    assert resp.status_code == 200, resp.text

    a, b, c = equipos
    partidos = await _partidos_de(client, torneo_admin_headers, torneo_id)
    for p in partidos:
        local, visit = p["equipos_id_local"], p["equipos_id_visitante"]
        # `a` gana siempre, `b` le gana a `c` — tabla sin empates: a 6pts, b 3pts, c 0pts.
        if a in (local, visit):
            ganador = a
        else:
            ganador = b
        goles = {local: (1 if local == ganador else 0), visit: (1 if visit == ganador else 0)}
        await _finalizar(db_session, p["id"], goles)

    resp = await client.get(f"/api/v1/torneos/{torneo_id}/estado-fase", headers=torneo_admin_headers)
    assert resp.status_code == 200, resp.text
    estado = resp.json()
    assert estado["fase_completa"] is True
    assert set(estado["acciones_disponibles"]) == {"cerrar_directo", "generar_playoffs"}

    resp = await client.post(f"/api/v1/torneos/{torneo_id}/cerrar", json={}, headers=torneo_admin_headers)
    assert resp.status_code == 200, resp.text
    torneo = resp.json()
    assert torneo["campeon_equipo_id"] == a
    assert torneo["subcampeon_equipo_id"] == b
    assert torneo["tercer_puesto_equipo_id"] == c
    assert torneo["estado"] == "Finalizado"
    assert torneo["fecha_cierre"] is not None


async def test_cerrar_liga_con_empate_sin_orden_es_rechazado(
    client: AsyncClient, torneo_admin_headers: dict[str, str], db_session: AsyncSession
):
    torneo_id, equipos = await _torneo_con_equipos(client, torneo_admin_headers, 3, "Liga", "Liga Empate")
    resp = await client.post(f"/api/v1/torneos/{torneo_id}/fixture", headers=torneo_admin_headers)
    assert resp.status_code == 200

    a, b, c = equipos
    partidos = await _partidos_de(client, torneo_admin_headers, torneo_id)
    for p in partidos:
        local, visit = p["equipos_id_local"], p["equipos_id_visitante"]
        # Todos 0-0: los 3 quedan en 1 punto cada uno — empate real en el podio.
        await _finalizar(db_session, p["id"], {local: 0, visit: 0})

    resp = await client.post(f"/api/v1/torneos/{torneo_id}/cerrar", json={}, headers=torneo_admin_headers)
    assert resp.status_code == 400, resp.text
    assert "empate" in resp.json()["detail"].lower()


async def test_cerrar_liga_con_orden_podio_resuelve_el_empate(
    client: AsyncClient, torneo_admin_headers: dict[str, str], db_session: AsyncSession
):
    torneo_id, equipos = await _torneo_con_equipos(client, torneo_admin_headers, 3, "Liga", "Liga Empate OK")
    resp = await client.post(f"/api/v1/torneos/{torneo_id}/fixture", headers=torneo_admin_headers)
    assert resp.status_code == 200

    a, b, c = equipos
    for p in await _partidos_de(client, torneo_admin_headers, torneo_id):
        local, visit = p["equipos_id_local"], p["equipos_id_visitante"]
        await _finalizar(db_session, p["id"], {local: 0, visit: 0})

    resp = await client.post(
        f"/api/v1/torneos/{torneo_id}/cerrar", json={"orden_podio": [c, b, a]}, headers=torneo_admin_headers
    )
    assert resp.status_code == 200, resp.text
    torneo = resp.json()
    assert torneo["campeon_equipo_id"] == c
    assert torneo["subcampeon_equipo_id"] == b
    assert torneo["tercer_puesto_equipo_id"] == a


async def test_cerrar_liga_equipo_no_empatado_en_orden_podio_es_rechazado(
    client: AsyncClient, torneo_admin_headers: dict[str, str], db_session: AsyncSession
):
    torneo_id, equipos = await _torneo_con_equipos(client, torneo_admin_headers, 3, "Liga", "Liga Orden Invalido")
    resp = await client.post(f"/api/v1/torneos/{torneo_id}/fixture", headers=torneo_admin_headers)
    assert resp.status_code == 200

    a, b, c = equipos
    partidos = await _partidos_de(client, torneo_admin_headers, torneo_id)
    for p in partidos:
        local, visit = p["equipos_id_local"], p["equipos_id_visitante"]
        ganador = a if a in (local, visit) else b
        goles = {local: (1 if local == ganador else 0), visit: (1 if visit == ganador else 0)}
        await _finalizar(db_session, p["id"], goles)

    # a tiene 6pts (sin empate) — pedirle un orden_podio que lo mueve es
    # un intento de reordenar a un equipo que no está empatado con nadie.
    resp = await client.post(
        f"/api/v1/torneos/{torneo_id}/cerrar", json={"orden_podio": [b, a]}, headers=torneo_admin_headers
    )
    assert resp.status_code == 400, resp.text


async def test_cerrar_liga_fase_incompleta_es_rechazado(
    client: AsyncClient, torneo_admin_headers: dict[str, str], db_session: AsyncSession
):
    torneo_id, equipos = await _torneo_con_equipos(client, torneo_admin_headers, 3, "Liga", "Liga Incompleta")
    resp = await client.post(f"/api/v1/torneos/{torneo_id}/fixture", headers=torneo_admin_headers)
    assert resp.status_code == 200
    partidos = await _partidos_de(client, torneo_admin_headers, torneo_id)
    # Deja el primero sin jugar.
    for p in partidos[1:]:
        await _finalizar(db_session, p["id"], {p["equipos_id_local"]: 1, p["equipos_id_visitante"]: 0})

    resp = await client.post(f"/api/v1/torneos/{torneo_id}/cerrar", json={}, headers=torneo_admin_headers)
    assert resp.status_code == 400, resp.text


async def test_cerrar_grupos_playoffs_en_fase_grupos_es_rechazado(
    client: AsyncClient, torneo_admin_headers: dict[str, str], db_session: AsyncSession
):
    """C4/Finding review: la Opción A no existe en Formato Grupos, ni
    siquiera si alguien llama el endpoint a mano."""
    torneo_id, equipos = await _torneo_con_equipos(
        client, torneo_admin_headers, 4, "Grupos_Playoffs", "Grupos Cierre Directo", equipos_por_grupo=2
    )
    resp = await client.post(f"/api/v1/torneos/{torneo_id}/sorteo", json={}, headers=torneo_admin_headers)
    assert resp.status_code == 200, resp.text

    resp = await client.post(f"/api/v1/torneos/{torneo_id}/cerrar", json={}, headers=torneo_admin_headers)
    assert resp.status_code == 400, resp.text


# ---------- Eliminación: podio por bracket ----------


async def test_cerrar_eliminacion_corona_por_bracket_con_tercer_lugar(
    client: AsyncClient, torneo_admin_headers: dict[str, str], db_session: AsyncSession
):
    torneo_id, equipos = await _torneo_con_equipos(
        client, torneo_admin_headers, 4, "Eliminacion", "Copa Cierre Bracket"
    )
    resp = await client.post(f"/api/v1/torneos/{torneo_id}/sorteo", json={"semilla": "x"}, headers=torneo_admin_headers)
    assert resp.status_code == 200, resp.text

    resp = await client.get(f"/api/v1/torneos/{torneo_id}/bracket", headers=torneo_admin_headers)
    partidos = resp.json()
    semis = [p for p in partidos if p["ronda_nombre"] == "Semifinal"]
    ganadores, perdedores = [], []
    for semi in semis:
        local, visit = semi["equipos_id_local"], semi["equipos_id_visitante"]
        await _finalizar(db_session, semi["id"], {local: 1, visit: 0})
        ganadores.append(local)
        perdedores.append(visit)

    resp = await client.get(f"/api/v1/torneos/{torneo_id}/bracket", headers=torneo_admin_headers)
    partidos = resp.json()
    final = next(p for p in partidos if p["ronda_nombre"] == "Final")
    tercer_lugar = next(p for p in partidos if p["ronda_nombre"] == "Tercer Lugar")
    assert {final["equipos_id_local"], final["equipos_id_visitante"]} == set(ganadores)
    assert {tercer_lugar["equipos_id_local"], tercer_lugar["equipos_id_visitante"]} == set(perdedores)

    await _finalizar(db_session, final["id"], {final["equipos_id_local"]: 2, final["equipos_id_visitante"]: 1})
    await _finalizar(db_session, tercer_lugar["id"], {tercer_lugar["equipos_id_local"]: 1, tercer_lugar["equipos_id_visitante"]: 0})

    resp = await client.post(f"/api/v1/torneos/{torneo_id}/cerrar", json={}, headers=torneo_admin_headers)
    assert resp.status_code == 200, resp.text
    torneo = resp.json()
    assert torneo["campeon_equipo_id"] == final["equipos_id_local"]
    assert torneo["subcampeon_equipo_id"] == final["equipos_id_visitante"]
    assert torneo["tercer_puesto_equipo_id"] == tercer_lugar["equipos_id_local"]


async def test_cerrar_eliminacion_2_equipos_sin_tercer_puesto(
    client: AsyncClient, torneo_admin_headers: dict[str, str], db_session: AsyncSession
):
    """Premisa corregida #2 del plan: un torneo de 2 equipos no tiene
    tercero — Tercer_Puesto_Equipo_ID queda NULL, no se inventa."""
    torneo_id, equipos = await _torneo_con_equipos(client, torneo_admin_headers, 2, "Eliminacion", "Copa Final Directa Cierre")
    resp = await client.post(f"/api/v1/torneos/{torneo_id}/sorteo", json={}, headers=torneo_admin_headers)
    assert resp.status_code == 200

    resp = await client.get(f"/api/v1/torneos/{torneo_id}/bracket", headers=torneo_admin_headers)
    final = resp.json()[0]
    await _finalizar(db_session, final["id"], {final["equipos_id_local"]: 1, final["equipos_id_visitante"]: 0})

    resp = await client.post(f"/api/v1/torneos/{torneo_id}/cerrar", json={}, headers=torneo_admin_headers)
    assert resp.status_code == 200, resp.text
    torneo = resp.json()
    assert torneo["campeon_equipo_id"] == final["equipos_id_local"]
    assert torneo["tercer_puesto_equipo_id"] is None


async def test_cerrar_dos_veces_es_rechazado(
    client: AsyncClient, torneo_admin_headers: dict[str, str], db_session: AsyncSession
):
    torneo_id, equipos = await _torneo_con_equipos(client, torneo_admin_headers, 2, "Eliminacion", "Copa Doble Cierre")
    resp = await client.post(f"/api/v1/torneos/{torneo_id}/sorteo", json={}, headers=torneo_admin_headers)
    assert resp.status_code == 200
    final = (await client.get(f"/api/v1/torneos/{torneo_id}/bracket", headers=torneo_admin_headers)).json()[0]
    await _finalizar(db_session, final["id"], {final["equipos_id_local"]: 1, final["equipos_id_visitante"]: 0})

    resp = await client.post(f"/api/v1/torneos/{torneo_id}/cerrar", json={}, headers=torneo_admin_headers)
    assert resp.status_code == 200

    resp = await client.post(f"/api/v1/torneos/{torneo_id}/cerrar", json={}, headers=torneo_admin_headers)
    assert resp.status_code == 400, resp.text


# ---------- reabrir_torneo ----------


async def test_reabrir_torneo_limpia_podio_y_permite_volver_a_cerrar(
    client: AsyncClient, torneo_admin_headers: dict[str, str], db_session: AsyncSession
):
    torneo_id, equipos = await _torneo_con_equipos(client, torneo_admin_headers, 2, "Eliminacion", "Copa Reabrir")
    resp = await client.post(f"/api/v1/torneos/{torneo_id}/sorteo", json={}, headers=torneo_admin_headers)
    assert resp.status_code == 200
    final = (await client.get(f"/api/v1/torneos/{torneo_id}/bracket", headers=torneo_admin_headers)).json()[0]
    await _finalizar(db_session, final["id"], {final["equipos_id_local"]: 1, final["equipos_id_visitante"]: 0})

    resp = await client.post(f"/api/v1/torneos/{torneo_id}/cerrar", json={}, headers=torneo_admin_headers)
    assert resp.status_code == 200

    # Escritura bloqueada mientras está cerrado.
    resp = await client.patch(
        f"/api/v1/partidos/{final['id']}", json={"jornada": 1}, headers=torneo_admin_headers
    )
    assert resp.status_code == 400, resp.text

    resp = await client.post(f"/api/v1/torneos/{torneo_id}/reabrir", headers=torneo_admin_headers)
    assert resp.status_code == 200, resp.text
    torneo = resp.json()
    assert torneo["estado"] == "Activo"
    assert torneo["campeon_equipo_id"] is None
    assert torneo["fecha_cierre"] is None

    resp = await client.post(f"/api/v1/torneos/{torneo_id}/cerrar", json={}, headers=torneo_admin_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["campeon_equipo_id"] == final["equipos_id_local"]


async def test_reabrir_torneo_no_cerrado_es_rechazado(client: AsyncClient, torneo_admin_headers: dict[str, str]):
    torneo_id, _ = await _torneo_con_equipos(client, torneo_admin_headers, 2, "Eliminacion", "Copa Sin Cerrar")
    resp = await client.post(f"/api/v1/torneos/{torneo_id}/reabrir", headers=torneo_admin_headers)
    assert resp.status_code == 400, resp.text


# ---------- estado-fase ----------


async def test_estado_fase_sin_partidos_no_ofrece_acciones(client: AsyncClient, torneo_admin_headers: dict[str, str]):
    torneo_id, _ = await _torneo_con_equipos(client, torneo_admin_headers, 3, "Liga", "Liga Sin Fixture")
    resp = await client.get(f"/api/v1/torneos/{torneo_id}/estado-fase", headers=torneo_admin_headers)
    assert resp.status_code == 200
    estado = resp.json()
    assert estado["fase_completa"] is False
    assert estado["acciones_disponibles"] == []
    assert estado["torneo_cerrado"] is False


async def test_estado_fase_eliminacion_completa_solo_ofrece_cerrar_directo(
    client: AsyncClient, torneo_admin_headers: dict[str, str], db_session: AsyncSession
):
    torneo_id, _ = await _torneo_con_equipos(client, torneo_admin_headers, 2, "Eliminacion", "Copa Estado Fase")
    resp = await client.post(f"/api/v1/torneos/{torneo_id}/sorteo", json={}, headers=torneo_admin_headers)
    assert resp.status_code == 200
    final = (await client.get(f"/api/v1/torneos/{torneo_id}/bracket", headers=torneo_admin_headers)).json()[0]
    await _finalizar(db_session, final["id"], {final["equipos_id_local"]: 1, final["equipos_id_visitante"]: 0})

    resp = await client.get(f"/api/v1/torneos/{torneo_id}/estado-fase", headers=torneo_admin_headers)
    estado = resp.json()
    assert estado["fase_completa"] is True
    assert estado["acciones_disponibles"] == ["cerrar_directo"]
