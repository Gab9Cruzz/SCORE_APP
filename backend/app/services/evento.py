from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evento import Evento
from app.repositories.evento import EventoRepository
from app.schemas.evento import EventoCreate, EventoUpdate


class EventoService:
    def __init__(self, session: AsyncSession):
        self.repo = EventoRepository(session)

    async def get(self, id_: int) -> Evento:
        return await self.repo.get_or_404(id_)

    async def list(self, skip: int = 0, limit: int = 100, estado: str | None = None) -> list[Evento]:
        return await self.repo.list(skip=skip, limit=limit, estado=estado)

    async def create(self, data: EventoCreate) -> Evento:
        return await self.repo.create(**data.model_dump())

    async def update(self, id_: int, data: EventoUpdate) -> Evento:
        return await self.repo.update(id_, **data.model_dump(exclude_unset=True))

    async def soft_delete(self, id_: int) -> Evento:
        return await self.repo.soft_delete(id_, estado_inactivo="Inactivo")
