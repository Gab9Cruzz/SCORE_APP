from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.schemas.registro_lote import ConfirmarLoteResponse, RegistroLoteRequest, ValidarLoteResponse
from app.services.registro_lote import RegistroLoteService

# Registro por lote con pantalla dividida (equipos-jugadores-plan.md, Fase
# 2). inscripcion_torneo_id viaja en el body, no en la URL — este backend
# no anida recursos en rutas (a diferencia del sketch original del plan,
# `/equipos/{id}/torneos/{torneo_id}/...`); INSCRIPCIONES_TORNEO ya ancla
# equipo+torneo (Fase 1), no hace falta repetirlo en el path.
router = APIRouter(prefix="/plantillas/lote", tags=["Registro por lote"])


@router.post("/validar", response_model=ValidarLoteResponse, dependencies=[Depends(require_roles("TorneoAdmin"))])
async def validar_lote(data: RegistroLoteRequest, session: AsyncSession = Depends(get_db)) -> ValidarLoteResponse:
    """200 siempre — inválido es un dato en la respuesta, no un error HTTP."""
    validos, invalidos = await RegistroLoteService(session).validar(data.inscripcion_torneo_id, data.filas)
    return ValidarLoteResponse(validos=validos, invalidos=invalidos)


@router.post(
    "/confirmar", response_model=ConfirmarLoteResponse, dependencies=[Depends(require_roles("TorneoAdmin"))]
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
