from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.errors import DomainRuleError, ForbiddenError, NotFoundError
from app.models.asignacion_torneo_admin import AsignacionTorneoAdmin
from app.models.usuario import Usuario
from app.repositories.asignacion_torneo_admin import AsignacionTorneoAdminRepository
from app.repositories.torneo import TorneoRepository
from app.repositories.usuario import UsuarioRepository


class AsignacionTorneoAdminService:
    """Licencia + asignación N:M de torneos (rbac-licencias-torneos-plan.md,
    §4.4). Los 3 endpoints de `usuarios.py` (§4.5) llaman acá — todos
    gateados a AdminGeneral río arriba vía `require_roles`."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.usuario_repo = UsuarioRepository(session)
        self.torneo_repo = TorneoRepository(session)
        self.asignacion_repo = AsignacionTorneoAdminRepository(session)

    async def set_licencia(self, usuario_id: int, activa: bool, actor: Usuario) -> Usuario:
        """Otorga/revoca la licencia. Bloquea la auto-revocación — clon
        exacto del guard de auto-lockout que ya existe en
        `UsuarioService.update()` (T6, roles-3-modulos-plan.md Fase 1):
        con potencialmente un solo AdminGeneral en la base, revocarse la
        propia licencia dejaría el sistema sin nadie que la reactive."""
        if usuario_id == actor.id and not activa:
            raise ForbiddenError("No podés revocar tu propia licencia.")
        usuario = await self.usuario_repo.get_or_404(usuario_id)
        # Mutación ORM directa (setattr + commit), no BaseRepository.update —
        # mismo nivel de simplicidad que BaseRepository.save_changes, pero
        # sin pasar por **datos genérico para un solo campo booleano.
        usuario.licencia_activa = activa
        await self.session.commit()
        await self.session.refresh(usuario)
        return usuario

    async def listar_torneos_asignados(self, usuario_id: int) -> list[int]:
        """GET /usuarios/{id}/torneos — precarga el modal (§5.3)."""
        await self.usuario_repo.get_or_404(usuario_id)
        return await self.asignacion_repo.listar_torneo_ids_activos(usuario_id)

    async def set_torneos_asignados(self, usuario_id: int, torneo_ids: list[int], actor: Usuario) -> list[int]:
        """Reemplaza el set completo de torneos asignados a `usuario_id`
        (§4.4) — matchea la UX de "modal con checkboxes, Guardar".

        Corrección post outside-voice (Eng review, hallazgo #1 — ALTA
        severidad): la mutación es fila por fila vía `session.add()`/
        `setattr()` ORM estándar con UN SOLO `commit()` al final — nunca
        un loop de `BaseRepository.update()`/`.create()` (cada uno
        commitea por su cuenta, así que un loop ahí serían N commits
        separados, no atómico). Este patrón clona
        `InscripcionTorneoService.copiar_plantilla_base_al_roster`
        (registro por lote), que ya resuelve el mismo problema en este
        repo. Mutación ORM (no `session.execute(insert/update(...))` de
        Core) es además la condición para que AUDITORIA capture esto
        gratis (§3.2 del plan)."""
        usuario = await self.usuario_repo.get_or_404(usuario_id)
        if usuario.rol != "TorneoAdmin":
            raise DomainRuleError(
                f"Solo se puede asignar torneos a cuentas con rol TorneoAdmin (esta cuenta es {usuario.rol})."
            )

        ids_pedidos = set(torneo_ids)
        if ids_pedidos:
            ids_validos = await self.torneo_repo.ids_existentes(list(ids_pedidos))
            ids_inexistentes = ids_pedidos - ids_validos
            if ids_inexistentes:
                raise NotFoundError("Torneo", ", ".join(str(i) for i in sorted(ids_inexistentes)))

        filas_existentes = await self.asignacion_repo.listar_todas_del_usuario(usuario_id)
        por_torneo = {fila.torneo_id: fila for fila in filas_existentes}

        for torneo_id in ids_pedidos:
            fila = por_torneo.get(torneo_id)
            if fila is None:
                self.session.add(AsignacionTorneoAdmin(usuario_id=usuario_id, torneo_id=torneo_id, estado="Activo"))
            elif fila.estado != "Activo":
                fila.estado = "Activo"

        for torneo_id, fila in por_torneo.items():
            if torneo_id not in ids_pedidos and fila.estado == "Activo":
                fila.estado = "Inactivo"

        await self.session.commit()
        return await self.asignacion_repo.listar_torneo_ids_activos(usuario_id)
