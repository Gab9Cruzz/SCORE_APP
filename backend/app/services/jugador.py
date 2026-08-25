from sqlalchemy.ext.asyncio import AsyncSession

from app.models.jugador import Jugador
from app.repositories.jugador import JugadorRepository
from app.schemas.jugador import JugadorCreate, JugadorUpdate


class JugadorService:
    def __init__(self, session: AsyncSession):
        self.repo = JugadorRepository(session)

    async def get(self, id_: int) -> Jugador:
        return await self.repo.get_or_404(id_)

    async def list(self, skip: int = 0, limit: int = 100, estado: str | None = None) -> list[Jugador]:
        return await self.repo.list(skip=skip, limit=limit, estado=estado)

    async def create(self, data: JugadorCreate) -> Jugador:
        return await self.repo.create(**data.model_dump())

    async def update(self, id_: int, data: JugadorUpdate) -> Jugador:
        return await self.repo.update(id_, **data.model_dump(exclude_unset=True))

    async def soft_delete(self, id_: int) -> Jugador:
        return await self.repo.soft_delete(id_, estado_inactivo="Inactivo")
