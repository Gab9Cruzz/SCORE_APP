from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.errors import NotFoundError
from app.models.torneo_grupo import TorneoGrupo
from app.repositories.torneo import TorneoRepository
from app.repositories.torneo_grupo import TorneoGrupoRepository
from app.schemas.torneo_grupo import EdicionResumen, TorneoGrupoConEdiciones, TorneoGrupoUpdate


class TorneoGrupoService:
    def __init__(self, session: AsyncSession):
        self.repo = TorneoGrupoRepository(session)
        self.torneo_repo = TorneoRepository(session)

    async def get(self, id_: int) -> TorneoGrupo:
        return await self.repo.get_or_404(id_)

    async def get_con_ediciones(self, id_: int, solo_publicados: bool = False) -> TorneoGrupoConEdiciones:
        """Un solo grupo + sus ediciones — usado por "Ver Torneo" para el
        selector de ediciones (a diferencia de `listar_con_ediciones`, que
        trae TODOS los grupos para la Pestaña Torneos)."""
        grupo = await self.repo.get_or_404(id_)
        ediciones = await self.torneo_repo.listar_ediciones_del_grupo(id_)
        # TASK-014 (SEC-07): un anónimo solo ve ediciones publicadas; un grupo
        # sin ninguna es, para él, inexistente (mismo 404 que un torneo).
        if solo_publicados:
            ediciones = [t for t in ediciones if t.publicado]
            if not ediciones:
                raise NotFoundError("TorneoGrupo", id_)
        return TorneoGrupoConEdiciones(
            id=grupo.id,
            nombre=grupo.nombre,
            estado=grupo.estado,
            fecha_registro=grupo.fecha_registro,
            fecha_modificacion=grupo.fecha_modificacion,
            ediciones=[EdicionResumen.model_validate(t) for t in ediciones],
        )

    async def update(self, id_: int, data: TorneoGrupoUpdate) -> TorneoGrupo:
        """Renombrar — EC-25 del plan: permitido sin restricción. El nombre
        se compone en runtime en cada edición, así que esto alcanza a
        todas de una — no hay ninguna fila de TORNEO que tocar."""
        return await self.repo.update(id_, **data.model_dump(exclude_unset=True))

    async def listar_con_ediciones(
        self, incluir_archivados: bool = False, solo_publicados: bool = False
    ) -> list[TorneoGrupoConEdiciones]:
        """Lo que consume la Pestaña Torneos (Fase 2, paso 1 del journey):
        tarjeta por grupo con todas sus ediciones.

        Dos consultas fijas — grupos + todas sus ediciones de una
        (equipos-disciplina-navegacion-plan.md, Mejora #4). Antes era un
        N+1 (una consulta por grupo), aceptado conscientemente cuando esta
        pantalla era un grid pasivo de 3 tarjetas; con la barra de
        navegación por disciplina pasa a ser el punto de entrada del
        módulo y se re-consulta en cada invalidateQueries. Mismo
        response_model y mismo orden que antes: el cambio es invisible
        desde afuera.

        3B-7: `incluir_archivados=False` (default) es el "oculta el grupo
        de los selectores" del plan — un grupo Archivado sigue existiendo
        entero (y sigue siendo consultable por GET /torneo-grupos/{id}
        directo, sin filtro), solo no aparece acá salvo que se pida."""
        grupos = await self.repo.listar_con_ediciones(incluir_archivados=incluir_archivados)
        ediciones_por_grupo = await self.torneo_repo.ediciones_por_grupo([g.id for g in grupos])
        # TASK-014 (SEC-07): ver get_con_ediciones.
        if solo_publicados:
            ediciones_por_grupo = {
                gid: [t for t in eds if t.publicado] for gid, eds in ediciones_por_grupo.items()
            }
            grupos = [g for g in grupos if ediciones_por_grupo.get(g.id)]
        return [
            TorneoGrupoConEdiciones(
                id=grupo.id,
                nombre=grupo.nombre,
                estado=grupo.estado,
                fecha_registro=grupo.fecha_registro,
                fecha_modificacion=grupo.fecha_modificacion,
                ediciones=[
                    EdicionResumen.model_validate(t) for t in ediciones_por_grupo.get(grupo.id, [])
                ],
            )
            for grupo in grupos
        ]
