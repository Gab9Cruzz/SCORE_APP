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
        # orden_manual (3A-12, EC-51): desempate de ÚLTIMA instancia, entre
        # pts/dg/gf y equipo — mismo criterio que el ORDER BY interno de
        # vw_tabla_posiciones (04_views.sql), repetido acá porque envolver
        # la vista en un SELECT * con su propio ORDER BY no hereda el de
        # adentro.
        if grupo_id is not None:
            return await self._fetch(
                "SELECT * FROM vw_tabla_posiciones WHERE torneo_id = :torneo_id AND grupo_id = :grupo_id "
                "ORDER BY pts DESC, dg DESC, gf DESC, orden_manual NULLS LAST, equipo",
                torneo_id=torneo_id,
                grupo_id=grupo_id,
            )
        return await self._fetch(
            "SELECT * FROM vw_tabla_posiciones WHERE torneo_id = :torneo_id "
            "ORDER BY pts DESC, dg DESC, gf DESC, orden_manual NULLS LAST, equipo",
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

    async def plantilla_equipo(self, equipo_id: int, torneo_id: int | None = None) -> list[dict[str, Any]]:
        """Plantilla vigente de un equipo. `torneo_id` acota al roster de ESE
        torneo (gestionar-partido-alineaciones-plan.md, H2-eng).

        Sin el filtro, un equipo inscripto en dos torneos activos de la misma
        disciplina devuelve el mismo `jugador_perfil_id` dos veces: rompe las
        keys de las listas del frontend y deja convocar a alguien del equipo
        **en otro torneo** — un titular que `_validar_titulares` no cuenta y al
        que `fn_validar_jugador_partido` le rechaza cualquier evento.

        Queda opcional para no romper a los callers que legítimamente quieren
        la plantilla del equipo sin acotar a un torneo (perfil del jugador,
        estadísticas históricas)."""
        if torneo_id is None:
            return await self._fetch(
                "SELECT * FROM vw_jugadores_activos_por_equipo WHERE equipo_id = :equipo_id "
                "ORDER BY dorsal NULLS LAST, jugador",
                equipo_id=equipo_id,
            )
        return await self._fetch(
            "SELECT * FROM vw_jugadores_activos_por_equipo "
            "WHERE equipo_id = :equipo_id AND torneo_id = :torneo_id "
            "ORDER BY dorsal NULLS LAST, jugador",
            equipo_id=equipo_id,
            torneo_id=torneo_id,
        )

    async def plantilla_equipo_en_fecha(
        self, equipo_id: int, torneo_id: int, fecha_partido: Any
    ) -> list[dict[str, Any]]:
        """Plantilla vigente de un equipo A LA FECHA de un partido concreto —
        distinto de `plantilla_equipo` (vw_jugadores_activos_por_equipo,
        "hoy"). Usado SOLO por `ConvocadoAPartidoService`: la vista existente
        no puede tomar un parámetro de fecha (control-mesa-reactividad-
        playoffs-plan.md, Fase 3 §4), y cambiarle la semántica rompería a sus
        otros callers legítimos ("plantel vigente ahora" — gestión de
        equipos, selector de goleador en partido en curso).

        Mismo WHERE de fecha que `fn_validar_jugador_partido`
        (06_triggers.sql): el candidato que esta consulta ofrece es
        EXACTAMENTE el que el trigger va a aceptar cuando se cargue un
        evento real para ese jugador en ese partido — evita la
        inconsistencia de hoy (se puede convocar a alguien que después el
        trigger rechaza al cargarle un evento)."""
        return await self._fetch(
            """
            SELECT e.ID AS equipo_id, e.Nombre AS equipo, it.Torneo_ID AS torneo_id,
                   j.ID AS jugador_id, j.Nombre AS jugador, jpd.ID AS jugador_perfil_id,
                   je.Dorsal AS dorsal, je.Fecha_Inicio AS fecha_inicio
            FROM JUGADOR_EQUIPO je
            JOIN JUGADOR_PERFIL_DISCIPLINA jpd ON jpd.ID = je.Jugador_Perfil_ID
            JOIN JUGADORES j ON j.ID = jpd.Jugador_ID
            JOIN INSCRIPCIONES_TORNEO it ON it.ID = je.Inscripcion_Torneo_ID
            JOIN EQUIPOS e ON e.ID = it.Equipo_ID
            WHERE e.ID = :equipo_id AND it.Torneo_ID = :torneo_id
              AND j.Estado = 'Activo' AND e.Estado = 'Activo' AND je.Estado = 'Activo'
              AND je.Fecha_Inicio <= CAST(:fecha_partido AS date)
              AND (je.Fecha_Fin IS NULL OR je.Fecha_Fin >= CAST(:fecha_partido AS date))
            ORDER BY je.Dorsal NULLS LAST, j.Nombre
            """,
            equipo_id=equipo_id,
            torneo_id=torneo_id,
            fecha_partido=fecha_partido,
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

    async def duracion_partido(self, partido_id: int) -> dict[str, Any] | None:
        """vw_duracion_partido (gestion-avanzada-equipos-control-mesa-
        plan.md, Requerimiento 5) — sin fila si el partido todavía no
        tiene Fin_Partido registrado (partido en curso o ni siquiera
        empezado); el caller lo trata como "sin dato todavía", no como
        error (ver DuracionPartidoOut)."""
        filas = await self._fetch(
            "SELECT * FROM vw_duracion_partido WHERE partido_id = :id", id=partido_id
        )
        return filas[0] if filas else None

    async def goles_totales_perfil(self, jugador_perfil_id: int) -> int:
        filas = await self._fetch(
            "SELECT goles_totales FROM vw_goleadores_por_disciplina WHERE jugador_perfil_id = :id",
            id=jugador_perfil_id,
        )
        return filas[0]["goles_totales"] if filas else 0
