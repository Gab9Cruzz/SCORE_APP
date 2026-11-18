"""Utilidades mínimas sobre `Request` compartidas entre rutas/dependencias."""
from fastapi import Request

from app.core.config import get_settings


def ip_del_cliente(request: Request | None) -> str | None:
    """La IP de quien hizo el pedido.

    Por defecto es la de la conexión (`request.client.host`). Detrás de un
    proxy o balanceador esa sería la del proxy, así que se toma el primer
    valor de X-Forwarded-For (el cliente original), pero **solo si la
    conexión viene de un proxy listado en `TRUSTED_PROXIES`**. Sin esa
    condición la cabecera la puede inventar cualquiera, y el límite de
    intentos de login, que cuenta por (usuario, IP), se eludía mandando una
    IP distinta en cada intento (TASK-004, SEC-01).

    Compartida por `routes/auth.py` (ACCESOS y límite de login) y
    `api/deps.py` (AUDITORIA): las dos bitácoras quieren el mismo criterio
    de "de dónde vino esto".
    """
    if request is None:
        return None
    directa = request.client.host if request.client else None
    if directa is not None and directa in get_settings().trusted_proxies_list:
        reenviada = request.headers.get("x-forwarded-for")
        if reenviada:
            return reenviada.split(",")[0].strip() or directa
    return directa
