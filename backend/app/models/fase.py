from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.mixins import TimestampMixin


class Fase(TimestampMixin, Base):
    """Formaliza lo que antes era PARTIDOS.Fase (texto libre) — motor de
    formatos, motor-formatos-plantillas-navegacion-plan.md, requerimiento
    #4. Liga/Eliminación → 1 FASE. Grupos + Playoffs → 2 FASES (Orden 1
    'Grupos', Orden 2 'Eliminacion', esta última recién al "Generar
    Playoffs" — Decisión G1: una sola FASE para TODO el bracket, el nombre
    de ronda se denormaliza en PARTIDOS.Ronda_Nombre)."""

    __tablename__ = "fase"

    id: Mapped[int] = mapped_column(primary_key=True)
    torneo_id: Mapped[int] = mapped_column(ForeignKey("torneo.id"))
    nombre: Mapped[str] = mapped_column(String(50))
    # Valores válidos: Liga, Grupos, Eliminacion (chk_fase_tipo)
    tipo: Mapped[str] = mapped_column(String(20))
    orden: Mapped[int]
    # Valores válidos: Pendiente, En_Curso, Finalizada (chk_fase_estado)
    estado: Mapped[str] = mapped_column(String(20), default="Pendiente")
