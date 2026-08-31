from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.mixins import TimestampMixin


class Jugador(TimestampMixin, Base):
    """Identidad de la persona (única por cédula). El perfil por disciplina
    vive en JugadorPerfilDisciplina — una persona puede jugar Fútbol y
    Tenis con dos perfiles sobre la misma fila acá (equipos-jugadores-plan.md)."""

    __tablename__ = "jugadores"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    cedula: Mapped[str] = mapped_column(String(20))
    # NO es único a nivel de columna a propósito (EC-12 del plan): dos
    # cédulas distintas pueden compartir un correo familiar.
    correo_electronico: Mapped[str] = mapped_column(String(150))
    # Valores válidos: Activo, Inactivo (chk_jugadores_estado)
    estado: Mapped[str] = mapped_column(String(20), default="Activo")
    # nullable a propósito: todos los jugadores existentes quedan sin foto,
    # el frontend cae a iniciales (motor-formatos-plantillas-navegacion-
    # plan.md, requerimiento #3) — sin uploader en este plan, acepta una URL.
    foto_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
