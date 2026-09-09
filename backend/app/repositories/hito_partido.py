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

    async def ultimo_hito(self, partido_id: int) -> HitoPartido | None:
        """El Hito más reciente (ID descendente = orden de inserción =
        cronológico real, ver listar_por_partido) de este partido — usado
        por HitoPartidoService.deshacer_fin_forzado (T17) para confirmar
        que lo último que pasó en el partido es EXACTAMENTE el cierre
        forzado que se quiere deshacer, no un Hito posterior."""
        stmt = (
            select(HitoPartido)
            .where(HitoPartido.partido_id == partido_id)
            .order_by(HitoPartido.id.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def existe_inicio_partido(self, partido_id: int) -> bool:
        """¿Este partido ya arrancó? (gestionar-partido-alineaciones-plan.md, C5)

        Es la señal que gobierna qué se puede editar de la convocatoria, y NO
        `PARTIDOS.Estado`: `PATCH /partidos/{id}` acepta `estado` sin validar
        transiciones, así que un cliente podría hacer
        `PATCH {estado:"Programado"}` -> operación prohibida ->
        `PATCH {estado:"En curso"}` y saltear el gate entero. Un HITOS_PARTIDO
        es append-only: ningún PATCH lo revierte."""
        stmt = (
            select(HitoPartido.id)
            .where(HitoPartido.partido_id == partido_id, HitoPartido.tipo_hito == "Inicio_Partido")
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first() is not None

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
