"""Plantilla Base de equipo (gestion-avanzada-equipos-control-mesa-plan.md,
Decisión D1-C) — banco de candidatos independiente de cualquier torneo.

05_seed.sql: Disciplina 1 = "Fútbol", Modalidad 1 = "Fútbol 11".
"""
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.disciplina import Disciplina
from app.models.modalidad import Modalidad

FUTBOL = {"disciplina_id": 1, "modalidad_id": 1}


async def _crear_disciplina_y_modalidad(
    session: AsyncSession, disciplina: str, modalidad: str, tamano_equipo: int = 5
) -> tuple[int, int]:
    d = Disciplina(nombre=disciplina)
    session.add(d)
    await session.flush()
    m = Modalidad(disciplina_id=d.id, nombre=modalidad, tamano_equipo=tamano_equipo)
    session.add(m)
    await session.commit()
    return d.id, m.id


async def _crear_equipo(client: AsyncClient, headers: dict[str, str], nombre: str) -> int:
    resp = await client.post("/api/v1/equipos", json={"nombre": nombre, **FUTBOL}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _crear_jugador(client: AsyncClient, headers: dict[str, str], nombre: str, cedula: str) -> int:
    resp = await client.post(
        "/api/v1/jugadores",
        json={"nombre": nombre, "cedula": cedula, "correo_electronico": f"{cedula}@example.com"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_plantilla_base_vacia_al_crear_equipo(client: AsyncClient, admin_general_headers: dict[str, str]):
    equipo_id = await _crear_equipo(client, admin_general_headers, "Equipo PB Vacio")
    resp = await client.get(f"/api/v1/equipos/{equipo_id}/plantilla-base", headers=admin_general_headers)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_agregar_y_listar_candidato(client: AsyncClient, admin_general_headers: dict[str, str]):
    equipo_id = await _crear_equipo(client, admin_general_headers, "Equipo PB Agregar")
    jugador_id = await _crear_jugador(client, admin_general_headers, "Juan Pérez PB", "PB-0001")

    resp = await client.post(
        f"/api/v1/equipos/{equipo_id}/plantilla-base",
        json={"jugador_id": jugador_id, "dorsal_sugerido": 10},
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["jugador_id"] == jugador_id
    assert body["jugador_nombre"] == "Juan Pérez PB"
    assert body["jugador_cedula"] == "PB-0001"
    assert body["dorsal_sugerido"] == 10
    assert body["estado"] == "Activo"

    resp = await client.get(f"/api/v1/equipos/{equipo_id}/plantilla-base", headers=admin_general_headers)
    assert len(resp.json()) == 1


# EC-2: el mismo jugador dos veces en la MISMA plantilla base se bloquea
# con un mensaje distinto al de multimilitancia.
async def test_ec2_duplicado_en_la_misma_plantilla_es_rechazado(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    equipo_id = await _crear_equipo(client, admin_general_headers, "Equipo PB EC2")
    jugador_id = await _crear_jugador(client, admin_general_headers, "Jugador EC2", "PB-EC2")

    resp = await client.post(
        f"/api/v1/equipos/{equipo_id}/plantilla-base",
        json={"jugador_id": jugador_id},
        headers=admin_general_headers,
    )
    assert resp.status_code == 201

    resp = await client.post(
        f"/api/v1/equipos/{equipo_id}/plantilla-base",
        json={"jugador_id": jugador_id},
        headers=admin_general_headers,
    )
    assert resp.status_code == 400
    assert "ya está en la plantilla" in resp.json()["detail"].lower()


# EC-3: quitar de la Plantilla Base es baja lógica — reactivar (no
# re-insertar) al agregar de nuevo, porque unique_equipo_jugador_base es
# incondicional.
async def test_quitar_y_reagregar_reactiva_la_fila(client: AsyncClient, admin_general_headers: dict[str, str]):
    equipo_id = await _crear_equipo(client, admin_general_headers, "Equipo PB Reactivar")
    jugador_id = await _crear_jugador(client, admin_general_headers, "Jugador Reactivar", "PB-REACT")

    resp = await client.post(
        f"/api/v1/equipos/{equipo_id}/plantilla-base",
        json={"jugador_id": jugador_id},
        headers=admin_general_headers,
    )
    item_id = resp.json()["id"]

    resp = await client.delete(
        f"/api/v1/equipos/{equipo_id}/plantilla-base/{item_id}", headers=admin_general_headers
    )
    assert resp.status_code == 200
    assert resp.json()["estado"] == "Inactivo"

    resp = await client.get(f"/api/v1/equipos/{equipo_id}/plantilla-base", headers=admin_general_headers)
    assert resp.json() == []

    resp = await client.post(
        f"/api/v1/equipos/{equipo_id}/plantilla-base",
        json={"jugador_id": jugador_id, "dorsal_sugerido": 7},
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["id"] == item_id  # misma fila reactivada
    assert resp.json()["estado"] == "Activo"


# EC-1: mismo jugador en la Plantilla Base de 2 equipos de disciplinas
# distintas NO es multimilitancia (el chequeo filtra por perfil, que ya es
# específico de una disciplina).
async def test_ec1_disciplinas_distintas_no_es_multimilitancia(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    resp = await client.post(
        "/api/v1/equipos",
        json={"nombre": "Torre Blanca EC1", "disciplina_id": 1, "modalidad_id": 1},
        headers=admin_general_headers,
    )
    equipo_futbol = resp.json()["id"]

    disciplina_tenis, modalidad_tenis = await _crear_disciplina_y_modalidad(
        db_session, "Tenis EC1", "Individual EC1", tamano_equipo=1
    )
    resp = await client.post(
        "/api/v1/equipos",
        json={"nombre": "Torre Blanca Tenis EC1", "disciplina_id": disciplina_tenis, "modalidad_id": modalidad_tenis},
        headers=admin_general_headers,
    )
    equipo_tenis = resp.json()["id"]

    jugador_id = await _crear_jugador(client, admin_general_headers, "Jugador EC1", "PB-EC1")

    resp = await client.post(
        f"/api/v1/equipos/{equipo_futbol}/plantilla-base",
        json={"jugador_id": jugador_id},
        headers=admin_general_headers,
    )
    assert resp.status_code == 201

    resp = await client.get(
        f"/api/v1/equipos/{equipo_tenis}/plantilla-base/verificar",
        params={"jugador_id": jugador_id},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["conflicto"] is False


# Flujo 2: multimilitancia real (mismo perfil de disciplina en otro
# equipo) — no bloqueante, solo informa.
async def test_verificar_multimilitancia_detecta_conflicto(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    equipo_a = await _crear_equipo(client, admin_general_headers, "Deportivo Norte MM")
    equipo_b = await _crear_equipo(client, admin_general_headers, "Los Halcones MM")
    jugador_id = await _crear_jugador(client, admin_general_headers, "Juan Perez MM", "PB-MM")

    resp = await client.post(
        f"/api/v1/equipos/{equipo_a}/plantilla-base",
        json={"jugador_id": jugador_id},
        headers=admin_general_headers,
    )
    assert resp.status_code == 201

    resp = await client.get(
        f"/api/v1/equipos/{equipo_b}/plantilla-base/verificar",
        params={"jugador_id": jugador_id},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["conflicto"] is True
    assert "Deportivo Norte MM" in body["equipos"]
    # El texto es el literal del Algoritmo de Multimilitancia del plan
    # (Nivel 1) — genérico ("Este jugador..."), la UI antepone el nombre
    # al mostrarlo (ya lo tiene del resultado de búsqueda).
    assert "Deportivo Norte MM" in body["mensaje"]
    assert "desvinculado" in body["mensaje"]

    # Y agregar igual al segundo equipo NUNCA se bloquea (Nivel 1 no es
    # bloqueante) — el llamador (POST) siempre procede.
    resp = await client.post(
        f"/api/v1/equipos/{equipo_b}/plantilla-base",
        json={"jugador_id": jugador_id},
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
