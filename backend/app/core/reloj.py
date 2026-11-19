"""Reloj del negocio (TASK-028, BE-05/DB-04).

Las columnas de fecha son TIMESTAMP sin zona y guardan la hora local del
negocio: cada conexión a la base fija `timezone` a `ZONA_HORARIA` (ver
db/database.py), así CURRENT_TIMESTAMP/CURRENT_DATE de valores por defecto
y triggers caen en esa zona. Lo que en Python se compare con esas columnas
tiene que salir de acá, no de `datetime.now()`/`date.today()`, que dependen
de la zona de la máquina donde corre la API.

JWT, registros y métricas siguen en UTC: no se comparan con la base.
"""
from datetime import date, datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

from app.core.config import get_settings


@lru_cache
def zona_negocio() -> ZoneInfo:
    return ZoneInfo(get_settings().zona_horaria)


def ahora_negocio() -> datetime:
    """Hora local del negocio, sin tzinfo (como las columnas TIMESTAMP)."""
    return datetime.now(zona_negocio()).replace(tzinfo=None)


def hoy_negocio() -> date:
    return datetime.now(zona_negocio()).date()
