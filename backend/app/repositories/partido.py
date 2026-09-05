from collections.abc import Sequence

from sqlalchemy import select

from app.models.partido import Partido
from app.repositories.base import BaseRepository


class PartidoRepository(BaseRepository[Partido]):
    model = Partido
    nombre_recurso = "Partido"

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        torneo_ids_permitidos: Sequence[int] | None = None,
        **filtros: object,
    ) -> list[Partido]:
        """Override de BaseRepository.list: mismo mecanismo exacto que
        TorneoRepository.list (control-mesa-centralizacion-fixture-plan.md,
        ítem 1 — GET /partidos?solo_mios=true para la lista de Control de
        Mesa). `torneo_ids_permitidos=[]` (lista vacía, no None) significa
        "el caller no tiene NINGÚN torneo asignado" — debe devolver 0
        filas, no todas; `None` significa "sin restricción" (comportamiento
        de siempre, el de la mayoría de las rutas públicas de /partidos)."""
        if torneo_ids_permitidos is not None:
            stmt = select(Partido).where(Partido.torneo_id.in_(torneo_ids_permitidos))
            for campo, valor in filtros.items():
                if valor is not None:
                    stmt = stmt.where(getattr(Partido, campo) == valor)
            stmt = stmt.order_by(Partido.id).offset(skip).limit(limit)
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        return await super().list(skip=skip, limit=limit, **filtros)
