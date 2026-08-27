from httpx import AsyncClient


async def test_listar_jugadores_es_publico(client: AsyncClient):
    # 05_seed.sql carga 6 jugadores.
    resp = await client.get("/api/v1/jugadores")
    assert resp.status_code == 200
    assert len(resp.json()) >= 6


async def test_listar_jugadores_anonimo_no_ve_pii(client: AsyncClient):
    # Security review de equipos-jugadores-plan.md, Fase 3: el GET sigue
    # siendo público, pero un caller sin token ya no debe recibir cédula ni
    # correo de nadie — antes de esta corrección, JugadorOut (con PII) se
    # devolvía tal cual a cualquiera.
    resp = await client.get("/api/v1/jugadores")
    assert resp.status_code == 200
    for jugador in resp.json():
        assert "cedula" not in jugador
        assert "correo_electronico" not in jugador
        assert "nombre" in jugador  # el nombre sí sigue siendo público


async def test_obtener_jugador_anonimo_no_ve_pii(client: AsyncClient):
    resp = await client.get("/api/v1/jugadores/1")
    assert resp.status_code == 200
    body = resp.json()
    assert "cedula" not in body
    assert "correo_electronico" not in body


async def test_listar_jugadores_autenticado_si_ve_pii(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    # El frontend admin (ya logueado) sigue viendo los datos completos en la
    # misma ruta — no hizo falta un endpoint aparte.
    resp = await client.get("/api/v1/jugadores", headers=admin_general_headers)
    assert resp.status_code == 200
    carlos = next(j for j in resp.json() if j["nombre"] == "Carlos Pérez")
    assert carlos["cedula"] == "0900000001"
    assert carlos["correo_electronico"] == "carlos.perez@example.com"


async def test_admin_crea_jugador(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/jugadores",
        json={
            "nombre": "Jugador Nuevo",
            "cedula": "0999999999",
            "correo_electronico": "jugador.nuevo@example.com",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["estado"] == "Activo"


async def test_cedula_duplicada_es_rechazada(client: AsyncClient, admin_general_headers: dict[str, str]):
    # unique_jugador_cedula (02_constraints.sql): la cédula 0900000001 ya
    # la tiene Carlos Pérez (05_seed.sql).
    resp = await client.post(
        "/api/v1/jugadores",
        json={
            "nombre": "Otro Carlos",
            "cedula": "0900000001",
            "correo_electronico": "otro.carlos@example.com",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 409
