from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.errors import DomainRuleError, PreconditionFailedError
from app.models.convocado_a_partido import ConvocadoAPartido
from app.models.evento_partido import EventoPartido
from app.models.jugador_perfil_disciplina import JugadorPerfilDisciplina
from app.models.usuario import Usuario
from app.repositories.convocado_a_partido import ConvocadoAPartidoRepository
from app.repositories.estadisticas import EstadisticasRepository
from app.repositories.hito_partido import HitoPartidoRepository
from app.repositories.modalidad import ModalidadRepository
from app.repositories.partido import PartidoRepository
from app.repositories.torneo import TorneoRepository
from app.schemas.convocado_a_partido import ConvocadoAgregarRequest, ConvocatoriaSetRequest
from app.services.permisos import verificar_arbitro_asignado


class ConvocadoAPartidoService:
    """Titular/suplente/convocados a un partido (3B-2,
    docs/plans/cierre-backlog-todos-plan.md) — dirección técnica del
    plan: tabla delgada, no-autoritativa, no reemplaza JugadorEquipo.

    Dos superficies con semántica distinta
    (gestionar-partido-alineaciones-plan.md, D3 revisada):

    - `reemplazar` (PUT): arma la alineación completa. Solo ANTES de que el
      partido arranque, con concurrencia optimista.
    - `agregar` (POST): suma un convocado como suplente. Es aditivo, así que
      también funciona con el partido en curso — es el camino de las llegadas
      tardías, y no toca el cronómetro ni el `titular` de nadie.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ConvocadoAPartidoRepository(session)
        self.partido_repo = PartidoRepository(session)
        self.estadisticas_repo = EstadisticasRepository(session)
        # C5 del plan: el gate se ancla al hito Inicio_Partido, no a
        # PARTIDOS.Estado — ver _ya_arranco.
        self.hito_repo = HitoPartidoRepository(session)
        # modo-vivo-sustituciones-cierre-plan.md, Área 1 (T2): tope
        # SUPERIOR de titulares — ver _maximo_titulares.
        self.torneo_repo = TorneoRepository(session)
        self.modalidad_repo = ModalidadRepository(session)

    async def listar(self, partido_id: int) -> list[ConvocadoAPartido]:
        await self.partido_repo.get_or_404(partido_id)
        return await self.repo.listar_por_partido(partido_id)

    async def _ya_arranco(self, partido_id: int) -> bool:
        """¿El partido ya arrancó? Se pregunta por el hito `Inicio_Partido`, NO
        por `PARTIDOS.Estado` (gestionar-partido-alineaciones-plan.md, C5).

        `PATCH /partidos/{id}` acepta `estado` y `PartidoService.update` no
        valida transiciones, así que un gate anclado al estado se saltearía con
        `PATCH {estado:"Programado"}` -> operación prohibida ->
        `PATCH {estado:"En curso"}`. El hito es append-only: ningún PATCH lo
        revierte."""
        return await self.hito_repo.existe_inicio_partido(partido_id)

    async def _perfiles_con_eventos(self, partido_id: int, perfiles: set[int]) -> set[int]:
        """Cuáles de esos perfiles ya tienen sucesos cargados en este partido.

        No hay columna en común entre las dos tablas (C4 del plan):
        `EVENTOS_PARTIDO.Jugador_ID` apunta a `JUGADORES`, mientras que
        `CONVOCADO_A_PARTIDO.Jugador_Perfil_ID` apunta a
        `JUGADOR_PERFIL_DISCIPLINA`. Hace falta el join por
        `jpd.jugador_id`.

        Cubre también `jugador_id_entra`: el suplente que ENTRÓ es exactamente
        el jugador que produce la feature de llegadas tardías, y sacarlo dejaría
        un cambio apuntando a alguien "no convocado".

        Los eventos `Anulado` no bloquean: si el suceso se dio de baja, el
        jugador puede salir de la convocatoria sin dejar nada colgado."""
        if not perfiles:
            return set()
        stmt = (
            select(JugadorPerfilDisciplina.id)
            .join(
                EventoPartido,
                (EventoPartido.jugador_id == JugadorPerfilDisciplina.jugador_id)
                | (EventoPartido.jugador_id_entra == JugadorPerfilDisciplina.jugador_id),
            )
            .where(
                EventoPartido.partidos_id == partido_id,
                EventoPartido.estado == "Registrado",
                JugadorPerfilDisciplina.id.in_(perfiles),
            )
            .distinct()
        )
        result = await self.session.execute(stmt)
        return set(result.scalars().all())

    async def _perfiles_por_equipo(self, partido) -> dict[int, set[int]]:
        """Perfiles de la plantilla vigente de CADA equipo (local/visitante)
        EN ESTE TORNEO, por separado — a diferencia de `_perfiles_validos`
        (que los mezcla en un solo set), esto es lo que necesita el tope de
        titulares (T2/T16): "¿cuántos titulares tiene ESTE equipo?" no se
        puede responder con un set unificado.

        El filtro por torneo importa (H2-eng): sin él, un equipo inscripto en
        dos torneos activos de la misma disciplina devuelve el mismo
        `jugador_perfil_id` dos veces, y se podría convocar a alguien del equipo
        **en otro torneo** — un titular fantasma que `_validar_titulares` no
        cuenta y al que `fn_validar_jugador_partido` le rechaza cualquier
        evento."""
        candidatos_local = await self.estadisticas_repo.plantilla_equipo(
            partido.equipos_id_local, partido.torneo_id
        )
        candidatos_visitante = await self.estadisticas_repo.plantilla_equipo(
            partido.equipos_id_visitante, partido.torneo_id
        )
        return {
            partido.equipos_id_local: {f["jugador_perfil_id"] for f in candidatos_local},
            partido.equipos_id_visitante: {f["jugador_perfil_id"] for f in candidatos_visitante},
        }

    async def _perfiles_validos(self, partido) -> set[int]:
        """Unión de `_perfiles_por_equipo` — "¿este perfil pertenece a
        alguno de los dos equipos?", sin importar a cuál."""
        por_equipo = await self._perfiles_por_equipo(partido)
        return set().union(*por_equipo.values())

    async def _maximo_titulares(self, torneo_id: int) -> int:
        """Tope SUPERIOR de titulares por equipo (modo-vivo-sustituciones-
        cierre-plan.md, Área 1, T2/T18) — espejo exacto de
        `HitoPartidoService._maximo_permitido`, pero resuelto desde acá
        (este service no comparte instancia con HitoPartidoService).
        `Torneo.maximo_titulares_permitido` en NULL = usar
        `Modalidad.tamano_equipo`."""
        torneo = await self.torneo_repo.get_or_404(torneo_id)
        modalidad = await self.modalidad_repo.get_or_404(torneo.modalidad_id)
        return torneo.maximo_titulares_permitido or modalidad.tamano_equipo

    async def _validar_tope_titulares(self, partido, titulares_nuevos: dict[int, int]) -> None:
        """`titulares_nuevos`: equipo_id -> cuántos titulares tendría ESE
        equipo tras la operación. Rechaza el primero que exceda el tope —
        mismo patrón de mensaje que `_motivo_faltan_titulares` en
        HitoPartidoService (dice el número real, no un 409 genérico)."""
        maximo = await self._maximo_titulares(partido.torneo_id)
        for equipo_id, n_titulares in titulares_nuevos.items():
            if n_titulares > maximo:
                raise DomainRuleError(
                    f"El equipo {equipo_id} tendría {n_titulares} titulares — el máximo permitido "
                    f"para este partido es {maximo}. Bajá alguno a suplente antes de guardar."
                )

    @staticmethod
    def _exigir_equipos_definidos(partido) -> None:
        if partido.equipos_id_local is None or partido.equipos_id_visitante is None:
            raise DomainRuleError(
                "Este partido todavía no tiene los dos equipos definidos — esperá a que termine "
                "el partido anterior del bracket."
            )

    @staticmethod
    def _exigir_partido_operable(partido) -> None:
        if partido.estado in ("Finalizado", "Cancelado"):
            raise DomainRuleError(
                f"Este partido está '{partido.estado}' — su convocatoria quedó cerrada."
            )

    async def reemplazar(
        self, partido_id: int, data: ConvocatoriaSetRequest, usuario_actual: Usuario
    ) -> list[ConvocadoAPartido]:
        """Reemplaza la alineación completa. Solo antes del arranque.

        Con el partido ya iniciado esto se rechaza entero: es la operación
        destructiva (puede quitar titulares, degradar, o vaciar la lista), y el
        camino habilitado en vivo es `agregar`, que es aditivo."""
        partido = await self.partido_repo.get_or_404(partido_id)
        # Mismo ownership-check que EventoPartidoService/HitoPartidoService
        # (D5, roles-3-modulos-plan.md) — un Árbitro solo arma la
        # convocatoria de SU partido asignado.
        verificar_arbitro_asignado(partido, usuario_actual)
        self._exigir_partido_operable(partido)
        self._exigir_equipos_definidos(partido)

        if await self._ya_arranco(partido_id):
            raise DomainRuleError(
                "El partido ya arrancó — no se puede reescribir la alineación. "
                "Para sumar un jugador que llegó tarde usá 'Sumar jugador', que lo agrega "
                "como suplente sin tocar el resto."
            )

        await self._verificar_version(partido_id, data.version)

        perfiles_por_equipo = await self._perfiles_por_equipo(partido)
        perfiles_validos = set().union(*perfiles_por_equipo.values())

        vistos: set[int] = set()
        for convocado in data.convocados:
            if convocado.jugador_perfil_id not in perfiles_validos:
                raise DomainRuleError(
                    f"El perfil {convocado.jugador_perfil_id} no pertenece a la plantilla vigente de "
                    "ninguno de los dos equipos de este partido."
                )
            if convocado.jugador_perfil_id in vistos:
                raise DomainRuleError("Un jugador no puede estar convocado dos veces en la misma lista.")
            vistos.add(convocado.jugador_perfil_id)

        # Área 1 (T2): tope SUPERIOR de titulares — reversión explícita de
        # la Decisión Audit #12 del plan anterior (diferida dos veces,
        # reabierta acá con evidencia concreta: Fútbol 7 aceptaba 8
        # titulares sin ningún aviso). Server-side siempre, aunque
        # `alineacion.ts` (cliente) ya lo rechace antes del POST — nunca se
        # confía solo en el cliente.
        titulares_nuevos = {
            equipo_id: sum(
                1 for c in data.convocados if c.titular and c.jugador_perfil_id in perfiles
            )
            for equipo_id, perfiles in perfiles_por_equipo.items()
        }
        await self._validar_tope_titulares(partido, titulares_nuevos)

        await self._verificar_no_quita_jugadores_con_eventos(partido_id, vistos)

        filas = [(c.jugador_perfil_id, c.titular) for c in data.convocados]
        return await self.repo.reemplazar_convocatoria(partido_id, filas)

    async def _verificar_version(self, partido_id: int, version: datetime | None) -> None:
        """Concurrencia optimista (EC-3): si la convocatoria cambió desde que el
        cliente la leyó, se rechaza con 412 y se le devuelve el estado vigente
        para que pueda mostrar el diff en vez de pisar el trabajo del otro.

        `version=None` significa "no me importa" y se acepta — mantiene
        compatible a cualquier cliente viejo que todavía no manda el campo."""
        if version is None:
            return
        actual = await self.repo.version_actual(partido_id)
        if actual is not None and actual != version:
            vigentes = await self.repo.listar_por_partido(partido_id)
            raise PreconditionFailedError(
                "La convocatoria cambió desde otro dispositivo mientras la editabas.",
                estado_actual=[
                    {"jugador_perfil_id": c.jugador_perfil_id, "titular": c.titular} for c in vigentes
                ],
            )

    async def _verificar_no_quita_jugadores_con_eventos(self, partido_id: int, perfiles_nuevos: set[int]) -> None:
        """Un jugador con goles o tarjetas cargados no puede desaparecer de la
        convocatoria (EC-1): dejaría estadísticas colgadas de alguien que,
        según la alineación, no jugó. La vista pública mostraría el marcador con
        una alineación en la que no está el goleador."""
        actuales = {c.jugador_perfil_id for c in await self.repo.listar_por_partido(partido_id)}
        a_quitar = actuales - perfiles_nuevos
        if not a_quitar:
            return
        con_eventos = await self._perfiles_con_eventos(partido_id, a_quitar)
        if con_eventos:
            raise DomainRuleError(
                "No se puede sacar de la convocatoria a un jugador que ya tiene sucesos cargados en "
                f"este partido (perfiles: {sorted(con_eventos)}). Anulá primero esos eventos."
            )

    async def agregar(
        self, partido_id: int, data: ConvocadoAgregarRequest, usuario_actual: Usuario
    ) -> ConvocadoAPartido:
        """Suma UN convocado sin tocar nada de lo ya cargado — el camino de las
        llegadas tardías (Requerimiento 3 del plan).

        Funciona con el partido en curso justamente porque es aditivo: no borra,
        no reordena y no cambia el `titular` de nadie. El que llega tarde entra
        como suplente y pasa a cancha por el evento `Cambio`, que es donde ese
        hecho ya tiene representación en el modelo.

        Un doble-tap del operador (que en una cancha es normal) responde con la
        fila que ya existía en vez de un error: la operación es idempotente."""
        partido = await self.partido_repo.get_or_404(partido_id)
        verificar_arbitro_asignado(partido, usuario_actual)
        self._exigir_partido_operable(partido)
        self._exigir_equipos_definidos(partido)

        perfiles_por_equipo = await self._perfiles_por_equipo(partido)
        equipo_del_jugador = next(
            (eq for eq, perfiles in perfiles_por_equipo.items() if data.jugador_perfil_id in perfiles), None
        )
        if equipo_del_jugador is None:
            raise DomainRuleError(
                f"El perfil {data.jugador_perfil_id} no pertenece a la plantilla vigente de "
                "ninguno de los dos equipos de este partido."
            )

        ya_arranco = await self._ya_arranco(partido_id)
        if ya_arranco and data.titular:
            # El requerimiento pide sumar al banco sin alterar la alineación
            # titular: con el partido en curso el flag `titular` es inmutable.
            raise DomainRuleError(
                "El partido ya arrancó — un jugador que llega tarde entra como suplente. "
                "Para ponerlo en cancha cargá un Cambio."
            )

        existentes = {c.jugador_perfil_id: c for c in await self.repo.listar_por_partido(partido_id)}
        if data.jugador_perfil_id in existentes:
            return existentes[data.jugador_perfil_id]

        if data.titular:
            # Área 1 (T2): mismo tope que `reemplazar`, para el caso (pre-
            # arranque) de sumar un convocado directo como titular vía POST
            # en vez de PUT.
            actuales = sum(
                1
                for c in existentes.values()
                if c.titular and c.jugador_perfil_id in perfiles_por_equipo[equipo_del_jugador]
            )
            await self._validar_tope_titulares(partido, {equipo_del_jugador: actuales + 1})

        try:
            return await self.repo.agregar_convocado(
                partido_id=partido_id,
                jugador_perfil_id=data.jugador_perfil_id,
                titular=data.titular,
                minuto_ingreso=data.minuto_ingreso if ya_arranco else None,
                registrado_por=usuario_actual.id,
            )
        except IntegrityError:
            # Carrera contra unique_convocado_partido: otro request lo agregó
            # entre el chequeo de arriba y el INSERT. Sigue siendo idempotente.
            await self.session.rollback()
            vigentes = {c.jugador_perfil_id: c for c in await self.repo.listar_por_partido(partido_id)}
            if data.jugador_perfil_id in vigentes:
                return vigentes[data.jugador_perfil_id]
            raise
