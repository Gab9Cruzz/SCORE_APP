from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.schemas.torneo_grupo import TorneoGrupoConEdiciones, TorneoGrupoOut, TorneoGrupoUpdate
from app.services.torneo_grupo import TorneoGrupoService

# Un TORNEO_GRUPO se CREA implícitamente vía POST /torneos con
# torneo_grupo_nombre (torneos-admin-plan.md, D-Eng-1) — no hay un
# POST acá. Esto solo lista lo agrupado (para la Pestaña Torneos) y
# permite renombrar (EC-25).
router = APIRouter(prefix="/torneo-grupos", tags=["Torneo Grupos"])


@router.get("", response_model=list[TorneoGrupoConEdiciones])
async def listar_torneo_grupos(session: AsyncSession = Depends(get_db)) -> list[TorneoGrupoConEdiciones]:
    """Tarjeta por grupo con sus ediciones (Fase 2, paso 1 del journey) —
    "N ediciones" y cuál es la más reciente/activa se calculan acá, no en
    cada componente de frontend que necesite la lista (D-Eng-1)."""
    return await TorneoGrupoService(session).listar_con_ediciones()


@router.get("/{torneo_grupo_id}", response_model=TorneoGrupoOut)
async def obtener_torneo_grupo(
    torneo_grupo_id: int, session: AsyncSession = Depends(get_db)
) -> TorneoGrupoOut:
    return await TorneoGrupoService(session).get(torneo_grupo_id)


@router.patch(
    "/{torneo_grupo_id}",
    response_model=TorneoGrupoOut,
    dependencies=[Depends(require_roles("TorneoAdmin"))],
)
async def renombrar_torneo_grupo(
    torneo_grupo_id: int, data: TorneoGrupoUpdate, session: AsyncSession = Depends(get_db)
) -> TorneoGrupoOut:
    """EC-25: renombrar un grupo con ediciones ya finalizadas está
    permitido sin restricción — el nombre se compone en runtime en cada
    edición, así que esto alcanza a todas de una."""
    return await TorneoGrupoService(session).update(torneo_grupo_id, data)
