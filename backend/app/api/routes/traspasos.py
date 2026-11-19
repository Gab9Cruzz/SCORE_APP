from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    get_current_user_optional,
    require_roles,
    require_torneo_access_de,
)
from app.core.paginacion import Pagina, informar_total, paginacion
from app.db.session import get_db
from app.models.usuario import Usuario
from app.repositories.asignacion_torneo_admin import AsignacionTorneoAdminRepository
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
    *,
    response: Response,
    pagina: Pagina = Depends(paginacion),
    session: AsyncSession = Depends(get_db),
    usuario: Usuario | None = Depends(get_current_user_optional),
) -> list[TraspasoOut]:
    """`torneo_id` filtra por el torneo del equipo DESTINO (ver
    TraspasoRepository.listar_por_torneo) — dashboard scoped por torneo
    (torneos-admin-plan.md, D-Eng-3).

    Recorte por asignación (P3, TODOS.md) — mismo criterio que
    `GET /inscripciones`/`GET /plantillas`: un TorneoAdmin queda forzado a
    sus torneos asignados, con o sin `torneo_id` explícito."""
    torneo_ids_permitidos: list[int] | None = None
    if usuario is not None and usuario.rol == "TorneoAdmin":
        torneo_ids_permitidos = await AsignacionTorneoAdminRepository(session).listar_torneo_ids_activos(usuario.id)
    filtros = {
        "jugador_perfil_id": jugador_perfil_id,
        "torneo_id": torneo_id,
        "torneo_ids_permitidos": torneo_ids_permitidos,
        # TASK-014 (SEC-07): mismo criterio que GET /torneos y /partidos.
        "solo_publicados": usuario is None,
    }
    servicio = TraspasoService(session)
    informar_total(response, await servicio.contar(**filtros))
    return await servicio.list(skip=pagina.skip, limit=pagina.limit, **filtros)


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
