from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.estadisticas import EstadisticasRepository
from app.schemas.estadisticas import (
    GoleadorOut,
    PlantillaJugadorOut,
    PosicionOut,
    ProximoPartidoOut,
    ResultadoPartidoOut,
)


class EstadisticasService:
    def __init__(self, session: AsyncSession):
        self.repo = EstadisticasRepository(session)

    async def tabla_posiciones(self, torneo_id: int, grupo_id: int | None = None) -> list[PosicionOut]:
        filas = await self.repo.tabla_posiciones(torneo_id, grupo_id=grupo_id)
        return [PosicionOut.model_validate(f) for f in filas]

    async def goleadores(self, torneo_id: int, limit: int = 50) -> list[GoleadorOut]:
        filas = await self.repo.goleadores(torneo_id, limit=limit)
        return [GoleadorOut.model_validate(f) for f in filas]

    async def proximos_partidos(self, torneo_id: int | None = None) -> list[ProximoPartidoOut]:
        filas = await self.repo.proximos_partidos(torneo_id)
        return [ProximoPartidoOut.model_validate(f) for f in filas]

    async def resultados_partidos(self, torneo_id: int) -> list[ResultadoPartidoOut]:
        filas = await self.repo.resultados_partidos(torneo_id)
        return [ResultadoPartidoOut.model_validate(f) for f in filas]

    async def plantilla_equipo(self, equipo_id: int) -> list[PlantillaJugadorOut]:
        filas = await self.repo.plantilla_equipo(equipo_id)
        return [PlantillaJugadorOut.model_validate(f) for f in filas]
