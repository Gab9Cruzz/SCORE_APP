from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.partido import EstadoPartido, PartidoCreate, PartidoOut, PartidoUpdate
from app.services.partido import PartidoService

router = APIRouter(prefix="/partidos", tags=["Partidos"])


@router.get("", response_model=list[PartidoOut])
async def listar_partidos(
    skip: int = 0,
    limit: int = Query(default=100, le=200),
    torneo_id: int | None = None,
    estado: EstadoPartido | None = None,
    arbitro_id: int | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[PartidoOut]:
    """Público, sin auth (roles-3-modulos-plan.md, Fase 1: los resultados
    ya son públicos a propósito). `arbitro_id` (Fase 3, D1) es un filtro
    más, no un chequeo de permiso: PartidoOut ya expone arbitro_id en
    cada fila, así que este query param no agrega ninguna fuga nueva,
    solo evita filtrar del lado del cliente."""
    return await PartidoService(session).list(
        skip=skip, limit=limit, torneo_id=torneo_id, estado=estado, arbitro_id=arbitro_id
    )


@router.get("/{partido_id}", response_model=PartidoOut)
async def obtener_partido(partido_id: int, session: AsyncSession = Depends(get_db)) -> PartidoOut:
    return await PartidoService(session).get(partido_id)


@router.post(
    "",
    response_model=PartidoOut,
    status_code=201,
    dependencies=[Depends(require_roles("TorneoAdmin"))],
)
async def crear_partido(data: PartidoCreate, session: AsyncSession = Depends(get_db)) -> PartidoOut:
    """Programa un partido. trg_partidos_validar_inscripcion (06_triggers.sql)
    rechaza si alguno de los dos equipos no está inscrito y no cancelado en
    el torneo — el error llega como 400 con el mensaje del trigger.

    Árbitro NO tiene este endpoint (roles-3-modulos-plan.md, Fase 1, D4):
    crear partidos es de TorneoAdmin/AdminGeneral. Árbitro solo carga
    partidos que ya le asignaron."""
    return await PartidoService(session).create(data)


@router.patch(
    "/{partido_id}",
    response_model=PartidoOut,
    dependencies=[Depends(require_roles("TorneoAdmin", "Arbitro"))],
)
async def actualizar_partido(
    partido_id: int,
    data: PartidoUpdate,
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
) -> PartidoOut:
    """Árbitro conserva este endpoint para avanzar el estado de SU partido
    (Programado -> En curso -> Finalizado). El chequeo de "¿es tuyo?" vive
    en PartidoService.update(), no acá (D5)."""
    return await PartidoService(session).update(partido_id, data, usuario_actual)


@router.delete(
    "/{partido_id}",
    response_model=PartidoOut,
    dependencies=[Depends(require_roles("TorneoAdmin"))],
)
async def cancelar_partido(partido_id: int, session: AsyncSession = Depends(get_db)) -> PartidoOut:
    """Borrado lógico -> Estado='Cancelado' (no 'Inactivo': no es un valor
    válido para partidos.estado, ver chk_partidos_estado)."""
    return await PartidoService(session).soft_delete(partido_id)
