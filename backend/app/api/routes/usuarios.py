from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.usuario import RolUsuario, UsuarioCreate, UsuarioOut, UsuarioUpdate
from app.services.usuario import UsuarioService

# Gestión de cuentas (AdminGeneral, TorneoAdmin, Arbitro, Publico).
#
# Escritura (POST/PATCH/DELETE) exige AdminGeneral LITERAL, a propósito —
# no es el swap uniforme Admin->TorneoAdmin que se aplicó en los demás
# routers (roles-3-modulos-plan.md, Fase 1, D3). Si este router pasara a
# aceptar TorneoAdmin en escritura, ese rol heredaría gestión de usuarios,
# incluyendo poder auto-escalarse a AdminGeneral por PATCH — fue un bug
# real encontrado por la voz externa en Fase 1, no lo repitas.
#
# Lectura (GET) SÍ acepta TorneoAdmin desde Fase 2 (D5): necesita ver qué
# usuarios son Árbitro para asignarlos a un partido. UsuarioService.list()/
# get() recortan el resultado a solo cuentas Arbitro para ese rol — el
# require_roles de acá solo decide quién entra al endpoint, no qué ve una
# vez adentro.
router = APIRouter(prefix="/usuarios", tags=["Usuarios"])


@router.get(
    "", response_model=list[UsuarioOut], dependencies=[Depends(require_roles("AdminGeneral", "TorneoAdmin"))]
)
async def listar_usuarios(
    skip: int = 0,
    limit: int = Query(default=100, le=200),
    rol: RolUsuario | None = None,
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
) -> list[UsuarioOut]:
    return await UsuarioService(session).list(usuario_actual, skip=skip, limit=limit, rol=rol)


@router.get(
    "/{usuario_id}",
    response_model=UsuarioOut,
    dependencies=[Depends(require_roles("AdminGeneral", "TorneoAdmin"))],
)
async def obtener_usuario(
    usuario_id: int,
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
) -> UsuarioOut:
    return await UsuarioService(session).get(usuario_id, usuario_actual)


@router.post(
    "", response_model=UsuarioOut, status_code=201, dependencies=[Depends(require_roles("AdminGeneral"))]
)
async def crear_usuario(data: UsuarioCreate, session: AsyncSession = Depends(get_db)) -> UsuarioOut:
    return await UsuarioService(session).create(data)


@router.patch(
    "/{usuario_id}", response_model=UsuarioOut, dependencies=[Depends(require_roles("AdminGeneral"))]
)
async def actualizar_usuario(
    usuario_id: int,
    data: UsuarioUpdate,
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
) -> UsuarioOut:
    """Rechaza que un AdminGeneral se cambie su propio rol o se desactive a
    sí mismo — chequeo en UsuarioService.update() (T6)."""
    return await UsuarioService(session).update(usuario_id, data, usuario_actual)


@router.delete(
    "/{usuario_id}", response_model=UsuarioOut, dependencies=[Depends(require_roles("AdminGeneral"))]
)
async def dar_de_baja_usuario(
    usuario_id: int,
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
) -> UsuarioOut:
    """Rechaza que un AdminGeneral se desactive a sí mismo — chequeo en
    UsuarioService.soft_delete() (T6)."""
    return await UsuarioService(session).soft_delete(usuario_id, usuario_actual)
