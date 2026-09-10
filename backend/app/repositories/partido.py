from collections.abc import Sequence

from sqlalchemy import and_, not_, select

from app.exceptions.errors import NotFoundError
from app.models.partido import Partido
from app.models.torneo import Torneo
from app.models.torneo_grupo import TorneoGrupo
from app.repositories.base import BaseRepository


class PartidoRepository(BaseRepository[Partido]):
    model = Partido
    nombre_recurso = "Partido"

    async def get_or_404_bloqueado(self, id_: int) -> Partido:
        """`SELECT ... FOR UPDATE` (goles-por-marcador-slots-plan.md, Fase 3
        Eng, corrección 2) — usado exclusivamente por
        `PartidoService.registrar_resultado_directo`, que lee `estado`
        UNA vez y después hace varios `flush()` antes del `commit()` final
        sin ningún lock; 2 requests concurrentes sobre el mismo partido
        'Programado' (doble-click antes de que React re-renderice
        `isPending`, o 2 pestañas) podían pasar el guard ambos y ambos
        insertar Inicio_Partido+eventos+Fin_Partido. `AsyncSession.get`
        soporta `with_for_update` nativo (no hace falta un `select()`
        manual) — el lock se libera en el `commit()`/rollback ya existente
        de ese método, sin reestructurar su transacción."""
        obj = await self.session.get(self.model, id_, with_for_update=True)
        if obj is None:
            raise NotFoundError(self.nombre_recurso, id_)
        return obj

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        torneo_ids_permitidos: Sequence[int] | None = None,
        incluir_archivados: bool = False,
        **filtros: object,
    ) -> list[Partido]:
        """Override de BaseRepository.list: mismo mecanismo exacto que
        TorneoRepository.list (control-mesa-centralizacion-fixture-plan.md,
        ítem 1 — GET /partidos?solo_mios=true para la lista de Control de
        Mesa). `torneo_ids_permitidos=[]` (lista vacía, no None) significa
        "el caller no tiene NINGÚN torneo asignado" — debe devolver 0
        filas, no todas; `None` significa "sin restricción" (comportamiento
        de siempre, el de la mayoría de las rutas públicas de /partidos).

        Cascada de archivado (cascada-archivado-alineaciones-traspasos-
        plan.md, P4): siempre hace JOIN Partido -> Torneo -> TorneoGrupo
        (2 hops) y excluye los partidos 'Programado' de un grupo Archivado
        salvo `incluir_archivados=True`. A diferencia de
        TorneoRepository.list, acá NO hay excepción por `torneo_id`
        explícito — un `torneo_id` puntual en /partidos es la navegación
        normal del selector de Control de Mesa, no "ya sé que está
        archivado y quiero verlo igual" (Decision Audit Trail #3). Los
        partidos 'En curso'/'Finalizado' de un grupo archivado NUNCA se
        excluyen (EC-A4) — solo los 'Programado' quedan huérfanos de
        sentido si el torneo se archiva a mitad de camino."""
        stmt = (
            select(Partido)
            .join(Torneo, Torneo.id == Partido.torneo_id)
            .join(TorneoGrupo, TorneoGrupo.id == Torneo.torneo_grupo_id)
        )
        if torneo_ids_permitidos is not None:
            stmt = stmt.where(Partido.torneo_id.in_(torneo_ids_permitidos))
        if not incluir_archivados:
            stmt = stmt.where(not_(and_(TorneoGrupo.estado == "Archivado", Partido.estado == "Programado")))
        for campo, valor in filtros.items():
            if valor is not None:
                stmt = stmt.where(getattr(Partido, campo) == valor)
        stmt = stmt.order_by(Partido.id).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
