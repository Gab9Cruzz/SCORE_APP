from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.paginacion import ids_por_coma, informar_total
from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.jugador_perfil_disciplina import (
    JugadorPerfilDisciplinaCreate,
    JugadorPerfilDisciplinaOut,
    JugadorPerfilDisciplinaUpdate,
)
from app.services.jugador_perfil_disciplina import JugadorPerfilDisciplinaService
from app.services.permisos_catalogo import exigir_admin_de_torneos_del_perfil

# jugador_perfil_disciplina: el jugador dentro de una disciplina puntual.
# Sin DELETE: la tabla no tiene Estado, ver el modelo.
router = APIRouter(prefix="/perfiles", tags=["Perfiles"])


@router.get("", response_model=list[JugadorPerfilDisciplinaOut])
async def listar_perfiles(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    jugador_id: int | None = None,
    disciplina_id: int | None = None,
    ids: list[int] | None = Depends(ids_por_coma),
    *,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> list[JugadorPerfilDisciplinaOut]:
    servicio = JugadorPerfilDisciplinaService(session)
    informar_total(response, await servicio.contar(jugador_id=jugador_id, disciplina_id=disciplina_id, ids=ids))
    return await servicio.list(skip=skip, limit=limit, jugador_id=jugador_id, disciplina_id=disciplina_id, ids=ids)


@router.get("/{perfil_id}", response_model=JugadorPerfilDisciplinaOut)
async def obtener_perfil(perfil_id: int, session: AsyncSession = Depends(get_db)) -> JugadorPerfilDisciplinaOut:
    return await JugadorPerfilDisciplinaService(session).get(perfil_id)


@router.post(
    "",
    response_model=JugadorPerfilDisciplinaOut,
    status_code=201,
    dependencies=[Depends(require_roles("TorneoAdmin"))],
)
async def crear_perfil(
    data: JugadorPerfilDisciplinaCreate, session: AsyncSession = Depends(get_db)
) -> JugadorPerfilDisciplinaOut:
    """unique_perfil_por_disciplina (02_constraints.sql) evita un segundo
    perfil para la misma (jugador, disciplina) — 409."""
    return await JugadorPerfilDisciplinaService(session).create(data)


@router.patch(
    "/{perfil_id}",
    response_model=JugadorPerfilDisciplinaOut,
    dependencies=[Depends(require_roles("TorneoAdmin"))],
)
async def actualizar_perfil(
    perfil_id: int,
    data: JugadorPerfilDisciplinaUpdate,
    session: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
) -> JugadorPerfilDisciplinaOut:
    """Único uso real: alternar `suspendido`. TASK-013 (SEC-04): exige
    administrar todos los torneos abiertos donde el jugador está activo."""
    await exigir_admin_de_torneos_del_perfil(usuario, perfil_id, session)
    return await JugadorPerfilDisciplinaService(session).update(perfil_id, data)
