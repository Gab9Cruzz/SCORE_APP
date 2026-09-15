"""Logging estructurado para métricas de uso (portal-publico-feed-partidos-
plan.md, C6/C20/F13). El backend hoy no tiene logger ni handler
(`grep -rn "import logging" backend/app` daba cero hits antes de esto; el
patrón era `print()` en `main.py`) — bajo el formateador por defecto de
uvicorn, `logger.info(..., extra={...})` descarta los campos de `extra`,
así que no alcanza con `logging.getLogger(__name__)` a secas.

Formato de línea (F13), a stdout: `{"evt": ..., ...campos, "ts": ...}` —
JSON de una línea, sin IP ni user-agent ni ningún dato personal. Retención:
la que ya tenga configurada la infraestructura de stdout del deploy (no se
agrega infraestructura nueva, C6 lo pide explícito) — ver el runbook.

Conteo: `grep '"evt": "torneo_hit"' <log> | wc -l` (o el equivalente del
log aggregator del entorno) — el mismo comando cuenta `feed_hit` cambiando
el valor. Ver docs/runbook-portal-publico.md.
"""
import json
import logging
import sys
import time

metricas_logger = logging.getLogger("score_app.metricas")
metricas_logger.setLevel(logging.INFO)
metricas_logger.propagate = False

if not metricas_logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    metricas_logger.addHandler(_handler)


def registrar_evento(evento: str, **campos: object) -> None:
    """Emite una línea JSON a stdout. `campos` son los datos propios del
    evento (nunca IP/user-agent/PII) — `evt` y `ts` se agregan acá."""
    linea = {"evt": evento, **campos, "ts": time.time()}
    metricas_logger.info(json.dumps(linea, default=str))
