from sqlalchemy import select

from app.models.fase import Fase
from app.repositories.base import BaseRepository


class FaseRepository(BaseRepository[Fase]):
    model = Fase
    nombre_recurso = "Fase"

    async def listar_por_torneo(self, torneo_id: int) -> list[Fase]:
        stmt = select(Fase).where(Fase.torneo_id == torneo_id).order_by(Fase.orden)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def ultima_por_torneo(self, torneo_id: int) -> Fase | None:
        """La FASE de Orden más alto de este torneo — donde "Generar
        Playoffs" engancha la fase nueva (Orden = fase_grupos.Orden + 1)."""
        stmt = select(Fase).where(Fase.torneo_id == torneo_id).order_by(Fase.orden.desc()).limit(1)
        result = await self.session.execute(stmt)
        return result.scalars().first()
