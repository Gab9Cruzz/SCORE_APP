from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.errors import DomainRuleError
from app.models.evento_partido import EventoPartido
from app.models.hito_partido import HitoPartido
from app.models.partido import Partido
from app.models.usuario import Usuario
from app.repositories.configuracion_tiempo_torneo import ConfiguracionTiempoTorneoRepository
from app.repositories.fase import FaseRepository
from app.repositories.partido import PartidoRepository
from app.repositories.torneo import TorneoRepository
from app.schemas.partido import PartidoCreate, PartidoUpdate, ResultadoDirectoCreate
from app.services.permisos import verificar_arbitro_asignado


class PartidoService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PartidoRepository(session)
        self.fase_repo = FaseRepository(session)
        self.torneo_repo = TorneoRepository(session)
        self.config_repo = ConfiguracionTiempoTorneoRepository(session)

    async def get(self, id_: int) -> Partido:
        return await self.repo.get_or_404(id_)

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        torneo_id: int | None = None,
        estado: str | None = None,
        arbitro_id: int | None = None,
        torneo_ids_permitidos: Sequence[int] | None = None,
    ) -> list[Partido]:
        # arbitro_id (Fase 3, D1): filtro más, mismo mecanismo genérico de
        # BaseRepository.list — no hace falta tocar el repositorio.
        # torneo_ids_permitidos (control-mesa-centralizacion-fixture-plan.md,
        # ítem 1): mismo mecanismo que TorneoService.list/E1 — ver el
        # override en PartidoRepository.list.
        return await self.repo.list(
            skip=skip,
            limit=limit,
            torneo_id=torneo_id,
            estado=estado,
            arbitro_id=arbitro_id,
            torneo_ids_permitidos=torneo_ids_permitidos,
        )

    async def create(self, data: PartidoCreate) -> Partido:
        # Nada de validación de negocio acá: quién disputa el partido y si
        # los equipos están inscritos lo valida trg_partidos_validar_inscripcion
        # (06_triggers.sql). El servicio solo pasa los datos; el trigger
        # rechaza con un mensaje en español que exceptions/handlers.py
        # devuelve tal cual como 400.
        return await self.repo.create(**data.model_dump())

    async def update(self, id_: int, data: PartidoUpdate, usuario_actual: Usuario) -> Partido:
        # Árbitro solo puede tocar SU partido asignado (D5/D6,
        # roles-3-modulos-plan.md Fase 1) — carga una vez, chequea, y
        # reusa ese mismo objeto para guardar (save_changes), sin volver
        # a consultarlo.
        partido = await self.repo.get_or_404(id_)
        verificar_arbitro_asignado(partido, usuario_actual)
        return await self.repo.save_changes(partido, **data.model_dump(exclude_unset=True))

    async def soft_delete(self, id_: int) -> Partido:
        return await self.repo.soft_delete(id_, estado_inactivo="Cancelado")

    async def marcar_walkover(self, id_: int, equipo_ausente_id: int, usuario_actual: Usuario) -> Partido:
        """3B-13 (docs/plans/cierre-backlog-todos-plan.md): cierra el
        partido 3-0 a favor del equipo presente por ausencia del otro —
        vw_resultados_partidos aplica el 3-0 (ver Es_Walkover en
        04_views.sql), fn_propagar_ganador_bracket avanza al ganador solo
        con el flag, sin necesitar eventos de gol reales.

        En Eliminación (incluida la fase de playoffs de Grupos_Playoffs)
        siempre está permitido — el bracket necesita un ganador para
        avanzar. Fuera de eso (Liga, o la fase de grupos en sí) requiere
        que el torneo lo haya habilitado explícitamente
        (Torneo.Permite_Walkover_Grupos) — no todo torneo quiere que un
        no-show cueste 3 puntos automáticos."""
        partido = await self.repo.get_or_404(id_)
        verificar_arbitro_asignado(partido, usuario_actual)

        if partido.estado in ("Finalizado", "Cancelado"):
            raise DomainRuleError(f"Este partido ya está '{partido.estado}' — no se puede marcar walkover.")
        if partido.equipos_id_local is None or partido.equipos_id_visitante is None:
            raise DomainRuleError(
                "Este partido todavía no tiene los dos equipos definidos — esperá a que termine "
                "el partido anterior del bracket."
            )
        if equipo_ausente_id not in (partido.equipos_id_local, partido.equipos_id_visitante):
            raise DomainRuleError("El equipo ausente debe ser uno de los dos que disputan este partido.")

        es_eliminacion = False
        if partido.fase_id is not None:
            fase = await self.fase_repo.get(partido.fase_id)
            es_eliminacion = fase is not None and fase.tipo == "Eliminacion"

        if not es_eliminacion:
            torneo = await self.torneo_repo.get_or_404(partido.torneo_id)
            if not torneo.permite_walkover_grupos:
                raise DomainRuleError(
                    "Este torneo no habilitó walkover para Liga/fase de grupos — activá "
                    "'Permitir walkover en fase de grupos' en la configuración del torneo."
                )

        return await self.repo.save_changes(
            partido, estado="Finalizado", es_walkover=True, walkover_equipo_ausente_id=equipo_ausente_id
        )

    async def registrar_resultado_directo(
        self, id_: int, data: ResultadoDirectoCreate, usuario_actual: Usuario
    ) -> Partido:
        """Alternativa A (control-mesa-centralizacion-fixture-plan.md,
        Sección 5): "Cargar resultado directo" desde Control de Mesa, sin
        pasar por el cronómetro en vivo — orquesta Hito Inicio_Partido + N
        eventos + Hito Fin_Partido, reusando exactamente las mismas tablas
        y triggers que ya valida el flujo en vivo (trg_hito_sincroniza_estado,
        fn_validar_jugador_partido, fn_validar_ganador_corrido), sin tabla
        paralela (Alternativa B, descartada).

        Atomicidad (Sección 11 del plan, requisito no negociable): a
        diferencia de HitoPartidoService.registrar()/EventoPartidoService.create()
        (que hacen su propio `session.commit()` cada uno, vía
        BaseRepository), acá se arma todo con `session.add()` + `flush()` —
        mismo criterio que InscripcionTorneoService._crear_individual — y
        se commitea UNA sola vez al final. Los triggers de validación SÍ
        corren en cada `flush()` (no hace falta esperar al commit): si el
        evento N-ésimo es inválido (ej. jugador ajeno al equipo), la
        excepción sube sin que nada de esto se haya persistido todavía, y
        `app/db/session.py` hace rollback de la transacción completa — ni
        el Inicio_Partido ni los eventos previos quedan a medias.
        """
        partido = await self.repo.get_or_404(id_)
        verificar_arbitro_asignado(partido, usuario_actual)

        if partido.estado != "Programado":
            raise DomainRuleError(
                f"Este partido está '{partido.estado}' — el resultado directo solo se puede cargar "
                "para un partido 'Programado' que todavía no arrancó."
            )
        if partido.equipos_id_local is None or partido.equipos_id_visitante is None:
            raise DomainRuleError(
                "Este partido todavía no tiene los dos equipos definidos — esperá a que termine "
                "el partido anterior del bracket."
            )

        config = await self.config_repo.get_by_torneo(partido.torneo_id)
        if config is None:
            raise DomainRuleError("Este torneo todavía no tiene configuración de tiempos.")
        if config.tipo_cronometro == "Corrido":
            if data.ganador_corrido_id is None:
                raise DomainRuleError("Un partido Corrido necesita el ganador para finalizar.")
            if data.ganador_corrido_id not in (partido.equipos_id_local, partido.equipos_id_visitante):
                raise DomainRuleError("El ganador debe ser uno de los dos equipos que disputan el partido.")

        self.session.add(HitoPartido(partido_id=id_, tipo_hito="Inicio_Partido", registrado_por=usuario_actual.id))
        await self.session.flush()

        for evento in data.eventos:
            self.session.add(EventoPartido(partidos_id=id_, **evento.model_dump()))
            await self.session.flush()

        if config.tipo_cronometro == "Corrido":
            # Antes del Hito Fin_Partido: fn_validar_ganador_corrido exige
            # Ganador_Corrido_ID ya seteado cuando ese Hito dispare (vía
            # trg_hito_sincroniza_estado) el UPDATE a Estado='Finalizado'.
            partido.ganador_corrido_id = data.ganador_corrido_id
            await self.session.flush()

        self.session.add(HitoPartido(partido_id=id_, tipo_hito="Fin_Partido", registrado_por=usuario_actual.id))
        await self.session.flush()

        await self.session.commit()
        await self.session.refresh(partido)
        return partido
