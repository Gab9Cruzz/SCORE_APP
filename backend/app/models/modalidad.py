from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Modalidad(Base):
    """Modalidad de una disciplina (Fútbol 11, Tenis Singles, Voleibol
    Playa 2x2, ...). tamano_equipo es la única fuente de verdad de cómo se
    inscribe (docs/plans/ediciones-catalogo-disciplinas-plan.md, Decisión
    A1): =1 → Individual (Jugador directo, sin Equipo), =2 → Pareja
    (Equipo autonombrado), >2 → Conjunto (Equipo, nombre libre). Toda
    disciplina tiene 1+ modalidades siempre, incluidas las que antes eran
    Tipo='Equipo' (Fútbol: "Fútbol 11", "Fútbol 5"...).

    Sin TimestampMixin, igual que Disciplina — ver ese modelo.
    """

    __tablename__ = "modalidad"

    id: Mapped[int] = mapped_column(primary_key=True)
    disciplina_id: Mapped[int] = mapped_column(ForeignKey("disciplina.id"))
    nombre: Mapped[str] = mapped_column(String(30))
    # CHECK (Tamano_Equipo > 0) — chk_modalidad_tamano
    tamano_equipo: Mapped[int]
    # 3B-4 (docs/plans/cierre-backlog-todos-plan.md): tope de PLANTILLA
    # (roster completo, con suplentes) para una modalidad de equipo grande
    # (tamano_equipo > 2) — distinto de tamano_equipo, que es cuántos
    # juegan A LA VEZ, no el máximo del plantel. NULL = sin tope (el
    # default de siempre). No aplica a Individual/Pareja: esas ya tienen
    # su tope exacto en tamano_equipo (EC-6, RegistroLoteService).
    tamano_plantilla_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Valores válidos: Activo, Inactivo (chk_modalidad_estado)
    estado: Mapped[str] = mapped_column(String(20), default="Activo")
