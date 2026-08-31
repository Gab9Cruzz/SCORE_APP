"""Auditoría de cambios (tabla AUDITORIA) — "cualquier cambio queda
registrado durante 1 mes": alta, modificación o baja de cualquier entidad.

El test que más importa acá es
`test_creacion_por_flujo_sin_baserepository_tambien_se_audita`: prueba que
el event listener de `app/core/auditoria.py` cubre escrituras que NO pasan
por `BaseRepository` (inscripciones usa `session.add()` directo) — es
justo la razón por la que se eligió esa arquitectura en vez de un hook
adentro de `BaseRepository.create()`.
"""
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auditoria import Auditoria


async def _auditoria_de(session: AsyncSession, tabla: str, registro_id: int | None = None) -> list[Auditoria]:
    stmt = select(Auditoria).where(Auditoria.tabla == tabla)
    if registro_id is not None:
        stmt = stmt.where(Auditoria.registro_id == registro_id)
    result = await session.execute(stmt.order_by(Auditoria.id))
    return list(result.scalars().all())


# --- Se registra cada tipo de cambio ---


async def test_crear_torneo_queda_registrado(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "nombre": "Torneo Auditado",
            "disciplina_id": 1,
            "modalidad_id": 1,
            "torneo_grupo_nombre": "Torneo Auditado",
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-06-01",
        },
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    torneo_id = resp.json()["id"]

    filas = await _auditoria_de(db_session, "torneo", torneo_id)
    assert len(filas) == 1
    assert filas[0].accion == "crear"
    assert filas[0].datos_anteriores is None
    assert filas[0].datos_nuevos["nombre"] == "Torneo Auditado"
    assert filas[0].usuario_id is not None  # el AdminGeneral del fixture


