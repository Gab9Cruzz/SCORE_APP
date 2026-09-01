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

    async def set_orden_manual(self, id_: int, orden_manual: int | None) -> GrupoEquipo:
        """3A-12 (docs/plans/cierre-backlog-todos-plan.md, EC-51): NO usa
        `BaseRepository.save_changes` — ese método saltea cualquier campo
        que llegue en `None` (así puede recibir un PATCH parcial sin pisar
        el resto), pero acá `None` es un valor válido y con intención
        propia ("sacar el desempate manual, volver al orden automático"),
        no "no lo toques". Setea el atributo directo, sea cual sea el
        valor."""
        obj = await self.get_or_404(id_)
        obj.orden_manual = orden_manual
        await self.session.commit()
        await self.session.refresh(obj)
        return obj
