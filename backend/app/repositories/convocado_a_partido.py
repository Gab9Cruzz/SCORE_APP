from sqlalchemy import delete, select

from app.models.convocado_a_partido import ConvocadoAPartido
from app.repositories.base import BaseRepository


class ConvocadoAPartidoRepository(BaseRepository[ConvocadoAPartido]):
    model = ConvocadoAPartido
    nombre_recurso = "Convocado"

    async def listar_por_partido(self, partido_id: int) -> list[ConvocadoAPartido]:
        stmt = select(ConvocadoAPartido).where(ConvocadoAPartido.partido_id == partido_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def reemplazar_convocatoria(
        self, partido_id: int, filas: list[tuple[int, bool]]
    ) -> list[ConvocadoAPartido]:
        """3B-2 (docs/plans/cierre-backlog-todos-plan.md): DELETE + INSERT
        de toda la convocatoria del partido en una sola transacción — el
        service ya validó cada `jugador_perfil_id` contra la plantilla de
        alguno de los dos equipos antes de llamar acá. `filas` es
        (jugador_perfil_id, titular)."""
        await self.session.execute(delete(ConvocadoAPartido).where(ConvocadoAPartido.partido_id == partido_id))
        nuevas = [
            ConvocadoAPartido(partido_id=partido_id, jugador_perfil_id=jugador_perfil_id, titular=titular)
            for jugador_perfil_id, titular in filas
        ]
        self.session.add_all(nuevas)
        await self.session.commit()
        for fila in nuevas:
            await self.session.refresh(fila)
        return nuevas
