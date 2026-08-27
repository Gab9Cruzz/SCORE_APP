from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

EstadoTorneo = Literal["Activo", "Inactivo", "Finalizado"]


class TorneoBase(BaseModel):
    nombre: str | None = None
    """Opcional en la creación (torneos-admin-plan.md, Decision Audit
    Trail #3): si no se manda, TorneoService.create() lo compone como
    "{grupo.nombre} - Edición {numero_edicion}" — el mismo criterio que
    usa el frontend para MOSTRAR el nombre, así queda persistido también
    para quien lea Torneo.nombre directo (reportes, listados viejos) sin
    duplicar una fuente de verdad distinta. Sigue siendo un campo real
    (no se puede omitir en TorneoOut): un admin puede pisarlo a mano si
    quiere un nombre propio distinto al compuesto."""
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
    """Exactamente uno de los dos (torneos-admin-plan.md, Fase 1/3):
    - `torneo_grupo_id`: esto es una EDICIÓN NUEVA de un grupo ya
      existente — TorneoService.create() calcula numero_edicion como
      MAX(del grupo) + 1, nunca lo manda el cliente.
    - `torneo_grupo_nombre`: crea un TORNEO_GRUPO nuevo (numero_edicion=1).
      Siempre crea un grupo — si el nombre tipeado coincide con uno ya
      existente, es responsabilidad del frontend detectarlo y mandar
      `torneo_grupo_id` en su lugar (journey, paso 1: el admin elige un
      grupo existente desde la tarjeta, no lo escribe de nuevo)."""

    torneo_grupo_id: int | None = None
    torneo_grupo_nombre: str | None = None

    @model_validator(mode="after")
    def exactamente_un_origen_de_grupo(self):
        tiene_id = self.torneo_grupo_id is not None
        tiene_nombre = bool(self.torneo_grupo_nombre and self.torneo_grupo_nombre.strip())
        if tiene_id == tiene_nombre:  # ambos True o ambos False
            raise ValueError(
                "Mandá exactamente uno: torneo_grupo_id (nueva edición de un grupo existente) "
                "o torneo_grupo_nombre (crea un grupo nuevo)."
            )
        return self


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
    # Override: TorneoBase lo declara opcional solo para la creación
    # (ver su docstring) — una vez creado, TorneoService.create() siempre
    # lo deja con un valor real (propio o compuesto), nunca None.
    nombre: str
    torneo_grupo_id: int
    numero_edicion: int
    estado: EstadoTorneo
    fecha_registro: datetime
    fecha_modificacion: datetime
