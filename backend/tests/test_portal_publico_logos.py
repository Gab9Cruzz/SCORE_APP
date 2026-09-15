"""Portal Público: validación de `logo_url` (E-S2, portal-publico-feed-
partidos-plan.md). El vector real no es XSS sino fuga de IP/Referer a un
host de tercero en una página pública + mixed-content con `http://` — se
rechaza en escritura y se neutraliza en lectura por si el dato entró
sucio por otro camino (seed, SQL directo).
"""
from sqlalchemy import text
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

DISCIPLINA_FUTBOL_ID = 1
MODALIDAD_FUTBOL_11_ID = 1


async def _crear_equipo(client: AsyncClient, headers: dict[str, str]) -> int:
    resp = await client.post(
        "/api/v1/equipos",
        json={"nombre": "Equipo Logo Test", "disciplina_id": DISCIPLINA_FUTBOL_ID, "modalidad_id": MODALIDAD_FUTBOL_11_ID},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_logo_url_https_se_acepta(client: AsyncClient, admin_general_headers: dict[str, str]):
    equipo_id = await _crear_equipo(client, admin_general_headers)
    resp = await client.patch(
        f"/api/v1/equipos/{equipo_id}",
        json={"logo_url": "https://cdn.example.com/escudo.png"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["logo_url"] == "https://cdn.example.com/escudo.png"


async def test_logo_url_http_es_rechazada(client: AsyncClient, admin_general_headers: dict[str, str]):
    equipo_id = await _crear_equipo(client, admin_general_headers)
    resp = await client.patch(
        f"/api/v1/equipos/{equipo_id}",
        json={"logo_url": "http://cdn.example.com/escudo.png"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 422


async def test_logo_url_javascript_es_rechazada(client: AsyncClient, admin_general_headers: dict[str, str]):
    equipo_id = await _crear_equipo(client, admin_general_headers)
    resp = await client.patch(
        f"/api/v1/equipos/{equipo_id}",
        json={"logo_url": "javascript:alert(1)"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 422


async def test_logo_url_data_uri_es_rechazada(client: AsyncClient, admin_general_headers: dict[str, str]):
    equipo_id = await _crear_equipo(client, admin_general_headers)
    resp = await client.patch(
        f"/api/v1/equipos/{equipo_id}",
        json={"logo_url": "data:image/png;base64,AAAA"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 422


async def test_logo_url_sucia_por_sql_directo_se_neutraliza_en_lectura(
    client: AsyncClient, admin_general_headers: dict[str, str], db_session: AsyncSession
):
    """El validador de escritura no cubre datos que entraron por otro
    camino (seed, SQL directo) — EquipoOut tiene que neutralizarlo igual
    en lectura, no confiar en que todo dato en la base ya es limpio."""
    equipo_id = await _crear_equipo(client, admin_general_headers)
    await db_session.execute(
        text("UPDATE EQUIPOS SET Logo_URL = 'http://sucio.example.com/x.png' WHERE ID = :id"),
        {"id": equipo_id},
    )
    await db_session.commit()

    resp = await client.get(f"/api/v1/equipos/{equipo_id}")
    assert resp.status_code == 200
    assert resp.json()["logo_url"] is None


async def test_torneo_grupo_logo_url_y_pais_editable_via_patch(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "disciplina_id": DISCIPLINA_FUTBOL_ID,
            "modalidad_id": MODALIDAD_FUTBOL_11_ID,
            "torneo_grupo_nombre": "Grupo Logo Pais Test",
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-06-01",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    grupo_id = resp.json()["torneo_grupo_id"]

    resp = await client.patch(
        f"/api/v1/torneo-grupos/{grupo_id}",
        json={"pais": "Ecuador", "logo_url": "https://cdn.example.com/logo.png"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["pais"] == "Ecuador"
    assert resp.json()["logo_url"] == "https://cdn.example.com/logo.png"

    resp = await client.patch(
        f"/api/v1/torneo-grupos/{grupo_id}",
        json={"logo_url": "http://inseguro.example.com/logo.png"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 422
