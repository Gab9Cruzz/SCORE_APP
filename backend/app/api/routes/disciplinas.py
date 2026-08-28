from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.schemas.disciplina import DisciplinaConModalidadesOut, DisciplinaOut, DisciplinaUpdate, EstadoDisciplina
from app.services.disciplina import DisciplinaService

router = APIRouter(prefix="/disciplinas", tags=["Disciplinas"])

# Catálogo de solo lectura + toggle de Estado (Decisión C1,
# ediciones-catalogo-disciplinas-plan.md) — sin POST: el catálogo lo carga
# 11_catalogo_disciplinas.sql (28 disciplinas / 66 modalidades), un admin
# ya no puede crear una disciplina nueva a mano desde acá.


@router.get("", response_model=list[DisciplinaOut])
async def listar_disciplinas(
    skip: int = 0,
    limit: int = Query(default=100, le=200),
    estado: EstadoDisciplina | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[DisciplinaOut]:
    """Lista plana. El selector de "Torneo nuevo" filtra `estado=Activo`
    (D-Eng-7) — una disciplina desactivada deja de ofrecerse para torneos
    NUEVOS sin afectar a los que ya la usan (EC-31)."""
    return await DisciplinaService(session).list(skip=skip, limit=limit, estado=estado)


# Va ANTES de /{disciplina_id}: si quedara después, FastAPI probaría a
# interpretar "con-modalidades" como un disciplina_id (int) y este path
# nunca matchearía (orden de registro = orden de matching de rutas).
@router.get("/con-modalidades", response_model=list[DisciplinaConModalidadesOut])
async def listar_disciplinas_con_modalidades(
    estado: EstadoDisciplina | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[DisciplinaConModalidadesOut]:
    """Vista jerárquica para CatalogoDisciplinasPage: cada disciplina con su
    roster de modalidades en una sola llamada, en vez de que el cliente
    arme el árbol cruzando /disciplinas y /modalidades por separado."""
    return await DisciplinaService(session).list_con_modalidades(estado=estado)


@router.get("/{disciplina_id}", response_model=DisciplinaOut)
async def obtener_disciplina(disciplina_id: int, session: AsyncSession = Depends(get_db)) -> DisciplinaOut:
    return await DisciplinaService(session).get(disciplina_id)


@router.patch(
    "/{disciplina_id}", response_model=DisciplinaOut, dependencies=[Depends(require_roles("TorneoAdmin"))]
)
async def actualizar_estado_disciplina(
    disciplina_id: int, data: DisciplinaUpdate, session: AsyncSession = Depends(get_db)
) -> DisciplinaOut:
    """Único cambio permitido sobre el catálogo: activar/desactivar
    (DisciplinaUpdate solo acepta `estado`, ver ese schema)."""
    return await DisciplinaService(session).update(disciplina_id, data)
