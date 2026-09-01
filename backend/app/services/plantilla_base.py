from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.errors import DomainRuleError
from app.models.jugador_perfil_disciplina import JugadorPerfilDisciplina
from app.repositories.equipo import EquipoRepository
from app.repositories.equipo_jugador_base import EquipoJugadorBaseRepository
from app.repositories.jugador import JugadorRepository
from app.repositories.jugador_perfil_disciplina import JugadorPerfilDisciplinaRepository
from app.schemas.equipo_jugador_base import ConflictoMultimilitancia, EquipoJugadorBaseCreate

_MENSAJE_MULTIMILITANCIA = (
    "Este jugador está inscrito en los equipos {lista}. Si este nuevo equipo "
    "ingresa a un torneo donde uno de esos equipos ya está participando, el "
    "jugador será desvinculado automáticamente de este equipo para ese torneo."
)


class PlantillaBaseService:
    """Plantilla Base de un equipo (gestion-avanzada-equipos-control-mesa-
    plan.md, Decisión D1-C): banco de candidatos independiente de
    cualquier torneo. Ver EquipoJugadorBase para por qué NO participa de
    ninguna regla de elegibilidad."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = EquipoJugadorBaseRepository(session)
        self.equipo_repo = EquipoRepository(session)
        self.jugador_repo = JugadorRepository(session)
        self.perfil_repo = JugadorPerfilDisciplinaRepository(session)

    async def listar(self, equipo_id: int) -> list[dict]:
        await self.equipo_repo.get_or_404(equipo_id)
        filas = await self.repo.listar_por_equipo(equipo_id)
        return await self.repo.con_datos_jugador(filas)

    async def verificar_multimilitancia(self, equipo_id: int, jugador_id: int) -> ConflictoMultimilitancia:
        """GET .../verificar?jugador_id= — Nivel 1 del Algoritmo de
        Multimilitancia: consulta de solo lectura, nunca bloquea (D1-C: no
        hay trigger de DB porque EQUIPO_JUGADOR_BASE no participa de
        ninguna regla de integridad)."""
        equipo = await self.equipo_repo.get_or_404(equipo_id)
        jugador = await self.jugador_repo.get_or_404(jugador_id)
        perfil = await self.perfil_repo.get_by_jugador_y_disciplina(jugador.id, equipo.disciplina_id)
        if perfil is None:
            return ConflictoMultimilitancia(conflicto=False)

        otros = await self.repo.verificar_multimilitancia(perfil.id, equipo_id)
        if not otros:
            return ConflictoMultimilitancia(conflicto=False)

        nombres = [nombre for _id, nombre in otros]
        return ConflictoMultimilitancia(
            conflicto=True,
            equipos=nombres,
            mensaje=_MENSAJE_MULTIMILITANCIA.format(lista=", ".join(nombres)),
        )

    async def agregar(self, equipo_id: int, data: EquipoJugadorBaseCreate) -> dict:
        """Agrega (o reactiva) un candidato. El llamador (POST) siempre
        procede — el chequeo de multimilitancia es responsabilidad de la
        UI, que consulta `verificar_multimilitancia` ANTES de confirmar
        (Flujo 2 del plan); acá solo se bloquea el duplicado real dentro
        de la MISMA plantilla base (EC-2), que es un error distinto."""
        equipo = await self.equipo_repo.get_or_404(equipo_id)
        jugador = await self.jugador_repo.get_or_404(data.jugador_id)

        perfil = await self.perfil_repo.get_by_jugador_y_disciplina(jugador.id, equipo.disciplina_id)
        if perfil is None:
            perfil = JugadorPerfilDisciplina(jugador_id=jugador.id, disciplina_id=equipo.disciplina_id)
            self.session.add(perfil)
            await self.session.flush()

        existente = await self.repo.get_por_equipo_y_perfil(equipo_id, perfil.id)
        if existente is not None:
            if existente.estado == "Activo":
                # EC-2: ya está en la plantilla de este equipo — mensaje
                # distinto al de multimilitancia (son dos errores distintos).
                raise DomainRuleError(f"{jugador.nombre} ya está en la plantilla base de este equipo.")
            # unique_equipo_jugador_base es incondicional (no parcial): un
            # candidato que se había quitado se REACTIVA, no se re-inserta.
            fila = await self.repo.save_changes(
                existente, estado="Activo", dorsal_sugerido=data.dorsal_sugerido
            )
        else:
            fila = await self.repo.create(
                equipo_id=equipo_id,
                jugador_perfil_id=perfil.id,
                dorsal_sugerido=data.dorsal_sugerido,
            )

        filas = await self.repo.con_datos_jugador([fila])
        return filas[0]

    async def quitar(self, equipo_id: int, item_id: int) -> dict:
        """Baja lógica (EC-3): no toca JugadorEquipo — son tablas
        independientes por diseño (D1)."""
        await self.equipo_repo.get_or_404(equipo_id)
        fila = await self.repo.get_or_404(item_id)
        if fila.equipo_id != equipo_id:
            raise DomainRuleError("Ese candidato no pertenece a este equipo.")
        actualizado = await self.repo.soft_delete(item_id)
        filas = await self.repo.con_datos_jugador([actualizado])
        return filas[0]
