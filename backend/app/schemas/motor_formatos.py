from pydantic import BaseModel


class SorteoRequest(BaseModel):
    """Semilla opcional (Design sección E / EC del plan): auditable y
    reproducible si se manda, aleatoria si no. Rehacer un sorteo (EC-52)
    usa este mismo endpoint — MotorFormatosService detecta si la fase ya
    tiene partidos y decide bloquear o limpiar+regenerar."""

    semilla: str | None = None
