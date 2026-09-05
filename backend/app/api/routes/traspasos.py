from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles, require_torneo_access_de
from app.db.session import get_db
from app.models.usuario import Usuario
from app.repositories.inscripcion_torneo import InscripcionTorneoRepository
from app.repositories.traspaso import TraspasoRepository
from app.schemas.traspaso import TraspasoCreate, TraspasoOut
from app.services.traspaso import TraspasoService

router = APIRouter(prefix="/traspasos", tags=["Traspasos"])


# Resolvers de torneo_id (rbac-licencias-torneos-plan.md, Fase 2) —
# Traspaso.inscripcion_destino_id -> InscripcionTorneo.torneo_id (1 hop).
# El torneo relevante es siempre el DESTINO (mismo criterio que
# TraspasoRepository.listar_por_torneo, ver comentario en la ruta GET
# de listado): un traspaso lo autoriza quien administra a DÓNDE llega el
# jugador, no de dónde sale.
async def _torneo_id_del_body(data: TraspasoCreate, session: AsyncSession = Depends(get_db)) -> int:
    inscripcion = await InscripcionTorneoRepository(session).get_or_404(data.inscripcion_destino_id)
    return inscripcion.torneo_id


async def _torneo_id_de_traspaso(traspaso_id: int, session: AsyncSession = Depends(get_db)) -> int:
    traspaso = await TraspasoRepository(session).get_or_404(traspaso_id)
    inscripcion = await InscripcionTorneoRepository(session).get_or_404(traspaso.inscripcion_destino_id)
    return inscripcion.torneo_id


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
    "",
    response_model=TraspasoOut,
    status_code=201,
    dependencies=[
        Depends(require_roles("TorneoAdmin")),
        Depends(require_torneo_access_de(_torneo_id_del_body)),
    ],
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
    "/{traspaso_id}/anular",
    response_model=TraspasoOut,
    dependencies=[
        Depends(require_roles("TorneoAdmin")),
        Depends(require_torneo_access_de(_torneo_id_de_traspaso)),
    ],
)
async def anular_traspaso(traspaso_id: int, session: AsyncSession = Depends(get_db)) -> TraspasoOut:
    """Revierte el traspaso de verdad: reactiva la membresía de origen (si
    había) y da de baja la de destino — ver TraspasoService.anular. Deja
    de estar disponible en cuanto el club destino ya arrancó un partido
    desde este traspaso (`TraspasoOut.puede_anularse`); a partir de ahí
    corresponde un traspaso nuevo en sentido inverso (POST /traspasos)."""
    return await TraspasoService(session).anular(traspaso_id)
