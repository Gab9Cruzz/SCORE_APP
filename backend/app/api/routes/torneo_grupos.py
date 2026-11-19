from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_optional, require_roles
from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.torneo_grupo import (
    TorneoGrupoConEdiciones,
    TorneoGrupoOut,
    TorneoGrupoUpdate,
)
from app.services.permisos_catalogo import exigir_admin_del_grupo
from app.services.torneo_grupo import TorneoGrupoService

# Un TORNEO_GRUPO se CREA implícitamente vía POST /torneos con
# torneo_grupo_nombre (torneos-admin-plan.md, D-Eng-1) — no hay un
# POST acá. Esto solo lista lo agrupado (para la Pestaña Torneos),
# permite renombrar (EC-25) y archivar/reactivar (3B-7,
# cierre-backlog-todos-plan.md) — nunca DELETE, ver el comentario de
# Estado en 01_schema.sql.
router = APIRouter(prefix="/torneo-grupos", tags=["Torneo Grupos"])


@router.get("", response_model=list[TorneoGrupoConEdiciones])
async def listar_torneo_grupos(
    incluir_archivados: bool = False,
    session: AsyncSession = Depends(get_db),
    usuario: Usuario | None = Depends(get_current_user_optional),
) -> list[TorneoGrupoConEdiciones]:
    """Tarjeta por grupo con sus ediciones (Fase 2, paso 1 del journey) —
    "N ediciones" y cuál es la más reciente/activa se calculan acá, no en
    cada componente de frontend que necesite la lista (D-Eng-1).

    3B-7 (docs/plans/cierre-backlog-todos-plan.md): sin
    `incluir_archivados`, los grupos Archivado no aparecen — TorneosAdminPage
    los pide explícito solo cuando el admin activa "Ver archivados"."""
    return await TorneoGrupoService(session).listar_con_ediciones(
        incluir_archivados=incluir_archivados, solo_publicados=usuario is None
    )


@router.get("/{torneo_grupo_id}", response_model=TorneoGrupoConEdiciones)
async def obtener_torneo_grupo(
    torneo_grupo_id: int,
    session: AsyncSession = Depends(get_db),
    usuario: Usuario | None = Depends(get_current_user_optional),
) -> TorneoGrupoConEdiciones:
    """Incluye `ediciones` (mismo shape que el listado) para que "Ver
    Torneo" (TorneoDashboardPage) pueda ofrecer el selector de ediciones
    del grupo y un atajo a "+ Nueva edición" sin tener que ir y volver a
    la Pestaña Torneos (ediciones-catalogo-disciplinas-plan.md, pedido de
    seguimiento: administrar ediciones desde adentro del panel del
    torneo)."""
    return await TorneoGrupoService(session).get_con_ediciones(torneo_grupo_id, solo_publicados=usuario is None)


@router.patch(
    "/{torneo_grupo_id}",
    response_model=TorneoGrupoOut,
    dependencies=[Depends(require_roles("TorneoAdmin"))],
)
async def renombrar_torneo_grupo(
    torneo_grupo_id: int,
    data: TorneoGrupoUpdate,
    session: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
) -> TorneoGrupoOut:
    """EC-25: renombrar un grupo con ediciones ya finalizadas está
    permitido sin restricción — el nombre se compone en runtime en cada
    edición, así que esto alcanza a todas de una.

    TASK-013 (SEC-04): solo quien administra alguna de sus ediciones (o un
    AdminGeneral). Archivar oculta todas las ediciones."""
    await exigir_admin_del_grupo(usuario, torneo_grupo_id, session)
    return await TorneoGrupoService(session).update(torneo_grupo_id, data)
