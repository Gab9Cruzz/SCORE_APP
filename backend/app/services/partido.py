from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.errors import DomainRuleError
from app.models.partido import Partido
from app.models.usuario import Usuario
from app.repositories.fase import FaseRepository
from app.repositories.partido import PartidoRepository
from app.repositories.torneo import TorneoRepository
from app.schemas.partido import PartidoCreate, PartidoUpdate
from app.services.permisos import verificar_arbitro_asignado


class PartidoService:
    def __init__(self, session: AsyncSession):
        self.repo = PartidoRepository(session)
        self.fase_repo = FaseRepository(session)
        self.torneo_repo = TorneoRepository(session)

    async def get(self, id_: int) -> Partido:
        return await self.repo.get_or_404(id_)

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        torneo_id: int | None = None,
        estado: str | None = None,
        arbitro_id: int | None = None,
    ) -> list[Partido]:
        # arbitro_id (Fase 3, D1): filtro más, mismo mecanismo genérico de
        # BaseRepository.list — no hace falta tocar el repositorio.
        return await self.repo.list(
            skip=skip, limit=limit, torneo_id=torneo_id, estado=estado, arbitro_id=arbitro_id
        )

    async def create(self, data: PartidoCreate) -> Partido:
        # Nada de validación de negocio acá: quién disputa el partido y si
        # los equipos están inscritos lo valida trg_partidos_validar_inscripcion
        # (06_triggers.sql). El servicio solo pasa los datos; el trigger
        # rechaza con un mensaje en español que exceptions/handlers.py
        # devuelve tal cual como 400.
        return await self.repo.create(**data.model_dump())

    async def update(self, id_: int, data: PartidoUpdate, usuario_actual: Usuario) -> Partido:
        # Árbitro solo puede tocar SU partido asignado (D5/D6,
        # roles-3-modulos-plan.md Fase 1) — carga una vez, chequea, y
        # reusa ese mismo objeto para guardar (save_changes), sin volver
        # a consultarlo.
        partido = await self.repo.get_or_404(id_)
        verificar_arbitro_asignado(partido, usuario_actual)
        return await self.repo.save_changes(partido, **data.model_dump(exclude_unset=True))

    async def soft_delete(self, id_: int) -> Partido:
        return await self.repo.soft_delete(id_, estado_inactivo="Cancelado")

    async def marcar_walkover(self, id_: int, equipo_ausente_id: int, usuario_actual: Usuario) -> Partido:
        """3B-13 (docs/plans/cierre-backlog-todos-plan.md): cierra el
        partido 3-0 a favor del equipo presente por ausencia del otro —
        vw_resultados_partidos aplica el 3-0 (ver Es_Walkover en
        04_views.sql), fn_propagar_ganador_bracket avanza al ganador solo
        con el flag, sin necesitar eventos de gol reales.

        En Eliminación (incluida la fase de playoffs de Grupos_Playoffs)
        siempre está permitido — el bracket necesita un ganador para
        avanzar. Fuera de eso (Liga, o la fase de grupos en sí) requiere
        que el torneo lo haya habilitado explícitamente
        (Torneo.Permite_Walkover_Grupos) — no todo torneo quiere que un
        no-show cueste 3 puntos automáticos."""
        partido = await self.repo.get_or_404(id_)
        verificar_arbitro_asignado(partido, usuario_actual)

        if partido.estado in ("Finalizado", "Cancelado"):
            raise DomainRuleError(f"Este partido ya está '{partido.estado}' — no se puede marcar walkover.")
        if partido.equipos_id_local is None or partido.equipos_id_visitante is None:
            raise DomainRuleError(
                "Este partido todavía no tiene los dos equipos definidos — esperá a que termine "
                "el partido anterior del bracket."
            )
        if equipo_ausente_id not in (partido.equipos_id_local, partido.equipos_id_visitante):
            raise DomainRuleError("El equipo ausente debe ser uno de los dos que disputan este partido.")

        es_eliminacion = False
        if partido.fase_id is not None:
            fase = await self.fase_repo.get(partido.fase_id)
            es_eliminacion = fase is not None and fase.tipo == "Eliminacion"

        if not es_eliminacion:
            torneo = await self.torneo_repo.get_or_404(partido.torneo_id)
            if not torneo.permite_walkover_grupos:
                raise DomainRuleError(
                    "Este torneo no habilitó walkover para Liga/fase de grupos — activá "
                    "'Permitir walkover en fase de grupos' en la configuración del torneo."
                )

        return await self.repo.save_changes(
            partido, estado="Finalizado", es_walkover=True, walkover_equipo_ausente_id=equipo_ausente_id
        )
