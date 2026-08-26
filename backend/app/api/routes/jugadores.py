from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.schemas.jugador import EstadoJugador, JugadorCreate, JugadorOut, JugadorUpdate
from app.services.jugador import JugadorService

router = APIRouter(prefix="/jugadores", tags=["Jugadores"])


@router.get("", response_model=list[JugadorOut])
async def listar_jugadores(
    skip: int = 0,
    limit: int = Query(default=100, le=200),
    estado: EstadoJugador | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[JugadorOut]:
    return await JugadorService(session).list(skip=skip, limit=limit, estado=estado)


@router.get("/{jugador_id}", response_model=JugadorOut)
async def obtener_jugador(jugador_id: int, session: AsyncSession = Depends(get_db)) -> JugadorOut:
    return await JugadorService(session).get(jugador_id)


@router.post("", response_model=JugadorOut, status_code=201, dependencies=[Depends(require_roles("TorneoAdmin"))])
async def crear_jugador(data: JugadorCreate, session: AsyncSession = Depends(get_db)) -> JugadorOut:
    return await JugadorService(session).create(data)


@router.patch("/{jugador_id}", response_model=JugadorOut, dependencies=[Depends(require_roles("TorneoAdmin"))])
async def actualizar_jugador(
    jugador_id: int, data: JugadorUpdate, session: AsyncSession = Depends(get_db)
) -> JugadorOut:
    return await JugadorService(session).update(jugador_id, data)


@router.delete("/{jugador_id}", response_model=JugadorOut, dependencies=[Depends(require_roles("TorneoAdmin"))])
async def dar_de_baja_jugador(jugador_id: int, session: AsyncSession = Depends(get_db)) -> JugadorOut:
    return await JugadorService(session).soft_delete(jugador_id)
