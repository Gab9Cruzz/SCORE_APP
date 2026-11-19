from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_optional, require_roles, require_torneo_access_de
from app.core.paginacion import Pagina, informar_total, paginacion
from app.db.session import get_db
from app.models.usuario import Usuario
from app.repositories.asignacion_torneo_admin import AsignacionTorneoAdminRepository
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
    *,
    response: Response,
    pagina: Pagina = Depends(paginacion),
    session: AsyncSession = Depends(get_db),
    usuario: Usuario | None = Depends(get_current_user_optional),
) -> list[InscripcionTorneoOut]:
    """Sin auth (anónimo/Público) o con AdminGeneral/Arbitro: sin recorte,
    igual que siempre — este listado alimenta pantallas públicas (equipos
    inscriptos de un torneo). Un TorneoAdmin SÍ queda recortado a sus
    torneos asignados, siempre, sin flag opt-in que el cliente pueda
    desactivar (TODOS.md, P3: "el alcance NO se expresa como query param
    elegible por el cliente — se deriva implícito del token vía
    torneo_ids_permitidos, mismo patrón que torneos/partidos"). A
    diferencia de `GET /torneos`/`GET /partidos` (que exponen `solo_mios`
    como opt-in), acá el recorte es forzado: el listado de sub-recursos de
    UN torneo específico no tiene un caso de uso legítimo en el que un
    TorneoAdmin necesite ver los de un torneo que no le asignaron."""
    torneo_ids_permitidos: list[int] | None = None
    if usuario is not None and usuario.rol == "TorneoAdmin":
        torneo_ids_permitidos = await AsignacionTorneoAdminRepository(session).listar_torneo_ids_activos(usuario.id)
    filtros = {
        "torneo_id": torneo_id,
        "equipo_id": equipo_id,
        "torneo_ids_permitidos": torneo_ids_permitidos,
        # TASK-014 (SEC-07): mismo criterio que GET /torneos y /partidos.
        "solo_publicados": usuario is None,
    }
    servicio = InscripcionTorneoService(session)
    informar_total(response, await servicio.contar(**filtros))
    return await servicio.list(skip=pagina.skip, limit=pagina.limit, **filtros)


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
