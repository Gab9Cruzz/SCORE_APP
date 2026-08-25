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
    # Valores válidos: Programado, En curso, Finalizado, Cancelado
    estado: Mapped[str] = mapped_column(String(20), default="Programado")
