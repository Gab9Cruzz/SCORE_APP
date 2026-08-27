from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Modalidad(Base):
    """Modalidad de una disciplina individual (Individual, Dobles, ...).
    tamano_equipo fija cuántos jugadores admite un "equipo" en esa
    modalidad (1 = individual, 2 = dobles/pádel) — equipos-jugadores-plan.md.

    Sin TimestampMixin, igual que Disciplina — ver ese modelo.
    """

    __tablename__ = "modalidad"

    id: Mapped[int] = mapped_column(primary_key=True)
    disciplina_id: Mapped[int] = mapped_column(ForeignKey("disciplina.id"))
    nombre: Mapped[str] = mapped_column(String(30))
    # CHECK (Tamano_Equipo > 0) — chk_modalidad_tamano
    tamano_equipo: Mapped[int]
    # Valores válidos: Activo, Inactivo (chk_modalidad_estado)
    estado: Mapped[str] = mapped_column(String(20), default="Activo")
