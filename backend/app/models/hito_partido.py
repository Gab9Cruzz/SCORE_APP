from datetime import datetime

from sqlalchemy import ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class HitoPartido(Base):
    """Hito auditable de un partido (inicio/fin de período,
    pausa/reanudación, fin de partido) — vocabulario único para ambos
    tipos de cronómetro (gestion-avanzada-equipos-control-mesa-plan.md).

    A diferencia de Traspasos (append-only), SÍ se permite UPDATE directo
    sobre minuto_reloj/timestamp_real (corrección de un hito mal cargado):
    queda capturado por el listener genérico de AUDITORIA
    (app/core/auditoria.py). Por eso esta tabla NO tiene fecha_modificacion
    ni TimestampMixin — ver el comentario largo en 01_schema.sql.
    """

    __tablename__ = "hitos_partido"

    id: Mapped[int] = mapped_column(primary_key=True)
    partido_id: Mapped[int] = mapped_column(ForeignKey("partidos.id"))
    # Valores válidos: Inicio_Partido, Inicio_Periodo, Fin_Periodo, Pausa,
    # Reanudacion, Fin_Partido (chk_hitos_partido_tipo)
    tipo_hito: Mapped[str] = mapped_column(String(20))
    numero_periodo: Mapped[int | None]
    timestamp_real: Mapped[datetime] = mapped_column(nullable=True, server_default=text("CURRENT_TIMESTAMP"))
    minuto_reloj: Mapped[int | None]
    registrado_por: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    fecha_registro: Mapped[datetime] = mapped_column(nullable=True, server_default=text("CURRENT_TIMESTAMP"))
