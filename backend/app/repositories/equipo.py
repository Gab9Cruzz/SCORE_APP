from collections.abc import Sequence

from sqlalchemy import func, select

from app.models.equipo import Equipo
from app.models.inscripcion_torneo import InscripcionTorneo
from app.models.jugador_equipo import JugadorEquipo
from app.repositories.base import BaseRepository


class EquipoRepository(BaseRepository[Equipo]):
    model = Equipo
    nombre_recurso = "Equipo"

    async def plantilla_total_por_equipo(self, equipo_ids: Sequence[int]) -> dict[int, int]:
        """Cuántos jugadores distintos tiene cada equipo, para toda la
        lista de una (D-Eng-10: UN GROUP BY, no una consulta por fila —
        /torneo-grupos ya arrastraba un N+1 aceptado conscientemente y
        esta lista es más larga que aquella).

        "Plantilla del equipo" es un dato DERIVADO (Decisión #1 = A1): no
        existe un roster permanente, existen N rosters (uno por
        inscripción a un torneo). Se cuentan perfiles DISTINTOS entre
        todas las inscripciones del equipo — un jugador que estuvo en tres
        ediciones cuenta una vez, que es lo que el admin espera leer en
        una columna que dice "14 jug.".

        Solo membresías Activo: un jugador dado de baja o traspasado ya no
        es parte de la plantilla, y contarlo inflaría el número sin que
        nada en pantalla explique por qué.
        """
        if not equipo_ids:
            return {}
        stmt = (
            select(
                InscripcionTorneo.equipo_id,
                func.count(func.distinct(JugadorEquipo.jugador_perfil_id)),
            )
            .join(JugadorEquipo, JugadorEquipo.inscripcion_torneo_id == InscripcionTorneo.id)
            .where(
                InscripcionTorneo.equipo_id.in_(equipo_ids),
                JugadorEquipo.estado == "Activo",
            )
            .group_by(InscripcionTorneo.equipo_id)
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
