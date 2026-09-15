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
    operador quiera cambiarlo."""

    clasificados_por_grupo: int | None = None
