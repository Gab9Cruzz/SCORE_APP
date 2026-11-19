"""TASK-046: base vacía para los recorridos de extremo a extremo.

Borra y recrea la base de `E2E_DATABASE_URL` con el mismo esquema que carga
`infrastructure/initdb/00_init.sh` en el contenedor (01-06 + catálogo de
disciplinas), sin datos de demostración: cada recorrido crea lo suyo por la
API. Solo acepta bases cuyo nombre termine en `_e2e`, para que un valor mal
puesto no borre la base de desarrollo.
"""
import asyncio
import os
import pathlib
import sys

import asyncpg

RAIZ = pathlib.Path(__file__).resolve().parents[2]
ARCHIVOS = [
    "01_schema.sql",
    "02_constraints.sql",
    "03_indexes.sql",
    "04_views.sql",
    "05_seed.sql",
    "06_triggers.sql",
    "11_catalogo_disciplinas.sql",
]


def _dsn(url: str) -> tuple[str, str]:
    """`postgresql+psycopg://u:p@host:5432/base` → (dsn sin la base, base)."""
    url = url.replace("postgresql+psycopg://", "postgresql://").replace("postgresql+asyncpg://", "postgresql://")
    servidor, base = url.rsplit("/", 1)
    return servidor, base.split("?", 1)[0]


async def main() -> None:
    url = os.environ.get("E2E_DATABASE_URL", "postgresql+psycopg://postgres:1234@localhost:5432/torneos_e2e")
    servidor, base = _dsn(url)
    if not base.endswith("_e2e"):
        sys.exit(f"E2E_DATABASE_URL apunta a '{base}': solo se recrean bases que terminan en _e2e.")

    mantenimiento = await asyncpg.connect(f"{servidor}/postgres")
    try:
        await mantenimiento.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = $1 AND pid <> pg_backend_pid()",
            base,
        )
        await mantenimiento.execute(f'DROP DATABASE IF EXISTS "{base}"')
        await mantenimiento.execute(f'CREATE DATABASE "{base}"')
    finally:
        await mantenimiento.close()

    conexion = await asyncpg.connect(f"{servidor}/{base}")
    try:
        for archivo in ARCHIVOS:
            async with conexion.transaction():
                await conexion.execute((RAIZ / "database" / archivo).read_text(encoding="utf-8"))
    finally:
        await conexion.close()
    print(f"e2e: base {base} lista ({len(ARCHIVOS)} archivos)", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
