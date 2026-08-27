from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Disciplina(Base):
    """Catálogo de disciplinas (Fútbol, Tenis, ...). Reemplaza a
    TORNEO.Disciplina (texto libre) — equipos-jugadores-plan.md.

    Sin TimestampMixin: 01_schema.sql no le dio fecha_registro/fecha_modificacion
    a esta tabla (solo Estado), a diferencia de las 9 tablas originales.
    """

    __tablename__ = "disciplina"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(50))
    # Valores válidos: Equipo, Individual (chk_disciplina_tipo). Equipo =
    # sin modalidad (Fútbol). Individual = requiere Modalidad en el torneo.
    tipo: Mapped[str] = mapped_column(String(20))
    # Valores válidos: Activo, Inactivo (chk_disciplina_estado)
    estado: Mapped[str] = mapped_column(String(20), default="Activo")
