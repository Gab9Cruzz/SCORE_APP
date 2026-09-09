from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class ConvocadoAPartido(Base):
    """Titular/suplente/convocado a UN partido puntual (3B-2,
    docs/plans/cierre-backlog-todos-plan.md) — mismo espíritu no-
    autoritativo que EquipoJugadorBase (app/models/equipo_jugador_base.py):
    NO reemplaza a JugadorEquipo (el roster vigente del torneo sigue
    siendo la única fuente de "quién puede jugar en este equipo"), solo
    dice quién de esa plantilla fue convocado a ESTE partido y si arranca
    de titular. Sin fila acá para un partido = comportamiento de siempre
    (toda la plantilla vigente es candidata en Control de Mesa)."""

    __tablename__ = "convocado_a_partido"

    id: Mapped[int] = mapped_column(primary_key=True)
    partido_id: Mapped[int] = mapped_column(ForeignKey("partidos.id"))
    jugador_perfil_id: Mapped[int] = mapped_column(ForeignKey("jugador_perfil_disciplina.id"))
    titular: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha_registro: Mapped[datetime] = mapped_column(nullable=True, server_default=text("CURRENT_TIMESTAMP"))
    # ETag de concurrencia optimista del PUT de convocatoria
    # (gestionar-partido-alineaciones-plan.md, H4-eng). Lo mantiene
    # trg_convocado_upd_fecha, no el service. NO se puede versionar por el set
    # de IDs: desde que el repositorio hace diff incremental en vez de
    # DELETE+INSERT, cambiar `titular` es un UPDATE que no toca ningún ID, así
    # que el set queda idéntico y el chequeo no detectaría nada.
    fecha_modificacion: Mapped[datetime] = mapped_column(nullable=True, server_default=text("CURRENT_TIMESTAMP"))
    # Valor probatorio de las llegadas tardías (H5-eng): `fecha_registro` sola
    # no alcanza — es el inicio de la transacción y no dice quién lo cargó.
    # Ambas quedan NULL para los convocados de la lista inicial; solo se llenan
    # en el alta aditiva con el partido ya en curso.
    minuto_ingreso: Mapped[int | None] = mapped_column(Integer, nullable=True)
    registrado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
