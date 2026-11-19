"""TASK-014 (SEC-05, SEC-07).

- Cédula y correo solo para roles de gestión (TorneoAdmin, AdminGeneral),
  no para "cualquiera con sesión": Publico y Arbitro reciben la proyección
  sin datos personales, y sin ese permiso la búsqueda no mira la cédula.
- Un anónimo no reconstruye un torneo no publicado por sus sub-recursos
  (inscripciones, plantillas, traspasos, ediciones de un grupo).
- La superficie de partido por ID queda como está (decisión C17).
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inscripcion_torneo import InscripcionTorneo
from app.models.jugador import Jugador
from app.models.jugador_equipo import JugadorEquipo
from app.models.jugador_perfil_disciplina import JugadorPerfilDisciplina
from tests.conftest import _crear_usuario, _login_headers


@pytest.fixture
async def publico_headers(db_session: AsyncSession, client: AsyncClient) -> dict[str, str]:
    await _crear_usuario(db_session, "publico_test", "publicopass123", "Publico")
    return await _login_headers(client, "publico_test", "publicopass123")


async def _cedula_de_jugador_1(client: AsyncClient, admin_general_headers: dict[str, str]) -> str:
    resp = await client.get("/api/v1/jugadores/1", headers=admin_general_headers)
    return resp.json()["cedula"]


# ---------- Datos personales ----------


async def test_anonimo_no_encuentra_a_nadie_por_cedula(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    """PR-036."""
    cedula = await _cedula_de_jugador_1(client, admin_general_headers)
    resp = await client.get("/api/v1/jugadores", params={"q": cedula})
    assert resp.status_code == 200
    assert resp.json() == []


async def test_anonimo_sigue_buscando_por_nombre(client: AsyncClient, admin_general_headers: dict[str, str]):
    nombre = (await client.get("/api/v1/jugadores/1", headers=admin_general_headers)).json()["nombre"]
    resp = await client.get("/api/v1/jugadores", params={"q": nombre.split()[0]})
    assert 1 in [j["id"] for j in resp.json()]
    assert all("cedula" not in j for j in resp.json())


async def _sin_datos_personales(client: AsyncClient, admin_general_headers: dict[str, str], headers: dict[str, str]):
    for ruta in ("/api/v1/jugadores/1", "/api/v1/jugadores/1/perfil"):
        cuerpo = (await client.get(ruta, headers=headers)).json()
        assert "cedula" not in cuerpo and "correo_electronico" not in cuerpo, ruta
    filas = (await client.get("/api/v1/jugadores", headers=headers)).json()
    assert filas and all("cedula" not in j for j in filas)

    cedula = await _cedula_de_jugador_1(client, admin_general_headers)
    assert (await client.get("/api/v1/jugadores", params={"q": cedula}, headers=headers)).json() == []


async def test_publico_no_recibe_cedula_ni_correo(
    client: AsyncClient, admin_general_headers: dict[str, str], publico_headers: dict[str, str]
):
    """PR-037."""
    await _sin_datos_personales(client, admin_general_headers, publico_headers)


async def test_arbitro_no_recibe_cedula_ni_correo(
    client: AsyncClient, admin_general_headers: dict[str, str], arbitro_headers: dict[str, str]
):
    """PR-037."""
    await _sin_datos_personales(client, admin_general_headers, arbitro_headers)


async def test_roles_de_gestion_ven_los_datos_y_buscan_por_cedula(
    client: AsyncClient, admin_general_headers: dict[str, str], torneo_admin_headers: dict[str, str]
):
    cedula = await _cedula_de_jugador_1(client, admin_general_headers)
    cuerpo = (await client.get("/api/v1/jugadores/1", headers=torneo_admin_headers)).json()
    assert cuerpo["cedula"] == cedula
    resp = await client.get("/api/v1/jugadores", params={"q": cedula}, headers=torneo_admin_headers)
    assert [j["id"] for j in resp.json()] == [1]


# ---------- Torneos no publicados ----------


@pytest.fixture
async def torneo_borrador(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
) -> dict:
    """Torneo no publicado con un equipo inscripto y un jugador en plantilla."""
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "torneo_grupo_nombre": "Borrador Privado",
            "disciplina_id": 1,
            "modalidad_id": 1,
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-06-01",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    torneo = resp.json()
    assert torneo["publicado"] is False
    resp = await client.post(
        "/api/v1/inscripciones", json={"torneo_id": torneo["id"], "equipo_id": 1}, headers=admin_general_headers
    )
    assert resp.status_code == 201, resp.text
    inscripcion_id = resp.json()["id"]

    jugador = Jugador(nombre="Solo Borrador", cedula="BORR-0001", correo_electronico="borr@test.com")
    db_session.add(jugador)
    await db_session.flush()
    perfil = JugadorPerfilDisciplina(jugador_id=jugador.id, disciplina_id=1)
    db_session.add(perfil)
    await db_session.flush()
    db_session.add(
        JugadorEquipo(jugador_perfil_id=perfil.id, inscripcion_torneo_id=inscripcion_id, fecha_inicio="2026-05-01")
    )
    await db_session.commit()
    return {**torneo, "inscripcion_id": inscripcion_id, "perfil_id": perfil.id}


@pytest.mark.parametrize("ruta", ["/api/v1/inscripciones", "/api/v1/plantillas", "/api/v1/traspasos"])
async def test_anonimo_no_lista_sub_recursos_de_un_torneo_no_publicado(
    client: AsyncClient, torneo_borrador: dict, ruta: str
):
    """PR-038."""
    resp = await client.get(ruta, params={"torneo_id": torneo_borrador["id"]})
    assert resp.status_code == 200, resp.text
    assert resp.json() == []
    assert resp.headers["X-Total-Count"] == "0"


async def test_anonimo_tampoco_los_obtiene_sin_filtrar_por_torneo(client: AsyncClient, torneo_borrador: dict):
    inscripciones = (await client.get("/api/v1/inscripciones", params={"limit": 200})).json()
    assert torneo_borrador["inscripcion_id"] not in [i["id"] for i in inscripciones]
    plantilla = (await client.get("/api/v1/plantillas", params={"jugador_perfil_id": torneo_borrador["perfil_id"]})).json()
    assert plantilla == []


async def test_con_sesion_se_ven_igual(
    client: AsyncClient, torneo_borrador: dict, admin_general_headers: dict[str, str]
):
    h = admin_general_headers
    assert len((await client.get("/api/v1/inscripciones", params={"torneo_id": torneo_borrador["id"]}, headers=h)).json()) == 1
    assert len((await client.get("/api/v1/plantillas", params={"torneo_id": torneo_borrador["id"]}, headers=h)).json()) == 1


async def test_los_torneos_publicados_siguen_visibles_para_anonimo(client: AsyncClient):
    """El torneo 1 de 05_seed.sql está publicado."""
    assert len((await client.get("/api/v1/inscripciones", params={"torneo_id": 1})).json()) == 3
    assert len((await client.get("/api/v1/plantillas", params={"torneo_id": 1})).json()) == 6


async def test_grupo_con_solo_ediciones_no_publicadas_no_aparece_para_anonimo(
    client: AsyncClient, torneo_borrador: dict, admin_general_headers: dict[str, str]
):
    grupo_id = torneo_borrador["torneo_grupo_id"]
    anonimo = [g["id"] for g in (await client.get("/api/v1/torneo-grupos")).json()]
    assert grupo_id not in anonimo
    assert (await client.get(f"/api/v1/torneo-grupos/{grupo_id}")).status_code == 404

    con_sesion = [g["id"] for g in (await client.get("/api/v1/torneo-grupos", headers=admin_general_headers)).json()]
    assert grupo_id in con_sesion
    resp = await client.get(f"/api/v1/torneo-grupos/{grupo_id}", headers=admin_general_headers)
    assert resp.status_code == 200 and len(resp.json()["ediciones"]) == 1


async def test_grupo_publicado_oculta_al_anonimo_sus_ediciones_en_borrador(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    """Copa Ecotec (grupo 1) tiene la edición 1 publicada; una edición nueva
    nace en borrador y el anónimo no la ve."""
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "torneo_grupo_id": 1,
            "disciplina_id": 1,
            "modalidad_id": 1,
            "fecha_inicio": "2027-01-10",
            "fecha_fin": "2027-03-30",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    nueva = resp.json()["id"]
    ediciones = (await client.get("/api/v1/torneo-grupos/1")).json()["ediciones"]
    assert nueva not in [e["id"] for e in ediciones]
    assert 1 in [e["id"] for e in ediciones]
