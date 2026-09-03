"""Dependencias compartidas: sesión de DB, usuario autenticado, chequeo de rol."""
from collections.abc import Callable

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auditoria import set_actor
from app.core.config import get_settings
from app.core.http import ip_del_cliente
from app.core.security import decode_access_token
from app.db.session import get_db
from app.exceptions.errors import AuthError, ForbiddenError, LicenseRevokedError
from app.models.usuario import Usuario
from app.repositories.asignacion_torneo_admin import AsignacionTorneoAdminRepository
from app.repositories.usuario import UsuarioRepository

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login", auto_error=False)


async def _resolver_usuario_autenticado(token: str | None, session: AsyncSession) -> Usuario | None:
    """Decodifica el token y resuelve la cuenta, chequeando Estado — pero
    NO Licencia_Activa (rbac-licencias-torneos-plan.md, hallazgo de la voz
    externa en la revisión CEO): `get_current_user` y
    `get_current_user_optional` necesitan reaccionar distinto a una
    licencia revocada (403 explícito vs. `None` silencioso), así que ese
    chequeo vive en cada caller, no acá. Antes de esta extracción,
    `get_current_user_optional` reimplementaba este mismo bloque de forma
    independiente — un segundo choke point que un chequeo nuevo (como el
    de licencia) podía terminar parchando en uno solo de los dos por
    accidente. Devuelve `None` para CUALQUIER motivo de identidad inválida
    (sin token, token corrupto/expirado, cuenta inexistente o inactiva) —
    el llamador decide si eso es un 401 o un `None` silencioso."""
    if token is None:
        return None
    payload = decode_access_token(token)
    if payload is None or "sub" not in payload:
        return None
    usuario = await UsuarioRepository(session).get_by_username(payload["sub"])
    if usuario is None or usuario.estado != "Activo":
        return None
    return usuario


async def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db),
) -> Usuario:
    usuario = await _resolver_usuario_autenticado(token, session)
    if usuario is None:
        raise AuthError("Falta el token de autenticación.") if token is None else AuthError(
            "Usuario inválido o inactivo."
        )
    # Kill switch de licencia (rbac-licencias-torneos-plan.md, D2a): se
    # chequea fresco en cada request, DESPUÉS de resolver identidad/estado
    # — un 403 de licencia siempre gana sobre cualquier chequeo posterior
    # (ej. require_torneo_access), nunca al revés. No vive en el JWT: así
    # la revocación es inmediata, sin esperar a que expire el token.
    if not usuario.licencia_activa:
        raise LicenseRevokedError()
    # Deja el actor listo en el contextvar de app/core/auditoria.py ANTES
    # de que el endpoint haga nada — así cualquier escritura que dispare
    # (venga de un repo, un service con session.add() directo, o lo que
    # sea) ya encuentra quién la hizo. Ver ese módulo para el porqué de
    # contextvars en vez de pasar usuario_actual a cada repositorio.
    set_actor(usuario_id=usuario.id, ip=ip_del_cliente(request), user_agent=request.headers.get("user-agent"))
    return usuario


async def get_current_user_optional(
    token: str | None = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db),
) -> Usuario | None:
    """Igual que `get_current_user`, pero nunca levanta 401/403 — devuelve
    None si no hay token, es inválido, o la licencia está revocada. Para
    GETs que siguen siendo públicos (no requieren login) pero necesitan
    distinguir "anónimo" de "logueado" para decidir cuánto exponer en la
    respuesta (ver JugadorPublicOut, equipos-jugadores-plan.md — PII como
    cédula/correo no debe salir para un caller anónimo, pero el admin
    logueado sigue viéndola en la misma ruta). Una cuenta con la licencia
    recién revocada se trata igual que "sin sesión" acá: no debe seguir
    viendo lo que solo un logueado ve, aunque este endpoint en particular
    no tire un 403 duro (rbac-licencias-torneos-plan.md, hallazgo de la
    voz externa — antes de este fix, este segundo camino quedaba sin
    chequeo de licencia)."""
    usuario = await _resolver_usuario_autenticado(token, session)
    if usuario is None or not usuario.licencia_activa:
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


