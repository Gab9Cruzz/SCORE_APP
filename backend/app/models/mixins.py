"""Columnas de auditoría comunes a las 9 tablas de /database/01_schema.sql.

fecha_registro y fecha_modificacion tienen DEFAULT CURRENT_TIMESTAMP en
Postgres (ver 01_schema.sql) y fecha_modificacion además se actualiza sola
en cada UPDATE por el trigger fn_actualizar_fecha_modificacion
(06_triggers.sql). server_default (no default de Python) es a propósito:
sin declarar ACÁ que hay un default del lado del servidor, SQLAlchemy no
tiene forma de saber que puede omitir la columna del INSERT, y termina
mandando NULL explícito en vez de dejar que Postgres aplique el suyo.
"""
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    fecha_registro: Mapped[datetime] = mapped_column(nullable=True, server_default=text("CURRENT_TIMESTAMP"))
    fecha_modificacion: Mapped[datetime] = mapped_column(
        nullable=True, server_default=text("CURRENT_TIMESTAMP")
    )
