from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.schemas.disciplina import DisciplinaCreate, DisciplinaOut, DisciplinaUpdate, EstadoDisciplina
from app.services.disciplina import DisciplinaService

router = APIRouter(prefix="/disciplinas", tags=["Disciplinas"])


@router.get("", response_model=list[DisciplinaOut])
async def listar_disciplinas(
    skip: int = 0,
    limit: int = Query(default=100, le=200),
    estado: EstadoDisciplina | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[DisciplinaOut]:
    return await DisciplinaService(session).list(skip=skip, limit=limit, estado=estado)


@router.get("/{disciplina_id}", response_model=DisciplinaOut)
async def obtener_disciplina(disciplina_id: int, session: AsyncSession = Depends(get_db)) -> DisciplinaOut:
    return await DisciplinaService(session).get(disciplina_id)


@router.post(
    "", response_model=DisciplinaOut, status_code=201, dependencies=[Depends(require_roles("TorneoAdmin"))]
)
async def crear_disciplina(data: DisciplinaCreate, session: AsyncSession = Depends(get_db)) -> DisciplinaOut:
    return await DisciplinaService(session).create(data)


@router.patch(
    "/{disciplina_id}", response_model=DisciplinaOut, dependencies=[Depends(require_roles("TorneoAdmin"))]
)
async def actualizar_disciplina(
    disciplina_id: int, data: DisciplinaUpdate, session: AsyncSession = Depends(get_db)
) -> DisciplinaOut:
    return await DisciplinaService(session).update(disciplina_id, data)


@router.delete(
    "/{disciplina_id}", response_model=DisciplinaOut, dependencies=[Depends(require_roles("TorneoAdmin"))]
)
async def dar_de_baja_disciplina(disciplina_id: int, session: AsyncSession = Depends(get_db)) -> DisciplinaOut:
    return await DisciplinaService(session).soft_delete(disciplina_id)
