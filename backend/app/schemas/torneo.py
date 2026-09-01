from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.schemas.configuracion_tiempo_torneo import ConfiguracionTiempoTorneoCreate, ConfiguracionTiempoTorneoOut

EstadoTorneo = Literal["Activo", "Inactivo", "Finalizado"]
# Motor de Formatos (motor-formatos-plantillas-navegacion-plan.md,
# requerimiento #4) — F1: CHECK enum, no tabla catálogo.
FormatoTorneo = Literal["Liga", "Eliminacion", "Grupos_Playoffs"]


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
    # Ambos opcionales acá — ver TorneoCreate.disciplina_modalidad_requeridas_si_grupo_nuevo:
    # obligatorios solo al crear un TORNEO_GRUPO nuevo (torneo_grupo_nombre).
    # En una edición nueva de un grupo existente (torneo_grupo_id) el
    # service los IGNORA y toma los del grupo sin importar lo que mande el
    # cliente acá (D-Eng-5/EC-26, ediciones-catalogo-disciplinas-plan.md) —
    # la herencia real vive en TorneoService.create, no en este schema.
    disciplina_id: int | None = None
    modalidad_id: int | None = None
    fecha_inicio: date
    fecha_fin: date
    # Motor de Formatos — Formato decide qué parámetros aplican (Design
    # sección E del plan). Coherencia validada en TorneoService (400 con
    # mensaje claro, no un CHECK de Postgres) — ver
    # validar_parametros_formato en ese servicio.
    formato: FormatoTorneo = "Liga"
    ida_vuelta: bool = False
    equipos_por_grupo: int | None = None
    clasificados_por_grupo: int | None = None
    incluye_tercer_lugar: bool = True
    # Motor de Tiempos (gestion-avanzada-equipos-control-mesa-plan.md) — si
    # no se manda, TorneoService la crea con un default derivado de
    # Modalidad.tamano_equipo (Corrido si es individual, Periodos 2x45' si
    # es de equipo). Nunca None una vez creado el torneo — ver TorneoOut.
    config_tiempo: ConfiguracionTiempoTorneoCreate | None = None

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

    @model_validator(mode="after")
    def disciplina_modalidad_requeridas_si_grupo_nuevo(self):
        """Un TORNEO_GRUPO nuevo no tiene ninguna edición previa de la que
        heredar Disciplina/Modalidad — acá sí son obligatorias (a
        diferencia de una edición nueva vía torneo_grupo_id, donde el
        service las ignora y las toma del grupo)."""
        if self.torneo_grupo_nombre and (self.disciplina_id is None or self.modalidad_id is None):
            raise ValueError(
                "disciplina_id y modalidad_id son obligatorios al crear un torneo_grupo nuevo "
                "(torneo_grupo_nombre) — una edición nueva de un grupo existente los hereda solo."
            )
        return self


class TorneoUpdate(BaseModel):
    nombre: str | None = None
    disciplina_id: int | None = None
    modalidad_id: int | None = None
    fecha_inicio: date | None = None
    fecha_fin: date | None = None
    estado: EstadoTorneo | None = None
    # EC-55: cambiar Formato con PARTIDOS ya creados se rechaza en
    # TorneoService.update, no acá (necesita consultar la base).
    formato: FormatoTorneo | None = None
    ida_vuelta: bool | None = None
    equipos_por_grupo: int | None = None
    clasificados_por_grupo: int | None = None
    incluye_tercer_lugar: bool | None = None
    # Si viene, TorneoService.update la crea (si no existía) o la
    # actualiza (si ya existía) — se puede corregir en cualquier momento
    # (EC-13 del plan: no hay trigger que lo impida, es responsabilidad
    # del admin no cambiarla a mitad de un torneo en curso).
    config_tiempo: ConfiguracionTiempoTorneoCreate | None = None


class TorneoOut(TorneoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    # Override: TorneoBase declara estos tres como opcionales solo para la
    # creación (nombre se compone si falta; disciplina_id/modalidad_id se
    # heredan del grupo en una edición nueva — ver sus docstrings). Una vez
    # creado, Torneo siempre tiene un valor real en los tres, nunca None
    # (disciplina_id/modalidad_id son NOT NULL a nivel de columna).
    nombre: str
    disciplina_id: int
    modalidad_id: int
    torneo_grupo_id: int
    numero_edicion: int
    estado: EstadoTorneo
    fecha_registro: datetime
    fecha_modificacion: datetime
    # Override: TorneoBase la tipa como *Create (lo que se manda); acá es
    # lo que se devuelve (con id/timestamps). TorneoService la puebla
    # explícitamente — Torneo (el modelo ORM) no tiene este atributo
    # directo, no es una relationship de SQLAlchemy.
    config_tiempo: ConfiguracionTiempoTorneoOut | None = None
