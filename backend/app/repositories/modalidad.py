from sqlalchemy import select

from app.models.modalidad import Modalidad
from app.repositories.base import BaseRepository


class ModalidadRepository(BaseRepository[Modalidad]):
    model = Modalidad
    nombre_recurso = "Modalidad"

    async def list_por_disciplina_ids(self, disciplina_ids: list[int]) -> list[Modalidad]:
        """Todas las Modalidad de un lote de disciplinas en una sola query —
        usado por DisciplinaService.list_con_modalidades para no hacer N+1
        contra el catálogo (una query por disciplina)."""
        if not disciplina_ids:
            return []
        stmt = (
            select(Modalidad)
            .where(Modalidad.disciplina_id.in_(disciplina_ids))
            .order_by(Modalidad.disciplina_id, Modalidad.id)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
