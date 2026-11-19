"""Traducción de excepciones a respuestas HTTP + traducción de errores crudos de Postgres."""
import logging
import uuid

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.core.logging import CABECERA_REQUEST_ID, request_id_actual

from app.exceptions.errors import (
    AuthError,
    ConcurrencyConflictError,
    ConflictError,
    DomainRuleError,
    ForbiddenError,
    LicenseRevokedError,
    NotFoundError,
    PreconditionFailedError,
    RateLimitError,
)

logger = logging.getLogger("score_app.errores")

ERROR_INTERNO = "Error interno."

# TASK-015 (BE-04, SEC-06): el mensaje de Postgres solo sale tal cual cuando
# lo escribió el proyecto (RAISE EXCEPTION de un trigger, P0001). Para las
# restricciones, un texto fijo por tipo: el crudo nombra tablas y
# restricciones. Cualquier otro error de base es un 500 genérico, registrado.
_MENSAJES_RESTRICCION = {
    "23505": "Ya existe un registro con esos datos (restricción de unicidad).",
    "23503": "El registro hace referencia a otro que no existe, o está en uso por otros datos.",
    "23514": "Los datos no cumplen una de las reglas de validación.",
    "23502": "Falta un dato obligatorio.",
    "23P01": "Los datos se superponen con otro registro existente.",
}
_MENSAJE_RESTRICCION_GENERICO = "Los datos entran en conflicto con una restricción."


def _sqlstate(exc: DBAPIError) -> str | None:
    return getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)


def _primera_linea(exc: DBAPIError) -> str:
    """psycopg agrega CONTEXT/DETAIL en líneas siguientes; el mensaje del
    RAISE EXCEPTION es la primera."""
    crudo = str(exc.orig) if exc.orig else str(exc)
    return crudo.strip().splitlines()[0] if crudo.strip() else crudo


def _request_id(request: Request | None) -> str:
    if request is not None:
        guardado = getattr(request.state, "request_id", None)
        if guardado:
            return guardado
    return request_id_actual.get() or str(uuid.uuid4())


def _error_interno(request: Request | None, exc: BaseException) -> JSONResponse:
    """500 sin detalle interno, con un identificador que también queda en el
    registro junto con la traza completa."""
    request_id = _request_id(request)
    logger.error(
        "error no controlado %s %s [%s]",
        request.method if request is not None else "-",
        request.url.path if request is not None else "-",
        request_id,
        exc_info=exc,
        extra={"request_id": request_id},
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": ERROR_INTERNO, "id": request_id},
        headers={CABECERA_REQUEST_ID: request_id},
    )


def _integrity_error_response(exc: IntegrityError) -> JSONResponse:
    mensaje = _MENSAJES_RESTRICCION.get(_sqlstate(exc) or "", _MENSAJE_RESTRICCION_GENERICO)
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": mensaje})


def _dbapi_error_response(exc: DBAPIError, request: Request | None = None) -> JSONResponse:
    sqlstate = _sqlstate(exc)
    # RAISE EXCEPTION en un trigger (fn_validar_jugador_partido,
    # fn_validar_equipos_inscritos) llega acá, no como IntegrityError: es una
    # regla de negocio escrita por el proyecto. SQLSTATE P0001.
    if sqlstate == "P0001":
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": _primera_linea(exc)})
    if sqlstate == "22001":
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": "Uno de los textos es demasiado largo."},
        )
    if sqlstate is not None and sqlstate.startswith("23"):
        return _integrity_error_response(exc)  # type: ignore[arg-type]
    return _error_interno(request, exc)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def _not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": exc.detail})

    @app.exception_handler(ConflictError)
    async def _conflict(_: Request, exc: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": exc.detail})

    @app.exception_handler(DomainRuleError)
    async def _domain_rule(_: Request, exc: DomainRuleError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": exc.detail})

    @app.exception_handler(AuthError)
    async def _auth(_: Request, exc: AuthError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": exc.detail},
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Registrada ANTES de ForbiddenError a propósito, aunque Starlette
    # resuelve por MRO de la excepción (no por orden de registro) — deja
    # explícito en el código que LicenseRevokedError es un caso más
    # específico. `X-License-Revoked` (no un campo en el body) para que
    # `client.ts` distinga esto de un 403 genérico sin clonar el stream de
    # la respuesta (rbac-licencias-torneos-plan.md, D3).
    @app.exception_handler(LicenseRevokedError)
    async def _license_revoked(_: Request, exc: LicenseRevokedError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": exc.detail},
            headers={"X-License-Revoked": "true"},
        )

    @app.exception_handler(ForbiddenError)
    async def _forbidden(_: Request, exc: ForbiddenError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": exc.detail})

    @app.exception_handler(PreconditionFailedError)
    async def _precondition_failed(_: Request, exc: PreconditionFailedError) -> JSONResponse:
        # 412, no 409: el 409 ya está tomado por IntegrityError (abajo) y el
        # cliente tiene que poder distinguir "alguien más editó" de "chocaste
        # contra una restricción de unicidad" — ver PreconditionFailedError.
        return JSONResponse(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            content={"detail": exc.detail, "estado_actual": exc.estado_actual},
        )

    # A1 (docs/plans/cierre-pendientes-todos-plan.md): mismo 409 que
    # IntegrityError (abajo), pero `detail` lleva el código estable
    # `evento_conflicto_concurrente` en vez de un mensaje de Postgres — el
    # frontend discrimina por ESE código, no por status, para ofrecer el
    # botón de reintento (ver docstring de ConcurrencyConflictError).
    @app.exception_handler(ConcurrencyConflictError)
    async def _concurrency_conflict(_: Request, exc: ConcurrencyConflictError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": exc.detail})

    @app.exception_handler(RateLimitError)
    async def _rate_limit(_: Request, exc: RateLimitError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": exc.detail},
            headers={"Retry-After": str(exc.retry_after_seconds)},
        )

    # Red de seguridad: si un repositorio se olvida de atrapar un error de
    # Postgres y lo traduce a una excepción de dominio, esto evita que el
    # mensaje crudo de asyncpg (con el SQL adentro) llegue al cliente como 500.
    @app.exception_handler(IntegrityError)
    async def _sa_integrity(_: Request, exc: IntegrityError) -> JSONResponse:
        return _integrity_error_response(exc)

    @app.exception_handler(DBAPIError)
    async def _sa_dbapi(request: Request, exc: DBAPIError) -> JSONResponse:
        return _dbapi_error_response(exc, request)

    # TASK-015: lo que nadie tradujo. Corre en ServerErrorMiddleware, fuera
    # de RequestIdMiddleware: por eso el identificador viaja en request.state
    # y la cabecera se pone acá.
    @app.exception_handler(Exception)
    async def _inesperado(request: Request, exc: Exception) -> JSONResponse:
        return _error_interno(request, exc)
