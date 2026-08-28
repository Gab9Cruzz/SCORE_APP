from httpx import AsyncClient

# 05_seed.sql (conftest.py solo aplica 01-06, no el catálogo maestro de
# 11_catalogo_disciplinas.sql): Disciplina "Fútbol" (id=1) con una única
# Modalidad "Fútbol 11" (id=1, tamano_equipo=11) —
# ediciones-catalogo-disciplinas-plan.md, catálogo unificado.
DISCIPLINA_FUTBOL_ID = 1
MODALIDAD_FUTBOL_11_ID = 1


async def test_listar_modalidades_es_publico(client: AsyncClient):
    resp = await client.get("/api/v1/modalidades")
    assert resp.status_code == 200
    nombres = {m["nombre"] for m in resp.json()}
    assert "Fútbol 11" in nombres


async def test_catalogo_ya_no_acepta_crear_modalidades(client: AsyncClient, admin_general_headers: dict[str, str]):
    # Decisión C1: catálogo de solo lectura + toggle de Estado — el POST ya
    # no existe como ruta (404), ni siquiera para AdminGeneral.
    resp = await client.post(
        "/api/v1/modalidades",
        json={"disciplina_id": DISCIPLINA_FUTBOL_ID, "nombre": "Fútbol 7", "tamano_equipo": 7},
        headers=admin_general_headers,
    )
    assert resp.status_code in (404, 405)


async def test_admin_activa_y_desactiva_una_modalidad(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.patch(
        f"/api/v1/modalidades/{MODALIDAD_FUTBOL_11_ID}",
        json={"estado": "Inactivo"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["estado"] == "Inactivo"

    resp = await client.patch(
        f"/api/v1/modalidades/{MODALIDAD_FUTBOL_11_ID}",
        json={"estado": "Activo"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["estado"] == "Activo"


async def test_patch_modalidad_ignora_tamano_equipo_el_catalogo_es_inmutable(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    # ModalidadUpdate solo declara `estado` — tamano_equipo/nombre en el
    # payload no tienen ningún campo al que mapear, se ignoran sin más.
    resp = await client.patch(
        f"/api/v1/modalidades/{MODALIDAD_FUTBOL_11_ID}",
        json={"estado": "Activo", "tamano_equipo": 999, "nombre": "Inventada"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["tamano_equipo"] == 11
    assert resp.json()["nombre"] == "Fútbol 11"


async def test_arbitro_no_puede_activar_ni_desactivar_modalidad(client: AsyncClient, arbitro_headers: dict[str, str]):
    resp = await client.patch(
        f"/api/v1/modalidades/{MODALIDAD_FUTBOL_11_ID}", json={"estado": "Inactivo"}, headers=arbitro_headers
    )
    assert resp.status_code == 403
