from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.schemas.jugador_equipo import (
    JugadorEquipoCreate,
    JugadorEquipoOut,
    JugadorEquipoUpdate,
)
from app.services.jugador_equipo import JugadorEquipoService

# jugador_equipo: quién juega en qué equipo y desde/hasta cuándo.
router = APIRouter(prefix="/plantillas", tags=["Plantillas"])


@router.get("", response_model=list[JugadorEquipoOut])
async def listar_plantilla(
    equipo_id: int | None = None,
    jugador_id: int | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[JugadorEquipoOut]:
    return await JugadorEquipoService(session).list(equipo_id=equipo_id, jugador_id=jugador_id)


@router.get("/{vinculo_id}", response_model=JugadorEquipoOut)
async def obtener_vinculo(vinculo_id: int, session: AsyncSession = Depends(get_db)) -> JugadorEquipoOut:
    return await JugadorEquipoService(session).get(vinculo_id)


@router.post(
    "", response_model=JugadorEquipoOut, status_code=201, dependencies=[Depends(require_roles("TorneoAdmin"))]
)
async def dar_de_alta_jugador(
    data: JugadorEquipoCreate, session: AsyncSession = Depends(get_db)
) -> JugadorEquipoOut:
    """dorsal único por equipo mientras la fila está vigente
    (uq_dorsal_por_equipo_vigente, 03_indexes.sql)."""
    return await JugadorEquipoService(session).create(data)


@router.patch(
    "/{vinculo_id}", response_model=JugadorEquipoOut, dependencies=[Depends(require_roles("TorneoAdmin"))]
)
async def actualizar_vinculo(
    vinculo_id: int, data: JugadorEquipoUpdate, session: AsyncSession = Depends(get_db)
) -> JugadorEquipoOut:
    return await JugadorEquipoService(session).update(vinculo_id, data)


@router.post(
    "/{vinculo_id}/baja",
    response_model=JugadorEquipoOut,
    dependencies=[Depends(require_roles("TorneoAdmin"))],
)
async def dar_de_baja_jugador(
    vinculo_id: int, fecha_fin: date, session: AsyncSession = Depends(get_db)
) -> JugadorEquipoOut:
    """Cierra la vigencia (fecha_fin) y libera el dorsal para otro jugador."""
    return await JugadorEquipoService(session).dar_de_baja(vinculo_id, fecha_fin)
