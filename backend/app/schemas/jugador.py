from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

EstadoJugador = Literal["Activo", "Inactivo"]


class JugadorBase(BaseModel):
    nombre: str


class JugadorCreate(JugadorBase):
    pass


class JugadorUpdate(BaseModel):
    nombre: str | None = None
    estado: EstadoJugador | None = None


class JugadorOut(JugadorBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    estado: EstadoJugador
    fecha_registro: datetime
    fecha_modificacion: datetime
