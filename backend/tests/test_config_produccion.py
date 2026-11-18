"""TASK-005 (SEC-02, OPS-04), prueba PR-032: con ENTORNO=produccion la
configuración rechaza los secretos de ejemplo y nombra la variable que hay
que corregir. En desarrollo no cambia nada."""
import pytest
from pydantic import ValidationError

from app.core.config import Settings

VALIDOS_PRODUCCION = {
    "database_url": "postgresql+psycopg://u:p@db:5432/torneos_mvp",
    "jwt_secret_key": "a" * 64,
    "admin_password": "una-clave-de-verdad-larga",
    "cors_origins": "https://torneos.example.com",
    "entorno": "produccion",
}


def _settings(**cambios: str) -> Settings:
    # _env_file=None: que el backend/.env local no se mezcle con el caso.
    return Settings(_env_file=None, **{**VALIDOS_PRODUCCION, **cambios})  # type: ignore[call-arg]


def test_produccion_con_valores_propios_arranca():
    assert _settings().entorno == "produccion"


@pytest.mark.parametrize(
    ("campo", "valor", "variable"),
    [
        ("jwt_secret_key", "change-me-please-do-not-use-in-production", "JWT_SECRET_KEY"),
        ("jwt_secret_key", "corto-de-31-caracteres-xxxxxxxx", "JWT_SECRET_KEY"),
        ("admin_password", "admin1234", "ADMIN_PASSWORD"),
        ("admin_password", "change-me-please", "ADMIN_PASSWORD"),
        ("admin_password", "once-chars!", "ADMIN_PASSWORD"),
        ("cors_origins", "*", "CORS_ORIGINS"),
        ("cors_origins", " * ", "CORS_ORIGINS"),
    ],
)
def test_produccion_rechaza_valores_de_ejemplo(campo: str, valor: str, variable: str):
    with pytest.raises(ValidationError) as exc:
        _settings(**{campo: valor})
    assert variable in str(exc.value)


def test_produccion_rechaza_la_contrasena_de_admin_por_defecto():
    """Sin ADMIN_PASSWORD en el entorno, el default es admin1234."""
    datos = {k: v for k, v in VALIDOS_PRODUCCION.items() if k != "admin_password"}
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None, **datos)  # type: ignore[call-arg]
    assert "ADMIN_PASSWORD" in str(exc.value)


def test_produccion_informa_todas_las_variables_a_corregir_juntas():
    with pytest.raises(ValidationError) as exc:
        _settings(jwt_secret_key="corto", admin_password="admin1234", cors_origins="*")
    mensaje = str(exc.value)
    assert all(v in mensaje for v in ("JWT_SECRET_KEY", "ADMIN_PASSWORD", "CORS_ORIGINS"))


def test_desarrollo_acepta_los_valores_de_ejemplo():
    s = _settings(
        entorno="desarrollo",
        jwt_secret_key="change-me-please-do-not-use-in-production",
        admin_password="admin1234",
        cors_origins="*",
    )
    assert s.entorno == "desarrollo"


def test_el_entorno_por_defecto_es_desarrollo():
    datos = {k: v for k, v in VALIDOS_PRODUCCION.items() if k != "entorno"}
    assert Settings(_env_file=None, **datos).entorno == "desarrollo"  # type: ignore[call-arg]
