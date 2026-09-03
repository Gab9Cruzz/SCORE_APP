from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles, require_torneo_access_de
from app.db.session import get_db
from app.repositories.inscripcion_torneo import InscripcionTorneoRepository
from app.schemas.registro_lote import ConfirmarLoteResponse, RegistroLoteRequest, ValidarLoteResponse
from app.services.registro_lote import RegistroLoteService


# Resolver de torneo_id (rbac-licencias-torneos-plan.md, Fase 2) —
# RegistroLoteRequest.inscripcion_torneo_id -> InscripcionTorneo.torneo_id
# (1 hop), mismo criterio que plantillas.py (registro por lote ES el
# camino masivo de dar de alta jugadores, mismo recurso de fondo).
async def _torneo_id_del_body(data: RegistroLoteRequest, session: AsyncSession = Depends(get_db)) -> int:
    inscripcion = await InscripcionTorneoRepository(session).get_or_404(data.inscripcion_torneo_id)
    return inscripcion.torneo_id

# Registro por lote con pantalla dividida (equipos-jugadores-plan.md, Fase
# 2). inscripcion_torneo_id viaja en el body, no en la URL — este backend
# no anida recursos en rutas (a diferencia del sketch original del plan,
# `/equipos/{id}/torneos/{torneo_id}/...`); INSCRIPCIONES_TORNEO ya ancla
# equipo+torneo (Fase 1), no hace falta repetirlo en el path.
router = APIRouter(prefix="/plantillas/lote", tags=["Registro por lote"])


@router.post(
    "/validar",
    response_model=ValidarLoteResponse,
    dependencies=[
        Depends(require_roles("TorneoAdmin")),
        Depends(require_torneo_access_de(_torneo_id_del_body)),
    ],
)
async def validar_lote(data: RegistroLoteRequest, session: AsyncSession = Depends(get_db)) -> ValidarLoteResponse:
    """200 siempre — inválido es un dato en la respuesta, no un error HTTP."""
    validos, invalidos = await RegistroLoteService(session).validar(data.inscripcion_torneo_id, data.filas)
    return ValidarLoteResponse(validos=validos, invalidos=invalidos)


@router.post(
    "/confirmar",
    response_model=ConfirmarLoteResponse,
    dependencies=[
        Depends(require_roles("TorneoAdmin")),
        Depends(require_torneo_access_de(_torneo_id_del_body)),
    ],
)
async def confirmar_lote(
    data: RegistroLoteRequest, session: AsyncSession = Depends(get_db)
) -> ConfirmarLoteResponse:
    """Revalida en el servidor (EC-7) — nunca confía en las filas
    "válidas" que el cliente vio en /validar. Éxito parcial también da 200."""
    insertados, rechazados = await RegistroLoteService(session).confirmar(
        data.inscripcion_torneo_id, data.fecha_inicio, data.filas
    )
    return ConfirmarLoteResponse(insertados=insertados, rechazados=rechazados)
