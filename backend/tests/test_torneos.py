from httpx import AsyncClient

# disciplina_id=1 = "Fútbol" (05_seed.sql, único registro de DISCIPLINA
# que carga el seed) — Tipo='Equipo', así que estos torneos no necesitan
# modalidad_id (fn_validar_torneo_modalidad lo prohibiría si lo mandaran).
DISCIPLINA_FUTBOL_ID = 1


async def test_listar_torneos_es_publico(client: AsyncClient):
    # 05_seed.sql carga "Copa Ecotec 2026".
    resp = await client.get("/api/v1/torneos")
    assert resp.status_code == 200
    nombres = [t["nombre"] for t in resp.json()]
    assert "Copa Ecotec 2026" in nombres


async def test_crear_torneo_sin_auth_falla(client: AsyncClient):
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "nombre": "Liga Test",
            "disciplina_id": DISCIPLINA_FUTBOL_ID,
            "torneo_grupo_nombre": "Liga Test",
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-06-01",
        },
    )
    assert resp.status_code == 401


async def test_admin_crea_torneo(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "nombre": "Liga Test",
            "disciplina_id": DISCIPLINA_FUTBOL_ID,
            "torneo_grupo_nombre": "Liga Test",
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-06-01",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["estado"] == "Activo"
    # Torneo nuevo vía torneo_grupo_nombre = Edición 1 de un grupo nuevo
    # (torneos-admin-plan.md, Fase 1/3).
    assert body["numero_edicion"] == 1
    assert isinstance(body["torneo_grupo_id"], int)

    resp = await client.get(f"/api/v1/torneos/{body['id']}")
    assert resp.status_code == 200


async def test_torneo_sin_grupo_ni_id_es_rechazado(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "nombre": "Torneo Sin Grupo",
            "disciplina_id": DISCIPLINA_FUTBOL_ID,
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-06-01",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 422


async def test_torneo_con_ambos_grupo_y_nombre_es_rechazado(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "nombre": "Torneo Ambiguo",
            "disciplina_id": DISCIPLINA_FUTBOL_ID,
            "torneo_grupo_id": 1,
            "torneo_grupo_nombre": "Otro Grupo",
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-06-01",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 422


async def test_segunda_edicion_de_un_grupo_existente_autonumera(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    primera = await client.post(
        "/api/v1/torneos",
        json={
            "nombre": "Liga Relámpago Ed. 1",
            "disciplina_id": DISCIPLINA_FUTBOL_ID,
            "torneo_grupo_nombre": "Liga Relámpago",
            "fecha_inicio": "2026-03-01",
            "fecha_fin": "2026-05-15",
        },
        headers=admin_general_headers,
    )
    assert primera.status_code == 201, primera.text
    grupo_id = primera.json()["torneo_grupo_id"]

    segunda = await client.post(
        "/api/v1/torneos",
        json={
            "nombre": "Liga Relámpago Ed. 2",
            "disciplina_id": DISCIPLINA_FUTBOL_ID,
            "torneo_grupo_id": grupo_id,
            "fecha_inicio": "2026-04-01",
            "fecha_fin": "2026-06-30",
        },
        headers=admin_general_headers,
    )
    assert segunda.status_code == 201, segunda.text
    assert segunda.json()["torneo_grupo_id"] == grupo_id
    assert segunda.json()["numero_edicion"] == 2

    # El selector de ediciones (Fase 2, parte B) lee esto.
    resp = await client.get(f"/api/v1/torneos?torneo_grupo_id={grupo_id}")
    assert resp.status_code == 200
    numeros = sorted(t["numero_edicion"] for t in resp.json())
    assert numeros == [1, 2]


async def test_nombre_se_compone_si_no_se_manda(client: AsyncClient, admin_general_headers: dict[str, str]):
    # Decision Audit Trail #3: sin "nombre", se compone
    # "{grupo.nombre} - Edición {n}" — evita pedirle al admin un dato
    # redundante con lo que ya escribió como nombre del grupo.
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "disciplina_id": DISCIPLINA_FUTBOL_ID,
            "torneo_grupo_nombre": "Liga Sin Nombre Propio",
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-06-01",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["nombre"] == "Liga Sin Nombre Propio - Edición 1"

    grupo_id = resp.json()["torneo_grupo_id"]
    segunda = await client.post(
        "/api/v1/torneos",
        json={
            "disciplina_id": DISCIPLINA_FUTBOL_ID,
            "torneo_grupo_id": grupo_id,
            "fecha_inicio": "2026-07-01",
            "fecha_fin": "2026-08-01",
        },
        headers=admin_general_headers,
    )
    assert segunda.status_code == 201, segunda.text
    assert segunda.json()["nombre"] == "Liga Sin Nombre Propio - Edición 2"


async def test_torneo_grupo_id_inexistente_da_404(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "nombre": "Torneo Huerfano",
            "disciplina_id": DISCIPLINA_FUTBOL_ID,
            "torneo_grupo_id": 999999,
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-06-01",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 404


async def test_fecha_fin_anterior_a_inicio_es_rechazada(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "nombre": "Torneo Invalido",
            "disciplina_id": DISCIPLINA_FUTBOL_ID,
            "torneo_grupo_nombre": "Torneo Invalido",
            "fecha_inicio": "2026-06-01",
            "fecha_fin": "2026-05-01",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 422


async def test_baja_logica_de_torneo(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "nombre": "Torneo A Borrar",
            "disciplina_id": DISCIPLINA_FUTBOL_ID,
            "torneo_grupo_nombre": "Torneo A Borrar",
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-06-01",
        },
        headers=admin_general_headers,
    )
    torneo_id = resp.json()["id"]

    resp = await client.delete(f"/api/v1/torneos/{torneo_id}", headers=admin_general_headers)
    assert resp.status_code == 200
    assert resp.json()["estado"] == "Inactivo"

    # Sigue existiendo (borrado lógico, no físico).
    resp = await client.get(f"/api/v1/torneos/{torneo_id}")
    assert resp.status_code == 200
    assert resp.json()["estado"] == "Inactivo"


async def test_torneo_inexistente_da_404(client: AsyncClient):
    resp = await client.get("/api/v1/torneos/999999")
    assert resp.status_code == 404
