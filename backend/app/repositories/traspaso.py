from app.models.traspaso import Traspaso
from app.repositories.base import BaseRepository


class TraspasoRepository(BaseRepository[Traspaso]):
    model = Traspaso
    nombre_recurso = "Traspaso"
