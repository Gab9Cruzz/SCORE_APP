from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

TipoHito = Literal["Inicio_Partido", "Inicio_Periodo", "Fin_Periodo", "Pausa", "Reanudacion", "Fin_Partido"]


class HitoPartidoCreate(BaseModel):
    tipo_hito: TipoHito
    numero_periodo: int | None = None
    minuto_reloj: int | None = None
    # Solo para tipo_hito='Fin_Partido' de un torneo 'Corrido' — el
    # trigger fn_validar_ganador_corrido exige que PARTIDOS.Ganador_Corrido_ID
    # ya esté seteado antes de que este Hito dispare el pase a
    # Estado='Finalizado' (Flujo 5 del plan: "¿Quién ganó?" antes de
    # "Finalizar partido").
    ganador_corrido_id: int | None = None

    @field_validator("numero_periodo")
    @classmethod
    def periodo_positivo(cls, v: int | None) -> int | None:
        if v is not None and v < 1:
            raise ValueError("numero_periodo debe ser mayor a 0.")
        return v


class HitoPartidoUpdate(BaseModel):
    """Corrección de un hito ya cargado (Flujo 5 del plan: "presioné Fin
    del 1er Tiempo tarde/temprano"). Solo Minuto_Reloj/Timestamp_Real son
    editables — no se puede recategorizar un hito (Tipo_Hito/Numero_Periodo
    fijos): eso sería otro hito, no una corrección del mismo."""

    minuto_reloj: int | None = None
    timestamp_real: datetime | None = None


class HitoPartidoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    partido_id: int
    tipo_hito: TipoHito
    numero_periodo: int | None
    timestamp_real: datetime
    minuto_reloj: int | None
    registrado_por: int
    fecha_registro: datetime


class EstadoCronometroOut(BaseModel):
    """GET /partidos/{id}/cronometro — la máquina de estados calculada,
    para que el frontend no la reimplemente (Fase 3 del plan: "expuesto en
    un endpoint dedicado para que el frontend no reimplemente la máquina
    de estados"). `acciones_permitidas` es la lista de tipo_hito válidos
    para el PRÓXIMO POST — la UI habilita/deshabilita botones con esto,
    nunca decidiendo la secuencia por su cuenta (Flujo 5: "Botón
    deshabilitado, no un error post-submit")."""

    tipo_cronometro: Literal["Periodos", "Corrido"]
    cantidad_periodos: int | None
    duracion_periodo_minutos: int | None
    duracion_descanso_minutos: int | None
    partido_iniciado: bool
    partido_finalizado: bool
    periodo_abierto: int | None
    ultimo_periodo_cerrado: int
    en_pausa: bool
    acciones_permitidas: list[TipoHito]
    hitos: list[HitoPartidoOut]


class DuracionPartidoOut(BaseModel):
    """GET /partidos/{id}/duracion — expone vw_duracion_partido. Todos
    los campos None significa "todavía sin dato" (partido sin Fin_Partido
    registrado), no un error."""

    partido_id: int
    inicio: datetime | None = None
    fin: datetime | None = None
    duracion_segundos: int | None = None
