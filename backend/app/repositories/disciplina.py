from app.models.disciplina import Disciplina
from app.repositories.base import BaseRepository


class DisciplinaRepository(BaseRepository[Disciplina]):
    model = Disciplina
    nombre_recurso = "Disciplina"
