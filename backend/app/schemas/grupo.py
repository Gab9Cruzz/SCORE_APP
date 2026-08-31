from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GrupoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fase_id: int
    nombre: str
    fecha_registro: datetime


class GrupoEquipoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    grupo_id: int
    inscripcion_torneo_id: int
    fecha_registro: datetime
