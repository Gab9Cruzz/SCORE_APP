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
    # 3B-13 (docs/plans/cierre-backlog-todos-plan.md).
    es_walkover: bool = False
    walkover_equipo_ausente_id: int | None = None
    fecha_registro: datetime
    fecha_modificacion: datetime


class WalkoverRequest(BaseModel):
    """POST /partidos/{id}/walkover (3B-13) — el equipo que NO se
    presentó. El otro gana 3-0 automático; ver PartidoService.marcar_walkover
    para cuándo está permitido."""

    equipo_ausente_id: int


class ResultadoDirectoEvento(BaseModel):
    """Un evento (gol/tarjeta/cambio) dentro de POST
    /partidos/{id}/resultado-directo (control-mesa-centralizacion-fixture-
    plan.md) — mismo shape que EventoPartidoCreate, salvo `partidos_id`
    (ya viene del path, no se repite acá)."""

    jugador_id: int
    equipo_id: int
    eventos_id: int
    jugador_id_entra: int | None = None
    minuto: int

    @field_validator("minuto")
    @classmethod
    def minuto_en_rango(cls, v: int) -> int:
        # chk_eventos_partido_minuto: 0..130 (120' de prórroga + descuento)
        if not (0 <= v <= 130):
            raise ValueError("minuto debe estar entre 0 y 130.")
        return v

    @field_validator("jugador_id_entra")
    @classmethod
    def entra_distinto_de_sale(cls, v: int | None, info) -> int | None:
        jugador_id = info.data.get("jugador_id")
        if v is not None and jugador_id is not None and v == jugador_id:
            raise ValueError("jugador_id_entra no puede ser el mismo que jugador_id.")
        return v


class ResultadoDirectoCreate(BaseModel):
    """POST /partidos/{id}/resultado-directo — Alternativa A (Sección 5 del
    plan): orquesta Hito Inicio_Partido + N eventos + Hito Fin_Partido en
    una sola transacción atómica (PartidoService.registrar_resultado_directo),
    reusando las MISMAS tablas/triggers que el flujo en vivo — sin tabla
    paralela. Una lista vacía es válida (0-0 sin sucesos)."""

    eventos: list[ResultadoDirectoEvento] = []
    # Solo exigido para torneos 'Corrido' (Tenis/Pádel, sin marcador de
    # goles) — fn_validar_ganador_corrido lo exige al pasar a 'Finalizado'.
    # Un torneo 'Periodos' lo ignora (el resultado sale del marcador de goles).
    ganador_corrido_id: int | None = None
