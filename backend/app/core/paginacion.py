"""Paginación de listados (TASK-011, FUN-05/BE-06).

Los listados devuelven una lista (el contrato no cambia) y el total de filas
que cumplen el filtro va en la cabecera `X-Total-Count`. Con eso el cliente
sabe si la lista que recibió está completa, que es lo que faltaba: antes
estas rutas no declaraban `skip`/`limit`, FastAPI ignoraba el `limit=200`
del frontend y el servicio cortaba en 100 sin avisar.
"""
from dataclasses import dataclass

from fastapi import Query, Response
from fastapi.exceptions import RequestValidationError

CABECERA_TOTAL = "X-Total-Count"
LIMITE_POR_DEFECTO = 100
LIMITE_MAXIMO = 200
# Los eventos de UN partido no se paginan en la interfaz: se traen enteros.
LIMITE_MAXIMO_EVENTOS = 500


@dataclass(frozen=True)
class Pagina:
    skip: int
    limit: int


def paginacion(
    skip: int = Query(0, ge=0),
    limit: int = Query(LIMITE_POR_DEFECTO, ge=1, le=LIMITE_MAXIMO),
) -> Pagina:
    return Pagina(skip=skip, limit=limit)


def paginacion_eventos(
    skip: int = Query(0, ge=0),
    limit: int = Query(LIMITE_POR_DEFECTO, ge=1, le=LIMITE_MAXIMO_EVENTOS),
) -> Pagina:
    return Pagina(skip=skip, limit=limit)


def informar_total(response: Response, total: int) -> None:
    response.headers[CABECERA_TOTAL] = str(total)


# TASK-039 (FE-09): resolver nombres de varios registros en UNA petición
# (`?ids=1,2,3`) en lugar de un GET por identificador. Va separado por comas
# y no como `ids=1&ids=2` para que la URL sea corta y legible en los logs.
MAXIMO_IDS = LIMITE_MAXIMO


def ids_por_coma(
    ids: str | None = Query(
        None,
        pattern=r"^\d+(,\d+)*$",
        description=f"Identificadores separados por coma (hasta {MAXIMO_IDS}).",
    ),
) -> list[int] | None:
    if ids is None:
        return None
    valores = list(dict.fromkeys(int(v) for v in ids.split(",")))
    if len(valores) > MAXIMO_IDS:
        raise RequestValidationError(
            [{"type": "too_long", "loc": ("query", "ids"), "msg": f"Como máximo {MAXIMO_IDS} identificadores.", "input": ids}]
        )
    return valores
