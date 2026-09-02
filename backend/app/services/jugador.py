from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.errors import ConflictError
from app.models.jugador import Jugador
from app.repositories.jugador import JugadorRepository
from app.repositories.jugador_equipo import JugadorEquipoRepository
from app.schemas.jugador import JugadorCreate, JugadorUpdate


class JugadorService:
    def __init__(self, session: AsyncSession):
        self.repo = JugadorRepository(session)
        self.jugador_equipo_repo = JugadorEquipoRepository(session)

    async def get(self, id_: int) -> Jugador:
        return await self.repo.get_or_404(id_)

    async def list(
        self, skip: int = 0, limit: int = 100, estado: str | None = None, q: str | None = None
    ) -> list[Jugador]:
        # q (gestion-avanzada-equipos-control-mesa-plan.md, Requerimiento 2):
        # búsqueda server-side por nombre/cédula, camino separado del
        # listado paginado plano — no tiene sentido combinar skip/limit con
        # un patrón de búsqueda de texto libre en la misma consulta.
        if q is not None and q.strip():
            return await self.repo.buscar(q, skip=skip, limit=limit, estado=estado)
        return await self.repo.list(skip=skip, limit=limit, estado=estado)

    async def create(self, data: JugadorCreate) -> Jugador:
        return await self.repo.create(**data.model_dump())

    async def update(self, id_: int, data: JugadorUpdate) -> Jugador:
        return await self.repo.update(id_, **data.model_dump(exclude_unset=True))

    async def soft_delete(self, id_: int) -> Jugador:
        """3B-3 (docs/plans/cierre-backlog-todos-plan.md): bloquea con 409
        en vez de cascada silenciosa — desactivar a una persona que sigue
        Activa en el roster de algún equipo la haría desaparecer de los
        listados mientras el sistema todavía la cuenta como jugando (goles
        futuros, un traspaso que la busca, la plantilla de su equipo). El
        admin tiene que resolver esas membresías primero (dar de baja del
        equipo o esperar a que termine el torneo), no algo que este
        endpoint deba decidir por él."""
        await self.repo.get_or_404(id_)
        if await self.jugador_equipo_repo.existe_activa_para_jugador(id_):
            raise ConflictError(
                "No se puede desactivar: el jugador tiene membresías activas en algún equipo. "
                "Dalo de baja del roster (o esperá a que termine el torneo) antes de desactivarlo."
            )
        return await self.repo.soft_delete(id_, estado_inactivo="Inactivo")
