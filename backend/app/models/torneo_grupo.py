from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.mixins import TimestampMixin


class TorneoGrupo(TimestampMixin, Base):
    """Agrupa las ediciones de un mismo torneo a través del tiempo (ej.
    "Liga Relámpago" agrupa su Edición 1, Edición 2, ...) —
    docs/plans/torneos-admin-plan.md, Fase 1/3. Cada `Torneo` es una
    edición numerada de su grupo (`Torneo.torneo_grupo_id` +
    `numero_edicion`, UNIQUE por par).

    El nombre mostrado de una edición se COMPONE en runtime
    ("{Nombre} - Edición {numero_edicion}"), nunca se guarda concatenado
    acá ni en Torneo.nombre — así renombrar el grupo actualiza todas sus
    ediciones sin tocar cada fila de TORNEO (Decision Audit Trail #3 del
    plan)."""

    __tablename__ = "torneo_grupo"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
