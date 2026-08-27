from datetime import datetime

from sqlalchemy import ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Traspaso(Base):
    """Trayectoria de traspasos, append-only (equipos-jugadores-plan.md,
    Fase 1). Nunca se edita ni se borra una fila — "anular" (Fase 2, Etapa
    C) solo cambia Estado a 'Anulado' como anotación visual, no toca
    JUGADOR_EQUIPO ni esta fila de ninguna otra forma. Corregir un
    traspaso mal hecho es un traspaso nuevo en sentido inverso (EC-20).

    Sin TimestampMixin: la tabla solo tiene Fecha_Traspaso, no
    fecha_modificacion (01_schema.sql) — mismo criterio que Disciplina/Modalidad.
    """

    __tablename__ = "traspasos"

    id: Mapped[int] = mapped_column(primary_key=True)
    jugador_perfil_id: Mapped[int] = mapped_column(ForeignKey("jugador_perfil_disciplina.id"))
    # NULL = fichaje desde agencia libre, no un traspaso equipo-a-equipo.
    inscripcion_origen_id: Mapped[int | None] = mapped_column(ForeignKey("inscripciones_torneo.id"))
    inscripcion_destino_id: Mapped[int] = mapped_column(ForeignKey("inscripciones_torneo.id"))
    dorsal_nuevo: Mapped[int | None]
    realizado_por: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    motivo: Mapped[str | None] = mapped_column(String(200))
    fecha_traspaso: Mapped[datetime] = mapped_column(nullable=True, server_default=text("CURRENT_TIMESTAMP"))
    # Valores válidos: Completado, Anulado (chk_traspasos_estado)
    estado: Mapped[str] = mapped_column(String(20), default="Completado")
