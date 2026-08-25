from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

EstadoEquipo = Literal["Activo", "Inactivo"]


class EquipoBase(BaseModel):
    nombre: str


class EquipoCreate(EquipoBase):
    pass


class EquipoUpdate(BaseModel):
    nombre: str | None = None
    estado: EstadoEquipo | None = None


class EquipoOut(EquipoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    estado: EstadoEquipo
    fecha_registro: datetime
    fecha_modificacion: datetime
