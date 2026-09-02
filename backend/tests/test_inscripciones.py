from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.disciplina import Disciplina
from app.models.modalidad import Modalidad


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


async def test_listar_inscripciones_es_publico(client: AsyncClient):
    resp = await client.get("/api/v1/inscripciones", params={"torneo_id": 1})
    assert resp.status_code == 200
    assert len(resp.json()) == 3  # 05_seed.sql inscribe a los 3 equipos


async def test_admin_inscribe_equipo_nuevo(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.post("/api/v1/equipos", json={"nombre": "Equipo Nuevo Inscripcion", "disciplina_id": 1, "modalidad_id": 1}, headers=admin_general_headers)
    equipo_id = resp.json()["id"]

    resp = await client.post(
        "/api/v1/inscripciones", json={"torneo_id": 1, "equipo_id": equipo_id}, headers=admin_general_headers
    )
    assert resp.status_code == 201
    assert resp.json()["estado"] == "Inscrito"


async def test_doble_inscripcion_es_rechazada(client: AsyncClient, admin_general_headers: dict[str, str]):
    # unique_inscripcion (02_constraints.sql): el equipo 1 ya está inscrito
    # en el torneo 1 por 05_seed.sql.
    resp = await client.post(
        "/api/v1/inscripciones", json={"torneo_id": 1, "equipo_id": 1}, headers=admin_general_headers
    )
    assert resp.status_code == 409


# T5 / EC-33 — filtro estricto por disciplina, del lado de la API
# (equipos-disciplina-navegacion-plan.md, pedido B, D-Eng-9). El modal del
# frontend ya no ofrece equipos de otra disciplina, pero eso es una
# comodidad, no una garantía: un curl directo tiene que rebotar acá.
async def test_ec33_equipo_de_otra_disciplina_no_se_puede_inscribir(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    disciplina_id, modalidad_id = await _crear_disciplina_y_modalidad(
        db_session, "Ajedrez EC33", "Blitz EC33", tamano_equipo=1
    )
    resp = await client.post(
        "/api/v1/equipos",
        json={"nombre": "Torre Blanca", "disciplina_id": disciplina_id, "modalidad_id": modalidad_id},
        headers=admin_general_headers,
    )
    equipo_id = resp.json()["id"]

    # El torneo 1 (05_seed.sql) es de Fútbol.
    resp = await client.post(
        "/api/v1/inscripciones",
        json={"torneo_id": 1, "equipo_id": equipo_id},
        headers=admin_general_headers,
    )
    assert resp.status_code == 400, resp.text
    detalle = resp.json()["detail"]
    assert "Ajedrez EC33" in detalle and "Fútbol" in detalle


# T6 / EC-44 — la MODALIDAD no se valida, solo la disciplina: un equipo de
# Fútbol 11 en un torneo de Fútbol 5 es legítimo (interpretación literal
# del pedido: "exactamente la misma Disciplina").
async def test_ec44_misma_disciplina_distinta_modalidad_es_valido(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    futbol_5 = Modalidad(disciplina_id=1, nombre="Fútbol 5 EC44", tamano_equipo=5)
    db_session.add(futbol_5)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/equipos",
        json={"nombre": "Equipo Fútbol 5 EC44", "disciplina_id": 1, "modalidad_id": futbol_5.id},
        headers=admin_general_headers,
    )
    equipo_id = resp.json()["id"]

    # Torneo 1 es Fútbol / "Fútbol 11" — misma disciplina, otra modalidad.
    resp = await client.post(
        "/api/v1/inscripciones",
        json={"torneo_id": 1, "equipo_id": equipo_id},
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text


# D-Eng-17 — hasta este plan, el camino de equipo no validaba ni que el
# torneo existiera: se creaba la inscripción y reventaba después contra la
# FK. Ahora es un 404 claro.
async def test_inscribir_equipo_en_torneo_inexistente_da_404(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    resp = await client.post(
        "/api/v1/inscripciones",
        json={"torneo_id": 99999, "equipo_id": 1},
        headers=admin_general_headers,
    )
    assert resp.status_code == 404, resp.text


async def test_3b10_cupo_maximo_de_inscripciones_rechaza_al_llegar_al_limite(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    """3B-10 (docs/plans/cierre-backlog-todos-plan.md): NULL = sin límite
    (comportamiento default, ya cubierto por el resto de esta suite) —
    este test cubre el caso con cupo seteado."""
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "disciplina_id": 1,
            "modalidad_id": 1,
            "torneo_grupo_nombre": "Torneo Cupo Chico",
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-06-01",
            "cupo_maximo_inscripciones": 1,
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    torneo_id = resp.json()["id"]
    assert resp.json()["cupo_maximo_inscripciones"] == 1

    equipo_a = (
        await client.post(
            "/api/v1/equipos",
            json={"nombre": "Cupo Chico A", "disciplina_id": 1, "modalidad_id": 1},
            headers=admin_general_headers,
        )
    ).json()["id"]
    equipo_b = (
        await client.post(
            "/api/v1/equipos",
            json={"nombre": "Cupo Chico B", "disciplina_id": 1, "modalidad_id": 1},
            headers=admin_general_headers,
        )
    ).json()["id"]

    resp = await client.post(
        "/api/v1/inscripciones", json={"torneo_id": torneo_id, "equipo_id": equipo_a}, headers=admin_general_headers
    )
    assert resp.status_code == 201, resp.text
    inscripcion_a_id = resp.json()["id"]

    resp = await client.post(
        "/api/v1/inscripciones", json={"torneo_id": torneo_id, "equipo_id": equipo_b}, headers=admin_general_headers
    )
    assert resp.status_code == 400, resp.text
    assert "cupo máximo" in resp.json()["detail"].lower()

    # Cancelar la primera libera el cupo — no es un tope "de por vida".
    resp = await client.patch(
        f"/api/v1/inscripciones/{inscripcion_a_id}", json={"estado": "Cancelado"}, headers=admin_general_headers
    )
    assert resp.status_code == 200, resp.text

    resp = await client.post(
        "/api/v1/inscripciones", json={"torneo_id": torneo_id, "equipo_id": equipo_b}, headers=admin_general_headers
    )
    assert resp.status_code == 201, resp.text


async def test_3b10_sin_cupo_seteado_no_hay_limite(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "disciplina_id": 1,
            "modalidad_id": 1,
            "torneo_grupo_nombre": "Torneo Sin Cupo",
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-06-01",
        },
        headers=admin_general_headers,
    )
    assert resp.json()["cupo_maximo_inscripciones"] is None
