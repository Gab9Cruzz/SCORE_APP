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


async def get_current_user_optional(
    token: str | None = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db),
) -> Usuario | None:
    """Igual que `get_current_user`, pero nunca levanta 401 — devuelve None
    si no hay token o es inválido. Para GETs que siguen siendo públicos
    (no requieren login) pero necesitan distinguir "anónimo" de "logueado"
    para decidir cuánto exponer en la respuesta (ver JugadorPublicOut,
    equipos-jugadores-plan.md — PII como cédula/correo no debe salir para
    un caller anónimo, pero el admin logueado sigue viéndola en la misma
    ruta)."""
    if token is None:
        return None
    payload = decode_access_token(token)
    if payload is None or "sub" not in payload:
        return None
    usuario = await UsuarioRepository(session).get_by_username(payload["sub"])
    if usuario is None or usuario.estado != "Activo":
        return None
    return usuario


def require_roles(*roles: str) -> Callable:
    """Uso: Depends(require_roles("TorneoAdmin")) o Depends(require_roles("TorneoAdmin", "Arbitro")).

    AdminGeneral no hace falta pasarlo en `roles`: pasa cualquier chequeo vía
    el bypass de abajo, centralizado acá en vez de enumerado en cada uno de
    los routers (ver roles-3-modulos-plan.md, Fase 1, D3). La única
    excepción real es usuarios.py, que sí llama a
    require_roles("AdminGeneral") explícito — ahí el bypass y el chequeo
    literal coinciden, así que no necesita tratamiento especial acá.
    """

    async def _checker(usuario: Usuario = Depends(get_current_user)) -> Usuario:
        if usuario.rol == "AdminGeneral" or usuario.rol in roles:
            return usuario
        raise ForbiddenError(
            f"Esta operación requiere rol {' o '.join(roles)} (tenés: {usuario.rol})."
        )

    return _checker
