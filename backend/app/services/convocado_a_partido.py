from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.errors import DomainRuleError
from app.models.convocado_a_partido import ConvocadoAPartido
from app.models.usuario import Usuario
from app.repositories.convocado_a_partido import ConvocadoAPartidoRepository
from app.repositories.estadisticas import EstadisticasRepository
from app.repositories.partido import PartidoRepository
from app.schemas.convocado_a_partido import ConvocatoriaSetRequest
from app.services.permisos import verificar_arbitro_asignado


class ConvocadoAPartidoService:
    """Titular/suplente/convocados a un partido (3B-2,
    docs/plans/cierre-backlog-todos-plan.md) — dirección técnica del
    plan: tabla delgada, no-autoritativa, no reemplaza JugadorEquipo. El
    único trabajo real de este service es validar que cada convocado
    pertenezca a la plantilla vigente de ALGUNO de los dos equipos que
    disputan ESE partido puntual antes de guardar la lista."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ConvocadoAPartidoRepository(session)
        self.partido_repo = PartidoRepository(session)
        self.estadisticas_repo = EstadisticasRepository(session)

    async def listar(self, partido_id: int) -> list[ConvocadoAPartido]:
        await self.partido_repo.get_or_404(partido_id)
        return await self.repo.listar_por_partido(partido_id)

    async def reemplazar(
        self, partido_id: int, data: ConvocatoriaSetRequest, usuario_actual: Usuario
    ) -> list[ConvocadoAPartido]:
        partido = await self.partido_repo.get_or_404(partido_id)
        # Mismo ownership-check que EventoPartidoService/HitoPartidoService
        # (D5, roles-3-modulos-plan.md) — un Árbitro solo arma la
        # convocatoria de SU partido asignado.
        verificar_arbitro_asignado(partido, usuario_actual)

        if partido.equipos_id_local is None or partido.equipos_id_visitante is None:
            raise DomainRuleError(
                "Este partido todavía no tiene los dos equipos definidos — esperá a que termine "
                "el partido anterior del bracket."
            )

        candidatos_local = await self.estadisticas_repo.plantilla_equipo(partido.equipos_id_local)
        candidatos_visitante = await self.estadisticas_repo.plantilla_equipo(partido.equipos_id_visitante)
        perfiles_validos = {f["jugador_perfil_id"] for f in candidatos_local} | {
            f["jugador_perfil_id"] for f in candidatos_visitante
        }

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

        filas = [(c.jugador_perfil_id, c.titular) for c in data.convocados]
        return await self.repo.reemplazar_convocatoria(partido_id, filas)
