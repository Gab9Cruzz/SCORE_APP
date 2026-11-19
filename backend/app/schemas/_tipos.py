"""Tipos de entrada reutilizables (TASK-029, BE-07/SEC-11).

Solo para los esquemas de ENTRADA (Create/Update/Request): un esquema de
salida que use estos tipos haría fallar la lectura de un dato viejo que no
cumpla (por ejemplo una foto guardada sin https). Las longitudes son las de
las columnas en database/01_schema.sql, así un texto de más vuelve como 422
legible y no como error de la base.
"""
import re
from typing import Annotated

from pydantic import AfterValidator, BeforeValidator, EmailStr, Field, StringConstraints


def Texto(maximo: int) -> type[str]:
    """Texto obligatorio: sin espacios sobrantes, no vacío, hasta `maximo`."""
    return Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=maximo)]  # type: ignore[return-value]


Nombre50 = Texto(50)
Nombre100 = Texto(100)
Texto200 = Texto(200)


def _normalizar_cedula(valor: object) -> object:
    """Un único punto de normalización: sin espacios ni guiones. "0912-345 678"
    y "0912345678" son la misma persona, y unique_jugador_cedula compara el
    texto exacto."""
    if isinstance(valor, str):
        return re.sub(r"[\s-]", "", valor)
    return valor


Cedula = Annotated[str, BeforeValidator(_normalizar_cedula), StringConstraints(min_length=1, max_length=20)]

Correo = Annotated[EmailStr, StringConstraints(max_length=150)]


def _exigir_https(valor: str) -> str:
    if not valor.startswith("https://"):
        raise ValueError("La URL tiene que empezar con https://.")
    return valor


UrlHttps = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500), AfterValidator(_exigir_https)]


def _vacio_a_none(valor: object) -> object:
    """Para opcionales que un formulario manda como "" cuando no hay valor
    (un <select> sin elegir): "" significa "sin dato", no un texto inválido."""
    if isinstance(valor, str) and valor.strip() == "":
        return None
    return valor


def TextoOpcional(maximo: int) -> type[str | None]:
    """Como Texto, pero "" o solo espacios se toman como None."""
    return Annotated[Texto(maximo) | None, BeforeValidator(_vacio_a_none)]  # type: ignore[return-value]


Dorsal = Annotated[int, Field(ge=1, le=999)]
EnteroPositivo = Annotated[int, Field(ge=1)]

# Topes de listas en una sola petición.
MAX_FILAS_LOTE = 100
MAX_EVENTOS_RESULTADO_DIRECTO = 300
MAX_CONVOCADOS = 60
