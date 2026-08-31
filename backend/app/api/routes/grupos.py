from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.grupo import GrupoRepository
from app.schemas.grupo import GrupoOut

# Motor de Formatos (motor-formatos-plantillas-navegacion-plan.md,
# requerimiento #4) — solo lectura, público (mismo criterio que
# /estadisticas): nombres de grupo ("A", "B", "C"...) para la tabla de
# posiciones por grupo (EC-54) y cualquier otra pantalla que necesite
# mostrarlos. Sin POST/PATCH: los grupos los arma MotorFormatosService al
# sortear, no se crean/editan a mano.
router = APIRouter(prefix="/grupos", tags=["Motor de Formatos"])


@router.get("", response_model=list[GrupoOut])
async def listar_grupos(fase_id: int, session: AsyncSession = Depends(get_db)) -> list[GrupoOut]:
    grupos = await GrupoRepository(session).listar_por_fase(fase_id)
    return [GrupoOut.model_validate(g) for g in grupos]
