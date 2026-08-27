from sqlalchemy import select

from app.models.jugador import Jugador
from app.repositories.base import BaseRepository


class JugadorRepository(BaseRepository[Jugador]):
    model = Jugador
    nombre_recurso = "Jugador"

    async def get_by_cedula(self, cedula: str) -> Jugador | None:
        """unique_jugador_cedula (02_constraints.sql) — la identidad de la
        persona es la cédula (registro por lote la usa para resolver-o-crear,
        equipos-jugadores-plan.md)."""
        stmt = select(Jugador).where(Jugador.cedula == cedula)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
