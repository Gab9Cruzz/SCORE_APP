from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.estadisticas import (
    GoleadorOut,
    PlantillaJugadorOut,
    PosicionOut,
    ProximoPartidoOut,
    ResultadoPartidoOut,
)
from app.services.estadisticas import EstadisticasService

# Consultas agregadas de solo lectura (las 5 vistas públicas de
# database/04_views.sql). Sin auth: es lo que ve cualquier espectador.
router = APIRouter(prefix="/estadisticas", tags=["Estadísticas"])


@router.get("/torneos/{torneo_id}/posiciones", response_model=list[PosicionOut])
async def tabla_posiciones(
    torneo_id: int, grupo_id: int | None = None, session: AsyncSession = Depends(get_db)
) -> list[PosicionOut]:
    # grupo_id (EC-54): un torneo Grupos_Playoffs necesita la tabla de UN
    # grupo puntual, no las N mezcladas.
    return await EstadisticasService(session).tabla_posiciones(torneo_id, grupo_id=grupo_id)


@router.get("/torneos/{torneo_id}/goleadores", response_model=list[GoleadorOut])
async def goleadores(
    torneo_id: int, limit: int = Query(default=50, le=200), session: AsyncSession = Depends(get_db)
) -> list[GoleadorOut]:
    return await EstadisticasService(session).goleadores(torneo_id, limit=limit)


@router.get("/torneos/{torneo_id}/resultados", response_model=list[ResultadoPartidoOut])
async def resultados_partidos(
    torneo_id: int, session: AsyncSession = Depends(get_db)
) -> list[ResultadoPartidoOut]:
    return await EstadisticasService(session).resultados_partidos(torneo_id)


@router.get("/proximos-partidos", response_model=list[ProximoPartidoOut])
async def proximos_partidos(
    torneo_id: int | None = None, session: AsyncSession = Depends(get_db)
) -> list[ProximoPartidoOut]:
    return await EstadisticasService(session).proximos_partidos(torneo_id)


@router.get("/equipos/{equipo_id}/plantilla", response_model=list[PlantillaJugadorOut])
async def plantilla_equipo(
    equipo_id: int, session: AsyncSession = Depends(get_db)
) -> list[PlantillaJugadorOut]:
    return await EstadisticasService(session).plantilla_equipo(equipo_id)
