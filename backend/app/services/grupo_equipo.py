from sqlalchemy.ext.asyncio import AsyncSession

from app.models.grupo_equipo import GrupoEquipo
from app.repositories.grupo_equipo import GrupoEquipoRepository
from app.schemas.grupo import GrupoEquipoOrdenManualUpdate


class GrupoEquipoService:
    """Desempate manual en la tabla de posiciones (3A-12,
    docs/plans/cierre-backlog-todos-plan.md, EC-51 de
    motor-formatos-plantillas-navegacion-plan.md): "enfrentamiento directo
    primero; si persiste el empate, resolución manual del admin". El
    enfrentamiento directo lo resuelve el admin a ojo (no hay cálculo de
    head-to-head en la vista, ver el comentario de vw_tabla_posiciones en
    04_views.sql) — este service solo persiste la decisión ya tomada."""

    def __init__(self, session: AsyncSession):
        self.repo = GrupoEquipoRepository(session)

    async def set_orden_manual(self, id_: int, data: GrupoEquipoOrdenManualUpdate) -> GrupoEquipo:
        return await self.repo.set_orden_manual(id_, data.orden_manual)
