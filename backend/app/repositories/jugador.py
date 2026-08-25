from app.models.jugador import Jugador
from app.repositories.base import BaseRepository


class JugadorRepository(BaseRepository[Jugador]):
    model = Jugador
    nombre_recurso = "Jugador"
