from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.auth import Token
from app.schemas.usuario import UsuarioOut
from app.services.usuario import UsuarioService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_db),
) -> Token:
    return await UsuarioService(session).login(form_data.username, form_data.password)


@router.get("/me", response_model=UsuarioOut)
async def me(usuario: Usuario = Depends(get_current_user)) -> Usuario:
    return usuario
