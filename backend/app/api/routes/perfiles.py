from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.schemas.jugador_perfil_disciplina import (
    JugadorPerfilDisciplinaCreate,
    JugadorPerfilDisciplinaOut,
    JugadorPerfilDisciplinaUpdate,
)
from app.services.jugador_perfil_disciplina import JugadorPerfilDisciplinaService

# jugador_perfil_disciplina: el jugador dentro de una disciplina puntual.
# Sin DELETE: la tabla no tiene Estado, ver el modelo.
router = APIRouter(prefix="/perfiles", tags=["Perfiles"])


@router.get("", response_model=list[JugadorPerfilDisciplinaOut])
async def listar_perfiles(
    skip: int = 0,
    limit: int = Query(default=100, le=200),
    jugador_id: int | None = None,
    disciplina_id: int | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[JugadorPerfilDisciplinaOut]:
    return await JugadorPerfilDisciplinaService(session).list(
        skip=skip, limit=limit, jugador_id=jugador_id, disciplina_id=disciplina_id
    )


@router.get("/{perfil_id}", response_model=JugadorPerfilDisciplinaOut)
async def obtener_perfil(perfil_id: int, session: AsyncSession = Depends(get_db)) -> JugadorPerfilDisciplinaOut:
    return await JugadorPerfilDisciplinaService(session).get(perfil_id)


@router.post(
    "",
    response_model=JugadorPerfilDisciplinaOut,
    status_code=201,
    dependencies=[Depends(require_roles("TorneoAdmin"))],
)
async def crear_perfil(
    data: JugadorPerfilDisciplinaCreate, session: AsyncSession = Depends(get_db)
) -> JugadorPerfilDisciplinaOut:
    """unique_perfil_por_disciplina (02_constraints.sql) evita un segundo
    perfil para la misma (jugador, disciplina) — 409."""
    return await JugadorPerfilDisciplinaService(session).create(data)


@router.patch(
    "/{perfil_id}",
    response_model=JugadorPerfilDisciplinaOut,
    dependencies=[Depends(require_roles("TorneoAdmin"))],
)
async def actualizar_perfil(
    perfil_id: int, data: JugadorPerfilDisciplinaUpdate, session: AsyncSession = Depends(get_db)
) -> JugadorPerfilDisciplinaOut:
    """Único uso real: alternar `suspendido`."""
    return await JugadorPerfilDisciplinaService(session).update(perfil_id, data)
