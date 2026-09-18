import logging
import time
from datetime import datetime

import psycopg.errors as psycopg_errors
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.exceptions.errors import ConcurrencyConflictError, DomainRuleError
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

logger = logging.getLogger("app.concurrencia")

# A1 (docs/plans/cierre-pendientes-todos-plan.md): clasifica un
# OperationalError de Postgres levantado por el `SELECT ... FOR UPDATE` con
# lock_timeout o por cualquier punto de la transacción — dos categorías
# distintas, tratadas distinto por los callers de este módulo:
# "contencion" (55P03 LockNotAvailable / 57014 QueryCanceled, el lock_timeout
# se agotó esperando) nunca se reintenta — ya esperamos lo que había que
# esperar; "deadlock" (40P01, DeadlockDetected) SÍ se reintenta una vez,
# como defensa en profundidad, aunque con un solo recurso lockeado (el
# Partido) por transacción un deadlock cruzado no debería ocurrir entre los
# dos callers de get_or_404_bloqueado (ver docstring de _crear_bajo_lock).
def _clasificar_error_concurrencia(exc: OperationalError) -> str | None:
    if isinstance(exc.orig, (psycopg_errors.LockNotAvailable, psycopg_errors.QueryCanceled)):
        return "contencion"
    if isinstance(exc.orig, psycopg_errors.DeadlockDetected):
        return "deadlock"
    return None


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
        """A1 (docs/plans/cierre-pendientes-todos-plan.md) — REESTRUCTURADO
        para cerrar la carrera de la doble tarjeta amarilla simultánea:
        antes, `self.repo.create()` commiteaba el evento (liberando
        cualquier lock) ANTES de que `_procesar_doble_amarilla_si_corresponde`
        contara las amarillas — dos requests concurrentes sobre el mismo
        jugador veían 1 amarilla cada uno y ninguno disparaba la roja
        automática. Ahora todo el intento (lock del partido + validación +
        insert del evento + roja automática si corresponde) es UNA sola
        transacción con un solo `commit()` final, igual que
        `PartidoService.registrar_resultado_directo` (ver su docstring).

        T-5 (decisión de taste del Gate): el catálogo de eventos se resuelve
        ANTES de tomar el lock del partido — no depende de esa fila, así que
        no tiene por qué alargar la ventana en la que el lock está tomado."""
        settings = get_settings()
        evento_catalogo = await self.evento_catalogo_repo.get_or_404(data.eventos_id)
        roja_catalogo_id: int | None = None
        if evento_catalogo.nombre == "Tarjeta Amarilla":
            rojas = await self.evento_catalogo_repo.list(limit=1, nombre="Tarjeta Roja")
            roja_catalogo_id = rojas[0].id if rojas else None

        intentos_restantes = settings.evento_concurrencia_reintentos
        while True:
            try:
                return await self._crear_bajo_lock(data, usuario_actual, evento_catalogo, roja_catalogo_id, settings)
            except OperationalError as exc:
                clasificacion = _clasificar_error_concurrencia(exc)
                if clasificacion is None:
                    raise
                # Tras cualquier error DBAPI, SQLAlchemy deja la sesión en
                # pending-rollback — sin este rollback, tanto el reintento
                # como el ConcurrencyConflictError de abajo fallarían con un
                # PendingRollbackError confuso en vez del error real.
                await self.session.rollback()
                if clasificacion == "contencion" or intentos_restantes <= 0:
                    raise ConcurrencyConflictError() from exc
                intentos_restantes -= 1
                # `rollback()` expira TODOS los objetos de la sesión,
                # incluidos los que se resolvieron ANTES del retry loop
                # (fuera de `_crear_bajo_lock`): `usuario_actual` (cargado
                # por `get_current_user`, antes de este método) y
                # `evento_catalogo` (T-5, resuelto antes del lock). Tocar un
                # atributo expirado con acceso sincrónico
                # (`usuario_actual.id`, `evento_catalogo.nombre`) en modo
                # async revienta con MissingGreenlet — hay que refrescarlos
                # con un `await` explícito antes de reintentar.
                await self.session.refresh(usuario_actual)
                await self.session.refresh(evento_catalogo)

    async def _crear_bajo_lock(
        self,
        data: EventoPartidoCreate,
        usuario_actual: Usuario,
        evento_catalogo,
        roja_catalogo_id: int | None,
        settings: Settings,
    ) -> EventoPartido:
        """Un intento completo de `create()`: lock, validación, insert,
        doble amarilla, commit. Reintentable ENTERO (no solo el insert) —
        el `minuto` se recalcula acá adentro en cada intento (nunca se
        reusa el de un intento previo que falló: escribiría un minuto
        viejo, y `chk_eventos_partido_minuto` no lo atraparía porque sigue
        estando entre 0 y 130).

        Con un solo recurso lockeado por transacción (este Partido, primero
        y único), un deadlock cruzado (40P01) entre este método y
        `PartidoService.registrar_resultado_directo` no debería ocurrir —
        ambos toman el `FOR UPDATE` sobre la misma fila, PRIMERO, así que
        el peor caso es contención (esperan y uno de los dos vence el
        `lock_timeout`), no un ciclo. El reintento de `create()` queda como
        defensa en profundidad para un tercer camino futuro que lockee más
        de un recurso, no porque este par lo necesite hoy."""
        partido = await self._bloquear_partido_con_timeout(data.partidos_id, usuario_actual.id, settings)
        # Árbitro solo puede cargar eventos en SU partido asignado (D5,
        # roles-3-modulos-plan.md Fase 1).
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

        await self._validar_reglas_cambio(partido, data, evento_catalogo)

        datos = data.model_dump()
        datos["minuto"] = minuto
        evento = EventoPartido(**datos)
        self.session.add(evento)
        await self.session.flush()

        # control-mesa-reactividad-playoffs-plan.md, Fase 3 §3 — listener de
        # doble amarilla en el camino EN VIVO, en la MISMA transacción que
        # el evento que lo dispara (eso es lo que A1 arregla: antes el
        # commit del evento liberaba el lock ANTES de que esto contara las
        # amarillas). Espejo del wiring en
        # `PartidoService.registrar_resultado_directo` (mismo módulo
        # `reglas_tarjetas`, ver su docstring, ya actualizado — los dos
        # callers comparten la misma disciplina transaccional ahora).
        if evento_catalogo.nombre == "Tarjeta Amarilla" and roja_catalogo_id is not None:
            roja_auto = await procesar_doble_amarilla(
                evento_partido_repo=self.repo,
                partido_id=evento.partidos_id,
                jugador_id=evento.jugador_id,
                equipo_id=evento.equipo_id,
                eventos_id_amarilla=evento.eventos_id,
                eventos_id_roja=roja_catalogo_id,
                minuto=minuto,
            )
            if roja_auto is not None:
                self.session.add(roja_auto)
                await self.session.flush()

        await self.session.commit()
        return evento

    async def _bloquear_partido_con_timeout(self, partido_id: int, usuario_id: int, settings: Settings) -> Partido:
        """`SET LOCAL lock_timeout` + `get_or_404_bloqueado` — sin esto, el
        default de Postgres es 0 (esperar para siempre): un cliente que
        muere reteniendo el `FOR UPDATE` cuelga indefinidamente todo evento
        posterior de ese partido, con `verificar.ps1` en verde porque
        ningún test lo detecta. Si la espera supera el umbral configurado
        (haya terminado en éxito o en `lock_timeout`), se loguea de forma
        estructurada con `partido_id` y `usuario_id` — el log solo puede
        dispararse DESPUÉS de que la espera termina, así que sin timeout
        esta alerta para un cuelgue indefinido nunca se emitiría.

        Runbook: si esta espera es constante (no un pico aislado), revisar
        `pg_stat_activity` por una transacción abierta sobre ese partido —
        normalmente un cliente que abrió la carga y nunca la cerró."""
        inicio = time.monotonic()
        try:
            # `SET LOCAL` no acepta bind parameters (Postgres los rechaza
            # con "syntax error near $1") — el valor se interpola directo.
            # Sin riesgo de inyección: `evento_lock_timeout_ms` es un int de
            # `Settings`, nunca un valor que venga del cliente.
            await self.session.execute(text(f"SET LOCAL lock_timeout = '{settings.evento_lock_timeout_ms}ms'"))
            return await self.partido_repo.get_or_404_bloqueado(partido_id)
        finally:
            espera_ms = (time.monotonic() - inicio) * 1000
            if espera_ms >= settings.evento_lock_log_umbral_ms:
                logger.warning(
                    "Espera larga por FOR UPDATE en Partido id=%s (usuario_id=%s): %.0fms — "
                    "si es constante, revisar pg_stat_activity por una transacción abierta sobre ese partido.",
                    partido_id,
                    usuario_id,
                    espera_ms,
                )

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

    async def _validar_reglas_cambio(self, partido: Partido, data: EventoPartidoCreate, evento_catalogo) -> None:
        """Área 3 (T5): delega en `reglas_cambio.validar_reglas_cambio`
        (goles-por-marcador-slots-plan.md, Fase 3 Eng, corrección 3) — la
        lógica de tope/no-retorno/doble-salida vive ahí, compartida con
        `PartidoService.registrar_resultado_directo`, no acá. Este método
        queda como wrapper delgado: solo el early-return barato si no es
        'Cambio' y la consulta de torneo. `evento_catalogo` ya lo resuelve
        `create()` antes de tomar el lock (T-5) — no se vuelve a consultar."""
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

        A1 (docs/plans/cierre-pendientes-todos-plan.md): si el evento
        objetivo es una tarjeta, toma el mismo lock de partido que
        `create()`. `_procesar_doble_amarilla_si_corresponde` (dentro de
        `_crear_bajo_lock`) cuenta las amarillas filtrando
        `estado='Registrado'`, y este método muta esa misma columna
        (`save_changes(evento, estado='Anulado')`) — sin el lock, anular la
        amarilla #1 en paralelo con el insert de la amarilla #2 corre la
        carrera en las dos direcciones: una roja para un jugador con una
        sola amarilla válida, o la desaparición de la roja que A1 garantiza.
        `corregir_minuto` (arriba) NO necesita esto: la regla de doble
        amarilla no lee el minuto, así que no hay carrera que cerrar ahí.
        """
        evento = await self.repo.get_or_404(id_)
        evento_catalogo = await self.evento_catalogo_repo.get_or_404(evento.eventos_id)
        es_tarjeta = evento_catalogo.nombre in ("Tarjeta Amarilla", "Tarjeta Roja")
        if es_tarjeta:
            settings = get_settings()
            try:
                partido = await self._bloquear_partido_con_timeout(evento.partidos_id, usuario_actual.id, settings)
            except OperationalError as exc:
                clasificacion = _clasificar_error_concurrencia(exc)
                if clasificacion is None:
                    raise
                await self.session.rollback()
                raise ConcurrencyConflictError() from exc
        else:
            partido = await self.partido_repo.get_or_404(evento.partidos_id)
        verificar_arbitro_asignado(partido, usuario_actual)
        return await self.repo.save_changes(evento, estado="Anulado")
