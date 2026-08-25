from sqlalchemy import select

from app.models.usuario import Usuario
from app.repositories.base import BaseRepository


class UsuarioRepository(BaseRepository[Usuario]):
    model = Usuario
    nombre_recurso = "Usuario"

    async def get_by_username(self, username: str) -> Usuario | None:
        stmt = select(Usuario).where(Usuario.username == username.strip().lower())
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def count(self) -> int:
        stmt = select(Usuario)
        result = await self.session.execute(stmt)
        return len(result.scalars().all())
