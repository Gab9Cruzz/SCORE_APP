"""Portal Público — Feed de Partidos del Día
(portal-publico-feed-partidos-plan.md, T3.3/E-G3/F5/E-S3).
"""
import time
from collections import OrderedDict
from collections.abc import Hashable
from datetime import date, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metricas import registrar_evento
from app.core.reloj import hoy_negocio
from app.repositories.feed import FeedRepository
from app.schemas.disciplina import DisciplinaConPartidosOut
from app.schemas.partido import (
    FeedEquipoOut,
    FeedPartidoOut,
    FeedResponseOut,
    FeedTorneoOut,
)

# E-S3a: caché en proceso — el feed no tiene auto-refresh (C14), así que
# 60s de frescura es gratis y hace irrelevante el costo por request de un
# endpoint público sin auth ni rate limit. La clave INCLUYE
# ventana_fallback_dias — el plan la proponía sin ese campo (F5 decía
# "(fecha, disciplina_id, limit)"), pero eso mezclaría bajo la misma
# entrada una carga inicial (ventana=7) con una navegación explícita
# (ventana=0): la primera puede resolver `fecha_efectiva` a otro día, y
# devolvérsela a la segunda sería un dato incorrecto, no solo stale.
_CACHE_TTL_SEGUNDOS = 60
_CACHE_MAXIMO = 256


class CacheAcotada:
    """TASK-030 (BE-08, SEC-08): caché en memoria con tamaño máximo (sale la
    menos usada) y expiración. Antes era un dict sin límite cuyas claves
    (fecha, disciplina, limit) las elige cualquier visitante anónimo: mil
    fechas distintas eran mil entradas para siempre.

    Es por proceso: con varios workers cada uno tiene la suya, que está bien
    para un TTL de 60 s. La caché compartida la da el proxy (Cache-Control,
    ver routes/partidos.py)."""

    def __init__(self, maximo: int, ttl_segundos: float):
        self.maximo = maximo
        self.ttl = ttl_segundos
        self._datos: OrderedDict[Hashable, tuple[float, Any]] = OrderedDict()

    def obtener(self, clave: Hashable, ahora: float | None = None) -> Any | None:
        ahora = time.monotonic() if ahora is None else ahora
        entrada = self._datos.get(clave)
        if entrada is None:
            return None
        vence, valor = entrada
        if vence <= ahora:
            del self._datos[clave]
            return None
        self._datos.move_to_end(clave)
        return valor

    def guardar(self, clave: Hashable, valor: Any, ahora: float | None = None) -> None:
        ahora = time.monotonic() if ahora is None else ahora
        self._datos[clave] = (ahora + self.ttl, valor)
        self._datos.move_to_end(clave)
        while len(self._datos) > self.maximo:
            self._datos.popitem(last=False)

    def clear(self) -> None:
        self._datos.clear()

    def __len__(self) -> int:
        return len(self._datos)


_cache = CacheAcotada(maximo=_CACHE_MAXIMO, ttl_segundos=_CACHE_TTL_SEGUNDOS)


# TASK-030: respuestas públicas iguales para todos; un proxy puede servirlas.
CACHE_CONTROL_PUBLICO = "public, max-age=60"
# TASK-030: una fecha absurda no tiene sentido y solo llena la caché.
DIAS_MAXIMOS_FEED = 730


def validar_fecha_feed(fecha: date | None) -> None:
    if fecha is not None and abs((fecha - hoy_negocio()).days) > DIAS_MAXIMOS_FEED:
        raise HTTPException(status_code=422, detail="La fecha tiene que estar dentro de los dos años de hoy.")


