from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Acceso(Base):
    """Un intento de inicio de sesión — exitoso o fallido.

    No usa TimestampMixin, y es la única tabla del proyecto que no lo hace:
    es append-only, así que `fecha_modificacion` no describiría nada real
    (una fila de auditoría no se modifica; si se modificara, sería el
    problema, no el dato). `fecha` es el momento del intento.

    `usuario_id` es nullable a propósito: el intento contra un username que
    no existe es justamente el que más interesa auditar, y ahí no hay a
    quién apuntar. Por eso `username` se guarda aparte, tal como se tipeó,
    y es obligatorio.

    Lo que NO se guarda: la contraseña probada, ni en claro ni hasheada.
    Un hash acá permitiría confirmar offline si una contraseña adivinada
    fue la que alguien usó — es exactamente el dato que una bitácora de
    accesos no debe tener.
    """

    __tablename__ = "accesos"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    username: Mapped[str] = mapped_column(String(50))
    exitoso: Mapped[bool] = mapped_column(Boolean)
    # None si exitoso; 'credenciales' o 'inactivo' si no (chk_accesos_motivo).
    motivo: Mapped[str | None] = mapped_column(String(30))
    ip: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    # Mismo caso que TimestampMixin: hace falta declarar el server_default o
    # SQLAlchemy manda NULL explícito en vez de dejar que Postgres ponga la fecha.
    fecha: Mapped[datetime] = mapped_column(nullable=True, server_default=text("CURRENT_TIMESTAMP"))
