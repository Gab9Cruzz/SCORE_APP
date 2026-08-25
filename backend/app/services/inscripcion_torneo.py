from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inscripcion_torneo import InscripcionTorneo
from app.repositories.inscripcion_torneo import InscripcionTorneoRepository
from app.schemas.inscripcion_torneo import InscripcionTorneoCreate, InscripcionTorneoUpdate


class InscripcionTorneoService:
    def __init__(self, session: AsyncSession):
        self.repo = InscripcionTorneoRepository(session)

    async def get(self, id_: int) -> InscripcionTorneo:
        return await self.repo.get_or_404(id_)

    async def list(
        self, skip: int = 0, limit: int = 100, torneo_id: int | None = None, equipo_id: int | None = None
    ) -> list[InscripcionTorneo]:
        return await self.repo.list(skip=skip, limit=limit, torneo_id=torneo_id, equipo_id=equipo_id)

    async def create(self, data: InscripcionTorneoCreate) -> InscripcionTorneo:
        # unique_inscripcion (02_constraints.sql) evita el mismo equipo dos
        # veces en el mismo torneo; el 409 lo arma exceptions/handlers.py.
        return await self.repo.create(**data.model_dump())

    async def update(self, id_: int, data: InscripcionTorneoUpdate) -> InscripcionTorneo:
        return await self.repo.update(id_, **data.model_dump(exclude_unset=True))
