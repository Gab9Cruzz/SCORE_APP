from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.mixins import TimestampMixin


class Usuario(TimestampMixin, Base):
    """Quien opera el sistema (login), no un participante del torneo.

    Sin FK hacia el dominio de torneos a propósito — ver el comentario en
    01_schema.sql. Username siempre en minúsculas (chk_usuarios_username_lower);
    normalizarlo también acá evita un viaje redundante a la base solo para
    que el CHECK lo rechace.
    """

    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50))
    nombre: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    # Valores válidos: AdminGeneral, TorneoAdmin, Arbitro, Publico (chk_usuarios_rol)
    rol: Mapped[str] = mapped_column(String(20), default="Publico")
    # Valores válidos: Activo, Inactivo (chk_usuarios_estado)
    estado: Mapped[str] = mapped_column(String(20), default="Activo")
