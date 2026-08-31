from fastapi import APIRouter

from app.api.routes import (
    accesos,
    auditoria,
    auth,
    disciplinas,
    equipos,
    estadisticas,
    eventos,
    eventos_partido,
    grupos,
    inscripciones,
    jugadores,
    modalidades,
    motor_formatos,
    partidos,
    perfiles,
    plantillas,
    registro_lote,
    torneo_grupos,
    torneos,
    traspasos,
    usuarios,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(disciplinas.router)
api_router.include_router(modalidades.router)
api_router.include_router(torneos.router)
api_router.include_router(motor_formatos.router)
api_router.include_router(grupos.router)
api_router.include_router(torneo_grupos.router)
api_router.include_router(equipos.router)
api_router.include_router(jugadores.router)
api_router.include_router(perfiles.router)
api_router.include_router(eventos.router)
api_router.include_router(partidos.router)
api_router.include_router(inscripciones.router)
api_router.include_router(plantillas.router)
api_router.include_router(registro_lote.router)
api_router.include_router(traspasos.router)
api_router.include_router(eventos_partido.router)
api_router.include_router(usuarios.router)
api_router.include_router(accesos.router)
api_router.include_router(auditoria.router)
api_router.include_router(estadisticas.router)
