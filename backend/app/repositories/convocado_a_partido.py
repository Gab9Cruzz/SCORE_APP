from datetime import datetime

from sqlalchemy import func, select

from app.models.convocado_a_partido import ConvocadoAPartido
from app.repositories.base import BaseRepository


class ConvocadoAPartidoRepository(BaseRepository[ConvocadoAPartido]):
    model = ConvocadoAPartido
    nombre_recurso = "Convocado"

    async def listar_por_partido(self, partido_id: int) -> list[ConvocadoAPartido]:
        stmt = select(ConvocadoAPartido).where(ConvocadoAPartido.partido_id == partido_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def version_actual(self, partido_id: int) -> datetime | None:
        """ETag de la convocatoria: `MAX(Fecha_Modificacion)` del partido
        (gestionar-partido-alineaciones-plan.md, H4-eng).

        NO se puede versionar por el set de IDs. Eso funcionaba por accidente
        mientras `reemplazar_convocatoria` hacía DELETE+INSERT y los IDs
        rotaban en cada guardado; desde que hace diff incremental, cambiar
        `titular` es un UPDATE que no toca ningún ID, así que el set queda
        idéntico y dos operadores intercambiando titulares se pisarían en
        silencio — justo el caso que la concurrencia optimista existe para
        prevenir.

        `None` = el partido no tiene convocatoria todavía."""
        stmt = select(func.max(ConvocadoAPartido.fecha_modificacion)).where(
            ConvocadoAPartido.partido_id == partido_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def reemplazar_convocatoria(
        self, partido_id: int, filas: list[tuple[int, bool]]
    ) -> list[ConvocadoAPartido]:
        """Diff incremental contra lo que ya está guardado. El service ya validó
        cada `jugador_perfil_id` contra la plantilla del torneo antes de llamar
        acá. `filas` es (jugador_perfil_id, titular).

        Antes esto era un `DELETE` masivo + `INSERT` de todo. Se cambió por dos
        razones concretas (gestionar-partido-alineaciones-plan.md, EC-2):

        1. `session.execute(delete(...))` no pasa por la unidad de trabajo del
           ORM, así que el listener de auditoría (`core/auditoria.py`, que
           engancha `before_flush`) NUNCA veía las bajas de convocatoria.
           Borrando por objeto vuelven a quedar auditadas.
        2. El DELETE+INSERT regeneraba `Fecha_Registro` de TODAS las filas en
           cada guardado, así que el dato de "a qué hora se sumó este jugador"
           —lo que justifica registrar llegadas tardías— se perdía al guardado
           siguiente.
        """
        actuales = {c.jugador_perfil_id: c for c in await self.listar_por_partido(partido_id)}
        deseados = dict(filas)

        for perfil_id, titular in deseados.items():
            existente = actuales.get(perfil_id)
            if existente is None:
                self.session.add(
                    ConvocadoAPartido(partido_id=partido_id, jugador_perfil_id=perfil_id, titular=titular)
                )
            elif existente.titular != titular:
                # Solo se toca si cambió: un UPDATE inútil movería el ETag y
                # haría fallar el guardado de otro operador sin motivo real.
                existente.titular = titular

        for perfil_id, obj in actuales.items():
            if perfil_id not in deseados:
                await self.session.delete(obj)

        await self.session.commit()
        return await self.listar_por_partido(partido_id)

    async def agregar_convocado(
        self,
        partido_id: int,
        jugador_perfil_id: int,
        titular: bool,
        minuto_ingreso: int | None,
        registrado_por: int | None,
    ) -> ConvocadoAPartido:
        """Alta aditiva de UN convocado — el camino de las llegadas tardías
        (gestionar-partido-alineaciones-plan.md, D3 revisada).

        No borra ni modifica ninguna fila existente, así que es conmutativa: dos
        operadores sumando jugadores distintos con el partido en curso no se
        pisan, y no hace falta chequeo de versión. Es lo que permite convocar a
        alguien sin tocar el cronómetro ni el resto de la alineación.

        `minuto_ingreso`/`registrado_por` son el valor probatorio que
        `Fecha_Registro` sola no da (H5-eng): esa es el inicio de la
        transacción y no dice quién cargó al jugador."""
        fila = ConvocadoAPartido(
            partido_id=partido_id,
            jugador_perfil_id=jugador_perfil_id,
            titular=titular,
            minuto_ingreso=minuto_ingreso,
            registrado_por=registrado_por,
        )
        self.session.add(fila)
        await self.session.commit()
        await self.session.refresh(fila)
        return fila
