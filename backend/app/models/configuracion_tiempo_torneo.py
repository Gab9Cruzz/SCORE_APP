from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.mixins import TimestampMixin


class ConfiguracionTiempoTorneo(TimestampMixin, Base):
    """Configuración del cronómetro de un torneo — 1:1 con Torneo
    (gestion-avanzada-equipos-control-mesa-plan.md). Tabla propia en vez de
    columnas en Torneo (que ya tiene 6 columnas condicionadas a Formato):
    este es un eje de configuración sin relación con el formato de
    competición. cantidad_periodos/duracion_periodo_minutos son requeridos
    si tipo_cronometro='Periodos' y prohibidos si 'Corrido'
    (chk_config_tiempo_periodos, 02_constraints.sql)."""

    __tablename__ = "configuracion_tiempo_torneo"

    id: Mapped[int] = mapped_column(primary_key=True)
    torneo_id: Mapped[int] = mapped_column(ForeignKey("torneo.id"))
    # Valores válidos: Periodos, Corrido (chk_config_tiempo_tipo)
    tipo_cronometro: Mapped[str] = mapped_column(String(20))
    cantidad_periodos: Mapped[int | None]
    duracion_periodo_minutos: Mapped[int | None]
    # Informativo únicamente — el cronómetro no lo cuenta activamente.
    duracion_descanso_minutos: Mapped[int | None]
