from sqlalchemy.ext.asyncio import AsyncSession

from app.models.jugador_equipo import JugadorEquipo
from app.repositories.jugador_equipo import JugadorEquipoRepository
from app.schemas.jugador_equipo import JugadorEquipoCreate, JugadorEquipoUpdate


class JugadorEquipoService:
    """Altas/bajas de plantilla. dorsal único por equipo vigente lo hace
    cumplir uq_dorsal_por_equipo_vigente (03_indexes.sql, índice parcial)."""

    def __init__(self, session: AsyncSession):
        self.repo = JugadorEquipoRepository(session)

    async def get(self, id_: int) -> JugadorEquipo:
        return await self.repo.get_or_404(id_)

    async def list(
        self, skip: int = 0, limit: int = 100, equipo_id: int | None = None, jugador_id: int | None = None
    ) -> list[JugadorEquipo]:
        return await self.repo.list(skip=skip, limit=limit, equipo_id=equipo_id, jugador_id=jugador_id)

    async def create(self, data: JugadorEquipoCreate) -> JugadorEquipo:
        return await self.repo.create(**data.model_dump())

    async def update(self, id_: int, data: JugadorEquipoUpdate) -> JugadorEquipo:
        return await self.repo.update(id_, **data.model_dump(exclude_unset=True))

    async def dar_de_baja(self, id_: int, fecha_fin) -> JugadorEquipo:
        """Cierra la vigencia de un jugador en el equipo (libera el dorsal)."""
        return await self.repo.update(id_, fecha_fin=fecha_fin, estado="Inactivo")
