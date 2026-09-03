from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles, require_torneo_access_de
from app.db.session import get_db
from app.models.usuario import Usuario
from app.repositories.evento_partido import EventoPartidoRepository
from app.repositories.partido import PartidoRepository
from app.schemas.evento_partido import EventoPartidoCreate, EventoPartidoMinutoUpdate, EventoPartidoOut
from app.services.evento_partido import EventoPartidoService

# Goles, tarjetas y cambios dentro de un partido. Distinto de /eventos, que
# es el catálogo (Gol, Autogol, Tarjeta Amarilla, ...).
router = APIRouter(prefix="/eventos-partido", tags=["Eventos de partido"])


# Resolvers de torneo_id (rbac-licencias-torneos-plan.md, Fase 2) —
# EventoPartido.partidos_id -> Partido.torneo_id (1 hop). "Arbitro" sin
# scoping en TODAS las rutas de este router (mismo criterio que
# partidos.py: ya tiene su propio ownership-check en el Service, D5).
async def _torneo_id_del_body(data: EventoPartidoCreate, session: AsyncSession = Depends(get_db)) -> int:
    partido = await PartidoRepository(session).get_or_404(data.partidos_id)
    return partido.torneo_id


async def _torneo_id_de_evento_partido(evento_partido_id: int, session: AsyncSession = Depends(get_db)) -> int:
    evento = await EventoPartidoRepository(session).get_or_404(evento_partido_id)
    partido = await PartidoRepository(session).get_or_404(evento.partidos_id)
    return partido.torneo_id


@router.get("", response_model=list[EventoPartidoOut])
async def listar_eventos_partido(
    partidos_id: int | None = None, session: AsyncSession = Depends(get_db)
) -> list[EventoPartidoOut]:
    return await EventoPartidoService(session).list(partidos_id=partidos_id)


@router.get("/{evento_partido_id}", response_model=EventoPartidoOut)
async def obtener_evento_partido(
    evento_partido_id: int, session: AsyncSession = Depends(get_db)
) -> EventoPartidoOut:
    return await EventoPartidoService(session).get(evento_partido_id)


@router.post(
    "",
    response_model=EventoPartidoOut,
    status_code=201,
    dependencies=[
        Depends(require_roles("TorneoAdmin", "Arbitro")),
        Depends(require_torneo_access_de(_torneo_id_del_body, "Arbitro")),
    ],
)
async def registrar_evento_partido(
    data: EventoPartidoCreate,
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
) -> EventoPartidoOut:
    """fn_validar_jugador_partido (06_triggers.sql) rechaza si el equipo no
    disputa el partido, si el jugador no pertenecía a ese equipo en esa
    fecha, o si jugador_id_entra falta/sobra según el tipo de evento.

    Árbitro: el chequeo de "¿es tu partido?" vive en
    EventoPartidoService.create() (D5), no acá."""
    return await EventoPartidoService(session).create(data, usuario_actual)


@router.patch(
    "/{evento_partido_id}",
    response_model=EventoPartidoOut,
    dependencies=[
        Depends(require_roles("TorneoAdmin", "Arbitro")),
        Depends(require_torneo_access_de(_torneo_id_de_evento_partido, "Arbitro")),
    ],
)
async def corregir_minuto_evento_partido(
    evento_partido_id: int,
    data: EventoPartidoMinutoUpdate,
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
) -> EventoPartidoOut:
    """Corrección de minuto (gestion-avanzada-equipos-control-mesa-plan.md)
    — gap preexistente: no había forma de arreglar un gol/tarjeta cargado
    con el minuto equivocado. Se permite en cualquier estado del partido
    (EC-15). Árbitro: mismo chequeo de "¿es tu partido?" que el resto de
    este router."""
    return await EventoPartidoService(session).corregir_minuto(evento_partido_id, data.minuto, usuario_actual)


@router.post(
    "/{evento_partido_id}/anular",
    response_model=EventoPartidoOut,
    dependencies=[
        Depends(require_roles("TorneoAdmin", "Arbitro")),
        Depends(require_torneo_access_de(_torneo_id_de_evento_partido, "Arbitro")),
    ],
)
async def anular_evento_partido(
    evento_partido_id: int,
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
) -> EventoPartidoOut:
    """Estado='Anulado' para un evento cargado por error (ej: gol mal
    registrado). No se borra físicamente, se anula: mantiene el historial.

    Árbitro: mismo chequeo que en registrar_evento_partido, ver
    EventoPartidoService.anular() (D5)."""
    return await EventoPartidoService(session).anular(evento_partido_id, usuario_actual)
