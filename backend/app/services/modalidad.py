from sqlalchemy.ext.asyncio import AsyncSession

from app.models.modalidad import Modalidad
from app.repositories.modalidad import ModalidadRepository
from app.schemas.modalidad import ModalidadUpdate


class ModalidadService:
    """Catálogo de solo lectura + toggle de Estado (Decisión C1,
    ediciones-catalogo-disciplinas-plan.md) — sin `create`: el catálogo lo
    carga 11_catalogo_disciplinas.sql, no un admin desde la UI."""

    def __init__(self, session: AsyncSession):
        self.repo = ModalidadRepository(session)

    async def get(self, id_: int) -> Modalidad:
        return await self.repo.get_or_404(id_)

    async def list(
        self, skip: int = 0, limit: int = 100, disciplina_id: int | None = None, estado: str | None = None
    ) -> list[Modalidad]:
        return await self.repo.list(skip=skip, limit=limit, disciplina_id=disciplina_id, estado=estado)

    async def update(self, id_: int, data: ModalidadUpdate) -> Modalidad:
        return await self.repo.update(id_, **data.model_dump(exclude_unset=True))
