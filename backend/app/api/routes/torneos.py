from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.schemas.torneo import EstadoTorneo, TorneoCreate, TorneoOut, TorneoUpdate
from app.services.torneo import TorneoService

router = APIRouter(prefix="/torneos", tags=["Torneos"])


@router.get("", response_model=list[TorneoOut])
async def listar_torneos(
    skip: int = 0,
    limit: int = Query(default=100, le=200),
    estado: EstadoTorneo | None = None,
    torneo_grupo_id: int | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[TorneoOut]:
    """`torneo_grupo_id` filtra a las ediciones de un mismo grupo — lo usa
    el selector de Estadísticas (torneos-admin-plan.md, Fase 2 parte B)."""
    return await TorneoService(session).list(
        skip=skip, limit=limit, estado=estado, torneo_grupo_id=torneo_grupo_id
    )


@router.get("/{torneo_id}", response_model=TorneoOut)
async def obtener_torneo(torneo_id: int, session: AsyncSession = Depends(get_db)) -> TorneoOut:
    return await TorneoService(session).get(torneo_id)


@router.post("", response_model=TorneoOut, status_code=201, dependencies=[Depends(require_roles("TorneoAdmin"))])
async def crear_torneo(data: TorneoCreate, session: AsyncSession = Depends(get_db)) -> TorneoOut:
    return await TorneoService(session).create(data)


@router.patch("/{torneo_id}", response_model=TorneoOut, dependencies=[Depends(require_roles("TorneoAdmin"))])
async def actualizar_torneo(
    torneo_id: int, data: TorneoUpdate, session: AsyncSession = Depends(get_db)
) -> TorneoOut:
    return await TorneoService(session).update(torneo_id, data)


@router.delete("/{torneo_id}", response_model=TorneoOut, dependencies=[Depends(require_roles("TorneoAdmin"))])
async def dar_de_baja_torneo(torneo_id: int, session: AsyncSession = Depends(get_db)) -> TorneoOut:
    """Borrado lógico (Estado='Inactivo'). No hay DELETE físico: ver el
    comentario sobre ON DELETE CASCADE en database/02_constraints.sql."""
    return await TorneoService(session).soft_delete(torneo_id)
