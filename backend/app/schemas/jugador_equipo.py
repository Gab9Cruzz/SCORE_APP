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
    """TASK-017 (FUN-20): solo el dorsal. Las bajas van por
    POST /plantillas/{id}/baja (que valida la fecha) y los cambios de equipo
    por traspaso; cambiar `estado` o `fecha_fin` acá saltaba esas reglas."""

    model_config = ConfigDict(extra="forbid")

    dorsal: int | None = None


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
