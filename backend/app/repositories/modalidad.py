from app.models.modalidad import Modalidad
from app.repositories.base import BaseRepository


class ModalidadRepository(BaseRepository[Modalidad]):
    model = Modalidad
    nombre_recurso = "Modalidad"
