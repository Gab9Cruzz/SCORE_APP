from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.schemas.evento import EstadoEvento, EventoCreate, EventoOut, EventoUpdate
from app.services.evento import EventoService

router = APIRouter(prefix="/eventos", tags=["Eventos (catálogo)"])


@router.get("", response_model=list[EventoOut])
async def listar_eventos(
    skip: int = 0,
    limit: int = Query(default=100, le=200),
    estado: EstadoEvento | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[EventoOut]:
    return await EventoService(session).list(skip=skip, limit=limit, estado=estado)


@router.get("/{evento_id}", response_model=EventoOut)
async def obtener_evento(evento_id: int, session: AsyncSession = Depends(get_db)) -> EventoOut:
    return await EventoService(session).get(evento_id)


@router.post("", response_model=EventoOut, status_code=201, dependencies=[Depends(require_roles("Admin"))])
async def crear_evento(data: EventoCreate, session: AsyncSession = Depends(get_db)) -> EventoOut:
    return await EventoService(session).create(data)


@router.patch("/{evento_id}", response_model=EventoOut, dependencies=[Depends(require_roles("Admin"))])
async def actualizar_evento(
    evento_id: int, data: EventoUpdate, session: AsyncSession = Depends(get_db)
) -> EventoOut:
    return await EventoService(session).update(evento_id, data)


@router.delete("/{evento_id}", response_model=EventoOut, dependencies=[Depends(require_roles("Admin"))])
async def dar_de_baja_evento(evento_id: int, session: AsyncSession = Depends(get_db)) -> EventoOut:
    return await EventoService(session).soft_delete(evento_id)
