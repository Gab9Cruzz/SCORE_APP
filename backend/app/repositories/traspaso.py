from typing import Sequence

from sqlalchemy import Select, select

from app.models.inscripcion_torneo import InscripcionTorneo
from app.models.traspaso import Traspaso
from app.repositories.base import BaseRepository


class TraspasoRepository(BaseRepository[Traspaso]):
    model = Traspaso
    nombre_recurso = "Traspaso"

    async def listar_por_torneo(
        self,
        torneo_id: int | None,
        skip: int = 0,
        limit: int = 100,
        jugador_perfil_id: int | None = None,
        torneo_ids_permitidos: Sequence[int] | None = None,
    ) -> list[Traspaso]:
        """Torneo_ID no vive directo en TRASPASOS — se filtra por el torneo
        del EQUIPO DESTINO (el traspaso "pertenece" al torneo al que el
        jugador se está incorporando; origen y destino son normalmente el
        mismo torneo, ver torneos-admin-plan.md, "Fuera de este módulo").
        Usado por el dashboard scoped de un torneo (D-Eng-3).

        `torneo_id` es opcional y `jugador_perfil_id` se suma al filtro
        (antes se perdía en cuanto `torneo_id` venía seteado — mismo bug ya
        corregido en `JugadorEquipoRepository.listar_por_torneo`, ver ese
        comentario) porque `torneo_ids_permitidos` (P3, TODOS.md) fuerza
        este método incluso sin `torneo_id` explícito: un TorneoAdmin que
        pida solo `?jugador_perfil_id=X` también tiene que quedar recortado
        a sus torneos asignados."""
        stmt = self._consulta_por_torneo(torneo_id, jugador_perfil_id, torneo_ids_permitidos)
        stmt = stmt.order_by(Traspaso.id).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def contar_por_torneo(
        self,
        torneo_id: int | None,
        jugador_perfil_id: int | None = None,
        torneo_ids_permitidos: Sequence[int] | None = None,
    ) -> int:
        """Total sin paginar con los mismos filtros que `listar_por_torneo`
        (TASK-011)."""
        return await self._contar(self._consulta_por_torneo(torneo_id, jugador_perfil_id, torneo_ids_permitidos))

    @staticmethod
    def _consulta_por_torneo(
        torneo_id: int | None, jugador_perfil_id: int | None, torneo_ids_permitidos: Sequence[int] | None
    ) -> Select:
        stmt = select(Traspaso).join(InscripcionTorneo, InscripcionTorneo.id == Traspaso.inscripcion_destino_id)
        if torneo_id is not None:
            stmt = stmt.where(InscripcionTorneo.torneo_id == torneo_id)
        if torneo_ids_permitidos is not None:
            stmt = stmt.where(InscripcionTorneo.torneo_id.in_(torneo_ids_permitidos))
        if jugador_perfil_id is not None:
            stmt = stmt.where(Traspaso.jugador_perfil_id == jugador_perfil_id)
        return stmt