async def test_modificar_torneo_registra_antes_y_despues(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    creado = await client.post(
        "/api/v1/torneos",
        json={
            "nombre": "Nombre Original",
            "disciplina_id": 1,
            "modalidad_id": 1,
            "torneo_grupo_nombre": "Nombre Original",
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-06-01",
        },
        headers=admin_general_headers,
    )
    torneo_id = creado.json()["id"]

    resp = await client.patch(
        f"/api/v1/torneos/{torneo_id}", json={"nombre": "Nombre Cambiado"}, headers=admin_general_headers
    )
    assert resp.status_code == 200, resp.text

    filas = await _auditoria_de(db_session, "torneo", torneo_id)
    modificacion = [f for f in filas if f.accion == "modificar"]
    assert len(modificacion) == 1
    fila = modificacion[0]
    assert fila.datos_anteriores["nombre"] == "Nombre Original"
    assert fila.datos_nuevos["nombre"] == "Nombre Cambiado"
    # Solo lo que cambió — no todas las columnas de la tabla.
    assert set(fila.datos_anteriores.keys()) == {"nombre"}


async def test_dar_de_baja_torneo_se_registra_como_eliminar(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """El borrado lógico (Estado -> Inactivo) tiene que distinguirse de una
    modificación cualquiera — ver el hint transiente que
    `BaseRepository.soft_delete` deja para el listener."""
    creado = await client.post(
        "/api/v1/torneos",
        json={
            "nombre": "Torneo A Dar De Baja",
            "disciplina_id": 1,
            "modalidad_id": 1,
            "torneo_grupo_nombre": "Torneo A Dar De Baja",
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-06-01",
        },
        headers=admin_general_headers,
    )
    torneo_id = creado.json()["id"]

    resp = await client.delete(f"/api/v1/torneos/{torneo_id}", headers=admin_general_headers)
    assert resp.status_code == 200, resp.text

    filas = await _auditoria_de(db_session, "torneo", torneo_id)
    baja = [f for f in filas if f.accion == "eliminar"]
    assert len(baja) == 1
    assert baja[0].datos_nuevos["estado"] == "Inactivo"


async def test_creacion_por_flujo_sin_baserepository_tambien_se_audita(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """InscripcionTorneoService.create() escribe con `session.add()` directo
    (services/inscripcion_torneo.py), sin pasar por BaseRepository — es el
    caso que un hook dentro de BaseRepository.create() se perdería."""
    equipo = await client.post(
        "/api/v1/equipos",
        json={"nombre": "Equipo Para Auditar Inscripcion", "disciplina_id": 1, "modalidad_id": 1},
        headers=admin_general_headers,
    )
    equipo_id = equipo.json()["id"]

    resp = await client.post(
        "/api/v1/inscripciones",
        json={"torneo_id": 1, "equipo_id": equipo_id},
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    inscripcion_id = resp.json()["id"]

    filas = await _auditoria_de(db_session, "inscripciones_torneo", inscripcion_id)
    assert len(filas) == 1
    assert filas[0].accion == "crear"
    assert filas[0].datos_nuevos["equipo_id"] == equipo_id


# --- Redacción de datos sensibles ---


async def test_password_hash_nunca_aparece_en_texto_plano(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    secreto = "PasswordDeUsuarioAuditado-123"
    resp = await client.post(
        "/api/v1/usuarios",
        json={"username": "auditado_pw", "nombre": "Auditado", "password": secreto, "rol": "Arbitro"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    usuario_id = resp.json()["id"]

    filas = await _auditoria_de(db_session, "usuarios", usuario_id)
    assert len(filas) == 1
    assert filas[0].datos_nuevos["password_hash"] == "(redactado)"
    valores = " ".join(str(v) for v in filas[0].datos_nuevos.values())
    assert secreto not in valores


# --- GET /auditoria ---


async def test_listar_auditoria_exige_admin_general(client: AsyncClient, torneo_admin_headers: dict[str, str]):
    resp = await client.get("/api/v1/auditoria", headers=torneo_admin_headers)
    assert resp.status_code == 403


async def test_listar_auditoria_es_privado(client: AsyncClient):
    resp = await client.get("/api/v1/auditoria")
    assert resp.status_code == 401


async def test_filtro_por_tabla_y_accion(client: AsyncClient, admin_general_headers: dict[str, str]):
    creado = await client.post(
        "/api/v1/torneos",
        json={
            "nombre": "Torneo Filtro Auditoria",
            "disciplina_id": 1,
            "modalidad_id": 1,
            "torneo_grupo_nombre": "Torneo Filtro Auditoria",
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-06-01",
        },
        headers=admin_general_headers,
    )
    torneo_id = creado.json()["id"]

    resp = await client.get(
        "/api/v1/auditoria",
        params={"tabla": "torneo", "registro_id": torneo_id, "accion": "crear"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    filas = resp.json()
    assert len(filas) == 1
    assert filas[0]["tabla"] == "torneo"
    assert filas[0]["registro_id"] == torneo_id


async def test_no_existe_forma_de_escribir_ni_borrar_la_bitacora(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    assert (await client.post("/api/v1/auditoria", json={}, headers=admin_general_headers)).status_code == 405
    assert (await client.delete("/api/v1/auditoria/1", headers=admin_general_headers)).status_code in (404, 405)


# --- Retención: se borra lo de más de un mes ---


async def test_purga_borra_lo_viejo_y_conserva_lo_reciente(db_session: AsyncSession):
    from datetime import datetime, timedelta

    from app.repositories.auditoria import AuditoriaRepository

    ahora = datetime.now()
    db_session.add_all([
        Auditoria(tabla="torneo", registro_id=1, accion="crear", fecha=ahora - timedelta(days=60)),
        Auditoria(tabla="torneo", registro_id=2, accion="crear", fecha=ahora - timedelta(days=31)),
        Auditoria(tabla="torneo", registro_id=3, accion="crear", fecha=ahora - timedelta(days=29)),
        Auditoria(tabla="torneo", registro_id=4, accion="crear", fecha=ahora - timedelta(days=1)),
    ])
    await db_session.commit()

    borrados = await AuditoriaRepository(db_session).purgar_anteriores_a(30)
    assert borrados == 2

    assert len(await _auditoria_de(db_session, "torneo", 1)) == 0
    assert len(await _auditoria_de(db_session, "torneo", 2)) == 0
    assert len(await _auditoria_de(db_session, "torneo", 3)) == 1
    assert len(await _auditoria_de(db_session, "torneo", 4)) == 1


async def test_purga_desactivada_no_borra_nada(db_session: AsyncSession):
    from datetime import datetime, timedelta

    from app.repositories.auditoria import AuditoriaRepository

    db_session.add(
        Auditoria(tabla="torneo", registro_id=999, accion="crear", fecha=datetime.now() - timedelta(days=999))
    )
    await db_session.commit()

    assert await AuditoriaRepository(db_session).purgar_anteriores_a(0) == 0
    assert len(await _auditoria_de(db_session, "torneo", 999)) == 1
