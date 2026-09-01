from sqlalchemy import or_, select

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

    async def buscar(
        self, q: str, skip: int = 0, limit: int = 100, estado: str | None = None
    ) -> list[Jugador]:
        """Búsqueda server-side por nombre (parcial, insensible a
        mayúsculas) o cédula (parcial) — gestion-avanzada-equipos-control-
        mesa-plan.md, Requerimiento 2. Sin esto, el buscador de la
        Plantilla Base filtraría en memoria sobre las primeras 200 filas
        del listado y "no encontraría" un jugador que sí existe (mismo bug
        que ya documenta TODOS.md para Equipos)."""
        patron = f"%{q.strip()}%"
        stmt = select(Jugador).where(or_(Jugador.nombre.ilike(patron), Jugador.cedula.ilike(patron)))
        if estado is not None:
            stmt = stmt.where(Jugador.estado == estado)
        stmt = stmt.order_by(Jugador.nombre).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
