"""TASK-039 (UX-05, FE-09): búsqueda por nombre en `/equipos`, resolución de
varios registros por `?ids=` y total en `X-Total-Count` en los listados que
pagina la interfaz.

Antes la grilla de equipos traía 200 filas y buscaba en el navegador (un
equipo 201 "no existía"), y cada nombre que faltaba en esa ventana costaba un
GET aparte."""
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.equipo import Equipo
from app.models.jugador import Jugador
from app.models.torneo import Torneo
from app.models.torneo_grupo import TorneoGrupo


@pytest.fixture
async def equipos_de_busqueda(db_session: AsyncSession) -> list[int]:
    """Tres equipos con un nombre que ningún dato semilla contiene."""
    base = (await db_session.execute(select(Equipo).order_by(Equipo.id).limit(1))).scalar_one()
    ids = []
    for nombre in ("Zorros Quimera", "Quimera del Sur", "Halcones Norte"):
        equipo = Equipo(nombre=nombre, disciplina_id=base.disciplina_id, modalidad_id=base.modalidad_id)
        db_session.add(equipo)
        await db_session.flush()
        ids.append(equipo.id)
    await db_session.commit()
    return ids


async def test_equipos_q_busca_por_nombre_en_el_servidor(client: AsyncClient, equipos_de_busqueda: list[int]):
    r = await client.get("/api/v1/equipos", params={"q": "quimera"})
    assert r.status_code == 200
    assert sorted(e["nombre"] for e in r.json()) == ["Quimera del Sur", "Zorros Quimera"]
    assert r.headers["X-Total-Count"] == "2"


async def test_equipos_q_respeta_la_paginacion_y_el_total(client: AsyncClient, equipos_de_busqueda: list[int]):
    r = await client.get("/api/v1/equipos", params={"q": "quimera", "limit": 1})
    assert len(r.json()) == 1
    assert r.headers["X-Total-Count"] == "2"
    r2 = await client.get("/api/v1/equipos", params={"q": "quimera", "limit": 1, "skip": 1})
    assert r2.json()[0]["id"] != r.json()[0]["id"]


async def test_equipos_q_vacio_no_filtra(client: AsyncClient, db_session: AsyncSession, equipos_de_busqueda: list[int]):
    total = (await db_session.execute(select(func.count()).select_from(Equipo))).scalar_one()
    r = await client.get("/api/v1/equipos", params={"q": "   "})
    assert r.headers["X-Total-Count"] == str(total)


async def test_equipos_ids_devuelve_solo_esos(client: AsyncClient, equipos_de_busqueda: list[int]):
    pedidos = [equipos_de_busqueda[2], equipos_de_busqueda[0]]
    r = await client.get("/api/v1/equipos", params={"ids": ",".join(map(str, pedidos))})
    assert r.status_code == 200
    assert sorted(e["id"] for e in r.json()) == sorted(pedidos)
    assert r.headers["X-Total-Count"] == "2"


async def test_equipos_ids_inexistentes_se_omiten(client: AsyncClient, equipos_de_busqueda: list[int]):
    r = await client.get("/api/v1/equipos", params={"ids": f"{equipos_de_busqueda[0]},999999"})
    assert [e["id"] for e in r.json()] == [equipos_de_busqueda[0]]


@pytest.mark.parametrize("valor", ["", "1,,2", "a,b", "1;2", "-1"])
async def test_equipos_ids_mal_formado_es_422(client: AsyncClient, valor: str):
    r = await client.get("/api/v1/equipos", params={"ids": valor})
    assert r.status_code == 422


async def test_equipos_mas_de_200_ids_es_422(client: AsyncClient):
    r = await client.get("/api/v1/equipos", params={"ids": ",".join(str(i) for i in range(1, 202))})
    assert r.status_code == 422


async def test_jugadores_ids_y_total(client: AsyncClient, db_session: AsyncSession):
    ids = list((await db_session.execute(select(Jugador.id).order_by(Jugador.id).limit(3))).scalars())
    r = await client.get("/api/v1/jugadores", params={"ids": ",".join(map(str, ids))})
    assert r.status_code == 200
    assert sorted(j["id"] for j in r.json()) == ids
    assert r.headers["X-Total-Count"] == "3"


