"""Traducción de excepciones a respuestas HTTP + traducción de errores crudos de Postgres."""
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.exceptions.errors import (
    AuthError,
    ConflictError,
    DomainRuleError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
)

# asyncpg antepone el SQLSTATE y un preámbulo largo al mensaje. Esto se queda
# solo con la última línea útil, que es la que escribió el RAISE EXCEPTION o
# el motor de constraints (ej: 'llave duplicada viola restricción de unicidad').
def _clean_pg_message(raw: str) -> str:
    line = raw.strip().splitlines()[0] if raw.strip() else raw
    for prefix in ("duplicate key value violates unique constraint",):
        if prefix in line:
            return "Ya existe un registro con esos datos (restricción de unicidad)."
    return line


def _integrity_error_response(exc: IntegrityError) -> JSONResponse:
    message = _clean_pg_message(str(exc.orig) if exc.orig else str(exc))
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": message})


def _dbapi_error_response(exc: DBAPIError) -> JSONResponse:
    # RAISE EXCEPTION en un trigger (fn_validar_jugador_partido,
    # fn_validar_equipos_inscritos) llega acá, no como IntegrityError: no es
    # una FK/UNIQUE/CHECK, es una regla de negocio explícita. SQLSTATE P0001.
    message = _clean_pg_message(str(exc.orig) if exc.orig else str(exc))
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": message})


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

    @app.exception_handler(ForbiddenError)
    async def _forbidden(_: Request, exc: ForbiddenError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": exc.detail})

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
    async def _sa_dbapi(_: Request, exc: DBAPIError) -> JSONResponse:
        return _dbapi_error_response(exc)
