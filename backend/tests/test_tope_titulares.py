"""Área 1 (modo-vivo-sustituciones-cierre-plan.md, T2/T16/T18): tope
SUPERIOR de titulares por equipo — reversión explícita de la Decisión
Audit #12 del plan anterior (diferida dos veces, reabierta con evidencia
concreta: un torneo de Fútbol 7 aceptaba 8 titulares sin ningún aviso).

Reusa el fixture ad-hoc de test_titulares_inicio_partido.py (mismo
criterio: modalidad/torneo/partido propios por test, para controlar
exactamente `tamano_equipo` sin depender del seed fijo).
"""
from sqlalchemy.ext.asyncio import AsyncSession

from httpx import AsyncClient

from tests.test_titulares_inicio_partido import (
    _agregar_jugador_activo,
    _armar_torneo_con_partido,
    _convocar,
)


async def test_reemplazar_convocatoria_con_exceso_de_titulares_es_rechazado(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """PUT /convocados (reemplazar) con MÁS titulares que tamano_equipo."""
    ctx = await _armar_torneo_con_partido(db_session, tamano_equipo=2, nombre="TopeReemplazar")
    perfiles = [
        await _agregar_jugador_activo(db_session, ctx["disciplina_id"], ctx["insc_local_id"], f"L{i}")
        for i in range(3)
    ]

    resp = await client.put(
        f"/api/v1/partidos/{ctx['partido_id']}/convocados",
        json={"convocados": [{"jugador_perfil_id": p, "titular": True} for p in perfiles]},
        headers=admin_general_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "titular" in resp.json()["detail"].lower()


async def test_reemplazar_convocatoria_con_titulares_exactos_al_tope_es_aceptado(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """Llegar EXACTO al tope (no excederlo) sigue funcionando — el fix no
    reduce el caso normal, solo cierra el exceso."""
    ctx = await _armar_torneo_con_partido(db_session, tamano_equipo=2, nombre="TopeExacto")
    perfiles = [
        await _agregar_jugador_activo(db_session, ctx["disciplina_id"], ctx["insc_local_id"], f"L{i}")
        for i in range(2)
    ]

    resp = await client.put(
        f"/api/v1/partidos/{ctx['partido_id']}/convocados",
        json={"convocados": [{"jugador_perfil_id": p, "titular": True} for p in perfiles]},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    assert sum(1 for c in resp.json() if c["titular"]) == 2


async def test_agregar_convocado_titular_que_excede_el_tope_es_rechazado(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """POST /convocados (agregar), pre-arranque: sumar un titular #N+1
    directo, sin pasar por el PUT."""
    ctx = await _armar_torneo_con_partido(db_session, tamano_equipo=1, nombre="TopeAgregar")
    ya_titular = await _agregar_jugador_activo(db_session, ctx["disciplina_id"], ctx["insc_local_id"], "L0")
    await _convocar(db_session, ctx["partido_id"], ya_titular, titular=True)
    otro = await _agregar_jugador_activo(db_session, ctx["disciplina_id"], ctx["insc_local_id"], "L1")

    resp = await client.post(
        f"/api/v1/partidos/{ctx['partido_id']}/convocados",
        json={"jugador_perfil_id": otro, "titular": True},
        headers=admin_general_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "titular" in resp.json()["detail"].lower()


async def test_maximo_titulares_permitido_del_torneo_reemplaza_tamano_equipo(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """Torneo.maximo_titulares_permitido, cuando está seteado, manda por
    encima de Modalidad.tamano_equipo (mismo patrón que
    minimo_jugadores_para_iniciar) — acá lo baja a 1 en una modalidad de
    tamano_equipo=5."""
    ctx = await _armar_torneo_con_partido(db_session, tamano_equipo=5, nombre="TopePorTorneo")
    resp_patch = await client.patch(
        f"/api/v1/torneos/{ctx['torneo_id']}",
        json={"maximo_titulares_permitido": 1},
        headers=admin_general_headers,
    )
    assert resp_patch.status_code == 200, resp_patch.text

    perfiles = [
        await _agregar_jugador_activo(db_session, ctx["disciplina_id"], ctx["insc_local_id"], f"L{i}")
        for i in range(2)
    ]
    resp = await client.put(
        f"/api/v1/partidos/{ctx['partido_id']}/convocados",
        json={"convocados": [{"jugador_perfil_id": p, "titular": True} for p in perfiles]},
        headers=admin_general_headers,
    )
    assert resp.status_code == 400, resp.text


async def test_insert_directo_por_encima_del_tope_lo_rechaza_el_trigger(
    db_session: AsyncSession,
):
    """Defensa en profundidad a nivel DB (T16): un INSERT que no pasa por
    ningún Service (bypassea el guard de Python) sigue chocando contra
    fn_validar_tope_titulares."""
    ctx = await _armar_torneo_con_partido(db_session, tamano_equipo=1, nombre="TopeTrigger")
    p1 = await _agregar_jugador_activo(db_session, ctx["disciplina_id"], ctx["insc_local_id"], "L0")
    p2 = await _agregar_jugador_activo(db_session, ctx["disciplina_id"], ctx["insc_local_id"], "L1")
    await _convocar(db_session, ctx["partido_id"], p1, titular=True)

    import pytest
    from sqlalchemy.exc import DBAPIError

    from app.models.convocado_a_partido import ConvocadoAPartido

    db_session.add(ConvocadoAPartido(partido_id=ctx["partido_id"], jugador_perfil_id=p2, titular=True))
    with pytest.raises(DBAPIError):
        await db_session.commit()
