from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

EstadoInscripcion = Literal["Inscrito", "Cancelado", "Confirmado"]


class InscripcionTorneoCreate(BaseModel):
    torneo_id: int
    equipo_id: int


class InscripcionTorneoUpdate(BaseModel):
    estado: EstadoInscripcion


class InscripcionTorneoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    torneo_id: int
    equipo_id: int
    estado: EstadoInscripcion
    fecha: datetime
    fecha_registro: datetime
    fecha_modificacion: datetime
