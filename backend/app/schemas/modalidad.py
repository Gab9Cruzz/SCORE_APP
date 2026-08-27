from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

EstadoModalidad = Literal["Activo", "Inactivo"]


class ModalidadBase(BaseModel):
    disciplina_id: int
    nombre: str
    tamano_equipo: int

    @field_validator("tamano_equipo")
    @classmethod
    def tamano_equipo_positivo(cls, v: int) -> int:
        # chk_modalidad_tamano: CHECK (Tamano_Equipo > 0)
        if v <= 0:
            raise ValueError("tamano_equipo debe ser mayor a 0.")
        return v


class ModalidadCreate(ModalidadBase):
    pass


class ModalidadUpdate(BaseModel):
    nombre: str | None = None
    tamano_equipo: int | None = None
    estado: EstadoModalidad | None = None

    @field_validator("tamano_equipo")
    @classmethod
    def tamano_equipo_positivo(cls, v: int | None) -> int | None:
        if v is not None and v <= 0:
            raise ValueError("tamano_equipo debe ser mayor a 0.")
        return v


class ModalidadOut(ModalidadBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    estado: EstadoModalidad
