from datetime import datetime

from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class GrupoEquipo(Base):
    """Resultado del sorteo de grupos: qué equipo (vía su inscripción a
    ESTE torneo) cayó en qué grupo — motor-formatos-plantillas-navegacion-
    plan.md, requerimiento #4. Ancla en INSCRIPCIONES_TORNEO, no en
    EQUIPOS directo (mismo criterio que JUGADOR_EQUIPO): reusa el ancla
    "equipo-en-este-torneo" ya existente en vez de una FK paralela.
    Exclusividad "un equipo, un grupo por fase" la exige
    fn_validar_equipo_un_grupo_por_fase (06_triggers.sql)."""

    __tablename__ = "grupo_equipo"

    id: Mapped[int] = mapped_column(primary_key=True)
    grupo_id: Mapped[int] = mapped_column(ForeignKey("grupo.id"))
    inscripcion_torneo_id: Mapped[int] = mapped_column(ForeignKey("inscripciones_torneo.id"))
    fecha_registro: Mapped[datetime] = mapped_column(nullable=True, server_default=text("CURRENT_TIMESTAMP"))
