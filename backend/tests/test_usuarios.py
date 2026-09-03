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


# --- Licencia + asignación de torneos (rbac-licencias-torneos-plan.md) ---


async def test_usuario_out_incluye_licencia_activa(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.get("/api/v1/usuarios", headers=admin_general_headers)
    assert resp.status_code == 200
    assert all("licencia_activa" in u for u in resp.json())
    # DEFAULT TRUE (rbac-licencias-torneos-plan.md, §3.1): nadie pierde
    # acceso el día del deploy.
    assert all(u["licencia_activa"] is True for u in resp.json())


async def test_admin_general_revoca_y_reotorga_licencia_de_otro(
    client: AsyncClient, admin_general_headers: dict[str, str], torneo_admin_headers: dict[str, str]
):
    resp = await client.get("/api/v1/auth/me", headers=torneo_admin_headers)
    otro_id = resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/usuarios/{otro_id}/licencia", json={"activa": False}, headers=admin_general_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["licencia_activa"] is False

    # La cuenta revocada pierde acceso de inmediato — sin esperar el JWT.
    resp = await client.get("/api/v1/auth/me", headers=torneo_admin_headers)
    assert resp.status_code == 403
    assert resp.headers.get("X-License-Revoked") == "true"

    resp = await client.patch(
        f"/api/v1/usuarios/{otro_id}/licencia", json={"activa": True}, headers=admin_general_headers
    )
    assert resp.status_code == 200
    assert resp.json()["licencia_activa"] is True


async def test_admin_general_no_puede_revocarse_su_propia_licencia(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    # Clon exacto de test_admin_general_no_puede_desactivarse_a_si_mismo
    # (T6) — con potencialmente un solo AdminGeneral en la base, esto es
    # el mismo self-lockout, otro campo.
    resp = await client.get("/api/v1/auth/me", headers=admin_general_headers)
    mi_id = resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/usuarios/{mi_id}/licencia", json={"activa": False}, headers=admin_general_headers
    )
    assert resp.status_code == 403

    # Otorgarse la propia licencia (ya la tiene) no está bloqueado — el
    # guard es específico de auto-REVOCACIÓN, no de tocar el propio campo.
    resp = await client.patch(
        f"/api/v1/usuarios/{mi_id}/licencia", json={"activa": True}, headers=admin_general_headers
    )
    assert resp.status_code == 200


async def test_torneo_admin_no_puede_tocar_licencia_ni_asignaciones(
    client: AsyncClient, torneo_admin_headers: dict[str, str], admin_general_headers: dict[str, str]
):
    resp = await client.get("/api/v1/auth/me", headers=torneo_admin_headers)
    mi_id = resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/usuarios/{mi_id}/licencia", json={"activa": False}, headers=torneo_admin_headers
    )
    assert resp.status_code == 403

    resp = await client.patch(
        f"/api/v1/usuarios/{mi_id}/torneos", json={"torneo_ids": [1]}, headers=torneo_admin_headers
    )
    assert resp.status_code == 403


async def test_asignar_torneo_a_usuario_con_rol_incorrecto_es_rechazado(
    client: AsyncClient, admin_general_headers: dict[str, str], arbitro_headers: dict[str, str]
):
    resp = await client.get("/api/v1/auth/me", headers=arbitro_headers)
    arbitro_id = resp.json()["id"]

    # DomainRuleError (service) — llega antes que el trigger de DB en
    # operación normal, mismo doble-cinturón que fn_validar_torneo_modalidad.
    resp = await client.patch(
        f"/api/v1/usuarios/{arbitro_id}/torneos", json={"torneo_ids": [1]}, headers=admin_general_headers
    )
    assert resp.status_code == 400


