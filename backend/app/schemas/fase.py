from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

TipoFase = Literal["Liga", "Grupos", "Eliminacion"]
EstadoFase = Literal["Pendiente", "En_Curso", "Finalizada"]


class FaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    torneo_id: int
    nombre: str
    tipo: TipoFase
    orden: int
    estado: EstadoFase
    fecha_registro: datetime
    fecha_modificacion: datetime
