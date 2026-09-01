from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GrupoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fase_id: int
    nombre: str
    fecha_registro: datetime


class GrupoEquipoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    grupo_id: int
    inscripcion_torneo_id: int
    orden_manual: int | None = None
    fecha_registro: datetime


class GrupoEquipoOrdenManualUpdate(BaseModel):
    """3A-12 (docs/plans/cierre-backlog-todos-plan.md, EC-51): `None`
    explícito es un valor válido acá — "sacar el desempate manual, volver
    al orden automático de PTS/DG/GF" — por eso el campo no es opcional
    (si lo fuera, un PATCH con `{"orden_manual": null}` y uno sin el campo
    serían indistinguibles para Pydantic; ver GrupoEquipoRepository.set_orden_manual
    para la otra mitad de esta misma decisión)."""

    # gt=0: mismo chequeo que chk_grupo_equipo_orden_manual
    # (02_constraints.sql) — se repite acá para devolver un 422 legible en
    # vez del 500 genérico de un CHECK de Postgres.
    orden_manual: int | None = Field(gt=0)
    model_config = ConfigDict(json_schema_extra={"example": {"orden_manual": 1}})
