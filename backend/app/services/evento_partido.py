from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.errors import DomainRuleError
from app.models.evento_partido import EventoPartido
from app.models.partido import Partido
from app.models.usuario import Usuario
from app.repositories.configuracion_tiempo_torneo import ConfiguracionTiempoTorneoRepository
from app.repositories.evento import EventoRepository
from app.repositories.evento_partido import EventoPartidoRepository
from app.repositories.hito_partido import HitoPartidoRepository
from app.repositories.partido import PartidoRepository
from app.repositories.torneo import TorneoRepository
from app.schemas.evento_partido import EventoPartidoCreate, EventoPartidoUpdate
from app.services.minuto_partido import calcular_minuto_actual
from app.services.permisos import verificar_arbitro_asignado


def _verificar_partido_en_curso(partido: Partido) -> None:
    """3A-8 (docs/plans/cierre-backlog-todos-plan.md), hallazgo de la
    revisión cruzada de roles-3-modulos-plan.md (decisión D6, aceptada como
    riesgo en su momento): la única protección contra cargar un evento en
    un partido que no arrancó vivía en el FILTRO de la lista de
    ControlDeMesaPage (`p.estado === "Programado" || "En curso"`, y ahí
    "Empezar Partido" siempre corre antes) — pero `MesaPanel` también se
    embebe directo en `MisPartidos.tsx` (Árbitro), un segundo camino de
    entrada que no pasa por ese filtro y podía cargar un evento en un
    partido todavía 'Programado' (o ya 'Cancelado').

    Solo 'En curso' habilita carga NUEVA sin restricciones (EC-C): un
    'Finalizado' sigue permitiendo CORREGIR minuto/anular un evento ya
    cargado a propósito (EC-15, ver EventoPartidoService.corregir_minuto),
    así que este guard es exclusivo de alta de evento nuevo — no se
    reusa en corregir_minuto/anular."""
    if partido.estado != "En curso":
        raise DomainRuleError(
            f"No se pueden cargar eventos: el partido está '{partido.estado}', no 'En curso'."
        )


