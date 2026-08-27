from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.schemas.modalidad import EstadoModalidad, ModalidadCreate, ModalidadOut, ModalidadUpdate
from app.services.modalidad import ModalidadService

router = APIRouter(prefix="/modalidades", tags=["Modalidades"])


@router.get("", response_model=list[ModalidadOut])
async def listar_modalidades(
    skip: int = 0,
    limit: int = Query(default=100, le=200),
    disciplina_id: int | None = None,
    estado: EstadoModalidad | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[ModalidadOut]:
    return await ModalidadService(session).list(skip=skip, limit=limit, disciplina_id=disciplina_id, estado=estado)


@router.get("/{modalidad_id}", response_model=ModalidadOut)
async def obtener_modalidad(modalidad_id: int, session: AsyncSession = Depends(get_db)) -> ModalidadOut:
    return await ModalidadService(session).get(modalidad_id)


@router.post(
    "", response_model=ModalidadOut, status_code=201, dependencies=[Depends(require_roles("TorneoAdmin"))]
)
async def crear_modalidad(data: ModalidadCreate, session: AsyncSession = Depends(get_db)) -> ModalidadOut:
    return await ModalidadService(session).create(data)


@router.patch(
    "/{modalidad_id}", response_model=ModalidadOut, dependencies=[Depends(require_roles("TorneoAdmin"))]
)
async def actualizar_modalidad(
    modalidad_id: int, data: ModalidadUpdate, session: AsyncSession = Depends(get_db)
) -> ModalidadOut:
    return await ModalidadService(session).update(modalidad_id, data)


@router.delete(
    "/{modalidad_id}", response_model=ModalidadOut, dependencies=[Depends(require_roles("TorneoAdmin"))]
)
async def dar_de_baja_modalidad(modalidad_id: int, session: AsyncSession = Depends(get_db)) -> ModalidadOut:
    return await ModalidadService(session).soft_delete(modalidad_id)
