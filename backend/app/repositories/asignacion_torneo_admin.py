from sqlalchemy import select

from app.models.asignacion_torneo_admin import AsignacionTorneoAdmin
from app.repositories.base import BaseRepository


class AsignacionTorneoAdminRepository(BaseRepository[AsignacionTorneoAdmin]):
    model = AsignacionTorneoAdmin
    nombre_recurso = "Asignación"

    async def existe_activa(self, usuario_id: int, torneo_id: int) -> bool:
        """Usado por `require_torneo_access` (api/deps.py) en cada request
        de escritura de un TorneoAdmin — probe de una sola fila sobre
        `unique_asignacion_usuario_torneo` (02_constraints.sql), no un scan."""
        stmt = select(AsignacionTorneoAdmin.id).where(
            AsignacionTorneoAdmin.usuario_id == usuario_id,
            AsignacionTorneoAdmin.torneo_id == torneo_id,
            AsignacionTorneoAdmin.estado == "Activo",
        )
        result = await self.session.execute(stmt)
        return result.first() is not None

    async def listar_torneo_ids_activos(self, usuario_id: int) -> list[int]:
        """Usado por GET /usuarios/{id}/torneos (precargar el modal) y por
        GET /torneos?solo_mios=true (E1)."""
        stmt = select(AsignacionTorneoAdmin.torneo_id).where(
            AsignacionTorneoAdmin.usuario_id == usuario_id,
            AsignacionTorneoAdmin.estado == "Activo",
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def listar_todas_del_usuario(self, usuario_id: int) -> list[AsignacionTorneoAdmin]:
        """Trae TODAS las filas (Activo e Inactivo) del usuario — usado por
        `AsignacionTorneoAdminService.set_torneos_asignados` para calcular
        el diff activar/desactivar contra el set nuevo sin perder de vista
        las filas ya `Inactivo` que se podrían reactivar en vez de
        reinsertar (unique_asignacion_usuario_torneo no lo permitiría)."""
        stmt = select(AsignacionTorneoAdmin).where(AsignacionTorneoAdmin.usuario_id == usuario_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def desactivar_todas_del_usuario(self, usuario_id: int) -> None:
        """Usado por `UsuarioService.update()` cuando un TorneoAdmin se
        degrada a otro rol (rbac-licencias-torneos-plan.md, §3.2,
        hallazgo #3 de la voz externa Eng) — mutación ORM fila por fila
        (no un UPDATE de Core), para que AUDITORIA la capture gratis, igual
        que `set_torneos_asignados`."""
        for fila in await self.listar_todas_del_usuario(usuario_id):
            if fila.estado == "Activo":
                fila.estado = "Inactivo"
        await self.session.commit()
