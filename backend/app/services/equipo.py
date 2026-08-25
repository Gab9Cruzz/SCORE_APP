from sqlalchemy.ext.asyncio import AsyncSession

from app.models.equipo import Equipo
from app.repositories.equipo import EquipoRepository
from app.schemas.equipo import EquipoCreate, EquipoUpdate


class EquipoService:
    def __init__(self, session: AsyncSession):
        self.repo = EquipoRepository(session)

    async def get(self, id_: int) -> Equipo:
        return await self.repo.get_or_404(id_)

    async def list(self, skip: int = 0, limit: int = 100, estado: str | None = None) -> list[Equipo]:
        return await self.repo.list(skip=skip, limit=limit, estado=estado)

    async def create(self, data: EquipoCreate) -> Equipo:
        return await self.repo.create(**data.model_dump())

    async def update(self, id_: int, data: EquipoUpdate) -> Equipo:
        return await self.repo.update(id_, **data.model_dump(exclude_unset=True))

    async def soft_delete(self, id_: int) -> Equipo:
        return await self.repo.soft_delete(id_, estado_inactivo="Inactivo")
