from sqlalchemy import select

from app.models.grupo import Grupo
from app.repositories.base import BaseRepository


class GrupoRepository(BaseRepository[Grupo]):
    model = Grupo
    nombre_recurso = "Grupo"

    async def listar_por_fase(self, fase_id: int) -> list[Grupo]:
        stmt = select(Grupo).where(Grupo.fase_id == fase_id).order_by(Grupo.nombre)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
