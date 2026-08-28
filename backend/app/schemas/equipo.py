from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

EstadoEquipo = Literal["Activo", "Inactivo"]


class EquipoBase(BaseModel):
    nombre: str


class EquipoCreate(EquipoBase):
    """disciplina_id/modalidad_id son obligatorios
    (equipos-disciplina-navegacion-plan.md, pedido A: "el formulario debe
    exigir la Disciplina"). Que la modalidad pertenezca a la disciplina lo
    valida EquipoService.create con un mensaje legible (D-Eng-15); el
    trigger de la base es la red de seguridad para un curl directo."""

    disciplina_id: int
    modalidad_id: int


class EquipoUpdate(BaseModel):
    """disciplina_id/modalidad_id se pueden corregir mientras el equipo NO
    esté inscrito en ningún torneo — EquipoService.update rechaza el
    cambio de disciplina si ya tiene inscripciones (EC-38): permitirlo
    dejaría inscripciones que violan la regla que este plan introduce."""

    nombre: str | None = None
    disciplina_id: int | None = None
    modalidad_id: int | None = None
    estado: EstadoEquipo | None = None


class EquipoOut(EquipoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    disciplina_id: int
    modalidad_id: int
    # Perfiles distintos con membresía en CUALQUIER inscripción de este
    # equipo (Decisión #1 = A1: la plantilla del equipo es derivada, no hay
    # tabla de roster permanente). Lo calcula el repositorio con un solo
    # GROUP BY sobre toda la lista, no una consulta por fila (D-Eng-10).
    # Default 0 para que un Equipo recién creado por el service — que
    # todavía no pasó por el listado — serialice sin romper.
    plantilla_total: int = 0
    estado: EstadoEquipo
    fecha_registro: datetime
    fecha_modificacion: datetime
