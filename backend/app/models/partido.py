from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.mixins import TimestampMixin


class Partido(TimestampMixin, Base):
    __tablename__ = "partidos"

    id: Mapped[int] = mapped_column(primary_key=True)
    torneo_id: Mapped[int] = mapped_column(ForeignKey("torneo.id"))
    equipos_id_local: Mapped[int] = mapped_column(ForeignKey("equipos.id"))
    equipos_id_visitante: Mapped[int] = mapped_column(ForeignKey("equipos.id"))
    fecha_partido: Mapped[datetime]
    jornada: Mapped[int | None]
    # Valores válidos: Regular, Grupos, Octavos, Cuartos, Semifinal, Final, Tercer puesto
    fase: Mapped[str] = mapped_column(String(30), default="Regular")
    grupo: Mapped[str | None] = mapped_column(String(10))
    # Árbitro asignado a este partido (nullable — puede no tener uno
    # todavía). Un solo árbitro por partido a propósito, ver D6 en
    # roles-3-modulos-plan.md. Usado por el ownership-check de
    # PartidoService/EventoPartidoService (D5).
    arbitro_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    # Valores válidos: Programado, En curso, Finalizado, Cancelado
    estado: Mapped[str] = mapped_column(String(20), default="Programado")
