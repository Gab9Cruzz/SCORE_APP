from httpx import AsyncClient


async def test_listar_usuarios_requiere_admin_general(client: AsyncClient):
    resp = await client.get("/api/v1/usuarios")
    assert resp.status_code == 401


async def test_arbitro_no_puede_gestionar_usuarios(client: AsyncClient, arbitro_headers: dict[str, str]):
    resp = await client.get("/api/v1/usuarios", headers=arbitro_headers)
    assert resp.status_code == 403


async def test_torneo_admin_no_puede_escribir_usuarios(
    client: AsyncClient, torneo_admin_headers: dict[str, str], admin_general_headers: dict[str, str]
):
    # Este es el chequeo que evita el bug de escalación de privilegios que
    # encontró la voz externa en la revisión de Fase 1: escritura en
    # usuarios.py gatea a AdminGeneral literal, NO al swap uniforme
    # Admin->TorneoAdmin que se aplicó en los demás routers. Si alguna vez
    # esto vuelve a dar 200/201, es porque alguien le agregó TorneoAdmin a
    # require_roles(...) en POST/PATCH/DELETE.
    resp = await client.post(
        "/api/v1/usuarios",
        json={"username": "otro_admin", "nombre": "Otro Admin", "password": "clave12345", "rol": "AdminGeneral"},
        headers=torneo_admin_headers,
    )
    assert resp.status_code == 403

    resp = await client.post(
        "/api/v1/usuarios",
        json={"username": "victima2_test", "nombre": "Victima2", "password": "clave12345", "rol": "Arbitro"},
        headers=admin_general_headers,
    )
    otro_id = resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/usuarios/{otro_id}", json={"nombre": "Cambiado"}, headers=torneo_admin_headers
    )
    assert resp.status_code == 403

    resp = await client.delete(f"/api/v1/usuarios/{otro_id}", headers=torneo_admin_headers)
    assert resp.status_code == 403


async def test_torneo_admin_puede_leer_pero_solo_ve_arbitros(
    client: AsyncClient,
    torneo_admin_headers: dict[str, str],
    admin_general_headers: dict[str, str],
    arbitro_headers: dict[str, str],
):
    # D5 (roles-3-modulos-plan.md, Fase 2): TorneoAdmin necesita ver la
    # lista de árbitros para asignarlos a un partido, pero nunca el roster
    # completo (no debe ver otros TorneoAdmin/AdminGeneral).
    resp = await client.get("/api/v1/usuarios", headers=torneo_admin_headers)
    assert resp.status_code == 200
    roles_vistos = {u["rol"] for u in resp.json()}
    assert roles_vistos == {"Arbitro"}

    # Aunque pida explícitamente otro rol, el filtro se pisa server-side.
    resp = await client.get(
        "/api/v1/usuarios", params={"rol": "AdminGeneral"}, headers=torneo_admin_headers
    )
    assert resp.status_code == 200
    assert {u["rol"] for u in resp.json()} == {"Arbitro"}

    # AdminGeneral sigue viendo la lista completa, sin recorte.
    resp = await client.get("/api/v1/usuarios", headers=admin_general_headers)
    assert resp.status_code == 200
    roles_admin_general = {u["rol"] for u in resp.json()}
    assert "AdminGeneral" in roles_admin_general
    assert "TorneoAdmin" in roles_admin_general


async def test_torneo_admin_get_por_id_de_no_arbitro_da_404(
    client: AsyncClient, torneo_admin_headers: dict[str, str], admin_general_headers: dict[str, str]
):
    resp = await client.get("/api/v1/auth/me", headers=admin_general_headers)
    id_admin_general = resp.json()["id"]

    resp = await client.get(f"/api/v1/usuarios/{id_admin_general}", headers=torneo_admin_headers)
    assert resp.status_code == 404


async def test_admin_general_crea_y_lista_usuarios(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/usuarios",
        json={"username": "Nuevo_Arbitro", "nombre": "Nuevo Árbitro", "password": "clave12345", "rol": "Arbitro"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    # chk_usuarios_username_lower: se normaliza a minúsculas antes de guardar.
    assert body["username"] == "nuevo_arbitro"
    assert "password" not in body
    assert "password_hash" not in body

    resp = await client.get("/api/v1/usuarios", headers=admin_general_headers)
    assert resp.status_code == 200
    usernames = [u["username"] for u in resp.json()]
    assert "nuevo_arbitro" in usernames


async def test_password_corta_es_rechazada(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/usuarios",
        json={"username": "corto", "nombre": "Corto", "password": "123", "rol": "Publico"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 422


async def test_patch_password_corta_es_rechazada(client: AsyncClient, admin_general_headers: dict[str, str]):
    # roles-3-modulos-plan.md, Fase 4, D3: UsuarioUpdate.password no tenía
    # el mismo mínimo de 8 caracteres que UsuarioCreate — agujero
    # preexistente, alcanzable ahora desde el form de edición nuevo.
    creado = await client.post(
        "/api/v1/usuarios",
        json={"username": "para_patch", "nombre": "Para Patch", "password": "clave12345", "rol": "Publico"},
        headers=admin_general_headers,
    )
    usuario_id = creado.json()["id"]

    resp = await client.patch(
        f"/api/v1/usuarios/{usuario_id}", json={"password": "123"}, headers=admin_general_headers
    )
    assert resp.status_code == 422


async def test_admin_general_no_puede_cambiarse_su_propio_rol(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    resp = await client.get("/api/v1/auth/me", headers=admin_general_headers)
    mi_id = resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/usuarios/{mi_id}", json={"rol": "TorneoAdmin"}, headers=admin_general_headers
    )
    assert resp.status_code == 403


async def test_admin_general_no_puede_desactivarse_a_si_mismo(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    resp = await client.get("/api/v1/auth/me", headers=admin_general_headers)
    mi_id = resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/usuarios/{mi_id}", json={"estado": "Inactivo"}, headers=admin_general_headers
    )
    assert resp.status_code == 403

    resp = await client.delete(f"/api/v1/usuarios/{mi_id}", headers=admin_general_headers)
    assert resp.status_code == 403


async def test_admin_general_puede_desactivar_a_otro_usuario(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    resp = await client.post(
        "/api/v1/usuarios",
        json={"username": "victima_test", "nombre": "Victima", "password": "clave12345", "rol": "Arbitro"},
        headers=admin_general_headers,
    )
    otro_id = resp.json()["id"]

    resp = await client.delete(f"/api/v1/usuarios/{otro_id}", headers=admin_general_headers)
    assert resp.status_code == 200
    assert resp.json()["estado"] == "Inactivo"
