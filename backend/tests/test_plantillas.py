import itertools

from httpx import AsyncClient

# 05_seed.sql: inscripcion_torneo_id=1 es Tiburones FC (equipo 1) en Copa
# Ecotec 2026 (torneo 1); disciplina_id=1 es Fútbol.
INSCRIPCION_TIBURONES_ID = 1
DISCIPLINA_FUTBOL_ID = 1

# unique_jugador_cedula exige una cédula distinta por jugador nuevo; un
# contador simple alcanza (los tests de este módulo no corren en paralelo
# entre sí, solo aislados por transacción — ver conftest.py).
_contador_cedulas = itertools.count(1)


async def _crear_perfil(client: AsyncClient, headers: dict[str, str], nombre: str) -> int:
    """Crea un jugador nuevo + su perfil de Fútbol, devuelve el perfil_id.
    Cada test usa un jugador distinto para no chocar con
    unique_perfil_por_disciplina si corren contra el mismo jugador."""
    cedula = f"08{next(_contador_cedulas):08d}"
    resp = await client.post(
        "/api/v1/jugadores",
        json={"nombre": nombre, "cedula": cedula, "correo_electronico": f"{cedula}@example.com"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    jugador_id = resp.json()["id"]

    resp = await client.post(
        "/api/v1/perfiles",
        json={"jugador_id": jugador_id, "disciplina_id": DISCIPLINA_FUTBOL_ID},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_listar_plantilla_de_equipo(client: AsyncClient):
    # 05_seed.sql pone a los jugadores 1 y 2 en el equipo 1 (torneo 1).
    resp = await client.get("/api/v1/plantillas", params={"inscripcion_torneo_id": INSCRIPCION_TIBURONES_ID})
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_admin_da_de_alta_jugador_en_equipo(client: AsyncClient, admin_general_headers: dict[str, str]):
    perfil_id = await _crear_perfil(client, admin_general_headers, "Fichaje Nuevo")

    resp = await client.post(
        "/api/v1/plantillas",
        json={
            "jugador_perfil_id": perfil_id,
            "inscripcion_torneo_id": INSCRIPCION_TIBURONES_ID,
            "dorsal": 99,
            "fecha_inicio": "2026-02-01",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["dorsal"] == 99


async def test_dorsal_repetido_en_roster_vigente_es_rechazado(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    # uq_dorsal_por_roster_vigente (03_indexes.sql): el dorsal 10 en la
    # inscripción 1 ya lo tiene Carlos Pérez (05_seed.sql).
    perfil_id = await _crear_perfil(client, admin_general_headers, "Otro Jugador")

    resp = await client.post(
        "/api/v1/plantillas",
        json={
            "jugador_perfil_id": perfil_id,
            "inscripcion_torneo_id": INSCRIPCION_TIBURONES_ID,
            "dorsal": 10,
            "fecha_inicio": "2026-02-01",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 409


async def test_perfil_ya_activo_en_el_torneo_es_rechazado(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    # fn_validar_exclusividad_torneo (06_triggers.sql): un perfil no puede
    # tener dos membresías Activo en el mismo torneo, aunque sea en otro
    # equipo. inscripcion_torneo_id=2 es Águilas del Sur en el mismo
    # torneo 1 que la inscripción 1.
    perfil_id = await _crear_perfil(client, admin_general_headers, "Jugador Doble Equipo")

    resp = await client.post(
        "/api/v1/plantillas",
        json={
            "jugador_perfil_id": perfil_id,
            "inscripcion_torneo_id": INSCRIPCION_TIBURONES_ID,
            "dorsal": 77,
            "fecha_inicio": "2026-02-01",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text

    resp = await client.post(
        "/api/v1/plantillas",
        json={
            "jugador_perfil_id": perfil_id,
            "inscripcion_torneo_id": 2,
            "dorsal": 78,
            "fecha_inicio": "2026-02-01",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 400, resp.text
