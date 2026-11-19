"""Ejecutor de migraciones con registro (TASK-031, ARQ-01/DB-10/OPS-10).

Cada base guarda en SCHEMA_MIGRATIONS qué migraciones (`database/NN_migracion_*.sql`)
tiene aplicadas. Este script compara esa tabla con los archivos y aplica lo
pendiente, cada migración en su propia transacción junto con su registro:
si una falla, no deja ni cambios ni registro.

Una instalación nueva (01–06) ya trae registradas como aplicadas todas las
migraciones que incorpora, así que acá no tiene nada pendiente.

Uso, desde backend/ (lee DATABASE_URL de .env):

    python -m scripts.migrar               # estado: aplicadas y pendientes
    python -m scripts.migrar --aplicar     # aplica las pendientes, en orden
    python -m scripts.migrar --marcar-hasta 41
        # da de alta una base existente: marca como aplicadas las
        # migraciones hasta la 41 SIN ejecutarlas

El procedimiento de database/README.md sigue valiendo: copia de seguridad
primero y ensayo en una base descartable. Esto reemplaza solo el paso de
`psql -1`.
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import re
import sys

import psycopg

DIRECTORIO_POR_DEFECTO = pathlib.Path(__file__).resolve().parents[2] / "database"
PATRON = re.compile(r"^(\d+)_migracion_.+\.sql$")

CREAR_TABLA = """
CREATE TABLE IF NOT EXISTS SCHEMA_MIGRATIONS (
    Nombre VARCHAR(200) PRIMARY KEY,
    Aplicada_En TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Checksum VARCHAR(64)
)
"""


def numero(nombre: str) -> int:
    m = PATRON.match(nombre)
    if m is None:
        raise ValueError(f"No es una migración: {nombre}")
    return int(m.group(1))


def listar_migraciones(directorio: pathlib.Path = DIRECTORIO_POR_DEFECTO) -> list[pathlib.Path]:
    archivos = [p for p in directorio.iterdir() if PATRON.match(p.name)]
    return sorted(archivos, key=lambda p: (numero(p.name), p.name))


def checksum(archivo: pathlib.Path) -> str:
    return hashlib.sha256(archivo.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def aplicadas(conn: psycopg.Connection) -> set[str]:
    with conn.transaction():
        conn.execute(CREAR_TABLA)
        return {fila[0] for fila in conn.execute("SELECT Nombre FROM SCHEMA_MIGRATIONS")}


def pendientes(conn: psycopg.Connection, directorio: pathlib.Path = DIRECTORIO_POR_DEFECTO) -> list[pathlib.Path]:
    hechas = aplicadas(conn)
    return [p for p in listar_migraciones(directorio) if p.name not in hechas]


def aplicar(conn: psycopg.Connection, directorio: pathlib.Path = DIRECTORIO_POR_DEFECTO) -> list[str]:
    """Aplica las pendientes en orden; se detiene en la primera que falle
    (esa queda sin cambios ni registro; las anteriores ya quedaron)."""
    aplicadas_ahora = []
    for archivo in pendientes(conn, directorio):
        with conn.transaction():
            conn.execute(archivo.read_text(encoding="utf-8"))
            conn.execute(
                "INSERT INTO SCHEMA_MIGRATIONS (Nombre, Checksum) VALUES (%s, %s)",
                (archivo.name, checksum(archivo)),
            )
        aplicadas_ahora.append(archivo.name)
    return aplicadas_ahora


def marcar_hasta(conn: psycopg.Connection, hasta: int, directorio: pathlib.Path = DIRECTORIO_POR_DEFECTO) -> list[str]:
    marcadas = []
    with conn.transaction():
        conn.execute(CREAR_TABLA)
        for archivo in listar_migraciones(directorio):
            if numero(archivo.name) <= hasta:
                cur = conn.execute(
                    "INSERT INTO SCHEMA_MIGRATIONS (Nombre, Checksum) VALUES (%s, %s) ON CONFLICT (Nombre) DO NOTHING",
                    (archivo.name, checksum(archivo)),
                )
                if cur.rowcount:
                    marcadas.append(archivo.name)
    return marcadas


def dsn_desde_settings() -> str:
    from app.core.config import get_settings

    return get_settings().database_url.replace("postgresql+psycopg://", "postgresql://", 1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Estado y aplicación de migraciones (database/NN_migracion_*.sql).")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--aplicar", action="store_true", help="aplica las migraciones pendientes")
    grupo.add_argument("--marcar-hasta", type=int, metavar="NN", help="marca como aplicadas hasta NN, sin ejecutarlas")
    parser.add_argument("--dsn", help="cadena de conexión (por defecto, DATABASE_URL de .env)")
    args = parser.parse_args(argv)

    with psycopg.connect(args.dsn or dsn_desde_settings(), autocommit=True) as conn:
        if args.marcar_hasta is not None:
            marcadas = marcar_hasta(conn, args.marcar_hasta)
            print(f"Marcadas como aplicadas: {len(marcadas)}")
            for nombre in marcadas:
                print(f"  {nombre}")
            return 0
        if args.aplicar:
            try:
                hechas = aplicar(conn)
            except psycopg.Error as exc:
                print(f"Falló una migración; se detuvo sin aplicarla: {exc}", file=sys.stderr)
                return 1
            print("Nada pendiente." if not hechas else f"Aplicadas: {', '.join(hechas)}")
            return 0
        faltan = pendientes(conn)
        if not faltan:
            print("Nada pendiente.")
        else:
            print(f"Pendientes ({len(faltan)}):")
            for archivo in faltan:
                print(f"  {archivo.name}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
