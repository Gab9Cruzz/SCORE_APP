from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

EstadoPartido = Literal["Programado", "En curso", "Finalizado", "Cancelado"]
FasePartido = Literal[
    "Regular", "Grupos", "Octavos", "Cuartos", "Semifinal", "Final", "Tercer puesto"
]
SlotBracket = Literal["Local", "Visitante"]


class PartidoBase(BaseModel):
    torneo_id: int
    equipos_id_local: int
    equipos_id_visitante: int
    fecha_partido: datetime
    jornada: int | None = None
    fase: FasePartido = "Regular"
    grupo: str | None = None

    @field_validator("equipos_id_visitante")
    @classmethod
    def equipos_distintos(cls, v: int, info):
        local = info.data.get("equipos_id_local")
        if local is not None and v == local:
            raise ValueError("equipos_id_local y equipos_id_visitante deben ser distintos.")
        return v

    @field_validator("jornada")
    @classmethod
    def jornada_positiva(cls, v: int | None) -> int | None:
        if v is not None and v <= 0:
            raise ValueError("jornada debe ser mayor a 0.")
        return v


class PartidoCreate(PartidoBase):
    pass


class PartidoUpdate(BaseModel):
    fecha_partido: datetime | None = None
    jornada: int | None = None
    fase: FasePartido | None = None
    grupo: str | None = None
    estado: EstadoPartido | None = None
    # Asignación de árbitro (D6, roles-3-modulos-plan.md) — un paso
    # separado de crear el partido, por eso no está en PartidoCreate.
    arbitro_id: int | None = None
    # Motor de Formatos (EC-48): desempate manual de un partido de
    # Eliminación empatado en goles — se manda ANTES o junto con
    # estado="Finalizado"; fn_validar_partido_eliminacion_desempate
    # rechaza el cierre si hace falta y no vino.
    ganador_desempate_id: int | None = None
    # Motor de Tiempos (gestion-avanzada-equipos-control-mesa-plan.md):
    # ganador de un partido "Corrido" (sin marcador de goles). Normalmente
    # se setea desde HitoPartidoService.registrar (Fin_Partido con
    # ganador_corrido_id) — este campo directo queda para el caso de un
    # PATCH manual de corrección.
    ganador_corrido_id: int | None = None


class PartidoOut(PartidoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    # Override: nullable en un shell de bracket sin equipos definidos
    # todavía ("Ganador Partido N") — PartidoBase los declara
    # obligatorios porque el alta manual (PartidoCreate) sí los exige.
    equipos_id_local: int | None
    equipos_id_visitante: int | None
    estado: EstadoPartido
    arbitro_id: int | None
    # Motor de Formatos — ver comentario grande en 01_schema.sql.
    fase_id: int | None = None
    grupo_id: int | None = None
    ronda_nombre: str | None = None
    partido_siguiente_id: int | None = None
    slot_siguiente: SlotBracket | None = None
    partido_perdedor_siguiente_id: int | None = None
    slot_perdedor_siguiente: SlotBracket | None = None
    ganador_desempate_id: int | None = None
    ganador_corrido_id: int | None = None
    fecha_registro: datetime
    fecha_modificacion: datetime
