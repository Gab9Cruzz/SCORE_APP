"""TASK-028 (BE-05, DB-04), paso mínimo. Decisión del propietario
(2026-11-19): zona del negocio America/Guayaquil, sin migrar columnas a
TIMESTAMPTZ.

Las columnas siguen siendo TIMESTAMP sin zona, pero ahora toda la app las
lee y escribe en la MISMA zona: cada conexión fija `timezone` a la del
negocio (así CURRENT_DATE/CURRENT_TIMESTAMP de la base, en valores por
defecto y triggers, no dependen de cómo esté configurado el servidor), y el
reloj de Python que se compara con esas columnas usa la misma zona."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.reloj import ahora_negocio, hoy_negocio
from app.repositories.feed import FeedRepository

ZONA = "America/Guayaquil"


def test_la_zona_del_negocio_por_defecto():
    assert get_settings().zona_horaria == ZONA


def test_una_zona_inexistente_no_arranca():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="postgresql+psycopg://u:p@h/db", jwt_secret_key="x" * 40,
                 zona_horaria="Marte/Olimpo")  # type: ignore[call-arg]


def test_el_reloj_de_la_app_esta_en_la_zona_del_negocio():
    esperado = datetime.now(ZoneInfo(ZONA)).replace(tzinfo=None)
    assert abs((ahora_negocio() - esperado).total_seconds()) < 5
    assert ahora_negocio().tzinfo is None  # comparable con las columnas TIMESTAMP
    assert hoy_negocio() == datetime.now(ZoneInfo(ZONA)).date()


async def test_las_conexiones_usan_la_zona_del_negocio(db_session: AsyncSession):
    zona = (await db_session.execute(text("SELECT current_setting('TimeZone')"))).scalar_one()
    assert zona == ZONA


async def test_el_hoy_de_la_base_es_el_del_negocio(db_session: AsyncSession):
    """El feed sin fecha usa CURRENT_DATE de la base: con la conexión en la
    zona del negocio es el día del negocio, esté el servidor donde esté."""
    assert await FeedRepository(db_session).fecha_actual_servidor() == hoy_negocio()


async def test_ahora_de_la_base_y_de_la_app_coinciden(db_session: AsyncSession):
    ahora_db = (await db_session.execute(text("SELECT LOCALTIMESTAMP"))).scalar_one()
    assert abs((ahora_db - ahora_negocio()).total_seconds()) < 60
