from collections.abc import Sequence

from sqlalchemy import select, text

from app.models.torneo import Torneo
from app.repositories.base import BaseRepository


class TorneoRepository(BaseRepository[Torneo]):
    model = Torneo
    nombre_recurso = "Torneo"

    async def lock_cupo_inscripciones(self, torneo_id: int) -> None:
        """3B-10 (docs/plans/cierre-backlog-todos-plan.md): mismo motivo y
        mismo mecanismo que InscripcionTorneoRepository.lock_cupo_inscripcion
        (EC-6) — dos altas de inscripción concurrentes contra el MISMO
        torneo pueden ambas contar el mismo N de inscripciones y ambas
        "ver" el último cupo libre. Forma de un solo argumento, mismo
        patrón que lock_numero_edicion (torneo_grupo.py) y
        lock_cupo_inscripcion (EC-6): los tres comparten el mismo espacio
        de claves de 64 bits de Postgres para locks de un solo argumento
        (distinto del de 2 argumentos que usa lock_exclusividad_torneo),
        así que un Torneo_ID, un Torneo_Grupo_ID y un Inscripcion_Torneo_ID
        que coincidan numéricamente por casualidad SÍ comparten el lock —
        en la práctica solo serializa de más entre operaciones no
        relacionadas por unos milisegundos, no corrompe nada (nunca hay
        dos secciones críticas DISTINTAS activas bajo la misma clave al
        mismo tiempo, solo esperan una a la otra sin necesidad)."""
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(:torneo_id)"), {"torneo_id": torneo_id}
        )

    async def listar_ediciones_del_grupo(self, torneo_grupo_id: int) -> list[Torneo]:
        """Todas las ediciones de un TORNEO_GRUPO, de la más reciente a la
        más antigua — es el orden que espera el selector de Estadísticas
        (torneos-admin-plan.md, Fase 2 parte B) y la tarjeta de la Pestaña
        Torneos ("Ver Torneo" abre la primera de esta lista)."""
        stmt = (
            select(Torneo)
            .where(Torneo.torneo_grupo_id == torneo_grupo_id)
            .order_by(Torneo.numero_edicion.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def ediciones_por_grupo(self, torneo_grupo_ids: Sequence[int]) -> dict[int, list[Torneo]]:
        """Las ediciones de VARIOS grupos en una sola consulta, agrupadas
        en Python (equipos-disciplina-navegacion-plan.md, Mejora #4).

        Reemplaza al loop de una consulta por grupo que tenia
        TorneoGrupoService.listar_con_ediciones — su propio docstring ya
        anticipaba este cambio como "aislado". Deja de ser aceptable
        ahora que la Pestaña Torneos es el punto de entrada del modulo y
        se re-consulta en cada invalidateQueries: con 66 grupos eran 67
        consultas por carga.

        Mismo orden que listar_ediciones_del_grupo (numero_edicion desc):
        quien consuma esto sigue leyendo "la mas reciente primero"."""
        if not torneo_grupo_ids:
            return {}
        stmt = (
            select(Torneo)
            .where(Torneo.torneo_grupo_id.in_(torneo_grupo_ids))
            .order_by(Torneo.torneo_grupo_id, Torneo.numero_edicion.desc())
        )
        result = await self.session.execute(stmt)
        agrupadas: dict[int, list[Torneo]] = {}
        for torneo in result.scalars().all():
            agrupadas.setdefault(torneo.torneo_grupo_id, []).append(torneo)
        return agrupadas
