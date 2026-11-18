# 08 — Auditoría de infraestructura y DevOps

Fase VIII: qué hay hoy para ejecutar SCORE_APP y qué falta para un despliegue de producción confiable.

> **Nivel de evidencia.** En la máquina de auditoría no hay Docker, así que `docker compose` **no se ejecutó**. Los hallazgos salen de leer `infrastructure/docker-compose.yml`, `backend/Dockerfile`, los README y los scripts. `OPS-01` se apoya además en lo que el propio repositorio documenta sobre sus migraciones.

## 1. Inventario

| Elemento | Estado |
|---|---|
| `backend/Dockerfile` | Existe. Imagen única `python:3.12-slim`, usuario sin privilegios, arranque con `uvicorn` |
| Dockerfile del frontend | **No existe** |
| `infrastructure/docker-compose.yml` | Dos servicios: `postgres` y `api`. Un volumen con nombre |
| Proxy inverso / TLS | **No existe** |
| Entornos (desarrollo, pruebas, producción) | Un solo compose, de desarrollo |
| Variables de entorno | `backend/.env.example`, `frontend/.env.example`. No hay ejemplo en `infrastructure/` |
| Integración y despliegue continuos | **No existe** (sin `.github/`, sin otro sistema) |
| Verificación local | `verificar.ps1` (PowerShell) y `npm run verify` |
| Migraciones | SQL manual con `psql -1`, procedimiento documentado en `database/README.md` |
| Copias de seguridad | Comando manual `pg_dump` documentado; carpeta `database/backups/` ignorada por git |
| Restauración | Comando manual `pg_restore` documentado; sin evidencia de ensayo |
| Observabilidad | `print()` y un logger de métricas en JSON; `/health` estático |
| Manuales de operación | `docs/runbook-portal-publico.md` (métricas del portal) |

## 2. Hallazgos

### OPS-01 — La inicialización de la base en `docker compose` aborta a mitad de camino

- **Tipo:** Confirmado (estático); **no ejecutado**. **Severidad:** Alto.
- **Ubicación:** `infrastructure/docker-compose.yml:27` (`../database:/docker-entrypoint-initdb.d:ro`), comentario de las líneas 1–15; `backend/tests/test_scripts_sql.py` (docstring del módulo); `database/README.md`; `database/08_migracion_equipos_jugadores.sql:56`.
- **Descripción:** el compose monta la carpeta `database/` entera como directorio de inicialización. La imagen oficial de PostgreSQL ejecuta todos los `.sql` por orden alfabético con `ON_ERROR_STOP=1`. Eso incluye:
  - `01`–`06`, que ya son el esquema final completo;
  - las migraciones históricas `07`, `08`, `09`, `12` y `13`, de las que el propio repositorio dice: "08 referencia `DISCIPLINA.Tipo`, que 12 eliminó. Que fallen sobre el esquema actual es correcto, no un bug";
  - los datos de demostración `10_demo_torneos_admin.sql` y `seed_portal_demo.sql`.

  Sobre el esquema final, `08` intenta `ADD CONSTRAINT … CHECK (Tipo IN (…))` sobre una columna que no existe, falla, y la inicialización se detiene.
- **Consecuencia previsible:** el contenedor termina con error en el primer arranque. Con `restart: unless-stopped` se reinicia, encuentra el directorio de datos ya creado y **omite la inicialización**: la base queda con `01`–`07` aplicados y sin el catálogo de `11_catalogo_disciplinas.sql` (28 disciplinas y 66 modalidades) ni nada posterior. La API arranca y responde, lo que oculta el problema.
- **Contradicción documental:** el comentario del compose afirma que "la API real necesita las migraciones 07-33"; `database/README.md` afirma que `01`–`06` describen el estado final y que las pruebas (que solo cargan `01`–`06`) lo demuestran. `TODOS.md:146` reconoce que el compose "no fue verificado end-to-end".
- **Impacto:** el camino que el `README.md` raíz recomienda para un clon nuevo no deja el sistema en un estado correcto, y es la base natural de cualquier despliegue.
- **Recomendación:** un directorio de inicialización propio con solo lo que debe correr en una base nueva (`01`–`06` y `11`), los datos de demostración como paso opcional, y una prueba que levante el compose. `TASK-006`.

### OPS-02 — No hay forma definida de desplegar el frontend ni de exponer el sistema

- **Tipo:** Confirmado (estático). **Severidad:** Alto.
- **Evidencia:** `README.md` ("Para el frontend… `npm install` + `npm run dev`"); no hay Dockerfile ni servicio para el frontend; `VITE_API_BASE_URL=http://127.0.0.1:8000`; la API se publica directamente en el puerto 8000.
- **Impacto:** no existe un artefacto desplegable de la interfaz, ni terminación TLS, ni cabeceras de seguridad, ni compresión, ni limitación de peticiones. La SPA usa rutas del lado del cliente, que necesitan que el servidor web devuelva `index.html` para cualquier ruta.
- **Recomendación:** imagen con servidor web para los estáticos y proxy inverso con TLS que sirva `/` y reenvíe `/api`. Mismo origen para ambos, lo que además permite cerrar CORS. `TASK-049`.

