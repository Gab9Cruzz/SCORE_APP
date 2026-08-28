from sqlalchemy.ext.asyncio import AsyncSession

from app.models.disciplina import Disciplina
from app.repositories.disciplina import DisciplinaRepository
from app.repositories.modalidad import ModalidadRepository
from app.schemas.disciplina import DisciplinaConModalidadesOut, DisciplinaUpdate
from app.schemas.modalidad import ModalidadOut


class DisciplinaService:
    """Catálogo de solo lectura + toggle de Estado (Decisión C1,
    ediciones-catalogo-disciplinas-plan.md) — sin `create`: el catálogo lo
    carga 11_catalogo_disciplinas.sql, no un admin desde la UI."""

    def __init__(self, session: AsyncSession):
        self.repo = DisciplinaRepository(session)
        self.modalidad_repo = ModalidadRepository(session)

    async def get(self, id_: int) -> Disciplina:
        return await self.repo.get_or_404(id_)

    async def list(self, skip: int = 0, limit: int = 100, estado: str | None = None) -> list[Disciplina]:
        return await self.repo.list(skip=skip, limit=limit, estado=estado)

    async def list_con_modalidades(self, estado: str | None = None) -> list[DisciplinaConModalidadesOut]:
        """Vista jerárquica para CatalogoDisciplinasPage: una sola llamada
        trae cada disciplina con su roster completo de modalidades (28
        disciplinas / 66 modalidades en total — sin paginar, es un
        catálogo chico y de solo lectura, no una tabla operacional)."""
        disciplinas = await self.repo.list(skip=0, limit=200, estado=estado)
        modalidades = await self.modalidad_repo.list_por_disciplina_ids([d.id for d in disciplinas])
        modalidades_por_disciplina: dict[int, list[ModalidadOut]] = {}
        for m in modalidades:
            modalidades_por_disciplina.setdefault(m.disciplina_id, []).append(ModalidadOut.model_validate(m))
        return [
            DisciplinaConModalidadesOut(
                id=d.id,
                nombre=d.nombre,
                estado=d.estado,
                modalidades=modalidades_por_disciplina.get(d.id, []),
            )
            for d in disciplinas
        ]

    async def update(self, id_: int, data: DisciplinaUpdate) -> Disciplina:
        return await self.repo.update(id_, **data.model_dump(exclude_unset=True))
