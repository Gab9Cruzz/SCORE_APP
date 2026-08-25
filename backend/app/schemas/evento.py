from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

EstadoEvento = Literal["Activo", "Inactivo"]


class EventoBase(BaseModel):
    nombre: str
    descripcion: str | None = None


class EventoCreate(EventoBase):
    pass


class EventoUpdate(BaseModel):
    nombre: str | None = None
    descripcion: str | None = None
    estado: EstadoEvento | None = None


class EventoOut(EventoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    estado: EstadoEvento
    fecha_registro: datetime
    fecha_modificacion: datetime
