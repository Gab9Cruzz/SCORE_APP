from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.modalidad import ModalidadOut

EstadoDisciplina = Literal["Activo", "Inactivo"]


class DisciplinaUpdate(BaseModel):
    """Catálogo de solo lectura + toggle de Estado (Decisión C1,
    ediciones-catalogo-disciplinas-plan.md) — no se acepta nombre: el
    catálogo es inmutable, un admin solo puede activar/desactivar una fila
    ya cargada por 11_catalogo_disciplinas.sql. `estado` es obligatorio (no
    hay otro campo que un PATCH pueda mandar)."""

    estado: EstadoDisciplina


class DisciplinaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    estado: EstadoDisciplina


class DisciplinaConModalidadesOut(DisciplinaOut):
    """Vista jerárquica para CatalogoDisciplinasPage (D-Eng arquitectura):
    una sola llamada trae la disciplina con su roster de modalidades, en
    vez de que el cliente arme el árbol cruzando dos listas planas."""

    modalidades: list[ModalidadOut] = []
