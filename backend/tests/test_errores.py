"""TASK-015 (BE-04, SEC-06, UX-12): las reglas de negocio llegan como 400
legibles, las restricciones como 409/422 sin nombres de tablas ni
restricciones, y lo inesperado como 500 genérico, siempre registrado con un
identificador que también va en la respuesta (`X-Request-ID`)."""
import json
import logging
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import DataError, IntegrityError, OperationalError

from app.db.session import get_db
from app.exceptions import handlers
from app.main import app
from app.services.equipo import EquipoService


class _ErrorPG(Exception):
    def __init__(self, mensaje: str, sqlstate: str | None):
        super().__init__(mensaje)
        self.sqlstate = sqlstate


def _cuerpo(respuesta) -> dict:
    return json.loads(respuesta.body)


# ---------- Mapeo por SQLSTATE (unitario) ----------


@pytest.mark.parametrize(
    ("sqlstate", "status"),
    [("23505", 409), ("23503", 409), ("23514", 409), ("23502", 409), ("23P01", 409)],
)
def test_restricciones_dan_409_sin_nombres_internos(sqlstate: str, status: int):
    crudo = 'el nuevo registro para la relación «partidos» viola la restricción «chk_partidos_reclamo»'
    exc = IntegrityError("INSERT INTO partidos ...", {}, _ErrorPG(crudo, sqlstate))
    respuesta = handlers._integrity_error_response(exc)
    assert respuesta.status_code == status
    detalle = _cuerpo(respuesta)["detail"]
    assert "partidos" not in detalle and "chk_" not in detalle and "«" not in detalle


def test_unicidad_conserva_el_mensaje_de_siempre():
    exc = IntegrityError("x", {}, _ErrorPG("llave duplicada viola restricción de unicidad «unique_x»", "23505"))
    assert _cuerpo(handlers._integrity_error_response(exc))["detail"] == (
        "Ya existe un registro con esos datos (restricción de unicidad)."
    )


def test_raise_de_trigger_llega_como_400_con_su_texto():
    exc = OperationalError("x", {}, _ErrorPG("El jugador no pertenecia a ese equipo.\nCONTEXT: PL/pgSQL", "P0001"))
    respuesta = handlers._dbapi_error_response(exc)
    assert respuesta.status_code == 400
    assert _cuerpo(respuesta)["detail"] == "El jugador no pertenecia a ese equipo."


def test_texto_demasiado_largo_es_422():
    exc = DataError("x", {}, _ErrorPG("el valor es demasiado largo para el tipo character varying(100)", "22001"))
    respuesta = handlers._dbapi_error_response(exc)
    assert respuesta.status_code == 422
    assert "varying" not in _cuerpo(respuesta)["detail"]


def test_otro_error_de_base_es_500_generico():
    exc = OperationalError("x", {}, _ErrorPG("no se pudo conectar al servidor: contraseña incorrecta", "08006"))
    respuesta = handlers._dbapi_error_response(exc)
    assert respuesta.status_code == 500
    cuerpo = _cuerpo(respuesta)
    assert cuerpo["detail"] == "Error interno."
    assert "contraseña" not in json.dumps(cuerpo)


# ---------- Integración ----------


@pytest.fixture
async def cliente_sin_reraise(db_session):
    """Como `client`, pero sin que ASGITransport re-lance la excepción: así
    se ve la respuesta 500 que recibe un cliente real."""

    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


async def test_regla_de_trigger_sigue_llegando_como_400(client: AsyncClient, arbitro_headers: dict[str, str]):
    """PR-039: el jugador 3 es de Águilas, que no juega el partido 3."""
    resp = await client.post(
        "/api/v1/partidos/3/resultado-directo",
        json={"eventos": [{"jugador_id": 3, "equipo_id": 3, "eventos_id": 1, "minuto": 10}]},
        headers=arbitro_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "El jugador no pertenecia a ese equipo en la fecha del partido."


async def test_unicidad_real_da_409_sin_nombres_internos(client: AsyncClient, admin_general_headers: dict[str, str]):
    # 05_seed.sql: el jugador 1 ya tiene perfil de Fútbol.
    resp = await client.post(
        "/api/v1/perfiles", json={"jugador_id": 1, "disciplina_id": 1}, headers=admin_general_headers
    )
    assert resp.status_code == 409, resp.text
    assert "unique" not in resp.json()["detail"].lower()
    assert "«" not in resp.json()["detail"]


async def test_fallo_de_conexion_da_500_generico_y_queda_registrado(
    cliente_sin_reraise: AsyncClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    async def _explota(self, id_):
        raise OperationalError("SELECT ...", {}, _ErrorPG("no se pudo conectar: contraseña de postgres incorrecta", "08006"))

    monkeypatch.setattr(EquipoService, "get", _explota)
    with caplog.at_level(logging.ERROR, logger="score_app"):
        resp = await cliente_sin_reraise.get("/api/v1/equipos/1")
    assert resp.status_code == 500
    cuerpo = resp.json()
    assert cuerpo["detail"] == "Error interno."
    assert "postgres" not in resp.text and "contraseña" not in resp.text
    assert cuerpo["id"] == resp.headers["X-Request-ID"]
    assert any(cuerpo["id"] in r.getMessage() or getattr(r, "request_id", None) == cuerpo["id"] for r in caplog.records)


async def test_excepcion_inesperada_da_500_con_identificador(
    cliente_sin_reraise: AsyncClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    async def _explota(self, id_):
        raise RuntimeError("detalle interno que no debe salir")

    monkeypatch.setattr(EquipoService, "get", _explota)
    with caplog.at_level(logging.ERROR, logger="score_app"):
        resp = await cliente_sin_reraise.get("/api/v1/equipos/1")
    assert resp.status_code == 500
    assert "detalle interno" not in resp.text
    assert resp.json()["id"] == resp.headers["X-Request-ID"]
    assert any(r.exc_info for r in caplog.records)


@pytest.mark.parametrize("ruta", ["/health", "/api/v1/torneos", "/api/v1/equipos/999999", "/api/v1/partidos?limit=0"])
async def test_toda_respuesta_lleva_x_request_id(client: AsyncClient, ruta: str):
    resp = await client.get(ruta)
    uuid.UUID(resp.headers["X-Request-ID"])


async def test_x_request_id_de_un_proxy_se_respeta_si_es_valido(client: AsyncClient):
    propio = str(uuid.uuid4())
    assert (await client.get("/health", headers={"X-Request-ID": propio})).headers["X-Request-ID"] == propio
    inventado = (await client.get("/health", headers={"X-Request-ID": "<script>"})).headers["X-Request-ID"]
    uuid.UUID(inventado)
