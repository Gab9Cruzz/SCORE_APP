from datetime import date

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.mixins import TimestampMixin


class JugadorEquipo(TimestampMixin, Base):
    """Membresía de un perfil de disciplina en el roster de un equipo para
    UN torneo puntual (equipos-jugadores-plan.md). Ya no referencia
    jugador/equipo directo: jugador_perfil_id resuelve la persona+disciplina,
    inscripcion_torneo_id ancla el roster (torneo+equipo, ya único por
    INSCRIPCIONES_TORNEO).

    fn_validar_jugador_partido (06_triggers.sql) usa fecha_inicio/fecha_fin
    para decidir si un jugador podía disputar un partido dado; dorsal es
    único por roster mientras la fila está vigente
    (uq_dorsal_por_roster_vigente, 03_indexes.sql — índice parcial, así que
    no se replica acá como constraint de Python, la base es quien la hace
    cumplir). fn_validar_exclusividad_torneo impide dos membresías Activo
    del mismo perfil en el mismo torneo.
    """

    __tablename__ = "jugador_equipo"

    id: Mapped[int] = mapped_column(primary_key=True)
    jugador_perfil_id: Mapped[int] = mapped_column(ForeignKey("jugador_perfil_disciplina.id"))
    inscripcion_torneo_id: Mapped[int] = mapped_column(ForeignKey("inscripciones_torneo.id"))
    dorsal: Mapped[int | None]
    fecha_inicio: Mapped[date]
    fecha_fin: Mapped[date | None]
    # Valores válidos: Activo, Inactivo, Suspendido, Traspasado
    # (chk_jugador_equipo_estado). 'Traspasado' lo pone el trigger de
    # Traspasos (Etapa C) — deja en la propia fila el POR QUÉ terminó la
    # membresía, sin ir a buscarlo en TRASPASOS.
    estado: Mapped[str] = mapped_column(String(20), default="Activo")
