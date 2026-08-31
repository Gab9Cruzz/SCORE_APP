"""Utilidades mínimas sobre `Request` compartidas entre rutas/dependencias."""
from fastapi import Request


def ip_del_cliente(request: Request | None) -> str | None:
    """La IP real cuando la app corre detrás de un proxy o balanceador.

    `request.client.host` sería la del proxy, no la de quien hizo el
    pedido — un registro que siempre anota la misma IP interna no sirve
    para auditar nada. Se prefiere el primer valor de X-Forwarded-For, el
    cliente original.

    Ojo con la confianza: ese header lo puede falsificar cualquiera si la
    app queda expuesta directo a internet sin un proxy que lo reescriba.
    Es un dato indicativo para auditar, no una identidad verificada, y no
    se usa para tomar ninguna decisión de autorización.

    Compartida por `routes/auth.py` (ACCESOS) y `api/deps.py` (AUDITORIA) —
    las dos bitácoras del proyecto quieren exactamente el mismo criterio de
    "de dónde vino esto".
    """
    if request is None:
        return None
    reenviada = request.headers.get("x-forwarded-for")
    if reenviada:
        return reenviada.split(",")[0].strip()
    return request.client.host if request.client else None
