from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.errors import DomainRuleError
from app.models.inscripcion_torneo import InscripcionTorneo
from app.models.jugador import Jugador
from app.models.jugador_equipo import JugadorEquipo
from app.models.jugador_perfil_disciplina import JugadorPerfilDisciplina
from app.repositories.disciplina import DisciplinaRepository
from app.repositories.equipo import EquipoRepository
from app.repositories.inscripcion_torneo import InscripcionTorneoRepository
from app.repositories.jugador import JugadorRepository
from app.repositories.jugador_equipo import JugadorEquipoRepository
from app.repositories.jugador_perfil_disciplina import JugadorPerfilDisciplinaRepository
from app.repositories.torneo import TorneoRepository
from app.schemas.inscripcion_torneo import InscripcionTorneoCreate, InscripcionTorneoUpdate


class InscripcionTorneoService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = InscripcionTorneoRepository(session)
        self.torneo_repo = TorneoRepository(session)
        self.jugador_repo = JugadorRepository(session)
        self.perfil_repo = JugadorPerfilDisciplinaRepository(session)
        self.jugador_equipo_repo = JugadorEquipoRepository(session)
        self.equipo_repo = EquipoRepository(session)
        self.disciplina_repo = DisciplinaRepository(session)

    async def get(self, id_: int) -> InscripcionTorneo:
        return await self.repo.get_or_404(id_)

    async def list(
        self, skip: int = 0, limit: int = 100, torneo_id: int | None = None, equipo_id: int | None = None
    ) -> list[InscripcionTorneo]:
        return await self.repo.list(skip=skip, limit=limit, torneo_id=torneo_id, equipo_id=equipo_id)

    async def create(self, data: InscripcionTorneoCreate) -> InscripcionTorneo:
        if data.equipo_id is not None:
            return await self._crear_por_equipo(data)
        return await self._crear_individual(data)

    async def _crear_por_equipo(self, data: InscripcionTorneoCreate) -> InscripcionTorneo:
        """Pareja/Conjunto. unique_inscripcion (02_constraints.sql) sigue
        evitando el mismo equipo dos veces en el mismo torneo (el 409 lo
        arma exceptions/handlers.py); lo nuevo acá es el filtro estricto
        por disciplina de equipos-disciplina-navegacion-plan.md (pedido B,
        D-Eng-9, EC-33).

        La validación vive en el SERVICE y no en el router ni en un
        trigger: es el único punto por el que ya pasan los dos caminos de
        inscripción, ya tiene torneo_repo inyectado, y DomainRuleError ya
        se traduce a 400 en exceptions/handlers.py. Un trigger daría un
        mensaje crudo de Postgres; el router dejaría fuera a cualquier
        llamador interno futuro.

        Solo se compara la DISCIPLINA, no la modalidad (EC-44): un equipo
        de Fútbol 11 inscribiéndose a un torneo de Fútbol 5 es legítimo, y
        el pedido dice "exactamente la misma Disciplina".
        """
        # D-Eng-17: hasta acá este camino no validaba ni que el torneo
        # existiera — se creaba la inscripción y reventaba después contra
        # la FK, con un 409 que no explicaba nada. El get_or_404 hace
        # falta igual para leer torneo.disciplina_id, así que el gap se
        # cierra solo.
        torneo = await self.torneo_repo.get_or_404(data.torneo_id)
        equipo = await self.equipo_repo.get_or_404(data.equipo_id)

        if equipo.disciplina_id != torneo.disciplina_id:
            disciplina_equipo = await self.disciplina_repo.get(equipo.disciplina_id)
            disciplina_torneo = await self.disciplina_repo.get(torneo.disciplina_id)
            raise DomainRuleError(
                f"El equipo '{equipo.nombre}' pertenece a "
                f"{disciplina_equipo.nombre if disciplina_equipo else 'otra disciplina'}; "
                f"este torneo es de {disciplina_torneo.nombre if disciplina_torneo else 'otra disciplina'}."
            )

        return await self.repo.create(torneo_id=data.torneo_id, equipo_id=data.equipo_id)

    async def _crear_individual(self, data: InscripcionTorneoCreate) -> InscripcionTorneo:
        """Individual (Decisión B1, D-Eng-6): resuelve-o-crea Jugador +
        JugadorPerfilDisciplina — mismo camino que RegistroLoteService
        (EC-2/EC-3/EC-4/EC-9), sin duplicar esa lógica — y ancla la
        inscripción directo a jugador_perfil_id, sin ninguna fila en
        EQUIPOS. También crea JUGADOR_EQUIPO (Dorsal=NULL) para que
        fn_validar_exclusividad_torneo siga aplicando sin reescribirse."""
        torneo = await self.torneo_repo.get_or_404(data.torneo_id)
        cedula = data.jugador_cedula.strip()
        nombre = data.jugador_nombre.strip()
        correo = data.jugador_correo_electronico.strip()

        jugador = await self.jugador_repo.get_by_cedula(cedula)
        # EC-2 (mismo criterio que RegistroLoteService): cédula ya
        # registrada con otro nombre — no se sobreescribe silenciosamente.
        if jugador is not None and jugador.nombre.strip().lower() != nombre.lower():
            raise DomainRuleError(
                f"El nombre no coincide con el registrado para esta cédula (registrado: {jugador.nombre})."
            )

        if jugador is None:
            jugador = Jugador(nombre=nombre, cedula=cedula, correo_electronico=correo)
            self.session.add(jugador)
            await self.session.flush()  # asigna jugador.id sin comprometer la transacción

        perfil = await self.perfil_repo.get_by_jugador_y_disciplina(jugador.id, torneo.disciplina_id)
        # EC-9: independiente de tener o no membresía activa.
        if perfil is not None and perfil.suspendido:
            raise DomainRuleError("Jugador suspendido en esta disciplina.")

        if perfil is None:
            perfil = JugadorPerfilDisciplina(jugador_id=jugador.id, disciplina_id=torneo.disciplina_id)
            self.session.add(perfil)
            await self.session.flush()

        inscripcion = InscripcionTorneo(torneo_id=data.torneo_id, jugador_perfil_id=perfil.id)
        self.session.add(inscripcion)
        await self.session.flush()  # asigna inscripcion.id sin comprometer la transacción

        # Serializa contra otra transacción concurrente activando el mismo
        # perfil en el mismo torneo — mismo mecanismo que
        # RegistroLoteService.confirmar, fn_validar_exclusividad_torneo por
        # sí sola no alcanza bajo READ COMMITTED (ver docstring del lock).
        await self.jugador_equipo_repo.lock_exclusividad_torneo(perfil.id, torneo.id)

        vinculo = JugadorEquipo(
            jugador_perfil_id=perfil.id,
            inscripcion_torneo_id=inscripcion.id,
            fecha_inicio=date.today(),
        )
        self.session.add(vinculo)
        # EC-27 (exclusividad): si el trigger rechaza este INSERT, la
        # excepción se propaga y app/db/session.py hace rollback de todo —
        # el Jugador/Perfil/Inscripcion recién flusheados en esta misma
        # transacción no quedan huérfanos (mismo criterio de atomicidad que
        # RegistroLoteService.confirmar).
        await self.session.commit()
        await self.session.refresh(inscripcion)
        return inscripcion

    async def update(self, id_: int, data: InscripcionTorneoUpdate) -> InscripcionTorneo:
        return await self.repo.update(id_, **data.model_dump(exclude_unset=True))
