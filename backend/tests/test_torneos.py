from httpx import AsyncClient

# disciplina_id=1 = "Fútbol" (05_seed.sql, único registro de DISCIPLINA
# que carga el seed). Modalidad_ID es siempre obligatorio desde el
# catálogo unificado (ediciones-catalogo-disciplinas-plan.md, Decisión
# A1) — modalidad_id=1 = "Fútbol 11" (única Modalidad que carga el seed).
DISCIPLINA_FUTBOL_ID = 1
MODALIDAD_FUTBOL_11_ID = 1


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
            "modalidad_id": MODALIDAD_FUTBOL_11_ID,
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
            "modalidad_id": MODALIDAD_FUTBOL_11_ID,
            "torneo_grupo_nombre": "Liga Test",
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-06-01",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["estado"] == "Activo"
    assert body["modalidad_id"] == MODALIDAD_FUTBOL_11_ID
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
            "modalidad_id": MODALIDAD_FUTBOL_11_ID,
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
            "modalidad_id": MODALIDAD_FUTBOL_11_ID,
            "torneo_grupo_id": 1,
            "torneo_grupo_nombre": "Otro Grupo",
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-06-01",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 422


async def test_torneo_grupo_nuevo_sin_disciplina_o_modalidad_es_rechazado(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    # TorneoCreate.disciplina_modalidad_requeridas_si_grupo_nuevo — un
    # TORNEO_GRUPO nuevo no tiene ninguna edición previa de la que heredar.
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "nombre": "Torneo Incompleto",
            "torneo_grupo_nombre": "Torneo Incompleto",
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
            "modalidad_id": MODALIDAD_FUTBOL_11_ID,
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
            "torneo_grupo_id": grupo_id,
            "fecha_inicio": "2026-04-01",
            "fecha_fin": "2026-06-30",
        },
        headers=admin_general_headers,
    )
    assert segunda.status_code == 201, segunda.text
    assert segunda.json()["torneo_grupo_id"] == grupo_id
    assert segunda.json()["numero_edicion"] == 2
    # D-Eng-5: hereda disciplina/modalidad de la edición anterior del grupo.
    assert segunda.json()["disciplina_id"] == DISCIPLINA_FUTBOL_ID
    assert segunda.json()["modalidad_id"] == MODALIDAD_FUTBOL_11_ID

    # El selector de ediciones (Fase 2, parte B) lee esto.
    resp = await client.get(f"/api/v1/torneos?torneo_grupo_id={grupo_id}")
    assert resp.status_code == 200
    numeros = sorted(t["numero_edicion"] for t in resp.json())
    assert numeros == [1, 2]


async def test_nueva_edicion_ignora_disciplina_y_modalidad_manipuladas_a_mano(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    # D-Eng-5/EC-26: un payload armado a mano con torneo_grupo_id + una
    # disciplina/modalidad distinta a la del grupo — el backend descarta
    # lo que mande el cliente y usa siempre los valores del grupo, sin
    # necesidad de un 400.
    grupo = await client.post(
        "/api/v1/torneos",
        json={
            "torneo_grupo_nombre": "Liga EC-26",
            "disciplina_id": DISCIPLINA_FUTBOL_ID,
            "modalidad_id": MODALIDAD_FUTBOL_11_ID,
            "fecha_inicio": "2026-03-01",
            "fecha_fin": "2026-05-15",
        },
        headers=admin_general_headers,
    )
    grupo_id = grupo.json()["torneo_grupo_id"]

    manipulado = await client.post(
        "/api/v1/torneos",
        json={
            "torneo_grupo_id": grupo_id,
            "disciplina_id": 999999,
            "modalidad_id": 999999,
            "fecha_inicio": "2026-06-01",
            "fecha_fin": "2026-08-01",
        },
        headers=admin_general_headers,
    )
    assert manipulado.status_code == 201, manipulado.text
    assert manipulado.json()["disciplina_id"] == DISCIPLINA_FUTBOL_ID
    assert manipulado.json()["modalidad_id"] == MODALIDAD_FUTBOL_11_ID


async def test_nombre_se_compone_si_no_se_manda(client: AsyncClient, admin_general_headers: dict[str, str]):
    # Decision Audit Trail #3: sin "nombre", se compone
    # "{grupo.nombre} - Edición {n}" — evita pedirle al admin un dato
    # redundante con lo que ya escribió como nombre del grupo.
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "disciplina_id": DISCIPLINA_FUTBOL_ID,
            "modalidad_id": MODALIDAD_FUTBOL_11_ID,
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
            "modalidad_id": MODALIDAD_FUTBOL_11_ID,
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
            "modalidad_id": MODALIDAD_FUTBOL_11_ID,
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


# --- require_torneo_access (rbac-licencias-torneos-plan.md, §4.3/§4.6) ---


async def test_torneo_admin_sin_asignacion_no_puede_editar_torneo_1(
    client: AsyncClient, torneo_admin_headers: dict[str, str]
):
    """Torneo 1 = 'Copa Ecotec 2026' (05_seed.sql). torneo_admin_headers
    (conftest.py) es un TorneoAdmin SIN ninguna fila en
    ASIGNACION_TORNEO_ADMIN — este es el gap que motivó todo el plan:
    antes de require_torneo_access, esto daba 200."""
    resp = await client.patch(
        "/api/v1/torneos/1", json={"nombre": "Hackeado"}, headers=torneo_admin_headers
    )
    assert resp.status_code == 403
    assert "asignado" in resp.json()["detail"]

    resp = await client.delete("/api/v1/torneos/1", headers=torneo_admin_headers)
    assert resp.status_code == 403


async def test_torneo_admin_con_asignacion_puede_editar_su_torneo(
    client: AsyncClient, torneo_admin_con_torneo_headers: dict[str, str]
):
    resp = await client.patch(
        "/api/v1/torneos/1", json={"nombre": "Copa Ecotec 2026 Editada"}, headers=torneo_admin_con_torneo_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["nombre"] == "Copa Ecotec 2026 Editada"


async def test_admin_general_edita_torneo_sin_asignacion_propia(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    """Bypass total, mismo criterio que require_roles — AdminGeneral no
    necesita fila en ASIGNACION_TORNEO_ADMIN."""
    resp = await client.patch(
        "/api/v1/torneos/1", json={"nombre": "Editado por AdminGeneral"}, headers=admin_general_headers
    )
    assert resp.status_code == 200


async def test_torneo_admin_con_asignacion_a_otro_torneo_no_puede_editar_este(
    client: AsyncClient,
    admin_general_headers: dict[str, str],
    torneo_admin_con_torneo_headers: dict[str, str],
):
    """Asignado al Torneo 1, no a un Torneo 2 recién creado — la
    granularidad es por torneo, no "TorneoAdmin administra todo"."""
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "nombre": "Otro Torneo",
            "disciplina_id": DISCIPLINA_FUTBOL_ID,
            "modalidad_id": MODALIDAD_FUTBOL_11_ID,
            "torneo_grupo_nombre": "Otro Torneo",
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-06-01",
        },
        headers=admin_general_headers,
    )
    otro_torneo_id = resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/torneos/{otro_torneo_id}",
        json={"nombre": "Hackeado"},
        headers=torneo_admin_con_torneo_headers,
    )
    assert resp.status_code == 403


