from datetime import datetime

from sqlalchemy import ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Sorteo(Base):
    """Auditoría append-only de cada sorteo (bracket o grupos) — mismo
    patrón que TRASPASOS: rehacer un sorteo no borra el anterior, lo marca
    'Rehecho' e inserta uno nuevo 'Completado' (EC-52,
    motor-formatos-plantillas-navegacion-plan.md)."""

    __tablename__ = "sorteos"

    id: Mapped[int] = mapped_column(primary_key=True)
    fase_id: Mapped[int] = mapped_column(ForeignKey("fase.id"))
    realizado_por: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    semilla: Mapped[str | None] = mapped_column(String(50))
    fecha_sorteo: Mapped[datetime] = mapped_column(nullable=True, server_default=text("CURRENT_TIMESTAMP"))
    # Valores válidos: Completado, Rehecho (chk_sorteos_estado)
    estado: Mapped[str] = mapped_column(String(20), default="Completado")
