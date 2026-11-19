from typing import Any

from sqlalchemy import Select, or_, select

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

    def _consulta_filtrada(self, q: str | None = None, incluir_cedula: bool = True, **filtros: Any) -> Select:
        """Filtros de `BaseRepository` más la búsqueda de texto de `buscar`.
        Compartida por el listado y por el conteo (TASK-039), para que el
        total de X-Total-Count cuente exactamente lo que se lista."""
        stmt = super()._consulta_filtrada(**filtros)
        if q is not None and q.strip():
            patron = f"%{q.strip()}%"
            # TASK-014: `incluir_cedula=False` para quien no puede ver datos
            # personales (ver services/permisos.puede_ver_pii).
            criterio = (
                or_(Jugador.nombre.ilike(patron), Jugador.cedula.ilike(patron))
                if incluir_cedula
                else Jugador.nombre.ilike(patron)
            )
            stmt = stmt.where(criterio)
        return stmt

    async def buscar(
        self,
        q: str,
        skip: int = 0,
        limit: int = 100,
        estado: str | None = None,
        incluir_cedula: bool = True,
        ids: list[int] | None = None,
    ) -> list[Jugador]:
        """Búsqueda server-side por nombre (parcial, insensible a
        mayúsculas) o cédula (parcial) — gestion-avanzada-equipos-control-
        mesa-plan.md, Requerimiento 2. Sin esto, el buscador de la
        Plantilla Base filtraría en memoria sobre las primeras 200 filas
        del listado y "no encontraría" un jugador que sí existe (mismo bug
        que ya documenta TODOS.md para Equipos)."""
        stmt = self._consulta_filtrada(q=q, incluir_cedula=incluir_cedula, estado=estado, ids=ids)
        # `id` desempata: sin él, dos homónimos podían repetirse o perderse
        # entre una página y la siguiente.
        stmt = stmt.order_by(Jugador.nombre, Jugador.id).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
