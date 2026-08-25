from app.models.inscripcion_torneo import InscripcionTorneo
from app.repositories.base import BaseRepository


class InscripcionTorneoRepository(BaseRepository[InscripcionTorneo]):
    model = InscripcionTorneo
    nombre_recurso = "Inscripción"
