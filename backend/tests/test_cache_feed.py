"""TASK-030 (BE-08, SEC-08): la caché del feed tiene tamaño máximo y
expiración (antes era un diccionario que crecía sin límite con claves que
elige cualquier visitante), y las respuestas públicas llevan Cache-Control
para que un proxy pueda servirlas."""
from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from app.services import feed as feed_service_module
from app.services.feed import CacheAcotada
from tests.test_consultas_n_mas_1 import contar_consultas


@pytest.fixture(autouse=True)
def _cache_limpia():
    feed_service_module._cache.clear()
    yield
    feed_service_module._cache.clear()


def test_la_cache_no_pasa_de_su_tamano_maximo():
    """PR-041."""
    cache = CacheAcotada(maximo=256, ttl_segundos=60)
    for i in range(1000):
        cache.guardar(("clave", i), i, ahora=0.0)
    assert len(cache) == 256
    assert cache.obtener(("clave", 999), ahora=1.0) == 999
    assert cache.obtener(("clave", 0), ahora=1.0) is None  # la más vieja salió


def test_lo_usado_hace_poco_no_se_expulsa():
    cache = CacheAcotada(maximo=2, ttl_segundos=60)
    cache.guardar("a", 1, ahora=0.0)
    cache.guardar("b", 2, ahora=0.0)
    assert cache.obtener("a", ahora=1.0) == 1
    cache.guardar("c", 3, ahora=1.0)
    assert cache.obtener("a", ahora=1.0) == 1
    assert cache.obtener("b", ahora=1.0) is None


def test_una_entrada_vencida_no_se_devuelve():
    cache = CacheAcotada(maximo=10, ttl_segundos=60)
    cache.guardar("a", 1, ahora=0.0)
    assert cache.obtener("a", ahora=59.0) == 1
    assert cache.obtener("a", ahora=61.0) is None
    assert len(cache) == 0


async def test_mil_fechas_distintas_dejan_la_cache_acotada(client: AsyncClient):
    hoy = date.today()
    for i in range(300):
        resp = await client.get(
            "/api/v1/partidos/feed", params={"fecha": str(hoy - timedelta(days=i)), "ventana_fallback_dias": 0}
        )
        assert resp.status_code == 200
    assert len(feed_service_module._cache) <= 256


async def test_dos_pedidos_iguales_consultan_una_sola_vez(client: AsyncClient, engine):
    params = {"fecha": str(date.today()), "ventana_fallback_dias": 0}
    await client.get("/api/v1/partidos/feed", params=params)
    with contar_consultas(engine) as c:
        resp = await client.get("/api/v1/partidos/feed", params=params)
    assert resp.status_code == 200
    assert c["n"] == 0


@pytest.mark.parametrize("ruta", ["/api/v1/partidos/feed", "/api/v1/disciplinas/con-partidos"])
async def test_las_respuestas_publicas_llevan_cache_control(client: AsyncClient, ruta: str):
    resp = await client.get(ruta)
    assert resp.status_code == 200, resp.text
    assert resp.headers["Cache-Control"] == "public, max-age=60"


@pytest.mark.parametrize("dias", [800, -800])
async def test_una_fecha_fuera_de_rango_es_422(client: AsyncClient, dias: int):
    fecha = date.today() + timedelta(days=dias)
    resp = await client.get("/api/v1/partidos/feed", params={"fecha": str(fecha)})
    assert resp.status_code == 422, resp.text
