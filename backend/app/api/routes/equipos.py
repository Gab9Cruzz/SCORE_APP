from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.schemas.equipo import EquipoCreate, EquipoOut, EquipoUpdate, EstadoEquipo
from app.schemas.equipo_jugador_base import (
    ConflictoMultimilitancia,
    EquipoJugadorBaseCreate,
    EquipoJugadorBaseOut,
)
from app.services.equipo import EquipoService
from app.services.plantilla_base import PlantillaBaseService

router = APIRouter(prefix="/equipos", tags=["Equipos"])


@router.get("", response_model=list[EquipoOut])
async def listar_equipos(
    skip: int = 0,
    limit: int = Query(default=100, le=200),
    estado: EstadoEquipo | None = None,
    # Filtros server-side (equipos-disciplina-navegacion-plan.md, Mejora
    # #1): son lo que permite que la grilla de Equipos no tope contra el
    # techo de 200 filas cuando el catálogo crece — filtrar en memoria
    # sobre las primeras 200 devolvía "no hay resultados" para un equipo
    # que sí existe.
    disciplina_id: int | None = None,
    modalidad_id: int | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[EquipoOut]:
    return await EquipoService(session).list(
        skip=skip,
        limit=limit,
        estado=estado,
        disciplina_id=disciplina_id,
        modalidad_id=modalidad_id,
    )


@router.get("/{equipo_id}", response_model=EquipoOut)
async def obtener_equipo(equipo_id: int, session: AsyncSession = Depends(get_db)) -> EquipoOut:
    return await EquipoService(session).get(equipo_id)


@router.post("", response_model=EquipoOut, status_code=201, dependencies=[Depends(require_roles("TorneoAdmin"))])
async def crear_equipo(data: EquipoCreate, session: AsyncSession = Depends(get_db)) -> EquipoOut:
    return await EquipoService(session).create(data)


@router.patch("/{equipo_id}", response_model=EquipoOut, dependencies=[Depends(require_roles("TorneoAdmin"))])
async def actualizar_equipo(
    equipo_id: int, data: EquipoUpdate, session: AsyncSession = Depends(get_db)
) -> EquipoOut:
    return await EquipoService(session).update(equipo_id, data)


@router.delete("/{equipo_id}", response_model=EquipoOut, dependencies=[Depends(require_roles("TorneoAdmin"))])
async def dar_de_baja_equipo(equipo_id: int, session: AsyncSession = Depends(get_db)) -> EquipoOut:
    return await EquipoService(session).soft_delete(equipo_id)


# ------------------------------------------------------------
# Plantilla Base (gestion-avanzada-equipos-control-mesa-plan.md, D1-C):
# banco de candidatos de un equipo, independiente de cualquier torneo.
# ------------------------------------------------------------


@router.get(
    "/{equipo_id}/plantilla-base",
    response_model=list[EquipoJugadorBaseOut],
    dependencies=[Depends(require_roles("TorneoAdmin"))],
)
async def listar_plantilla_base(
    equipo_id: int, session: AsyncSession = Depends(get_db)
) -> list[EquipoJugadorBaseOut]:
    return await PlantillaBaseService(session).listar(equipo_id)


@router.get(
    "/{equipo_id}/plantilla-base/verificar",
    response_model=ConflictoMultimilitancia,
    dependencies=[Depends(require_roles("TorneoAdmin"))],
)
async def verificar_multimilitancia(
    equipo_id: int, jugador_id: int, session: AsyncSession = Depends(get_db)
) -> ConflictoMultimilitancia:
    """Chequeo de multimilitancia (Flujo 2 del plan) — solo lectura, nunca
    bloquea; la UI decide si muestra el modal de advertencia antes de
    confirmar el POST de abajo."""
    return await PlantillaBaseService(session).verificar_multimilitancia(equipo_id, jugador_id)


@router.post(
    "/{equipo_id}/plantilla-base",
    response_model=EquipoJugadorBaseOut,
    status_code=201,
    dependencies=[Depends(require_roles("TorneoAdmin"))],
)
async def agregar_a_plantilla_base(
    equipo_id: int, data: EquipoJugadorBaseCreate, session: AsyncSession = Depends(get_db)
) -> EquipoJugadorBaseOut:
    return await PlantillaBaseService(session).agregar(equipo_id, data)


@router.delete(
    "/{equipo_id}/plantilla-base/{item_id}",
    response_model=EquipoJugadorBaseOut,
    dependencies=[Depends(require_roles("TorneoAdmin"))],
)
async def quitar_de_plantilla_base(
    equipo_id: int, item_id: int, session: AsyncSession = Depends(get_db)
) -> EquipoJugadorBaseOut:
    """Baja lógica (EC-3 del plan) — no toca el roster real de ningún torneo."""
    return await PlantillaBaseService(session).quitar(equipo_id, item_id)
