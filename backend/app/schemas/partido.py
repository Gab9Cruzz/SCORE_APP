from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

EstadoPartido = Literal["Programado", "En curso", "Finalizado", "Cancelado"]
FasePartido = Literal[
    "Regular", "Grupos", "Octavos", "Cuartos", "Semifinal", "Final", "Tercer puesto"
]


class PartidoBase(BaseModel):
    torneo_id: int
    equipos_id_local: int
    equipos_id_visitante: int
    fecha_partido: datetime
    jornada: int | None = None
    fase: FasePartido = "Regular"
    grupo: str | None = None

    @field_validator("equipos_id_visitante")
    @classmethod
    def equipos_distintos(cls, v: int, info):
        local = info.data.get("equipos_id_local")
        if local is not None and v == local:
            raise ValueError("equipos_id_local y equipos_id_visitante deben ser distintos.")
        return v

    @field_validator("jornada")
    @classmethod
    def jornada_positiva(cls, v: int | None) -> int | None:
        if v is not None and v <= 0:
            raise ValueError("jornada debe ser mayor a 0.")
        return v


class PartidoCreate(PartidoBase):
    pass


class PartidoUpdate(BaseModel):
    fecha_partido: datetime | None = None
    jornada: int | None = None
    fase: FasePartido | None = None
    grupo: str | None = None
    estado: EstadoPartido | None = None


class PartidoOut(PartidoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    estado: EstadoPartido
    fecha_registro: datetime
    fecha_modificacion: datetime
