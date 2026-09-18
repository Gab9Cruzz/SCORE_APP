from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.errors import DomainRuleError
from app.models.configuracion_tiempo_torneo import ConfiguracionTiempoTorneo
from app.models.hito_partido import HitoPartido
from app.models.modalidad import Modalidad
from app.models.partido import Partido
from app.models.torneo import Torneo
from app.models.usuario import Usuario
from app.repositories.configuracion_tiempo_torneo import ConfiguracionTiempoTorneoRepository
from app.repositories.convocado_a_partido import ConvocadoAPartidoRepository
from app.repositories.equipo import EquipoRepository
from app.repositories.fase import FaseRepository
from app.repositories.hito_partido import HitoPartidoRepository
from app.repositories.inscripcion_torneo import InscripcionTorneoRepository
from app.repositories.jugador_equipo import JugadorEquipoRepository
from app.repositories.modalidad import ModalidadRepository
from app.repositories.partido import PartidoRepository
from app.repositories.torneo import TorneoRepository
from app.repositories.torneo_grupo import TorneoGrupoRepository
from app.schemas.hito_partido import (
    DeshacerCierreForzadoOut,
    EstadoCronometroOut,
    HitoPartidoCreate,
    HitoPartidoOut,
    HitoPartidoUpdate,
    PreflightInicioOut,
    TitularesEquipoOut,
)
from app.core.metricas import registrar_evento
from app.services.desempate import (
    completar_metodo_manual,
    derivar_ganador_desde_penales,
    es_escape_manual_sobre_metodo_configurado,
)
from app.services.permisos import verificar_arbitro_asignado
from app.services.reglamento_torneo import ReglamentoTorneo

# Área 4 (T6/T17): ventana de deshacer del cierre forzado, real y
# autoritativa en el SERVIDOR (Eng Fase 3, corrección de diseño — ver
# HitoPartidoService._registrar_fin_forzado). Constante de módulo porque la
# usan tanto el registro (calcula deshacer_disponible_hasta) como el
# deshacer (valida contra ella).
VENTANA_DESHACER_SEGUNDOS = 5


