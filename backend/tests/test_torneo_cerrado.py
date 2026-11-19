"""TASK-027 (DB-06): un torneo cerrado (Finalizado) es inmutable salvo
reapertura. El guard de la base ya cubría eventos, hitos y la edición de
partidos; ahora también crear o borrar partidos, convocatorias e
inscripciones. La plantilla (JUGADOR_EQUIPO) queda fuera a propósito: el
propio cierre la escribe al liberar a los jugadores."""
import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

CODIGO = "torneo_cerrado_resultados_bloqueados"


@pytest.fixture
async def torneo_1_cerrado(db_session: AsyncSession) -> None:
    await db_session.execute(text("UPDATE TORNEO SET Estado = 'Finalizado' WHERE ID = 1"))
    await db_session.commit()


@pytest.mark.parametrize(
    "sentencia",
    [
        "INSERT INTO PARTIDOS (Torneo_ID, EQUIPOS_ID_LOCAL, EQUIPOS_ID_VISITANTE, Fecha_Partido) "
        "VALUES (1, 1, 2, '2026-04-01 16:00')",
        "DELETE FROM PARTIDOS WHERE ID = 3",
        "INSERT INTO CONVOCADO_A_PARTIDO (Partido_ID, Jugador_Perfil_ID, Titular) VALUES (3, 1, TRUE)",
        "INSERT INTO INSCRIPCIONES_TORNEO (Torneo_ID, Equipo_ID) "
        "VALUES (1, (SELECT MAX(ID) FROM EQUIPOS))",
        "UPDATE INSCRIPCIONES_TORNEO SET Estado = 'Cancelado' WHERE ID = 1",
    ],
)
async def test_en_un_torneo_cerrado_no_se_escribe(db_session: AsyncSession, torneo_1_cerrado, sentencia: str):
    if "INSCRIPCIONES_TORNEO (Torneo_ID" in sentencia:
        await db_session.execute(
            text("INSERT INTO EQUIPOS (Nombre, Disciplina_ID, Modalidad_ID) VALUES ('Tarde', 1, 1)")
        )
    with pytest.raises(DBAPIError) as exc:
        async with db_session.begin_nested():
            await db_session.execute(text(sentencia))
    assert CODIGO in str(exc.value)


async def test_crear_un_partido_en_un_torneo_cerrado_devuelve_el_codigo(
    client: AsyncClient, admin_general_headers: dict[str, str], torneo_1_cerrado
):
    resp = await client.post(
        "/api/v1/partidos",
        json={"torneo_id": 1, "equipos_id_local": 1, "equipos_id_visitante": 2, "fecha_partido": "2026-04-01T16:00:00"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["detail"] == CODIGO


async def test_en_un_torneo_abierto_se_sigue_escribiendo(db_session: AsyncSession):
    await db_session.execute(
        text(
            "INSERT INTO PARTIDOS (Torneo_ID, EQUIPOS_ID_LOCAL, EQUIPOS_ID_VISITANTE, Fecha_Partido) "
            "VALUES (1, 1, 2, '2026-04-01 16:00')"
        )
    )
