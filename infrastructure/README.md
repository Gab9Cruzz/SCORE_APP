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

`JWT_SECRET_KEY` es obligatorio — no tiene default (a propósito: un default
hardcodeado acá terminaría siendo un secreto público). Exportalo antes de
levantar el compose (o creá un `.env` en esta carpeta — docker compose lo
lee solo). `ADMIN_PASSWORD` sí tiene default (`admin1234`) para desarrollo,
pero conviene cambiarlo del mismo modo antes de cualquier entorno real:

```bash
JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))") \
ADMIN_PASSWORD=una-clave-real \
docker compose up --build
```

Para reiniciar la base desde cero (ej. después de cambiar el esquema en
`/database`), `docker compose down -v` borra el volumen `postgres-data` —
la próxima `up` la recrea corriendo los `.sql` de nuevo.

## Postgres en el host, en vez del contenedor

Si preferís seguir usando un Postgres que ya tenés instalado (el
comportamiento de antes de DX-2): comentá el servicio `postgres` de
`docker-compose.yml`, sacale el `depends_on` al servicio `api`, y volvé
`DATABASE_URL` a `postgresql+psycopg://postgres:1234@host.docker.internal:5432/torneos_mvp`
(`extra_hosts` ya deja `host.docker.internal` resuelto en Windows/Mac/Linux).

## Sin Docker

Ver la sección "Correr local" en [`/backend/README.md`](../backend/README.md).
