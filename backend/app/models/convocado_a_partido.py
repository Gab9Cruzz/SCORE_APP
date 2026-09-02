from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class ConvocadoAPartido(Base):
    """Titular/suplente/convocado a UN partido puntual (3B-2,
    docs/plans/cierre-backlog-todos-plan.md) — mismo espíritu no-
    autoritativo que EquipoJugadorBase (app/models/equipo_jugador_base.py):
    NO reemplaza a JugadorEquipo (el roster vigente del torneo sigue
    siendo la única fuente de "quién puede jugar en este equipo"), solo
    dice quién de esa plantilla fue convocado a ESTE partido y si arranca
    de titular. Sin fila acá para un partido = comportamiento de siempre
    (toda la plantilla vigente es candidata en Control de Mesa)."""

    __tablename__ = "convocado_a_partido"

    id: Mapped[int] = mapped_column(primary_key=True)
    partido_id: Mapped[int] = mapped_column(ForeignKey("partidos.id"))
    jugador_perfil_id: Mapped[int] = mapped_column(ForeignKey("jugador_perfil_disciplina.id"))
    titular: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha_registro: Mapped[datetime] = mapped_column(nullable=True, server_default=text("CURRENT_TIMESTAMP"))
