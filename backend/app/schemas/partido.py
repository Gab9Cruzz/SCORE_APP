from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

EstadoPartido = Literal["Programado", "En curso", "Finalizado", "Cancelado"]
FasePartido = Literal[
    "Regular", "Grupos", "Octavos", "Cuartos", "Semifinal", "Final", "Tercer puesto"
]
SlotBracket = Literal["Local", "Visitante"]
# Desempate de eliminatoria: tiempo extra y penales (docs/plans/desempate-
# tiempo-extra-penales-plan.md, D3/§5) — QUÉ terminó resolviendo un empate
# de tiempo regular.
MetodoDesempate = Literal["Tiempo_Extra", "Penales", "Manual"]
# F7/§8: dominio más angosto que MetodoDesempateEliminatoria (de torneo.py)
# — 'Penales_Salvo_Final' ya se resolvió a uno de estos tres concretos al
# snapshotear.
MetodoDesempateAplicable = Literal["Manual", "Penales_Directo", "Tiempo_Extra_Penales"]


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
    # modo-vivo-sustituciones-cierre-plan.md (Bloque 0, T1/T14): `estado`
    # se retira como campo escribible — PARTIDOS.Estado pasa a ser 100%
    # derivado de Hitos (trg_hito_sincroniza_estado, 06_triggers.sql),
    # nunca un valor que un PATCH pueda fijar directamente. Un cierre
    # forzado inserta un Hito Fin_Partido(forzado=true) en vez de hacer
    # PATCH {estado: "Finalizado"} (ver HitoPartidoService.registrar).
    #
    # `extra="forbid"` es la mitad no negociable de este fix (hallazgo
    # crítico del Eng subagent, Fase 3): sin esto, Pydantic v2 ignora
    # silenciosamente cualquier `estado` que un cliente mande en el body
    # (default `extra="ignore"`), que es exactamente el fallo silencioso
    # que se buscaba cerrar. Con `forbid`, ese PATCH devuelve 422 real.
    model_config = ConfigDict(extra="forbid")

    fecha_partido: datetime | None = None
    jornada: int | None = None
    fase: FasePartido | None = None
    grupo: str | None = None
    # Asignación de árbitro (D6, roles-3-modulos-plan.md) — un paso
    # separado de crear el partido, por eso no está en PartidoCreate.
    arbitro_id: int | None = None
    # Motor de Formatos (EC-48): desempate manual de un partido de
    # Eliminación empatado en goles — se manda ANTES o junto con
    # estado="Finalizado"; fn_validar_partido_eliminacion_desempate
    # rechaza el cierre si hace falta y no vino.
    ganador_desempate_id: int | None = None
    # Desempate de eliminatoria: tiempo extra y penales (D3/§5, SPEC-REVIEW
    # F1): CÓMO se resolvió el empate. Si viene `ganador_desempate_id` sin
    # `metodo_desempate`, PartidoService lo completa a 'Manual' — los
    # caminos de hoy (radio "¿quién avanza?") no saben mandar este campo, y
    # sin ese default `fn_validar_partido_eliminacion_desempate` rechazaría
    # con `desempate_sin_metodo` todo cierre Manual apenas la migración 33
    # esté aplicada.
    metodo_desempate: MetodoDesempate | None = None
    # Marcador de la tanda de penales — PATCH de corrección sobre un
    # partido ya Finalizado (fn_validar_partido_eliminacion_desempate
    # corre las reglas de forma/rango/coherencia también en ese caso, D3/§5).
    penales_local: int | None = None
    penales_visitante: int | None = None
    hubo_tiempo_extra: bool | None = None
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
    # Cierre de Fase Regular + Llaves + Playoffs (Fase A3/D): en el
    # partido de VUELTA, apunta a su IDA — así BracketView puede agrupar
    # las dos piernas de una misma llave. NULL en un partido único o en
    # el de IDA (que no lo lleva).
    partido_ida_id: int | None = None
    ganador_desempate_id: int | None = None
    ganador_corrido_id: int | None = None
    # Desempate de eliminatoria: tiempo extra y penales (D3/§5) — el CÓMO
    # al lado del QUIÉN. Ver la matriz de render de 8 celdas del plan (§11)
    # para cómo combinarlas al mostrar un resultado.
    metodo_desempate: MetodoDesempate | None = None
    penales_local: int | None = None
    penales_visitante: int | None = None
    hubo_tiempo_extra: bool = False
    metodo_desempate_aplicable: MetodoDesempateAplicable | None = None
    # Fase 1 (sin migración) — SPEC-REVIEW S12/D-Q2: reemplaza las dos
    # derivaciones divergentes que tenía el cliente (MesaPanel.tsx
    # ignoraba ida/vuelta y Corrido; ModalResultadoDirecto.tsx sí excluía
    # Corrido) con un solo cálculo en el servidor. `elegible_desempate` es
    # la parte ESTRUCTURAL (¿esta ronda puede terminar en desempate?) —
    # Eliminación, no Corrido, no walkover, y NUNCA una ida (D4/§6: el
    # desempate es de la VUELTA/GLOBAL o de un partido único). No es el
    # booleano final: el cliente sigue siendo quien sabe el marcador que
    # está construyendo (en vivo, o el draft de un resultado directo
    # todavía sin guardar) — por eso además vienen `goles_previos_global_*`:
    # en una VUELTA, los goles YA JUGADOS de la ida, cruzados a la
    # orientación local/visitante de ESTE partido (fn_resolver_llave
    # invierte la ida), para que el cliente arme el global sumando su
    # propio marcador. NULL/0 en un partido único (nada que sumar).
    elegible_desempate: bool = False
    goles_previos_global_local: int | None = None
    goles_previos_global_visitante: int | None = None
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
    # Desempate manual (Fase 0 de cierre-fase-regular-llaves-playoffs-
    # plan.md, Finding 1): solo hace falta si el marcador de goles termina
    # empatado en un partido de fase Eliminación — fn_validar_partido_
    # eliminacion_desempate lo exige al pasar a 'Finalizado'. Mismo patrón
    # que ganador_corrido_id: se setea ANTES del Hito Fin_Partido.
    ganador_desempate_id: int | None = None
    # Desempate de eliminatoria: tiempo extra y penales (D3/§5, D-D12/E4,
    # SPEC-REVIEW F9) — divulgación progresiva en el modal: estos tres
    # solo aparecen cuando `requiere_desempate`/`elegible_desempate` (Fase
    # 1) es true. `penales_local/visitante`: marcador de la tanda — si
    # vienen los dos, PartidoService deriva `metodo_desempate='Penales'` y
    # el ganador de la tanda (rechazado por el trigger si no coincide con
    # `ganador_desempate_id`, cuando también vino). `hubo_tiempo_extra`:
    # checkbox "se jugó prórroga" — si viene TRUE y el marcador final NO
    # está empatado, PartidoService deriva `metodo_desempate='Tiempo_Extra'`
    # (F9: sin esta regla, un "2-1 a.e.t." cargado a mano quedaría con
    # Hubo_Tiempo_Extra=TRUE y Metodo_Desempate=NULL — una celda indefinida
    # en la matriz de render). "No tengo el marcador de la tanda" (E4) es
    # no mandar ninguno de los tres: PartidoService cae a
    # `metodo_desempate='Manual'` con `ganador_desempate_id`, igual que
    # hoy — el escape hatch que mantiene honesta la carga en papel.
    penales_local: int | None = None
    penales_visitante: int | None = None
    hubo_tiempo_extra: bool = False

    @model_validator(mode="after")
    def coherencia_penales(self):
        # D-S1: "un entero del cliente no entra sin techo al acta" —
        # chequeo en Python para un 400 legible antes del 409 genérico del
        # CHECK de Postgres (mismo criterio que el resto del módulo). El
        # trigger (fn_validar_forma_desempate) es la defensa de fondo.
        if (self.penales_local is None) != (self.penales_visitante is None):
            raise ValueError("penales_local y penales_visitante van juntos: los dos o ninguno.")
        if self.penales_local is not None:
            if not (0 <= self.penales_local <= 99) or not (0 <= self.penales_visitante <= 99):
                raise ValueError("El marcador de la tanda de penales debe estar entre 0 y 99.")
            if self.penales_local == self.penales_visitante:
                raise ValueError("Una tanda de penales no puede terminar empatada.")
        return self


