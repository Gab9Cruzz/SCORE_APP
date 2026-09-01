from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evento_partido import EventoPartido
from app.models.usuario import Usuario
from app.repositories.evento_partido import EventoPartidoRepository
from app.repositories.partido import PartidoRepository
from app.schemas.evento_partido import EventoPartidoCreate, EventoPartidoUpdate
from app.services.permisos import verificar_arbitro_asignado


class EventoPartidoService:
    """Registro de goles/tarjetas/cambios de un partido (rol Arbitro).

    Toda la validación de negocio (el equipo indicado disputa el partido, el
    jugador pertenecía a ese equipo en esa fecha, jugador_id_entra solo para
    'Cambio') la hace fn_validar_jugador_partido (06_triggers.sql). No se
    duplica acá: si se duplicara en Python y el trigger cambiara, quedarían
    desincronizados.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = EventoPartidoRepository(session)
        self.partido_repo = PartidoRepository(session)

    async def get(self, id_: int) -> EventoPartido:
        return await self.repo.get_or_404(id_)

    async def list(
        self, skip: int = 0, limit: int = 100, partidos_id: int | None = None
    ) -> list[EventoPartido]:
        return await self.repo.list(skip=skip, limit=limit, partidos_id=partidos_id)

    async def create(self, data: EventoPartidoCreate, usuario_actual: Usuario) -> EventoPartido:
        # Árbitro solo puede cargar eventos en SU partido asignado (D5,
        # roles-3-modulos-plan.md Fase 1). No hay una carga previa que
        # reusar acá — es una consulta nueva, distinta del insert que sigue.
        partido = await self.partido_repo.get_or_404(data.partidos_id)
        verificar_arbitro_asignado(partido, usuario_actual)
        return await self.repo.create(**data.model_dump())

    async def corregir_minuto(self, id_: int, minuto: int, usuario_actual: Usuario) -> EventoPartido:
        """PATCH /eventos-partido/{id} (gestion-avanzada-equipos-control-
        mesa-plan.md) — corrección de minuto de un gol/tarjeta/cambio ya
        cargado, gap preexistente que responde directamente al Entregable
        3 del plan ("¿cómo editás minutos si el árbitro se equivoca?") para
        el caso de eventos de partido, distinto del de Hitos de tiempo (ver
        HitoPartidoService.corregir). Se permite en cualquier estado del
        partido, incluido 'Finalizado' (EC-15) — un error se puede
        descubrir después de cerrado. El UPDATE vuelve a pasar por
        fn_validar_jugador_partido (revalidación en UPDATE, 06_triggers.sql)."""
        evento = await self.repo.get_or_404(id_)
        partido = await self.partido_repo.get_or_404(evento.partidos_id)
        verificar_arbitro_asignado(partido, usuario_actual)
        return await self.repo.save_changes(evento, minuto=minuto)

    async def anular(self, id_: int, usuario_actual: Usuario) -> EventoPartido:
        """Anula un evento cargado por error (ej: gol mal registrado).

        Único de los tres chequeos que reusa una carga que ya iba a pasar:
        get_or_404(id_) trae el evento (para saber su partidos_id) antes de
        mutar, en vez de una consulta aparte.
        """
        evento = await self.repo.get_or_404(id_)
        partido = await self.partido_repo.get_or_404(evento.partidos_id)
        verificar_arbitro_asignado(partido, usuario_actual)
        return await self.repo.save_changes(evento, estado="Anulado")
