from sqlalchemy.ext.asyncio import AsyncSession

from app.models.partido import Partido
from app.models.usuario import Usuario
from app.repositories.partido import PartidoRepository
from app.schemas.partido import PartidoCreate, PartidoUpdate
from app.services.permisos import verificar_arbitro_asignado


class PartidoService:
    def __init__(self, session: AsyncSession):
        self.repo = PartidoRepository(session)

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
