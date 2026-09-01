from sqlalchemy import select

from app.models.hito_partido import HitoPartido
from app.repositories.base import BaseRepository


class HitoPartidoRepository(BaseRepository[HitoPartido]):
    model = HitoPartido
    nombre_recurso = "Hito de partido"

    async def listar_por_partido(self, partido_id: int) -> list[HitoPartido]:
        """Orden de inserción (ID ascendente) — coincide con el orden
        cronológico real porque Timestamp_Real es DEFAULT CURRENT_TIMESTAMP
        y los hitos se crean uno a la vez, nunca en lote. HitoPartidoService
        recorre esta lista para calcular el estado del cronómetro y qué
        acciones habilitar (Flujo 5 del plan)."""
        stmt = select(HitoPartido).where(HitoPartido.partido_id == partido_id).order_by(HitoPartido.id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
