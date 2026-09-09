from typing import Any

from sqlalchemy import select

from app.models.evento_partido import EventoPartido
from app.repositories.base import BaseRepository


class EventoPartidoRepository(BaseRepository[EventoPartido]):
    model = EventoPartido
    nombre_recurso = "Evento de partido"

    async def list(self, skip: int = 0, limit: int = 100, **filtros: Any) -> list[EventoPartido]:
        """Override de BaseRepository.list (modo-vivo-sustituciones-cierre-
        plan.md, T7/Área 2): orden CRONOLÓGICO real (`minuto` ascendente,
        `id` como desempate estable para dos eventos del mismo minuto —
        determinístico, no es un error, ver Sección 2 del plan), en vez del
        orden por `id` (orden de inserción) que usa el genérico.

        Antes de esto, el reordenamiento cronológico vivía SOLO como un
        `.sort()` client-side en `MesaPanel.tsx` — cualquier otro consumidor
        (o el propio resultado directo, que carga eventos fuera de orden de
        minuto) veía la lista en orden de inserción. Ahora el backend
        devuelve ya ordenado; el cliente no tiene que reimplementar el sort.
        """
        stmt = select(self.model)
        for campo, valor in filtros.items():
            if valor is not None:
                stmt = stmt.where(getattr(self.model, campo) == valor)
        stmt = stmt.order_by(self.model.minuto, self.model.id).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
