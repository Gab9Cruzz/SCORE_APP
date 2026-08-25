from app.models.equipo import Equipo
from app.repositories.base import BaseRepository


class EquipoRepository(BaseRepository[Equipo]):
    model = Equipo
    nombre_recurso = "Equipo"
