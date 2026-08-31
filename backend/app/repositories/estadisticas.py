"""Consultas de solo lectura contra las vistas de /database/04_views.sql.

Son vistas, no tablas mapeadas por el ORM (no tienen PK propia útil para
identidad de objeto), así que se consultan con SQL textual y se devuelven
como mappings; los schemas de app/schemas/estadisticas.py las validan.
"""
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class EstadisticasRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _fetch(self, sql: str, **params: Any) -> list[dict[str, Any]]:
        result = await self.session.execute(text(sql), params)
        return [dict(row) for row in result.mappings().all()]

    async def tabla_posiciones(self, torneo_id: int, grupo_id: int | None = None) -> list[dict[str, Any]]:
        # EC-54: sin grupo_id, un torneo Grupos_Playoffs devuelve sus N
        # tablas mezcladas (mismo comportamiento que antes del motor de
        # formatos para Liga, que nunca tiene grupo) — el consumidor que
        # sabe que está mirando un torneo de grupos pasa grupo_id.
        if grupo_id is not None:
            return await self._fetch(
                "SELECT * FROM vw_tabla_posiciones WHERE torneo_id = :torneo_id AND grupo_id = :grupo_id "
                "ORDER BY pts DESC, dg DESC, gf DESC, equipo",
                torneo_id=torneo_id,
                grupo_id=grupo_id,
            )
        return await self._fetch(
            "SELECT * FROM vw_tabla_posiciones WHERE torneo_id = :torneo_id "
            "ORDER BY pts DESC, dg DESC, gf DESC, equipo",
            torneo_id=torneo_id,
        )

    async def goleadores(self, torneo_id: int, limit: int = 50) -> list[dict[str, Any]]:
        return await self._fetch(
            "SELECT * FROM vw_goleadores WHERE torneo_id = :torneo_id "
            "ORDER BY goles DESC, jugador LIMIT :limit",
            torneo_id=torneo_id,
            limit=limit,
        )

    async def proximos_partidos(self, torneo_id: int | None = None) -> list[dict[str, Any]]:
        if torneo_id is not None:
            return await self._fetch(
                "SELECT * FROM vw_proximos_partidos WHERE torneo_id = :torneo_id "
                "ORDER BY fecha_partido",
                torneo_id=torneo_id,
            )
        return await self._fetch("SELECT * FROM vw_proximos_partidos ORDER BY fecha_partido")

    async def resultados_partidos(self, torneo_id: int) -> list[dict[str, Any]]:
        return await self._fetch(
            "SELECT * FROM vw_resultados_partidos WHERE torneo_id = :torneo_id "
            "ORDER BY fecha_partido DESC",
            torneo_id=torneo_id,
        )

    async def plantilla_equipo(self, equipo_id: int) -> list[dict[str, Any]]:
        return await self._fetch(
            "SELECT * FROM vw_jugadores_activos_por_equipo WHERE equipo_id = :equipo_id "
            "ORDER BY dorsal NULLS LAST, jugador",
            equipo_id=equipo_id,
        )

    async def estado_perfil(self, jugador_perfil_id: int) -> str | None:
        """Libre/Activo/Suspendido, derivado (Fase 1, EC-10/EC-11) — se
        reusa la vista en vez de reimplementar la lógica acá (Perfil de
        Jugador, Fase 2 Etapa D)."""
        filas = await self._fetch(
            "SELECT estado FROM vw_estado_perfil_disciplina WHERE jugador_perfil_id = :id",
            id=jugador_perfil_id,
        )
        return filas[0]["estado"] if filas else None

    async def goles_totales_perfil(self, jugador_perfil_id: int) -> int:
        filas = await self._fetch(
            "SELECT goles_totales FROM vw_goleadores_por_disciplina WHERE jugador_perfil_id = :id",
            id=jugador_perfil_id,
        )
        return filas[0]["goles_totales"] if filas else 0
