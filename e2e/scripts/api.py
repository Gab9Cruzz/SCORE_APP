"""TASK-046: la API para los recorridos, en el puerto `E2E_API_PORT`.

Igual que `backend/run.py` (bucle con selectores, que en Windows necesita
psycopg en modo async), pero con puerto configurable para no chocar con una
API de desarrollo en el 8000.
"""
import asyncio
import os
import pathlib
import selectors
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "backend"))

import uvicorn  # noqa: E402


def main() -> None:
    puerto = int(os.environ.get("E2E_API_PORT", "8100"))
    config = uvicorn.Config("app.main:app", host="127.0.0.1", port=puerto, log_level="warning")
    servidor = uvicorn.Server(config)
    asyncio.run(servidor.serve(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))


if __name__ == "__main__":
    main()
