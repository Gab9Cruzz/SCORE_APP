from datetime import datetime

from sqlalchemy import ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.mixins import TimestampMixin


class InscripcionTorneo(TimestampMixin, Base):
    """Un equipo inscrito en un torneo. unique_inscripcion evita duplicados."""

    __tablename__ = "inscripciones_torneo"

    id: Mapped[int] = mapped_column(primary_key=True)
    torneo_id: Mapped[int] = mapped_column(ForeignKey("torneo.id"))
    equipo_id: Mapped[int] = mapped_column(ForeignKey("equipos.id"))
    # Fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP (01_schema.sql) — mismo caso
    # que TimestampMixin: hace falta declarar server_default acá o SQLAlchemy
    # manda NULL explícito en vez de dejar que Postgres ponga la fecha.
    fecha: Mapped[datetime] = mapped_column(nullable=True, server_default=text("CURRENT_TIMESTAMP"))
    # Valores válidos: Inscrito, Cancelado, Confirmado (chk_inscripciones_estado)
    estado: Mapped[str] = mapped_column(String(20), default="Inscrito")
