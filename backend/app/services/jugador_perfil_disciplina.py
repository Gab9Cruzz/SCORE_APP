from sqlalchemy.ext.asyncio import AsyncSession

from app.models.jugador_perfil_disciplina import JugadorPerfilDisciplina
from app.repositories.jugador_perfil_disciplina import JugadorPerfilDisciplinaRepository
from app.schemas.jugador_perfil_disciplina import (
    JugadorPerfilDisciplinaCreate,
    JugadorPerfilDisciplinaUpdate,
)


class JugadorPerfilDisciplinaService:
    """Sin soft_delete: la tabla no tiene Estado (ver el modelo) — el
    estado Libre/Activo/Suspendido se deriva vía vw_estado_perfil_disciplina,
    no se borra lógicamente un perfil."""

    def __init__(self, session: AsyncSession):
        self.repo = JugadorPerfilDisciplinaRepository(session)

    async def get(self, id_: int) -> JugadorPerfilDisciplina:
        return await self.repo.get_or_404(id_)

    async def list(
        self, skip: int = 0, limit: int = 100, jugador_id: int | None = None, disciplina_id: int | None = None
    ) -> list[JugadorPerfilDisciplina]:
        return await self.repo.list(skip=skip, limit=limit, jugador_id=jugador_id, disciplina_id=disciplina_id)

    async def create(self, data: JugadorPerfilDisciplinaCreate) -> JugadorPerfilDisciplina:
        # unique_perfil_por_disciplina (02_constraints.sql) evita un
        # segundo perfil para la misma (jugador, disciplina) — 409.
        return await self.repo.create(**data.model_dump())

    async def update(self, id_: int, data: JugadorPerfilDisciplinaUpdate) -> JugadorPerfilDisciplina:
        return await self.repo.update(id_, **data.model_dump(exclude_unset=True))
