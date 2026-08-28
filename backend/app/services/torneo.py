from sqlalchemy.ext.asyncio import AsyncSession

from app.models.torneo import Torneo
from app.models.torneo_grupo import TorneoGrupo
from app.repositories.torneo import TorneoRepository
from app.repositories.torneo_grupo import TorneoGrupoRepository
from app.schemas.torneo import TorneoCreate, TorneoUpdate


class TorneoService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = TorneoRepository(session)
        self.grupo_repo = TorneoGrupoRepository(session)

    async def get(self, id_: int) -> Torneo:
        return await self.repo.get_or_404(id_)

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        estado: str | None = None,
        torneo_grupo_id: int | None = None,
    ) -> list[Torneo]:
        return await self.repo.list(skip=skip, limit=limit, estado=estado, torneo_grupo_id=torneo_grupo_id)

    async def create(self, data: TorneoCreate) -> Torneo:
        """Resuelve el grupo ANTES de crear la edición
        (torneos-admin-plan.md, Fase 1/3 — TorneoCreate.exactamente_un_origen_de_grupo
        ya garantiza que vino uno solo de los dos):

        - `torneo_grupo_nombre` -> crea un TORNEO_GRUPO nuevo, Edición 1.
          disciplina_id/modalidad_id vienen del cliente (obligatorios acá,
          TorneoCreate.disciplina_modalidad_requeridas_si_grupo_nuevo).
        - `torneo_grupo_id` -> edición nueva de un grupo YA existente;
          numero_edicion se calcula bajo un advisory lock (EC-21: dos
          admins creando "Edición 3" del mismo grupo a la vez no deben
          poder leer el mismo MAX() y chocar contra unique_edicion_por_grupo
          sin enterarse de por qué — mismo mecanismo que
          JugadorEquipoRepository.lock_exclusividad_torneo, serializa la
          carrera en vez de reaccionar a ella después del INSERT fallido).
          disciplina_id/modalidad_id se HEREDAN de la edición más reciente
          del grupo — lo que mande el cliente en esos dos campos se
          descarta sin más (D-Eng-5/EC-26 de
          ediciones-catalogo-disciplinas-plan.md): un "Nueva edición" con
          disciplina distinta a la del grupo no es un error a rechazar,
          es un campo que ya no se le hace caso al cliente, ni siquiera
          vía un curl directo.
        """
        datos = data.model_dump(exclude={"torneo_grupo_nombre"})

        if data.torneo_grupo_nombre:
            grupo = TorneoGrupo(nombre=data.torneo_grupo_nombre.strip())
            self.session.add(grupo)
            await self.session.flush()  # asigna grupo.id sin comprometer la transacción
            datos["torneo_grupo_id"] = grupo.id
            datos["numero_edicion"] = 1
        else:
            grupo = await self.grupo_repo.get_or_404(data.torneo_grupo_id)  # 404 claro si el id no existe
            await self.grupo_repo.lock_numero_edicion(data.torneo_grupo_id)
            datos["numero_edicion"] = await self.grupo_repo.siguiente_numero_edicion(data.torneo_grupo_id)

            ediciones_previas = await self.repo.listar_ediciones_del_grupo(data.torneo_grupo_id)
            if ediciones_previas:
                edicion_referencia = ediciones_previas[0]  # la más reciente
                datos["disciplina_id"] = edicion_referencia.disciplina_id
                datos["modalidad_id"] = edicion_referencia.modalidad_id

        # Nombre compuesto si el cliente no mandó uno propio (Decision
        # Audit Trail #3 del plan) — así Torneo.nombre nunca queda vacío
        # para quien lo lea directo (reportes, listados que todavía no
        # migraron a componer grupo+edición del lado de la UI).
        if not datos.get("nombre"):
            datos["nombre"] = f"{grupo.nombre} - Edición {datos['numero_edicion']}"

        return await self.repo.create(**datos)

    async def update(self, id_: int, data: TorneoUpdate) -> Torneo:
        return await self.repo.update(id_, **data.model_dump(exclude_unset=True))

    async def soft_delete(self, id_: int) -> Torneo:
        return await self.repo.soft_delete(id_, estado_inactivo="Inactivo")
