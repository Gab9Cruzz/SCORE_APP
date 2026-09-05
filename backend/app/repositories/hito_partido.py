from datetime import datetime

from sqlalchemy import or_, select

from app.models.hito_partido import HitoPartido
from app.models.partido import Partido
from app.repositories.base import BaseRepository


class HitoPartidoRepository(BaseRepository[HitoPartido]):
    model = HitoPartido
    nombre_recurso = "Hito de partido"

    async def listar_por_partido(self, partido_id: int) -> list[HitoPartido]:
        """Orden de inserción (ID ascendente) — coincide con el orden
        cronológico real porque Timestamp_Real es DEFAULT CURRENT_TIMESTAMP
        y los hitos se crean uno a la vez, nunca en lote. HitoPartidoService
        recorre esta lista para calcular el estado del cronómetro y qué
        acciones habilitar (Flujo 5 del plan)."""
        stmt = select(HitoPartido).where(HitoPartido.partido_id == partido_id).order_by(HitoPartido.id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def existe_inicio_desde(self, equipo_id: int, desde: datetime) -> bool:
        """Anular un traspaso (fixes-datos-traspasos-control-mesa-plan.md):
        ¿el equipo ya arrancó (Inicio_Partido) algún partido, local o
        visitante, desde `desde`? Decisión explícita del usuario: la
        reversión deja de ofrecerse en cuanto el CLUB destino ya compitió
        (participe o no puntualmente el jugador de este traspaso) — a
        partir de ahí corregir el roster es un traspaso nuevo en sentido
        inverso, no un "deshacer"."""
        stmt = (
            select(HitoPartido.id)
            .join(Partido, Partido.id == HitoPartido.partido_id)
            .where(
                HitoPartido.tipo_hito == "Inicio_Partido",
                HitoPartido.timestamp_real >= desde,
                or_(Partido.equipos_id_local == equipo_id, Partido.equipos_id_visitante == equipo_id),
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first() is not None
