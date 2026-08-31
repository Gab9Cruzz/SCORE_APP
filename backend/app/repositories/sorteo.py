from sqlalchemy import select

from app.models.sorteo import Sorteo
from app.repositories.base import BaseRepository


class SorteoRepository(BaseRepository[Sorteo]):
    model = Sorteo
    nombre_recurso = "Sorteo"

    async def listar_por_fase(self, fase_id: int) -> list[Sorteo]:
        stmt = select(Sorteo).where(Sorteo.fase_id == fase_id).order_by(Sorteo.fecha_sorteo.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
