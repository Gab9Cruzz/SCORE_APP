from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.errors import DomainRuleError
from app.models.evento import Evento
from app.repositories.evento import EventoRepository
from app.schemas.evento import EventoCreate, EventoUpdate


class EventoService:
    def __init__(self, session: AsyncSession):
        self.repo = EventoRepository(session)

    async def get(self, id_: int) -> Evento:
        return await self.repo.get_or_404(id_)

    async def list(self, skip: int = 0, limit: int = 100, estado: str | None = None) -> list[Evento]:
        return await self.repo.list(skip=skip, limit=limit, estado=estado)

    async def create(self, data: EventoCreate) -> Evento:
        return await self.repo.create(**data.model_dump())

    async def update(self, id_: int, data: EventoUpdate) -> Evento:
        cambios = data.model_dump(exclude_unset=True)
        evento = await self.repo.get_or_404(id_)
        # TASK-019 (FUN-14): un tipo de sistema sostiene marcador, tarjetas y
        # cambios; renombrarlo o darlo de baja rompería esa lógica. La
        # descripción sí se edita.
        if evento.codigo is not None:
            if "nombre" in cambios and cambios["nombre"] != evento.nombre:
                raise DomainRuleError(f"'{evento.nombre}' es un tipo de evento del sistema: no se puede renombrar.")
            if "estado" in cambios and cambios["estado"] != evento.estado:
                raise DomainRuleError(f"'{evento.nombre}' es un tipo de evento del sistema: no se puede dar de baja.")
        return await self.repo.update(id_, **cambios)

    async def soft_delete(self, id_: int) -> Evento:
        evento = await self.repo.get_or_404(id_)
        if evento.codigo is not None:
            raise DomainRuleError(f"'{evento.nombre}' es un tipo de evento del sistema: no se puede dar de baja.")
        return await self.repo.soft_delete(id_, estado_inactivo="Inactivo")

