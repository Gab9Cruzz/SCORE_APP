"""Traspasos (equipos-jugadores-plan.md, Fase 2, Etapa C)."""
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.errors import DomainRuleError
from app.models.jugador_equipo import JugadorEquipo
from app.models.traspaso import Traspaso
from app.repositories.equipo import EquipoRepository
from app.repositories.hito_partido import HitoPartidoRepository
from app.repositories.inscripcion_torneo import InscripcionTorneoRepository
from app.repositories.jugador_equipo import JugadorEquipoRepository
from app.repositories.traspaso import TraspasoRepository
from app.schemas.traspaso import TraspasoCreate, TraspasoOut


class TraspasoService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = TraspasoRepository(session)
        self.jugador_equipo_repo = JugadorEquipoRepository(session)
        self.inscripcion_repo = InscripcionTorneoRepository(session)
        # fixes-datos-traspasos-control-mesa-plan.md: anular ahora revierte
        # de verdad y necesita saber si el club destino ya jugó.
        self.equipo_repo = EquipoRepository(session)
        self.hito_repo = HitoPartidoRepository(session)

    async def get(self, id_: int) -> TraspasoOut:
        return await self._a_salida(await self.repo.get_or_404(id_))

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        jugador_perfil_id: int | None = None,
        torneo_id: int | None = None,
    ) -> list[TraspasoOut]:
        # Mismo criterio que JugadorEquipoService.list: torneo_id necesita
        # un join, rama aparte del filtro genérico (D-Eng-3 del plan).
        if torneo_id is not None:
            traspasos = await self.repo.listar_por_torneo(torneo_id, skip=skip, limit=limit)
        else:
            traspasos = await self.repo.list(skip=skip, limit=limit, jugador_perfil_id=jugador_perfil_id)
        return [await self._a_salida(t) for t in traspasos]

    async def _puede_anularse(self, traspaso: Traspaso) -> bool:
        """fixes-datos-traspasos-control-mesa-plan.md: False si ya está
        Anulado, o si el club DESTINO ya arrancó un partido desde este
        traspaso (decisión explícita del usuario — no depende de si ESTE
        jugador puntualmente participó, solo de si el club ya compitió)."""
        if traspaso.estado == "Anulado":
            return False
        inscripcion_destino = await self.inscripcion_repo.get_or_404(traspaso.inscripcion_destino_id)
        ya_jugo = await self.hito_repo.existe_inicio_desde(inscripcion_destino.equipo_id, traspaso.fecha_traspaso)
        return not ya_jugo

    async def _a_salida(self, traspaso: Traspaso) -> TraspasoOut:
        salida = TraspasoOut.model_validate(traspaso)
        salida.puede_anularse = await self._puede_anularse(traspaso)
        return salida

    async def crear(self, data: TraspasoCreate, usuario_actual_id: int) -> TraspasoOut:
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
        # inscripcion_destino se resuelve PRIMERO (antes de tocar el
        # origen) — 3B-8 (docs/plans/cierre-backlog-todos-plan.md) necesita
        # su Torneo_ID para el chequeo de "misma edición" de abajo, y el
        # resto del método ya lo necesitaba para el lock.
        inscripcion_destino = await self.inscripcion_repo.get_or_404(data.inscripcion_destino_id)

        if data.inscripcion_origen_id is not None:
            # 3B-8: TRASPASOS siempre asumió que origen y destino son de la
            # MISMA edición — la UI (TraspasosDelTorneo.tsx) solo ofrece
            # pickers de esta edición, pero nada lo exigía ACÁ, así que un
            # curl directo con dos inscripciones de ediciones distintas
            # colaba un "traspaso" que en los hechos es otra cosa: mover un
            # jugador a otra edición es un ALTA NUEVA ahí (Registro por
            # lote / Agregar jugador en la edición destino), no un
            # traspaso — TRASPASOS no tiene ningún campo para modelar
            # "cambió de edición", solo "cambió de equipo dentro de una".
            inscripcion_origen = await self.inscripcion_repo.get_or_404(data.inscripcion_origen_id)
            if inscripcion_origen.torneo_id != inscripcion_destino.torneo_id:
                raise DomainRuleError(
                    "Origen y destino deben ser de la misma edición. Para mover un jugador a otra "
                    "edición, date de alta ahí directamente (Registro por lote o Agregar jugador) "
                    "en vez de un traspaso."
                )
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
        return await self._a_salida(traspaso)

    async def anular(self, id_: int) -> TraspasoOut:
        """Revierte el traspaso de verdad (fixes-datos-traspasos-control-
        mesa-plan.md, decisión explícita del usuario — reemplaza el
        criterio anterior de "anotación visual" de EC-20): el jugador
        vuelve al equipo donde estaba, como si el traspaso no hubiera
        pasado.

        - Da de baja la membresía que este traspaso abrió en el destino
          (estado='Inactivo', fecha_fin=hoy) — simétrico con una baja
          normal.
        - Si había origen, reactiva esa membresía (estado='Activo',
          fecha_fin=None) — el jugador sigue su tenencia ahí sin
          interrupción, como si el traspaso nunca hubiera pasado. Un
          fichaje desde agencia libre no tiene membresía que reactivar: el
          jugador simplemente vuelve a estar libre.
        - Deja de ofrecerse en cuanto el club DESTINO ya arrancó un
          partido desde este traspaso (`_puede_anularse`) — a partir de
          ahí, corregir el roster es un traspaso nuevo en sentido inverso,
          no un "deshacer" (el club ya compitió con ese jugador en su
          plantilla, aunque no haya generado un evento personal).
        """
        traspaso = await self.repo.get_or_404(id_)
        if traspaso.estado == "Anulado":
            raise DomainRuleError("Este traspaso ya está anulado.")

        inscripcion_destino = await self.inscripcion_repo.get_or_404(traspaso.inscripcion_destino_id)
        if await self.hito_repo.existe_inicio_desde(inscripcion_destino.equipo_id, traspaso.fecha_traspaso):
            equipo_destino = await self.equipo_repo.get_or_404(inscripcion_destino.equipo_id)
            raise DomainRuleError(
                f"No se puede anular: {equipo_destino.nombre} ya arrancó un partido desde este "
                "traspaso. Cargá un traspaso en sentido inverso para corregirlo."
            )

        # Mismo lock que crear() — serializa contra otro movimiento
        # concurrente del mismo perfil en el mismo torneo mientras se
        # reactiva el origen.
        await self.jugador_equipo_repo.lock_exclusividad_torneo(
            traspaso.jugador_perfil_id, inscripcion_destino.torneo_id
        )

        destino_activo = await self.jugador_equipo_repo.get_activo_en_inscripcion(
            traspaso.jugador_perfil_id, traspaso.inscripcion_destino_id
        )
        if destino_activo is None:
            raise DomainRuleError(
                "El jugador ya no está activo en el equipo destino de este traspaso — probablemente "
                "un movimiento posterior ya lo sacó de ahí. No se puede revertir automáticamente."
            )
        destino_activo.estado = "Inactivo"
        destino_activo.fecha_fin = date.today()
        # Cierra destino ANTES de reactivar origen (mismo motivo que
        # crear(): fn_validar_exclusividad_torneo no debe ver dos Activo
        # del mismo perfil en el mismo torneo a la vez).
        await self.session.flush()

        if traspaso.inscripcion_origen_id is not None:
            origen_cerrado = await self.jugador_equipo_repo.get_ultima_traspasada_en_inscripcion(
                traspaso.jugador_perfil_id, traspaso.inscripcion_origen_id
            )
            if origen_cerrado is None:
                raise DomainRuleError(
                    "No se encontró la membresía de origen para reactivar — no se puede revertir "
                    "automáticamente."
                )
            origen_cerrado.estado = "Activo"
            origen_cerrado.fecha_fin = None

        traspaso.estado = "Anulado"
        await self.session.commit()
        await self.session.refresh(traspaso)
        return await self._a_salida(traspaso)
