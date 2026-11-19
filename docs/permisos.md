# Permisos por rol y ruta

Generado desde `backend/tests/test_matriz_permisos.py` (TASK-048). No editar a mano:
cambiá la matriz y regenerá con `python -m tests.test_matriz_permisos` desde `backend/`.
La suite falla si este archivo no coincide con la matriz, o si hay una ruta de escritura
sin declarar.

✅ pasa la autorización (después pueden aplicar reglas de negocio) · 🔒 401 sin sesión ·
⛔ 403 sin permiso. "El torneo" es el torneo del recurso; "su partido" es el partido
que el árbitro tiene asignado.

| Método | Ruta | Anónimo | Publico | Árbitro (otro partido) | Árbitro (su partido) | TorneoAdmin (sin el torneo) | TorneoAdmin (con el torneo) | AdminGeneral | Nota |
|---|---|---|---|---|---|---|---|---|---|
| POST | `/api/v1/auth/cambiar-password` | 🔒 401 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |  |
| PATCH | `/api/v1/disciplinas/{id}` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ |  |
| PATCH | `/api/v1/modalidades/{id}` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ |  |
| POST | `/api/v1/eventos` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ |  |
| PATCH | `/api/v1/eventos/{id}` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ |  |
| DELETE | `/api/v1/eventos/{id}` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ |  |
| POST | `/api/v1/usuarios` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ |  |
| PATCH | `/api/v1/usuarios/{id}` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ |  |
| DELETE | `/api/v1/usuarios/{id}` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ |  |
| PATCH | `/api/v1/usuarios/{id}/licencia` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ |  |
| PATCH | `/api/v1/usuarios/{id}/torneos` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ |  |
| POST | `/api/v1/equipos` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ | ✅ | ✅ |  |
| PATCH | `/api/v1/equipos/{id}` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ | ✅ | ✅ |  |
| DELETE | `/api/v1/equipos/{id}` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ | ✅ | Baja: exige administrar los torneos abiertos donde juega. |
| POST | `/api/v1/equipos/{id}/plantilla-base` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ | ✅ | ✅ |  |
| DELETE | `/api/v1/equipos/{id}/plantilla-base/{id}` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ | ✅ | ✅ |  |
| POST | `/api/v1/jugadores` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ | ✅ | ✅ |  |
| PATCH | `/api/v1/jugadores/{id}` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ | ✅ | ✅ |  |
| DELETE | `/api/v1/jugadores/{id}` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ | ✅ | Baja: exige administrar los torneos abiertos donde juega. |
| POST | `/api/v1/perfiles` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ | ✅ | ✅ |  |
| PATCH | `/api/v1/perfiles/{id}` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ | ✅ | Suspensión: exige administrar los torneos abiertos donde juega. |
| POST | `/api/v1/torneos` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ | ✅ | ✅ |  |
| PATCH | `/api/v1/torneo-grupos/{id}` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ | ✅ |  |
| PATCH | `/api/v1/torneos/{id}` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ | ✅ |  |
| DELETE | `/api/v1/torneos/{id}` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ | ✅ |  |
| POST | `/api/v1/torneos/{id}/cerrar` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ | ✅ |  |
| POST | `/api/v1/torneos/{id}/reabrir` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ | ✅ |  |
| POST | `/api/v1/torneos/{id}/fixture` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ | ✅ |  |
| POST | `/api/v1/torneos/{id}/sorteo` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ | ✅ |  |
| POST | `/api/v1/torneos/{id}/playoffs` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ | ✅ |  |
| PATCH | `/api/v1/grupos/equipos/{id}` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ | ✅ |  |
| POST | `/api/v1/inscripciones` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ | ✅ |  |
| PATCH | `/api/v1/inscripciones/{id}` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ | ✅ |  |
| POST | `/api/v1/plantillas` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ | ✅ |  |
| PATCH | `/api/v1/plantillas/{id}` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ | ✅ |  |
| POST | `/api/v1/plantillas/{id}/baja` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ | ✅ |  |
| POST | `/api/v1/plantillas/lote/validar` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ | ✅ |  |
| POST | `/api/v1/plantillas/lote/confirmar` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ | ✅ |  |
| POST | `/api/v1/traspasos` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ | ✅ |  |
| POST | `/api/v1/traspasos/{id}/anular` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ | ✅ |  |
| POST | `/api/v1/partidos` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ | ✅ |  |
| DELETE | `/api/v1/partidos/{id}` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ | ✅ |  |
| POST | `/api/v1/partidos/{id}/reclamo` | 🔒 401 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ⛔ 403 | ✅ | ✅ |  |
| PATCH | `/api/v1/partidos/{id}` | 🔒 401 | ⛔ 403 | ⛔ 403 | ✅ | ⛔ 403 | ✅ | ✅ |  |
| PUT | `/api/v1/partidos/{id}/convocados` | 🔒 401 | ⛔ 403 | ⛔ 403 | ✅ | ⛔ 403 | ✅ | ✅ |  |
| POST | `/api/v1/partidos/{id}/convocados` | 🔒 401 | ⛔ 403 | ⛔ 403 | ✅ | ⛔ 403 | ✅ | ✅ |  |
| POST | `/api/v1/partidos/{id}/hitos` | 🔒 401 | ⛔ 403 | ⛔ 403 | ✅ | ⛔ 403 | ✅ | ✅ |  |
| PATCH | `/api/v1/partidos/{id}/hitos/{id}` | 🔒 401 | ⛔ 403 | ⛔ 403 | ✅ | ⛔ 403 | ✅ | ✅ |  |
| POST | `/api/v1/partidos/{id}/deshacer-cierre-forzado` | 🔒 401 | ⛔ 403 | ⛔ 403 | ✅ | ⛔ 403 | ✅ | ✅ |  |
| POST | `/api/v1/partidos/{id}/walkover` | 🔒 401 | ⛔ 403 | ⛔ 403 | ✅ | ⛔ 403 | ✅ | ✅ |  |
| POST | `/api/v1/partidos/{id}/resultado-directo` | 🔒 401 | ⛔ 403 | ⛔ 403 | ✅ | ⛔ 403 | ✅ | ✅ |  |
| POST | `/api/v1/eventos-partido` | 🔒 401 | ⛔ 403 | ⛔ 403 | ✅ | ⛔ 403 | ✅ | ✅ |  |
| PATCH | `/api/v1/eventos-partido/{id}` | 🔒 401 | ⛔ 403 | ⛔ 403 | ✅ | ⛔ 403 | ✅ | ✅ |  |
| POST | `/api/v1/eventos-partido/{id}/anular` | 🔒 401 | ⛔ 403 | ⛔ 403 | ✅ | ⛔ 403 | ✅ | ✅ |  |

## Rutas sin autorización

- `POST /api/v1/auth/login`: Es el login: pública por definición.
