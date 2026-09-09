from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

TipoHito = Literal["Inicio_Partido", "Inicio_Periodo", "Fin_Periodo", "Pausa", "Reanudacion", "Fin_Partido"]
# Cierre forzado (modo-vivo-sustituciones-cierre-plan.md, T13/Design Fase 2
# Pass 7): picklist corto en vez de texto libre, para no fragmentar la
# métrica de observabilidad de "cierres forzados por semana" en strings
# distintas — 'Otro' es la única puerta a texto libre, vía motivo_cierre_detalle.
MotivoCierre = Literal["Clima", "Incidente", "Lesion_Grave", "Orden_Seguridad", "Otro"]


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
    # Cierre forzado (Área 4, T6): reusa este mismo endpoint
    # (POST /partidos/{id}/hitos) con tipo_hito='Fin_Partido' — evita un
    # segundo camino de escritura para el mismo Hito terminal (ver Sección 1
    # del plan, Fase 3). `forzado=True` salta el gate normal de
    # acciones_permitidas (HitoPartidoService.registrar) y exige motivo_cierre.
    forzado: bool = False
    motivo_cierre: MotivoCierre | None = None
    motivo_cierre_detalle: str | None = None

    @field_validator("numero_periodo")
    @classmethod
    def periodo_positivo(cls, v: int | None) -> int | None:
        if v is not None and v < 1:
            raise ValueError("numero_periodo debe ser mayor a 0.")
        return v

    @model_validator(mode="after")
    def forzado_solo_fin_partido_con_motivo(self):
        if self.forzado:
            if self.tipo_hito != "Fin_Partido":
                raise ValueError("forzado solo aplica a tipo_hito='Fin_Partido'.")
            if self.motivo_cierre is None:
                raise ValueError("Un cierre forzado necesita motivo_cierre.")
            if self.motivo_cierre == "Otro" and not (self.motivo_cierre_detalle or "").strip():
                raise ValueError("Especificá el motivo del cierre forzado (motivo_cierre_detalle).")
        elif self.motivo_cierre is not None:
            raise ValueError("motivo_cierre solo aplica a un cierre forzado (forzado=true).")
        return self


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
    forzado: bool = False
    motivo_cierre: MotivoCierre | None = None
    motivo_cierre_detalle: str | None = None
    # Solo poblado en la respuesta de un Fin_Partido forzado (T6/T17):
    # ventana de deshacer calculada server-side (Timestamp_Real + 5s), para
    # que el banner de countdown del frontend sobreviva un F5 a mitad de la
    # ventana (Eng Fase 3, corrección de diseño: el commit es INMEDIATO —
    # ver HitoPartidoService.registrar_fin_forzado — el deshacer es una
    # ventana de gracia real en el servidor, no un envío diferido del lado
    # del cliente). `None` en cualquier otro Hito.
    deshacer_disponible_hasta: datetime | None = None


class DeshacerCierreForzadoOut(BaseModel):
    """POST /partidos/{id}/deshacer-cierre-forzado — el partido vuelve a
    'En curso' (o al estado que corresponda según los Hitos que queden)."""

    partido_id: int
    estado: str


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


class TitularesEquipoOut(BaseModel):
    """Cuántos titulares válidos tiene un equipo para este partido. `titulares`
    ya está intersectado contra el roster activo — un convocado dado de baja
    después no cuenta."""

    equipo_id: int
    nombre: str
    titulares: int


class PreflightInicioOut(BaseModel):
    """GET /partidos/{id}/preflight-inicio — ¿se puede tocar "Empezar Partido"?
    (gestionar-partido-alineaciones-plan.md, H1-eng).

    Endpoint propio y AUTENTICADO en vez de campos nuevos en
    `GET /partidos/{id}/cronometro`: ese es público sin auth y lo pollean cada
    5 segundos `Cronometro.tsx` y `PartidoEnVivo.tsx` de forma anónima.

    El frontend NO reimplementa la regla: consume `puede_iniciar` y
    `motivo_bloqueo` tal cual, que salen del mismo código que después aplica el
    gate en `HitoPartidoService.registrar` (C1 del plan — antes existía
    `useTitularesCompletos`, una réplica client-side que podía divergir).

    `titulares_por_equipo` viene vacío cuando no hay nada que contar (partido ya
    iniciado, sin rival definido, o torneo archivado): en esos casos el motivo
    lo explica y el roster ni se consulta."""

    minimo_para_iniciar: int
    # Área 1 (T2/T18): tope SUPERIOR de titulares por equipo — mismo origen
    # que minimo_para_iniciar (Torneo.maximo_titulares_permitido o
    # Modalidad.tamano_equipo), publicado acá para que
    # AlineacionEditor.tsx bloquee el movimiento en el cliente ANTES del
    # POST, sin reimplementar de dónde sale el número.
    maximo_titulares: int
    titulares_por_equipo: list[TitularesEquipoOut]
    puede_iniciar: bool
    motivo_bloqueo: str | None = None
    partido_iniciado: bool


class DuracionPartidoOut(BaseModel):
    """GET /partidos/{id}/duracion — expone vw_duracion_partido. Todos
    los campos None significa "todavía sin dato" (partido sin Fin_Partido
    registrado), no un error."""

    partido_id: int
    inicio: datetime | None = None
    fin: datetime | None = None
    duracion_segundos: int | None = None
