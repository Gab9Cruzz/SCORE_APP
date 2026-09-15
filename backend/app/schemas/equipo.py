from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

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
    # Portal Público (portal-publico-feed-partidos-plan.md, C3).
    logo_url: str | None = None

    @field_validator("logo_url")
    @classmethod
    def logo_url_debe_ser_https(cls, v: str | None) -> str | None:
        """E-S2: el vector real no es XSS (un `<img src="javascript:...">`
        no ejecuta en ningún navegador moderno) — es que una URL de
        tercero en una página PÚBLICA filtra IP/Referer de cada visitante
        anónimo al host que el admin pegó, y `http://` rompe la página por
        mixed-content. Se valida en escritura; EquipoOut la neutraliza de
        nuevo en lectura por si el dato entró sucio por otro camino
        (seed, SQL directo)."""
        if v is not None and not v.startswith("https://"):
            raise ValueError("La URL del escudo tiene que empezar con https://.")
        return v


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
    logo_url: str | None = None
    fecha_registro: datetime
    fecha_modificacion: datetime

    @field_validator("logo_url")
    @classmethod
    def neutralizar_logo_url_insegura(cls, v: str | None) -> str | None:
        """E-S2: neutraliza en LECTURA lo que haya entrado sucio antes de
        que existiera esta validación (seed, SQL directo) — el fallback a
        iniciales (avatarUtils.ts) cubre el `None`."""
        return v if v is not None and v.startswith("https://") else None
