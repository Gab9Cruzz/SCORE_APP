from sqlalchemy import func, select, text

from app.models.torneo import Torneo
from app.models.torneo_grupo import TorneoGrupo
from app.repositories.base import BaseRepository


class TorneoGrupoRepository(BaseRepository[TorneoGrupo]):
    model = TorneoGrupo
    nombre_recurso = "Torneo Grupo"

    async def siguiente_numero_edicion(self, torneo_grupo_id: int) -> int:
        """MAX(numero_edicion) + 1 dentro del grupo, o 1 si todavía no tiene
        ninguna edición (no debería pasar en la práctica — un grupo nace
        siempre con su Edición 1 — pero un default seguro es más simple que
        asumir que la fila ya existe)."""
        stmt = select(func.max(Torneo.numero_edicion)).where(Torneo.torneo_grupo_id == torneo_grupo_id)
        result = await self.session.execute(stmt)
        maximo = result.scalar_one_or_none()
        return (maximo or 0) + 1

    async def lock_numero_edicion(self, torneo_grupo_id: int) -> None:
        """Dos admins creando "Edición 3" del mismo grupo a la vez (EC-21
        del plan) podrían ambos leer el mismo MAX() antes de que cualquiera
        haga INSERT — mismo problema de raíz que la exclusividad por
        torneo (ver JugadorEquipoRepository.lock_exclusividad_torneo), y se
        resuelve con el mismo mecanismo: pg_advisory_xact_lock serializa la
        carrera en vez de confiar en el UNIQUE para atajarla después de que
        ya se malgastó un INSERT. Forma de un solo argumento (en vez de
        (jugador_perfil_id, torneo_id) que usa el lock de arriba): distinto
        espacio de claves en Postgres, no colisiona con ese lock aunque el
        ID numérico coincida por casualidad."""
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(:torneo_grupo_id)"),
            {"torneo_grupo_id": torneo_grupo_id},
        )

    async def listar_con_ediciones(self, incluir_archivados: bool = False) -> list[TorneoGrupo]:
        """Todos los grupos — el llamador (TorneoGrupoService) arma la
        lista de ediciones de cada uno por separado vía Torneo.list, para
        no depender de que la relación ORM esté declarada (no lo está: los
        modelos de este proyecto no usan `relationship()`, solo FKs
        planas, mismo criterio que el resto de los modelos).

        3B-7 (docs/plans/cierre-backlog-todos-plan.md): sin
        `incluir_archivados`, un grupo Estado='Archivado' no entra —
        "oculta el grupo de los selectores" del plan."""
        stmt = select(TorneoGrupo).order_by(TorneoGrupo.nombre)
        if not incluir_archivados:
            stmt = stmt.where(TorneoGrupo.estado == "Activo")
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
