from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

RolUsuario = Literal["Admin", "Arbitro", "Publico"]
EstadoUsuario = Literal["Activo", "Inactivo"]


class UsuarioCreate(BaseModel):
    username: str
    nombre: str
    password: str
    rol: RolUsuario = "Publico"

    @field_validator("username")
    @classmethod
    def username_normalizado(cls, v: str) -> str:
        # chk_usuarios_username_lower y chk_usuarios_username_min (02_constraints.sql)
        # exigen minúsculas y largo >= 3; se normaliza acá para no gastar un
        # round-trip a la base solo para que el CHECK lo rechace.
        v = v.strip().lower()
        if len(v) < 3:
            raise ValueError("username debe tener al menos 3 caracteres.")
        return v

    @field_validator("password")
    @classmethod
    def password_minima(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("password debe tener al menos 8 caracteres.")
        return v


class UsuarioUpdate(BaseModel):
    nombre: str | None = None
    rol: RolUsuario | None = None
    estado: EstadoUsuario | None = None
    password: str | None = None


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nombre: str
    rol: RolUsuario
    estado: EstadoUsuario
    fecha_registro: datetime
    fecha_modificacion: datetime
