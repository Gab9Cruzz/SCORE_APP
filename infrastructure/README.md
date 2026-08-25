# Infrastructure

`docker-compose.yml` levanta la API (`/backend`) en un contenedor y la
conecta al PostgreSQL que ya corre en el host (`torneos_mvp`, ver
`/database`) vía `host.docker.internal`. Postgres mismo **no** corre en
Docker acá — ya está instalado y con el esquema cargado en la máquina.

## Uso

```bash
cd infrastructure
docker compose up --build
```

API en http://localhost:8000/docs

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

Si tu Postgres no está en `localhost:5432` con `postgres`/`1234`, editá la
variable `DATABASE_URL` en `docker-compose.yml`.

## Sin Docker

Ver la sección "Correr local" en [`/backend/README.md`](../backend/README.md).
