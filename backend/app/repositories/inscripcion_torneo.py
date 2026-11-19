from __future__ import annotations

from typing import Sequence

from sqlalchemy import Select, func, select

from app.core.bloqueos import Espacio, bloquear
from app.models.inscripcion_torneo import InscripcionTorneo
from app.models.torneo import Torneo
from app.repositories.base import BaseRepository


class InscripcionTorneoRepository(BaseRepository[InscripcionTorneo]):
    model = InscripcionTorneo
    nombre_recurso = "Inscripción"

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        torneo_id: int | None = None,
        equipo_id: int | None = None,
        torneo_ids_permitidos: Sequence[int] | None = None,
        solo_publicados: bool = False,
    ) -> list[InscripcionTorneo]:
        """Override de `BaseRepository.list` (P3, TODOS.md): el filtro por
        asignación necesita `.in_()`, que el genérico por igualdad de la
        base no sabe hacer — mismo motivo que `TorneoRepository.list`/
        `PartidoRepository.list` ya tienen el suyo propio."""
        stmt = self._consulta(torneo_id, equipo_id, torneo_ids_permitidos, solo_publicados)
        stmt = stmt.order_by(InscripcionTorneo.id).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def contar_filtrado(  # type: ignore[override]
        self,
        torneo_id: int | None = None,
        equipo_id: int | None = None,
        torneo_ids_permitidos: Sequence[int] | None = None,
        solo_publicados: bool = False,
    ) -> int:
        """Total sin paginar con los mismos filtros que `list` (TASK-011)."""
        return await self._contar(self._consulta(torneo_id, equipo_id, torneo_ids_permitidos, solo_publicados))

    @staticmethod
    def _consulta(
        torneo_id: int | None,
        equipo_id: int | None,
        torneo_ids_permitidos: Sequence[int] | None,
        solo_publicados: bool = False,
    ) -> Select:
        stmt = select(InscripcionTorneo)
        # TASK-014 (SEC-07): un anónimo no reconstruye un torneo no publicado.
        if solo_publicados:
            stmt = stmt.join(Torneo, Torneo.id == InscripcionTorneo.torneo_id).where(Torneo.publicado.is_(True))
        if torneo_id is not None:
            stmt = stmt.where(InscripcionTorneo.torneo_id == torneo_id)
        if equipo_id is not None:
            stmt = stmt.where(InscripcionTorneo.equipo_id == equipo_id)
        if torneo_ids_permitidos is not None:
            stmt = stmt.where(InscripcionTorneo.torneo_id.in_(torneo_ids_permitidos))
        return stmt

    async def lock_cupo_inscripcion(self, inscripcion_torneo_id: int) -> None:
        """EC-6 (cupo de la modalidad, Pareja/Individual tamano_equipo<=2):
        RegistroLoteService._validar_lote cuenta los activos de la
        inscripción y resta contra `modalidad.tamano_equipo` sin lock — bajo
        READ COMMITTED, dos /confirmar concurrentes contra la MISMA
        inscripción pueden ambos leer el mismo conteo antes de que
        cualquiera haga INSERT, y los dos "ven" cupo libre (mismo problema
        de raíz que la exclusividad por torneo, ver
        JugadorEquipoRepository.lock_exclusividad_torneo).

        pg_advisory_xact_lock, forma de un solo argumento (mismo criterio
        que TorneoGrupoRepository.lock_numero_edicion: un solo entero, no
        colisiona con el lock de exclusividad de arriba aunque el ID
        numérico coincida por casualidad — son espacios de claves
        distintos en Postgres). Se libera solo al terminar la transacción."""
        await bloquear(self.session, Espacio.CUPO_INSCRIPCION, inscripcion_torneo_id)

    async def contar_no_canceladas(self, torneo_id: int) -> int:
        """3B-10 (docs/plans/cierre-backlog-todos-plan.md): cuántas
        inscripciones ocupan cupo en este torneo AHORA — 'Cancelado' no
        cuenta (libera el cupo), 'Inscrito'/'Confirmado' sí."""
        stmt = (
            select(func.count())
            .select_from(InscripcionTorneo)
            .where(InscripcionTorneo.torneo_id == torneo_id, InscripcionTorneo.estado != "Cancelado")
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