# --- D4: auto-asignación del creador (rbac-licencias-torneos-plan.md, §7) ---


async def test_torneo_admin_creador_queda_auto_asignado(
    client: AsyncClient, admin_general_headers: dict[str, str], torneo_admin_headers: dict[str, str]
):
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "nombre": "Torneo Creado Por TorneoAdmin",
            "disciplina_id": DISCIPLINA_FUTBOL_ID,
            "modalidad_id": MODALIDAD_FUTBOL_11_ID,
            "torneo_grupo_nombre": "Torneo Creado Por TorneoAdmin",
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-06-01",
        },
        headers=torneo_admin_headers,
    )
    assert resp.status_code == 201, resp.text
    torneo_id = resp.json()["id"]

    # Sin auto-asignación, esto daría 403 (mismo test que
    # test_torneo_admin_sin_asignacion_no_puede_editar_torneo_1).
    resp = await client.patch(
        f"/api/v1/torneos/{torneo_id}", json={"nombre": "Editado"}, headers=torneo_admin_headers
    )
    assert resp.status_code == 200, resp.text


async def test_admin_general_creador_no_regresiona(client: AsyncClient, admin_general_headers: dict[str, str]):
    """Corrección post outside-voice (Eng review, hallazgo #3 del plan
    original antes de la corrección): auto-asignar sin el guard de rol
    hacía que esto fallara con un rechazo del trigger de rol — regresión
    sobre un flujo que hoy anda. Con el guard, AdminGeneral crea sin
    auto-asignarse (no necesita fila, tiene bypass total)."""
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "nombre": "Torneo Creado Por AdminGeneral",
            "disciplina_id": DISCIPLINA_FUTBOL_ID,
            "modalidad_id": MODALIDAD_FUTBOL_11_ID,
            "torneo_grupo_nombre": "Torneo Creado Por AdminGeneral",
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-06-01",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text


# --- E1: GET /torneos?solo_mios=true (rbac-licencias-torneos-plan.md) ---


async def test_solo_mios_filtra_a_los_torneos_asignados(
    client: AsyncClient,
    admin_general_headers: dict[str, str],
    torneo_admin_con_torneo_headers: dict[str, str],
):
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "nombre": "Torneo No Asignado",
            "disciplina_id": DISCIPLINA_FUTBOL_ID,
            "modalidad_id": MODALIDAD_FUTBOL_11_ID,
            "torneo_grupo_nombre": "Torneo No Asignado",
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-06-01",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 201

    resp = await client.get(
        "/api/v1/torneos", params={"solo_mios": "true"}, headers=torneo_admin_con_torneo_headers
    )
    assert resp.status_code == 200
    ids = [t["id"] for t in resp.json()]
    assert ids == [1]


async def test_solo_mios_sin_asignaciones_devuelve_lista_vacia(
    client: AsyncClient, torneo_admin_headers: dict[str, str]
):
    resp = await client.get("/api/v1/torneos", params={"solo_mios": "true"}, headers=torneo_admin_headers)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_solo_mios_sin_efecto_para_admin_general_y_anonimo(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    resp_publico = await client.get("/api/v1/torneos", params={"solo_mios": "true"})
    resp_sin_filtro = await client.get("/api/v1/torneos")
    assert [t["id"] for t in resp_publico.json()] == [t["id"] for t in resp_sin_filtro.json()]

    resp_admin = await client.get(
        "/api/v1/torneos", params={"solo_mios": "true"}, headers=admin_general_headers
    )
    assert [t["id"] for t in resp_admin.json()] == [t["id"] for t in resp_sin_filtro.json()]
