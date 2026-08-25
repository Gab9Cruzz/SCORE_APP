"""Dependencia FastAPI para obtener una sesión de DB por request."""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            # Sin este rollback, un commit fallido (constraint, trigger) deja
            # la sesión en estado "pending rollback" y la excepción de
            # exceptions/handlers.py se serializa bien, pero la conexión
            # queda envenenada para lo que quede del request.
            await session.rollback()
            raise
