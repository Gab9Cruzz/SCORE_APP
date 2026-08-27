from httpx import AsyncClient

# 05_seed.sql: torneo 1 = Copa Ecotec 2026 (Fútbol, disciplina_id=1).
# inscripcion 1 = Tiburones FC (Carlos Pérez dorsal10, Luis Andrade dorsal7,
# ambos ya Activo). inscripcion 2 = Águilas del Sur. inscripcion 3 = Halcones.
INSCRIPCION_TIBURONES = 1
INSCRIPCION_AGUILAS = 2
VALIDAR = "/api/v1/plantillas/lote/validar"
CONFIRMAR = "/api/v1/plantillas/lote/confirmar"


def _fila(cedula: str, nombre: str, dorsal: int | None = None, correo: str | None = None) -> dict:
    return {
        "cedula": cedula,
        "nombre": nombre,
        "correo_electronico": correo or f"{cedula}@example.com",
        "dorsal": dorsal,
    }


async def test_ec1_cedula_duplicada_en_el_lote(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.post(
        VALIDAR,
        json={
            "inscripcion_torneo_id": INSCRIPCION_TIBURONES,
            "fecha_inicio": "2026-02-01",
            "filas": [_fila("0977000101", "Fila Uno"), _fila("0977000101", "Fila Uno Otra Vez")],
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["validos"] == []
    assert len(body["invalidos"]) == 2
    assert "duplicada en este mismo lote" in body["invalidos"][0]["motivo"]


async def test_ec2_nombre_no_coincide_con_cedula_registrada(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    # Cédula de Carlos Pérez (05_seed.sql) con un nombre distinto.
    resp = await client.post(
        VALIDAR,
        json={
            "inscripcion_torneo_id": INSCRIPCION_AGUILAS,
            "fecha_inicio": "2026-02-01",
            "filas": [_fila("0900000001", "Nombre Equivocado")],
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["validos"] == []
    assert "no coincide" in body["invalidos"][0]["motivo"]


async def test_ec3_jugador_existente_libre_se_reutiliza(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/jugadores",
        json={"nombre": "Libre Sin Perfil", "cedula": "0977000102", "correo_electronico": "libre@example.com"},
        headers=admin_general_headers,
    )
    jugador_id = resp.json()["id"]

    resp = await client.post(
        VALIDAR,
        json={
            "inscripcion_torneo_id": INSCRIPCION_TIBURONES,
            "fecha_inicio": "2026-02-01",
            "filas": [_fila("0977000102", "Libre Sin Perfil", dorsal=50)],
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["validos"]) == 1
    assert body["validos"][0]["jugador_id"] == jugador_id


async def test_ec4_jugador_existente_nueva_disciplina(client: AsyncClient, admin_general_headers: dict[str, str]):
    # Carlos Pérez (05_seed.sql) ya tiene perfil de Fútbol. Se lo registra
    # en una disciplina nueva (Tenis) — válido, perfil aislado por disciplina.
    resp = await client.post(
        "/api/v1/disciplinas", json={"nombre": "Tenis EC4", "tipo": "Individual"}, headers=admin_general_headers
    )
    disciplina_id = resp.json()["id"]
    resp = await client.post(
        "/api/v1/modalidades",
        json={"disciplina_id": disciplina_id, "nombre": "Individual", "tamano_equipo": 1},
        headers=admin_general_headers,
    )
    modalidad_id = resp.json()["id"]
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "nombre": "Abierto Tenis EC4",
            "disciplina_id": disciplina_id,
            "modalidad_id": modalidad_id,
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-05-10",
        },
        headers=admin_general_headers,
    )
    torneo_id = resp.json()["id"]
    resp = await client.post("/api/v1/equipos", json={"nombre": "Equipo Tenis EC4"}, headers=admin_general_headers)
    equipo_id = resp.json()["id"]
    resp = await client.post(
        "/api/v1/inscripciones",
        json={"torneo_id": torneo_id, "equipo_id": equipo_id},
        headers=admin_general_headers,
    )
    inscripcion_id = resp.json()["id"]

    resp = await client.post(
        VALIDAR,
        json={
            "inscripcion_torneo_id": inscripcion_id,
            "fecha_inicio": "2026-05-01",
            "filas": [_fila("0900000001", "Carlos Pérez")],
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["validos"]) == 1


async def test_ec6_capacidad_de_la_modalidad(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/disciplinas", json={"nombre": "Padel EC6", "tipo": "Individual"}, headers=admin_general_headers
    )
    disciplina_id = resp.json()["id"]
    resp = await client.post(
        "/api/v1/modalidades",
        json={"disciplina_id": disciplina_id, "nombre": "Dobles", "tamano_equipo": 1},
        headers=admin_general_headers,
    )
    modalidad_id = resp.json()["id"]
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "nombre": "Abierto Padel EC6",
            "disciplina_id": disciplina_id,
            "modalidad_id": modalidad_id,
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-05-10",
        },
        headers=admin_general_headers,
    )
    torneo_id = resp.json()["id"]
    resp = await client.post("/api/v1/equipos", json={"nombre": "Equipo Padel EC6"}, headers=admin_general_headers)
    equipo_id = resp.json()["id"]
    resp = await client.post(
        "/api/v1/inscripciones",
        json={"torneo_id": torneo_id, "equipo_id": equipo_id},
        headers=admin_general_headers,
    )
    inscripcion_id = resp.json()["id"]

    resp = await client.post(
        VALIDAR,
        json={
            "inscripcion_torneo_id": inscripcion_id,
            "fecha_inicio": "2026-05-01",
            "filas": [_fila("0977000103", "Cupo Uno"), _fila("0977000104", "Cupo Dos")],
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["validos"]) == 1
    assert len(body["invalidos"]) == 1
    assert "máximo 1 jugadores" in body["invalidos"][0]["motivo"]


async def test_ec9_jugador_suspendido(client: AsyncClient, admin_general_headers: dict[str, str]):
    # Bryan Chávez (jugador 6, 05_seed.sql) ya tiene perfil de Fútbol —
    # se resuelve el id del perfil por API, no se asume el id (el backfill
    # del seed no garantiza 1:1 con el id de jugador).
    resp = await client.get("/api/v1/perfiles", params={"jugador_id": 6, "disciplina_id": 1})
    perfil_id = resp.json()[0]["id"]

    resp = await client.patch(
        f"/api/v1/perfiles/{perfil_id}", json={"suspendido": True}, headers=admin_general_headers
    )
    assert resp.status_code == 200, resp.text

    resp = await client.post(
        VALIDAR,
        json={
            "inscripcion_torneo_id": INSCRIPCION_AGUILAS,
            "fecha_inicio": "2026-02-01",
            "filas": [_fila("0900000006", "Bryan Chávez")],
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["validos"] == []
    assert "suspendido" in body["invalidos"][0]["motivo"].lower()

    # Devuelve el perfil a su estado normal — no ensuciar el resto del run.
    await client.patch(f"/api/v1/perfiles/{perfil_id}", json={"suspendido": False}, headers=admin_general_headers)


async def test_ec13_dorsal_repetido_en_lote_y_en_roster(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.post(
        VALIDAR,
        json={
            "inscripcion_torneo_id": INSCRIPCION_TIBURONES,
            "fecha_inicio": "2026-02-01",
            "filas": [
                _fila("0977000105", "Dorsal Repetido Lote A", dorsal=55),
                _fila("0977000106", "Dorsal Repetido Lote B", dorsal=55),
                _fila("0977000107", "Dorsal Ya En Uso", dorsal=10),  # Carlos Pérez ya tiene el 10 acá
            ],
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # La primera fila con dorsal=55 pasa (nada choca con ella todavía);
    # recién la segunda con el mismo dorsal es la que se marca — orden de
    # llegada, no las dos a la vez.
    assert len(body["validos"]) == 1
    assert body["validos"][0]["cedula"] == "0977000105"
    motivos = {i["motivo"] for i in body["invalidos"]}
    assert any("repetido en este mismo lote" in m for m in motivos)
    assert any("ya está en uso" in m for m in motivos)


async def test_ec18_exclusividad_por_torneo(client: AsyncClient, admin_general_headers: dict[str, str]):
    # Carlos Pérez ya está Activo en Tiburones (inscripcion 1) del torneo 1.
    # Intentar registrarlo en Águilas (inscripcion 2), mismo torneo.
    resp = await client.post(
        VALIDAR,
        json={
            "inscripcion_torneo_id": INSCRIPCION_AGUILAS,
            "fecha_inicio": "2026-02-01",
            "filas": [_fila("0900000001", "Carlos Pérez")],
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["validos"] == []
    assert "Ya juega en" in body["invalidos"][0]["motivo"]
    assert "Tiburones FC" in body["invalidos"][0]["motivo"]


async def test_confirmar_inserta_los_validos(client: AsyncClient, admin_general_headers: dict[str, str]):
    filas = [_fila("0977000108", "Confirmado Uno", dorsal=61), _fila("0977000109", "Confirmado Dos", dorsal=62)]
    resp = await client.post(
        CONFIRMAR,
        json={"inscripcion_torneo_id": INSCRIPCION_TIBURONES, "fecha_inicio": "2026-02-01", "filas": filas},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["insertados"]) == 2
    assert body["rechazados"] == []

    resp = await client.get("/api/v1/jugadores")
    nombres = {j["nombre"] for j in resp.json()}
    assert {"Confirmado Uno", "Confirmado Dos"} <= nombres


async def test_ec7_race_entre_validar_y_confirmar(client: AsyncClient, admin_general_headers: dict[str, str]):
    cedula = "0977000110"
    filas = [_fila(cedula, "Jugador En Carrera", dorsal=63)]

    # 1. Un admin valida — todavía nadie con esta cédula existe, válido.
    resp = await client.post(
        VALIDAR,
        json={"inscripcion_torneo_id": INSCRIPCION_TIBURONES, "fecha_inicio": "2026-02-01", "filas": filas},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["validos"]) == 1

    # 2. "Otro admin" registra esa misma cédula, en OTRO equipo del mismo
    # torneo, por el camino normal — entre el validar y el confirmar del
    # primero.
    resp = await client.post(
        "/api/v1/jugadores",
        json={"nombre": "Jugador En Carrera", "cedula": cedula, "correo_electronico": f"{cedula}@example.com"},
        headers=admin_general_headers,
    )
    jugador_id = resp.json()["id"]
    resp = await client.post(
        "/api/v1/perfiles", json={"jugador_id": jugador_id, "disciplina_id": 1}, headers=admin_general_headers
    )
    perfil_id = resp.json()["id"]
    resp = await client.post(
        "/api/v1/plantillas",
        json={
            "jugador_perfil_id": perfil_id,
            "inscripcion_torneo_id": INSCRIPCION_AGUILAS,
            "dorsal": 64,
            "fecha_inicio": "2026-02-01",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text

    # 3. El primer admin confirma su lote original, sin saber lo anterior —
    # debe rechazar esta fila (exclusividad), no explotar en 500, y no
    # duplicar al jugador.
    resp = await client.post(
        CONFIRMAR,
        json={"inscripcion_torneo_id": INSCRIPCION_TIBURONES, "fecha_inicio": "2026-02-01", "filas": filas},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["insertados"] == []
    assert len(body["rechazados"]) == 1
    assert "Ya juega en" in body["rechazados"][0]["motivo"]


async def test_arbitro_no_puede_validar_lote(client: AsyncClient, arbitro_headers: dict[str, str]):
    resp = await client.post(
        VALIDAR,
        json={"inscripcion_torneo_id": INSCRIPCION_TIBURONES, "fecha_inicio": "2026-02-01", "filas": []},
        headers=arbitro_headers,
    )
    assert resp.status_code == 403


async def test_arbitro_no_puede_confirmar_lote(client: AsyncClient, arbitro_headers: dict[str, str]):
    resp = await client.post(
        CONFIRMAR,
        json={"inscripcion_torneo_id": INSCRIPCION_TIBURONES, "fecha_inicio": "2026-02-01", "filas": []},
        headers=arbitro_headers,
    )
    assert resp.status_code == 403


async def test_validar_con_inscripcion_inexistente(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.post(
        VALIDAR,
        json={"inscripcion_torneo_id": 999999, "fecha_inicio": "2026-02-01", "filas": []},
        headers=admin_general_headers,
    )
    assert resp.status_code == 404


async def test_cedula_con_espacios_se_normaliza(client: AsyncClient, admin_general_headers: dict[str, str]):
    # El registro por lote es la frontera de confianza real: aunque el
    # frontend ya recorta antes de mandar, el backend no debe depender de
    # eso — " 0900000001" (con espacio) debe resolver a Carlos Pérez
    # (cédula 0900000001, 05_seed.sql), no crear un jugador duplicado.
    resp = await client.post(
        VALIDAR,
        json={
            "inscripcion_torneo_id": INSCRIPCION_AGUILAS,
            "fecha_inicio": "2026-02-01",
            "filas": [_fila(" 0900000001", "Carlos Pérez")],
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Carlos Pérez ya está Activo en Tiburones (mismo torneo) — con la
    # cédula bien normalizada, esto debe chocar por exclusividad (EC-18),
    # no colarse como jugador "nuevo" con cédula con espacio.
    assert body["validos"] == []
    assert "Ya juega en" in body["invalidos"][0]["motivo"]
