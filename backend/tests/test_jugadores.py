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


# Búsqueda server-side por nombre/cédula (gestion-avanzada-equipos-control-
# mesa-plan.md, Requerimiento 2) — 05_seed.sql: Carlos Pérez / 0900000001.
async def test_buscar_jugador_por_nombre_parcial(client: AsyncClient):
    resp = await client.get("/api/v1/jugadores", params={"q": "Pérez"})
    assert resp.status_code == 200
    nombres = [j["nombre"] for j in resp.json()]
    assert "Carlos Pérez" in nombres


async def test_buscar_jugador_por_cedula_parcial(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.get(
        "/api/v1/jugadores", params={"q": "0900000001"}, headers=admin_general_headers
    )
    assert resp.status_code == 200
    cedulas = [j["cedula"] for j in resp.json()]
    assert "0900000001" in cedulas


async def test_buscar_jugador_sin_resultados(client: AsyncClient):
    resp = await client.get("/api/v1/jugadores", params={"q": "nadie-con-este-nombre-existe"})
    assert resp.status_code == 200
    assert resp.json() == []


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


# T30/T31 (motor-formatos-plantillas-navegacion-plan.md): ModalPerfilJugador
# conecta este PATCH, hasta ahora sin ningún test ni consumidor en el
# frontend — Decisión P8 del plan ("está ahí, sin conectar a esta vista").
async def test_admin_edita_datos_personales_del_jugador(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.patch(
        "/api/v1/jugadores/1",
        json={"nombre": "Carlos Pérez Editado", "correo_electronico": "nuevo@example.com"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["nombre"] == "Carlos Pérez Editado"
    assert body["correo_electronico"] == "nuevo@example.com"
    assert body["cedula"] == "0900000001"  # no tocado, sigue igual


async def test_editar_jugador_con_cedula_duplicada_es_rechazado(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    # unique_jugador_cedula: jugador 2 no puede robarle la cédula al 1.
    resp = await client.patch(
        "/api/v1/jugadores/2",
        json={"cedula": "0900000001"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 409


async def test_foto_url_es_opcional_y_editable(client: AsyncClient, admin_general_headers: dict[str, str]):
    # requerimiento #3 del plan: campo de texto (URL), nullable — sin foto
    # seteada por defecto (05_seed.sql no la carga).
    resp = await client.get("/api/v1/jugadores/1", headers=admin_general_headers)
    assert resp.json()["foto_url"] is None

    resp = await client.patch(
        "/api/v1/jugadores/1",
        json={"foto_url": "https://example.com/foto.jpg"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["foto_url"] == "https://example.com/foto.jpg"


async def test_desactivar_jugador_con_membresia_activa_es_rechazado(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    """3B-3 (docs/plans/cierre-backlog-todos-plan.md): Carlos Pérez
    (jugador 1, 05_seed.sql) está Activo en Tiburones FC — desactivarlo lo
    haría desaparecer de los listados mientras el sistema lo sigue
    contando en un roster vigente."""
    resp = await client.delete("/api/v1/jugadores/1", headers=admin_general_headers)
    assert resp.status_code == 409, resp.text
    assert "membresías activas" in resp.json()["detail"].lower()

    resp = await client.get("/api/v1/jugadores/1", headers=admin_general_headers)
    assert resp.json()["estado"] == "Activo"


async def test_desactivar_jugador_sin_membresia_activa_funciona(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    resp = await client.post(
        "/api/v1/jugadores",
        json={"nombre": "Sin Equipo", "cedula": "0977200001", "correo_electronico": "sinequipo@example.com"},
        headers=admin_general_headers,
    )
    jugador_id = resp.json()["id"]

    resp = await client.delete(f"/api/v1/jugadores/{jugador_id}", headers=admin_general_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["estado"] == "Inactivo"
