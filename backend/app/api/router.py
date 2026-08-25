from fastapi import APIRouter

from app.api.routes import (
    auth,
    equipos,
    estadisticas,
    eventos,
    eventos_partido,
    inscripciones,
    jugadores,
    partidos,
    plantillas,
    torneos,
    usuarios,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(torneos.router)
api_router.include_router(equipos.router)
api_router.include_router(jugadores.router)
api_router.include_router(eventos.router)
api_router.include_router(partidos.router)
api_router.include_router(inscripciones.router)
api_router.include_router(plantillas.router)
api_router.include_router(eventos_partido.router)
api_router.include_router(usuarios.router)
api_router.include_router(estadisticas.router)
