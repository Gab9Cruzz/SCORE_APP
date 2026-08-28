from fastapi import APIRouter, Depends, Request
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
        ip=_ip_del_cliente(request),
        user_agent=request.headers.get("user-agent"),
    )


def _ip_del_cliente(request: Request) -> str | None:
    """La IP real cuando la app corre detrás de un proxy o balanceador.

    `request.client.host` sería la del proxy, no la de quien intentó
    entrar — y una bitácora que anota siempre la misma IP interna no sirve
    para nada. Se prefiere el primer valor de X-Forwarded-For, que es el
    cliente original.

    Ojo con la confianza: ese header lo puede falsificar cualquiera si la
    app queda expuesta directo a internet sin un proxy que lo reescriba.
    Es un dato indicativo para auditar, no una identidad verificada, y no
    se usa para tomar ninguna decisión de autorización."""
    reenviada = request.headers.get("x-forwarded-for")
    if reenviada:
        return reenviada.split(",")[0].strip()
    return request.client.host if request.client else None


@router.get("/me", response_model=UsuarioOut)
async def me(usuario: Usuario = Depends(get_current_user)) -> Usuario:
    return usuario
