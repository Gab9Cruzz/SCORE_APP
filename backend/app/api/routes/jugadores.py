from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_optional, require_roles
from app.db.session import get_db
from app.models.usuario import Usuario
from app.schemas.jugador import EstadoJugador, JugadorCreate, JugadorOut, JugadorPublicOut, JugadorUpdate
from app.schemas.perfil_jugador import PerfilJugadorOut, PerfilJugadorPublicOut
from app.services.jugador import JugadorService
from app.services.perfil_jugador import PerfilJugadorService

router = APIRouter(prefix="/jugadores", tags=["Jugadores"])

# `response_model=None` es deliberado en los 3 GET de abajo: la proyección
# se elige EN RUNTIME según haya o no usuario autenticado, y dejar que
# FastAPI valide contra un único modelo rompería uno de los dos caminos.
# Pero `response_model=None` también borra el schema de la respuesta del
# OpenAPI —quedaba como `unknown`, y de ahí el `{}` que veía el frontend
# generado— así que la forma se declara acá aparte, solo para documentar.
# Es la unión real de lo que devuelve cada camino, no una simplificación:
# un caller anónimo recibe la variante sin PII y el schema lo dice.
RESPUESTA_LISTA_JUGADORES = {
    200: {"model": list[JugadorOut] | list[JugadorPublicOut], "description": "Successful Response"}
}
RESPUESTA_JUGADOR = {200: {"model": JugadorOut | JugadorPublicOut, "description": "Successful Response"}}
RESPUESTA_PERFIL = {
    200: {"model": PerfilJugadorOut | PerfilJugadorPublicOut, "description": "Successful Response"}
}

# Los 3 GET de acá abajo siguen siendo públicos (no exigen login) pero ya no
# filtran PII (cédula, correo) a un caller anónimo — security review de
# equipos-jugadores-plan.md, Fase 3. get_current_user_optional nunca levanta
# 401: un caller sin token o con token inválido recibe la proyección
# *PublicOut (sin PII); el frontend admin, que ya manda su Bearer token en
# cada request (api/client.ts), sigue viendo JugadorOut/PerfilJugadorOut
# completo en la misma ruta — no hizo falta tocar el frontend.


@router.get("", response_model=None, responses=RESPUESTA_LISTA_JUGADORES)
async def listar_jugadores(
    skip: int = 0,
    limit: int = Query(default=100, le=200),
    estado: EstadoJugador | None = None,
    # Búsqueda server-side por nombre/cédula (gestion-avanzada-equipos-
    # control-mesa-plan.md, Requerimiento 2) — la usa el buscador de la
    # Plantilla Base, el registro por lote y (opcional) el buscador de
    # Control de Mesa.
    q: str | None = None,
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario | None = Depends(get_current_user_optional),
) -> list[JugadorOut] | list[JugadorPublicOut]:
    jugadores = await JugadorService(session).list(skip=skip, limit=limit, estado=estado, q=q)
    if usuario_actual is None:
        return [JugadorPublicOut.model_validate(j) for j in jugadores]
    return [JugadorOut.model_validate(j) for j in jugadores]


@router.get("/{jugador_id}", response_model=None, responses=RESPUESTA_JUGADOR)
async def obtener_jugador(
    jugador_id: int,
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario | None = Depends(get_current_user_optional),
) -> JugadorOut | JugadorPublicOut:
    jugador = await JugadorService(session).get(jugador_id)
    if usuario_actual is None:
        return JugadorPublicOut.model_validate(jugador)
    return JugadorOut.model_validate(jugador)


@router.get("/{jugador_id}/perfil", response_model=None, responses=RESPUESTA_PERFIL)
async def obtener_perfil_de_jugador(
    jugador_id: int,
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario | None = Depends(get_current_user_optional),
) -> PerfilJugadorOut | PerfilJugadorPublicOut:
    """Stats + trayectoria consolidadas por disciplina (equipos-jugadores-plan.md,
    Fase 2, Etapa D)."""
    resultado = await PerfilJugadorService(session).obtener(jugador_id)
    if usuario_actual is None:
        return PerfilJugadorPublicOut.model_validate(resultado.model_dump())
    return resultado


@router.post("", response_model=JugadorOut, status_code=201, dependencies=[Depends(require_roles("TorneoAdmin"))])
async def crear_jugador(data: JugadorCreate, session: AsyncSession = Depends(get_db)) -> JugadorOut:
    return await JugadorService(session).create(data)


@router.patch("/{jugador_id}", response_model=JugadorOut, dependencies=[Depends(require_roles("TorneoAdmin"))])
async def actualizar_jugador(
    jugador_id: int, data: JugadorUpdate, session: AsyncSession = Depends(get_db)
) -> JugadorOut:
    return await JugadorService(session).update(jugador_id, data)


@router.delete("/{jugador_id}", response_model=JugadorOut, dependencies=[Depends(require_roles("TorneoAdmin"))])
async def dar_de_baja_jugador(jugador_id: int, session: AsyncSession = Depends(get_db)) -> JugadorOut:
    return await JugadorService(session).soft_delete(jugador_id)
