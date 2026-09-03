from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles, require_torneo_access_de
from app.db.session import get_db
from app.repositories.inscripcion_torneo import InscripcionTorneoRepository
from app.repositories.jugador_equipo import JugadorEquipoRepository
from app.schemas.jugador_equipo import (
    JugadorEquipoCreate,
    JugadorEquipoOut,
    JugadorEquipoUpdate,
)
from app.services.jugador_equipo import JugadorEquipoService

# jugador_equipo: quién juega en qué equipo y desde/hasta cuándo.
router = APIRouter(prefix="/plantillas", tags=["Plantillas"])


# Resolvers de torneo_id (rbac-licencias-torneos-plan.md, Fase 2) —
# JugadorEquipo.inscripcion_torneo_id -> InscripcionTorneo.torneo_id (1 hop).
async def _torneo_id_del_body(data: JugadorEquipoCreate, session: AsyncSession = Depends(get_db)) -> int:
    inscripcion = await InscripcionTorneoRepository(session).get_or_404(data.inscripcion_torneo_id)
    return inscripcion.torneo_id


async def _torneo_id_de_vinculo(vinculo_id: int, session: AsyncSession = Depends(get_db)) -> int:
    vinculo = await JugadorEquipoRepository(session).get_or_404(vinculo_id)
    inscripcion = await InscripcionTorneoRepository(session).get_or_404(vinculo.inscripcion_torneo_id)
    return inscripcion.torneo_id


@router.get("", response_model=list[JugadorEquipoOut])
async def listar_plantilla(
    inscripcion_torneo_id: int | None = None,
    jugador_perfil_id: int | None = None,
    torneo_id: int | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[JugadorEquipoOut]:
    """`torneo_id` filtra a los vínculos de ESE torneo (todos sus equipos) —
    lo usa el dashboard scoped por torneo (torneos-admin-plan.md, D-Eng-3).
    Antes de esto el GET devolvía el sistema completo sin filtrar."""
    return await JugadorEquipoService(session).list(
        inscripcion_torneo_id=inscripcion_torneo_id, jugador_perfil_id=jugador_perfil_id, torneo_id=torneo_id
    )


@router.get("/{vinculo_id}", response_model=JugadorEquipoOut)
async def obtener_vinculo(vinculo_id: int, session: AsyncSession = Depends(get_db)) -> JugadorEquipoOut:
    return await JugadorEquipoService(session).get(vinculo_id)


@router.post(
    "",
    response_model=JugadorEquipoOut,
    status_code=201,
    dependencies=[
        Depends(require_roles("TorneoAdmin")),
        Depends(require_torneo_access_de(_torneo_id_del_body)),
    ],
)
async def dar_de_alta_jugador(
    data: JugadorEquipoCreate, session: AsyncSession = Depends(get_db)
) -> JugadorEquipoOut:
    """dorsal único por roster (torneo+equipo) mientras la fila está vigente
    (uq_dorsal_por_roster_vigente, 03_indexes.sql). La exclusividad por
    torneo (un perfil, un equipo, por torneo) la valida
    fn_validar_exclusividad_torneo (06_triggers.sql) — llega como 400."""
    return await JugadorEquipoService(session).create(data)


@router.patch(
    "/{vinculo_id}",
    response_model=JugadorEquipoOut,
    dependencies=[
        Depends(require_roles("TorneoAdmin")),
        Depends(require_torneo_access_de(_torneo_id_de_vinculo)),
    ],
)
async def actualizar_vinculo(
    vinculo_id: int, data: JugadorEquipoUpdate, session: AsyncSession = Depends(get_db)
) -> JugadorEquipoOut:
    return await JugadorEquipoService(session).update(vinculo_id, data)


@router.post(
    "/{vinculo_id}/baja",
    response_model=JugadorEquipoOut,
    dependencies=[
        Depends(require_roles("TorneoAdmin")),
        Depends(require_torneo_access_de(_torneo_id_de_vinculo)),
    ],
)
async def dar_de_baja_jugador(
    vinculo_id: int, fecha_fin: date, session: AsyncSession = Depends(get_db)
) -> JugadorEquipoOut:
    """Cierra la vigencia (fecha_fin) y libera el dorsal para otro jugador."""
    return await JugadorEquipoService(session).dar_de_baja(vinculo_id, fecha_fin)