async def _verificar_acceso_torneo(
    usuario: Usuario, torneo_id: int, session: AsyncSession, roles_sin_scoping: tuple[str, ...] = ()
) -> None:
    """Núcleo compartido de `require_torneo_access`/`require_torneo_access_de`
    (rbac-licencias-torneos-plan.md, §4.3 + Fase 2). AdminGeneral: bypass
    total, mismo criterio que `require_roles`. `roles_sin_scoping`: roles
    que YA tienen su propio ownership-check río abajo (ej. Arbitro vía
    `verificar_arbitro_asignado`, `services/permisos.py`) — pasan sin que
    ESTE chequeo les exija además una asignación de torneo; aplicarles el
    scoping de TorneoAdmin sería incorrecto, no más estricto (Arbitro no
    tiene ni necesita filas en ASIGNACION_TORNEO_ADMIN). TorneoAdmin:
    exige una fila Activa en esa tabla para `torneo_id`."""
    if usuario.rol == "AdminGeneral" or usuario.rol in roles_sin_scoping:
        return
    if usuario.rol != "TorneoAdmin":
        roles_validos = ("TorneoAdmin", *roles_sin_scoping)
        raise ForbiddenError(f"Esta operación requiere {' o '.join(roles_validos)}.")
    tiene_acceso = await AsignacionTorneoAdminRepository(session).existe_activa(
        usuario_id=usuario.id, torneo_id=torneo_id
    )
    if not tiene_acceso:
        raise ForbiddenError(
            "No tenés este torneo asignado. Pedile a tu Admin General "
            "que te lo asigne desde el panel de usuarios."
        )


def require_torneo_access(*roles_sin_scoping: str) -> Callable:
    """Uso: Depends(require_torneo_access()) en una ruta con `torneo_id`
    en el path (rbac-licencias-torneos-plan.md, §4.3). Para rutas
    compartidas con Arbitro (que ya tiene su propio ownership-check, ej.
    `partidos.py`), pasar el rol explícito:
    `Depends(require_torneo_access("Arbitro"))`.

    `get_current_user` (arriba) ya bloqueó "sin licencia" antes de que
    esto se evalúe — FastAPI resuelve esa dependencia primero, así que acá
    solo hace falta preocuparse por la asignación, no por la licencia otra
    vez."""

    async def _checker(
        torneo_id: int,
        usuario: Usuario = Depends(get_current_user),
        session: AsyncSession = Depends(get_db),
    ) -> Usuario:
        await _verificar_acceso_torneo(usuario, torneo_id, session, roles_sin_scoping)
        return usuario

    return _checker


def require_torneo_access_de(resolver: Callable[..., object], *roles_sin_scoping: str) -> Callable:
    """Variante de `require_torneo_access` para rutas donde `torneo_id` NO
    es un path param directo (rbac-licencias-torneos-plan.md, Fase 2 —
    la mayoría de los 8 routers de esta fase: `inscripciones.py`,
    `plantillas.py`, `traspasos.py`, `eventos_partido.py`, `grupos.py`,
    `registro_lote.py`, y parte de `partidos.py`).

    `resolver` es un callable async (con sus propios path params/body vía
    los parámetros normales de FastAPI, como cualquier dependency) que
    resuelve `torneo_id` desde el recurso indirecto — ej. cargar un
    `Partido` por `partido_id` y devolver `partido.torneo_id`. Vive cada
    uno junto al router que lo usa (no acá): cada resolver depende de un
    modelo distinto y centralizarlos acá ensuciaría este archivo con
    imports de todo el dominio."""

    async def _checker(
        usuario: Usuario = Depends(get_current_user),
        session: AsyncSession = Depends(get_db),
        torneo_id: int = Depends(resolver),
    ) -> Usuario:
        await _verificar_acceso_torneo(usuario, torneo_id, session, roles_sin_scoping)
        return usuario

    return _checker
