from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.schemas.usuario import RolUsuario, UsuarioCreate, UsuarioOut, UsuarioUpdate
from app.services.usuario import UsuarioService

# Gestión de cuentas (Admin, Arbitro, Publico). Todo el router exige Admin:
# es quien da de alta árbitros y otros admins (ver core/security.py + bootstrap
# del primer Admin en app/main.py).
router = APIRouter(prefix="/usuarios", tags=["Usuarios"], dependencies=[Depends(require_roles("Admin"))])


@router.get("", response_model=list[UsuarioOut])
async def listar_usuarios(
    skip: int = 0,
    limit: int = Query(default=100, le=200),
    rol: RolUsuario | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[UsuarioOut]:
    return await UsuarioService(session).list(skip=skip, limit=limit, rol=rol)


@router.get("/{usuario_id}", response_model=UsuarioOut)
async def obtener_usuario(usuario_id: int, session: AsyncSession = Depends(get_db)) -> UsuarioOut:
    return await UsuarioService(session).get(usuario_id)


@router.post("", response_model=UsuarioOut, status_code=201)
async def crear_usuario(data: UsuarioCreate, session: AsyncSession = Depends(get_db)) -> UsuarioOut:
    return await UsuarioService(session).create(data)


@router.patch("/{usuario_id}", response_model=UsuarioOut)
async def actualizar_usuario(
    usuario_id: int, data: UsuarioUpdate, session: AsyncSession = Depends(get_db)
) -> UsuarioOut:
    return await UsuarioService(session).update(usuario_id, data)


@router.delete("/{usuario_id}", response_model=UsuarioOut)
async def dar_de_baja_usuario(usuario_id: int, session: AsyncSession = Depends(get_db)) -> UsuarioOut:
    return await UsuarioService(session).soft_delete(usuario_id)
