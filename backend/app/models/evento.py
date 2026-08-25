from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.mixins import TimestampMixin


class Evento(TimestampMixin, Base):
    """Catálogo de tipos de evento: Gol, Autogol, Tarjeta Amarilla, Tarjeta Roja, Cambio.

    No confundir con EventoPartido (app/models/evento_partido.py), que es la
    ocurrencia concreta de uno de estos tipos dentro de un partido.
    """

    __tablename__ = "eventos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(50))
    descripcion: Mapped[str | None] = mapped_column(String(200))
    # Valores válidos: Activo, Inactivo (chk_eventos_estado)
    estado: Mapped[str] = mapped_column(String(20), default="Activo")
