from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.mixins import TimestampMixin


class EventoPartido(TimestampMixin, Base):
    """Ocurrencia de un evento (gol, tarjeta, cambio) dentro de un partido.

    equipo_id es el equipo AL QUE PERTENECÍA el jugador en ese partido; es
    obligatorio y no se deduce de jugador_equipo (ver el comentario largo en
    01_schema.sql: un jugador con historial en ambos equipos duplicaría el
    gol). Para 'Autogol' el gol se acredita al rival — eso lo resuelve la
    vista vw_goles_acreditados, esta tabla guarda el dato crudo.
    jugador_id_entra solo aplica al evento 'Cambio' (fn_validar_jugador_partido
    lo exige y lo valida).
    """

    __tablename__ = "eventos_partido"

    id: Mapped[int] = mapped_column(primary_key=True)
    partidos_id: Mapped[int] = mapped_column(ForeignKey("partidos.id"))
    jugador_id: Mapped[int] = mapped_column(ForeignKey("jugadores.id"))
    equipo_id: Mapped[int] = mapped_column(ForeignKey("equipos.id"))
    eventos_id: Mapped[int] = mapped_column(ForeignKey("eventos.id"))
    jugador_id_entra: Mapped[int | None] = mapped_column(ForeignKey("jugadores.id"))
    minuto: Mapped[int]
    # Valores válidos: Registrado, Anulado (chk_eventos_partido_estado)
    estado: Mapped[str] = mapped_column(String(20), default="Registrado")
