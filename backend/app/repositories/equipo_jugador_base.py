from sqlalchemy import select

from app.models.equipo_jugador_base import EquipoJugadorBase
from app.models.jugador import Jugador
from app.models.jugador_perfil_disciplina import JugadorPerfilDisciplina
from app.repositories.base import BaseRepository


class EquipoJugadorBaseRepository(BaseRepository[EquipoJugadorBase]):
    model = EquipoJugadorBase
    nombre_recurso = "Candidato de plantilla base"

    async def listar_por_equipo(self, equipo_id: int, estado: str = "Activo") -> list[EquipoJugadorBase]:
        stmt = (
            select(EquipoJugadorBase)
            .where(EquipoJugadorBase.equipo_id == equipo_id, EquipoJugadorBase.estado == estado)
            .order_by(EquipoJugadorBase.id)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_por_equipo_y_perfil(self, equipo_id: int, jugador_perfil_id: int) -> EquipoJugadorBase | None:
        """unique_equipo_jugador_base (02_constraints.sql) es INCONDICIONAL
        (no parcial por Estado) — a diferencia de JugadorEquipo, acá no se
        puede "volver a insertar" tras un soft-delete: hay que reactivar la
        misma fila (EquipoJugadorBaseService lo hace) o el segundo INSERT
        choca contra el UNIQUE aunque la primera fila esté Inactivo."""
        stmt = select(EquipoJugadorBase).where(
            EquipoJugadorBase.equipo_id == equipo_id,
            EquipoJugadorBase.jugador_perfil_id == jugador_perfil_id,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def con_datos_jugador(self, filas: list[EquipoJugadorBase]) -> list[dict]:
        """Denormaliza jugador_id/nombre/cedula para EquipoJugadorBaseOut —
        la tabla de la UI ("Cédula | Nombre | Dorsal sugerido | Quitar")
        los necesita directo, un solo query para toda la lista (mismo
        criterio D-Eng-10 que EquipoRepository.plantilla_total_por_equipo)."""
        if not filas:
            return []
        perfil_ids = [f.jugador_perfil_id for f in filas]
        stmt = (
            select(JugadorPerfilDisciplina.id, Jugador.id, Jugador.nombre, Jugador.cedula)
            .join(Jugador, Jugador.id == JugadorPerfilDisciplina.jugador_id)
            .where(JugadorPerfilDisciplina.id.in_(perfil_ids))
        )
        result = await self.session.execute(stmt)
        datos = {perfil_id: (jugador_id, nombre, cedula) for perfil_id, jugador_id, nombre, cedula in result.all()}

        salida = []
        for f in filas:
            jugador_id, nombre, cedula = datos[f.jugador_perfil_id]
            salida.append(
                {
                    "id": f.id,
                    "equipo_id": f.equipo_id,
                    "jugador_perfil_id": f.jugador_perfil_id,
                    "jugador_id": jugador_id,
                    "jugador_nombre": nombre,
                    "jugador_cedula": cedula,
                    "dorsal_sugerido": f.dorsal_sugerido,
                    "estado": f.estado,
                    "fecha_registro": f.fecha_registro,
                    "fecha_modificacion": f.fecha_modificacion,
                }
            )
        return salida

    async def verificar_multimilitancia(
        self, jugador_perfil_id: int, equipo_id_actual: int
    ) -> list[tuple[int, str]]:
        """Nivel 1 del Algoritmo de Multimilitancia — global, no
        bloqueante. Otros equipos (activos) que ya tienen a este mismo
        perfil de disciplina en su Plantilla Base."""
        from app.models.equipo import Equipo

        stmt = (
            select(Equipo.id, Equipo.nombre)
            .join(EquipoJugadorBase, EquipoJugadorBase.equipo_id == Equipo.id)
            .where(
                EquipoJugadorBase.jugador_perfil_id == jugador_perfil_id,
                EquipoJugadorBase.estado == "Activo",
                EquipoJugadorBase.equipo_id != equipo_id_actual,
            )
            .distinct()
        )
        result = await self.session.execute(stmt)
        return list(result.all())

    async def plantilla_total_por_equipo(self, equipo_ids: list[int]) -> dict[int, int]:
        """Cuántos candidatos activos tiene la Plantilla Base de cada
        equipo — fuente de la columna "Plantilla" del listado global desde
        este plan (antes contaba JugadorEquipo, torneo-scoped; ver Flujo 1
        del plan: "responde la pregunta que esa columna necesita responder
        ahora", que es "¿este equipo tiene jugadores cargados?" incluso
        antes de que exista ningún torneo)."""
        from sqlalchemy import func

        if not equipo_ids:
            return {}
        stmt = (
            select(EquipoJugadorBase.equipo_id, func.count())
            .where(EquipoJugadorBase.equipo_id.in_(equipo_ids), EquipoJugadorBase.estado == "Activo")
            .group_by(EquipoJugadorBase.equipo_id)
        )
        result = await self.session.execute(stmt)
        return {equipo_id: total for equipo_id, total in result.all()}
