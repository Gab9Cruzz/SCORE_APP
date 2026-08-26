from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.schemas.equipo import EquipoCreate, EquipoOut, EquipoUpdate, EstadoEquipo
from app.services.equipo import EquipoService

router = APIRouter(prefix="/equipos", tags=["Equipos"])


@router.get("", response_model=list[EquipoOut])
async def listar_equipos(
    skip: int = 0,
    limit: int = Query(default=100, le=200),
    estado: EstadoEquipo | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[EquipoOut]:
    return await EquipoService(session).list(skip=skip, limit=limit, estado=estado)


@router.get("/{equipo_id}", response_model=EquipoOut)
async def obtener_equipo(equipo_id: int, session: AsyncSession = Depends(get_db)) -> EquipoOut:
    return await EquipoService(session).get(equipo_id)


@router.post("", response_model=EquipoOut, status_code=201, dependencies=[Depends(require_roles("TorneoAdmin"))])
async def crear_equipo(data: EquipoCreate, session: AsyncSession = Depends(get_db)) -> EquipoOut:
    return await EquipoService(session).create(data)


@router.patch("/{equipo_id}", response_model=EquipoOut, dependencies=[Depends(require_roles("TorneoAdmin"))])
async def actualizar_equipo(
    equipo_id: int, data: EquipoUpdate, session: AsyncSession = Depends(get_db)
) -> EquipoOut:
    return await EquipoService(session).update(equipo_id, data)


@router.delete("/{equipo_id}", response_model=EquipoOut, dependencies=[Depends(require_roles("TorneoAdmin"))])
async def dar_de_baja_equipo(equipo_id: int, session: AsyncSession = Depends(get_db)) -> EquipoOut:
    return await EquipoService(session).soft_delete(equipo_id)
