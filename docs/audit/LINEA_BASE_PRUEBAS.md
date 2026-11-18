# Línea base de pruebas (TASK-043)

**Fecha:** 2026-11-18
**Commit de partida:** `ae44345`, sobre el árbol auditado (`7d5a365` + los 22 archivos de tipado, ya confirmados en `bd52660`).
**Entorno:** Windows 10, PostgreSQL 17.12 (servicio local), Python 3.12.5 en `backend/.venv`, Node 26.13.1.

Cierra la limitación 1 de la auditoría (`QA-03`): la suite de backend nunca se había ejecutado en esta máquina.

## Backend

| Ejecución | Resultado | Duración |
|---|---|---|
| `python -m pytest -q -m "not concurrencia"` | **533 pasan, 1 falla**, 5 deseleccionadas | 357 s |
| `python -m pytest -q -m concurrencia` | **5 pasan** | 14 s |
| Tras corregir el fallo, `tests/test_plantillas.py` | 11 pasan | 10 s |

La auditoría contaba 505 pruebas; hoy son 539 (534 normales + 5 de concurrencia). La diferencia sale de las pruebas añadidas en `7d5a365`.

### El único fallo

`tests/test_plantillas.py::test_torneo_admin_con_asignacion_ve_la_plantilla_de_su_torneo` esperaba 3 jugadores en la plantilla del torneo 1, y la API devuelve 6.

- **Causa:** la prueba estaba mal, no el código. `05_seed.sql` inscribe 6 jugadores en el torneo 1 (2 por cada uno de sus 3 equipos) desde `3ae5365` (2026-08-27). La prueba se añadió en `7d5a365` (2026-09-20) sin haberse ejecutado, y el 3 coincide con el número de equipos inscriptos, no con el de jugadores.
- **Comportamiento correcto:** un TorneoAdmin asignado al torneo 1 ve el roster completo de ese torneo; el recorte por asignación solo debe quitar torneos ajenos (lo cubren las dos pruebas siguientes del mismo archivo, que pasan).
- **Corrección:** la prueba ahora compara contra el listado sin recorte (anónimo) y además fija el total en 6.
- No lo explica ningún hallazgo de la auditoría; no abre tarea nueva.

## Frontend

`npm run verify` (oxlint, `tsc -b --noEmit`, Vitest, `vite build`): **en verde, 344 de 344**, después de `TASK-001` y `TASK-002`.

## Comparación de esquemas (`DB-10`)

No se pudo hacer en la forma que plantea la tarea: esta máquina no tenía una base `torneos_mvp` con historia. La que existe ahora se creó el 2026-11-18 desde `01`–`06` más `11_catalogo_disciplinas.sql` y `10_demo_torneos_admin.sql` (cada uno con `psql -1`), así que coincide con el esquema de las pruebas por construcción.

Si hay una base `torneos_mvp` de más tiempo en otra máquina o servidor, la comparación sigue pendiente ahí:

```powershell
$pg = "C:\Program Files\PostgreSQL\17\bin"
& "$pg\pg_dump.exe" -h 127.0.0.1 -U postgres --schema-only --no-owner torneos_mvp      > real.sql
& "$pg\pg_dump.exe" -h 127.0.0.1 -U postgres --schema-only --no-owner torneos_mvp_test > esperado.sql
git diff --no-index esperado.sql real.sql
```

(`torneos_mvp_test` queda armada desde `01`–`06` después de cualquier corrida de pytest.) El registro de migraciones aplicadas que evita tener que hacer esto a mano es `TASK-031`.

## Criterios de aceptación

- [x] Existe el documento de línea base con los resultados de las dos ejecuciones.
- [x] Cada prueba fallida tiene causa identificada (y está corregida).
- [x] Está documentada la comparación de esquemas (no aplicable en esta máquina; procedimiento para la base real).
