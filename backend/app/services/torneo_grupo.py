from sqlalchemy.ext.asyncio import AsyncSession

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

    async def update(self, id_: int, data: TorneoGrupoUpdate) -> TorneoGrupo:
        """Renombrar — EC-25 del plan: permitido sin restricción. El nombre
        se compone en runtime en cada edición, así que esto alcanza a
        todas de una — no hay ninguna fila de TORNEO que tocar."""
        return await self.repo.update(id_, **data.model_dump(exclude_unset=True))

    async def listar_con_ediciones(self) -> list[TorneoGrupoConEdiciones]:
        """Lo que consume la Pestaña Torneos (Fase 2, paso 1 del journey):
        tarjeta por grupo con todas sus ediciones. N+1 consultas (una por
        grupo) — aceptable al volumen actual del sistema (D-Eng-2 del plan
        hace la misma llamada de juicio para equipos no inscritos); migrar
        a un solo JOIN es un cambio aislado si el catálogo de torneos
        crece mucho."""
        grupos = await self.repo.listar_con_ediciones()
        resultado: list[TorneoGrupoConEdiciones] = []
        for grupo in grupos:
            ediciones = await self.torneo_repo.listar_ediciones_del_grupo(grupo.id)
            resultado.append(
                TorneoGrupoConEdiciones(
                    id=grupo.id,
                    nombre=grupo.nombre,
                    fecha_registro=grupo.fecha_registro,
                    fecha_modificacion=grupo.fecha_modificacion,
                    ediciones=[EdicionResumen.model_validate(t) for t in ediciones],
                )
            )
        return resultado
