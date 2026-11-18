#!/usr/bin/env bash
# TASK-006 (OPS-01): inicialización de la base del compose.
#
# La imagen oficial de PostgreSQL ejecuta lo que hay en
# /docker-entrypoint-initdb.d solo la primera vez (volumen de datos vacío).
# Antes se montaba ahí la carpeta database/ entera, y eso corría también las
# migraciones históricas (07+), que no aplican sobre el esquema final:
# 08 referencia DISCIPLINA.Tipo y abortaba la inicialización a medias.
#
# Una instalación nueva es exactamente esto (ver database/README.md):
#   01–06  el esquema final y los datos mínimos
#   11     el catálogo de disciplinas y modalidades
# Los datos de demostración (10_demo_torneos_admin.sql, seed_portal_demo.sql)
# son opcionales y se cargan a mano: ver infrastructure/README.md.
#
# SQL_DIR y la conexión se pueden cambiar por variables de entorno para
# probar el script fuera del contenedor.
#
# Sin `set -u`: si el archivo pierde el bit de ejecución, la imagen lo
# carga con `source` en su propio shell, y `-u` se filtraría a él.
set -eo pipefail

SQL_DIR="${SQL_DIR:-/database}"
BASE="${POSTGRES_DB:-torneos_mvp}"
USUARIO="${POSTGRES_USER:-postgres}"

for archivo in \
    01_schema.sql \
    02_constraints.sql \
    03_indexes.sql \
    04_views.sql \
    05_seed.sql \
    06_triggers.sql \
    11_catalogo_disciplinas.sql
do
    echo "initdb: $archivo"
    # -1: cada archivo en una sola transacción, igual que una migración.
    psql -v ON_ERROR_STOP=1 -q -1 --username "$USUARIO" --dbname "$BASE" -f "$SQL_DIR/$archivo"
done

echo "initdb: esquema cargado en $BASE"
