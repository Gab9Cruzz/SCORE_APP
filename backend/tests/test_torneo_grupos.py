from httpx import AsyncClient


async def test_listar_torneo_grupos_incluye_ediciones(client: AsyncClient):
    # 05_seed.sql: grupo "Copa Ecotec" con una sola edición ("Copa Ecotec 2026").
    resp = await client.get("/api/v1/torneo-grupos")
    assert resp.status_code == 200
    grupo = next(g for g in resp.json() if g["nombre"] == "Copa Ecotec")
    assert len(grupo["ediciones"]) == 1
    assert grupo["ediciones"][0]["numero_edicion"] == 1


async def test_renombrar_torneo_grupo(client: AsyncClient, admin_general_headers: dict[str, str]):
    # EC-25 del plan: renombrar un grupo alcanza a todas sus ediciones sin
    # tocar ninguna fila de TORNEO — el nombre se compone en runtime.
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "nombre": "Torneo Original Ed. 1",
            "disciplina_id": 1,
            "modalidad_id": 1,  # "Fútbol 11" (05_seed.sql)
            "torneo_grupo_nombre": "Nombre Original",
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-06-01",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    grupo_id = resp.json()["torneo_grupo_id"]

    resp = await client.patch(
        f"/api/v1/torneo-grupos/{grupo_id}",
        json={"nombre": "Nombre Renombrado"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["nombre"] == "Nombre Renombrado"

    resp = await client.get("/api/v1/torneo-grupos")
    grupo = next(g for g in resp.json() if g["id"] == grupo_id)
    assert grupo["nombre"] == "Nombre Renombrado"


async def test_renombrar_torneo_grupo_sin_auth_falla(client: AsyncClient):
    resp = await client.patch("/api/v1/torneo-grupos/1", json={"nombre": "Hackeado"})
    assert resp.status_code == 401


async def test_torneo_grupo_inexistente_da_404(client: AsyncClient):
    resp = await client.get("/api/v1/torneo-grupos/999999")
    assert resp.status_code == 404


async def test_obtener_torneo_grupo_por_id_incluye_ediciones(client: AsyncClient):
    # Seguimiento a ediciones-catalogo-disciplinas-plan.md: "Ver Torneo"
    # necesita las ediciones del grupo para el selector, no solo el
    # nombre — GET /torneo-grupos/{id} pasó a devolver el mismo shape que
    # el listado (TorneoGrupoConEdiciones).
    resp = await client.get("/api/v1/torneo-grupos/1")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["nombre"] == "Copa Ecotec"
    assert len(body["ediciones"]) == 1
    assert body["ediciones"][0]["numero_edicion"] == 1


async def test_ec23_jugador_activo_en_dos_ediciones_del_mismo_grupo_simultaneamente(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    """EC-23 del plan (torneos-admin-plan.md, "Diagrama de pruebas"): el
    escenario de Micky — activo en la Edición 1 y la Edición 2 de la
    misma Liga (mismo TORNEO_GRUPO, misma disciplina) a la vez, en dos
    equipos distintos. Confirma que agregar TORNEO_GRUPO es puramente
    organizativo: fn_validar_exclusividad_torneo (06_triggers.sql) evalúa
    por Torneo_ID, y dos ediciones del mismo grupo son Torneo_ID distintos
    — el trigger no necesitó ningún cambio para esto."""
    edicion1 = await client.post(
        "/api/v1/torneos",
        json={
            "disciplina_id": 1,  # Fútbol (05_seed.sql)
            "modalidad_id": 1,  # "Fútbol 11" (05_seed.sql)
            "torneo_grupo_nombre": "Liga Relámpago EC23",
            "fecha_inicio": "2026-03-01",
            "fecha_fin": "2026-05-15",
        },
        headers=admin_general_headers,
    )
    assert edicion1.status_code == 201, edicion1.text
    grupo_id = edicion1.json()["torneo_grupo_id"]

    edicion2 = await client.post(
        "/api/v1/torneos",
        json={
            "torneo_grupo_id": grupo_id,
            "fecha_inicio": "2026-04-01",
            "fecha_fin": "2026-06-30",
        },
        headers=admin_general_headers,
    )
    assert edicion2.status_code == 201, edicion2.text
    assert edicion1.json()["id"] != edicion2.json()["id"]  # Torneo_ID distinto, mismo grupo

    equipo_halcones = await client.post(
        "/api/v1/equipos", json={"nombre": "Halcones FC EC23", "disciplina_id": 1, "modalidad_id": 1}, headers=admin_general_headers
    )
    equipo_tiburones = await client.post(
        "/api/v1/equipos", json={"nombre": "Tiburones FC EC23", "disciplina_id": 1, "modalidad_id": 1}, headers=admin_general_headers
    )

    inscripcion1 = await client.post(
        "/api/v1/inscripciones",
        json={"torneo_id": edicion1.json()["id"], "equipo_id": equipo_halcones.json()["id"]},
        headers=admin_general_headers,
    )
    inscripcion2 = await client.post(
        "/api/v1/inscripciones",
        json={"torneo_id": edicion2.json()["id"], "equipo_id": equipo_tiburones.json()["id"]},
        headers=admin_general_headers,
    )

    micky = await client.post(
        "/api/v1/jugadores",
        json={"nombre": "Micky Fernández", "cedula": "0102030405", "correo_electronico": "micky@example.com"},
        headers=admin_general_headers,
    )
    perfil = await client.post(
        "/api/v1/perfiles",
        json={"jugador_id": micky.json()["id"], "disciplina_id": 1},
        headers=admin_general_headers,
    )
    perfil_id = perfil.json()["id"]

    # Activo en Halcones FC (Edición 1)...
    resp1 = await client.post(
        "/api/v1/plantillas",
        json={
            "jugador_perfil_id": perfil_id,
            "inscripcion_torneo_id": inscripcion1.json()["id"],
            "dorsal": 9,
            "fecha_inicio": "2026-03-01",
        },
        headers=admin_general_headers,
    )
    assert resp1.status_code == 201, resp1.text

    # ...y a la vez Activo en Tiburones FC (Edición 2) — distinto Torneo_ID,
    # el trigger no lo rechaza aunque sea la misma disciplina y el mismo
    # TORNEO_GRUPO.
    resp2 = await client.post(
        "/api/v1/plantillas",
        json={
            "jugador_perfil_id": perfil_id,
            "inscripcion_torneo_id": inscripcion2.json()["id"],
            "dorsal": 21,
            "fecha_inicio": "2026-04-01",
        },
        headers=admin_general_headers,
    )
    assert resp2.status_code == 201, resp2.text
    assert resp1.json()["estado"] == "Activo"
    assert resp2.json()["estado"] == "Activo"

    # Contraparte esperada (ya cubierta en test_plantillas.py, se repite
    # acá para dejar el contraste explícito en el mismo test): un TERCER
    # equipo dentro de la MISMA edición (Edición 2) sí debe rechazarse.
    equipo_aguilas = await client.post(
        "/api/v1/equipos", json={"nombre": "Águilas EC23", "disciplina_id": 1, "modalidad_id": 1}, headers=admin_general_headers
    )
    inscripcion3 = await client.post(
        "/api/v1/inscripciones",
        json={"torneo_id": edicion2.json()["id"], "equipo_id": equipo_aguilas.json()["id"]},
        headers=admin_general_headers,
    )
    resp3 = await client.post(
        "/api/v1/plantillas",
        json={
            "jugador_perfil_id": perfil_id,
            "inscripcion_torneo_id": inscripcion3.json()["id"],
            "dorsal": 7,
            "fecha_inicio": "2026-04-01",
        },
        headers=admin_general_headers,
    )
    assert resp3.status_code == 400, resp3.text
