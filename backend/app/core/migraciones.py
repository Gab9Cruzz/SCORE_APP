"""Aviso de migraciones pendientes al arrancar (TASK-031).

La API no aplica migraciones sola: solo avisa en el registro si la base no
tiene alguna de las que hay en database/. Se aplican con
`python -m scripts.migrar --aplicar` (ver ese script).
"""
import logging
import pathlib
import re

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("score_app.migraciones")

DIRECTORIO_MIGRACIONES = pathlib.Path(__file__).resolve().parents[3] / "database"
_PATRON = re.compile(r"^\d+_migracion_.+\.sql$")


async def migraciones_pendientes(
    session: AsyncSession, directorio: pathlib.Path = DIRECTORIO_MIGRACIONES
) -> list[str] | None:
    """Nombres de las migraciones que hay en `directorio` y la base no tiene
    registradas. None si no se puede saber: sin la carpeta (una imagen que
    no la copia) o sin la tabla SCHEMA_MIGRATIONS (base anterior a TASK-031,
    hay que darla de alta con --marcar-hasta)."""
    if not directorio.is_dir():
        return None
    try:
        filas = await session.execute(text("SELECT Nombre FROM SCHEMA_MIGRATIONS"))
    except DBAPIError:
        await session.rollback()
        return None
    registradas = {nombre for (nombre,) in filas.all()}
    en_disco = sorted(p.name for p in directorio.iterdir() if _PATRON.match(p.name))
    return [nombre for nombre in en_disco if nombre not in registradas]


def avisar(pendientes: list[str] | None) -> None:
    if pendientes is None:
        logger.warning(
            "no se pudo verificar el estado de las migraciones (falta database/ o la tabla "
            "SCHEMA_MIGRATIONS: dar de alta la base con `python -m scripts.migrar --marcar-hasta NN`)"
        )
    elif pendientes:
        logger.warning(
            "hay %s migración(es) sin aplicar en esta base: %s. Aplicalas con `python -m scripts.migrar --aplicar`.",
            len(pendientes),
            ", ".join(pendientes),
        )
