from sqlalchemy import func, select, text

from app.models.inscripcion_torneo import InscripcionTorneo
from app.repositories.base import BaseRepository


class InscripcionTorneoRepository(BaseRepository[InscripcionTorneo]):
    model = InscripcionTorneo
    nombre_recurso = "Inscripción"

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
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(:inscripcion_torneo_id)"),
            {"inscripcion_torneo_id": inscripcion_torneo_id},
        )

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
