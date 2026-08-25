from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

EstadoEventoPartido = Literal["Registrado", "Anulado"]


class EventoPartidoCreate(BaseModel):
    partidos_id: int
    jugador_id: int
    equipo_id: int
    eventos_id: int
    jugador_id_entra: int | None = None
    minuto: int

    @field_validator("minuto")
    @classmethod
    def minuto_en_rango(cls, v: int) -> int:
        # chk_eventos_partido_minuto: 0..130 (120' de prórroga + descuento)
        if not (0 <= v <= 130):
            raise ValueError("minuto debe estar entre 0 y 130.")
        return v

    @field_validator("jugador_id_entra")
    @classmethod
    def entra_distinto_de_sale(cls, v: int | None, info) -> int | None:
        jugador_id = info.data.get("jugador_id")
        if v is not None and jugador_id is not None and v == jugador_id:
            raise ValueError("jugador_id_entra no puede ser el mismo que jugador_id.")
        return v


class EventoPartidoUpdate(BaseModel):
    estado: EstadoEventoPartido | None = None


class EventoPartidoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    partidos_id: int
    jugador_id: int
    equipo_id: int
    eventos_id: int
    jugador_id_entra: int | None
    minuto: int
    estado: EstadoEventoPartido
    fecha_registro: datetime
    fecha_modificacion: datetime
