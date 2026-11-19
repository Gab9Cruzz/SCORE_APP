from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.paginacion import informar_total
from app.db.session import get_db
from app.repositories.auditoria import AuditoriaRepository
from app.schemas.auditoria import AccionAuditoria, AuditoriaOut

router = APIRouter(prefix="/auditoria", tags=["Auditoría de cambios"])

# Solo lectura, y solo AdminGeneral — mismo gate y mismo motivo que
# /accesos (routes/accesos.py): no hay POST/PATCH/DELETE porque nadie
# escribe acá a mano, y una bitácora con endpoint de escritura o borrado se
# puede falsificar desde afuera. Acá es incluso más sensible que /accesos:
# expone el detalle de CUALQUIER cambio en CUALQUIER entidad del sistema,
# torneos incluidos, así que un TorneoAdmin no la ve ni recortada.


@router.get("", response_model=list[AuditoriaOut], dependencies=[Depends(require_roles("AdminGeneral"))])
async def listar_auditoria(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    tabla: str | None = None,
    registro_id: int | None = None,
    accion: AccionAuditoria | None = None,
    usuario_id: int | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    *,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> list[AuditoriaOut]:
    """Bitácora de cambios (alta/modificación/baja) de cualquier entidad,
    del más reciente al más antiguo. `desde`/`hasta` son días completos.
    """
    filtros = {
        "tabla": tabla,
        "registro_id": registro_id,
        "accion": accion,
        "usuario_id": usuario_id,
        "desde": desde,
        "hasta": hasta,
    }
    repo = AuditoriaRepository(session)
    informar_total(response, await repo.contar_listado(**filtros))
    return await repo.listar(skip=skip, limit=limit, **filtros)
