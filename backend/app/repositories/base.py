"""CRUD genérico con borrado lógico.

El comentario en 02_constraints.sql es explícito: la API usa borrado lógico
(Estado='Inactivo') y nunca expone un DELETE físico, porque 6 FK tienen ON
DELETE CASCADE y arrastrarían inscripciones, partidos y eventos. Por eso este
repositorio no tiene un método `delete`, solo `soft_delete`.
"""
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.errors import NotFoundError

ModelT = TypeVar("ModelT")


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]
    nombre_recurso: str

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, id_: int) -> ModelT | None:
        return await self.session.get(self.model, id_)

    async def get_or_404(self, id_: int) -> ModelT:
        obj = await self.get(id_)
        if obj is None:
            raise NotFoundError(self.nombre_recurso, id_)
        return obj

    async def list(self, skip: int = 0, limit: int = 100, **filtros: Any) -> list[ModelT]:
        stmt = select(self.model)
        for campo, valor in filtros.items():
            if valor is not None:
                stmt = stmt.where(getattr(self.model, campo) == valor)
        stmt = stmt.order_by(self.model.id).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, **datos: Any) -> ModelT:
        obj = self.model(**datos)
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def update(self, id_: int, **datos: Any) -> ModelT:
        obj = await self.get_or_404(id_)
        return await self.save_changes(obj, **datos)

    async def save_changes(self, obj: ModelT, **datos: Any) -> ModelT:
        """Igual que `update`, pero recibe el objeto ya cargado.

        Separado de `update` para que un caller que necesite hacer algo con
        el objeto ANTES de mutarlo (ej: el ownership-check de Árbitro en
        roles-3-modulos-plan.md Fase 1) no tenga que cargarlo dos veces —
        una para el chequeo y otra dentro de `update`.
        """
        for campo, valor in datos.items():
            if valor is not None:
                setattr(obj, campo, valor)
        await self.session.commit()
        # fecha_modificacion la pisa el trigger fn_actualizar_fecha_modificacion
        # (06_triggers.sql) en el UPDATE; refresh trae ese valor real de vuelta.
        await self.session.refresh(obj)
        return obj

    async def soft_delete(self, id_: int, estado_inactivo: str = "Inactivo") -> ModelT:
        return await self.update(id_, estado=estado_inactivo)
