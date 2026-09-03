from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles, require_torneo_access
from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.fase import FaseOut
from app.schemas.motor_formatos import SorteoRequest
from app.schemas.partido import PartidoOut
from app.services.motor_formatos import MotorFormatosService

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
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
) -> FaseOut:
    """Solo Grupos + Playoffs, y solo cuando la Fase de Grupos ya terminó:
    cruza los clasificados de cada grupo (1°A-2°B...) y sortea el bracket
    de la fase eliminatoria — T42/T51."""
    fase = await MotorFormatosService(session).generar_playoffs(torneo_id, usuario_actual.id)
    return FaseOut.model_validate(fase)


@router.get("/{torneo_id}/bracket", response_model=list[PartidoOut])
async def bracket(torneo_id: int, session: AsyncSession = Depends(get_db)) -> list[PartidoOut]:
    """Solo lectura, público (mismo criterio que /estadisticas) — T46."""
    partidos = await MotorFormatosService(session).bracket(torneo_id)
    return [PartidoOut.model_validate(p) for p in partidos]
