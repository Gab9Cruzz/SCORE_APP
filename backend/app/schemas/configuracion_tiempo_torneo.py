from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

TipoCronometro = Literal["Periodos", "Corrido"]


class ConfiguracionTiempoTorneoCreate(BaseModel):
    """Viaja anidado en TorneoCreate/TorneoUpdate como `config_tiempo`
    (gestion-avanzada-equipos-control-mesa-plan.md) — se crea/actualiza en
    la misma transacción que el torneo, nunca por separado. Espejo de
    chk_config_tiempo_periodos (02_constraints.sql): cantidad_periodos y
    duracion_periodo_minutos son obligatorios si tipo_cronometro='Periodos',
    prohibidos si 'Corrido' — Python se anticipa para dar un 400 legible en
    vez del 409 genérico de un CHECK de Postgres violado (mismo criterio
    que TorneoService._validar_parametros_formato)."""

    tipo_cronometro: TipoCronometro
    cantidad_periodos: int | None = None
    duracion_periodo_minutos: int | None = None
    duracion_descanso_minutos: int | None = None

    @model_validator(mode="after")
    def coherencia_periodos(self):
        if self.tipo_cronometro == "Periodos":
            if self.cantidad_periodos is None or self.duracion_periodo_minutos is None:
                raise ValueError(
                    "cantidad_periodos y duracion_periodo_minutos son obligatorios con tipo_cronometro='Periodos'."
                )
        elif self.cantidad_periodos is not None or self.duracion_periodo_minutos is not None:
            raise ValueError(
                "cantidad_periodos y duracion_periodo_minutos no aplican con tipo_cronometro='Corrido'."
            )
        return self


class ConfiguracionTiempoTorneoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    torneo_id: int
    tipo_cronometro: TipoCronometro
    cantidad_periodos: int | None
    duracion_periodo_minutos: int | None
    duracion_descanso_minutos: int | None
    fecha_registro: datetime
    fecha_modificacion: datetime
