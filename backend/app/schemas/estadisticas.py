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
    # Motor de Formatos: FK estructurales, en paralelo a fase/grupo (texto
    # libre del alta manual) — ver comentario grande en 01_schema.sql.
    fase_id: int | None = None
    grupo_id: int | None = None
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
    # EC-54 (motor-formatos-plantillas-navegacion-plan.md): un torneo
    # Grupos_Playoffs produce varias tablas bajo el mismo Torneo_ID — el
    # consumidor filtra también por Grupo_ID. NULL en Liga/Eliminación.
    fase_id: int | None = None
    grupo_id: int | None = None
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
    # 3A-12 (docs/plans/cierre-backlog-todos-plan.md, EC-51): NULL en Liga
    # (sin GRUPO_EQUIPO) y en cualquier fila sin desempate manual seteado.
    # grupo_equipo_id es lo que el frontend manda de vuelta en el PATCH de
    # PUT /grupos/equipos/{id} — evita resolverlo aparte.
    grupo_equipo_id: int | None = None
    orden_manual: int | None = None


class PlantillaJugadorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    equipo_id: int
    equipo: str
    jugador_id: int
    jugador: str
    dorsal: int | None
    fecha_inicio: date