async def test_jugadores_total_cuenta_la_busqueda(client: AsyncClient, db_session: AsyncSession):
    for i in range(3):
        db_session.add(Jugador(nombre=f"Ornitorrinco {i}", cedula=f"ORN{i:04d}", correo_electronico=f"orn{i}@t.com"))
    await db_session.commit()
    r = await client.get("/api/v1/jugadores", params={"q": "ornitorrinco", "limit": 2})
    assert len(r.json()) == 2
    assert r.headers["X-Total-Count"] == "3"


async def test_jugadores_anonimo_no_cuenta_por_cedula(client: AsyncClient, db_session: AsyncSession):
    """TASK-014: sin permiso para ver datos personales la búsqueda no mira la
    cédula, y el total tampoco (si no, el total delataría la coincidencia)."""
    db_session.add(Jugador(nombre="Sin Pista", cedula="CED-SECRETA-77", correo_electronico="sp@t.com"))
    await db_session.commit()
    r = await client.get("/api/v1/jugadores", params={"q": "SECRETA-77"})
    assert r.json() == []
    assert r.headers["X-Total-Count"] == "0"


async def test_perfiles_por_ids(client: AsyncClient):
    r = await client.get("/api/v1/perfiles", params={"ids": "1,2"})
    assert r.status_code == 200
    assert sorted(p["id"] for p in r.json()) == [1, 2]


async def test_torneos_informan_el_total(client: AsyncClient):
    r = await client.get("/api/v1/torneos", params={"limit": 1})
    assert r.status_code == 200
    assert int(r.headers["X-Total-Count"]) >= len(r.json())


async def test_usuarios_total_recortado_para_torneo_admin(
    client: AsyncClient, torneo_admin_headers: dict[str, str], admin_general_headers: dict[str, str]
):
    """El total respeta el mismo recorte que la lista: un TorneoAdmin solo ve
    árbitros, y el total no puede contar las demás cuentas."""
    r = await client.get("/api/v1/usuarios", headers=torneo_admin_headers)
    assert r.headers["X-Total-Count"] == str(len(r.json()))
    assert all(u["rol"] == "Arbitro" for u in r.json())
    todos = await client.get("/api/v1/usuarios", headers=admin_general_headers)
    assert int(todos.headers["X-Total-Count"]) > int(r.headers["X-Total-Count"])


async def test_accesos_y_auditoria_informan_el_total(client: AsyncClient, admin_general_headers: dict[str, str]):
    for ruta in ("/api/v1/accesos", "/api/v1/auditoria"):
        r = await client.get(ruta, headers=admin_general_headers, params={"limit": 1})
        assert r.status_code == 200, ruta
        assert int(r.headers["X-Total-Count"]) >= len(r.json()), ruta
    # Los filtros también cuentan: el login del fixture fue exitoso.
    r = await client.get(
        "/api/v1/accesos", headers=admin_general_headers, params={"exitoso": "false", "username": "nadie-asi"}
    )
    assert r.headers["X-Total-Count"] == "0"


async def test_torneos_por_ids_incluye_los_de_un_grupo_archivado(client: AsyncClient, db_session: AsyncSession):
    """Pedir por id es acceso directo (como GET /torneos/{id}): el listado
    general oculta las ediciones archivadas, pero quien ya tiene el id —un
    partido viejo que nombra su torneo— lo tiene que poder resolver."""
    torneo = (await db_session.execute(select(Torneo).order_by(Torneo.id).limit(1))).scalar_one()
    grupo = await db_session.get(TorneoGrupo, torneo.torneo_grupo_id)
    grupo.estado = "Archivado"
    await db_session.commit()

    general = await client.get("/api/v1/torneos", params={"limit": 200})
    assert torneo.id not in [t["id"] for t in general.json()]
    por_id = await client.get("/api/v1/torneos", params={"ids": str(torneo.id)})
    assert [t["id"] for t in por_id.json()] == [torneo.id]
    assert por_id.headers["X-Total-Count"] == "1"
