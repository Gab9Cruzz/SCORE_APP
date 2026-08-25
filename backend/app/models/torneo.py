from datetime import date

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.mixins import TimestampMixin


class Torneo(TimestampMixin, Base):
    __tablename__ = "torneo"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    disciplina: Mapped[str] = mapped_column(String(50))
    fecha_inicio: Mapped[date]
    fecha_fin: Mapped[date]
    # Valores válidos: Activo, Inactivo, Finalizado (chk_torneo_estado, 02_constraints.sql)
    estado: Mapped[str] = mapped_column(String(20), default="Activo")
