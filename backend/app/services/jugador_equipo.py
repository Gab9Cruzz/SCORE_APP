from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.errors import DomainRuleError
from app.models.jugador_equipo import JugadorEquipo
from app.repositories.equipo import EquipoRepository
from app.repositories.inscripcion_torneo import InscripcionTorneoRepository
from app.repositories.jugador_equipo import JugadorEquipoRepository
from app.schemas.jugador_equipo import JugadorEquipoCreate, JugadorEquipoUpdate


class JugadorEquipoService:
    """Altas/bajas de plantilla. dorsal único por roster vigente lo hace
    cumplir uq_dorsal_por_roster_vigente (03_indexes.sql, índice parcial)."""

    def __init__(self, session: AsyncSession):
        self.repo = JugadorEquipoRepository(session)
        self.inscripcion_repo = InscripcionTorneoRepository(session)
        self.equipo_repo = EquipoRepository(session)

    async def get(self, id_: int) -> JugadorEquipo:
        return await self.repo.get_or_404(id_)

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        inscripcion_torneo_id: int | None = None,
        jugador_perfil_id: int | None = None,
        torneo_id: int | None = None,
    ) -> list[JugadorEquipo]:
        # torneo_id necesita un join (no vive directo en la fila, ver
        # JugadorEquipoRepository.listar_por_torneo) — no se puede combinar
        # con el filtro genérico de BaseRepository.list en la misma
        # consulta, así que es una rama aparte (D-Eng-3 del plan).
        if torneo_id is not None:
            return await self.repo.listar_por_torneo(torneo_id, skip=skip, limit=limit)
        return await self.repo.list(
            skip=skip,
            limit=limit,
            inscripcion_torneo_id=inscripcion_torneo_id,
            jugador_perfil_id=jugador_perfil_id,
        )

    async def create(self, data: JugadorEquipoCreate) -> JugadorEquipo:
        # Serializa contra otra transacción concurrente activando el mismo
        # perfil en el mismo torneo (equipos-jugadores-plan.md, Fase 3
        # security review) — fn_validar_exclusividad_torneo (06_triggers.sql)
        # no alcanza sola, ver JugadorEquipoRepository.lock_exclusividad_torneo.
        inscripcion = await self.inscripcion_repo.get_or_404(data.inscripcion_torneo_id)
        await self.repo.lock_exclusividad_torneo(data.jugador_perfil_id, inscripcion.torneo_id)
        # Motor de Plantilla consolidado (Design sección A del plan): mismo
        # criterio que registro_lote.py (EC-18) — se anticipa acá para dar
        # el motivo específico ("ya juega en X") en vez de la excepción
        # cruda de fn_validar_exclusividad_torneo ("jugador_ya_activo_en_este_torneo").
        conflicto = await self.repo.get_activo_en_torneo(data.jugador_perfil_id, inscripcion.torneo_id)
        if conflicto is not None:
            insc_conflicto = await self.inscripcion_repo.get_or_404(conflicto.inscripcion_torneo_id)
            equipo_conflicto = await self.equipo_repo.get_or_404(insc_conflicto.equipo_id)
            raise DomainRuleError(
                f"Ya juega en {equipo_conflicto.nombre} este torneo — usa Traspasos en Plantillas para moverlo"
            )
        # EC-45 (motor-formatos-plantillas-navegacion-plan.md): el alta
        # individual dependía solo del índice uq_dorsal_por_roster_vigente,
        # que cae al 409 genérico de handlers.py sin decir "el dorsal ya
        # está ocupado". Se anticipa acá con el mismo mensaje que ya usa
        # registro_lote.py (EC-13) para el mismo caso.
        if data.dorsal is not None and await self.repo.dorsal_en_uso(
            data.inscripcion_torneo_id, data.dorsal
        ):
            raise DomainRuleError(f"El dorsal {data.dorsal} ya está en uso en este equipo")
        return await self.repo.create(**data.model_dump())

    async def update(self, id_: int, data: JugadorEquipoUpdate) -> JugadorEquipo:
        return await self.repo.update(id_, **data.model_dump(exclude_unset=True))

    async def dar_de_baja(self, id_: int, fecha_fin) -> JugadorEquipo:
        """Cierra la vigencia de un jugador en el equipo (libera el dorsal)."""
        return await self.repo.update(id_, fecha_fin=fecha_fin, estado="Inactivo")