class EventoPartidoService:
    """Registro de goles/tarjetas/cambios de un partido (rol Arbitro).

    Toda la validación de negocio (el equipo indicado disputa el partido, el
    jugador pertenecía a ese equipo en esa fecha, jugador_id_entra solo para
    'Cambio') la hace fn_validar_jugador_partido (06_triggers.sql). No se
    duplica acá: si se duplicara en Python y el trigger cambiara, quedarían
    desincronizados.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = EventoPartidoRepository(session)
        self.partido_repo = PartidoRepository(session)
        # Área 3 (T3/T22 — minuto automático; T5 — reglas de cambio).
        self.hito_repo = HitoPartidoRepository(session)
        self.config_repo = ConfiguracionTiempoTorneoRepository(session)
        self.torneo_repo = TorneoRepository(session)
        self.evento_catalogo_repo = EventoRepository(session)

    async def get(self, id_: int) -> EventoPartido:
        return await self.repo.get_or_404(id_)

    async def list(
        self, skip: int = 0, limit: int = 100, partidos_id: int | None = None
    ) -> list[EventoPartido]:
        return await self.repo.list(skip=skip, limit=limit, partidos_id=partidos_id)

    async def create(self, data: EventoPartidoCreate, usuario_actual: Usuario) -> EventoPartido:
        # Árbitro solo puede cargar eventos en SU partido asignado (D5,
        # roles-3-modulos-plan.md Fase 1). No hay una carga previa que
        # reusar acá — es una consulta nueva, distinta del insert que sigue.
        partido = await self.partido_repo.get_or_404(data.partidos_id)
        verificar_arbitro_asignado(partido, usuario_actual)
        _verificar_partido_en_curso(partido)

        # Área 3 (T3/T22): este método es EXCLUSIVAMENTE el camino en vivo
        # (la línea de arriba ya lo garantiza — solo 'En curso' llega hasta
        # acá), así que el minuto se calcula SIEMPRE server-side desde el
        # cronómetro — lo que `data.minuto` traiga se ignora. El resultado
        # directo (PartidoService.registrar_resultado_directo) es el único
        # camino que sigue aceptando el minuto del cliente, y no pasa por
        # este método (inserta EventoPartido directo).
        minuto = await self._minuto_en_vivo(partido)

        await self._validar_reglas_cambio(partido, data)

        datos = data.model_dump()
        datos["minuto"] = minuto
        return await self.repo.create(**datos)

    async def _minuto_en_vivo(self, partido: Partido) -> int:
        config = await self.config_repo.get_by_torneo(partido.torneo_id)
        if config is None:
            # No debería pasar (Inicio_Partido exige config, ver
            # HitoPartidoService._cargar_contexto) — mensaje de dominio en
            # vez de dejar que un None se cuele silencioso más abajo
            # (Sección 2 del plan: el GAP real era justo esto).
            raise DomainRuleError("Este torneo todavía no tiene configuración de tiempos.")
        hitos = await self.hito_repo.listar_por_partido(partido.id)
        minuto = calcular_minuto_actual(hitos, config, datetime.now())
        if minuto is None:
            raise DomainRuleError(
                "El cronómetro todavía no arrancó — esperá el primer inicio de partido para cargar eventos."
            )
        return minuto

    async def _validar_reglas_cambio(self, partido: Partido, data: EventoPartidoCreate) -> None:
        """Área 3 (T5): tope de cantidad + no-retorno, gobernados por
        `Torneo.maximo_cambios_por_equipo`/`Torneo.permite_cambios_ilimitados`
        — ver el comentario grande en 01_schema.sql para por qué son 2 ejes
        independientes. Solo aplica a tipo_hito='Cambio'; cualquier otro
        evento (Gol, Autogol, tarjetas) no toca esto."""
        evento_catalogo = await self.evento_catalogo_repo.get_or_404(data.eventos_id)
        if evento_catalogo.nombre != "Cambio":
            return

        torneo = await self.torneo_repo.get_or_404(partido.torneo_id)

        if not torneo.permite_cambios_ilimitados and data.jugador_id_entra is not None:
            ya_salio = await self.repo.list(
                limit=1,
                partidos_id=partido.id,
                eventos_id=data.eventos_id,
                jugador_id=data.jugador_id_entra,
                estado="Registrado",
            )
            if ya_salio:
                raise DomainRuleError(
                    "Ese jugador ya salió por cambio antes en este partido — este torneo no permite "
                    "reingresos (cambios rotativos). Activá 'Permite cambios ilimitados' si corresponde."
                )

        if torneo.maximo_cambios_por_equipo is not None:
            usados = await self.repo.list(
                limit=torneo.maximo_cambios_por_equipo + 1,
                partidos_id=partido.id,
                eventos_id=data.eventos_id,
                equipo_id=data.equipo_id,
                estado="Registrado",
            )
            if len(usados) >= torneo.maximo_cambios_por_equipo:
                raise DomainRuleError(
                    f"Ya se usaron los {torneo.maximo_cambios_por_equipo} cambios permitidos para "
                    "este equipo en este partido."
                )

    async def corregir_minuto(self, id_: int, minuto: int, usuario_actual: Usuario) -> EventoPartido:
        """PATCH /eventos-partido/{id} (gestion-avanzada-equipos-control-
        mesa-plan.md) — corrección de minuto de un gol/tarjeta/cambio ya
        cargado, gap preexistente que responde directamente al Entregable
        3 del plan ("¿cómo editás minutos si el árbitro se equivoca?") para
        el caso de eventos de partido, distinto del de Hitos de tiempo (ver
        HitoPartidoService.corregir). Se permite en cualquier estado del
        partido, incluido 'Finalizado' (EC-15) — un error se puede
        descubrir después de cerrado. El UPDATE vuelve a pasar por
        fn_validar_jugador_partido (revalidación en UPDATE, 06_triggers.sql)."""
        evento = await self.repo.get_or_404(id_)
        partido = await self.partido_repo.get_or_404(evento.partidos_id)
        verificar_arbitro_asignado(partido, usuario_actual)
        return await self.repo.save_changes(evento, minuto=minuto)

    async def anular(self, id_: int, usuario_actual: Usuario) -> EventoPartido:
        """Anula un evento cargado por error (ej: gol mal registrado).

        Único de los tres chequeos que reusa una carga que ya iba a pasar:
        get_or_404(id_) trae el evento (para saber su partidos_id) antes de
        mutar, en vez de una consulta aparte.
        """
        evento = await self.repo.get_or_404(id_)
        partido = await self.partido_repo.get_or_404(evento.partidos_id)
        verificar_arbitro_asignado(partido, usuario_actual)
        return await self.repo.save_changes(evento, estado="Anulado")
