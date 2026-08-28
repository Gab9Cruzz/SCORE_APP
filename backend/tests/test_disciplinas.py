from httpx import AsyncClient

# 11_catalogo_disciplinas.sql no corre en la base de test (conftest.py solo
# aplica 01-06) — el catálogo acá es solo lo que carga 05_seed.sql:
# "Fútbol" (id=1), sin Tipo (ediciones-catalogo-disciplinas-plan.md,
# Decisión A1).
DISCIPLINA_FUTBOL_ID = 1


async def test_catalogo_de_disciplinas_es_publico(client: AsyncClient):
    resp = await client.get("/api/v1/disciplinas")
    assert resp.status_code == 200
    nombres = {d["nombre"] for d in resp.json()}
    assert "Fútbol" in nombres
    assert "tipo" not in resp.json()[0]


async def test_disciplinas_con_modalidades_es_jerarquico(client: AsyncClient):
    # GET /disciplinas/con-modalidades (D-Eng, arquitectura del plan) — una
    # sola llamada trae cada disciplina con su roster de modalidades.
    resp = await client.get("/api/v1/disciplinas/con-modalidades")
    assert resp.status_code == 200
    futbol = next(d for d in resp.json() if d["nombre"] == "Fútbol")
    assert any(m["nombre"] == "Fútbol 11" for m in futbol["modalidades"])


async def test_catalogo_ya_no_acepta_crear_disciplinas(client: AsyncClient, admin_general_headers: dict[str, str]):
    # Decisión C1: catálogo de solo lectura + toggle de Estado — el POST ya
    # no existe como ruta (404), ni siquiera para AdminGeneral.
    resp = await client.post(
        "/api/v1/disciplinas",
        json={"nombre": "Rugby"},
        headers=admin_general_headers,
    )
    assert resp.status_code in (404, 405)


async def test_admin_activa_y_desactiva_una_disciplina(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.patch(
        f"/api/v1/disciplinas/{DISCIPLINA_FUTBOL_ID}",
        json={"estado": "Inactivo"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["estado"] == "Inactivo"

    resp = await client.patch(
        f"/api/v1/disciplinas/{DISCIPLINA_FUTBOL_ID}",
        json={"estado": "Activo"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["estado"] == "Activo"


async def test_patch_disciplina_ignora_nombre_el_catalogo_es_inmutable(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    # DisciplinaUpdate solo declara `estado` — un `nombre` en el payload no
    # tiene ningún campo al que mapear, se ignora sin más.
    resp = await client.patch(
        f"/api/v1/disciplinas/{DISCIPLINA_FUTBOL_ID}",
        json={"estado": "Activo", "nombre": "Fulbo mal escrito"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["nombre"] == "Fútbol"


async def test_arbitro_no_puede_activar_ni_desactivar_disciplina(client: AsyncClient, arbitro_headers: dict[str, str]):
    resp = await client.patch(
        f"/api/v1/disciplinas/{DISCIPLINA_FUTBOL_ID}", json={"estado": "Inactivo"}, headers=arbitro_headers
    )
    assert resp.status_code == 403


async def test_selector_de_torneo_nuevo_filtra_solo_activas(client: AsyncClient, admin_general_headers: dict[str, str]):
    # D-Eng-7: el catálogo completo (Activo + Inactivo) se sirve al admin,
    # pero filtrar por estado=Activo (lo que usa el selector de "Torneo
    # nuevo") excluye una disciplina desactivada.
    resp = await client.patch(
        f"/api/v1/disciplinas/{DISCIPLINA_FUTBOL_ID}", json={"estado": "Inactivo"}, headers=admin_general_headers
    )
    assert resp.status_code == 200

    resp = await client.get("/api/v1/disciplinas", params={"estado": "Activo"})
    assert resp.status_code == 200
    assert DISCIPLINA_FUTBOL_ID not in {d["id"] for d in resp.json()}

    resp = await client.get("/api/v1/disciplinas")
    assert DISCIPLINA_FUTBOL_ID in {d["id"] for d in resp.json()}
