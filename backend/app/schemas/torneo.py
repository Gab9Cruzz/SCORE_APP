from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

EstadoTorneo = Literal["Activo", "Inactivo", "Finalizado"]


class TorneoBase(BaseModel):
    nombre: str
    disciplina_id: int
    # NULL si Disciplina.Tipo='Equipo', obligatorio si es 'Individual' — lo
    # exige fn_validar_torneo_modalidad (06_triggers.sql), no acá: cruza
    # tablas, un validator de Pydantic no ve el Tipo de la disciplina sin
    # una consulta a la base, y esta capa se queda deliberadamente sin
    # acceso a la sesión (ver docstring de EventoPartidoService).
    modalidad_id: int | None = None
    fecha_inicio: date
    fecha_fin: date

    @field_validator("fecha_fin")
    @classmethod
    def fecha_fin_no_anterior(cls, v: date, info):
        inicio = info.data.get("fecha_inicio")
        if inicio and v < inicio:
            raise ValueError("fecha_fin no puede ser anterior a fecha_inicio.")
        return v


class TorneoCreate(TorneoBase):
    pass


class TorneoUpdate(BaseModel):
    nombre: str | None = None
    disciplina_id: int | None = None
    modalidad_id: int | None = None
    fecha_inicio: date | None = None
    fecha_fin: date | None = None
    estado: EstadoTorneo | None = None


class TorneoOut(TorneoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    estado: EstadoTorneo
    fecha_registro: datetime
    fecha_modificacion: datetime
