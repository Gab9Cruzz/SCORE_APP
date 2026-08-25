from app.models.jugador_equipo import JugadorEquipo
from app.repositories.base import BaseRepository


class JugadorEquipoRepository(BaseRepository[JugadorEquipo]):
    model = JugadorEquipo
    nombre_recurso = "Vínculo jugador-equipo"
