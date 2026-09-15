"""Portal Público — Feed de Partidos del Día
(portal-publico-feed-partidos-plan.md, T3.3/E-L2/E-L5).

Sobre vw_feed_partidos (04_views.sql), con SQL textual — igual que
EstadisticasRepository: es una vista, no una entidad con identidad ORM.
"""
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class FeedRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def fecha_actual_servidor(self) -> date:
        """E-M1: el default de `fecha` se resuelve en Postgres, no con
        `date.today()` de Python — hay dos relojes (proceso vs. DB) que
        pueden diferir hasta una hora entera durante la madrugada según el
        TZ de cada uno."""
        result = await self.session.execute(text("SELECT CURRENT_DATE"))
        return result.scalar_one()

    async def dias_con_contenido(
        self, fecha_desde: date, fecha_hasta: date, disciplina_id: int | None
    ) -> set[date]:
        """Qué días en [fecha_desde, fecha_hasta] (ambos inclusive) tienen
        al menos un partido — resuelve `fecha_efectiva` (E-G3) con UNA
        consulta en vez de hasta 2*ventana+1. Mismo predicado de rango
        semiabierto que `partidos_del_dia` (E-L2, sargable)."""
        sql = """
            SELECT DISTINCT DATE(Fecha_Partido) AS dia
            FROM vw_feed_partidos
            WHERE Fecha_Partido >= :desde
              AND Fecha_Partido < (CAST(:hasta AS date) + INTERVAL '1 day')
              AND (CAST(:disciplina_id AS int) IS NULL OR Disciplina_ID = :disciplina_id)
        """
        result = await self.session.execute(
            text(sql), {"desde": fecha_desde, "hasta": fecha_hasta, "disciplina_id": disciplina_id}
        )
        return {row[0] for row in result.all()}

    async def partidos_del_dia(
        self, fecha: date, disciplina_id: int | None, limit: int
    ) -> tuple[list[dict[str, Any]], int]:
        """Filas del feed para UN día (rango semiabierto — E-L2, sargable
        sobre idx_partidos_fecha) con el corte de E-L5: `limit` es un
        mínimo redondeado hacia arriba al borde de bloque de torneo, no un
        máximo estricto — el primer bloque completo entra siempre, aunque
        por sí solo supere `limit`. `total_disponible` es el total SIN
        truncar (la misma query, no una consulta aparte).

        Devuelve `([], 0)` si no hay partidos ese día — no hay fila de la
        que leer `total_disponible` cuando `filas` está vacío, así que ese
        caso se resuelve en Python, no en SQL."""
        sql = """
            WITH filas AS (
                SELECT f.*,
                       DENSE_RANK() OVER (ORDER BY f.Torneo_Grupo, f.Torneo_ID) AS bloque_rank
                FROM vw_feed_partidos f
                WHERE f.Fecha_Partido >= :fecha
                  AND f.Fecha_Partido < (CAST(:fecha AS date) + INTERVAL '1 day')
                  AND (CAST(:disciplina_id AS int) IS NULL OR f.Disciplina_ID = :disciplina_id)
            ),
            bloques AS (
                SELECT bloque_rank, COUNT(*) AS filas_en_bloque
                FROM filas
                GROUP BY bloque_rank
            ),
            acumulado AS (
                SELECT bloque_rank, SUM(filas_en_bloque) OVER (ORDER BY bloque_rank) AS total_hasta
                FROM bloques
            ),
            corte AS (
                SELECT MIN(bloque_rank) AS rank_corte FROM acumulado WHERE total_hasta >= :limit
            )
            SELECT filas.*, (SELECT COUNT(*) FROM filas) AS total_disponible
            FROM filas
            WHERE filas.bloque_rank <= COALESCE(
                (SELECT rank_corte FROM corte),
                (SELECT MAX(bloque_rank) FROM filas)
            )
            -- E-M6: torneo_grupo.Nombre/torneo.ID son el contrato de
            -- desempate, no un detalle — dos grupos homónimos ordenan
            -- por ID y siguen contiguos (T4.4 agrupa por bloque en el
            -- cliente confiando en este orden).
            ORDER BY filas.Torneo_Grupo, filas.Torneo_ID, filas.Fecha_Partido, filas.Partido_ID
        """
        result = await self.session.execute(
            text(sql), {"fecha": fecha, "disciplina_id": disciplina_id, "limit": limit}
        )
        filas = [dict(row) for row in result.mappings().all()]
        total_disponible = filas[0]["total_disponible"] if filas else 0
        return filas, total_disponible

    async def disciplinas_con_partidos(self, fecha: date) -> list[dict[str, Any]]:
        """E-L4/E-M3: disciplinas con al menos un partido en `fecha` — sin
        filtro de disciplina (es la fuente de `GET /disciplinas/con-partidos`,
        que resuelve su propia `fecha_efectiva` de forma independiente del
        feed, ver FeedService). Necesita el Slug (F3) para el deep link."""
        sql = """
            SELECT DISTINCT f.Disciplina_ID AS id, disc.Slug AS slug, f.Disciplina AS nombre
            FROM vw_feed_partidos f
            JOIN DISCIPLINA disc ON disc.ID = f.Disciplina_ID
            WHERE f.Fecha_Partido >= :fecha
              AND f.Fecha_Partido < (CAST(:fecha AS date) + INTERVAL '1 day')
            ORDER BY nombre
        """
        result = await self.session.execute(text(sql), {"fecha": fecha})
        return [dict(row) for row in result.mappings().all()]
