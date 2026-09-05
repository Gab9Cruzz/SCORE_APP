from sqlalchemy import func, select, text

from app.models.inscripcion_torneo import InscripcionTorneo
from app.models.jugador_equipo import JugadorEquipo
from app.models.jugador_perfil_disciplina import JugadorPerfilDisciplina
from app.repositories.base import BaseRepository


class JugadorEquipoRepository(BaseRepository[JugadorEquipo]):
    model = JugadorEquipo
    nombre_recurso = "Vínculo jugador-equipo"

    async def lock_exclusividad_torneo(self, jugador_perfil_id: int, torneo_id: int) -> None:
        """fn_validar_exclusividad_torneo (06_triggers.sql) hace un SELECT
        COUNT sin lock — bajo READ COMMITTED (el nivel por defecto de
        Postgres, que este proyecto no cambia en ningún lado) dos
        transacciones concurrentes activando al MISMO perfil en el MISMO
        torneo pueden ambas ver 0 conflictos y comprometer el invariante
        central del módulo (equipos-jugadores-plan.md, Fase 3 security
        review — no hay UNIQUE que lo blinde porque Torneo_ID no vive
        directo en JUGADOR_EQUIPO, ver el comentario del trigger).

        pg_advisory_xact_lock serializa esa carrera: la segunda transacción
        que pida el mismo (jugador_perfil_id, torneo_id) espera hasta que la
        primera haga commit/rollback, momento en el que ya ve el INSERT (o
        su ausencia) de la primera. El lock se libera solo, automáticamente,
        al terminar la transacción — no hace falta un unlock explícito."""
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(:jugador_perfil_id, :torneo_id)"),
            {"jugador_perfil_id": jugador_perfil_id, "torneo_id": torneo_id},
        )

    async def listar_por_torneo(
        self,
        torneo_id: int,
        skip: int = 0,
        limit: int = 100,
        jugador_perfil_id: int | None = None,
        inscripcion_torneo_id: int | None = None,
    ) -> list[JugadorEquipo]:
        """Torneo_ID no vive directo en esta tabla (Fase 1) — mismo join que
        get_activo_en_torneo. Usado por el dashboard scoped de
        torneos-admin-plan.md (D-Eng-3): sin este filtro, la sub-pestaña
        "Plantillas" del panel de un torneo mostraba TODO el sistema, no
        solo lo de ese torneo.

        `jugador_perfil_id`/`inscripcion_torneo_id` (fixes-datos-traspasos-
        control-mesa-plan.md): antes de esto, `JugadorEquipoService.list`
        los descartaba en silencio en cuanto se pasaba `torneo_id` junto
        con cualquiera de los dos — GET /plantillas?jugador_perfil_id=X&
        torneo_id=Y devolvía TODO el roster del torneo, no solo lo del
        perfil pedido (bug real, encontrado en producción: Traspasos
        mostraba siempre el mismo equipo de origen — el primero de la
        lista sin filtrar — para cualquier jugador)."""
        stmt = (
            select(JugadorEquipo)
            .join(InscripcionTorneo, InscripcionTorneo.id == JugadorEquipo.inscripcion_torneo_id)
            .where(InscripcionTorneo.torneo_id == torneo_id)
        )
        if jugador_perfil_id is not None:
            stmt = stmt.where(JugadorEquipo.jugador_perfil_id == jugador_perfil_id)
        if inscripcion_torneo_id is not None:
            stmt = stmt.where(JugadorEquipo.inscripcion_torneo_id == inscripcion_torneo_id)
        stmt = stmt.order_by(JugadorEquipo.id).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_activo_en_torneo(self, jugador_perfil_id: int, torneo_id: int) -> JugadorEquipo | None:
        """Join con INSCRIPCIONES_TORNEO: Torneo_ID no vive directo acá (Fase 1).
        Mismo criterio que fn_validar_exclusividad_torneo (06_triggers.sql) —
        se anticipa acá para dar el motivo específico ("ya juega en X") en vez
        de dejar que el trigger lo rechace sin contexto (registro por lote,
        Fase 2 EC-18)."""
        stmt = (
            select(JugadorEquipo)
            .join(InscripcionTorneo, InscripcionTorneo.id == JugadorEquipo.inscripcion_torneo_id)
            .where(
                JugadorEquipo.jugador_perfil_id == jugador_perfil_id,
                JugadorEquipo.estado == "Activo",
                InscripcionTorneo.torneo_id == torneo_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_ultima_traspasada_en_inscripcion(
        self, jugador_perfil_id: int, inscripcion_torneo_id: int
    ) -> JugadorEquipo | None:
        """Anular un traspaso (fixes-datos-traspasos-control-mesa-plan.md):
        la fila 'Traspasado' MÁS RECIENTE de este perfil en esta
        inscripción — la que el traspaso que se está anulando cerró. LIFO:
        si hubo más de un ida-y-vuelta entre los mismos dos equipos, la
        más reciente es la relevante para revertir el traspaso más
        reciente (no hay un FK directo entre TRASPASOS y la fila que
        cerró, así que se correlaciona por ser la última)."""
        stmt = (
            select(JugadorEquipo)
            .where(
                JugadorEquipo.jugador_perfil_id == jugador_perfil_id,
                JugadorEquipo.inscripcion_torneo_id == inscripcion_torneo_id,
                JugadorEquipo.estado == "Traspasado",
            )
            .order_by(JugadorEquipo.id.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_activo_en_inscripcion(
        self, jugador_perfil_id: int, inscripcion_torneo_id: int
    ) -> JugadorEquipo | None:
        """Sin join: inscripcion_torneo_id ya vive directo en la fila. Usado
        por Traspasos para confirmar que el origen declarado es real antes
        de cerrarlo (Fase 2, Etapa C)."""
        stmt = select(JugadorEquipo).where(
            JugadorEquipo.jugador_perfil_id == jugador_perfil_id,
            JugadorEquipo.inscripcion_torneo_id == inscripcion_torneo_id,
            JugadorEquipo.estado == "Activo",
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_activa_de_perfil(self, jugador_perfil_id: int) -> JugadorEquipo | None:
        """Cualquier membresía Activo del perfil, en cualquier roster. Usado
        por Traspasos para validar un fichaje "desde libre" (Fase 2, Etapa C)."""
        stmt = select(JugadorEquipo).where(
            JugadorEquipo.jugador_perfil_id == jugador_perfil_id,
            JugadorEquipo.estado == "Activo",
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def listar_activos_por_perfil(self, jugador_perfil_id: int) -> list[JugadorEquipo]:
        """Todas las membresías Activo del perfil (normalmente 0 o 1 por
        torneo, puede haber varias si el jugador milita en varios torneos a
        la vez — EC-10). Usado por el Perfil de Jugador (Fase 2, Etapa D)."""
        stmt = select(JugadorEquipo).where(
            JugadorEquipo.jugador_perfil_id == jugador_perfil_id,
            JugadorEquipo.estado == "Activo",
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def contar_activos_en_inscripcion(self, inscripcion_torneo_id: int) -> int:
        """Tamaño actual del roster vigente — para el tope de
        Modalidad.tamano_equipo (registro por lote, Fase 2 EC-6)."""
        stmt = select(func.count()).select_from(JugadorEquipo).where(
            JugadorEquipo.inscripcion_torneo_id == inscripcion_torneo_id,
            JugadorEquipo.estado == "Activo",
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def existe_activa_para_jugador(self, jugador_id: int) -> bool:
        """3B-3 (docs/plans/cierre-backlog-todos-plan.md): ¿tiene ESTE
        JUGADOR (persona) alguna membresía Activo en CUALQUIER
        disciplina/roster? Cruza JUGADOR_PERFIL_DISCIPLINA porque
        JUGADOR_EQUIPO ancla al perfil, no al jugador directo (mismo
        criterio que el resto de este repositorio) — usada para bloquear
        la desactivación de la persona en vez de dejarla desaparecer de
        golpe de un roster vigente."""
        stmt = (
            select(JugadorEquipo.id)
            .join(JugadorPerfilDisciplina, JugadorPerfilDisciplina.id == JugadorEquipo.jugador_perfil_id)
            .where(JugadorPerfilDisciplina.jugador_id == jugador_id, JugadorEquipo.estado == "Activo")
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first() is not None

    async def dorsal_en_uso(self, inscripcion_torneo_id: int, dorsal: int) -> bool:
        """Mismo criterio que uq_dorsal_por_roster_vigente (03_indexes.sql):
        vigente = Fecha_Fin IS NULL AND Estado='Activo'. Se anticipa acá
        (registro por lote, EC-13) para no depender solo del 409 del índice."""
        stmt = select(JugadorEquipo).where(
            JugadorEquipo.inscripcion_torneo_id == inscripcion_torneo_id,
            JugadorEquipo.dorsal == dorsal,
            JugadorEquipo.fecha_fin.is_(None),
            JugadorEquipo.estado == "Activo",
        )
        result = await self.session.execute(stmt)
        return result.scalars().first() is not None
