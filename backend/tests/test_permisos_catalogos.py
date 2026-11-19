"""TASK-013 (SEC-04). Decisión del propietario (2026-11-18): equipos y
jugadores son un catálogo COMPARTIDO entre organizadores.

- Disciplinas, modalidades y tipos de evento: solo AdminGeneral escribe
  (afectan a todos los torneos; renombrar "Gol" ponía en cero todos los
  marcadores, FUN-14).
- Grupos de torneo: hace falta administrar alguna de sus ediciones.
- Equipos, jugadores y perfiles: cualquiera los crea y edita, pero las
  acciones destructivas (baja, cambio de estado, suspensión) exigen
  administrar TODOS los torneos abiertos donde participan.

05_seed.sql: grupo 1 "Copa Ecotec" con el torneo 1 (en curso); equipos 1-3
inscriptos ahí; jugadores 1-6 en sus plantillas (perfiles 1-6).
`torneo_admin_headers` no tiene torneos; `torneo_admin_con_torneo_headers`
tiene el torneo 1.
"""
import pytest
from httpx import AsyncClient


# ---------- Grupos de torneo ----------


@pytest.mark.parametrize("cuerpo", [{"estado": "Archivado"}, {"nombre": "Copa Ajena"}])
async def test_torneo_admin_sin_ediciones_del_grupo_no_lo_modifica(
    client: AsyncClient, torneo_admin_headers: dict[str, str], cuerpo: dict
):
    """PR-033."""
    resp = await client.patch("/api/v1/torneo-grupos/1", json=cuerpo, headers=torneo_admin_headers)
    assert resp.status_code == 403, resp.text


async def test_torneo_admin_con_una_edicion_del_grupo_lo_renombra(
    client: AsyncClient, torneo_admin_con_torneo_headers: dict[str, str]
):
    resp = await client.patch(
        "/api/v1/torneo-grupos/1", json={"nombre": "Copa Ecotec Renombrada"}, headers=torneo_admin_con_torneo_headers
    )
    assert resp.status_code == 200, resp.text


async def test_quien_creo_el_torneo_sigue_renombrando_su_grupo(
    client: AsyncClient, torneo_admin_headers: dict[str, str]
):
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "torneo_grupo_nombre": "Liga Propia",
            "disciplina_id": 1,
            "modalidad_id": 1,
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-06-01",
        },
        headers=torneo_admin_headers,
    )
    assert resp.status_code == 201, resp.text
    grupo_id = resp.json()["torneo_grupo_id"]

    resp = await client.patch(
        f"/api/v1/torneo-grupos/{grupo_id}", json={"nombre": "Liga Propia 2"}, headers=torneo_admin_headers
    )
    assert resp.status_code == 200, resp.text


