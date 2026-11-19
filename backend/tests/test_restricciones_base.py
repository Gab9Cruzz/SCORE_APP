"""TASK-026 (DB-01, DB-02): la base rechaza los valores incoherentes que
antes aceptaba por SQL directo: estados nulos, fechas invertidas, rangos
imposibles y nombres vacíos."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

TABLAS_CON_ESTADO = (
    "disciplina", "modalidad", "torneo", "equipos", "jugadores", "inscripciones_torneo", "jugador_equipo",
    "traspasos", "equipo_jugador_base", "partidos", "eventos", "usuarios", "eventos_partido",
)


async def test_las_columnas_estado_no_admiten_nulo(db_session: AsyncSession):
    filas = (
        await db_session.execute(
            text(
                "SELECT table_name, is_nullable FROM information_schema.columns "
                "WHERE column_name = 'estado' AND table_name = ANY(:tablas)"
            ),
            {"tablas": list(TABLAS_CON_ESTADO)},
        )
    ).all()
    assert {t for t, _ in filas} == set(TABLAS_CON_ESTADO)
    assert [t for t, nulo in filas if nulo != "NO"] == []


@pytest.mark.parametrize(
    "sentencia",
    [
        # 05_seed.sql: torneo 1, vínculo de plantilla 1, partido 3, equipo 1,
        # jugador 1, evento 1, hito ninguno (se prueba con un INSERT).
        "UPDATE TORNEO SET Fecha_Fin = Fecha_Inicio - 1 WHERE ID = 1",
        "UPDATE TORNEO SET Equipos_Por_Grupo = 0 WHERE ID = 1",
        "UPDATE TORNEO SET Clasificados_Por_Grupo = 0 WHERE ID = 1",
        "UPDATE JUGADOR_EQUIPO SET Fecha_Fin = Fecha_Inicio - 1, Estado = 'Inactivo' WHERE ID = 1",
        "UPDATE JUGADOR_EQUIPO SET Dorsal = 0 WHERE ID = 1",
        "UPDATE CONFIGURACION_TIEMPO_TORNEO SET Cantidad_Periodos = 0 WHERE Torneo_ID = 1",
        "UPDATE CONFIGURACION_TIEMPO_TORNEO SET Duracion_Periodo_Minutos = 0 WHERE Torneo_ID = 1",
        "UPDATE CONFIGURACION_TIEMPO_TORNEO SET Duracion_Descanso_Minutos = -1 WHERE Torneo_ID = 1",
        "INSERT INTO HITOS_PARTIDO (Partido_ID, Tipo_Hito, Minuto_Reloj, Registrado_Por) "
        "SELECT 3, 'Pausa', -1, (SELECT MIN(ID) FROM USUARIOS)",
        "UPDATE EQUIPOS SET Nombre = '   ' WHERE ID = 1",
        "UPDATE JUGADORES SET Nombre = '' WHERE ID = 1",
        "UPDATE TORNEO SET Nombre = ' ' WHERE ID = 1",
        "UPDATE EVENTOS SET Nombre = '' WHERE ID = 1",
        "UPDATE EQUIPOS SET Estado = NULL WHERE ID = 1",
    ],
)
async def test_la_base_rechaza_valores_incoherentes(db_session: AsyncSession, sentencia: str):
    if "HITOS_PARTIDO" in sentencia:
        await db_session.execute(
            text(
                "INSERT INTO USUARIOS (Username, Nombre, Password_Hash, Rol) "
                "VALUES ('restricciones_test', 'R', :h, 'Arbitro')"
            ),
            {"h": "x" * 60},
        )
    with pytest.raises(DBAPIError):
        async with db_session.begin_nested():
            await db_session.execute(text(sentencia))


async def test_los_valores_validos_siguen_entrando(db_session: AsyncSession):
    await db_session.execute(text("UPDATE TORNEO SET Fecha_Fin = Fecha_Inicio WHERE ID = 1"))
    await db_session.execute(text("UPDATE JUGADOR_EQUIPO SET Dorsal = 1 WHERE ID = 1"))
    await db_session.execute(text("UPDATE CONFIGURACION_TIEMPO_TORNEO SET Duracion_Descanso_Minutos = 0 WHERE Torneo_ID = 1"))


async def test_la_migracion_se_detiene_si_hay_datos_invalidos(db_session: AsyncSession):
    """Con una fila que viola una regla nueva, la migración 40 no toca nada
    y dice qué corregir."""
    import pathlib

    script = (pathlib.Path(__file__).resolve().parents[2] / "database" / "40_migracion_restricciones_coherencia.sql").read_text(
        encoding="utf-8"
    )
    async with db_session.begin_nested():
        await db_session.execute(text("ALTER TABLE EQUIPOS DROP CONSTRAINT chk_equipos_nombre_no_vacio"))
        await db_session.execute(text("UPDATE EQUIPOS SET Nombre = ' ' WHERE ID = 1"))
        with pytest.raises(DBAPIError) as exc:
            async with db_session.begin_nested():
                conexion = await db_session.connection()
                await conexion.exec_driver_sql(script)
        assert "equipos sin nombre" in str(exc.value)
