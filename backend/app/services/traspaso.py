"""Traspasos (equipos-jugadores-plan.md, Fase 2, Etapa C)."""
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.errors import DomainRuleError
from app.models.jugador_equipo import JugadorEquipo
from app.models.traspaso import Traspaso
from app.repositories.inscripcion_torneo import InscripcionTorneoRepository
from app.repositories.jugador_equipo import JugadorEquipoRepository
from app.repositories.traspaso import TraspasoRepository
from app.schemas.traspaso import TraspasoCreate


class TraspasoService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = TraspasoRepository(session)
        self.jugador_equipo_repo = JugadorEquipoRepository(session)
        self.inscripcion_repo = InscripcionTorneoRepository(session)

    async def get(self, id_: int) -> Traspaso:
        return await self.repo.get_or_404(id_)

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        jugador_perfil_id: int | None = None,
        torneo_id: int | None = None,
    ) -> list[Traspaso]:
        # Mismo criterio que JugadorEquipoService.list: torneo_id necesita
        # un join, rama aparte del filtro genérico (D-Eng-3 del plan).
        if torneo_id is not None:
            return await self.repo.listar_por_torneo(torneo_id, skip=skip, limit=limit)
        return await self.repo.list(skip=skip, limit=limit, jugador_perfil_id=jugador_perfil_id)

    async def crear(self, data: TraspasoCreate, usuario_actual_id: int) -> Traspaso:
        """Cierra el origen (si hay), abre el destino y registra el
        traspaso — las tres escrituras van en un solo `commit()`, no tres
        llamadas separadas a `BaseRepository.create()`: si el alta del
        destino fallara después de haber cerrado el origen en sesiones
        distintas, quedaría un jugador sin equipo en ningún lado sin que
        nada lo revierta.

        El orden importa por otra razón: si origen y destino son del MISMO
        torneo, fn_validar_exclusividad_torneo (06_triggers.sql) evaluaría
        el INSERT del destino contra el origen si ese todavía figurara
        Activo — SQLAlchemy manda los UPDATE (cerrar origen) antes que los
        INSERT nuevos dentro del mismo flush, así que cerrar primero y
        agregar después alcanza.
        """
        if data.inscripcion_origen_id is not None:
            origen = await self.jugador_equipo_repo.get_activo_en_inscripcion(
                data.jugador_perfil_id, data.inscripcion_origen_id
            )
            if origen is None:
                raise DomainRuleError(
                    "El jugador no tiene una membresía activa en el equipo de origen indicado."
                )
            origen.estado = "Traspasado"
            origen.fecha_fin = date.today()
        else:
            # Fichaje desde agencia libre: el perfil no debe tener NINGUNA
            # membresía activa ahora mismo, o esto no es una agencia libre
            # real — corresponde un traspaso con origen.
            activa_actual = await self.jugador_equipo_repo.get_activa_de_perfil(data.jugador_perfil_id)
            if activa_actual is not None:
                raise DomainRuleError(
                    "El jugador ya tiene una membresía activa — usa un traspaso con equipo de origen, "
                    "no un fichaje desde libre."
                )

        # Serializa contra otra transacción concurrente (otro traspaso, o un
        # registro por lote) activando el mismo perfil en el mismo torneo
        # destino — fn_validar_exclusividad_torneo (06_triggers.sql) no
        # alcanza sola bajo concurrencia real, ver
        # JugadorEquipoRepository.lock_exclusividad_torneo.
        inscripcion_destino = await self.inscripcion_repo.get_or_404(data.inscripcion_destino_id)
        await self.jugador_equipo_repo.lock_exclusividad_torneo(data.jugador_perfil_id, inscripcion_destino.torneo_id)

        nueva_membresia = JugadorEquipo(
            jugador_perfil_id=data.jugador_perfil_id,
            inscripcion_torneo_id=data.inscripcion_destino_id,
            dorsal=data.dorsal_nuevo,
            fecha_inicio=date.today(),
            estado="Activo",
        )
        self.session.add(nueva_membresia)

        traspaso = Traspaso(
            jugador_perfil_id=data.jugador_perfil_id,
            inscripcion_origen_id=data.inscripcion_origen_id,
            inscripcion_destino_id=data.inscripcion_destino_id,
            dorsal_nuevo=data.dorsal_nuevo,
            realizado_por=usuario_actual_id,
            motivo=data.motivo,
            estado="Completado",
        )
        self.session.add(traspaso)

        await self.session.commit()
        await self.session.refresh(traspaso)
        return traspaso

    async def anular(self, id_: int) -> Traspaso:
        """EC-20: anotación visual, nunca toca JUGADOR_EQUIPO. Corregir el
        roster de verdad es un traspaso nuevo en sentido inverso — una
        llamada normal a `crear`."""
        traspaso = await self.repo.get_or_404(id_)
        if traspaso.estado == "Anulado":
            raise DomainRuleError("Este traspaso ya está anulado.")
        return await self.repo.save_changes(traspaso, estado="Anulado")
