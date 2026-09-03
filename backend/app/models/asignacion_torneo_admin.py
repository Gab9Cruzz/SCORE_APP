from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.mixins import TimestampMixin


class AsignacionTorneoAdmin(TimestampMixin, Base):
    """Asignación N:M Usuario (TorneoAdmin) ↔ Torneo
    (rbac-licencias-torneos-plan.md, §3.2).

    Fila = "este usuario puede administrar este torneo". Estado en vez de
    DELETE (mismo criterio soft-delete que el resto del esquema): revocar
    acceso es un flip a 'Inactivo', no borrar la fila — así tildar/destildar
    el mismo torneo en el modal de asignación no reinserta el historial de
    auditoría una y otra vez. unique_asignacion_usuario_torneo (02_constraints.sql)
    garantiza como mucho una fila por (Usuario_ID, Torneo_ID).

    fn_validar_asignacion_torneo_admin_rol (06_triggers.sql) exige que
    Usuario_ID sea una cuenta Rol='TorneoAdmin' al momento de insertar/
    actualizar esta fila — pero NO revalida si esa cuenta cambia de rol
    después. Eso lo cubre UsuarioService.update(), que desactiva las filas
    Activo de este usuario cuando su Rol deja de ser 'TorneoAdmin'.
    """

    __tablename__ = "asignacion_torneo_admin"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    torneo_id: Mapped[int] = mapped_column(ForeignKey("torneo.id"))
    # Valores válidos: Activo, Inactivo (chk_asignacion_estado)
    estado: Mapped[str] = mapped_column(String(20), default="Activo")
