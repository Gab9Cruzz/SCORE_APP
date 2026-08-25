from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.mixins import TimestampMixin


class Equipo(TimestampMixin, Base):
    __tablename__ = "equipos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    # Valores válidos: Activo, Inactivo (chk_equipos_estado)
    estado: Mapped[str] = mapped_column(String(20), default="Activo")
