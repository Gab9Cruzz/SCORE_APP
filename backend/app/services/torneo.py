from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.errors import DomainRuleError
from app.models.configuracion_tiempo_torneo import ConfiguracionTiempoTorneo
from app.models.fase import Fase
from app.models.partido import Partido
from app.models.torneo import Torneo
from app.models.torneo_grupo import TorneoGrupo
from app.repositories.configuracion_tiempo_torneo import ConfiguracionTiempoTorneoRepository
from app.repositories.fase import FaseRepository
from app.repositories.modalidad import ModalidadRepository
from app.repositories.torneo import TorneoRepository
from app.repositories.torneo_grupo import TorneoGrupoRepository
from app.schemas.configuracion_tiempo_torneo import ConfiguracionTiempoTorneoCreate, ConfiguracionTiempoTorneoOut
from app.schemas.torneo import TorneoCreate, TorneoOut, TorneoUpdate

# Motor de Formatos (motor-formatos-plantillas-navegacion-plan.md,
# requerimiento #4) — Decisión G1: Liga/Eliminación son 1 sola FASE;
# Grupos + Playoffs arranca con la FASE de Grupos, la de Eliminación
# ("Eliminatoria") la crea recién MotorFormatosService.generar_playoffs.
_TIPO_FASE_INICIAL = {"Liga": "Liga", "Eliminacion": "Eliminacion", "Grupos_Playoffs": "Grupos"}
_NOMBRE_FASE_INICIAL = {"Liga": "Liga Regular", "Eliminacion": "Eliminatoria", "Grupos_Playoffs": "Fase de Grupos"}

# Motor de Tiempos (gestion-avanzada-equipos-control-mesa-plan.md) — default
# cuando el cliente no manda config_tiempo al crear un torneo. El propio
# requerimiento dice que el mismo deporte puede jugarse con duraciones
# distintas según el nivel, así que esto es solo un punto de partida
# editable, no una regla rígida ligada a la disciplina.
_DEFAULT_PERIODOS = {
    "tipo_cronometro": "Periodos",
    "cantidad_periodos": 2,
    "duracion_periodo_minutos": 45,
    "duracion_descanso_minutos": 15,
}
_DEFAULT_CORRIDO = {
    "tipo_cronometro": "Corrido",
    "cantidad_periodos": None,
    "duracion_periodo_minutos": None,
    "duracion_descanso_minutos": None,
}


