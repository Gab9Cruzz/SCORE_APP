from datetime import date

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.mixins import TimestampMixin


class Torneo(TimestampMixin, Base):
    """disciplina_id reemplazó a Disciplina (texto libre) en
    equipos-jugadores-plan.md. modalidad_id es siempre obligatorio desde
    el catálogo unificado (ediciones-catalogo-disciplinas-plan.md, Decisión
    A1): toda disciplina tiene 1+ modalidades, así que todo torneo tiene
    una. Que la modalidad pertenezca a la disciplina lo exige
    fn_validar_torneo_modalidad (06_triggers.sql), no un CHECK de Python."""

    __tablename__ = "torneo"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    disciplina_id: Mapped[int] = mapped_column(ForeignKey("disciplina.id"))
    modalidad_id: Mapped[int] = mapped_column(ForeignKey("modalidad.id"))
    # Cada Torneo es UNA edición de su grupo (torneos-admin-plan.md, Fase 1).
    # numero_edicion es único por grupo (unique_edicion_por_grupo,
    # 02_constraints.sql) — lo asigna TorneoService.create() como
    # MAX(numero_edicion del grupo) + 1, nunca lo manda el cliente.
    torneo_grupo_id: Mapped[int] = mapped_column(ForeignKey("torneo_grupo.id"))
    numero_edicion: Mapped[int] = mapped_column(default=1)
    fecha_inicio: Mapped[date]
    fecha_fin: Mapped[date]
    # Valores válidos: Activo, Inactivo, Finalizado (chk_torneo_estado, 02_constraints.sql)
    estado: Mapped[str] = mapped_column(String(20), default="Activo")
    # Motor de Formatos (motor-formatos-plantillas-navegacion-plan.md,
    # requerimiento #4). Valores válidos: Liga, Eliminacion,
    # Grupos_Playoffs (chk_torneo_formato). La coherencia de los 4
    # parámetros de abajo con el Formato la valida TorneoService (400 con
    # mensaje claro), no un CHECK de Postgres — ver ese comentario en
    # 02_constraints.sql.
    formato: Mapped[str] = mapped_column(String(20), default="Liga")
    ida_vuelta: Mapped[bool] = mapped_column(Boolean, default=False)
    equipos_por_grupo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clasificados_por_grupo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    incluye_tercer_lugar: Mapped[bool] = mapped_column(Boolean, default=True)
