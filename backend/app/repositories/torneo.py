from sqlalchemy import select

from app.models.torneo import Torneo
from app.repositories.base import BaseRepository


class TorneoRepository(BaseRepository[Torneo]):
    model = Torneo
    nombre_recurso = "Torneo"

    async def listar_ediciones_del_grupo(self, torneo_grupo_id: int) -> list[Torneo]:
        """Todas las ediciones de un TORNEO_GRUPO, de la más reciente a la
        más antigua — es el orden que espera el selector de Estadísticas
        (torneos-admin-plan.md, Fase 2 parte B) y la tarjeta de la Pestaña
        Torneos ("Ver Torneo" abre la primera de esta lista)."""
        stmt = (
            select(Torneo)
            .where(Torneo.torneo_grupo_id == torneo_grupo_id)
            .order_by(Torneo.numero_edicion.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
