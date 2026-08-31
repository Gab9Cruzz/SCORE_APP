from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Disciplina(Base):
    """Catálogo maestro de disciplinas (Fútbol, Tenis, ...). Reemplaza a
    TORNEO.Disciplina (texto libre) — equipos-jugadores-plan.md.

    Ya no tiene `tipo`: el catálogo se unificó bajo Modalidad.tamano_equipo
    (docs/plans/ediciones-catalogo-disciplinas-plan.md, Decisión A1) — toda
    disciplina tiene 1+ modalidades siempre, así que ya no hace falta
    distinguir "de Equipo" (sin modalidad) de "Individual" (con modalidad)
    acá. Catálogo de solo lectura + toggle de Estado (Decisión C1): no hay
    servicio/endpoint de creación ni de edición de nombre.

    Sin TimestampMixin: 01_schema.sql no le dio fecha_registro/fecha_modificacion
    a esta tabla (solo Estado), a diferencia de las 9 tablas originales.
    """

    __tablename__ = "disciplina"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(50))
    # Valores válidos: Activo, Inactivo (chk_disciplina_estado)
    estado: Mapped[str] = mapped_column(String(20), default="Activo")
    # NULL = no seteado, ordena al final (NULLS LAST) — motor-formatos-
    # plantillas-navegacion-plan.md, requerimiento #3 (barra tipo
    # SofaScore ordenada por popularidad, no alfabético).
    orden_popularidad: Mapped[int | None] = mapped_column(Integer, nullable=True)
