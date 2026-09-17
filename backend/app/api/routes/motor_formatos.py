from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles, require_torneo_access, verificar_torneo_visible
from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.fase import FaseOut
from app.schemas.motor_formatos import CerrarTorneoRequest, EstadoFaseOut, PlayoffsRequest, SorteoRequest
from app.schemas.partido import PartidoOut
from app.schemas.torneo import TorneoOut
from app.services.motor_formatos import MotorFormatosService
from app.services.torneo import TorneoService

# Motor de Formatos de Competición (motor-formatos-plantillas-navegacion-
# plan.md, requerimiento #4) — Generar Fixture (Liga), Hacer Sorteo
# (Eliminación / asignación de Grupos), Generar Playoffs (cruce desde
# Grupos) y la vista de bracket, todo scoped a UN torneo puntual.
router = APIRouter(prefix="/torneos", tags=["Motor de Formatos"])


@router.post(
    "/{torneo_id}/fixture",
    response_model=FaseOut,
    dependencies=[Depends(require_roles("TorneoAdmin")), Depends(require_torneo_access())],
)
async def generar_fixture(torneo_id: int, session: AsyncSession = Depends(get_db)) -> FaseOut:
    """Formato Liga: todos contra todos (ida y vuelta si el torneo lo
    pide), método del círculo — T34/T35."""
    fase = await MotorFormatosService(session).generar_fixture(torneo_id)
    return FaseOut.model_validate(fase)


@router.post(
    "/{torneo_id}/sorteo",
    response_model=FaseOut,
    dependencies=[Depends(require_roles("TorneoAdmin")), Depends(require_torneo_access())],
)
async def sortear(
    torneo_id: int,
    data: SorteoRequest,
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
) -> FaseOut:
    """Formato Eliminación: sortea el bracket completo (con Tercer Lugar
    si aplica). Formato Grupos + Playoffs: sortea los grupos y genera el
    round robin de cada uno — T36/T39/T43/T44/T47/T50."""
    fase = await MotorFormatosService(session).sortear(torneo_id, usuario_actual.id, semilla=data.semilla)
    return FaseOut.model_validate(fase)


@router.post(
    "/{torneo_id}/playoffs",
    response_model=FaseOut,
    dependencies=[Depends(require_roles("TorneoAdmin")), Depends(require_torneo_access())],
)
async def generar_playoffs(
    torneo_id: int,
    data: PlayoffsRequest = PlayoffsRequest(),
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
) -> FaseOut:
    """Solo Grupos + Playoffs, y solo cuando la Fase de Grupos ya terminó:
    cruza los clasificados de cada grupo (1°A-2°B...) y sortea el bracket
    de la fase eliminatoria — T42/T51. `data.clasificados_por_grupo`
    (control-mesa-reactividad-playoffs-plan.md, Fase 3 §6): opcional,
    default None = usa el config del torneo sin cambios."""
    fase = await MotorFormatosService(session).generar_playoffs(
        torneo_id,
        usuario_actual.id,
        clasificados_por_grupo=data.clasificados_por_grupo,
        formato_eliminatoria=data.formato_eliminatoria,
    )
    return FaseOut.model_validate(fase)


@router.get(
    "/{torneo_id}/bracket",
    response_model=list[PartidoOut],
    dependencies=[Depends(verificar_torneo_visible)],
)
async def bracket(torneo_id: int, session: AsyncSession = Depends(get_db)) -> list[PartidoOut]:
    """Solo lectura, público (mismo criterio que /estadisticas) — T46.

    Gateado por Publicado (portal-publico-feed-partidos-plan.md, C18/E-B3a):
    sin esto, el bracket completo de un torneo borrador seguía siendo
    enumerable por un anónimo aunque el detalle del torneo ya 404eara."""
    partidos = await MotorFormatosService(session).bracket(torneo_id)
    return [PartidoOut.model_validate(p) for p in partidos]


@router.get(
    "/{torneo_id}/estado-fase",
    response_model=EstadoFaseOut,
    dependencies=[Depends(require_roles("TorneoAdmin")), Depends(require_torneo_access())],
)
async def estado_fase(torneo_id: int, session: AsyncSession = Depends(get_db)) -> EstadoFaseOut:
    """C4 (cierre-fase-regular-llaves-playoffs-plan.md): fuente única de
    "¿la fase terminó y qué se puede hacer ahora?" — no público (a
    diferencia de /bracket): informa qué botones de administración
    mostrar, no un dato de audiencia."""
    estado = await MotorFormatosService(session).estado_fase(torneo_id)
    return EstadoFaseOut.model_validate(estado)


@router.post(
    "/{torneo_id}/cerrar",
    response_model=TorneoOut,
    dependencies=[Depends(require_roles("TorneoAdmin")), Depends(require_torneo_access())],
)
async def cerrar_torneo(
    torneo_id: int,
    data: CerrarTorneoRequest = CerrarTorneoRequest(),
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
) -> TorneoOut:
    """Cierre de fase regular (C3): resuelve y persiste el podio. 400 si
    el torneo ya está cerrado, si la fase actual no está completa, si es
    de tipo Grupos (Opción A no existe ahí), o si hay un empate en el
    podio sin `orden_podio`."""
    await MotorFormatosService(session).cerrar_torneo(torneo_id, usuario_actual.id, orden_podio=data.orden_podio)
    return await TorneoService(session).get(torneo_id)


@router.post(
    "/{torneo_id}/reabrir",
    response_model=TorneoOut,
    dependencies=[Depends(require_roles("TorneoAdmin")), Depends(require_torneo_access())],
)
async def reabrir_torneo(
    torneo_id: int,
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
) -> TorneoOut:
    """Finding 4 / T3: reversa un cierre — limpia el podio y devuelve el
    torneo/fase a en curso. 400 si el torneo no está cerrado."""
    await MotorFormatosService(session).reabrir_torneo(torneo_id, usuario_actual.id)
    return await TorneoService(session).get(torneo_id)