async def test_admin_general_modifica_cualquier_grupo(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.patch("/api/v1/torneo-grupos/1", json={"nombre": "Por AdminGeneral"}, headers=admin_general_headers)
    assert resp.status_code == 200, resp.text


# ---------- Catálogos de sistema: disciplinas, modalidades, eventos ----------


async def test_torneo_admin_no_escribe_tipos_de_evento(
    client: AsyncClient, torneo_admin_con_torneo_headers: dict[str, str]
):
    """PR-034: ni siquiera con torneos asignados."""
    h = torneo_admin_con_torneo_headers
    assert (await client.post("/api/v1/eventos", json={"nombre": "Falta"}, headers=h)).status_code == 403
    assert (await client.patch("/api/v1/eventos/1", json={"nombre": "Gol ⚽"}, headers=h)).status_code == 403
    assert (await client.delete("/api/v1/eventos/1", headers=h)).status_code == 403


async def test_torneo_admin_no_edita_disciplinas_ni_modalidades(
    client: AsyncClient, torneo_admin_con_torneo_headers: dict[str, str]
):
    h = torneo_admin_con_torneo_headers
    assert (await client.patch("/api/v1/disciplinas/1", json={"nombre": "Fútbol X"}, headers=h)).status_code == 403
    assert (await client.patch("/api/v1/modalidades/1", json={"nombre": "Fútbol 12"}, headers=h)).status_code == 403


async def test_admin_general_escribe_los_catalogos_de_sistema(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    h = admin_general_headers
    resp = await client.post("/api/v1/eventos", json={"nombre": "Falta", "descripcion": "Falta"}, headers=h)
    assert resp.status_code == 201, resp.text
    resp = await client.patch("/api/v1/modalidades/1", json={"estado": "Activo"}, headers=h)
    assert resp.status_code == 200, resp.text


# ---------- Equipos y jugadores: compartidos, bajas acotadas ----------


async def test_equipos_y_jugadores_siguen_siendo_compartidos_para_editar(
    client: AsyncClient, torneo_admin_headers: dict[str, str]
):
    resp = await client.patch("/api/v1/equipos/1", json={"nombre": "Tiburones FC"}, headers=torneo_admin_headers)
    assert resp.status_code == 200, resp.text
    resp = await client.patch("/api/v1/jugadores/1", json={"nombre": "Carlos Pérez"}, headers=torneo_admin_headers)
    assert resp.status_code == 200, resp.text


async def test_baja_de_equipo_que_juega_un_torneo_ajeno_es_403(
    client: AsyncClient, torneo_admin_headers: dict[str, str]
):
    assert (await client.delete("/api/v1/equipos/1", headers=torneo_admin_headers)).status_code == 403
    resp = await client.patch("/api/v1/equipos/1", json={"estado": "Inactivo"}, headers=torneo_admin_headers)
    assert resp.status_code == 403, resp.text


async def test_baja_de_jugador_que_juega_un_torneo_ajeno_es_403(
    client: AsyncClient, torneo_admin_headers: dict[str, str]
):
    assert (await client.delete("/api/v1/jugadores/1", headers=torneo_admin_headers)).status_code == 403
    resp = await client.patch("/api/v1/jugadores/1", json={"estado": "Inactivo"}, headers=torneo_admin_headers)
    assert resp.status_code == 403, resp.text


async def test_suspender_un_perfil_que_juega_un_torneo_ajeno_es_403(
    client: AsyncClient, torneo_admin_headers: dict[str, str]
):
    resp = await client.patch("/api/v1/perfiles/1", json={"suspendido": True}, headers=torneo_admin_headers)
    assert resp.status_code == 403, resp.text


async def test_quien_administra_el_torneo_puede_dar_bajas_y_suspender(
    client: AsyncClient, torneo_admin_con_torneo_headers: dict[str, str]
):
    h = torneo_admin_con_torneo_headers
    resp = await client.patch("/api/v1/perfiles/1", json={"suspendido": True}, headers=h)
    assert resp.status_code == 200, resp.text
    # La baja puede rechazarse por otras reglas (TASK-016), pero no por permiso.
    assert (await client.delete("/api/v1/jugadores/1", headers=h)).status_code != 403
    assert (await client.delete("/api/v1/equipos/1", headers=h)).status_code != 403


async def test_equipo_sin_torneos_abiertos_lo_da_de_baja_cualquier_organizador(
    client: AsyncClient, torneo_admin_headers: dict[str, str]
):
    resp = await client.post(
        "/api/v1/equipos",
        json={"nombre": "Equipo Libre", "disciplina_id": 1, "modalidad_id": 1},
        headers=torneo_admin_headers,
    )
    assert resp.status_code == 201, resp.text
    resp = await client.delete(f"/api/v1/equipos/{resp.json()['id']}", headers=torneo_admin_headers)
    assert resp.status_code == 200, resp.text


async def test_admin_general_da_de_baja_cualquier_equipo(client: AsyncClient, admin_general_headers: dict[str, str]):
    assert (await client.delete("/api/v1/equipos/2", headers=admin_general_headers)).status_code != 403
