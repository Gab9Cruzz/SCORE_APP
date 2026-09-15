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
from app.services.reglas_cambio import validar_reglas_cambio
from app.services.reglas_tarjetas import procesar_doble_amarilla


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
        evento = await self.repo.create(**datos)
        await self._procesar_doble_amarilla_si_corresponde(evento, minuto)
        return evento

    async def _procesar_doble_amarilla_si_corresponde(self, evento: EventoPartido, minuto: int) -> None:
        """control-mesa-reactividad-playoffs-plan.md, Fase 3 §3 — listener
        de doble amarilla en el camino EN VIVO. Espejo del wiring en
        `PartidoService.registrar_resultado_directo` (mismo módulo
        `reglas_tarjetas`, ver su docstring): ambos caminos de inserción de
        eventos necesitan la regla, no solo uno."""
        evento_catalogo = await self.evento_catalogo_repo.get_or_404(evento.eventos_id)
        if evento_catalogo.nombre != "Tarjeta Amarilla":
            return
        rojas = await self.evento_catalogo_repo.list(limit=1, nombre="Tarjeta Roja")
        if not rojas:
            return
        roja_auto = await procesar_doble_amarilla(
            evento_partido_repo=self.repo,
            partido_id=evento.partidos_id,
            jugador_id=evento.jugador_id,
            equipo_id=evento.equipo_id,
            eventos_id_amarilla=evento.eventos_id,
            eventos_id_roja=rojas[0].id,
            minuto=minuto,
        )
        if roja_auto is None:
            return
        # `procesar_doble_amarilla` devuelve sin persistir (ver su
        # docstring) — acá SÍ se commitea de inmediato, mismo criterio que
        # `self.repo.create()` arriba (este método ya hace un commit por
        # evento, a diferencia de `registrar_resultado_directo`).
        self.session.add(roja_auto)
        await self.session.commit()

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
        """Área 3 (T5): delega en `reglas_cambio.validar_reglas_cambio`
        (goles-por-marcador-slots-plan.md, Fase 3 Eng, corrección 3) — la
        lógica de tope/no-retorno/doble-salida vive ahí, compartida con
        `PartidoService.registrar_resultado_directo`, no acá. Este método
        queda como wrapper delgado: solo resuelve el catálogo de evento
        (para el early-return barato si no es 'Cambio', sin gastar la
        consulta de torneo en el caso común de Gol/tarjeta) y el torneo."""
        evento_catalogo = await self.evento_catalogo_repo.get_or_404(data.eventos_id)
        if evento_catalogo.nombre != "Cambio":
            return

        torneo = await self.torneo_repo.get_or_404(partido.torneo_id)
        await validar_reglas_cambio(
            torneo=torneo,
            evento_catalogo_nombre=evento_catalogo.nombre,
            evento_partido_repo=self.repo,
            partido_id=partido.id,
            jugador_id=data.jugador_id,
            jugador_id_entra=data.jugador_id_entra,
            equipo_id=data.equipo_id,
            eventos_id=data.eventos_id,
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
