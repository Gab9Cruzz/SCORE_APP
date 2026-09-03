from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles, require_torneo_access_de
from app.db.session import get_db
from app.repositories.inscripcion_torneo import InscripcionTorneoRepository
from app.schemas.inscripcion_torneo import (
    InscripcionTorneoCreate,
    InscripcionTorneoOut,
    InscripcionTorneoUpdate,
)
from app.services.inscripcion_torneo import InscripcionTorneoService

router = APIRouter(prefix="/inscripciones", tags=["Inscripciones"])


# Resolvers de torneo_id (rbac-licencias-torneos-plan.md, Fase 2) —
# InscripcionTorneo.torneo_id es directo (database/01_schema.sql), sin
# join intermedio.
async def _torneo_id_del_body(data: InscripcionTorneoCreate) -> int:
    return data.torneo_id


async def _torneo_id_de_inscripcion(inscripcion_id: int, session: AsyncSession = Depends(get_db)) -> int:
    inscripcion = await InscripcionTorneoRepository(session).get_or_404(inscripcion_id)
    return inscripcion.torneo_id


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
    "",
    response_model=InscripcionTorneoOut,
    status_code=201,
    dependencies=[
        Depends(require_roles("TorneoAdmin")),
        Depends(require_torneo_access_de(_torneo_id_del_body)),
    ],
)
async def crear_inscripcion(
    data: InscripcionTorneoCreate, session: AsyncSession = Depends(get_db)
) -> InscripcionTorneoOut:
    """Dos caminos según la Modalidad del torneo (Decisión B1,
    ediciones-catalogo-disciplinas-plan.md) — ver InscripcionTorneoCreate:
    `equipo_id` (Pareja/Conjunto) o `jugador_cedula`/`jugador_nombre`/
    `jugador_correo_electronico` (Individual, sin fila en EQUIPOS).
    unique_inscripcion/unique_inscripcion_individual (02_constraints.sql)
    evitan duplicados en cada camino (409)."""
    return await InscripcionTorneoService(session).create(data)


@router.patch(
    "/{inscripcion_id}",
    response_model=InscripcionTorneoOut,
    dependencies=[
        Depends(require_roles("TorneoAdmin")),
        Depends(require_torneo_access_de(_torneo_id_de_inscripcion)),
    ],
)
async def actualizar_inscripcion(
    inscripcion_id: int, data: InscripcionTorneoUpdate, session: AsyncSession = Depends(get_db)
) -> InscripcionTorneoOut:
    """Cambiar a Estado='Cancelado' es el borrado lógico de una inscripción."""
    return await InscripcionTorneoService(session).update(inscripcion_id, data)
