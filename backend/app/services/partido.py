from collections.abc import Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metricas import registrar_evento
from app.exceptions.errors import DomainRuleError
from app.models.evento_partido import EventoPartido
from app.models.hito_partido import HitoPartido
from app.models.partido import Partido
from app.models.usuario import Usuario
from app.repositories.configuracion_tiempo_torneo import ConfiguracionTiempoTorneoRepository
from app.repositories.evento import EventoRepository
from app.repositories.evento_partido import EventoPartidoRepository
from app.repositories.fase import FaseRepository
from app.repositories.partido import PartidoRepository
from app.repositories.torneo import TorneoRepository
from app.repositories.torneo_grupo import TorneoGrupoRepository
from app.schemas.partido import PartidoCreate, PartidoOut, PartidoUpdate, ResultadoDirectoCreate
from app.services.desempate import (
    completar_metodo_manual,
    es_escape_manual_sobre_metodo_configurado,
    resolver_desempate_resultado_directo,
)
from app.services.permisos import verificar_arbitro_asignado
from app.services.reglamento_torneo import ReglamentoTorneo
from app.services.reglas_cambio import validar_reglas_cambio
from app.services.reglas_tarjetas import procesar_doble_amarilla


class PartidoService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PartidoRepository(session)
        self.fase_repo = FaseRepository(session)
        self.torneo_repo = TorneoRepository(session)
        self.config_repo = ConfiguracionTiempoTorneoRepository(session)
        # H7: guard de torneo archivado en registrar_resultado_directo, que
        # inserta el HitoPartido a mano y por eso no pasa por HitoPartidoService.
        self.torneo_grupo_repo = TorneoGrupoRepository(session)
        # goles-por-marcador-slots-plan.md, Fase 3 Eng (corrección 3): repos
        # propios para llamar `validar_reglas_cambio` sin instanciar
        # `EventoPartidoService` — ningún servicio de este repo instancia a
        # otro, mismo patrón que los repos de arriba.
        self.evento_catalogo_repo = EventoRepository(session)
        self.evento_partido_repo = EventoPartidoRepository(session)

    async def get(self, id_: int) -> PartidoOut:
        return await self._a_salida(await self.repo.get_or_404(id_))

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        torneo_id: int | None = None,
        estado: str | None = None,
        arbitro_id: int | None = None,
        torneo_ids_permitidos: Sequence[int] | None = None,
        incluir_archivados: bool = False,
        solo_publicados: bool = False,
    ) -> list[PartidoOut]:
        # arbitro_id (Fase 3, D1): filtro más, mismo mecanismo genérico de
        # BaseRepository.list — no hace falta tocar el repositorio.
        # torneo_ids_permitidos (control-mesa-centralizacion-fixture-plan.md,
        # ítem 1): mismo mecanismo que TorneoService.list/E1 — ver el
        # override en PartidoRepository.list.
        # incluir_archivados (cascada-archivado-alineaciones-traspasos-
        # plan.md): ver PartidoRepository.list — ningún consumidor actual
        # lo pasa `True`.
        # solo_publicados (portal-publico-feed-partidos-plan.md, E-B3a):
        # mismo mecanismo que TorneoService.list — `True` cuando el router
        # resolvió un caller anónimo.
        partidos = await self.repo.list(
            skip=skip,
            limit=limit,
            torneo_id=torneo_id,
            estado=estado,
            arbitro_id=arbitro_id,
            torneo_ids_permitidos=torneo_ids_permitidos,
            incluir_archivados=incluir_archivados,
            solo_publicados=solo_publicados,
        )
        return [await self._a_salida(p) for p in partidos]

    async def create(self, data: PartidoCreate) -> PartidoOut:
        # Nada de validación de negocio acá: quién disputa el partido y si
        # los equipos están inscritos lo valida trg_partidos_validar_inscripcion
        # (06_triggers.sql). El servicio solo pasa los datos; el trigger
        # rechaza con un mensaje en español que exceptions/handlers.py
        # devuelve tal cual como 400.
        return await self._a_salida(await self.repo.create(**data.model_dump()))

    async def update(self, id_: int, data: PartidoUpdate, usuario_actual: Usuario) -> PartidoOut:
        # Árbitro solo puede tocar SU partido asignado (D5/D6,
        # roles-3-modulos-plan.md Fase 1) — carga una vez, chequea, y
        # reusa ese mismo objeto para guardar (save_changes), sin volver
        # a consultarlo.
        partido = await self.repo.get_or_404(id_)
        verificar_arbitro_asignado(partido, usuario_actual)
        payload = data.model_dump(exclude_unset=True)
        # SPEC-REVIEW F1: el PATCH genérico es uno de los cuatro caminos
        # que ya escriben `ganador_desempate_id` hoy sin saber mandar
        # `metodo_desempate` — se completa a 'Manual' para no romper con
        # `desempate_sin_metodo` apenas la migración 33 esté aplicada.
        if "ganador_desempate_id" in payload:
            payload["metodo_desempate"] = completar_metodo_manual(
                payload["ganador_desempate_id"], payload.get("metodo_desempate")
            )
        return await self._a_salida(await self.repo.save_changes(partido, **payload))

    async def soft_delete(self, id_: int) -> PartidoOut:
        return await self._a_salida(await self.repo.soft_delete(id_, estado_inactivo="Cancelado"))

    async def marcar_walkover(self, id_: int, equipo_ausente_id: int, usuario_actual: Usuario) -> PartidoOut:
        """3B-13 (docs/plans/cierre-backlog-todos-plan.md): cierra el
        partido 3-0 a favor del equipo presente por ausencia del otro —
        vw_resultados_partidos aplica el 3-0 (ver Es_Walkover en
        04_views.sql), fn_propagar_ganador_bracket avanza al ganador solo
        con el flag, sin necesitar eventos de gol reales.

        Excepción reconocida a "Hito es la única fuente de verdad de
        Estado" (modo-vivo-sustituciones-cierre-plan.md, Eng Fase 3,
        hallazgo medio #3): este método escribe `estado="Finalizado"`
        directamente vía `save_changes`, sin insertar ningún Hito. Es
        deliberado — un walkover no tiene cronómetro corriendo ni eventos
        que lo justifiquen, y ya tiene sus propios guards completos acá
        mismo (fase de eliminación, o `Permite_Walkover_Grupos`). No se
        unifica con el flujo de Hitos en este plan (fuera de alcance).

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

        return await self._a_salida(await self.repo.save_changes(
            partido, estado="Finalizado", es_walkover=True, walkover_equipo_ausente_id=equipo_ausente_id
        ))

    async def registrar_resultado_directo(
        self, id_: int, data: ResultadoDirectoCreate, usuario_actual: Usuario
    ) -> PartidoOut:
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

        Lock de fila (goles-por-marcador-slots-plan.md, Fase 3 Eng,
        corrección 2): `get_or_404_bloqueado` en vez de `get_or_404` — sin
        esto, 2 requests concurrentes sobre el mismo partido 'Programado'
        (doble-click, o 2 pestañas) podían leer `estado='Programado'` los
        dos antes de que cualquiera hiciera commit, y los dos insertar
        Inicio_Partido+eventos+Fin_Partido. El lock se libera en el
        `commit()`/rollback que este método ya tiene, sin reestructurar la
        transacción.
        """
        partido = await self.repo.get_or_404_bloqueado(id_)
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

        # H7 del plan (gestionar-partido-alineaciones-plan.md): este método
        # inserta el HitoPartido a mano, así que NUNCA pasa por
        # HitoPartidoService.registrar y se salteaba las dos validaciones que
        # ese aplica. La de torneo archivado es un agujero: cargar un resultado
        # en un torneo archivado no tiene lectura legítima.
        #
        # La de titulares NO se agrega, a propósito (D4): este camino existe
        # para partidos que YA se jugaron y se registraron en papel, donde
        # exigir una alineación sería pedir un dato que el operador no tiene.
        #
        # Va acá, ANTES del primer flush(): una vez insertado el Inicio_Partido,
        # trg_hito_sincroniza_estado ya movió PARTIDOS.Estado en la base
        # mientras el objeto Python sigue diciendo 'Programado'
        # (expire_on_commit=False, db/database.py), así que un chequeo posterior
        # leería un estado que no es el real.
        torneo = await self.torneo_repo.get_or_404(partido.torneo_id)
        grupo = await self.torneo_grupo_repo.get_or_404(torneo.torneo_grupo_id)
        if grupo.estado == "Archivado":
            raise DomainRuleError("Este torneo está archivado — reactivalo antes de operar sus partidos.")

        config = await self.config_repo.get_by_torneo(partido.torneo_id)
        if config is None:
            raise DomainRuleError("Este torneo todavía no tiene configuración de tiempos.")
        if config.tipo_cronometro == "Corrido":
            if data.ganador_corrido_id is None:
                raise DomainRuleError("Un partido Corrido necesita el ganador para finalizar.")
            if data.ganador_corrido_id not in (partido.equipos_id_local, partido.equipos_id_visitante):
                raise DomainRuleError("El ganador debe ser uno de los dos equipos que disputan el partido.")

        # Desempate de eliminatoria: tiempo extra y penales (D6/§8) —
        # snapshot de Metodo_Desempate_Aplicable en el momento en que ESTE
        # partido arranca (mismo criterio exacto que HitoPartidoService.
        # _snapshotear_metodo_desempate_aplicable para el camino en vivo,
        # este es el que corresponde a la carga directa: no hay un Hito
        # Inicio_Partido separado que pase por ese servicio).
        if partido.fase_id is not None:
            fase = await self.fase_repo.get(partido.fase_id)
            if fase is not None and fase.tipo == "Eliminacion":
                partido.metodo_desempate_aplicable = ReglamentoTorneo.desde(torneo).resolver_desempate_aplicable(
                    partido.ronda_nombre
                )

        self.session.add(HitoPartido(partido_id=id_, tipo_hito="Inicio_Partido", registrado_por=usuario_actual.id))
        await self.session.flush()

        # control-mesa-reactividad-playoffs-plan.md, Fase 3 §3: resuelto UNA
        # vez fuera del loop (no cambia por evento), igual criterio que
        # `torneo`/`config` arriba — evita una consulta repetida por evento.
        rojas_catalogo = await self.evento_catalogo_repo.list(limit=1, nombre="Tarjeta Roja")
        eventos_id_roja = rojas_catalogo[0].id if rojas_catalogo else None

        for evento in data.eventos:
            # goles-por-marcador-slots-plan.md, Fase 1 (hallazgo 6): antes de
            # esta corrección, este método nunca llamaba nada de
            # `reglas_cambio` — un resultado directo con 10 cambios para un
            # equipo con tope 5 se aceptaba sin aviso. Se valida ANTES del
            # `add()`/`flush()` de este evento, usando los eventos ya
            # flusheados en vueltas anteriores del mismo loop (visibles acá
            # porque comparten la misma transacción) — si este evento viola
            # una regla, ninguno de los siguientes llega a insertarse y el
            # rollback de `app/db/session.py` deshace los anteriores también.
            evento_catalogo = await self.evento_catalogo_repo.get_or_404(evento.eventos_id)
            await validar_reglas_cambio(
                torneo=torneo,
                evento_catalogo_nombre=evento_catalogo.nombre,
                evento_partido_repo=self.evento_partido_repo,
                partido_id=id_,
                jugador_id=evento.jugador_id,
                jugador_id_entra=evento.jugador_id_entra,
                equipo_id=evento.equipo_id,
                eventos_id=evento.eventos_id,
            )
            self.session.add(EventoPartido(partidos_id=id_, **evento.model_dump()))
            await self.session.flush()

            # Fase 3 §3: listener de doble amarilla — mismo módulo que usa
            # EventoPartidoService.create (camino en vivo), para que la
            # regla no dependa de por cuál pantalla cargó el operador. Se
            # evalúa DESPUÉS del flush de este evento (visible en la misma
            # transacción, igual criterio que validar_reglas_cambio arriba
            # con los eventos de vueltas anteriores del loop).
            if eventos_id_roja is not None and evento_catalogo.nombre == "Tarjeta Amarilla":
                roja_auto = await procesar_doble_amarilla(
                    evento_partido_repo=self.evento_partido_repo,
                    partido_id=id_,
                    jugador_id=evento.jugador_id,
                    equipo_id=evento.equipo_id,
                    eventos_id_amarilla=evento.eventos_id,
                    eventos_id_roja=eventos_id_roja,
                    minuto=evento.minuto,
                )
                if roja_auto is not None:
                    self.session.add(roja_auto)
                    await self.session.flush()

        if config.tipo_cronometro == "Corrido":
            # Antes del Hito Fin_Partido: fn_validar_ganador_corrido exige
            # Ganador_Corrido_ID ya seteado cuando ese Hito dispare (vía
            # trg_hito_sincroniza_estado) el UPDATE a Estado='Finalizado'.
            partido.ganador_corrido_id = data.ganador_corrido_id
            await self.session.flush()

        # Desempate manual (Fase 0, Finding 1) + desempate de eliminatoria:
        # tiempo extra y penales (D-D12/E4, SPEC-REVIEW F9) — mismo motivo
        # que el ganador_corrido_id de arriba: se setea ANTES del Hito
        # Fin_Partido, para que fn_validar_partido_eliminacion_desempate ya
        # lo vea si el partido terminó empatado. Se acepta sin exigirlo
        # (el trigger decide si hacía falta) — mismo criterio de siempre.
        metodo_desempate: str | None
        ganador_desempate_id = data.ganador_desempate_id
        if config.tipo_cronometro == "Corrido":
            # D5/§7: el desempate de eliminatoria (tiempo extra/penales) es
            # solo para disciplinas de gol — acá solo hace falta completar
            # el default 'Manual' si vino un ganador_desempate_id suelto
            # (SPEC-REVIEW F1).
            metodo_desempate = completar_metodo_manual(ganador_desempate_id, None)
        else:
            goles = await self.session.execute(
                text(
                    "SELECT "
                    "COUNT(*) FILTER (WHERE Equipo_Acreditado = :local) AS goles_local, "
                    "COUNT(*) FILTER (WHERE Equipo_Acreditado = :visitante) AS goles_visitante "
                    "FROM vw_goles_acreditados WHERE PARTIDOS_ID = :partido_id"
                ),
                {"local": partido.equipos_id_local, "visitante": partido.equipos_id_visitante, "partido_id": id_},
            )
            fila = goles.one()
            metodo_desempate, ganador_desempate_id = resolver_desempate_resultado_directo(
                ganador_desempate_id=data.ganador_desempate_id,
                penales_local=data.penales_local,
                penales_visitante=data.penales_visitante,
                hubo_tiempo_extra=data.hubo_tiempo_extra,
                equipo_local_id=partido.equipos_id_local,
                equipo_visitante_id=partido.equipos_id_visitante,
                goles_local=fila.goles_local,
                goles_visitante=fila.goles_visitante,
            )

        if (
            ganador_desempate_id is not None
            or metodo_desempate is not None
            or data.penales_local is not None
            or data.hubo_tiempo_extra
        ):
            if es_escape_manual_sobre_metodo_configurado(metodo_desempate, partido.metodo_desempate_aplicable):
                registrar_evento(
                    "desempate_manual_sobre_metodo_configurado",
                    partido_id=partido.id,
                    torneo_id=partido.torneo_id,
                    metodo_aplicable=partido.metodo_desempate_aplicable,
                    camino="carga_directa",
                )
            partido.ganador_desempate_id = ganador_desempate_id
            partido.metodo_desempate = metodo_desempate
            partido.penales_local = data.penales_local
            partido.penales_visitante = data.penales_visitante
            partido.hubo_tiempo_extra = data.hubo_tiempo_extra
            await self.session.flush()

        self.session.add(HitoPartido(partido_id=id_, tipo_hito="Fin_Partido", registrado_por=usuario_actual.id))
        await self.session.flush()

        await self.session.commit()
        await self.session.refresh(partido)
        return await self._a_salida(partido)

    async def _a_salida(self, partido: Partido) -> PartidoOut:
        """Fase 1 (sin migración) del plan de desempate de eliminatoria —
        SPEC-REVIEW S12/D-Q2: reemplaza las dos derivaciones de cliente
        divergentes (`MesaPanel.tsx:290` no excluía Corrido/ida;
        `ModalResultadoDirecto.tsx:420` sí excluía Corrido) con un único
        cálculo del servidor. Ver el docstring de `PartidoOut.elegible_desempate`
        (schemas/partido.py) para la semántica exacta — no es el booleano
        final, es la parte estructural más los goles ya jugados de la ida
        cuando corresponde, para que el cliente arme el global sumando su
        propio marcador (en vivo, o un draft de resultado directo todavía
        sin guardar)."""
        salida = PartidoOut.model_validate(partido)
        if partido.fase_id is None or partido.es_walkover:
            return salida

        fase = await self.fase_repo.get(partido.fase_id)
        if fase is None or fase.tipo != "Eliminacion":
            return salida

        es_ida = await self.repo.list(partido_ida_id=partido.id, limit=1)
        if es_ida:
            return salida  # D4/§6: una ida nunca es elegible para desempate.

        config = await self.config_repo.get_by_torneo(partido.torneo_id)
        if config is not None and config.tipo_cronometro == "Corrido":
            return salida  # D5/§7: solo disciplinas de gol.

        salida.elegible_desempate = True

        if partido.partido_ida_id is not None:
            ida = await self.repo.get(partido.partido_ida_id)
            if ida is not None:
                goles = await self.session.execute(
                    text(
                        "SELECT "
                        "COUNT(*) FILTER (WHERE Equipo_Acreditado = :ida_visitante) AS previos_local, "
                        "COUNT(*) FILTER (WHERE Equipo_Acreditado = :ida_local) AS previos_visitante "
                        "FROM vw_goles_acreditados WHERE PARTIDOS_ID = :ida_id"
                    ),
                    {
                        "ida_visitante": ida.equipos_id_visitante,
                        "ida_local": ida.equipos_id_local,
                        "ida_id": ida.id,
                    },
                )
                fila = goles.one()
                # fn_resolver_llave invierte la ida: el LOCAL de la ida
                # juega de VISITANTE en la vuelta y viceversa — los goles
                # ya jugados se cruzan acá para que salgan expresados en la
                # orientación local/visitante de ESTE partido (la vuelta).
                salida.goles_previos_global_local = fila.previos_local
                salida.goles_previos_global_visitante = fila.previos_visitante

        return salida
