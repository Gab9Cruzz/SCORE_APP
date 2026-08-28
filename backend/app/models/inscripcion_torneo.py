from datetime import datetime

from sqlalchemy import ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.mixins import TimestampMixin


class InscripcionTorneo(TimestampMixin, Base):
    """Un Equipo o un Jugador (perfil de disciplina) inscrito en un torneo
    — exactamente uno de los dos (chk_inscripcion_exactamente_uno,
    02_constraints.sql). Antes de ediciones-catalogo-disciplinas-plan.md
    (Decisión B1) toda inscripción exigía equipo_id, incluso en
    disciplinas individuales (se autocreaba un "equipo" fantasma con el
    nombre del jugador); ahora una disciplina individual
    (Modalidad.tamano_equipo=1) referencia jugador_perfil_id directo, sin
    ninguna fila en EQUIPOS. unique_inscripcion/unique_inscripcion_individual
    evitan duplicados en cada camino."""

    __tablename__ = "inscripciones_torneo"

    id: Mapped[int] = mapped_column(primary_key=True)
    torneo_id: Mapped[int] = mapped_column(ForeignKey("torneo.id"))
    equipo_id: Mapped[int | None] = mapped_column(ForeignKey("equipos.id"))
    jugador_perfil_id: Mapped[int | None] = mapped_column(ForeignKey("jugador_perfil_disciplina.id"))
    # Fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP (01_schema.sql) — mismo caso
    # que TimestampMixin: hace falta declarar server_default acá o SQLAlchemy
    # manda NULL explícito en vez de dejar que Postgres ponga la fecha.
    fecha: Mapped[datetime] = mapped_column(nullable=True, server_default=text("CURRENT_TIMESTAMP"))
    # Valores válidos: Inscrito, Cancelado, Confirmado (chk_inscripciones_estado)
    estado: Mapped[str] = mapped_column(String(20), default="Inscrito")
