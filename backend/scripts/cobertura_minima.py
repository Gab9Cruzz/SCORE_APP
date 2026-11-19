"""TASK-047: piso de cobertura por carpeta del backend.

coverage.py solo tiene un `fail_under` global; esto lee el `coverage.xml`
que deja `pytest --cov --cov-report=xml` y exige un mínimo de líneas
cubiertas en cada carpeta crítica. El piso de cada una es la medición del
2026-11-19 menos dos puntos (docs/cobertura.md tiene la medición completa).

Uso: python scripts/cobertura_minima.py [coverage.xml]
Sale con 1 si alguna carpeta queda por debajo.
"""
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict

PISOS = {
    # carpeta dentro de app/: porcentaje mínimo de líneas
    "services": 89.0,
    "repositories": 93.0,
    "api": 96.0,
}


def medir(ruta: str) -> dict[str, tuple[int, int]]:
    raiz = ET.parse(ruta).getroot()
    por_carpeta: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for clase in raiz.iter("class"):
        archivo = clase.get("filename", "").replace("\\", "/")
        carpeta = archivo.split("/", 1)[0] if "/" in archivo else "(app)"
        lineas = clase.findall("lines/line")
        por_carpeta[carpeta][0] += sum(1 for linea in lineas if linea.get("hits") != "0")
        por_carpeta[carpeta][1] += len(lineas)
    return {k: (v[0], v[1]) for k, v in por_carpeta.items()}


def main() -> int:
    ruta = sys.argv[1] if len(sys.argv) > 1 else "coverage.xml"
    medido = medir(ruta)
    fallas = 0
    for carpeta, piso in PISOS.items():
        cubiertas, total = medido.get(carpeta, (0, 0))
        porcentaje = 100 * cubiertas / total if total else 0.0
        ok = porcentaje >= piso
        fallas += not ok
        print(f"{'ok ' if ok else 'BAJO'} app/{carpeta:<13} {porcentaje:5.1f} %  (piso {piso:.0f} %, {cubiertas}/{total} líneas)")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