class FeedService:
    def __init__(self, session: AsyncSession):
        self.repo = FeedRepository(session)

    async def obtener_feed(
        self,
        fecha_pedida: date | None,
        disciplina_id: int | None,
        limit: int,
        ventana_fallback_dias: int,
    ) -> FeedResponseOut:
        """3 reglas no obvias del contrato (F12):

        1. Sin `fecha`, se resuelve DIRECTO a la fecha más cercana con
           partidos publicados (E-G3) — no hay estado intermedio de "hoy
           vacío". Con `fecha` explícita, `ventana_fallback_dias` decide
           si esa resolución aplica (7 en la carga inicial sin fecha en la
           URL, 0 al navegar explícito — D3/F5): buscando hacia atrás
           primero (más cercano al pasado gana sobre cualquier fecha
           futura) y recién después hacia adelante, acotado a
           `ventana_fallback_dias` (máx. 7, E-S3b). Fuera de esa ventana,
           vacío real — `fecha_efectiva == fecha_pedida`.
        2. Orden determinista: torneo_grupo.Nombre, torneo.ID (desempate
           de homónimos, E-M6), fecha_partido, partido_id — los partidos
           de un mismo torneo quedan contiguos, T4.4 los agrupa en el
           cliente confiando en esto.
        3. El corte por `limit` respeta bordes de bloque de torneo
           (E-L5): siempre se devuelve el primer bloque completo aunque
           por sí solo supere `limit` — nunca corta un torneo a mitad.
           `total_disponible` es el total real del día, sin truncar.

        Ejemplo: `GET /api/v1/partidos/feed?disciplina_id=1&limit=20` un
        martes sin partidos de fútbol hoy pero sí el domingo pasado ->
        `{"fecha_pedida": "<martes>", "fecha_efectiva": "<domingo>",
        "total_disponible": 12, "partidos": [...]}`.
        """
        fecha_pedida_real = fecha_pedida if fecha_pedida is not None else await self.repo.fecha_actual_servidor()

        clave = (fecha_pedida_real, disciplina_id, limit, ventana_fallback_dias)
        cacheado = _cache.obtener(clave)
        if cacheado is not None:
            return cacheado

        fecha_efectiva = await self._resolver_fecha_efectiva(
            fecha_pedida_real, disciplina_id, ventana_fallback_dias
        )
        filas, total_disponible = await self.repo.partidos_del_dia(fecha_efectiva, disciplina_id, limit)
        partidos = [self._a_partido_out(f) for f in filas]
        respuesta = FeedResponseOut(
            fecha_pedida=fecha_pedida_real,
            fecha_efectiva=fecha_efectiva,
            total_disponible=total_disponible,
            partidos=partidos,
        )

        # E-S3c: se loguea SOLO cuando el fallback se activó de verdad —
        # el resto se cuenta en memoria (no hay línea por cada hit).
        if fecha_efectiva != fecha_pedida_real:
            registrar_evento(
                "feed_hit",
                disciplina_id=disciplina_id,
                fecha_pedida=str(fecha_pedida_real),
                fecha_efectiva=str(fecha_efectiva),
            )

        _cache.guardar(clave, respuesta)
        return respuesta

    async def obtener_disciplinas_con_partidos(
        self, fecha_pedida: date | None, ventana_fallback_dias: int
    ) -> list[DisciplinaConPartidosOut]:
        """E-L4/E-M3: endpoint propio de la barra pública de deportes —
        antes era un sidecar del envelope del feed, pero eso lo dejaba
        vacío exactamente los días en que más hacía falta (un feriado sin
        partidos de la disciplina filtrada) y era circular con
        `fecha_efectiva` (F4). Acá NO se filtra por disciplina — nunca
        está vacío mientras el feed tenga contenido en algún deporte."""
        fecha_pedida_real = fecha_pedida if fecha_pedida is not None else await self.repo.fecha_actual_servidor()
        fecha_efectiva = await self._resolver_fecha_efectiva(fecha_pedida_real, None, ventana_fallback_dias)
        filas = await self.repo.disciplinas_con_partidos(fecha_efectiva)
        return [DisciplinaConPartidosOut.model_validate(f) for f in filas]

    async def _resolver_fecha_efectiva(
        self, fecha_pedida: date, disciplina_id: int | None, ventana_fallback_dias: int
    ) -> date:
        if ventana_fallback_dias <= 0:
            return fecha_pedida

        desde = fecha_pedida - timedelta(days=ventana_fallback_dias)
        hasta = fecha_pedida + timedelta(days=ventana_fallback_dias)
        dias = await self.repo.dias_con_contenido(desde, hasta, disciplina_id)

        if fecha_pedida in dias:
            return fecha_pedida
        # E-G3: "hacia atrás primero, después hacia adelante" — TODO el
        # rango pasado se agota antes de mirar el futuro, no una
        # alternancia -1/+1/-2/+2 por cercanía pura.
        for offset in range(1, ventana_fallback_dias + 1):
            candidato = fecha_pedida - timedelta(days=offset)
            if candidato in dias:
                return candidato
        for offset in range(1, ventana_fallback_dias + 1):
            candidato = fecha_pedida + timedelta(days=offset)
            if candidato in dias:
                return candidato
        return fecha_pedida  # fuera de la ventana: vacío real, no un sustituto

    @staticmethod
    def _a_partido_out(fila: dict) -> FeedPartidoOut:
        return FeedPartidoOut(
            partido_id=fila["partido_id"],
            torneo=FeedTorneoOut(
                id=fila["torneo_id"],
                nombre=fila["torneo"],
                grupo=fila["torneo_grupo"],
                pais=fila["pais"],
                logo_url=fila["logo_torneo"],
            ),
            disciplina_id=fila["disciplina_id"],
            disciplina=fila["disciplina"],
            local=FeedEquipoOut(
                id=fila["equipo_local_id"],
                nombre=fila["equipo_local"],
                logo_url=fila["logo_local"],
                goles=fila["goles_local"],
            ),
            visitante=FeedEquipoOut(
                id=fila["equipo_visitante_id"],
                nombre=fila["equipo_visitante"],
                logo_url=fila["logo_visitante"],
                goles=fila["goles_visitante"],
            ),
            fecha_partido=fila["fecha_partido"],
            estado=fila["estado"],
        )