### OPS-03 — Sin integración continua

- **Tipo:** Confirmado (estático). **Severidad:** Alto.
- **Evidencia:** no existe `.github/` ni configuración de otro sistema; `TODOS.md` lista "Mover `verificar.ps1` a CI (GitHub Actions) — infraestructura nueva" entre lo descartado a propósito, con la indicación de no reabrir sin evidencia nueva.
- **Evidencia nueva que justifica reabrirlo:** en la máquina del propietario la verificación del frontend da rojo en las 344 pruebas por la versión de Node (`QA-01`), y eso tapó una prueba realmente rota (`QA-02`). Con una ejecución automática en un entorno fijo, ambos se habrían visto el día que aparecieron. Además, `verificar.ps1` solo funciona en Windows.
- **Recomendación:** un flujo mínimo con dos trabajos (backend con un servicio PostgreSQL; frontend con Node fijado). `TASK-003`.

### OPS-04 — Sin separación de entornos ni gestión de secretos

- **Tipo:** Confirmado (estático). **Severidad:** Medio.
- **Ubicación:** `infrastructure/docker-compose.yml:20-25,51-53`.
- **Detalle:** un único compose con contraseña de base `1234`, puerto 5432 publicado al anfitrión, contraseña de administrador con valor por defecto, CORS abierto y `extra_hosts` de desarrollo. La API no distingue modo desarrollo de producción: no hay variable de entorno que endurezca valores por defecto o desactive `/docs`.
- **Recomendación:** variable `ENTORNO`, archivo de compose de producción sin puertos de base publicados, secretos por archivo o gestor, y validación al arrancar (`SEC-02`). `TASK-005`, `TASK-050`.

### OPS-05 — Copias de seguridad manuales y restauración sin ensayar

- **Tipo:** Confirmado (estático). **Severidad:** Alto para producción.
- **Evidencia:** `database/README.md` documenta `pg_dump` antes de cada migración y `pg_restore`; no hay tarea programada, política de retención, copia fuera del servidor ni registro de un ensayo de restauración. El volumen `postgres-data` es el único lugar donde viven los datos, y `docker compose down -v` lo borra.
- **Impacto:** un fallo de disco o un `down -v` por error supone perder todos los torneos.
- **Recomendación:** copia diaria automática con retención, copia externa y un ensayo de restauración documentado con tiempos. `TASK-051`.

### OPS-06 — Observabilidad insuficiente para operar

- **Tipo:** Confirmado (estático). **Severidad:** Medio.
- **Ubicación:** `backend/app/main.py:38-43,74-81,96-103,135-137`; `backend/app/core/metricas.py`; `infrastructure/docker-compose.yml` (el servicio `api` no tiene `healthcheck`).
- **Detalle:** mensajes con `print` sin nivel ni formato; ningún registro de errores (`BE-04`); `/health` devuelve "ok" aunque la base esté caída (decisión deliberada para no tumbar el arranque, pero entonces falta una comprobación de disponibilidad real); sin métricas de latencia o errores; sin alertas. Lo que sí hay: eventos de uso del portal en JSON y aviso de esperas largas por bloqueo.
- **Recomendación:** logging estructurado con identificador de petición, `/health/live` y `/health/ready`, comprobación de salud en el compose y métricas básicas. `TASK-052`.

### OPS-07 — Mantenimiento que solo ocurre al arrancar

- **Tipo:** Confirmado (estático). **Severidad:** Medio.
- **Ubicación:** `backend/app/main.py:46-113`.
- **Descripción:** las purgas de accesos y de auditoría corren una vez, al iniciar el proceso. El propio comentario lo advierte: "un servidor que queda semanas levantado sin reiniciarse no purga" y remite a `TODOS.md`, donde la nota ya no figura. Con `restart: unless-stopped` ese es justamente el modo de funcionamiento en producción.
- **Recomendación:** tarea programada (cron del sistema, `pg_cron` o un bucle interno con intervalo). `TASK-053`.

### Hallazgos menores

| ID | Tipo | Severidad | Hallazgo | Evidencia | Tarea |
|---|---|---|---|---|---|
| OPS-08 | Confirmado (estático) | Bajo | Imagen de la API: base sin fijar por resumen, sin etapa de construcción separada, dependencias de prueba incluidas (pytest, httpx, asyncpg), sin `HEALTHCHECK`, un solo proceso `uvicorn` sin configuración de workers ni de tiempos de espera. Comentario desactualizado ("asyncpg es puro Python") cuando el controlador es psycopg | `backend/Dockerfile`, `backend/requirements.txt` | `TASK-049` |
| OPS-09 | Confirmado (estático / ejecutado) | Medio | Entorno de desarrollo no reproducible: Node sin fijar (`QA-01`); `verificar.ps1` solo para Windows; arranque especial `run.py` en Windows sin recarga automática; `Enceder.txt` con rutas de otra máquina | `frontend/package.json`, `verificar.ps1`, `backend/run.py`, `Enceder.txt` | `TASK-001`, `TASK-055` |
| OPS-10 | Mejora | Medio | Migraciones manuales sin registro de aplicación por entorno | `DB-10` | `TASK-031` |
| OPS-11 | Mejora | Bajo | Sin estrategia de versiones ni de vuelta atrás: versión fija `0.1.0` en la API y `0.0.0` en el frontend, sin etiquetas en git | `backend/app/main.py:119`, `frontend/package.json` | `TASK-054` |
| OPS-12 | Mejora | Bajo | El cliente de API se regenera a mano contra un backend en marcha (`npm run gen:api`); nada comprueba que `schema.d.ts` esté al día | `frontend/package.json`, `frontend/README.md` | `TASK-003` |
| OPS-13 | Riesgo potencial | Bajo | El sondeo del partido en vivo (cada 5 s por espectador, tres consultas por llamada) y la caché en memoria condicionan el dimensionamiento; no hay prueba de carga | `backend/app/services/hito_partido.py:80-98` | `TASK-052` |

