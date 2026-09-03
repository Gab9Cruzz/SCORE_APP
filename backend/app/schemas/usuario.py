from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

RolUsuario = Literal["AdminGeneral", "TorneoAdmin", "Arbitro", "Publico"]
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

    @field_validator("password")
    @classmethod
    def password_minima(cls, v: str | None) -> str | None:
        # roles-3-modulos-plan.md, Fase 4, D3: UsuarioCreate ya tenía este
        # mínimo, acá faltaba — agujero preexistente que antes solo era
        # alcanzable llamando la API cruda, ahora es un click de distancia
        # con el form de edición de Usuarios. `None` (no tocar la
        # contraseña) sigue siendo válido, solo se valida si mandan algo.
        if v is not None and len(v) < 8:
            raise ValueError("password debe tener al menos 8 caracteres.")
        return v


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nombre: str
    rol: RolUsuario
    estado: EstadoUsuario
    # rbac-licencias-torneos-plan.md, §4.5 (corrección post outside-voice):
    # sin este campo, el toggle del panel de Admin General no tiene con
    # qué pintar su estado inicial al cargar GET /usuarios.
    licencia_activa: bool
    fecha_registro: datetime
    fecha_modificacion: datetime


class LicenciaUpdate(BaseModel):
    """Body de PATCH /usuarios/{id}/licencia (rbac-licencias-torneos-plan.md, §4.5)."""

    activa: bool


class AsignacionTorneosUpdate(BaseModel):
    """Body de PATCH /usuarios/{id}/torneos — reemplaza el set completo de
    torneos asignados (rbac-licencias-torneos-plan.md, §4.5; endpoint
    corregido de PUT a PATCH, ver Eng review hallazgo #2)."""

    torneo_ids: list[int]
