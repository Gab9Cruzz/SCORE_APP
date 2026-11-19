from app.schemas._tipos import MAX_FILAS_LOTE, Cedula, Correo, Dorsal, Nombre100

"""Registro por lote con pantalla dividida (equipos-jugadores-plan.md,
Fase 2). Las dos rutas (validar/confirmar) devuelven 200 siempre — es una
operación de resultados mixtos por fila, no el create de un solo recurso;
"inválido" es un dato en la respuesta, no un error HTTP."""
from datetime import date

from pydantic import BaseModel, Field

from app.schemas.jugador_equipo import JugadorEquipoOut


class RegistroLoteFila(BaseModel):
    cedula: Cedula
    nombre: Nombre100
    correo_electronico: Correo
    dorsal: Dorsal | None = None


class RegistroLoteRequest(BaseModel):
    """Mismo shape para /validar y /confirmar: confirmar SIEMPRE revalida
    contra la base actual (EC-7), no confía en el snapshot que manda el
    cliente — el cliente igual manda las filas "válidas" que vio, no solo
    los ids, porque un jugador nuevo todavía no tiene id."""

    inscripcion_torneo_id: int
    fecha_inicio: date
    filas: list[RegistroLoteFila] = Field(max_length=MAX_FILAS_LOTE)  # TASK-029


class FilaValida(BaseModel):
    fila_index: int
    cedula: str
    nombre: str
    correo_electronico: str
    dorsal: int | None
    # None = jugador nuevo, todavía no existe en JUGADORES.
    jugador_id: int | None


class FilaInvalida(BaseModel):
    fila_index: int
    cedula: str
    nombre: str
    motivo: str


class ValidarLoteResponse(BaseModel):
    validos: list[FilaValida]
    invalidos: list[FilaInvalida]


class ConfirmarLoteResponse(BaseModel):
    insertados: list[JugadorEquipoOut]
    rechazados: list[FilaInvalida]
