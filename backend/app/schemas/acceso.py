from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

MotivoFallo = Literal["credenciales", "inactivo", "bloqueado"]


class AccesoOut(BaseModel):
    """Solo lectura: ACCESOS no tiene Create/Update expuestos a propósito.
    Las filas las escribe UsuarioService.login() y nadie más — una
    bitácora con endpoint de escritura es una bitácora que se puede
    falsificar desde afuera."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int | None
    username: str
    exitoso: bool
    motivo: MotivoFallo | None
    ip: str | None
    user_agent: str | None
    fecha: datetime
