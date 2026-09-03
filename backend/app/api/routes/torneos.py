from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_optional, require_roles, require_torneo_access
from app.db.session import get_db
from app.models.usuario import Usuario
from app.repositories.asignacion_torneo_admin import AsignacionTorneoAdminRepository
from app.schemas.torneo import EstadoTorneo, TorneoCreate, TorneoOut, TorneoUpdate
from app.services.torneo import TorneoService

router = APIRouter(prefix="/torneos", tags=["Torneos"])


@router.get("", response_model=list[TorneoOut])
async def listar_torneos(
    skip: int = 0,
    limit: int = Query(default=100, le=200),
    estado: EstadoTorneo | None = None,
    torneo_grupo_id: int | None = None,
    # rbac-licencias-torneos-plan.md, E1: filtra a los torneos asignados
    # cuando el caller es TorneoAdmin. Sin efecto para AdminGeneral,
    # Arbitro, Publico o llamadas anónimas — el listado sigue siendo
    # público por default, esto es un opt-in de UX para el propio panel
    # de un TorneoAdmin, no una restricción de seguridad nueva (las
    # rutas de escritura ya están scoped vía require_torneo_access).
    solo_mios: bool = False,
    session: AsyncSession = Depends(get_db),
    usuario: Usuario | None = Depends(get_current_user_optional),
) -> list[TorneoOut]:
    """`torneo_grupo_id` filtra a las ediciones de un mismo grupo — lo usa
    el selector de Estadísticas (torneos-admin-plan.md, Fase 2 parte B)."""
    torneo_ids_permitidos: list[int] | None = None
    if solo_mios and usuario is not None and usuario.rol == "TorneoAdmin":
        torneo_ids_permitidos = await AsignacionTorneoAdminRepository(session).listar_torneo_ids_activos(usuario.id)
    return await TorneoService(session).list(
        skip=skip,
        limit=limit,
        estado=estado,
        torneo_grupo_id=torneo_grupo_id,
        torneo_ids_permitidos=torneo_ids_permitidos,
    )


@router.get("/{torneo_id}", response_model=TorneoOut)
async def obtener_torneo(torneo_id: int, session: AsyncSession = Depends(get_db)) -> TorneoOut:
    return await TorneoService(session).get(torneo_id)


@router.post("", response_model=TorneoOut, status_code=201, dependencies=[Depends(require_roles("TorneoAdmin"))])
async def crear_torneo(
    data: TorneoCreate,
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
) -> TorneoOut:
    return await TorneoService(session).create(data, usuario_actual)


@router.patch(
    "/{torneo_id}",
    response_model=TorneoOut,
    dependencies=[Depends(require_roles("TorneoAdmin")), Depends(require_torneo_access())],
)
async def actualizar_torneo(
    torneo_id: int, data: TorneoUpdate, session: AsyncSession = Depends(get_db)
) -> TorneoOut:
    return await TorneoService(session).update(torneo_id, data)


@router.delete(
    "/{torneo_id}",
    response_model=TorneoOut,
    dependencies=[Depends(require_roles("TorneoAdmin")), Depends(require_torneo_access())],
)
async def dar_de_baja_torneo(torneo_id: int, session: AsyncSession = Depends(get_db)) -> TorneoOut:
    """Borrado lógico (Estado='Inactivo'). No hay DELETE físico: ver el
    comentario sobre ON DELETE CASCADE en database/02_constraints.sql.

    require_torneo_access (rbac-licencias-torneos-plan.md, §4.3/§4.6):
    AdminGeneral bypass total; TorneoAdmin exige asignación Activa a ESTE
    torneo_id — sin asignación, 403 antes de llegar al service."""
    return await TorneoService(session).soft_delete(torneo_id)
