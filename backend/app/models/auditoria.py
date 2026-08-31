from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Auditoria(Base):
    """Un cambio (alta, modificación o baja lógica) sobre cualquier entidad
    del sistema. La llena sola `app/core/auditoria.py` (un event listener de
    SQLAlchemy), no algo que un service arme a mano — ver el docstring largo
    ahí para el por qué.

    Igual que `Acceso` (ver su docstring), no usa `TimestampMixin`: es
    append-only, así que `fecha_modificacion` no describiría nada real.

    `usuario_id` es nullable por el mismo motivo que en `Acceso`: un cambio
    disparado sin actor resuelto (no debería pasar hoy — toda ruta que
    muta pasa por `require_roles`/`get_current_user` — pero la columna no
    fuerza esa garantía) queda igual registrado, sin usuario.

    `tabla` + `registro_id` identifican la fila afectada sin FK real: no
    hay una tabla única a la que apuntar (son 18 posibles), así que es
    texto libre + entero, resuelto por el listener desde
    `obj.__tablename__` y `obj.id`.
    """

    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    tabla: Mapped[str] = mapped_column(String(50))
    registro_id: Mapped[int]
    # 'crear' | 'modificar' | 'eliminar' (chk_auditoria_accion)
    accion: Mapped[str] = mapped_column(String(20))
    # JSONB en Postgres; JSON genérico como fallback para que el modelo siga
    # siendo válido si algún día corre sobre otro motor en tests unitarios.
    datos_anteriores: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    datos_nuevos: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    ip: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    fecha: Mapped[datetime] = mapped_column(nullable=True, server_default=text("CURRENT_TIMESTAMP"))
