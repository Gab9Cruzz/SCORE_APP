from collections.abc import Sequence

from sqlalchemy import func, select

from app.models.equipo import Equipo
from app.models.equipo_jugador_base import EquipoJugadorBase
from app.models.inscripcion_torneo import InscripcionTorneo
from app.repositories.base import BaseRepository


class EquipoRepository(BaseRepository[Equipo]):
    model = Equipo
    nombre_recurso = "Equipo"

    async def plantilla_total_por_equipo(self, equipo_ids: Sequence[int]) -> dict[int, int]:
        """Cuántos candidatos tiene la Plantilla Base de cada equipo, para
        toda la lista de una (D-Eng-10: UN GROUP BY, no una consulta por
        fila).

        gestion-avanzada-equipos-control-mesa-plan.md (Flujo 1) cambia la
        FUENTE de esta columna: antes contaba JugadorEquipo (roster
        torneo-scoped, Decisión #1 = A1 del plan anterior — "no existe
        roster permanente, existen N rosters"); ahora cuenta
        EQUIPO_JUGADOR_BASE activa, que es la que responde "¿este equipo
        tiene jugadores cargados?" incluso ANTES de que exista ningún
        torneo — la pregunta que esta columna necesita responder desde que
        la Plantilla Base existe. Ya no depende de InscripcionTorneo.
        """
        if not equipo_ids:
            return {}
        stmt = (
            select(EquipoJugadorBase.equipo_id, func.count())
            .where(EquipoJugadorBase.equipo_id.in_(equipo_ids), EquipoJugadorBase.estado == "Activo")
            .group_by(EquipoJugadorBase.equipo_id)
        )
        result = await self.session.execute(stmt)
        return {equipo_id: total for equipo_id, total in result.all()}

    async def tiene_inscripciones(self, equipo_id: int) -> bool:
        """EC-38: si el equipo ya está inscrito en algún torneo, cambiarle
        la disciplina dejaría inscripciones que violan la regla que este
        plan introduce. Cuenta TODAS las inscripciones, incluidas las
        Canceladas: una inscripción cancelada sigue siendo historia de ese
        equipo en esa disciplina."""
        stmt = select(func.count()).select_from(InscripcionTorneo).where(
            InscripcionTorneo.equipo_id == equipo_id
        )
        result = await self.session.execute(stmt)
        return (result.scalar_one() or 0) > 0
