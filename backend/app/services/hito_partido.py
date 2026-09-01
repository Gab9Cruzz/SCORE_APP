from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.errors import DomainRuleError
from app.models.configuracion_tiempo_torneo import ConfiguracionTiempoTorneo
from app.models.hito_partido import HitoPartido
from app.models.partido import Partido
from app.models.usuario import Usuario
from app.repositories.configuracion_tiempo_torneo import ConfiguracionTiempoTorneoRepository
from app.repositories.hito_partido import HitoPartidoRepository
from app.repositories.partido import PartidoRepository
from app.schemas.hito_partido import EstadoCronometroOut, HitoPartidoCreate, HitoPartidoOut, HitoPartidoUpdate
from app.services.permisos import verificar_arbitro_asignado


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

    async def registrar(self, partido_id: int, data: HitoPartidoCreate, usuario_actual: Usuario) -> HitoPartidoOut:
        partido, config, hitos = await self._cargar_contexto(partido_id)
        verificar_arbitro_asignado(partido, usuario_actual)

        estado = self._calcular_estado(hitos, config)
        if data.tipo_hito not in estado["acciones_permitidas"]:
            raise DomainRuleError(
                f"No se puede registrar '{data.tipo_hito}' en el estado actual del partido "
                f"(hitos válidos ahora: {', '.join(estado['acciones_permitidas']) or 'ninguno'})."
            )

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

        hito = await self.repo.create(
            partido_id=partido_id,
            tipo_hito=data.tipo_hito,
            numero_periodo=numero_periodo,
            minuto_reloj=data.minuto_reloj,
            registrado_por=usuario_actual.id,
        )
        return HitoPartidoOut.model_validate(hito)

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