# ------------------------------------------------------------
# Portal Público — Feed de Partidos del Día
# (portal-publico-feed-partidos-plan.md, T3.3/F6/F7)
# ------------------------------------------------------------


class FeedTorneoOut(BaseModel):
    """F6: anidado — antes eran 5 campos planos (torneo/torneo_id/
    torneo_grupo/pais/logo_torneo) con tres convenciones de nombre
    distintas conviviendo. `id` es el de la EDICIÓN (Torneo_ID, lo que
    resuelve /torneos/:id), `grupo` es el nombre mostrado (compuesto en
    runtime en el resto del sistema, acá viene directo de TORNEO_GRUPO)."""

    id: int
    nombre: str
    grupo: str
    pais: str | None
    logo_url: str | None


class FeedEquipoOut(BaseModel):
    """F6: `goles` vive DENTRO del equipo (antes goles_local/goles_visitante
    sueltos) — agrupa lo que ya es semánticamente del mismo lado."""

    id: int
    nombre: str
    logo_url: str | None
    goles: int


class FeedPartidoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    partido_id: int
    torneo: FeedTorneoOut
    disciplina_id: int
    disciplina: str
    local: FeedEquipoOut
    visitante: FeedEquipoOut
    fecha_partido: datetime
    estado: EstadoPartido


class FeedResponseOut(BaseModel):
    """Envelope de `GET /api/v1/partidos/feed` — ver el docstring del
    handler (routes/partidos.py) para las 3 reglas no obvias (F12):
    fallback de fecha y su ventana, orden determinista
    torneo_grupo→torneo→fecha→id, y el corte en borde de bloque de
    torneo (`total_disponible` puede ser mayor a `len(partidos)` — no
    porque falten partidos del bloque cortado, sino porque el bloque
    completo que sí entró puede por sí solo superar el `limit` pedido,
    ver E-L5)."""

    fecha_pedida: date
    fecha_efectiva: date
    total_disponible: int
    partidos: list[FeedPartidoOut]
