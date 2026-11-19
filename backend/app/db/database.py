"""Engine async de SQLAlchemy.

El esquema (tablas, constraints, vistas, triggers) vive en /database y se
aplica con los .sql directamente contra Postgres — esta app no usa Alembic
ni crea tablas por su cuenta. `Base` solo sirve para declarar los modelos
ORM que mapean ese esquema ya existente.
"""
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def make_engine(database_url: str) -> AsyncEngine:
    """TASK-028: cada conexión fija `timezone` a la zona del negocio, así
    CURRENT_DATE/CURRENT_TIMESTAMP (valores por defecto, triggers, el "hoy"
    del feed) caen en esa zona aunque el servidor esté en UTC (Docker)."""
    zona = get_settings().zona_horaria
    return create_async_engine(
        database_url,
        pool_pre_ping=True,
        future=True,
        connect_args={"options": f"-c timezone={zona}"},
    )


settings = get_settings()
engine = make_engine(settings.database_url)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)