class TorneoService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = TorneoRepository(session)
        self.grupo_repo = TorneoGrupoRepository(session)
        self.fase_repo = FaseRepository(session)
        self.modalidad_repo = ModalidadRepository(session)
        self.config_tiempo_repo = ConfiguracionTiempoTorneoRepository(session)

    async def get(self, id_: int) -> TorneoOut:
        return await self._con_config_tiempo(await self.repo.get_or_404(id_))

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        estado: str | None = None,
        torneo_grupo_id: int | None = None,
    ) -> list[TorneoOut]:
        torneos = await self.repo.list(skip=skip, limit=limit, estado=estado, torneo_grupo_id=torneo_grupo_id)
        configs = await self._configs_por_torneo([t.id for t in torneos])
        return [self._a_salida(t, configs.get(t.id)) for t in torneos]

    async def create(self, data: TorneoCreate) -> TorneoOut:
        """Resuelve el grupo ANTES de crear la edición
        (torneos-admin-plan.md, Fase 1/3 — TorneoCreate.exactamente_un_origen_de_grupo
        ya garantiza que vino uno solo de los dos):

        - `torneo_grupo_nombre` -> crea un TORNEO_GRUPO nuevo, Edición 1.
          disciplina_id/modalidad_id vienen del cliente (obligatorios acá,
          TorneoCreate.disciplina_modalidad_requeridas_si_grupo_nuevo).
        - `torneo_grupo_id` -> edición nueva de un grupo YA existente;
          numero_edicion se calcula bajo un advisory lock (EC-21: dos
          admins creando "Edición 3" del mismo grupo a la vez no deben
          poder leer el mismo MAX() y chocar contra unique_edicion_por_grupo
          sin enterarse de por qué — mismo mecanismo que
          JugadorEquipoRepository.lock_exclusividad_torneo, serializa la
          carrera en vez de reaccionar a ella después del INSERT fallido).
          disciplina_id/modalidad_id se HEREDAN de la edición más reciente
          del grupo — lo que mande el cliente en esos dos campos se
          descarta sin más (D-Eng-5/EC-26 de
          ediciones-catalogo-disciplinas-plan.md): un "Nueva edición" con
          disciplina distinta a la del grupo no es un error a rechazar,
          es un campo que ya no se le hace caso al cliente, ni siquiera
          vía un curl directo.

        Motor de Formatos (requerimiento #4): valida que los parámetros
        (Ida_Vuelta/Equipos_Por_Grupo/Clasificados_Por_Grupo) sean
        coherentes con el Formato elegido (T33 — 400 con mensaje claro, no
        el 409 genérico de un CHECK de Postgres), y crea la FASE #1 del
        torneo automáticamente — todo torneo nace con al menos una FASE,
        tanto si el admin usa el motor nuevo como si sigue de alta manual
        (POST /partidos, ver comentario grande en 01_schema.sql sobre esa
        convivencia).

        Motor de Tiempos (gestion-avanzada-equipos-control-mesa-plan.md):
        todo torneo nace también con una CONFIGURACION_TIEMPO_TORNEO —
        la que mande el cliente (`config_tiempo`) o, si no manda nada, un
        default derivado de Modalidad.tamano_equipo (mismo patrón que la
        FASE inicial: se crea sola, no hay que pedirla aparte).
        """
        self._validar_parametros_formato(
            data.formato, data.ida_vuelta, data.equipos_por_grupo, data.clasificados_por_grupo
        )
        datos = data.model_dump(exclude={"torneo_grupo_nombre", "config_tiempo"})

        if data.torneo_grupo_nombre:
            grupo = TorneoGrupo(nombre=data.torneo_grupo_nombre.strip())
            self.session.add(grupo)
            await self.session.flush()  # asigna grupo.id sin comprometer la transacción
            datos["torneo_grupo_id"] = grupo.id
            datos["numero_edicion"] = 1
        else:
            grupo = await self.grupo_repo.get_or_404(data.torneo_grupo_id)  # 404 claro si el id no existe
            await self.grupo_repo.lock_numero_edicion(data.torneo_grupo_id)
            datos["numero_edicion"] = await self.grupo_repo.siguiente_numero_edicion(data.torneo_grupo_id)

            ediciones_previas = await self.repo.listar_ediciones_del_grupo(data.torneo_grupo_id)
            if ediciones_previas:
                edicion_referencia = ediciones_previas[0]  # la más reciente
                datos["disciplina_id"] = edicion_referencia.disciplina_id
                datos["modalidad_id"] = edicion_referencia.modalidad_id

        # Nombre compuesto si el cliente no mandó uno propio (Decision
        # Audit Trail #3 del plan) — así Torneo.nombre nunca queda vacío
        # para quien lo lea directo (reportes, listados que todavía no
        # migraron a componer grupo+edición del lado de la UI).
        if not datos.get("nombre"):
            datos["nombre"] = f"{grupo.nombre} - Edición {datos['numero_edicion']}"

        torneo = await self.repo.create(**datos)
        await self._crear_fase_inicial(torneo)
        config = await self._crear_config_tiempo_inicial(torneo, data.config_tiempo)
        return self._a_salida(torneo, config)

    def _validar_parametros_formato(
        self,
        formato: str,
        ida_vuelta: bool,
        equipos_por_grupo: int | None,
        clasificados_por_grupo: int | None,
    ) -> None:
        """T33: parámetros que no aplican al Formato elegido → 400 con
        mensaje claro. Design sección E del plan: el selector de Formato
        muestra solo los campos que aplican, pero la API es la frontera de
        confianza real (mismo criterio que el resto del módulo)."""
        if formato != "Liga" and ida_vuelta:
            raise DomainRuleError(f"Ida y vuelta no aplica a Formato {formato}.")
        if formato != "Grupos_Playoffs" and (equipos_por_grupo is not None or clasificados_por_grupo is not None):
            raise DomainRuleError(
                f"Equipos por grupo y Clasificados por grupo no aplican a Formato {formato} "
                "— son parámetros exclusivos de Grupos + Playoffs."
            )

    async def _crear_fase_inicial(self, torneo: Torneo) -> None:
        fase = Fase(
            torneo_id=torneo.id,
            nombre=_NOMBRE_FASE_INICIAL[torneo.formato],
            tipo=_TIPO_FASE_INICIAL[torneo.formato],
            orden=1,
            estado="Pendiente",
        )
        self.session.add(fase)
        await self.session.commit()

    async def _crear_config_tiempo_inicial(
        self, torneo: Torneo, config_tiempo: ConfiguracionTiempoTorneoCreate | None
    ) -> ConfiguracionTiempoTorneo:
        if config_tiempo is not None:
            datos = config_tiempo.model_dump()
        else:
            modalidad = await self.modalidad_repo.get_or_404(torneo.modalidad_id)
            datos = dict(_DEFAULT_CORRIDO if modalidad.tamano_equipo == 1 else _DEFAULT_PERIODOS)
        config = await self.config_tiempo_repo.create(torneo_id=torneo.id, **datos)
        return config

    async def update(self, id_: int, data: TorneoUpdate) -> TorneoOut:
        payload = data.model_dump(exclude_unset=True, exclude={"config_tiempo"})
        torneo_actual = await self.repo.get_or_404(id_)

        if "formato" in payload and payload["formato"] != torneo_actual.formato:
            # EC-55: cambiar Formato con PARTIDOS ya creados se bloquea —
            # mismo criterio que EC-38 (bloquear cambio de disciplina de un
            # equipo con inscripciones).
            result = await self.session.execute(select(Partido.id).where(Partido.torneo_id == id_).limit(1))
            if result.first() is not None:
                raise DomainRuleError("No se puede cambiar el Formato de un torneo que ya tiene partidos.")

        if any(campo in payload for campo in ("formato", "ida_vuelta", "equipos_por_grupo", "clasificados_por_grupo")):
            self._validar_parametros_formato(
                payload.get("formato", torneo_actual.formato),
                payload.get("ida_vuelta", torneo_actual.ida_vuelta),
                payload.get("equipos_por_grupo", torneo_actual.equipos_por_grupo),
                payload.get("clasificados_por_grupo", torneo_actual.clasificados_por_grupo),
            )

        torneo = await self.repo.save_changes(torneo_actual, **payload)

        config = await self.config_tiempo_repo.get_by_torneo(id_)
        if data.config_tiempo is not None:
            # EC-13 del plan: se permite el PATCH en cualquier momento, no
            # hay trigger que lo impida — los hitos ya guardados no se
            # re-validan retroactivamente (limitación conocida, documentada
            # en el plan, no defendida por trigger).
            datos_config = data.config_tiempo.model_dump()
            if config is None:
                config = await self.config_tiempo_repo.create(torneo_id=id_, **datos_config)
            else:
                config = await self.config_tiempo_repo.reemplazar(config, **datos_config)

        return self._a_salida(torneo, config)

    async def soft_delete(self, id_: int) -> TorneoOut:
        torneo = await self.repo.soft_delete(id_, estado_inactivo="Inactivo")
        return await self._con_config_tiempo(torneo)

    async def _con_config_tiempo(self, torneo: Torneo) -> TorneoOut:
        config = await self.config_tiempo_repo.get_by_torneo(torneo.id)
        return self._a_salida(torneo, config)

    async def _configs_por_torneo(self, torneo_ids: list[int]) -> dict[int, ConfiguracionTiempoTorneo]:
        if not torneo_ids:
            return {}
        stmt = select(ConfiguracionTiempoTorneo).where(ConfiguracionTiempoTorneo.torneo_id.in_(torneo_ids))
        result = await self.session.execute(stmt)
        return {c.torneo_id: c for c in result.scalars().all()}

    @staticmethod
    def _a_salida(torneo: Torneo, config: ConfiguracionTiempoTorneo | None) -> TorneoOut:
        salida = TorneoOut.model_validate(torneo)
        salida.config_tiempo = ConfiguracionTiempoTorneoOut.model_validate(config) if config else None
        return salida
