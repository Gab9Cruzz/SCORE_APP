"""Dependencias compartidas: sesión de DB, usuario autenticado, chequeo de rol."""
from collections.abc import Callable

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.exceptions.errors import AuthError, ForbiddenError
from app.models.usuario import Usuario
from app.repositories.usuario import UsuarioRepository

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login", auto_error=False)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db),
) -> Usuario:
    if token is None:
        raise AuthError("Falta el token de autenticación.")
    payload = decode_access_token(token)
    if payload is None or "sub" not in payload:
        raise AuthError("Token inválido o expirado.")
    usuario = await UsuarioRepository(session).get_by_username(payload["sub"])
    if usuario is None or usuario.estado != "Activo":
        raise AuthError("Usuario inválido o inactivo.")
    return usuario


def require_roles(*roles: str) -> Callable:
    """Uso: Depends(require_roles("Admin")) o Depends(require_roles("Admin", "Arbitro"))."""

    async def _checker(usuario: Usuario = Depends(get_current_user)) -> Usuario:
        if usuario.rol not in roles:
            raise ForbiddenError(
                f"Esta operación requiere rol {' o '.join(roles)} (tenés: {usuario.rol})."
            )
        return usuario

    return _checker
