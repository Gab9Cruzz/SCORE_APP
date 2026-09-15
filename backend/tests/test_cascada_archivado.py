"""Cascada de archivado de torneos (cascada-archivado-alineaciones-
traspasos-plan.md, Área 1). Extiende 3B-7 (que solo ocultaba el propio
TORNEO_GRUPO de /torneo-grupos, ver test_torneo_grupos.py): archivar un
grupo ahora también saca sus ediciones del listado general de /torneos y
sus partidos 'Programado' del de /partidos — salvo acceso directo/scoped
(P6), que sigue funcionando igual que ya lo hace /torneo-grupos/{id}.
"""
from datetime import datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.partido import Partido

DISCIPLINA_FUTBOL_ID = 1
MODALIDAD_FUTBOL_11_ID = 1


async def _crear_torneo(client: AsyncClient, headers: dict[str, str], nombre: str) -> dict:
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "disciplina_id": DISCIPLINA_FUTBOL_ID,
            "modalidad_id": MODALIDAD_FUTBOL_11_ID,
            "torneo_grupo_nombre": nombre,
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-06-01",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _archivar(client: AsyncClient, headers: dict[str, str], grupo_id: int) -> None:
    resp = await client.patch(
        f"/api/v1/torneo-grupos/{grupo_id}", json={"estado": "Archivado"}, headers=headers
    )
    assert resp.status_code == 200, resp.text


