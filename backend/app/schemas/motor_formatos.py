from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class SorteoRequest(BaseModel):
    """Semilla opcional (Design sección E / EC del plan): auditable y
    reproducible si se manda, aleatoria si no. Rehacer un sorteo (EC-52)
    usa este mismo endpoint — MotorFormatosService detecta si la fase ya
    tiene partidos y decide bloquear o limpiar+regenerar."""

    semilla: str | None = None


class PlayoffsRequest(BaseModel):
    """control-mesa-reactividad-playoffs-plan.md, Fase 3 §6 — cuántos
    equipos clasifican por grupo, opcional: si no se manda, se usa
    `Torneo.clasificados_por_grupo` (o 2 si tampoco está seteado, igual
    que antes de este cambio). Si se manda, además de generar los
    playoffs con ese valor, queda PERSISTIDO en `Torneo.clasificados_por_grupo`
    (Gate Final T2 de ese plan: persistir, no efímero) — la próxima
    generación para este torneo no vuelve a preguntar salvo que el
    operador quiera cambiarlo.

    `formato_eliminatoria` (cierre-fase-regular-llaves-playoffs-plan.md,
    Fase D): igual criterio que `clasificados_por_grupo` — si se manda,
    se PERSISTE en `Torneo.formato_eliminatoria`; si no, se usa el
    guardado."""

    clasificados_por_grupo: int | None = None
    formato_eliminatoria: Literal["Unico", "Ida_Vuelta", "Mixto"] | None = None
    # Desempate de eliminatoria: tiempo extra y penales
    # (docs/plans/desempate-tiempo-extra-penales-plan.md, D1/§3): mismo
    # criterio exacto que `formato_eliminatoria` — si se manda, se
    # PERSISTE en `Torneo.metodo_desempate_eliminatoria`; si no, se usa el
    # guardado. `MotorFormatosService.generar_playoffs` rechaza un valor
    # distinto de 'Manual' si el torneo es 'Corrido' (D5/§7).
    metodo_desempate_eliminatoria: Literal["Manual", "Penales_Directo"] | None = None


class CerrarTorneoRequest(BaseModel):
    """POST /torneos/{id}/cerrar — `orden_podio`: el orden explícito que
    el admin eligió para desempatar equipos empatados en pts/dg/gf en el
    podio de una Liga (Finding 2 / Taste Decision T1), o `None` para
    tomar la tabla tal cual viene. El servidor valida que cada id mandado
    esté inscripto en el torneo y REALMENTE empatado con el equipo que
    desplaza — no es un input de confianza."""

    orden_podio: list[int] | None = None


class FaseEstadoOut(BaseModel):
    id: int
    nombre: str
    tipo: Literal["Liga", "Grupos", "Eliminacion"]
    estado: Literal["Pendiente", "En_Curso", "Finalizada"]


class PodioOut(BaseModel):
    campeon_equipo_id: int | None
    subcampeon_equipo_id: int | None
    tercer_puesto_equipo_id: int | None
    fecha_cierre: datetime | None
    # Admin-only en el frontend (Design review): un torneo cerrado cuya
    # tabla EN VIVO ya no coincide con el podio guardado — nunca en el
    # portal público.
    diverge_de_tabla_actual: bool


class EstadoFaseOut(BaseModel):
    """GET /torneos/{id}/estado-fase — C4 del plan: fuente única de "¿la
    fase terminó y qué se puede hacer ahora?", para que el frontend deje
    de reimplementar esta regla escaneando `partidos` en el cliente.

    El conteo es de 3 partes (Design review — reemplaza el "N de M
    resueltos" original): Finalizado/Cancelado/pendiente, porque la
    regla real es "Finalizado O Cancelado", nunca "100% Finalizado"
    literal (un partido cancelado nunca llega a Finalizado)."""

    fase_actual: FaseEstadoOut | None
    partidos_total: int
    partidos_finalizados: int
    partidos_cancelados: int
    partidos_pendientes: int
    fase_completa: bool
    acciones_disponibles: list[Literal["cerrar_directo", "generar_playoffs"]]
    torneo_cerrado: bool
    podio: PodioOut | None
