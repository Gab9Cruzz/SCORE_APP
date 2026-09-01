from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.mixins import TimestampMixin


class EquipoJugadorBase(TimestampMixin, Base):
    """Plantilla Base de un equipo (gestion-avanzada-equipos-control-mesa-plan.md,
    Decisión D1-C): banco de candidatos de un equipo ANTES/independiente de
    cualquier torneo. Explícitamente NO autoritativo — no participa de
    ninguna regla de elegibilidad (esa sigue viviendo exclusivamente en
    JugadorEquipo, torneo-scoped). Se copia a JugadorEquipo recién al
    inscribir el equipo a un torneo (InscripcionTorneoService), momento en
    el que sí pasa por fn_validar_exclusividad_torneo.

    dorsal_sugerido no es autoritativo: solo un valor por defecto al
    copiar — la unicidad real de dorsal sigue viviendo en
    uq_dorsal_por_roster_vigente (torneo-scoped)."""

    __tablename__ = "equipo_jugador_base"

    id: Mapped[int] = mapped_column(primary_key=True)
    equipo_id: Mapped[int] = mapped_column(ForeignKey("equipos.id"))
    jugador_perfil_id: Mapped[int] = mapped_column(ForeignKey("jugador_perfil_disciplina.id"))
    dorsal_sugerido: Mapped[int | None]
    # Valores válidos: Activo, Inactivo (chk_equipo_jugador_base_estado) — baja lógica.
    estado: Mapped[str] = mapped_column(String(20), default="Activo")
