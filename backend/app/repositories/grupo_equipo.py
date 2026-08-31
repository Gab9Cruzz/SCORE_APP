from sqlalchemy import select

from app.models.grupo_equipo import GrupoEquipo
from app.repositories.base import BaseRepository


class GrupoEquipoRepository(BaseRepository[GrupoEquipo]):
    model = GrupoEquipo
    nombre_recurso = "GrupoEquipo"

    async def listar_por_grupo(self, grupo_id: int) -> list[GrupoEquipo]:
        stmt = select(GrupoEquipo).where(GrupoEquipo.grupo_id == grupo_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def listar_por_grupos(self, grupo_ids: list[int]) -> list[GrupoEquipo]:
        if not grupo_ids:
            return []
        stmt = select(GrupoEquipo).where(GrupoEquipo.grupo_id.in_(grupo_ids))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
