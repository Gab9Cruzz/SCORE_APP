from typing import Any

from sqlalchemy import select

from app.models.disciplina import Disciplina
from app.repositories.base import BaseRepository


class DisciplinaRepository(BaseRepository[Disciplina]):
    model = Disciplina
    nombre_recurso = "Disciplina"

    async def list(self, skip: int = 0, limit: int = 100, **filtros: Any) -> list[Disciplina]:
        # T28 (motor-formatos-plantillas-navegacion-plan.md): la barra tipo
        # SofaScore ordena por popularidad, no por el id crudo del catálogo
        # (BaseRepository.list ordena por .id). NULLS LAST para las
        # disciplinas sin Orden_Popularidad seteado — quedan al final en
        # vez de romper el orden esperado.
        stmt = select(Disciplina)
        for campo, valor in filtros.items():
            if valor is not None:
                stmt = stmt.where(getattr(Disciplina, campo) == valor)
        stmt = (
            stmt.order_by(Disciplina.orden_popularidad.asc().nullslast(), Disciplina.id)
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
