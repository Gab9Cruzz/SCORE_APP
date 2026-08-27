from sqlalchemy.ext.asyncio import AsyncSession

from app.models.modalidad import Modalidad
from app.repositories.modalidad import ModalidadRepository
from app.schemas.modalidad import ModalidadCreate, ModalidadUpdate


class ModalidadService:
    def __init__(self, session: AsyncSession):
        self.repo = ModalidadRepository(session)

    async def get(self, id_: int) -> Modalidad:
        return await self.repo.get_or_404(id_)

    async def list(
        self, skip: int = 0, limit: int = 100, disciplina_id: int | None = None, estado: str | None = None
    ) -> list[Modalidad]:
        return await self.repo.list(skip=skip, limit=limit, disciplina_id=disciplina_id, estado=estado)

    async def create(self, data: ModalidadCreate) -> Modalidad:
        return await self.repo.create(**data.model_dump())

    async def update(self, id_: int, data: ModalidadUpdate) -> Modalidad:
        return await self.repo.update(id_, **data.model_dump(exclude_unset=True))

    async def soft_delete(self, id_: int) -> Modalidad:
        return await self.repo.soft_delete(id_, estado_inactivo="Inactivo")