async def test_set_torneos_asignados_reemplaza_el_set_completo(
    client: AsyncClient, admin_general_headers: dict[str, str], torneo_admin_headers: dict[str, str]
):
    resp = await client.get("/api/v1/auth/me", headers=torneo_admin_headers)
    torneo_admin_id = resp.json()["id"]

    resp = await client.get(f"/api/v1/usuarios/{torneo_admin_id}/torneos", headers=admin_general_headers)
    assert resp.status_code == 200
    assert resp.json() == []

    resp = await client.patch(
        f"/api/v1/usuarios/{torneo_admin_id}/torneos",
        json={"torneo_ids": [1]},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200
    assert resp.json() == [1]

    # El propio TorneoAdmin puede leer SU set (no el de otro).
    resp = await client.get(f"/api/v1/usuarios/{torneo_admin_id}/torneos", headers=torneo_admin_headers)
    assert resp.status_code == 200
    assert resp.json() == [1]

    # Set vacío = desasignar todo — comportamiento explícito, no un caso especial.
    resp = await client.patch(
        f"/api/v1/usuarios/{torneo_admin_id}/torneos",
        json={"torneo_ids": []},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_set_torneos_asignados_con_id_inexistente_da_404_con_el_id_culpable(
    client: AsyncClient, admin_general_headers: dict[str, str], torneo_admin_headers: dict[str, str]
):
    """T7 (rbac-licencias-torneos-plan.md, GAP identificado en la CEO
    review): un torneo_id basura no debe perderse silencioso en el
    diff — debe rechazar con 404 antes de tocar ninguna fila."""
    resp = await client.get("/api/v1/auth/me", headers=torneo_admin_headers)
    torneo_admin_id = resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/usuarios/{torneo_admin_id}/torneos",
        json={"torneo_ids": [1, 999999]},
        headers=admin_general_headers,
    )
    assert resp.status_code == 404
    assert "999999" in resp.json()["detail"]

    # Nada se aplicó — ni siquiera el ID 1 válido del mismo pedido.
    resp = await client.get(f"/api/v1/usuarios/{torneo_admin_id}/torneos", headers=admin_general_headers)
    assert resp.json() == []


async def test_torneo_admin_puede_leer_su_propio_set_pero_no_el_de_otro(
    client: AsyncClient,
    admin_general_headers: dict[str, str],
    torneo_admin_headers: dict[str, str],
    torneo_admin_con_torneo_headers: dict[str, str],
):
    resp = await client.get("/api/v1/auth/me", headers=torneo_admin_con_torneo_headers)
    otro_id = resp.json()["id"]

    resp = await client.get(f"/api/v1/usuarios/{otro_id}/torneos", headers=torneo_admin_headers)
    assert resp.status_code == 403


async def test_degradar_torneo_admin_desactiva_sus_asignaciones(
    client: AsyncClient,
    admin_general_headers: dict[str, str],
    torneo_admin_con_torneo_headers: dict[str, str],
):
    """T15 / hallazgo #3 de la voz externa Eng: degradar el rol de un
    TorneoAdmin con torneos asignados debe desactivar esas filas — si no,
    quedan huérfanas y podrían resucitar acceso si se lo re-promueve."""
    resp = await client.get("/api/v1/auth/me", headers=torneo_admin_con_torneo_headers)
    body = resp.json()
    usuario_id = body["id"]
    assert body["rol"] == "TorneoAdmin"

    resp = await client.get(f"/api/v1/usuarios/{usuario_id}/torneos", headers=admin_general_headers)
    assert resp.json() == [1]

    resp = await client.patch(
        f"/api/v1/usuarios/{usuario_id}", json={"rol": "Arbitro"}, headers=admin_general_headers
    )
    assert resp.status_code == 200, resp.text

    resp = await client.get(f"/api/v1/usuarios/{usuario_id}/torneos", headers=admin_general_headers)
    assert resp.json() == []

    # Re-promoverlo NO resucita la asignación vieja — queda Inactivo hasta
    # que un AdminGeneral lo asigne de nuevo, conscientemente.
    resp = await client.patch(
        f"/api/v1/usuarios/{usuario_id}", json={"rol": "TorneoAdmin"}, headers=admin_general_headers
    )
    assert resp.status_code == 200

    resp = await client.get(f"/api/v1/usuarios/{usuario_id}/torneos", headers=admin_general_headers)
    assert resp.json() == []
