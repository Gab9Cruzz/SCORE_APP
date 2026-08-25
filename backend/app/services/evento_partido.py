from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evento_partido import EventoPartido
from app.repositories.evento_partido import EventoPartidoRepository
from app.schemas.evento_partido import EventoPartidoCreate, EventoPartidoUpdate


class EventoPartidoService:
    """Registro de goles/tarjetas/cambios de un partido (rol Arbitro).

    Toda la validación de negocio (el equipo indicado disputa el partido, el
    jugador pertenecía a ese equipo en esa fecha, jugador_id_entra solo para
    'Cambio') la hace fn_validar_jugador_partido (06_triggers.sql). No se
    duplica acá: si se duplicara en Python y el trigger cambiara, quedarían
    desincronizados.
    """

    def __init__(self, session: AsyncSession):
        self.repo = EventoPartidoRepository(session)

    async def get(self, id_: int) -> EventoPartido:
        return await self.repo.get_or_404(id_)

    async def list(
        self, skip: int = 0, limit: int = 100, partidos_id: int | None = None
    ) -> list[EventoPartido]:
        return await self.repo.list(skip=skip, limit=limit, partidos_id=partidos_id)

    async def create(self, data: EventoPartidoCreate) -> EventoPartido:
        return await self.repo.create(**data.model_dump())

    async def anular(self, id_: int) -> EventoPartido:
        """Anula un evento cargado por error (ej: gol mal registrado)."""
        return await self.repo.update(id_, estado="Anulado")
