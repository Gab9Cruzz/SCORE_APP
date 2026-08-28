"""Equipos — CRUD y las reglas nuevas de
equipos-disciplina-navegacion-plan.md (Disciplina obligatoria, coherencia
disciplina↔modalidad, plantilla derivada, EC-38).

En 05_seed.sql: Disciplina 1 = "Fútbol", Modalidad 1 = "Fútbol 11", y los
3 equipos de prueba pertenecen a esa disciplina.
"""
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.disciplina import Disciplina
from app.models.modalidad import Modalidad

FUTBOL = {"disciplina_id": 1, "modalidad_id": 1}


async def _crear_disciplina_y_modalidad(
    session: AsyncSession, disciplina: str, modalidad: str, tamano_equipo: int = 5
) -> tuple[int, int]:
    d = Disciplina(nombre=disciplina)
    session.add(d)
    await session.flush()
    m = Modalidad(disciplina_id=d.id, nombre=modalidad, tamano_equipo=tamano_equipo)
    session.add(m)
    await session.commit()
    return d.id, m.id


async def test_listar_equipos_es_publico(client: AsyncClient):
    # 05_seed.sql carga 3 equipos.
    resp = await client.get("/api/v1/equipos")
    assert resp.status_code == 200
    assert len(resp.json()) >= 3


async def test_arbitro_no_puede_crear_equipo(client: AsyncClient, arbitro_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/equipos", json={"nombre": "Nuevo FC", **FUTBOL}, headers=arbitro_headers
    )
    assert resp.status_code == 403


async def test_admin_crea_actualiza_y_da_de_baja_equipo(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    resp = await client.post(
        "/api/v1/equipos", json={"nombre": "Nuevo FC", **FUTBOL}, headers=admin_general_headers
    )
    assert resp.status_code == 201, resp.text
    equipo_id = resp.json()["id"]
    assert resp.json()["disciplina_id"] == 1
    assert resp.json()["modalidad_id"] == 1

    resp = await client.patch(
        f"/api/v1/equipos/{equipo_id}",
        json={"nombre": "Nuevo FC Renombrado"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["nombre"] == "Nuevo FC Renombrado"

    resp = await client.delete(f"/api/v1/equipos/{equipo_id}", headers=admin_general_headers)
    assert resp.status_code == 200
    assert resp.json()["estado"] == "Inactivo"


# T1 — la Disciplina es obligatoria al crear (pedido A del plan).
async def test_crear_equipo_sin_disciplina_es_rechazado(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    resp = await client.post(
        "/api/v1/equipos", json={"nombre": "Equipo Sin Disciplina"}, headers=admin_general_headers
    )
    assert resp.status_code == 422


# T2 / EC-34 — la modalidad tiene que pertenecer a la disciplina (D-Eng-15).
async def test_ec34_modalidad_de_otra_disciplina_es_rechazada(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    _, modalidad_tenis = await _crear_disciplina_y_modalidad(
        db_session, "Tenis T2", "Singles T2", tamano_equipo=1
    )
    resp = await client.post(
        "/api/v1/equipos",
        json={"nombre": "Equipo Incoherente", "disciplina_id": 1, "modalidad_id": modalidad_tenis},
        headers=admin_general_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "no pertenece" in resp.json()["detail"].lower()


# T3 — los filtros server-side que sostienen la grilla (Mejora #1).
async def test_listar_equipos_filtra_por_disciplina_y_modalidad(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    disciplina_id, modalidad_id = await _crear_disciplina_y_modalidad(
        db_session, "Ajedrez T3", "Blitz T3", tamano_equipo=1
    )
    resp = await client.post(
        "/api/v1/equipos",
        json={"nombre": "Torre Negra", "disciplina_id": disciplina_id, "modalidad_id": modalidad_id},
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text

    resp = await client.get("/api/v1/equipos", params={"disciplina_id": disciplina_id})
    assert resp.status_code == 200
    assert [e["nombre"] for e in resp.json()] == ["Torre Negra"]

    resp = await client.get("/api/v1/equipos", params={"modalidad_id": modalidad_id})
    assert [e["nombre"] for e in resp.json()] == ["Torre Negra"]

    # Los 3 equipos del seed son de Fútbol; el de Ajedrez no debe aparecer.
    resp = await client.get("/api/v1/equipos", params={"disciplina_id": 1})
    assert "Torre Negra" not in [e["nombre"] for e in resp.json()]


# T4 — plantilla_total: perfiles distintos entre TODAS las inscripciones
# del equipo (Decisión #1 = A1, D-Eng-10).
async def test_plantilla_total_cuenta_perfiles_distintos(client: AsyncClient):
    # 05_seed.sql: el equipo 1 tiene 2 jugadores en el torneo 1.
    resp = await client.get("/api/v1/equipos/1")
    assert resp.status_code == 200
    assert resp.json()["plantilla_total"] == 2

    # Y en el listado llega el mismo número (mismo GROUP BY, un solo viaje).
    resp = await client.get("/api/v1/equipos")
    por_id = {e["id"]: e for e in resp.json()}
    assert por_id[1]["plantilla_total"] == 2


async def test_equipo_recien_creado_tiene_plantilla_cero(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    # EC-39: un equipo con 0 jugadores es válido, no un error.
    resp = await client.post(
        "/api/v1/equipos", json={"nombre": "Equipo Vacío", **FUTBOL}, headers=admin_general_headers
    )
    assert resp.json()["plantilla_total"] == 0


# T7 / EC-38 — no se puede mover de disciplina un equipo ya inscrito.
async def test_ec38_cambiar_disciplina_con_inscripciones_es_rechazado(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    disciplina_id, modalidad_id = await _crear_disciplina_y_modalidad(
        db_session, "Voleibol T7", "Pista T7", tamano_equipo=6
    )
    # El equipo 1 (05_seed.sql) ya está inscrito en el torneo 1.
    resp = await client.patch(
        "/api/v1/equipos/1",
        json={"disciplina_id": disciplina_id, "modalidad_id": modalidad_id},
        headers=admin_general_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "inscrito" in resp.json()["detail"].lower()


async def test_cambiar_disciplina_sin_inscripciones_es_permitido(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    # La contraparte de EC-38: un equipo que nunca jugó nada sí se puede
    # corregir — es el caso de los huérfanos que la migración desactiva
    # (EC-36) y el admin reactiva eligiendo disciplina desde la UI.
    disciplina_id, modalidad_id = await _crear_disciplina_y_modalidad(
        db_session, "Rugby T7b", "Rugby 7 T7b", tamano_equipo=7
    )
    resp = await client.post(
        "/api/v1/equipos", json={"nombre": "Equipo Movible", **FUTBOL}, headers=admin_general_headers
    )
    equipo_id = resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/equipos/{equipo_id}",
        json={"disciplina_id": disciplina_id, "modalidad_id": modalidad_id},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["disciplina_id"] == disciplina_id


async def test_patch_que_reenvia_la_misma_disciplina_no_se_bloquea(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    # Un formulario de edición manda todos los campos, incluida la
    # disciplina sin cambios — eso no es "cambiar la disciplina" y no debe
    # chocar contra EC-38 (el equipo 1 está inscrito en el torneo 1).
    resp = await client.patch(
        "/api/v1/equipos/1",
        json={"nombre": "Tiburones FC", **FUTBOL},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
