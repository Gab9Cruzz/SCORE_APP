import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.db.database import async_session_factory
from app.exceptions.handlers import register_exception_handlers
from app.services.usuario import UsuarioService

settings = get_settings()


async def _bootstrap_admin_con_reintentos() -> None:
    """Crea el primer Admin si usuarios está vacía (ver bootstrap_admin_si_no_existe).

    Reintenta porque la primerísima conexión asyncpg que abre un proceso
    recién arrancado puede fallar una vez por una condición de carrera
    transitoria del socket (visto tanto en Windows/ProactorEventLoop como en
    arranques con Postgres en un contenedor que aún no aceptó conexiones),
    aunque la base esté sana. Corre en background (ver lifespan): así un
    Postgres caído en el arranque no tumba el server entero — /health sigue
    respondiendo y el resto de los endpoints funcionan igual, solo que sin
    el Admin bootstrap hasta que la base vuelva.
    """
    for intento in range(5):
        try:
            async with async_session_factory() as session:
                creado = await UsuarioService(session).bootstrap_admin_si_no_existe(
                    settings.admin_username, settings.admin_password, settings.admin_nombre
                )
                if creado:
                    print(f"[bootstrap] Usuario Admin '{creado.username}' creado.")
            return
        except Exception as exc:  # noqa: BLE001 - se loguea, no se propaga (ver docstring)
            print(f"[bootstrap] intento {intento + 1}/5 falló al conectar con la base: {exc!r}")
            await asyncio.sleep(1)
    print("[bootstrap] no se pudo conectar con la base tras 5 intentos; sigo sin el Admin bootstrap.")


@asynccontextmanager
async def lifespan(_: FastAPI):
    asyncio.create_task(_bootstrap_admin_con_reintentos())
    yield


app = FastAPI(
    title="Torneo MVP API",
    description="API para gestión de torneos, equipos, jugadores, partidos y estadísticas.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.cors_origins != "*",
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["Health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
