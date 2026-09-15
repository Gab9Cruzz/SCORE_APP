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
    orden_popularidad: int | None = None
    # Portal Público (portal-publico-feed-partidos-plan.md, F3): id legible
    # para el deep link `/?deporte=<slug>` — generado por
    # fn_generar_disciplina_slug (06_triggers.sql), nunca por el cliente.
    slug: str


class DisciplinaConModalidadesOut(DisciplinaOut):
    """Vista jerárquica para CatalogoDisciplinasPage (D-Eng arquitectura):
    una sola llamada trae la disciplina con su roster de modalidades, en
    vez de que el cliente arme el árbol cruzando dos listas planas."""

    modalidades: list[ModalidadOut] = []


class DisciplinaConPartidosOut(BaseModel):
    """E-L4/E-M3 — GET /disciplinas/con-partidos: sidecar de la barra
    pública de deportes, endpoint propio (no un campo del envelope del
    feed — eso era circular, ver F4). Solo lo que la pill necesita
    pintarse y armar su propio link (`/?deporte=<slug>`)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    nombre: str
