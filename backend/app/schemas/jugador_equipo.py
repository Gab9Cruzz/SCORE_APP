from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

# 'Traspasado' lo pone el trigger de Traspasos (Etapa C), no se ofrece como
# opción manual en el form de edición del frontend — ver PlantillasAdmin.tsx.
EstadoJugadorEquipo = Literal["Activo", "Inactivo", "Suspendido", "Traspasado"]


class JugadorEquipoCreate(BaseModel):
    jugador_perfil_id: int
    inscripcion_torneo_id: int
    dorsal: int | None = None
    fecha_inicio: date


class JugadorEquipoUpdate(BaseModel):
    dorsal: int | None = None
    fecha_fin: date | None = None
    estado: EstadoJugadorEquipo | None = None


class JugadorEquipoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    jugador_perfil_id: int
    inscripcion_torneo_id: int
    dorsal: int | None
    fecha_inicio: date
    fecha_fin: date | None
    estado: EstadoJugadorEquipo
    fecha_registro: datetime
    fecha_modificacion: datetime
