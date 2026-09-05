from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

EstadoTraspaso = Literal["Completado", "Anulado"]


class TraspasoCreate(BaseModel):
    jugador_perfil_id: int
    # NULL = fichaje desde agencia libre.
    inscripcion_origen_id: int | None = None
    inscripcion_destino_id: int
    dorsal_nuevo: int | None = None
    motivo: str | None = None


class TraspasoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    jugador_perfil_id: int
    inscripcion_origen_id: int | None
    inscripcion_destino_id: int
    dorsal_nuevo: int | None
    realizado_por: int
    motivo: str | None
    fecha_traspaso: datetime
    estado: EstadoTraspaso
    # fixes-datos-traspasos-control-mesa-plan.md: computado por
    # TraspasoService, no una columna — le dice al frontend si "Anular"
    # todavía puede ofrecerse (False una vez que el club destino ya
    # arrancó un partido desde este traspaso, o si ya está Anulado).
    puede_anularse: bool = False
