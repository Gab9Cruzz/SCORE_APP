from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.mixins import TimestampMixin


class Equipo(TimestampMixin, Base):
    """disciplina_id/modalidad_id son NOT NULL desde
    equipos-disciplina-navegacion-plan.md (Decisiones #1 a #3): hasta este
    plan un equipo era solo (nombre, estado) y podía inscribirse a un
    torneo de cualquier disciplina sin que nada lo impidiera. Ahora la
    disciplina del equipo es la que se compara contra la del torneo al
    inscribirlo (InscripcionTorneoService.create, D-Eng-9).

    modalidad_id es lo que la UI muestra como "Categoría" (Decisión #2 =
    B1): no hay catálogo de categorías etarias en el sistema, y la
    modalidad es el único eje de clasificación que ya existe, ya tiene
    catálogo y ya está validado. Que la modalidad pertenezca a la
    disciplina lo exige fn_validar_equipo_modalidad (06_triggers.sql),
    espejo de fn_validar_torneo_modalidad — igual que en Torneo, no un
    CHECK de Python.

    La "plantilla" del equipo NO vive acá (Decisión #1 = A1): sigue
    colgando de INSCRIPCIONES_TORNEO vía JUGADOR_EQUIPO, una por torneo.
    EquipoOut.plantilla_total la deriva contando perfiles distintos entre
    todas las inscripciones del equipo — ver EquipoRepository.
    """

    __tablename__ = "equipos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    disciplina_id: Mapped[int] = mapped_column(ForeignKey("disciplina.id"))
    modalidad_id: Mapped[int] = mapped_column(ForeignKey("modalidad.id"))
    # Valores válidos: Activo, Inactivo (chk_equipos_estado)
    estado: Mapped[str] = mapped_column(String(20), default="Activo")
