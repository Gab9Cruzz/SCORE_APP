from app.models.evento import Evento
from app.repositories.base import BaseRepository


class EventoRepository(BaseRepository[Evento]):
    model = Evento
    nombre_recurso = "Evento"
