from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

EstadoTorneoGrupo = Literal["Activo", "Archivado"]


class TorneoGrupoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    estado: EstadoTorneoGrupo
    # Portal Público (portal-publico-feed-partidos-plan.md, C3).
    pais: str | None = None
    logo_url: str | None = None
    fecha_registro: datetime
    fecha_modificacion: datetime

    @field_validator("logo_url")
    @classmethod
    def neutralizar_logo_url_insegura(cls, v: str | None) -> str | None:
        """E-S2: mismo criterio que EquipoOut — filtra en lectura lo que
        haya entrado sucio antes de que existiera esta validación."""
        return v if v is not None and v.startswith("https://") else None


class TorneoGrupoUpdate(BaseModel):
    """Renombrar (torneos-admin-plan.md, EC-25: permitido sin restricción,
    actualiza el nombre mostrado de todas sus ediciones porque se compone
    en runtime, nunca se guarda concatenado) y/o archivar/reactivar (3B-7,
    docs/plans/cierre-backlog-todos-plan.md). Los dos campos opcionales:
    un PATCH que solo archiva no debería tener que repetir el nombre.

    pais/logo_url (portal-publico-feed-partidos-plan.md, C3): cabecera del
    feed/vista pública de torneo — ver D14b, el frontend usa un <select>
    de países para `pais`, no un input libre (esta capa no lo valida)."""

    nombre: str | None = None
    estado: EstadoTorneoGrupo | None = None
    pais: str | None = None
    logo_url: str | None = None

    @field_validator("logo_url")
    @classmethod
    def logo_url_debe_ser_https(cls, v: str | None) -> str | None:
        """E-S2: ver el mismo validador en schemas/equipo.py."""
        if v is not None and not v.startswith("https://"):
            raise ValueError("La URL del logo tiene que empezar con https://.")
        return v


class EdicionResumen(BaseModel):
    """Fila liviana para el selector de ediciones (Fase 2, parte B del
    plan) — evita mandar el TorneoOut completo (disciplina_id,
    modalidad_id...) cuando el frontend solo necesita poblar el
    desplegable "Edición: [...]"."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    numero_edicion: int
    disciplina_id: int
    # Siempre obligatorio desde el catálogo unificado (Decisión A1,
    # ediciones-catalogo-disciplinas-plan.md) — ver Torneo.modalidad_id.
    modalidad_id: int
    estado: str
    fecha_inicio: date
    fecha_fin: date
    # Portal Público (portal-publico-feed-partidos-plan.md, C2/T5.2c/D16):
    # la tarjeta de TorneosAdmin.tsx necesita saber si CADA edición está
    # publicada para mostrar el toggle y el aviso "Vista previa (no
    # publicado)" sin una consulta aparte por edición.
    publicado: bool


class TorneoGrupoConEdiciones(TorneoGrupoOut):
    """Lo que consume la tarjeta de la Pestaña Torneos (Fase 2, paso 1 del
    journey): un grupo + sus ediciones, ordenadas de más reciente a más
    antigua (mismo orden que necesita el desplegable de Estadísticas)."""

    ediciones: list[EdicionResumen]
