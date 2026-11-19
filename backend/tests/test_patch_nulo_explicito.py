"""TASK-020 (FUN-10): en un PATCH, `null` limpia el campo si la columna lo
admite; omitir un campo no lo toca; `null` en un campo obligatorio es 422.
Antes BaseRepository.save_changes descartaba todo None y no se podía vaciar
ningún campo."""
from httpx import AsyncClient


async def test_patch_partido_con_arbitro_null_lo_deja_sin_arbitro(
    client: AsyncClient, admin_general_headers: dict[str, str], arbitro_headers: dict[str, str]
):
    """PR-021: `arbitro_headers` asigna un árbitro al partido 3."""
    assert (await client.get("/api/v1/partidos/3")).json()["arbitro_id"] is not None
    resp = await client.patch("/api/v1/partidos/3", json={"arbitro_id": None}, headers=admin_general_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["arbitro_id"] is None


async def test_patch_jugador_con_foto_null_borra_la_foto(client: AsyncClient, admin_general_headers: dict[str, str]):
    h = admin_general_headers
    resp = await client.patch("/api/v1/jugadores/1", json={"foto_url": "https://example.com/f.png"}, headers=h)
    assert resp.json()["foto_url"] == "https://example.com/f.png"
    resp = await client.patch("/api/v1/jugadores/1", json={"foto_url": None}, headers=h)
    assert resp.status_code == 200, resp.text
    assert resp.json()["foto_url"] is None


async def test_patch_equipo_con_logo_null_borra_el_logo(client: AsyncClient, admin_general_headers: dict[str, str]):
    h = admin_general_headers
    await client.patch("/api/v1/equipos/1", json={"logo_url": "https://example.com/l.png"}, headers=h)
    resp = await client.patch("/api/v1/equipos/1", json={"logo_url": None}, headers=h)
    assert resp.status_code == 200, resp.text
    assert resp.json()["logo_url"] is None


async def test_un_campo_omitido_no_se_modifica(client: AsyncClient, admin_general_headers: dict[str, str]):
    h = admin_general_headers
    antes = (await client.get("/api/v1/jugadores/1", headers=h)).json()
    resp = await client.patch("/api/v1/jugadores/1", json={"nombre": "Carlos P."}, headers=h)
    assert resp.status_code == 200, resp.text
    despues = resp.json()
    assert despues["nombre"] == "Carlos P."
    assert despues["cedula"] == antes["cedula"]
    assert despues["correo_electronico"] == antes["correo_electronico"]


async def test_null_en_un_campo_obligatorio_es_422(client: AsyncClient, admin_general_headers: dict[str, str]):
    h = admin_general_headers
    for ruta, cuerpo in (
        ("/api/v1/jugadores/1", {"nombre": None}),
        ("/api/v1/equipos/1", {"nombre": None}),
        ("/api/v1/partidos/3", {"fecha_partido": None}),
    ):
        resp = await client.patch(ruta, json=cuerpo, headers=h)
        assert resp.status_code == 422, (ruta, resp.text)


async def test_torneo_sigue_limpiando_sus_campos_anulables(client: AsyncClient, admin_general_headers: dict[str, str]):
    """El tratamiento especial de torneo.py ya no hace falta: lo hace la
    base para todos."""
    h = admin_general_headers
    resp = await client.patch("/api/v1/torneos/1", json={"maximo_cambios_por_equipo": 5}, headers=h)
    assert resp.json()["maximo_cambios_por_equipo"] == 5
    resp = await client.patch("/api/v1/torneos/1", json={"maximo_cambios_por_equipo": None}, headers=h)
    assert resp.status_code == 200, resp.text
    assert resp.json()["maximo_cambios_por_equipo"] is None
