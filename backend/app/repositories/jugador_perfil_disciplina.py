from sqlalchemy import select

from app.models.jugador_perfil_disciplina import JugadorPerfilDisciplina
from app.repositories.base import BaseRepository


class JugadorPerfilDisciplinaRepository(BaseRepository[JugadorPerfilDisciplina]):
    model = JugadorPerfilDisciplina
    nombre_recurso = "Perfil de jugador"

    async def get_by_jugador_y_disciplina(
        self, jugador_id: int, disciplina_id: int
    ) -> JugadorPerfilDisciplina | None:
        """unique_perfil_por_disciplina (02_constraints.sql) — resolver-o-crear
        el perfil al registrar por lote o vincular en Plantillas."""
        stmt = select(JugadorPerfilDisciplina).where(
            JugadorPerfilDisciplina.jugador_id == jugador_id,
            JugadorPerfilDisciplina.disciplina_id == disciplina_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
