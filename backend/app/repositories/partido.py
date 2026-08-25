from app.models.partido import Partido
from app.repositories.base import BaseRepository


class PartidoRepository(BaseRepository[Partido]):
    model = Partido
    nombre_recurso = "Partido"
