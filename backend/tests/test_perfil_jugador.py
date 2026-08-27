from httpx import AsyncClient

# 05_seed.sql: Carlos Pérez (jugador 1) está Activo en Tiburones FC
# (inscripcion 1, torneo 1, Fútbol), dorsal 10, y anotó 1 gol (evento del
# partido 1).
INSCRIPCION_TIBURONES = 1
INSCRIPCION_AGUILAS = 2


async def test_perfil_con_estado_activo_goles_y_equipo(client: AsyncClient):
    resp = await client.get("/api/v1/jugadores/1/perfil")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["nombre"] == "Carlos Pérez"
    assert len(body["disciplinas"]) == 1


async def test_perfil_anonimo_no_ve_pii(client: AsyncClient):
    # Security review de equipos-jugadores-plan.md, Fase 3: sigue siendo
    # público, pero ya no filtra cédula/correo a un caller sin token.
    resp = await client.get("/api/v1/jugadores/1/perfil")
    assert resp.status_code == 200
    body = resp.json()
    assert "cedula" not in body
    assert "correo_electronico" not in body
    assert body["disciplinas"]  # el resto del perfil sigue disponible


async def test_perfil_autenticado_si_ve_pii(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.get("/api/v1/jugadores/1/perfil", headers=admin_general_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["cedula"] == "0900000001"
    assert body["correo_electronico"] == "carlos.perez@example.com"

    futbol = body["disciplinas"][0]
    assert futbol["disciplina"] == "Fútbol"
    assert futbol["estado"] == "Activo"
    assert futbol["goles_totales"] == 1
    assert len(futbol["equipos_activos"]) == 1
    assert futbol["equipos_activos"][0]["equipo"] == "Tiburones FC"
    assert futbol["equipos_activos"][0]["dorsal"] == 10
    assert futbol["trayectoria"] == []


async def test_perfil_libre_sin_membresia(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/jugadores",
        json={"nombre": "Jugador Libre Perfil", "cedula": "0955500010", "correo_electronico": "libre@example.com"},
        headers=admin_general_headers,
    )
    jugador_id = resp.json()["id"]
    resp = await client.post(
        "/api/v1/perfiles", json={"jugador_id": jugador_id, "disciplina_id": 1}, headers=admin_general_headers
    )

    resp = await client.get(f"/api/v1/jugadores/{jugador_id}/perfil")
    assert resp.status_code == 200, resp.text
    futbol = resp.json()["disciplinas"][0]
    assert futbol["estado"] == "Libre"
    assert futbol["goles_totales"] == 0
    assert futbol["equipos_activos"] == []


async def test_perfil_suspendido(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.get("/api/v1/perfiles", params={"jugador_id": 2, "disciplina_id": 1})
    perfil_id = resp.json()[0]["id"]
    await client.patch(f"/api/v1/perfiles/{perfil_id}", json={"suspendido": True}, headers=admin_general_headers)

    resp = await client.get("/api/v1/jugadores/2/perfil")
    assert resp.status_code == 200, resp.text
    assert resp.json()["disciplinas"][0]["estado"] == "Suspendido"

    await client.patch(f"/api/v1/perfiles/{perfil_id}", json={"suspendido": False}, headers=admin_general_headers)


async def test_perfil_con_trayectoria_de_traspaso(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.get("/api/v1/perfiles", params={"jugador_id": 1, "disciplina_id": 1})
    perfil_id = resp.json()[0]["id"]

    resp = await client.post(
        "/api/v1/traspasos",
        json={
            "jugador_perfil_id": perfil_id,
            "inscripcion_origen_id": INSCRIPCION_TIBURONES,
            "inscripcion_destino_id": INSCRIPCION_AGUILAS,
            "motivo": "Prueba perfil",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text

    resp = await client.get("/api/v1/jugadores/1/perfil")
    assert resp.status_code == 200, resp.text
    futbol = resp.json()["disciplinas"][0]
    assert len(futbol["trayectoria"]) == 1
    trayecto = futbol["trayectoria"][0]
    assert "Tiburones FC" in trayecto["origen"]
    assert "Águilas del Sur" in trayecto["destino"]
    assert trayecto["motivo"] == "Prueba perfil"
    assert trayecto["estado"] == "Completado"
    # El roster se movió con el traspaso — el equipo activo ahora es el
    # destino, no el origen.
    assert futbol["equipos_activos"][0]["equipo"] == "Águilas del Sur"


async def test_perfiles_de_dos_disciplinas_no_se_mezclan(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/disciplinas", json={"nombre": "Tenis Perfil", "tipo": "Individual"}, headers=admin_general_headers
    )
    disciplina_id = resp.json()["id"]

    resp = await client.post(
        "/api/v1/perfiles", json={"jugador_id": 1, "disciplina_id": disciplina_id}, headers=admin_general_headers
    )
    assert resp.status_code == 201, resp.text

    resp = await client.get("/api/v1/jugadores/1/perfil")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["disciplinas"]) == 2

    por_disciplina = {d["disciplina"]: d for d in body["disciplinas"]}
    assert por_disciplina["Fútbol"]["goles_totales"] == 1
    # El perfil de Tenis es nuevo, sin membresías ni goles — no se mezcla
    # con el gol de Fútbol de la misma persona.
    assert por_disciplina["Tenis Perfil"]["goles_totales"] == 0
    assert por_disciplina["Tenis Perfil"]["estado"] == "Libre"