## 3. Lo que está bien

- **Usuario sin privilegios en el contenedor**, con el motivo explicado en el Dockerfile.
- **`.dockerignore`** que excluye `.env`, pruebas y entorno virtual.
- **Secreto del JWT obligatorio** en el compose, con un mensaje de error que explica cómo generarlo.
- **Comprobación de salud de PostgreSQL** y `depends_on` con condición de servicio sano.
- **Arranque tolerante**: la creación del administrador reintenta y no tumba la API si la base tarda.
- **Procedimiento de migración prudente**: copia previa, ensayo en una base descartable, transacción única, y un script de verificación (`backend/scripts/verificar_migracion_13.py`) que sirve de molde.
- **`verificar.ps1`** ordena los pasos de más informativo a menos y se detiene en el primer fallo.
- **Prueba de los scripts SQL** que detecta un seed roto por un cambio de esquema.
- **Datos sintéticos separados** de los orgánicos y documentados (`docs/queries/README.md`).

## 4. Qué hace falta para producción

Lista mínima, en orden. Cada punto remite a su tarea.

| # | Requisito | Hoy | Tarea |
|---|---|---|---|
| 1 | Verificación automática en un entorno fijo | No | `TASK-001`, `TASK-003` |
| 2 | Base que se inicializa bien desde cero | No (`OPS-01`) | `TASK-006` |
| 3 | Arranque que rechaza secretos de ejemplo | No | `TASK-005` |
| 4 | Frontend empaquetado y servido tras un proxy con TLS | No | `TASK-049` |
| 5 | Configuración por entorno; base no expuesta; CORS cerrado | No | `TASK-050` |
| 6 | Copia diaria, retención y restauración ensayada | No | `TASK-051` |
| 7 | Registro estructurado, salud real, métricas y alertas | Parcial | `TASK-052` |
| 8 | Mantenimiento programado; servidor con varios procesos | No | `TASK-053` |
| 9 | Migraciones con registro de versión | No | `TASK-031` |
| 10 | Manual de despliegue y de vuelta atrás | No | `TASK-054` |
| 11 | Análisis de dependencias en cada cambio | No | `TASK-056` |

### Arquitectura de despliegue propuesta

Suficiente para el volumen actual (decenas de equipos, un organizador) y compatible con lo que ya existe:

```
Internet ──TLS──► Proxy inverso (Caddy o nginx)
                    ├─ /            → estáticos del frontend (build de Vite)
                    ├─ /api/        → API (uvicorn, 2 procesos)   ──► PostgreSQL 16
                    └─ cabeceras de seguridad, compresión,              │ volumen
                       limitación de peticiones, caché corta            ▼
                       para lecturas públicas                    Copia diaria → almacenamiento externo
```

Un solo servidor con Docker Compose es una opción razonable. No hace falta orquestación más compleja mientras no cambie la escala.

**Antes de pasar a varios procesos de API** hay que resolver dos cosas que hoy dependen de que haya uno solo: la caché en memoria del feed (`BE-08`) y las tareas de arranque (`OPS-07`).

## 5. Resumen

| ID | Severidad | Tipo | Resumen |
|---|---|---|---|
| OPS-01 | Alto | Confirmado (estático), no ejecutado | La inicialización del compose aborta y deja la base incompleta |
| OPS-02 | Alto | Confirmado (estático) | Sin despliegue del frontend ni TLS |
| OPS-03 | Alto | Confirmado (estático) | Sin integración continua |
| OPS-04 | Medio | Confirmado (estático) | Sin entornos ni gestión de secretos |
| OPS-05 | Alto | Confirmado (estático) | Copias manuales, restauración sin ensayar |
| OPS-06 | Medio | Confirmado (estático) | Observabilidad insuficiente |
| OPS-07 | Medio | Confirmado (estático) | Purgas solo al arrancar |
| OPS-08 a OPS-13 | Bajo/Medio | Varios | Imagen, reproducibilidad, migraciones, versiones, cliente generado, carga |

Es el área más atrasada, lo que es coherente con un proyecto que hasta ahora se ha usado en una sola máquina de desarrollo. Nada de lo pendiente es difícil; es trabajo que todavía no se ha empezado.
