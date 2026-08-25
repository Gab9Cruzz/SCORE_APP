from app.models.evento_partido import EventoPartido
from app.repositories.base import BaseRepository


class EventoPartidoRepository(BaseRepository[EventoPartido]):
    model = EventoPartido
    nombre_recurso = "Evento de partido"
