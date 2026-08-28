from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class TorneoGrupoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    fecha_registro: datetime
    fecha_modificacion: datetime


class TorneoGrupoUpdate(BaseModel):
    """Solo renombrar — torneos-admin-plan.md, EC-25: permitido sin
    restricción, actualiza el nombre mostrado de todas sus ediciones
    porque se compone en runtime (nunca se guarda concatenado)."""

    nombre: str


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


class TorneoGrupoConEdiciones(TorneoGrupoOut):
    """Lo que consume la tarjeta de la Pestaña Torneos (Fase 2, paso 1 del
    journey): un grupo + sus ediciones, ordenadas de más reciente a más
    antigua (mismo orden que necesita el desplegable de Estadísticas)."""

    ediciones: list[EdicionResumen]
