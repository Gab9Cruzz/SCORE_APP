from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.http import ip_del_cliente
from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.auth import Token
from app.schemas.usuario import UsuarioOut
from app.services.usuario import UsuarioService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_db),
) -> Token:
    """Todo intento —exitoso o no— queda registrado en ACCESOS
    (UsuarioService.login). El Request se pide solo para eso: es acá donde
    vive el dato de red, y el service no debería depender de FastAPI para
    conocerlo."""
    return await UsuarioService(session).login(
        form_data.username,
        form_data.password,
        ip=ip_del_cliente(request),
        user_agent=request.headers.get("user-agent"),
    )


@router.get("/me", response_model=UsuarioOut)
async def me(usuario: Usuario = Depends(get_current_user)) -> Usuario:
    return usuario
