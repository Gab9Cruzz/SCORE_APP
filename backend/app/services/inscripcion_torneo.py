from datetime import date

from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.errors import DomainRuleError
from app.models.inscripcion_torneo import InscripcionTorneo
from app.models.jugador import Jugador
from app.models.jugador_equipo import JugadorEquipo
from app.models.jugador_perfil_disciplina import JugadorPerfilDisciplina
from app.models.torneo import Torneo
from app.repositories.disciplina import DisciplinaRepository
from app.repositories.equipo import EquipoRepository
from app.repositories.equipo_jugador_base import EquipoJugadorBaseRepository
from app.repositories.inscripcion_torneo import InscripcionTorneoRepository
from app.repositories.jugador import JugadorRepository
from app.repositories.jugador_equipo import JugadorEquipoRepository
from app.repositories.jugador_perfil_disciplina import JugadorPerfilDisciplinaRepository
from app.repositories.torneo import TorneoRepository
from app.schemas.inscripcion_torneo import (
    ConflictoPlantillaBase,
    InscripcionTorneoCreate,
    InscripcionTorneoOut,
    InscripcionTorneoUpdate,
    PlantillaBaseCopiaResumen,
)

_MENSAJE_CONFLICTO_TORNEO = (
    "El jugador {nombre} ya pertenece a otro equipo en este torneo. Para que "
    "pueda jugar en este club, andá a la pestaña 'Traspasos' y hacé la "
    "transferencia formal."
)


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
        self.plantilla_base_repo = EquipoJugadorBaseRepository(session)

    async def get(self, id_: int) -> InscripcionTorneo:
        return await self.repo.get_or_404(id_)

    async def list(
        self, skip: int = 0, limit: int = 100, torneo_id: int | None = None, equipo_id: int | None = None
    ) -> list[InscripcionTorneo]:
        return await self.repo.list(skip=skip, limit=limit, torneo_id=torneo_id, equipo_id=equipo_id)

    async def create(self, data: InscripcionTorneoCreate) -> InscripcionTorneoOut:
        if data.equipo_id is not None:
            return await self._crear_por_equipo(data)
        inscripcion = await self._crear_individual(data)
        return InscripcionTorneoOut.model_validate(inscripcion)

    async def _verificar_cupo(self, torneo: Torneo) -> None:
        """3B-10 (docs/plans/cierre-backlog-todos-plan.md): NULL en
        `Cupo_Maximo_Inscripciones` = sin límite, el comportamiento de
        siempre — la mayoría de los torneos no lo van a tocar. El lock (EC-6,
        mismo patrón) serializa la LECTURA del conteo contra cualquier otra
        alta concurrente sobre el MISMO torneo antes de confiar en él."""
        if torneo.cupo_maximo_inscripciones is None:
            return
        await self.torneo_repo.lock_cupo_inscripciones(torneo.id)
        actuales = await self.repo.contar_no_canceladas(torneo.id)
        if actuales >= torneo.cupo_maximo_inscripciones:
            raise DomainRuleError(
                f"Este torneo llegó a su cupo máximo de {torneo.cupo_maximo_inscripciones} inscripciones."
            )

    async def _crear_por_equipo(self, data: InscripcionTorneoCreate) -> InscripcionTorneoOut:
        """Pareja/Conjunto. unique_inscripcion (02_constraints.sql) sigue
        evitando el mismo equipo dos veces en el mismo torneo (el 409 lo
        arma exceptions/handlers.py); lo nuevo acá es el filtro estricto
        por disciplina de equipos-disciplina-navegacion-plan.md (pedido B,
        D-Eng-9, EC-33).

        gestion-avanzada-equipos-control-mesa-plan.md (Requerimiento 3):
        tras crear la inscripción, copia la Plantilla Base del equipo al
        roster real — SIN revertir la inscripción del equipo si algún
        candidato entra en conflicto (ver copiar_plantilla_base_al_roster).

        La validación de disciplina vive en el SERVICE y no en el router
        ni en un trigger: es el único punto por el que ya pasan los dos
        caminos de inscripción, ya tiene torneo_repo inyectado, y
        DomainRuleError ya se traduce a 400 en exceptions/handlers.py.
        """
        torneo = await self.torneo_repo.get_or_404(data.torneo_id)
        await self._verificar_cupo(torneo)
        equipo = await self.equipo_repo.get_or_404(data.equipo_id)

        if equipo.disciplina_id != torneo.disciplina_id:
            disciplina_equipo = await self.disciplina_repo.get(equipo.disciplina_id)
            disciplina_torneo = await self.disciplina_repo.get(torneo.disciplina_id)
            raise DomainRuleError(
                f"El equipo '{equipo.nombre}' pertenece a "
                f"{disciplina_equipo.nombre if disciplina_equipo else 'otra disciplina'}; "
                f"este torneo es de {disciplina_torneo.nombre if disciplina_torneo else 'otra disciplina'}."
            )

        inscripcion = await self.repo.create(torneo_id=data.torneo_id, equipo_id=data.equipo_id)
        resumen = await self.copiar_plantilla_base_al_roster(inscripcion, data.equipo_id)

        salida = InscripcionTorneoOut.model_validate(inscripcion)
        salida.plantilla_base = resumen
        return salida

    async def copiar_plantilla_base_al_roster(
        self, inscripcion: InscripcionTorneo, equipo_id: int
    ) -> PlantillaBaseCopiaResumen | None:
        """Requerimiento 3 / Algoritmo de Multimilitancia Nivel 2 del plan:
        cada candidato de la Plantilla Base se inserta en un SAVEPOINT
        propio, así un conflicto de exclusividad en UN candidato no
        aborta el resto (sin savepoints, la excepción del trigger
        abortaría TODA la transacción de Postgres). Un dorsal sugerido ya
        tomado en este roster (EC-6) NO excluye al candidato: se reintenta
        sin dorsal, el admin lo completa a mano después.

        Devuelve None si el equipo no tenía Plantilla Base cargada (0
        candidatos) — no None-vs-vacío ambiguo para el caller: se
        distingue "no había nada que copiar" (equipo sin plantilla base
        todavía) de "se copiaron 0 porque todos entraron en conflicto"
        devolviendo igual un resumen con insertados=0 en ese segundo caso.
        """
        candidatos = await self.plantilla_base_repo.listar_por_equipo(equipo_id)
        if not candidatos:
            return None

        candidatos_con_datos = {
            fila["jugador_perfil_id"]: fila
            for fila in await self.plantilla_base_repo.con_datos_jugador(candidatos)
        }

        insertados = 0
        sin_dorsal = 0
        conflictos: list[ConflictoPlantillaBase] = []

        for candidato in candidatos:
            datos = candidatos_con_datos[candidato.jugador_perfil_id]
            resultado = await self._copiar_un_candidato(
                candidato.jugador_perfil_id, inscripcion.id, candidato.dorsal_sugerido
            )
            if resultado == "conflicto":
                conflictos.append(
                    ConflictoPlantillaBase(
                        jugador_perfil_id=candidato.jugador_perfil_id,
                        jugador_nombre=datos["jugador_nombre"],
                        mensaje=_MENSAJE_CONFLICTO_TORNEO.format(nombre=datos["jugador_nombre"]),
                    )
                )
            else:
                insertados += 1
                if resultado == "sin_dorsal":
                    sin_dorsal += 1

        # Los candidatos insertados con éxito solo llegaron a FLUSH dentro
        # de su propio savepoint (que ya se liberó) — falta el COMMIT que
        # los persiste de verdad. Los que fallaron ya se revirtieron a su
        # savepoint individualmente, así que este commit no arrastra nada
        # de ellos.
        await self.session.commit()

        return PlantillaBaseCopiaResumen(insertados=insertados, sin_dorsal=sin_dorsal, conflictos=conflictos)

    async def _copiar_un_candidato(
        self, jugador_perfil_id: int, inscripcion_torneo_id: int, dorsal_sugerido: int | None
    ) -> str:
        """Intenta insertar con el dorsal sugerido dentro de un SAVEPOINT.
        Devuelve 'insertado' | 'sin_dorsal' | 'conflicto'.

        Orden de fallo posible: el trigger de exclusividad
        (fn_validar_exclusividad_torneo, BEFORE INSERT) corre antes que la
        base llegue a chequear el índice único de dorsal — así que un
        conflicto de exclusividad se detecta ANTES que uno de dorsal, y si
        el trigger no dispara pero el dorsal sí choca, ahí recién se
        reintenta sin dorsal."""
        try:
            async with self.session.begin_nested():
                self.session.add(
                    JugadorEquipo(
                        jugador_perfil_id=jugador_perfil_id,
                        inscripcion_torneo_id=inscripcion_torneo_id,
                        dorsal=dorsal_sugerido,
                        fecha_inicio=date.today(),
                    )
                )
                await self.session.flush()
        except DBAPIError as exc:
            mensaje = str(exc.orig) if exc.orig else str(exc)
            if "jugador_ya_activo_en_este_torneo" in mensaje:
                return "conflicto"
            if not isinstance(exc, IntegrityError) or dorsal_sugerido is None:
                # No es el caso de dorsal duplicado esperado (EC-6) — no
                # hay nada más que reintentar, se cuenta como conflicto en
                # vez de tumbar toda la inscripción del equipo.
                return "conflicto"
            # Dorsal ya tomado en este roster (uq_dorsal_por_roster_vigente)
            # — el jugador SÍ pertenece al roster, solo falta el número.
            try:
                async with self.session.begin_nested():
                    self.session.add(
                        JugadorEquipo(
                            jugador_perfil_id=jugador_perfil_id,
                            inscripcion_torneo_id=inscripcion_torneo_id,
                            dorsal=None,
                            fecha_inicio=date.today(),
                        )
                    )
                    await self.session.flush()
            except DBAPIError:
                return "conflicto"
            return "sin_dorsal"
        return "insertado"

    async def _crear_individual(self, data: InscripcionTorneoCreate) -> InscripcionTorneo:
        """Individual (Decisión B1, D-Eng-6): resuelve-o-crea Jugador +
        JugadorPerfilDisciplina — mismo camino que RegistroLoteService
        (EC-2/EC-3/EC-4/EC-9), sin duplicar esa lógica — y ancla la
        inscripción directo a jugador_perfil_id, sin ninguna fila en
        EQUIPOS. También crea JUGADOR_EQUIPO (Dorsal=NULL) para que
        fn_validar_exclusividad_torneo siga aplicando sin reescribirse."""
        torneo = await self.torneo_repo.get_or_404(data.torneo_id)
        await self._verificar_cupo(torneo)
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