class HitoPartidoService:
    """Motor de Tiempos + Control de Mesa en vivo
    (gestion-avanzada-equipos-control-mesa-plan.md, Fase 3). La secuencia
    ESTRICTA (qué hito es válido a continuación) vive acá, no solo en el
    trigger de la base (fn_validar_hito_partido, que solo evita
    duplicados/coherencia de Numero_Periodo) — es la misma regla que
    decide qué botones habilita el frontend (GET .../cronometro), server-
    side como defensa en profundidad, no duplicada en SQL y en Python."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = HitoPartidoRepository(session)
        self.partido_repo = PartidoRepository(session)
        self.config_repo = ConfiguracionTiempoTorneoRepository(session)
        # B.2 (fixes-datos-traspasos-control-mesa-plan.md, D4): validación
        # de titulares antes de Inicio_Partido — ver _validar_titulares.
        self.torneo_repo = TorneoRepository(session)
        # Desempate de eliminatoria: tiempo extra y penales (D6/§8) — para
        # saber si ESTE partido es de fase Eliminación al snapshotear
        # Metodo_Desempate_Aplicable en Inicio_Partido.
        self.fase_repo = FaseRepository(session)
        # Cascada de archivado (cascada-archivado-alineaciones-traspasos-
        # plan.md, P7): defensa en profundidad contra Inicio_Partido en un
        # torneo archivado — ver _validar_torneo_no_archivado.
        self.torneo_grupo_repo = TorneoGrupoRepository(session)
        self.modalidad_repo = ModalidadRepository(session)
        self.equipo_repo = EquipoRepository(session)
        self.inscripcion_repo = InscripcionTorneoRepository(session)
        self.jugador_equipo_repo = JugadorEquipoRepository(session)
        self.convocado_repo = ConvocadoAPartidoRepository(session)

    async def _cargar_contexto(self, partido_id: int) -> tuple[Partido, ConfiguracionTiempoTorneo, list[HitoPartido]]:
        partido = await self.partido_repo.get_or_404(partido_id)
        config = await self.config_repo.get_by_torneo(partido.torneo_id)
        if config is None:
            raise DomainRuleError("Este torneo todavía no tiene configuración de tiempos.")
        hitos = await self.repo.listar_por_partido(partido_id)
        return partido, config, hitos

    async def estado_cronometro(self, partido_id: int) -> EstadoCronometroOut:
        _partido, config, hitos = await self._cargar_contexto(partido_id)
        estado = self._calcular_estado(hitos, config)
        return EstadoCronometroOut(
            tipo_cronometro=config.tipo_cronometro,
            cantidad_periodos=config.cantidad_periodos,
            duracion_periodo_minutos=config.duracion_periodo_minutos,
            duracion_descanso_minutos=config.duracion_descanso_minutos,
            hitos=[HitoPartidoOut.model_validate(h) for h in hitos],
            **estado,
        )

    @staticmethod
    def _calcular_estado(hitos: list[HitoPartido], config: ConfiguracionTiempoTorneo) -> dict:
        partido_iniciado = any(h.tipo_hito == "Inicio_Partido" for h in hitos)
        partido_finalizado = any(h.tipo_hito == "Fin_Partido" for h in hitos)

        # Pausa/Reanudacion pueden repetirse (trg_hito_partido_validar las
        # exceptúa del chequeo de duplicados) — el estado real es "cuál fue
        # la última de las dos", recorriendo en orden cronológico (ID
        # ascendente, ver HitoPartidoRepository.listar_por_partido).
        en_pausa = False
        for h in hitos:
            if h.tipo_hito == "Pausa":
                en_pausa = True
            elif h.tipo_hito == "Reanudacion":
                en_pausa = False

        periodo_abierto: int | None = None
        ultimo_periodo_cerrado = 0
        if config.tipo_cronometro == "Periodos":
            iniciados = {h.numero_periodo for h in hitos if h.tipo_hito == "Inicio_Periodo"}
            cerrados = {h.numero_periodo for h in hitos if h.tipo_hito == "Fin_Periodo"}
            ultimo_periodo_cerrado = max(cerrados) if cerrados else 0
            abiertos = iniciados - cerrados
            periodo_abierto = max(abiertos) if abiertos else None

        acciones: list[str] = []
        if not partido_iniciado:
            acciones.append("Inicio_Partido")
        elif not partido_finalizado:
            corriendo = periodo_abierto is not None if config.tipo_cronometro == "Periodos" else True

            if corriendo and not en_pausa:
                acciones.append("Pausa")
            elif en_pausa:
                acciones.append("Reanudacion")

            if config.tipo_cronometro == "Periodos":
                cantidad = config.cantidad_periodos or 0
                if periodo_abierto is not None:
                    acciones.append("Fin_Periodo")
                elif ultimo_periodo_cerrado < cantidad:
                    acciones.append("Inicio_Periodo")
                if periodo_abierto is None and cantidad and ultimo_periodo_cerrado == cantidad:
                    acciones.append("Fin_Partido")
            else:
                acciones.append("Fin_Partido")

        return {
            "partido_iniciado": partido_iniciado,
            "partido_finalizado": partido_finalizado,
            "periodo_abierto": periodo_abierto,
            "ultimo_periodo_cerrado": ultimo_periodo_cerrado,
            "en_pausa": en_pausa,
            "acciones_permitidas": acciones,
        }

    async def _validar_torneo_no_archivado(self, torneo: Torneo) -> None:
        """Defensa en profundidad (cascada-archivado-alineaciones-
        traspasos-plan.md, P7): GET /partidos ya excluye del listado los
        partidos 'Programado' de un torneo cuyo grupo está Archivado — la
        UI de Control de Mesa nunca ofrece el botón "Empezar Partido" para
        uno de estos. Esto es el resguardo de backend por si alguien
        intenta arrancarlo igual vía API directa, mismo criterio que
        _validar_titulares (B.2): la fuente de verdad vive acá, no solo en
        qué oculta la UI."""
        grupo = await self.torneo_grupo_repo.get_or_404(torneo.torneo_grupo_id)
        if grupo.estado == "Archivado":
            raise DomainRuleError("Este torneo está archivado — reactivalo antes de operar sus partidos.")

    @staticmethod
    def _minimo_requerido(torneo: Torneo, modalidad: Modalidad) -> int:
        """Cuántos titulares por equipo exige "Empezar Partido"
        (gestionar-partido-alineaciones-plan.md, D1) — delega en
        ReglamentoTorneo, único lugar que resuelve este fallback ahora
        (antes duplicado acá y en ConvocadoAPartidoService)."""
        return ReglamentoTorneo.desde(torneo).minimo_titulares(modalidad.tamano_equipo)

    @staticmethod
    def _maximo_permitido(torneo: Torneo, modalidad: Modalidad) -> int:
        """Tope SUPERIOR de titulares por equipo (modo-vivo-sustituciones-
        cierre-plan.md, Área 1, T2/T18) — espejo de `_minimo_requerido`,
        mismo motivo para delegar en ReglamentoTorneo."""
        return ReglamentoTorneo.desde(torneo).maximo_titulares(modalidad.tamano_equipo)

    async def _contar_titulares(self, partido: Partido, torneo: Torneo) -> tuple[int, list[dict]]:
        """Cuántos titulares válidos tiene cada equipo y cuántos hacen falta.

        Extraído de `_validar_titulares` para que el preflight
        (gestionar-partido-alineaciones-plan.md, H1-eng) publique EXACTAMENTE
        el mismo veredicto que después va a aplicar el gate de arranque. Si
        esto se duplicara, el botón del frontend prometería lo que el backend
        rechaza — que es el problema que C1 del plan viene a cerrar.

        Un `ConvocadoAPartido.titular=True` de un jugador que ya no está en el
        roster activo del equipo (dado de baja después de convocarlo) no
        cuenta: se intersecta contra el roster vigente, no se confía en la
        convocatoria sola.

        Devuelve `(requeridos, [{equipo_id, nombre, titulares}])`.
        """
        modalidad = await self.modalidad_repo.get_or_404(torneo.modalidad_id)
        requeridos = self._minimo_requerido(torneo, modalidad)

        convocados = await self.convocado_repo.listar_por_partido(partido.id)
        titulares_convocados = {c.jugador_perfil_id for c in convocados if c.titular}

        por_equipo: list[dict] = []
        for equipo_id in (partido.equipos_id_local, partido.equipos_id_visitante):
            inscripciones = await self.inscripcion_repo.list(torneo_id=torneo.id, equipo_id=equipo_id, limit=1)
            if inscripciones:
                roster_activo = await self.jugador_equipo_repo.list(
                    inscripcion_torneo_id=inscripciones[0].id, estado="Activo", limit=10_000
                )
                perfiles_roster = {j.jugador_perfil_id for j in roster_activo}
                n = len(titulares_convocados & perfiles_roster)
            else:
                # No debería pasar (P12: todo Partido con equipo_id sale de
                # una inscripción real) — se trata como 0 titulares, no
                # como un 500 sin explicación.
                n = 0
            equipo = await self.equipo_repo.get_or_404(equipo_id)
            por_equipo.append({"equipo_id": equipo_id, "nombre": equipo.nombre, "titulares": n})

        return requeridos, por_equipo

    def _motivo_faltan_titulares(self, torneo: Torneo, requeridos: int, fila: dict) -> str:
        titular_plural = "es" if fila["titulares"] != 1 else ""
        marcado_plural = "s" if fila["titulares"] != 1 else ""
        # El texto distingue de dónde sale el número: si el torneo tiene un
        # mínimo propio, decir "esta modalidad exige N" sería mentira (la
        # modalidad puede exigir más).
        origen = (
            "el reglamento de este torneo exige"
            if torneo.minimo_jugadores_para_iniciar
            else "esta modalidad exige"
        )
        return (
            f"{fila['nombre']} tiene {fila['titulares']} titular{titular_plural} "
            f"marcado{marcado_plural}, {origen} {requeridos}. "
            "Definí la convocatoria antes de empezar el partido."
        )

    async def _validar_titulares(self, partido: Partido, torneo: Torneo) -> None:
        """B.2 (fixes-datos-traspasos-control-mesa-plan.md, D4/P10): antes
        de esto, "Empezar Partido" no validaba nada de la convocatoria — el
        partido arrancaba aunque nadie hubiera tocado "Convocados".

        Cuántos titulares exige sale de `_minimo_requerido` (el mínimo del
        torneo si lo tiene, si no `Modalidad.tamano_equipo`), y el conteo de
        `_contar_titulares`, compartido con el preflight.

        `torneo` llega ya resuelto por `registrar()` (cascada-archivado-
        alineaciones-traspasos-plan.md, P7) — evita pedirlo dos veces junto
        con `_validar_torneo_no_archivado`, que corre antes."""
        if partido.equipos_id_local is None or partido.equipos_id_visitante is None:
            # P12: todo PARTIDOS de Equipo/Pareja nace de un bracket o de un
            # fixture ya armado — este caso es "todavía no se sabe quién
            # juega" (bracket en curso), no un partido con titulares
            # pendientes de definir.
            raise DomainRuleError(
                "Este partido todavía no tiene los dos equipos definidos — esperá a que termine "
                "el partido anterior del bracket."
            )

        requeridos, por_equipo = await self._contar_titulares(partido, torneo)
        for fila in por_equipo:
            if fila["titulares"] < requeridos:
                raise DomainRuleError(self._motivo_faltan_titulares(torneo, requeridos, fila))

    async def _snapshotear_metodo_desempate_aplicable(self, partido: Partido, torneo: Torneo) -> Partido:
        """D6/§8: graba en `Metodo_Desempate_Aplicable` la regla CONCRETA
        que rige a ESTE partido, tomada de `Torneo.metodo_desempate_eliminatoria`
        en el instante en que el partido arranca — no la regla actual del
        torneo, que puede cambiar después sin afectar partidos ya
        arrancados (la edición en `TorneoUpdate` queda libre de romper
        nada retroactivamente).

        Solo para partidos de fase Eliminación — en cualquier otro caso
        (Liga/Grupos) queda NULL, que es la señal que usa
        `_periodos_totales_permitidos` (Fase 3) para saber que esto no es
        un partido de eliminación sin que se le pase la fase aparte."""
        if partido.fase_id is None:
            return partido
        fase = await self.fase_repo.get(partido.fase_id)
        if fase is None or fase.tipo != "Eliminacion":
            return partido
        metodo_aplicable = ReglamentoTorneo.desde(torneo).resolver_desempate_aplicable(partido.ronda_nombre)
        return await self.partido_repo.save_changes(partido, metodo_desempate_aplicable=metodo_aplicable)

    async def preflight_inicio(self, partido_id: int) -> PreflightInicioOut:
        """¿Se puede tocar "Empezar Partido"? — el veredicto que consume el
        frontend (gestionar-partido-alineaciones-plan.md, H1-eng).

        Endpoint propio y AUTENTICADO en vez de campos nuevos en
        `GET /partidos/{id}/cronometro`: ese es público sin auth y lo pollean
        cada 5 segundos `Cronometro.tsx` y `PartidoEnVivo.tsx` de forma
        anónima. Meterle este cálculo (~7 queries, con un `list(limit=10_000)`
        de roster por equipo) lo convertiría en el endpoint más caro del
        sistema, sin autenticación de por medio.

        Reusa `_contar_titulares` y `_validar_torneo_no_archivado` para que el
        veredicto publicado sea el mismo que aplica `registrar()` — si
        divergieran, el botón se habilitaría y el POST devolvería 400 (M5-eng).
        """
        partido = await self.partido_repo.get_or_404(partido_id)
        torneo = await self.torneo_repo.get_or_404(partido.torneo_id)
        modalidad = await self.modalidad_repo.get_or_404(torneo.modalidad_id)

        ya_inicio = await self.repo.existe_inicio_partido(partido_id)
        if ya_inicio:
            # Una vez arrancado, "puede iniciar" no significa nada. Se devuelve
            # el mínimo (la UI lo sigue mostrando como referencia) pero no se
            # recalcula el roster: es el caso que más se consulta y el más caro.
            return PreflightInicioOut(
                minimo_para_iniciar=self._minimo_requerido(torneo, modalidad),
                maximo_titulares=self._maximo_permitido(torneo, modalidad),
                titulares_por_equipo=[],
                puede_iniciar=False,
                motivo_bloqueo="El partido ya arrancó.",
                partido_iniciado=True,
            )

        if partido.equipos_id_local is None or partido.equipos_id_visitante is None:
            return PreflightInicioOut(
                minimo_para_iniciar=self._minimo_requerido(torneo, modalidad),
                maximo_titulares=self._maximo_permitido(torneo, modalidad),
                titulares_por_equipo=[],
                puede_iniciar=False,
                motivo_bloqueo=(
                    "Este partido todavía no tiene los dos equipos definidos — esperá a que termine "
                    "el partido anterior del bracket."
                ),
                partido_iniciado=False,
            )

        try:
            await self._validar_torneo_no_archivado(torneo)
        except DomainRuleError as exc:
            return PreflightInicioOut(
                minimo_para_iniciar=self._minimo_requerido(torneo, modalidad),
                maximo_titulares=self._maximo_permitido(torneo, modalidad),
                titulares_por_equipo=[],
                puede_iniciar=False,
                motivo_bloqueo=str(exc),
                partido_iniciado=False,
            )

        requeridos, por_equipo = await self._contar_titulares(partido, torneo)
        faltantes = [f for f in por_equipo if f["titulares"] < requeridos]
        motivo = self._motivo_faltan_titulares(torneo, requeridos, faltantes[0]) if faltantes else None

        return PreflightInicioOut(
            minimo_para_iniciar=requeridos,
            maximo_titulares=self._maximo_permitido(torneo, modalidad),
            titulares_por_equipo=[TitularesEquipoOut(**f) for f in por_equipo],
            puede_iniciar=not faltantes,
            motivo_bloqueo=motivo,
            partido_iniciado=False,
        )

    async def registrar(self, partido_id: int, data: HitoPartidoCreate, usuario_actual: Usuario) -> HitoPartidoOut:
        partido, config, hitos = await self._cargar_contexto(partido_id)
        verificar_arbitro_asignado(partido, usuario_actual)

        estado = self._calcular_estado(hitos, config)

        if data.forzado:
            # Área 4 (T6): reusa este mismo endpoint (mismo Hito terminal,
            # mismo trigger de sincronización) en vez de un segundo camino
            # de escritura — ver _registrar_fin_forzado.
            return await self._registrar_fin_forzado(partido, config, estado, data, usuario_actual)

        if data.tipo_hito not in estado["acciones_permitidas"]:
            raise DomainRuleError(
                f"No se puede registrar '{data.tipo_hito}' en el estado actual del partido "
                f"(hitos válidos ahora: {', '.join(estado['acciones_permitidas']) or 'ninguno'})."
            )

        if data.tipo_hito == "Inicio_Partido":
            # Fail-fast (P7): no tiene sentido calcular titulares de un
            # torneo que ni siquiera puede operarse — se resuelve el
            # torneo una sola vez para las dos validaciones.
            torneo = await self.torneo_repo.get_or_404(partido.torneo_id)
            await self._validar_torneo_no_archivado(torneo)
            await self._validar_titulares(partido, torneo)
            partido = await self._snapshotear_metodo_desempate_aplicable(partido, torneo)

        numero_periodo = data.numero_periodo
        if data.tipo_hito == "Inicio_Periodo" and numero_periodo is None:
            numero_periodo = estado["ultimo_periodo_cerrado"] + 1
        elif data.tipo_hito == "Fin_Periodo" and numero_periodo is None:
            numero_periodo = estado["periodo_abierto"]

        if data.tipo_hito == "Fin_Partido" and config.tipo_cronometro == "Corrido":
            if data.ganador_corrido_id is None:
                raise DomainRuleError("Un partido Corrido necesita el ganador para finalizar.")
            if data.ganador_corrido_id not in (partido.equipos_id_local, partido.equipos_id_visitante):
                raise DomainRuleError("El ganador debe ser uno de los dos equipos que disputan el partido.")
            # Se setea ANTES del Hito: fn_validar_ganador_corrido (BEFORE
            # UPDATE en PARTIDOS) exige Ganador_Corrido_ID no-NULL en el
            # mismo UPDATE que pone Estado='Finalizado', y ese UPDATE lo
            # dispara fn_hito_sincroniza_estado_partido AFTER INSERT del
            # Hito — si el ganador no está seteado antes, el trigger de
            # validación lo rechaza.
            partido = await self.partido_repo.save_changes(partido, ganador_corrido_id=data.ganador_corrido_id)

        if data.tipo_hito == "Fin_Partido" and (
            data.ganador_desempate_id is not None or data.penales_local is not None
        ):
            # Mismo motivo que el ganador_corrido_id de arriba: se setea
            # ANTES del Hito, para que fn_validar_partido_eliminacion_
            # desempate ya lo vea no-NULL si el partido terminó empatado en
            # goles. No se exige acá (a diferencia de Corrido) — el
            # trigger es quien sabe si hacía falta, mismo criterio que
            # PartidoUpdate.ganador_desempate_id.
            #
            # Desempate de eliminatoria: tiempo extra y penales (D-D1 — el
            # paso de tanda entra en fase 2 también acá, en el cronómetro
            # EN VIVO). Si vino la tanda, el ganador se DERIVA de ella
            # siempre (D-D4: nunca del cliente — una tanda cargada al
            # revés en una vuelta, cuyo encabezado muestra el GLOBAL con
            # localía cruzada, avanzaría al equipo equivocado si se
            # confiara en el `ganador_desempate_id` que mandó el cliente).
            # Si no vino tanda, es el radio manual de siempre — se completa
            # `metodo_desempate='Manual'` (SPEC-REVIEW F1): ese camino no
            # sabe mandarlo, y sin este default la migración 33 lo rechaza
            # con `desempate_sin_metodo`.
            ganador_desempate_id = data.ganador_desempate_id
            metodo_desempate = data.metodo_desempate
            if data.penales_local is not None:
                ganador_desempate_id = derivar_ganador_desde_penales(
                    data.penales_local, data.penales_visitante,
                    partido.equipos_id_local, partido.equipos_id_visitante,
                )
                metodo_desempate = "Penales"
            else:
                metodo_desempate = completar_metodo_manual(ganador_desempate_id, metodo_desempate)
            if es_escape_manual_sobre_metodo_configurado(metodo_desempate, partido.metodo_desempate_aplicable):
                # D-A1/métrica 3 (§12-bis): cierre Manual sobre un torneo
                # configurado de otra forma — permitido a propósito, pero
                # logueado.
                registrar_evento(
                    "desempate_manual_sobre_metodo_configurado",
                    partido_id=partido.id,
                    torneo_id=partido.torneo_id,
                    metodo_aplicable=partido.metodo_desempate_aplicable,
                    camino="vivo",
                )
            partido = await self.partido_repo.save_changes(
                partido,
                ganador_desempate_id=ganador_desempate_id,
                metodo_desempate=metodo_desempate,
                penales_local=data.penales_local,
                penales_visitante=data.penales_visitante,
            )

        hito = await self.repo.create(
            partido_id=partido_id,
            tipo_hito=data.tipo_hito,
            numero_periodo=numero_periodo,
            minuto_reloj=data.minuto_reloj,
            registrado_por=usuario_actual.id,
        )
        return HitoPartidoOut.model_validate(hito)

    async def _registrar_fin_forzado(
        self,
        partido: Partido,
        config: ConfiguracionTiempoTorneo,
        estado: dict,
        data: HitoPartidoCreate,
        usuario_actual: Usuario,
    ) -> HitoPartidoOut:
        """Área 4 (T6): "Fin de Partido forzado" — override global,
        permitido desde CUALQUIER `acciones_permitidas` (a diferencia del
        Fin_Partido normal, gateado por `_calcular_estado`) mientras el
        partido esté iniciado y no finalizado. El único estado "imposible"
        que se sigue rechazando: doble Fin_Partido (normal+forzado, o
        forzado dos veces) — `estado["partido_finalizado"]` lo corta acá en
        el caso no-concurrente; el índice único parcial
        `uq_hitos_partido_fin_unico` (T15, 03_indexes.sql) es la defensa de
        fondo contra 2 requests concurrentes (TOCTOU).

        Corrección de diseño de Eng Fase 3 (supera la decisión inicial de
        "commit diferido 100% cliente" de la Fase 1): el Hito se inserta DE
        INMEDIATO — dispara la misma cascada que un cierre normal
        (`trg_hito_sincroniza_estado`, `fn_propagar_ganador_bracket`) en la
        misma transacción. La ventana de 5s que ve el operador es una
        ventana de DESHACER real y autoritativa en el SERVIDOR (ver
        `deshacer_fin_forzado`), no un envío retrasado: así el cierre queda
        firme aunque el dispositivo del operador se apague en medio de la
        ventana — exactamente el escenario (clima, incidente) que esta
        feature dice cubrir, y que un commit diferido del lado del cliente
        NO protegía (el partido nunca se cerraba si el dispositivo fallaba
        antes de los 5s)."""
        if not estado["partido_iniciado"]:
            raise DomainRuleError("El partido todavía no arrancó — no se puede forzar el cierre.")
        if estado["partido_finalizado"]:
            raise DomainRuleError("El partido ya está finalizado.")

        if config.tipo_cronometro == "Corrido":
            # Mismo requisito que un Fin_Partido normal de un torneo
            # Corrido (Tenis/Pádel): fn_validar_ganador_corrido (BEFORE
            # UPDATE en PARTIDOS) exige Ganador_Corrido_ID no-NULL en el
            # mismo UPDATE que este Hito va a disparar hacia
            # Estado='Finalizado' — un cierre forzado no es una excepción
            # a esa integridad de datos, solo salta el gate de
            # `acciones_permitidas`. El frontend reusa el mismo paso
            # "¿Quién ganó?" que ya tiene para el cierre normal.
            if data.ganador_corrido_id is None:
                raise DomainRuleError(
                    "Un partido Corrido necesita el ganador para finalizar, incluso en un cierre forzado."
                )
            if data.ganador_corrido_id not in (partido.equipos_id_local, partido.equipos_id_visitante):
                raise DomainRuleError("El ganador debe ser uno de los dos equipos que disputan el partido.")
            partido = await self.partido_repo.save_changes(partido, ganador_corrido_id=data.ganador_corrido_id)

        if data.ganador_desempate_id is not None or data.penales_local is not None:
            # Mismo criterio exacto que el Fin_Partido normal (SPEC-REVIEW
            # F1/D-D4) — un cierre forzado con empate puede venir con tanda
            # de penales igual que uno normal.
            ganador_desempate_id = data.ganador_desempate_id
            metodo_desempate = data.metodo_desempate
            if data.penales_local is not None:
                ganador_desempate_id = derivar_ganador_desde_penales(
                    data.penales_local, data.penales_visitante,
                    partido.equipos_id_local, partido.equipos_id_visitante,
                )
                metodo_desempate = "Penales"
            else:
                metodo_desempate = completar_metodo_manual(ganador_desempate_id, metodo_desempate)
            if es_escape_manual_sobre_metodo_configurado(metodo_desempate, partido.metodo_desempate_aplicable):
                registrar_evento(
                    "desempate_manual_sobre_metodo_configurado",
                    partido_id=partido.id,
                    torneo_id=partido.torneo_id,
                    metodo_aplicable=partido.metodo_desempate_aplicable,
                    camino="forzado",
                )
            partido = await self.partido_repo.save_changes(
                partido,
                ganador_desempate_id=ganador_desempate_id,
                metodo_desempate=metodo_desempate,
                penales_local=data.penales_local,
                penales_visitante=data.penales_visitante,
            )

        hito = await self.repo.create(
            partido_id=partido.id,
            tipo_hito="Fin_Partido",
            numero_periodo=None,
            minuto_reloj=data.minuto_reloj,
            registrado_por=usuario_actual.id,
            forzado=True,
            motivo_cierre=data.motivo_cierre,
            motivo_cierre_detalle=data.motivo_cierre_detalle,
        )
        salida = HitoPartidoOut.model_validate(hito)
        salida.deshacer_disponible_hasta = hito.timestamp_real + timedelta(seconds=VENTANA_DESHACER_SEGUNDOS)
        return salida

    async def deshacer_fin_forzado(self, partido_id: int, usuario_actual: Usuario) -> DeshacerCierreForzadoOut:
        """POST /partidos/{id}/deshacer-cierre-forzado (T17) — reversión
        atómica de un Fin_Partido forzado, solo dentro de la ventana de
        `VENTANA_DESHACER_SEGUNDOS` contada desde el SERVIDOR (nunca
        confiando en el reloj/timer del cliente — Design Fase 2 solo
        resolvía el caso de navegar DENTRO de la app; esto cierra el caso
        real: el dispositivo deja de responder).

        Tres guardas, en orden (Sección 4/Registro de Modos de Falla de la
        Fase 3):
          1. El último Hito de este partido tiene que ser el Fin_Partido
             forzado que se quiere deshacer — no se puede deshacer "el
             cierre de hace 3 partidos" ni uno normal (no forzado).
          2. La ventana server-side no expiró.
          3. Si hubo propagación de bracket (Partido_Siguiente_ID /
             Partido_Perdedor_Siguiente_ID), el próximo partido todavía no
             tiene ningún Hito propio — si el rival ya empezó a operarlo,
             deshacer acá dejaría datos huérfanos del otro lado.

        Revierte en una sola transacción: borra el Hito, recalcula
        `PARTIDOS.Estado` desde los Hitos que quedan (reusa
        `_calcular_estado` — nunca un valor hardcodeado, mismo principio
        que el resto del servicio) y limpia el slot que la propagación
        hubiera escrito en el/los partido(s) siguientes."""
        partido = await self.partido_repo.get_or_404(partido_id)
        verificar_arbitro_asignado(partido, usuario_actual)

        ultimo = await self.repo.ultimo_hito(partido_id)
        if ultimo is None or ultimo.tipo_hito != "Fin_Partido" or not ultimo.forzado:
            raise DomainRuleError("No hay un cierre forzado reciente para deshacer en este partido.")

        limite = ultimo.timestamp_real + timedelta(seconds=VENTANA_DESHACER_SEGUNDOS)
        if datetime.now() > limite:
            raise DomainRuleError("La ventana para deshacer este cierre ya expiró.")

        for siguiente_id in (partido.partido_siguiente_id, partido.partido_perdedor_siguiente_id):
            if siguiente_id is None:
                continue
            hitos_siguiente = await self.repo.listar_por_partido(siguiente_id)
            if hitos_siguiente:
                raise DomainRuleError(
                    "Ya no se puede deshacer: el próximo partido del bracket ya tiene actividad propia."
                )

        # Revierte la propagación ANTES de borrar el Hito (mismo criterio de
        # orden que registrar_resultado_directo: cada paso con flush(),
        # commit único al final — si algo falla acá, nada de esto queda a
        # medias). Solo limpia el slot que ESTE partido pudo haber escrito
        # — nunca toca el otro slot del partido siguiente (el que llena la
        # otra rama del bracket).
        if partido.partido_siguiente_id is not None:
            siguiente = await self.partido_repo.get_or_404(partido.partido_siguiente_id)
            if partido.slot_siguiente == "Local":
                siguiente.equipos_id_local = None
            elif partido.slot_siguiente == "Visitante":
                siguiente.equipos_id_visitante = None
        if partido.partido_perdedor_siguiente_id is not None:
            perdedor_siguiente = await self.partido_repo.get_or_404(partido.partido_perdedor_siguiente_id)
            if partido.slot_perdedor_siguiente == "Local":
                perdedor_siguiente.equipos_id_local = None
            elif partido.slot_perdedor_siguiente == "Visitante":
                perdedor_siguiente.equipos_id_visitante = None
        await self.session.flush()

        await self.session.delete(ultimo)
        await self.session.flush()

        hitos_restantes = await self.repo.listar_por_partido(partido_id)
        config = await self.config_repo.get_by_torneo(partido.torneo_id)
        estado = self._calcular_estado(hitos_restantes, config)
        partido.estado = "Finalizado" if estado["partido_finalizado"] else "En curso"
        # SPEC-REVIEW S2: deshacer_fin_forzado ya limpiaba Ganador_Corrido_ID
        # implícitamente (nunca lo tocó, se recalcula solo al re-cerrar) pero
        # NO limpiaba Ganador_Desempate_ID — un partido deshecho volvía a
        # 'En curso' arrastrando una tanda de penales que ya no decidió
        # nada. Las cinco columnas de desempate se limpian acá.
        partido.metodo_desempate = None
        partido.penales_local = None
        partido.penales_visitante = None
        partido.ganador_desempate_id = None
        partido.hubo_tiempo_extra = False
        await self.session.commit()
        await self.session.refresh(partido)

        return DeshacerCierreForzadoOut(partido_id=partido.id, estado=partido.estado)

    async def corregir(
        self, partido_id: int, hito_id: int, data: HitoPartidoUpdate, usuario_actual: Usuario
    ) -> HitoPartidoOut:
        """Corrección de Minuto_Reloj/Timestamp_Real de un hito ya
        registrado (Flujo 5: "presioné Fin del 1er Tiempo tarde/temprano")
        — UPDATE directo, sin restricción de estado del partido. Queda
        auditado por el listener genérico de AUDITORIA, no hace falta un
        mecanismo propio (ver el comentario grande en 01_schema.sql)."""
        partido = await self.partido_repo.get_or_404(partido_id)
        verificar_arbitro_asignado(partido, usuario_actual)

        hito = await self.repo.get_or_404(hito_id)
        if hito.partido_id != partido_id:
            raise DomainRuleError("Ese hito no pertenece a este partido.")

        cambios = data.model_dump(exclude_unset=True)
        hito = await self.repo.save_changes(hito, **cambios)
        return HitoPartidoOut.model_validate(hito)
