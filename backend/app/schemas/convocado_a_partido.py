from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConvocadoInput(BaseModel):
    """Una fila de la convocatoria que manda el frontend — ver
    ConvocatoriaSetRequest para el shape completo del PUT."""

    jugador_perfil_id: int
    titular: bool = False


class ConvocatoriaSetRequest(BaseModel):
    """PUT /partidos/{id}/convocados reemplaza la convocatoria ENTERA de
    ese partido de una sola vez (3B-2, docs/plans/cierre-backlog-todos-plan.md)
    — no hay POST/DELETE de una fila suelta: el flujo real es "el
    entrenador arma la lista completa antes del partido", no ir tildando
    de a uno contra el servidor. Una lista vacía es válida (saca la
    convocatoria entera, vuelve al comportamiento de siempre: toda la
    plantilla es candidata)."""

    convocados: list[ConvocadoInput]


class ConvocadoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    partido_id: int
    jugador_perfil_id: int
    titular: bool
    fecha_registro: datetime
