from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

EstadoSorteo = Literal["Completado", "Rehecho"]


class SorteoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fase_id: int
    realizado_por: int
    semilla: str | None
    fecha_sorteo: datetime
    estado: EstadoSorteo
