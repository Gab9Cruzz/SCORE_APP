# Cobertura de pruebas

TASK-047 (`QA-04`, `QA-11`). Cada piso es la medición indicada menos dos
puntos, redondeada hacia abajo. Bajar de un piso hace fallar CI.

## Cómo se mide

| Lado | Comando | Informe |
|---|---|---|
| Backend | `python -m pytest -m "not concurrencia" --cov --cov-report=xml --cov-report=html`, después `python scripts/cobertura_minima.py coverage.xml` | `backend/htmlcov/`, `backend/coverage.xml` |
| Frontend | `npm run coverage` | `frontend/coverage/index.html` |

En CI los dos informes quedan como artefactos (`cobertura-backend`,
`cobertura-frontend`) en cada corrida.

**Backend y SQLAlchemy async.** `.coveragerc` declara
`concurrency = thread,greenlet`. Sin eso, coverage pierde el rastro después
de cada `await` a la base (SQLAlchemy ejecuta las consultas en greenlets) y
subestima todo lo que toca datos: en la misma prueba, `motor_formatos.py`
daba 27 % sin la opción y 67 % con ella. La primera medición sin la opción
(services 58 %) era falsa y se descartó.

## Frontend — medición del 2026-11-19

486 pruebas. Total: líneas 84,7 %, sentencias 81,7 %, ramas 72,6 %,
funciones 77,6 %.

| Carpeta | Líneas | Sentencias | Ramas | Funciones | Piso (L / S / R / F) |
|---|---|---|---|---|---|
| `src/lib/` | 97,7 | 97,0 | 97,0 | 92,6 | 95 / 95 / 95 / 90 |
| `src/hooks/` | 95,1 | 93,9 | 89,3 | 98,5 | 93 / 91 / 87 / 96 |

Los pisos están en `frontend/vite.config.ts` (`coverage.thresholds`).

Antes de fijarlos se sumaron pruebas a los dos archivos sin prueba propia
con menor cobertura: `lib/desempate.ts` (de 33 % a 100 % de líneas; `lib/`
pasó de 74,7 % a 97,7 %) y `pages/Dashboard.tsx` (de 31 % a 100 %).

Comprobado que el piso corta: sin `lib/desempate.test.ts`, `npm run
coverage` sale con error ("Coverage for lines (74.71%) does not meet
src/lib/** threshold (95%)").

Quedan por debajo del promedio, sin piso propio: `pages/publico/`
(65,9 % de líneas), `pages/control-mesa/` (77,1 %), `components/Cronometro.tsx`
(54 %) y `pages/control-mesa/AlineacionEditor.tsx` (58 %). Las cubren en
parte los recorridos de `e2e/`, que no entran en esta medición.

## Backend — medición del 2026-11-19

930 pruebas (`-m "not concurrencia"`). Total: 94,0 % de líneas.

| Carpeta | Líneas | Piso |
|---|---|---|
| `app/services/` | 91,5 % (2514/2747) | 89 |
| `app/repositories/` | 95,0 % (734/773) | 93 |
| `app/api/` | 98,6 % (762/773) | 96 |

Sin piso: `models/` 100 %, `exceptions/` 99,2 %, `schemas/` 97,2 %,
`core/` 96,0 %, `db/` 71,4 % y los módulos sueltos de `app/` 44,6 % (sobre
todo `main.py`: el arranque y las tareas de purga, que las pruebas no
ejecutan).

Los pisos están en `backend/scripts/cobertura_minima.py`, que lee
`coverage.xml` (coverage.py solo tiene un piso global). Comprobado que
corta: con el piso de services en 99 sale con error y marca "BAJO".

El servicio más flojo es `services/minuto_partido.py` (36 %), seguido de
`inscripcion_torneo.py` (78 %); el resto de services pasa del 88 %.
