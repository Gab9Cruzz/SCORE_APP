from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.repositories.grupo import GrupoRepository
from app.schemas.grupo import GrupoEquipoOrdenManualUpdate, GrupoEquipoOut, GrupoOut
from app.services.grupo_equipo import GrupoEquipoService

# Motor de Formatos (motor-formatos-plantillas-navegacion-plan.md,
# requerimiento #4) — solo lectura, público (mismo criterio que
# /estadisticas): nombres de grupo ("A", "B", "C"...) para la tabla de
# posiciones por grupo (EC-54) y cualquier otra pantalla que necesite
# mostrarlos. Los grupos en sí los arma MotorFormatosService al sortear,
# no se crean/editan a mano — la única excepción es el desempate manual de
# más abajo (3A-12), que no toca el sorteo, solo un campo de la fila ya
# sorteada.
router = APIRouter(prefix="/grupos", tags=["Motor de Formatos"])


@router.get("", response_model=list[GrupoOut])
async def listar_grupos(fase_id: int, session: AsyncSession = Depends(get_db)) -> list[GrupoOut]:
    grupos = await GrupoRepository(session).listar_por_fase(fase_id)
    return [GrupoOut.model_validate(g) for g in grupos]


@router.patch(
    "/equipos/{grupo_equipo_id}",
    response_model=GrupoEquipoOut,
    dependencies=[Depends(require_roles("TorneoAdmin"))],
)
async def definir_orden_manual(
    grupo_equipo_id: int,
    data: GrupoEquipoOrdenManualUpdate,
    session: AsyncSession = Depends(get_db),
) -> GrupoEquipoOut:
    """Desempate manual en la tabla de posiciones (3A-12, EC-51 de
    motor-formatos-plantillas-navegacion-plan.md): `orden_manual=null`
    saca el override y vuelve al orden automático (PTS/DG/GF) —
    vw_tabla_posiciones lo aplica como desempate de ÚLTIMA instancia,
    nunca puede promover a un equipo por encima de otro con más puntos."""
    grupo_equipo = await GrupoEquipoService(session).set_orden_manual(grupo_equipo_id, data)
    return GrupoEquipoOut.model_validate(grupo_equipo)
