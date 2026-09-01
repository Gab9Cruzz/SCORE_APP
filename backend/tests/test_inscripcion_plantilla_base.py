"""Copia de Plantilla Base -> roster real al inscribir un equipo
(gestion-avanzada-equipos-control-mesa-plan.md, Requerimiento 3) — el
corazón del plan: un conflicto de exclusividad en UN candidato NO debe
tumbar a los demás ni revertir la inscripción del equipo (SAVEPOINT por
candidato, InscripcionTorneoService.copiar_plantilla_base_al_roster).
"""
from httpx import AsyncClient

FUTBOL = {"disciplina_id": 1, "modalidad_id": 1}


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


async def _crear_torneo(client: AsyncClient, headers: dict[str, str], nombre: str) -> int:
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "torneo_grupo_nombre": nombre,
            "disciplina_id": 1,
            "modalidad_id": 1,
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-06-01",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _agregar_a_plantilla_base(
    client: AsyncClient, headers: dict[str, str], equipo_id: int, jugador_id: int, dorsal: int | None = None
) -> None:
    resp = await client.post(
        f"/api/v1/equipos/{equipo_id}/plantilla-base",
        json={"jugador_id": jugador_id, "dorsal_sugerido": dorsal},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text


# EC-7: copiar una Plantilla Base vacía es un éxito trivial.
async def test_inscribir_equipo_sin_plantilla_base(client: AsyncClient, admin_general_headers: dict[str, str]):
    torneo_id = await _crear_torneo(client, admin_general_headers, "Torneo PB Vacio")
    equipo_id = await _crear_equipo(client, admin_general_headers, "Equipo PB Vacio Insc")

    resp = await client.post(
        "/api/v1/inscripciones",
        json={"torneo_id": torneo_id, "equipo_id": equipo_id},
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["plantilla_base"] is None


async def test_copiar_plantilla_base_sin_conflictos(client: AsyncClient, admin_general_headers: dict[str, str]):
    torneo_id = await _crear_torneo(client, admin_general_headers, "Torneo PB Sin Conflicto")
    equipo_id = await _crear_equipo(client, admin_general_headers, "Equipo PB Sin Conflicto")

    j1 = await _crear_jugador(client, admin_general_headers, "Jugador Copia 1", "PBCOPY-1")
    j2 = await _crear_jugador(client, admin_general_headers, "Jugador Copia 2", "PBCOPY-2")
    await _agregar_a_plantilla_base(client, admin_general_headers, equipo_id, j1, dorsal=7)
    await _agregar_a_plantilla_base(client, admin_general_headers, equipo_id, j2, dorsal=9)

    resp = await client.post(
        "/api/v1/inscripciones",
        json={"torneo_id": torneo_id, "equipo_id": equipo_id},
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    resumen = resp.json()["plantilla_base"]
    assert resumen["insertados"] == 2
    assert resumen["sin_dorsal"] == 0
    assert resumen["conflictos"] == []


# El corazón del Requerimiento 3: equipo A ya tiene a Carlos Pérez (jugador
# 1 del seed, perfil de Fútbol) activo en el torneo. Equipo B se inscribe
# al mismo torneo con Carlos Pérez en su Plantilla Base + otro candidato
# sin conflicto — la inscripción del equipo B tiene que entrar igual, el
# candidato sano se copia, y solo Carlos queda excluido con el mensaje de
# conflicto.
async def test_copiar_plantilla_base_con_conflicto_de_torneo(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    torneo_id = await _crear_torneo(client, admin_general_headers, "Torneo PB Conflicto Real")

    equipo_a = await _crear_equipo(client, admin_general_headers, "Equipo A PB Conflicto Real")
    await _agregar_a_plantilla_base(client, admin_general_headers, equipo_a, 1)  # Carlos Pérez, jugador 1 del seed

    resp = await client.post(
        "/api/v1/inscripciones",
        json={"torneo_id": torneo_id, "equipo_id": equipo_a},
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["plantilla_base"]["insertados"] == 1  # Carlos entra activo al roster de A

    equipo_b = await _crear_equipo(client, admin_general_headers, "Equipo B PB Conflicto Real")
    otro_jugador = await _crear_jugador(client, admin_general_headers, "Jugador Sano Conflicto", "PBCONF-SANO")
    await _agregar_a_plantilla_base(client, admin_general_headers, equipo_b, 1)  # Carlos Pérez de nuevo
    await _agregar_a_plantilla_base(client, admin_general_headers, equipo_b, otro_jugador)

    resp = await client.post(
        "/api/v1/inscripciones",
        json={"torneo_id": torneo_id, "equipo_id": equipo_b},
        headers=admin_general_headers,
    )
    # La inscripción del EQUIPO nunca se revierte por un conflicto de jugador.
    assert resp.status_code == 201, resp.text
    resumen = resp.json()["plantilla_base"]
    assert resumen["insertados"] == 1  # el jugador sano sí entra
    assert len(resumen["conflictos"]) == 1
    assert resumen["conflictos"][0]["jugador_nombre"] == "Carlos Pérez"
    assert "Traspasos" in resumen["conflictos"][0]["mensaje"]

    # Confirma en la base: el roster real (jugador_equipo) de B tiene al
    # jugador sano activo, y NO a Carlos.
    resp = await client.get(f"/api/v1/estadisticas/equipos/{equipo_b}/plantilla", headers=admin_general_headers)
    nombres_roster_b = [fila["jugador"] for fila in resp.json()]
    assert "Jugador Sano Conflicto" in nombres_roster_b
    assert "Carlos Pérez" not in nombres_roster_b


# EC-6: dorsal sugerido ya ocupado en el roster real -> se inserta sin
# dorsal en vez de fallar todo el candidato.
async def test_copiar_plantilla_base_con_dorsal_duplicado(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    torneo_id = await _crear_torneo(client, admin_general_headers, "Torneo PB Dorsal")
    equipo_id = await _crear_equipo(client, admin_general_headers, "Equipo PB Dorsal")

    j1 = await _crear_jugador(client, admin_general_headers, "Jugador Dorsal 1", "PBDORSAL-1")
    j2 = await _crear_jugador(client, admin_general_headers, "Jugador Dorsal 2", "PBDORSAL-2")
    await _agregar_a_plantilla_base(client, admin_general_headers, equipo_id, j1, dorsal=10)
    await _agregar_a_plantilla_base(client, admin_general_headers, equipo_id, j2, dorsal=10)  # mismo dorsal

    resp = await client.post(
        "/api/v1/inscripciones",
        json={"torneo_id": torneo_id, "equipo_id": equipo_id},
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    resumen = resp.json()["plantilla_base"]
    assert resumen["insertados"] == 2  # ambos entran al roster
    assert resumen["sin_dorsal"] == 1  # uno de los dos sin número
    assert resumen["conflictos"] == []
