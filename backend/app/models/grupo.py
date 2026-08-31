from datetime import datetime

from sqlalchemy import ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Grupo(Base):
    """Grupo dentro de una FASE Tipo='Grupos' ("A", "B", "C"...) — motor de
    formatos, motor-formatos-plantillas-navegacion-plan.md, requerimiento
    #4. Sin TimestampMixin: solo tiene Fecha_Registro (01_schema.sql),
    mismo criterio que TRASPASOS."""

    __tablename__ = "grupo"

    id: Mapped[int] = mapped_column(primary_key=True)
    fase_id: Mapped[int] = mapped_column(ForeignKey("fase.id"))
    nombre: Mapped[str] = mapped_column(String(10))
    fecha_registro: Mapped[datetime] = mapped_column(nullable=True, server_default=text("CURRENT_TIMESTAMP"))
