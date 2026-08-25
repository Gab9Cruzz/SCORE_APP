from datetime import date

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.mixins import TimestampMixin


class JugadorEquipo(TimestampMixin, Base):
    """Plantilla: a qué equipo pertenece un jugador y en qué rango de fechas.

    fn_validar_jugador_partido (06_triggers.sql) usa fecha_inicio/fecha_fin
    para decidir si un jugador podía disputar un partido dado; dorsal es
    único por equipo mientras la fila está vigente (uq_dorsal_por_equipo_vigente,
    03_indexes.sql — índice parcial, así que no se replica acá como constraint
    de Python, la base es quien la hace cumplir).
    """

    __tablename__ = "jugador_equipo"

    id: Mapped[int] = mapped_column(primary_key=True)
    jugador_id: Mapped[int] = mapped_column(ForeignKey("jugadores.id"))
    equipo_id: Mapped[int] = mapped_column(ForeignKey("equipos.id"))
    dorsal: Mapped[int | None]
    fecha_inicio: Mapped[date]
    fecha_fin: Mapped[date | None]
    # Valores válidos: Activo, Inactivo, Suspendido (chk_jugador_equipo_estado)
    estado: Mapped[str] = mapped_column(String(20), default="Activo")
