from app.models.torneo import Torneo
from app.repositories.base import BaseRepository


class TorneoRepository(BaseRepository[Torneo]):
    model = Torneo
    nombre_recurso = "Torneo"
