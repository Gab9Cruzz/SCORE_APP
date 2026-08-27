from datetime import date

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.mixins import TimestampMixin


class Torneo(TimestampMixin, Base):
    """disciplina_id reemplazó a Disciplina (texto libre) en
    equipos-jugadores-plan.md. modalidad_id es NULL si la disciplina es de
    Tipo='Equipo', obligatorio si es 'Individual' — lo exige
    fn_validar_torneo_modalidad (06_triggers.sql), no un CHECK de Python."""

    __tablename__ = "torneo"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    disciplina_id: Mapped[int] = mapped_column(ForeignKey("disciplina.id"))
    modalidad_id: Mapped[int | None] = mapped_column(ForeignKey("modalidad.id"))
    fecha_inicio: Mapped[date]
    fecha_fin: Mapped[date]
    # Valores válidos: Activo, Inactivo, Finalizado (chk_torneo_estado, 02_constraints.sql)
    estado: Mapped[str] = mapped_column(String(20), default="Activo")
