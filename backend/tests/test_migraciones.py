"""TASK-031 (ARQ-01, DB-10, OPS-10): registro de migraciones aplicadas y
ejecutor (scripts/migrar.py), contra una base descartable armada desde
01–06."""
import asyncio
import logging
import pathlib
import re
import shutil

import psycopg
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import migraciones as aviso
from scripts import migrar
from tests.conftest import DATABASE_DIR, TEST_DATABASE_URL, _recrear_base

BASE = "torneos_mvp_migraciones_test"
DSN = TEST_DATABASE_URL.rsplit("/", 1)[0].replace("postgresql+psycopg://", "postgresql://", 1) + "/" + BASE


@pytest.fixture
async def base_nueva():
    await _recrear_base(BASE)
    yield DSN


@pytest.fixture
def carpeta(tmp_path: pathlib.Path) -> pathlib.Path:
    """Copia de las migraciones del repo, para sumar archivos de prueba."""
    for archivo in migrar.listar_migraciones():
        shutil.copy(archivo, tmp_path / archivo.name)
    return tmp_path


def _con(dsn: str):
    return psycopg.connect(dsn, autocommit=True)


async def test_en_una_base_nueva_no_hay_nada_pendiente(base_nueva):
    def _pendientes():
        with _con(base_nueva) as conn:
            return migrar.pendientes(conn)

    assert await asyncio.to_thread(_pendientes) == []


async def test_una_migracion_nueva_se_aplica_una_vez_y_queda_registrada(base_nueva, carpeta):
    (carpeta / "99_migracion_prueba.sql").write_text("CREATE TABLE PRUEBA_MIGRAR (ID INT);", encoding="utf-8")

    def _correr():
        with _con(base_nueva) as conn:
            primera = migrar.aplicar(conn, carpeta)
            segunda = migrar.aplicar(conn, carpeta)
            fila = conn.execute(
                "SELECT Checksum FROM SCHEMA_MIGRATIONS WHERE Nombre = '99_migracion_prueba.sql'"
            ).fetchone()
            existe = conn.execute("SELECT to_regclass('prueba_migrar') IS NOT NULL").fetchone()[0]
            return primera, segunda, fila, existe

    primera, segunda, fila, existe = await asyncio.to_thread(_correr)
    assert primera == ["99_migracion_prueba.sql"]
    assert segunda == []
    assert fila is not None and len(fila[0]) == 64
    assert existe


async def test_una_migracion_que_falla_no_deja_cambios_ni_registro(base_nueva, carpeta):
    (carpeta / "98_migracion_falla.sql").write_text(
        "CREATE TABLE DEBE_DESAPARECER (ID INT);\nSELECT 1 / 0;", encoding="utf-8"
    )

    def _correr():
        with _con(base_nueva) as conn:
            with pytest.raises(psycopg.Error):
                migrar.aplicar(conn, carpeta)
            registrada = conn.execute(
                "SELECT COUNT(*) FROM SCHEMA_MIGRATIONS WHERE Nombre = '98_migracion_falla.sql'"
            ).fetchone()[0]
            existe = conn.execute("SELECT to_regclass('debe_desaparecer') IS NOT NULL").fetchone()[0]
            return registrada, existe

    registrada, existe = await asyncio.to_thread(_correr)
    assert registrada == 0
    assert not existe


async def test_marcar_hasta_da_de_alta_una_base_existente(base_nueva):
    """Una base de antes de TASK-031: sin registro. Se marca hasta la 41 y
    queda pendiente solo la 42."""

    def _correr():
        with _con(base_nueva) as conn:
            conn.execute("DROP TABLE SCHEMA_MIGRATIONS")
            marcadas = migrar.marcar_hasta(conn, 41)
            return marcadas, [p.name for p in migrar.pendientes(conn)]

    marcadas, pendientes = await asyncio.to_thread(_correr)
    assert "41_migracion_bloqueo_torneo_cerrado.sql" in marcadas
    assert pendientes == ["42_migracion_schema_migrations.sql"]


async def test_la_api_avisa_si_falta_alguna(db_session: AsyncSession, carpeta, caplog: pytest.LogCaptureFixture):
    (carpeta / "99_migracion_prueba.sql").write_text("SELECT 1;", encoding="utf-8")
    pendientes = await aviso.migraciones_pendientes(db_session, carpeta)
    assert pendientes == ["99_migracion_prueba.sql"]
    with caplog.at_level(logging.WARNING, logger="score_app.migraciones"):
        aviso.avisar(pendientes)
    assert "99_migracion_prueba.sql" in caplog.text


async def test_con_todo_aplicado_la_api_no_avisa(db_session: AsyncSession):
    assert await aviso.migraciones_pendientes(db_session) == []


def test_la_linea_de_base_de_06_lista_todas_las_migraciones():
    """Una migración nueva tiene que sumarse a la línea de base de
    06_triggers.sql, o una instalación nueva la vería como pendiente."""
    texto = (DATABASE_DIR / "06_triggers.sql").read_text(encoding="utf-8")
    bloque = texto[texto.index("INSERT INTO SCHEMA_MIGRATIONS (Nombre) VALUES"):]
    en_linea_base = set(re.findall(r"'(\d+_migracion_[^']+\.sql)'", bloque))
    assert en_linea_base == {p.name for p in migrar.listar_migraciones()}
