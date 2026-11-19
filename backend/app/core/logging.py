"""Registro de la aplicación (TASK-015, BE-04/SEC-06).

Una línea JSON por evento a stdout, con el identificador de la petición en
curso (`request_id`), que también va en la cabecera `X-Request-ID` de la
respuesta y en el cuerpo de un 500: quien reporta un error puede dar ese
identificador y se encuentra la línea exacta con la traza.

Logger raíz de la aplicación: "score_app" (los módulos usan
`logging.getLogger("score_app.<algo>")`). `score_app.metricas` tiene su
propio formato y no propaga (ver core/metricas.py).
"""
import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

CABECERA_REQUEST_ID = "X-Request-ID"

request_id_actual: ContextVar[str | None] = ContextVar("request_id_actual", default=None)

logger = logging.getLogger("score_app")


class _FormatoJSON(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        linea = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "nivel": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None) or request_id_actual.get()
        if request_id:
            linea["request_id"] = request_id
        if record.exc_info:
            linea["traza"] = self.formatException(record.exc_info)
        return json.dumps(linea, ensure_ascii=False)


def configurar_logging() -> None:
    """Idempotente: llamarlo dos veces no duplica el handler."""
    if any(getattr(h, "_score_app", False) for h in logger.handlers):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_FormatoJSON())
    handler._score_app = True  # type: ignore[attr-defined]
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def _request_id_valido(valor: str | None) -> str | None:
    """Se respeta el identificador que manda un proxy solo si es un UUID:
    la cabecera llega del exterior y termina en los registros."""
    if not valor:
        return None
    try:
        return str(uuid.UUID(valor))
    except ValueError:
        return None


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = _request_id_valido(request.headers.get(CABECERA_REQUEST_ID)) or str(uuid.uuid4())
        token = request_id_actual.set(request_id)
        # También en request.state: el handler de errores no capturados corre
        # fuera de este middleware (ServerErrorMiddleware) y lo lee de ahí.
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        finally:
            request_id_actual.reset(token)
        response.headers[CABECERA_REQUEST_ID] = request_id
        return response
