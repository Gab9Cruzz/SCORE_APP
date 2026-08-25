"""Arranque alternativo para Windows.

`uvicorn app.main:app` fuerza ProactorEventLoop en Windows (lo necesita
`--reload` para poder lanzar subprocesos) y asyncpg/psycopg en modo async
no funcionan sobre ese loop ahí: toda conexión falla con WinError 64
("ConnectionResetError") o, con psycopg, directamente lo rechaza con un
error explícito. SelectorEventLoop sí funciona.

Este script arma el servidor a mano (`uvicorn.Server(...).serve()`) en vez
de usar `uvicorn.run()`, que es donde uvicorn decide forzar Proactor —
así el loop queda con SelectorEventLoop de punta a punta. Contrapartida:
sin `--reload` (SelectorEventLoop no soporta subprocesos en Windows).

Uso:  python run.py
En Linux/Mac esto no hace falta — ahí `uvicorn app.main:app --reload`
anda directo, y así es como corre igual dentro de Docker (ver /infrastructure).
"""
import asyncio
import selectors

import uvicorn


def main() -> None:
    config = uvicorn.Config("app.main:app", host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)
    asyncio.run(
        server.serve(),
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()),
    )


if __name__ == "__main__":
    main()