async def test_grupo_archivado_excluye_su_edicion_del_listado_general(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    torneo = await _crear_torneo(client, admin_general_headers, "Grupo Archivado Torneos")
    await _archivar(client, admin_general_headers, torneo["torneo_grupo_id"])

    resp = await client.get("/api/v1/torneos")
    assert resp.status_code == 200
    ids = {t["id"] for t in resp.json()}
    assert torneo["id"] not in ids


async def test_grupo_archivado_sigue_apareciendo_con_torneo_grupo_id_explicito(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    """P6/EC-A5: el selector de Estadísticas de un torneo ya abierto
    (GET /torneos?torneo_grupo_id=X) no debe romperse si el admin navega
    directo a la edición de un grupo que se archivó mientras tanto."""
    torneo = await _crear_torneo(client, admin_general_headers, "Grupo Archivado Scoped")
    grupo_id = torneo["torneo_grupo_id"]
    await _archivar(client, admin_general_headers, grupo_id)

    # Con headers (portal-publico-feed-partidos-plan.md, E-M2): el torneo
    # nace Publicado=False, así que un chequeo anónimo de "existe y se ve"
    # no aplica acá — lo que este test verifica es el filtro de archivado.
    resp = await client.get(
        "/api/v1/torneos", params={"torneo_grupo_id": grupo_id}, headers=admin_general_headers
    )
    assert resp.status_code == 200
    ids = {t["id"] for t in resp.json()}
    assert torneo["id"] in ids

    # El GET puntual por ID tampoco filtra por archivado — nunca lo hizo,
    # sigue igual (con headers por el mismo motivo que arriba).
    resp = await client.get(f"/api/v1/torneos/{torneo['id']}", headers=admin_general_headers)
    assert resp.status_code == 200


async def test_incluir_archivados_true_trae_todo(client: AsyncClient, admin_general_headers: dict[str, str]):
    torneo = await _crear_torneo(client, admin_general_headers, "Grupo Incluir Archivados")
    await _archivar(client, admin_general_headers, torneo["torneo_grupo_id"])

    resp = await client.get(
        "/api/v1/torneos", params={"incluir_archivados": True}, headers=admin_general_headers
    )
    assert resp.status_code == 200
    ids = {t["id"] for t in resp.json()}
    assert torneo["id"] in ids


async def test_reactivar_grupo_devuelve_su_edicion_al_listado_general(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    torneo = await _crear_torneo(client, admin_general_headers, "Grupo A Reactivar Torneos")
    grupo_id = torneo["torneo_grupo_id"]
    await _archivar(client, admin_general_headers, grupo_id)

    resp = await client.get("/api/v1/torneos", headers=admin_general_headers)
    assert torneo["id"] not in {t["id"] for t in resp.json()}

    resp = await client.patch(
        f"/api/v1/torneo-grupos/{grupo_id}", json={"estado": "Activo"}, headers=admin_general_headers
    )
    assert resp.status_code == 200, resp.text

    resp = await client.get("/api/v1/torneos", headers=admin_general_headers)
    assert torneo["id"] in {t["id"] for t in resp.json()}


async def test_grupo_activo_no_cambia_comportamiento_de_listado(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    """Regresión: un torneo de un grupo Activo (el caso común) no debe
    verse afectado por el JOIN nuevo."""
    torneo = await _crear_torneo(client, admin_general_headers, "Grupo Activo Sin Cambios")

    resp = await client.get("/api/v1/torneos", headers=admin_general_headers)
    assert resp.status_code == 200
    assert torneo["id"] in {t["id"] for t in resp.json()}


async def test_partido_programado_de_grupo_archivado_excluido_del_listado(
    client: AsyncClient, admin_general_headers: dict[str, str], db_session: AsyncSession
):
    torneo = await _crear_torneo(client, admin_general_headers, "Grupo Archivado Partidos")
    equipo_local = await client.post(
        "/api/v1/equipos",
        json={"nombre": "Local CA", "disciplina_id": DISCIPLINA_FUTBOL_ID, "modalidad_id": MODALIDAD_FUTBOL_11_ID},
        headers=admin_general_headers,
    )
    equipo_visitante = await client.post(
        "/api/v1/equipos",
        json={"nombre": "Visitante CA", "disciplina_id": DISCIPLINA_FUTBOL_ID, "modalidad_id": MODALIDAD_FUTBOL_11_ID},
        headers=admin_general_headers,
    )
    await client.post(
        "/api/v1/inscripciones",
        json={"torneo_id": torneo["id"], "equipo_id": equipo_local.json()["id"]},
        headers=admin_general_headers,
    )
    await client.post(
        "/api/v1/inscripciones",
        json={"torneo_id": torneo["id"], "equipo_id": equipo_visitante.json()["id"]},
        headers=admin_general_headers,
    )
    partido = Partido(
        torneo_id=torneo["id"],
        equipos_id_local=equipo_local.json()["id"],
        equipos_id_visitante=equipo_visitante.json()["id"],
        fecha_partido=datetime(2026, 5, 10, 15, 0, 0),
        estado="Programado",
    )
    db_session.add(partido)
    await db_session.commit()
    await db_session.refresh(partido)

    resp = await client.get(
        "/api/v1/partidos", params={"torneo_id": torneo["id"]}, headers=admin_general_headers
    )
    assert partido.id in {p["id"] for p in resp.json()}

    await _archivar(client, admin_general_headers, torneo["torneo_grupo_id"])

    resp = await client.get(
        "/api/v1/partidos", params={"torneo_id": torneo["id"]}, headers=admin_general_headers
    )
    assert resp.status_code == 200
    assert partido.id not in {p["id"] for p in resp.json()}

    # incluir_archivados=true lo trae de vuelta.
    resp = await client.get(
        "/api/v1/partidos",
        params={"torneo_id": torneo["id"], "incluir_archivados": True},
        headers=admin_general_headers,
    )
    assert partido.id in {p["id"] for p in resp.json()}

    # Reactivar el grupo también lo devuelve, sin dato adicional que migrar.
    await client.patch(
        f"/api/v1/torneo-grupos/{torneo['torneo_grupo_id']}",
        json={"estado": "Activo"},
        headers=admin_general_headers,
    )
    resp = await client.get(
        "/api/v1/partidos", params={"torneo_id": torneo["id"]}, headers=admin_general_headers
    )
    assert partido.id in {p["id"] for p in resp.json()}


async def test_partido_en_curso_de_grupo_archivado_no_se_excluye(
    client: AsyncClient, admin_general_headers: dict[str, str], db_session: AsyncSession
):
    """EC-A4: un partido que ya arrancó cuando su torneo se archiva a
    mitad de camino no debe quedar huérfano sin ninguna pantalla desde
    donde operarlo — solo los 'Programado' se ocultan."""
    torneo = await _crear_torneo(client, admin_general_headers, "Grupo Archivado Partido En Curso")
    equipo_local = await client.post(
        "/api/v1/equipos",
        json={"nombre": "Local EC", "disciplina_id": DISCIPLINA_FUTBOL_ID, "modalidad_id": MODALIDAD_FUTBOL_11_ID},
        headers=admin_general_headers,
    )
    equipo_visitante = await client.post(
        "/api/v1/equipos",
        json={"nombre": "Visitante EC", "disciplina_id": DISCIPLINA_FUTBOL_ID, "modalidad_id": MODALIDAD_FUTBOL_11_ID},
        headers=admin_general_headers,
    )
    await client.post(
        "/api/v1/inscripciones",
        json={"torneo_id": torneo["id"], "equipo_id": equipo_local.json()["id"]},
        headers=admin_general_headers,
    )
    await client.post(
        "/api/v1/inscripciones",
        json={"torneo_id": torneo["id"], "equipo_id": equipo_visitante.json()["id"]},
        headers=admin_general_headers,
    )
    partido = Partido(
        torneo_id=torneo["id"],
        equipos_id_local=equipo_local.json()["id"],
        equipos_id_visitante=equipo_visitante.json()["id"],
        fecha_partido=datetime(2026, 5, 10, 15, 0, 0),
        estado="En curso",
    )
    db_session.add(partido)
    await db_session.commit()
    await db_session.refresh(partido)

    await _archivar(client, admin_general_headers, torneo["torneo_grupo_id"])

    resp = await client.get(
        "/api/v1/partidos", params={"torneo_id": torneo["id"]}, headers=admin_general_headers
    )
    assert resp.status_code == 200
    assert partido.id in {p["id"] for p in resp.json()}


async def test_inicio_partido_de_torneo_archivado_es_rechazado(
    client: AsyncClient, admin_general_headers: dict[str, str], db_session: AsyncSession
):
    """P7: defensa en profundidad — la UI ya oculta estos partidos del
    listado, pero un intento directo por API contra
    POST /partidos/{id}/hitos debe rechazarse igual."""
    torneo = await _crear_torneo(client, admin_general_headers, "Grupo Archivado Inicio Rechazado")
    equipo_local = await client.post(
        "/api/v1/equipos",
        json={"nombre": "Local IR", "disciplina_id": DISCIPLINA_FUTBOL_ID, "modalidad_id": MODALIDAD_FUTBOL_11_ID},
        headers=admin_general_headers,
    )
    equipo_visitante = await client.post(
        "/api/v1/equipos",
        json={"nombre": "Visitante IR", "disciplina_id": DISCIPLINA_FUTBOL_ID, "modalidad_id": MODALIDAD_FUTBOL_11_ID},
        headers=admin_general_headers,
    )
    await client.post(
        "/api/v1/inscripciones",
        json={"torneo_id": torneo["id"], "equipo_id": equipo_local.json()["id"]},
        headers=admin_general_headers,
    )
    await client.post(
        "/api/v1/inscripciones",
        json={"torneo_id": torneo["id"], "equipo_id": equipo_visitante.json()["id"]},
        headers=admin_general_headers,
    )
    partido = Partido(
        torneo_id=torneo["id"],
        equipos_id_local=equipo_local.json()["id"],
        equipos_id_visitante=equipo_visitante.json()["id"],
        fecha_partido=datetime(2026, 5, 10, 15, 0, 0),
        estado="Programado",
    )
    db_session.add(partido)
    await db_session.commit()
    await db_session.refresh(partido)

    await _archivar(client, admin_general_headers, torneo["torneo_grupo_id"])

    resp = await client.post(
        f"/api/v1/partidos/{partido.id}/hitos",
        json={"tipo_hito": "Inicio_Partido"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "archivado" in resp.json()["detail"].lower()


async def test_inicio_partido_de_torneo_no_archivado_sin_cambio(
    client: AsyncClient, admin_general_headers: dict[str, str], db_session: AsyncSession
):
    """Regresión: un torneo de un grupo Activo sigue pudiendo arrancar sus
    partidos con la convocatoria completa — el chequeo nuevo no interfiere
    con el camino feliz ya cubierto por test_titulares_inicio_partido.py."""
    from app.models.convocado_a_partido import ConvocadoAPartido
    from app.models.jugador import Jugador
    from app.models.jugador_equipo import JugadorEquipo
    from app.models.jugador_perfil_disciplina import JugadorPerfilDisciplina

    torneo = await _crear_torneo(client, admin_general_headers, "Grupo Activo Inicio Ok")
    equipo_local = await client.post(
        "/api/v1/equipos",
        json={"nombre": "Local OK", "disciplina_id": DISCIPLINA_FUTBOL_ID, "modalidad_id": MODALIDAD_FUTBOL_11_ID},
        headers=admin_general_headers,
    )
    equipo_visitante = await client.post(
        "/api/v1/equipos",
        json={"nombre": "Visitante OK", "disciplina_id": DISCIPLINA_FUTBOL_ID, "modalidad_id": MODALIDAD_FUTBOL_11_ID},
        headers=admin_general_headers,
    )
    insc_local = await client.post(
        "/api/v1/inscripciones",
        json={"torneo_id": torneo["id"], "equipo_id": equipo_local.json()["id"]},
        headers=admin_general_headers,
    )
    insc_visitante = await client.post(
        "/api/v1/inscripciones",
        json={"torneo_id": torneo["id"], "equipo_id": equipo_visitante.json()["id"]},
        headers=admin_general_headers,
    )
    partido = Partido(
        torneo_id=torneo["id"],
        equipos_id_local=equipo_local.json()["id"],
        equipos_id_visitante=equipo_visitante.json()["id"],
        fecha_partido=datetime(2026, 5, 10, 15, 0, 0),
        estado="Programado",
    )
    db_session.add(partido)
    await db_session.flush()

    for lado, insc_id in (("L", insc_local.json()["id"]), ("V", insc_visitante.json()["id"])):
        for i in range(11):
            jugador = Jugador(
                nombre=f"Jugador {lado}{i} OK",
                cedula=f"7777{lado}{i}",
                correo_electronico=f"jok.{lado}{i}@example.com",
            )
            db_session.add(jugador)
            await db_session.flush()
            perfil = JugadorPerfilDisciplina(jugador_id=jugador.id, disciplina_id=DISCIPLINA_FUTBOL_ID)
            db_session.add(perfil)
            await db_session.flush()
            db_session.add(
                JugadorEquipo(
                    jugador_perfil_id=perfil.id,
                    inscripcion_torneo_id=insc_id,
                    fecha_inicio="2026-01-01",
                    estado="Activo",
                )
            )
            await db_session.flush()
            db_session.add(ConvocadoAPartido(partido_id=partido.id, jugador_perfil_id=perfil.id, titular=True))
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/partidos/{partido.id}/hitos",
        json={"tipo_hito": "Inicio_Partido"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
