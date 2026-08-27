from sqlalchemy import Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.mixins import TimestampMixin


class JugadorPerfilDisciplina(TimestampMixin, Base):
    """Perfil de un jugador dentro de una disciplina — un perfil por
    (jugador, disciplina) (unique_perfil_por_disciplina). El roster
    (JugadorEquipo) referencia este id, no al jugador directo.

    suspendido es una sanción explícita — el estado Libre/Activo NO se
    guarda acá, se deriva de si hay una JugadorEquipo vigente (ver
    vw_estado_perfil_disciplina, 04_views.sql, y EC-10/EC-11 del plan):
    guardarlo como columna obliga a recordar actualizarlo en cada
    agencia-libre y cada traspaso. Por eso esta tabla NO tiene Estado
    (a diferencia de las 9 tablas originales) — solo tiene las dos fechas.
    """

    __tablename__ = "jugador_perfil_disciplina"

    id: Mapped[int] = mapped_column(primary_key=True)
    jugador_id: Mapped[int] = mapped_column(ForeignKey("jugadores.id"))
    disciplina_id: Mapped[int] = mapped_column(ForeignKey("disciplina.id"))
    suspendido: Mapped[bool] = mapped_column(Boolean, default=False)
