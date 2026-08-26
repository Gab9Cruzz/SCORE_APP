from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.schemas.inscripcion_torneo import (
    InscripcionTorneoCreate,
    InscripcionTorneoOut,
    InscripcionTorneoUpdate,
)
from app.services.inscripcion_torneo import InscripcionTorneoService

router = APIRouter(prefix="/inscripciones", tags=["Inscripciones"])


@router.get("", response_model=list[InscripcionTorneoOut])
async def listar_inscripciones(
    torneo_id: int | None = None,
    equipo_id: int | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[InscripcionTorneoOut]:
    return await InscripcionTorneoService(session).list(torneo_id=torneo_id, equipo_id=equipo_id)


@router.get("/{inscripcion_id}", response_model=InscripcionTorneoOut)
async def obtener_inscripcion(
    inscripcion_id: int, session: AsyncSession = Depends(get_db)
) -> InscripcionTorneoOut:
    return await InscripcionTorneoService(session).get(inscripcion_id)


@router.post(
    "", response_model=InscripcionTorneoOut, status_code=201, dependencies=[Depends(require_roles("TorneoAdmin"))]
)
async def inscribir_equipo(
    data: InscripcionTorneoCreate, session: AsyncSession = Depends(get_db)
) -> InscripcionTorneoOut:
    """unique_inscripcion (02_constraints.sql) evita inscribir el mismo
    equipo dos veces en el mismo torneo (409)."""
    return await InscripcionTorneoService(session).create(data)


@router.patch(
    "/{inscripcion_id}",
    response_model=InscripcionTorneoOut,
    dependencies=[Depends(require_roles("TorneoAdmin"))],
)
async def actualizar_inscripcion(
    inscripcion_id: int, data: InscripcionTorneoUpdate, session: AsyncSession = Depends(get_db)
) -> InscripcionTorneoOut:
    """Cambiar a Estado='Cancelado' es el borrado lógico de una inscripción."""
    return await InscripcionTorneoService(session).update(inscripcion_id, data)
