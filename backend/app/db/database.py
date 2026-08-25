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
    return create_async_engine(database_url, pool_pre_ping=True, future=True)


settings = get_settings()
engine = make_engine(settings.database_url)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)
