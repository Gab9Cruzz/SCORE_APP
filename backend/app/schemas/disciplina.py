from typing import Literal

from pydantic import BaseModel, ConfigDict

EstadoDisciplina = Literal["Activo", "Inactivo"]
TipoDisciplina = Literal["Equipo", "Individual"]


class DisciplinaBase(BaseModel):
    nombre: str
    tipo: TipoDisciplina


class DisciplinaCreate(DisciplinaBase):
    pass


class DisciplinaUpdate(BaseModel):
    nombre: str | None = None
    tipo: TipoDisciplina | None = None
    estado: EstadoDisciplina | None = None


class DisciplinaOut(DisciplinaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    estado: EstadoDisciplina
