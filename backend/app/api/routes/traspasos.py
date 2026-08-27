from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.traspaso import TraspasoCreate, TraspasoOut
from app.services.traspaso import TraspasoService

router = APIRouter(prefix="/traspasos", tags=["Traspasos"])


@router.get("", response_model=list[TraspasoOut])
async def listar_traspasos(
    jugador_perfil_id: int | None = None,
    torneo_id: int | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[TraspasoOut]:
    """`torneo_id` filtra por el torneo del equipo DESTINO (ver
    TraspasoRepository.listar_por_torneo) — dashboard scoped por torneo
    (torneos-admin-plan.md, D-Eng-3)."""
    return await TraspasoService(session).list(jugador_perfil_id=jugador_perfil_id, torneo_id=torneo_id)


@router.get("/{traspaso_id}", response_model=TraspasoOut)
async def obtener_traspaso(traspaso_id: int, session: AsyncSession = Depends(get_db)) -> TraspasoOut:
    return await TraspasoService(session).get(traspaso_id)


@router.post(
    "", response_model=TraspasoOut, status_code=201, dependencies=[Depends(require_roles("TorneoAdmin"))]
)
async def crear_traspaso(
    data: TraspasoCreate,
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
) -> TraspasoOut:
    """Cierra la membresía de origen (si hay) y abre la de destino en una
    sola transacción — ver TraspasoService.crear."""
    return await TraspasoService(session).crear(data, usuario_actual.id)


@router.post(
    "/{traspaso_id}/anular", response_model=TraspasoOut, dependencies=[Depends(require_roles("TorneoAdmin"))]
)
async def anular_traspaso(traspaso_id: int, session: AsyncSession = Depends(get_db)) -> TraspasoOut:
    """EC-20: anotación visual — NO revierte el roster. Corregir el error
    de verdad es un traspaso nuevo en sentido inverso (POST /traspasos)."""
    return await TraspasoService(session).anular(traspaso_id)
