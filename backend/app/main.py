import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core import auditoria as _auditoria_listener  # noqa: F401 - registra el event listener de flush (ver ese módulo)
from app.core.config import get_settings
from app.db.database import async_session_factory
from app.exceptions.handlers import register_exception_handlers
from app.repositories.acceso import AccesoRepository
from app.repositories.auditoria import AuditoriaRepository
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


async def _purgar_accesos_viejos() -> None:
    """Borra de ACCESOS lo más viejo que `accesos_retencion_dias` (30 por
    defecto). Corre al arrancar la API.

    Por qué en el arranque y no en cada login: el camino de login es el
    más caliente de la app y no debería cargar con un DELETE que casi
    siempre no borra nada. Este proyecto no tiene scheduler (ni pg_cron),
    y el servidor se levanta a mano cada vez que se enciende la máquina
    (ver README) — o sea que en la práctica esto corre a diario, que es
    exactamente la frecuencia que una purga mensual necesita.

    La contrapartida, y hay que tenerla presente: **un servidor que queda
    semanas levantado sin reiniciarse no purga**. Si esto pasa a correr
    como servicio permanente, la purga tiene que mudarse a un scheduler
    de verdad (pg_cron o un cron del sistema llamando al mismo
    repositorio); está anotado en TODOS.md.

    Como el bootstrap del Admin: los errores se loguean y no se propagan.
    Que no se pueda limpiar la bitácora no es razón para no levantar la
    API — la app funciona igual, solo crece una tabla.
    """
    if settings.accesos_retencion_dias <= 0:
        return
    try:
        async with async_session_factory() as session:
            repo = AccesoRepository(session)
            borrados = await repo.purgar_anteriores_a(settings.accesos_retencion_dias)
            if borrados:
                print(
                    f"[accesos] purga: {borrados} registro(s) de más de "
                    f"{settings.accesos_retencion_dias} días eliminados; "
                    f"quedan {await repo.contar()}."
                )
    except Exception as exc:  # noqa: BLE001 - se loguea, no se propaga (ver docstring)
        print(f"[accesos] no se pudo purgar la bitácora: {exc!r}")


async def _purgar_auditoria_vieja() -> None:
    """Borra de AUDITORIA lo más viejo que `auditoria_retencion_dias` (30
    por defecto — "1 mes", como se pidió). Mismo mecanismo, mismo
    razonamiento y mismas limitaciones que `_purgar_accesos_viejos` de
    arriba: corre al arrancar la API porque este proyecto no tiene
    scheduler, así que un servidor que queda semanas sin reiniciarse no
    purga (ver esa función para el detalle completo)."""
    if settings.auditoria_retencion_dias <= 0:
        return
    try:
        async with async_session_factory() as session:
            repo = AuditoriaRepository(session)
            borrados = await repo.purgar_anteriores_a(settings.auditoria_retencion_dias)
            if borrados:
                print(
                    f"[auditoria] purga: {borrados} registro(s) de más de "
                    f"{settings.auditoria_retencion_dias} días eliminados; "
                    f"quedan {await repo.contar()}."
                )
    except Exception as exc:  # noqa: BLE001 - se loguea, no se propaga (ver docstring)
        print(f"[auditoria] no se pudo purgar la bitácora: {exc!r}")


@asynccontextmanager
async def lifespan(_: FastAPI):
    asyncio.create_task(_bootstrap_admin_con_reintentos())
    # Después del bootstrap y también en background: si la base todavía no
    # responde, no vale la pena bloquear el arranque por una limpieza.
    asyncio.create_task(_purgar_accesos_viejos())
    asyncio.create_task(_purgar_auditoria_vieja())
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
