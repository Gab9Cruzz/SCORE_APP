from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

AccionAuditoria = Literal["crear", "modificar", "eliminar"]


class AuditoriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int | None
    tabla: str
    registro_id: int
    accion: AccionAuditoria
    datos_anteriores: dict[str, Any] | None
    datos_nuevos: dict[str, Any] | None
    ip: str | None
    user_agent: str | None
    fecha: datetime
