# Infrastructure

`docker-compose.yml` levanta **Postgres + la API** (`/backend`), los dos en
contenedor (DX-2, docs/plans/cierre-pendientes-todos-plan.md). El servicio
`postgres` monta `../database` como `docker-entrypoint-initdb.d`: en la
primera inicialización (volumen de datos vacío), la imagen oficial corre
todos los `.sql` de ahí en orden — el esquema completo (`01_schema.sql`
hasta la última migración) queda cargado solo, sin depender de que ya
tengas Postgres instalado en el host con `torneos_mvp` armado a mano. Esa
suposición era justo lo que rompía a la segunda persona que clonaba el
repo.

## Uso

```bash
cd infrastructure
docker compose up --build
```

API en http://localhost:8000/docs. Postgres queda expuesto en
`localhost:5432` (usuario `postgres`, clave `1234`, base `torneos_mvp`) por
si querés conectarte con un cliente SQL aparte.

`JWT_SECRET_KEY` y `ADMIN_PASSWORD` son obligatorios — no tienen default
(a propósito: un default hardcodeado acá terminaría siendo un secreto
público). Exportalos antes de levantar el compose (o creá un `.env` en esta
carpeta — docker compose lo lee solo):

```bash
JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))") \
ADMIN_PASSWORD=una-clave-real \
docker compose up --build
```

Con `ENTORNO=produccion` la API se niega a arrancar si `JWT_SECRET_KEY`
tiene menos de 32 caracteres o es el de ejemplo, si `ADMIN_PASSWORD` es un
valor de ejemplo o tiene menos de 12, o si `CORS_ORIGINS` es `*` (en ese
caso, pasá los orígenes del frontend separados por coma). El error dice
qué variable corregir. Por defecto el compose usa `ENTORNO=desarrollo`.

Para reiniciar la base desde cero (ej. después de cambiar el esquema en
`/database`), `docker compose down -v` borra el volumen `postgres-data` —
la próxima `up` la recrea corriendo `initdb/00_init.sh` de nuevo.

## Qué carga la primera inicialización

`initdb/00_init.sh` carga `01`–`06` (el esquema final y los datos mínimos)
y `11_catalogo_disciplinas.sql`. **No** corre las migraciones `07`+: son
historia ya incorporada a `01`–`06` y varias no aplican sobre el esquema
actual (ver `database/README.md`).

### Datos de demostración (opcional)

Con el compose levantado:

```bash
docker compose exec -T postgres psql -U postgres -d torneos_mvp -v ON_ERROR_STOP=1 -1 -f /database/10_demo_torneos_admin.sql
docker compose exec -T postgres psql -U postgres -d torneos_mvp -v ON_ERROR_STOP=1 -1 -f /database/seed_portal_demo.sql
```

## Postgres en el host, en vez del contenedor

Si preferís seguir usando un Postgres que ya tenés instalado (el
comportamiento de antes de DX-2): comentá el servicio `postgres` de
`docker-compose.yml`, sacale el `depends_on` al servicio `api`, y volvé
`DATABASE_URL` a `postgresql+psycopg://postgres:1234@host.docker.internal:5432/torneos_mvp`
(`extra_hosts` ya deja `host.docker.internal` resuelto en Windows/Mac/Linux).

## Sin Docker

Ver la sección "Correr local" en [`/backend/README.md`](../backend/README.md).
