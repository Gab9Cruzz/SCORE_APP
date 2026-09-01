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
    # 3A-12 (docs/plans/cierre-backlog-todos-plan.md, EC-51): NULL = sin
    # override, el orden automático de vw_tabla_posiciones (PTS/DG/GF)
    # manda solo — ver el comentario de la columna en 01_schema.sql.
    orden_manual: Mapped[int | None] = mapped_column(nullable=True)
    fecha_registro: Mapped[datetime] = mapped_column(nullable=True, server_default=text("CURRENT_TIMESTAMP"))
