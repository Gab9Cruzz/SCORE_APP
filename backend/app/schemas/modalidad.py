from typing import Literal

from pydantic import BaseModel, ConfigDict

EstadoModalidad = Literal["Activo", "Inactivo"]


class ModalidadUpdate(BaseModel):
    """Catálogo de solo lectura + toggle de Estado (Decisión C1,
    ediciones-catalogo-disciplinas-plan.md) — no se acepta nombre ni
    tamano_equipo: el catálogo es inmutable, un admin solo puede
    activar/desactivar una fila ya cargada por 11_catalogo_disciplinas.sql."""

    estado: EstadoModalidad


class ModalidadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    disciplina_id: int
    nombre: str
    tamano_equipo: int
    estado: EstadoModalidad
