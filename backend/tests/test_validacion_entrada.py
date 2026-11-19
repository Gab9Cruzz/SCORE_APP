"""TASK-029 (BE-07, SEC-11): toda entrada inválida se rechaza con 422 antes
de llegar a la base: textos con su longitud, correos con formato, URLs con
https, enteros con rango, listas con tope y skip/limit válidos."""
import pytest
from httpx import AsyncClient
from pydantic import BaseModel, ValidationError

from app.schemas._tipos import Cedula, Correo, Dorsal, EnteroPositivo, Nombre100, UrlHttps


class _Modelo(BaseModel):
    nombre: Nombre100 | None = None
    cedula: Cedula | None = None
    correo: Correo | None = None
    url: UrlHttps | None = None
    dorsal: Dorsal | None = None
    entero: EnteroPositivo | None = None


@pytest.mark.parametrize(
    "datos",
    [
        {"nombre": ""}, {"nombre": "   "}, {"nombre": "x" * 101},
        {"cedula": ""}, {"cedula": "1" * 21},
        {"correo": "no-es-un-correo"},
        {"url": "http://inseguro.com/a.png"}, {"url": "javascript:alert(1)"},
        {"dorsal": 0}, {"dorsal": 1000},
        {"entero": 0}, {"entero": -3},
    ],
)
def test_cada_tipo_rechaza_lo_invalido(datos: dict):
    with pytest.raises(ValidationError):
        _Modelo(**datos)


def test_cada_tipo_acepta_y_normaliza_lo_valido():
    m = _Modelo(nombre="  Carlos  ", cedula="0912-345 678", correo="c@example.com",
                url="https://cdn.example.com/f.png", dorsal=10, entero=1)
    assert m.nombre == "Carlos"
    assert m.cedula == "0912345678"


# ---------- Por la API ----------


@pytest.mark.parametrize("nombre", ["", "   ", "x" * 101])
async def test_nombre_vacio_o_largo_es_422(client: AsyncClient, admin_general_headers: dict[str, str], nombre: str):
    resp = await client.post(
        "/api/v1/equipos", json={"nombre": nombre, "disciplina_id": 1, "modalidad_id": 1}, headers=admin_general_headers
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.parametrize(
    "ruta",
    ["/api/v1/torneos", "/api/v1/equipos", "/api/v1/jugadores", "/api/v1/eventos", "/api/v1/disciplinas",
     "/api/v1/modalidades", "/api/v1/perfiles", "/api/v1/usuarios", "/api/v1/accesos", "/api/v1/auditoria",
     "/api/v1/partidos", "/api/v1/plantillas", "/api/v1/inscripciones", "/api/v1/traspasos"],
)
@pytest.mark.parametrize("params", [{"skip": -1}, {"limit": 0}])
async def test_skip_y_limit_invalidos_son_422(
    client: AsyncClient, admin_general_headers: dict[str, str], ruta: str, params: dict
):
    resp = await client.get(ruta, params=params, headers=admin_general_headers)
    assert resp.status_code == 422, (ruta, resp.text)


async def test_un_lote_de_101_filas_es_422(client: AsyncClient, admin_general_headers: dict[str, str]):
    filas = [{"cedula": f"LOTE{i:04d}", "nombre": f"J {i}", "correo_electronico": f"j{i}@example.com"} for i in range(101)]
    resp = await client.post(
        "/api/v1/plantillas/lote/validar",
        json={"inscripcion_torneo_id": 1, "fecha_inicio": "2026-01-01", "filas": filas},
        headers=admin_general_headers,
    )
    assert resp.status_code == 422, resp.text


async def test_foto_url_sin_https_es_422(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.patch(
        "/api/v1/jugadores/1", json={"foto_url": "http://example.com/f.png"}, headers=admin_general_headers
    )
    assert resp.status_code == 422, resp.text


async def test_correo_sin_formato_es_422(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/jugadores",
        json={"nombre": "Sin Correo", "cedula": "VAL0001", "correo_electronico": "no-es-correo"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 422, resp.text


async def test_dorsal_fuera_de_rango_es_422(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.patch("/api/v1/plantillas/1", json={"dorsal": 0}, headers=admin_general_headers)
    assert resp.status_code == 422, resp.text


async def test_la_cedula_se_guarda_normalizada(client: AsyncClient, admin_general_headers: dict[str, str]):
    resp = await client.post(
        "/api/v1/jugadores",
        json={"nombre": "Con Guiones", "cedula": "0999-111 222", "correo_electronico": "g@example.com"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["cedula"] == "0999111222"
