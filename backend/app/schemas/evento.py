from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas._tipos import Nombre50, Texto200

EstadoEvento = Literal["Activo", "Inactivo"]


class EventoBase(BaseModel):
    nombre: str
    descripcion: str | None = None


class EventoCreate(EventoBase):
    nombre: Nombre50  # TASK-029
    descripcion: Texto200 | None = None
    pass


class EventoUpdate(BaseModel):
    nombre: Nombre50 | None = None
    descripcion: Texto200 | None = None
    estado: EstadoEvento | None = None


class EventoOut(EventoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    # TASK-019: GOL, AUTOGOL, TARJETA_AMARILLA, TARJETA_ROJA, CAMBIO, o
    # None para un tipo propio.
    codigo: str | None = None
    estado: EstadoEvento
    fecha_registro: datetime
    fecha_modificacion: datetime
