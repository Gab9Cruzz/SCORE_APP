from sqlalchemy import select

from app.models.inscripcion_torneo import InscripcionTorneo
from app.models.traspaso import Traspaso
from app.repositories.base import BaseRepository


class TraspasoRepository(BaseRepository[Traspaso]):
    model = Traspaso
    nombre_recurso = "Traspaso"

    async def listar_por_torneo(self, torneo_id: int, skip: int = 0, limit: int = 100) -> list[Traspaso]:
        """Torneo_ID no vive directo en TRASPASOS — se filtra por el torneo
        del EQUIPO DESTINO (el traspaso "pertenece" al torneo al que el
        jugador se está incorporando; origen y destino son normalmente el
        mismo torneo, ver torneos-admin-plan.md, "Fuera de este módulo").
        Usado por el dashboard scoped de un torneo (D-Eng-3)."""
        stmt = (
            select(Traspaso)
            .join(InscripcionTorneo, InscripcionTorneo.id == Traspaso.inscripcion_destino_id)
            .where(InscripcionTorneo.torneo_id == torneo_id)
            .order_by(Traspaso.id)
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
