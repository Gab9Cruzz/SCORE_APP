"""Schemas de solo lectura, uno por vista de /database/04_views.sql."""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ProximoPartidoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    partido_id: int
    torneo_id: int
    torneo: str
    equipo_local_id: int
    equipo_local: str
    equipo_visitante_id: int
    equipo_visitante: str
    fecha_partido: datetime
    jornada: int | None
    fase: str
    grupo: str | None
    estado: str


class ResultadoPartidoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    partido_id: int
    torneo_id: int
    equipo_local_id: int
    equipo_local: str
    equipo_visitante_id: int
    equipo_visitante: str
    goles_local: int
    goles_visitante: int
    fecha_partido: datetime
    jornada: int | None
    fase: str
    grupo: str | None
    estado: str


class GoleadorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    torneo_id: int
    jugador_id: int
    jugador: str
    equipo_id: int
    equipo: str
    goles: int


class PosicionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    torneo_id: int
    equipo_id: int
    equipo: str
    pj: int
    pg: int
    pe: int
    pp: int
    gf: int
    gc: int
    dg: int
    pts: int


class PlantillaJugadorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    equipo_id: int
    equipo: str
    jugador_id: int
    jugador: str
    dorsal: int | None
    fecha_inicio: date
