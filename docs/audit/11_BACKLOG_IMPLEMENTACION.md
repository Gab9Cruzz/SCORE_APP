# 11 — Backlog de implementación

Fase XI: 56 tareas ejecutables, ordenadas por fase y por dependencias. Cada una está escrita para que un agente de programación pueda ejecutarla sin releer todo el diagnóstico.

## Reglas comunes a todas las tareas

1. **Prueba primero.** Escribir la prueba que reproduce el problema y comprobar que falla antes de tocar el código. Los hallazgos de esta auditoría son en su mayoría estáticos: si la prueba pasa sin cambios, detenerse, anotar por qué y cerrar la tarea sin modificar nada más.
2. **Cambios de esquema en tres lugares** (`database/README.md`): `01`–`06` al estado final, una migración idempotente con el siguiente número libre (el último es `33`) y su alta en `SCRIPTS_VIGENTES` de `backend/tests/test_scripts_sql.py`.
3. **Contrato:** si cambia un esquema de Pydantic o una ruta, ejecutar `npm run gen:api` con el backend en marcha y corregir lo que `tsc` señale. No añadir `as never`.
4. **Verificación:** `python -m pytest` en `backend/` y `npm run verify` en `frontend/` antes de dar la tarea por terminada.
5. **No ampliar el alcance.** Si aparece otro problema, anotarlo; no corregirlo dentro de la misma tarea.
6. **Rutas de archivo:** todas las citadas existen en el commit `7d5a365`, salvo las marcadas como *(nuevo)*.

Las referencias `PR-nnn` remiten a la matriz de pruebas de [07_AUDITORIA_QA.md](07_AUDITORIA_QA.md).

---

# Fase 0 — Recuperar la señal

## TASK-001 — Fijar la versión de Node y reparar la suite de Vitest

**Prioridad:** P0

**Categoría:** QA / Frontend

**Problema:** con Node 26.13.1, `localStorage` global vale `undefined` y tapa al de jsdom; `afterEach(() => localStorage.clear())` falla en las 344 pruebas (`QA-01`, `FE-01`, `OPS-09`).

**Objetivo:** que `npm run verify` dé el mismo resultado en cualquier máquina y que la versión de Node admitida quede declarada.

**Archivos afectados:** `frontend/package.json`, `frontend/vite.config.ts`, `frontend/src/test/setup.ts`, `frontend/.nvmrc` *(nuevo)*, `frontend/README.md`.

**Implementación propuesta:**
1. Elegir la versión LTS de Node que se va a soportar y declararla en `engines` y en `.nvmrc`.
2. Hacer la configuración inmune al `localStorage` nativo: en `vite.config.ts`, pasar `--no-experimental-webstorage` a los procesos de prueba (`test.poolOptions.forks.execArgv`), o bien instalar en `setup.ts` una implementación en memoria sobre `globalThis` antes de cualquier uso. Verificar con Node LTS y con Node 26.
3. Quitar `passWithNoTests: true` (`QA-08`).
4. Documentar la versión en `frontend/README.md`.

**Dependencias:** ninguna.

**Criterios de aceptación:**
- [ ] `npx vitest run`, sin variables de entorno, no produce ningún `TypeError` de `localStorage` con la versión fijada ni con Node 26.
- [ ] Como máximo falla la prueba de `TASK-002`.
- [ ] `package.json` declara `engines.node` y existe `.nvmrc`.

**Pruebas requeridas:**
- Ejecución completa de la suite en las dos versiones de Node.
- Regresión: `src/lib/colaOfflineEventos.test.ts` y `src/api/client.test.ts` en verde.

**Estimación:** 2 h

## TASK-002 — Corregir la prueba desactualizada y silenciar el ruido de MSW

**Prioridad:** P1

**Categoría:** QA / Frontend

**Problema:** una aserción de `ModalSiguienteFase.test.tsx` espera dos campos y el componente envía tres (`QA-02`); 90 avisos de peticiones sin manejador ensucian la salida (`QA-07`, `FE-07`).

**Objetivo:** suite del frontend en verde y con salida limpia.

**Archivos afectados:** `frontend/src/pages/torneo-admin/torneo-dashboard/ModalSiguienteFase.test.tsx`, `frontend/src/test/setup.ts`, `frontend/src/test/msw-server.ts`, `frontend/src/App.routing.test.tsx`.

**Implementación propuesta:**
1. Confirmar con `ModalSiguienteFase.tsx` qué campos debe enviar el caso "envía formato_eliminatoria y clasificados_por_grupo elegidos" y actualizar la aserción.
2. Añadir manejadores por defecto para las peticiones que hoy quedan sin responder (la más frecuente: `GET /api/v1/disciplinas/con-partidos`).
3. Configurar `server.listen({ onUnhandledRequest: "error" })` para que una petición no prevista haga fallar la prueba.

**Dependencias:** TASK-001.

**Criterios de aceptación:**
- [ ] 344 de 344 pruebas pasan.
- [ ] La salida no contiene "intercepted a request without a matching request handler".
- [ ] Una petición sin manejador hace fallar la prueba que la provoca.

**Pruebas requeridas:**
- Ejecución completa de Vitest.

**Estimación:** 0,5 h

## TASK-043 — Ejecutar la suite de backend y registrar la línea base

**Prioridad:** P0

**Categoría:** QA / Backend

**Problema:** las 505 pruebas del backend no se ejecutaron en la auditoría por falta de PostgreSQL (`QA-03`). No se sabe si el árbol actual, con 22 archivos modificados sin confirmar, está en verde.

**Objetivo:** conocer el estado real antes de corregir nada.

**Archivos afectados:** ninguno del código; `docs/audit/LINEA_BASE_PRUEBAS.md` *(nuevo)*.

**Implementación propuesta:**
1. En una máquina con PostgreSQL 16, configurar `backend/.env` con `TEST_DATABASE_URL`.
2. Ejecutar `python -m pytest -q -m "not concurrencia"` y `python -m pytest -q -m concurrencia`.
3. Registrar número de pruebas, fallos y duración. Para cada fallo, anotar si lo explica un hallazgo de esta auditoría.
4. Comparar el esquema de la base en uso con el que generan `01`–`06` (`pg_dump --schema-only` de ambas y `diff`) y anotar las diferencias (`DB-10`).

**Dependencias:** ninguna.

**Criterios de aceptación:**
- [ ] Existe el documento de línea base con los resultados de las dos ejecuciones.
- [ ] Cada prueba fallida tiene causa identificada o una tarea abierta.
- [ ] Está documentada la comparación de esquemas.

**Pruebas requeridas:**
- Las dos ejecuciones de pytest.

**Estimación:** 4 h

## TASK-003 — Integración continua mínima

**Prioridad:** P1

**Categoría:** DevOps / QA

**Problema:** la verificación depende de una ejecución manual en Windows (`OPS-03`, `QA-09`, `QA-10`, `BE-11`, `OPS-12`). El propietario la descartó en `TODOS.md`; `QA-01` y `QA-02` son la evidencia nueva para reconsiderarlo. **Requiere su conformidad.**

**Objetivo:** que cada cambio ejecute las dos suites en un entorno fijo.

**Archivos afectados:** `.github/workflows/ci.yml` *(nuevo)*, `backend/requirements-dev.txt` *(nuevo)*, `README.md`, `TODOS.md`.

**Implementación propuesta:**
1. Trabajo `backend`: Python 3.12, servicio `postgres:16`, `pip install -r requirements.txt`, `pytest -m "not concurrencia"` y después `pytest -m concurrencia`.
2. Trabajo `frontend`: Node de `.nvmrc`, `npm ci`, `npm run verify`.
3. Paso de contrato: arrancar la API, ejecutar `npm run gen:api` y fallar si `git diff --exit-code src/api/schema.d.ts` detecta cambios.
4. Añadir `ruff check` al backend como paso informativo (sin bloquear al principio).
5. Mover la entrada de `TODOS.md` de "Descartado" a "Resuelto", con el motivo.

**Dependencias:** TASK-001, TASK-002, TASK-043.

**Criterios de aceptación:**
- [ ] El flujo se ejecuta en cada `push` y en cada solicitud de cambios.
- [ ] Un fallo en cualquiera de las suites marca el cambio en rojo.
- [ ] Un `schema.d.ts` desactualizado hace fallar el flujo.

**Pruebas requeridas:**
- Una rama de prueba con un fallo deliberado en cada suite.

**Estimación:** 6 h

---

# Fase 1 — Estabilización

## TASK-004 — Límite de login no eludible

**Prioridad:** P0

**Categoría:** Seguridad

**Problema:** el contador de fallos usa el nombre de usuario tal como llega y la IP de `X-Forwarded-For` sin validar (`SEC-01`, `SEC-13`).

**Objetivo:** que variar mayúsculas, espacios o la cabecera no reinicie el contador.

**Archivos afectados:** `backend/app/services/usuario.py`, `backend/app/repositories/acceso.py`, `backend/app/core/http.py`, `backend/app/core/config.py`, `backend/.env.example`, `backend/tests/test_rate_limiting_login.py`, `backend/tests/test_accesos.py`.

**Implementación propuesta:**
1. En `UsuarioService.login`, normalizar una vez (`username.strip().lower()`) y usar ese valor para contar, buscar y registrar el acceso.
2. Añadir `trusted_proxies` a `Settings` (lista vacía por defecto). En `ip_del_cliente`, leer `X-Forwarded-For` solo si `request.client.host` está en esa lista; si no, usar `request.client.host`.
3. Añadir un segundo tope por cuenta, independiente de la IP y más alto (por ejemplo 20 fallos en 15 minutos), para frenar ataques distribuidos sin facilitar el bloqueo malicioso de una cuenta con pocos intentos.
4. Calcular un hash de relleno cuando la cuenta no existe, para igualar tiempos.
5. Adaptar las pruebas existentes, que hoy eligen la IP con la cabecera.

**Dependencias:** TASK-043.

**Criterios de aceptación:**
- [ ] Cinco fallos con `admin` y un sexto con `ADMIN ` desde la misma IP devuelven 429.
- [ ] Sin proxies de confianza, cambiar `X-Forwarded-For` en cada intento no evita el 429.
- [ ] Con un proxy de confianza configurado, la bitácora sigue registrando la IP original.
- [ ] El nombre queda normalizado en `ACCESOS`.

**Pruebas requeridas:**
- Integración: PR-030, PR-031.
- Regresión: `test_rate_limiting_login.py` y `test_accesos.py` completos.

**Estimación:** 4 h

## TASK-005 — Rechazar secretos de ejemplo al arrancar

**Prioridad:** P0

**Categoría:** Seguridad / DevOps

**Problema:** contraseña de administrador `admin1234` por defecto y secreto de JWT sin validar (`SEC-02`, `OPS-04`).

**Objetivo:** que un despliegue de producción no pueda arrancar con valores conocidos.

**Archivos afectados:** `backend/app/core/config.py`, `backend/app/main.py`, `backend/.env.example`, `infrastructure/docker-compose.yml`, `infrastructure/README.md`, `backend/tests/test_bootstrap.py`.

**Implementación propuesta:**
1. Añadir `entorno: Literal["desarrollo", "produccion"] = "desarrollo"` a `Settings`.
2. Validador de modelo: si `entorno == "produccion"`, exigir `jwt_secret_key` de 32 caracteres o más y distinto del valor de ejemplo, `admin_password` distinta de `admin1234` y de `change-me-please` y de 12 caracteres o más, y `cors_origins` distinto de `*`. Si no se cumple, lanzar un error que nombre la variable.
3. Quitar el valor por defecto de `ADMIN_PASSWORD` en el compose, igual que ya se hace con `JWT_SECRET_KEY`.

**Dependencias:** TASK-043.

**Criterios de aceptación:**
- [ ] Con `ENTORNO=produccion` y cualquiera de los valores de ejemplo, la aplicación no arranca y el mensaje indica qué variable corregir.
- [ ] En `desarrollo` el comportamiento actual no cambia.
- [ ] El compose falla con un mensaje claro si falta `ADMIN_PASSWORD`.

**Pruebas requeridas:**
- Unitaria: construcción de `Settings` con cada combinación inválida (PR-032).
- Regresión: `test_bootstrap.py`.

**Estimación:** 4 h

## TASK-006 — Inicialización correcta de la base en Docker

**Prioridad:** P0

**Categoría:** DevOps / Base de datos

**Problema:** el compose ejecuta todas las migraciones históricas y los datos de demostración sobre el esquema final; `08` falla y deja la base a medias (`OPS-01`).

**Objetivo:** que `docker compose up` desde un volumen vacío deje una base correcta y sin datos de demostración.

**Archivos afectados:** `infrastructure/docker-compose.yml`, `infrastructure/initdb/` *(nuevo)*, `infrastructure/README.md`, `README.md`, `database/README.md`, `TODOS.md`.

**Implementación propuesta:**
1. Reproducir primero el fallo: `docker compose down -v && docker compose up` y guardar el registro del servicio `postgres`.
2. Crear `infrastructure/initdb/00_init.sh`, que ejecute con `psql -v ON_ERROR_STOP=1` solo `01`–`06` y `11_catalogo_disciplinas.sql` desde `/database` montado en modo lectura.
3. Montar `../database:/database:ro` y `./initdb:/docker-entrypoint-initdb.d:ro`.
4. Datos de demostración como paso opcional documentado (`10_demo_torneos_admin.sql`, `seed_portal_demo.sql`).
5. Corregir el comentario inicial del compose y la nota de `TODOS.md` que dice "no verificado".

**Dependencias:** ninguna (necesita una máquina con Docker).

**Criterios de aceptación:**
- [ ] Desde un volumen vacío, el servicio `postgres` termina la inicialización sin errores.
- [ ] `SELECT count(*) FROM disciplina` devuelve 28 y `SELECT count(*) FROM torneo` devuelve 0.
- [ ] `GET /health` y `POST /api/v1/auth/login` responden.
- [ ] El registro del primer arranque no contiene `ERROR`.

**Pruebas requeridas:**
- Manual documentada: arranque desde cero, dos veces.
- Automatizable en `TASK-046`.

**Estimación:** 4 h

## TASK-008 — Validar la pertenencia del jugador por fecha

**Prioridad:** P1 (planificar junto con TASK-007, antes de ella)

**Categoría:** Base de datos / Backend

**Problema:** `fn_validar_jugador_partido` y la consulta de plantilla en fecha exigen `Estado = 'Activo'` hoy, además de la vigencia por fechas (`FUN-02`).

**Objetivo:** que un jugador sea válido en un partido si su membresía cubría la fecha del partido, aunque después haya sido traspasado o dado de baja.

**Archivos afectados:** `database/06_triggers.sql` (función `fn_validar_jugador_partido`, y la verificación final del archivo), `database/34_migracion_validar_jugador_por_fecha.sql` *(nuevo)*, `backend/app/repositories/estadisticas.py` (`plantilla_equipo_en_fecha`), `backend/tests/test_scripts_sql.py`, `backend/tests/test_traspasos.py`, `backend/tests/test_resultado_directo.py`.

**Implementación propuesta:**
1. Escribir PR-003, PR-004 y PR-005 y comprobar que las dos primeras fallan.
2. En las dos consultas del trigger (jugador y jugador que entra), sustituir `je.Estado = 'Activo'` por `je.Estado IN ('Activo', 'Inactivo', 'Traspasado')` y conservar las condiciones de fecha. `Suspendido` queda fuera.
3. Aplicar el mismo criterio en `plantilla_equipo_en_fecha`.
4. Revisar el caso límite del día del traspaso: origen con `Fecha_Fin = hoy` y destino con `Fecha_Inicio = hoy` son ambos válidos para un partido de hoy. Si no se quiere, dar al cierre de origen `Fecha_Fin = hoy − 1` en `TraspasoService.crear` y cubrirlo con una prueba.
5. Actualizar el bloque de verificación final de `06_triggers.sql` con el mismo criterio.

**Dependencias:** TASK-043.

**Criterios de aceptación:**
- [ ] Tras un traspaso, se puede cargar por resultado directo un partido anterior con el jugador en su equipo de origen.
- [ ] Un jugador cuya membresía empezó después del partido sigue siendo rechazado.
- [ ] Un jugador `Suspendido` sigue siendo rechazado.
- [ ] La migración se ejecuta dos veces sin error.

**Pruebas requeridas:**
- Integración: PR-003, PR-004, PR-005.
- Regresión: `test_db_triggers_equipos_jugadores.py`, `test_traspasos.py`, `test_eventos_partido.py`, `test_convocados_a_partido.py`.

**Estimación:** 6 h

## TASK-007 — Reabrir un torneo restaura sus plantillas

**Prioridad:** P0

**Categoría:** Backend / Base de datos

**Problema:** el cierre da de baja todas las membresías y la reapertura no las repone (`FUN-01`). **Requiere decisión del propietario** entre las dos opciones del paso 2.

**Objetivo:** que tras reabrir se puedan cargar y corregir eventos como antes del cierre.

**Archivos afectados:** `database/06_triggers.sql` (`fn_cerrar_torneo_libera_jugadores`), `backend/app/services/motor_formatos.py` (`reabrir_torneo`), migración *(nueva)*, `backend/tests/test_cierre_torneo.py`.

**Implementación propuesta:**
1. Escribir PR-001 y PR-002 y comprobar que fallan.
2. Elegir:
   - **A (recomendada):** conservar el trigger de cierre. En `reabrir_torneo`, reactivar las membresías del torneo que estén `Inactivo` con `Fecha_Fin` igual a la fecha de `torneo.fecha_cierre` (leer la fecha antes de ponerla a nulo), dejándolas `Activo` con `Fecha_Fin` nula. Si un jugador ya está activo en otro equipo del mismo torneo, no aplica; si la reactivación choca con la exclusividad, informar de esos casos sin abortar.
   - **B:** con `TASK-008` hecha, la validación de eventos ya no depende del estado; bastaría con reactivar solo para que el editor de alineaciones y las altas funcionen.
3. Mutar con el ORM para que quede en `AUDITORIA`.
4. Ampliar la prueba existente de reapertura.

**Dependencias:** TASK-008, TASK-043.

**Criterios de aceptación:**
- [ ] Cerrar, reabrir y registrar un gol de un jugador de la plantilla devuelve 201.
- [ ] La plantilla activa tras reabrir coincide con la de antes del cierre.
- [ ] Una baja manual anterior al cierre no se reactiva.
- [ ] Volver a cerrar sigue funcionando y calcula el podio.

**Pruebas requeridas:**
- Integración: PR-001, PR-002.
- Regresión: `test_cierre_torneo.py`, `test_plantillas.py`.

**Estimación:** 6 h

## TASK-010 — Cerrar el `PATCH` de torneo

**Prioridad:** P0

**Categoría:** Backend

**Problema:** `TorneoUpdate` admite `estado`, `disciplina_id` y `modalidad_id` sin guardas, y fechas invertidas (`FUN-04`, `DB-02`).

**Objetivo:** que el estado de un torneo solo cambie por sus endpoints específicos y que no se pueda dejar incoherente.

**Archivos afectados:** `backend/app/schemas/torneo.py`, `backend/app/services/torneo.py`, `frontend/src/pages/torneo-admin/TorneosAdmin.tsx`, `frontend/src/api/schema.d.ts`, `backend/tests/test_torneos.py`.

**Implementación propuesta:**
1. Buscar en el frontend quién envía `estado` en el `PATCH` de torneo y con qué intención.
2. Quitar `estado` de `TorneoUpdate` y añadir `model_config = ConfigDict(extra="forbid")`. Si la interfaz necesita reactivar un torneo `Inactivo`, crear `POST /torneos/{id}/reactivar`.
3. En `TorneoService.update`, rechazar el cambio de `disciplina_id` o `modalidad_id` si hay inscripciones o partidos (mismo patrón que el bloqueo de `formato`).
4. Validar `fecha_fin >= fecha_inicio` combinando lo recibido con lo guardado.

**Dependencias:** TASK-043.

**Criterios de aceptación:**
- [ ] `PATCH` con `estado` devuelve 422.
- [ ] `PATCH` con otra disciplina en un torneo con inscripciones devuelve 400.
- [ ] `PATCH` que deja la fecha de fin antes de la de inicio devuelve 400 o 422.
- [ ] Cerrar, reabrir y dar de baja siguen funcionando por sus endpoints.
- [ ] El formulario de edición del frontend sigue funcionando.

**Pruebas requeridas:**
- Integración: PR-008, PR-009, PR-010.
- Regresión: `test_torneos.py`, `TorneosAdmin.test.tsx`.

**Estimación:** 4 h

## TASK-011 — Paginación explícita en los listados que cortan en 100

**Prioridad:** P0

**Categoría:** Backend / Frontend

**Problema:** `/plantillas`, `/inscripciones`, `/traspasos` y `/eventos-partido` no declaran `skip` ni `limit`; el servidor corta en 100 y el frontend no se entera (`FUN-05`, `BE-06`, `UX-05`).

**Objetivo:** que ningún listado se trunque sin que el cliente lo sepa.

**Archivos afectados:** `backend/app/api/routes/plantillas.py`, `inscripciones.py`, `traspasos.py`, `eventos_partido.py`; `backend/app/core/paginacion.py` *(nuevo)*; `frontend/src/hooks/useResourceCrud.ts`; `backend/tests/test_plantillas.py`, `test_inscripciones.py`, `test_traspasos.py`, `test_eventos_partido.py`.

**Implementación propuesta:**
1. Escribir PR-011 y PR-012 creando 150 vínculos en un torneo.
2. Declarar en las cuatro rutas `skip: int = Query(0, ge=0)` y `limit: int = Query(100, ge=1, le=200)` y pasarlos al servicio.
3. Devolver el total en la cabecera `X-Total-Count` (no rompe el contrato de lista) con una dependencia común; añadir `expose_headers=["X-Total-Count"]` al middleware de CORS.
4. Para `/eventos-partido` filtrado por partido, subir el máximo a 500: un partido no se pagina.
5. En `useResourceCrud`, leer la cabecera y calcular `truncado` como `total > filas.length`.

**Dependencias:** TASK-043.

**Criterios de aceptación:**
- [ ] Con 150 vínculos, `limit=200` devuelve 150 y `X-Total-Count: 150`.
- [ ] Sin `limit`, devuelve 100 y `X-Total-Count: 150`.
- [ ] `limit=0`, `limit=-1` y `skip=-1` devuelven 422.
- [ ] La pantalla de plantillas muestra el aviso de truncado cuando el total supera lo cargado.

**Pruebas requeridas:**
- Integración: PR-011, PR-012.
- Frontend: prueba de `useResourceCrud` con la cabecera.
- Regresión: los cuatro archivos de prueba citados.

**Estimación:** 5 h

## TASK-012 — Control de Mesa y "Mis partidos" filtran por estado en el servidor

**Prioridad:** P1

**Categoría:** Backend / Frontend

**Problema:** se piden los primeros 100 partidos por ID y se filtra en el navegador (`FUN-06`).

**Objetivo:** que siempre aparezcan los partidos pendientes, sea cual sea el tamaño del torneo.

**Archivos afectados:** `backend/app/api/routes/partidos.py`, `backend/app/services/partido.py`, `backend/app/repositories/partido.py`, `frontend/src/pages/control-mesa/ControlDeMesa.tsx`, `frontend/src/pages/arbitro/MisPartidos.tsx`, `backend/tests/test_partidos.py`, `ControlDeMesa.test.tsx`, `MisPartidos.test.tsx`.

**Implementación propuesta:**
1. Escribir PR-013.
2. Aceptar `estado` repetido (`estado: list[EstadoPartido] | None = Query(None)`) y aplicarlo con `IN`.
3. Añadir `orden: Literal["id", "fecha"] = "id"`.
4. En las dos pantallas, pedir `estado=Programado&estado=En curso&orden=fecha` y eliminar el filtro del cliente.
5. Reutilizar `X-Total-Count` de `TASK-011` y mostrar "ver más" si hay más de una página.

**Dependencias:** TASK-011.

**Criterios de aceptación:**
- [ ] Con 130 partidos y 110 finalizados, la pantalla muestra los 20 pendientes.
- [ ] La lista sale ordenada por fecha.
- [ ] `GET /partidos?estado=Programado` (un solo valor) sigue funcionando.

**Pruebas requeridas:**
- Integración: PR-013.
- Frontend: los dos archivos de prueba actualizados.

**Estimación:** 4 h

## TASK-009 — Proteger las consecuencias de anular eventos en un partido finalizado

**Prioridad:** P1

**Categoría:** Backend / Base de datos

**Problema:** anular un gol tras el cierre puede cambiar el ganador sin actualizar la llave ni el podio (`FUN-03`, `FUN-19`). **Requiere decisión del propietario** (prohibir o recalcular).

**Objetivo:** que el cuadro nunca contradiga el marcador vigente.

**Archivos afectados:** `backend/app/services/evento_partido.py` (`anular`), `backend/app/services/partido.py`, `backend/tests/test_eventos_partido.py`, `backend/tests/test_motor_formatos_llaves.py`.

**Implementación propuesta:**
1. Escribir PR-006 y PR-007.
2. En `anular`, cuando el partido está `Finalizado`, pertenece a una fase de eliminación y el evento es `Gol` o `Autogol`:
   - calcular el ganador antes y después con `fn_marcador_partido` o `fn_resolver_llave` dentro de la transacción;
   - si no cambia, continuar;
   - si cambia y el partido siguiente (o el del perdedor) tiene hitos, rechazar con un mensaje que explique el bloqueo;
   - si cambia y no hay actividad posterior, actualizar los equipos del partido siguiente reutilizando la lógica de `deshacer_fin_forzado`, y exigir desempate si quedó empatado.
3. Tomar el bloqueo de fila del partido también para goles (hoy solo para tarjetas).
4. Para `FUN-19`, documentar en la interfaz que un partido de llave se resuelve por walkover, no cancelándolo; rechazar la cancelación de un partido con `partido_siguiente_id`.

**Dependencias:** TASK-043.

**Criterios de aceptación:**
- [ ] Anular el gol decisivo con la final ya empezada devuelve 400 con un mensaje claro.
- [ ] Anularlo sin actividad posterior deja el partido siguiente con el equipo correcto o exige desempate.
- [ ] Anular un gol que no cambia el ganador funciona como hasta ahora.
- [ ] En fases de liga no cambia nada.

**Pruebas requeridas:**
- Integración: PR-006, PR-007.
- Regresión: `test_eventos_partido.py`, `test_db_triggers_motor_formatos.py`, `test_fin_forzado.py`.

**Estimación:** 8 h

## TASK-013 — Autorización de catálogos globales

**Prioridad:** P1

**Categoría:** Seguridad

**Problema:** cualquier TorneoAdmin puede archivar grupos de torneo ajenos, editar equipos y jugadores de otros y modificar tipos de evento, disciplinas y modalidades (`SEC-04`). **Requiere decisión del propietario** sobre equipos y jugadores.

**Objetivo:** que un TorneoAdmin solo pueda afectar a lo que administra.

**Archivos afectados:** `backend/app/api/routes/torneo_grupos.py`, `eventos.py`, `disciplinas.py`, `modalidades.py`, `equipos.py`, `jugadores.py`, `perfiles.py`; `backend/app/api/deps.py`; `backend/app/repositories/asignacion_torneo_admin.py`; pruebas correspondientes; `frontend/src/pages/torneo-admin/CatalogoDisciplinas.tsx`.

**Implementación propuesta:**
1. Escribir PR-033 y PR-034.
2. Tipos de evento, disciplinas y modalidades: escritura solo con `require_roles("AdminGeneral")`. Ocultar los controles en la interfaz para TorneoAdmin.
3. Grupos de torneo: dependencia nueva que exija una asignación activa a alguna edición del grupo.
4. Equipos, jugadores y perfiles, según la decisión: (a) dejarlos compartidos y limitar solo las acciones destructivas (baja, suspensión) a quien administre un torneo donde participen, o (b) introducir propiedad. La opción (a) no requiere cambio de esquema.

**Dependencias:** TASK-043.

**Criterios de aceptación:**
- [ ] Un TorneoAdmin sin ediciones asignadas en un grupo recibe 403 al archivarlo.
- [ ] Un TorneoAdmin recibe 403 al escribir en `/eventos`, `/disciplinas` y `/modalidades`.
- [ ] AdminGeneral conserva todos los permisos.
- [ ] El TorneoAdmin que creó un torneo puede seguir renombrando su grupo.

**Pruebas requeridas:**
- Integración: PR-033, PR-034.
- Regresión: `test_torneo_grupos.py`, `test_disciplinas.py`, `test_modalidades.py`, `test_eventos.py`, `test_equipos.py`, `test_jugadores.py`.

**Estimación:** 6 h

## TASK-014 — Datos personales y sub-recursos de torneos no publicados

**Prioridad:** P1

**Categoría:** Seguridad

**Problema:** búsqueda anónima por cédula; cédula y correo visibles para cualquier cuenta; sub-recursos de torneos en borrador accesibles por ID (`SEC-05`, `SEC-07`).

**Objetivo:** que los datos personales solo los vean los roles de gestión y que un torneo no publicado no se pueda reconstruir sin sesión.

**Archivos afectados:** `backend/app/api/routes/jugadores.py`, `backend/app/services/jugador.py`, `backend/app/repositories/jugador.py`, `backend/app/api/routes/inscripciones.py`, `plantillas.py`, `traspasos.py`, `torneo_grupos.py`, `grupos.py`, `backend/app/repositories/torneo.py`, `backend/tests/test_jugadores.py`, `test_portal_publico_visibilidad.py`.

**Implementación propuesta:**
1. Escribir PR-036, PR-037 y PR-038.
2. Elegir la proyección con un auxiliar `puede_ver_pii(usuario)` (roles `TorneoAdmin` y `AdminGeneral`), no con "hay sesión".
3. Pasar a `buscar` un indicador `incluir_cedula`; para quien no puede ver datos personales, buscar solo por nombre.
4. En los listados de inscripciones, plantillas y traspasos, para anónimos, añadir la condición `Torneo.publicado` (unión con `TORNEO`).
5. En `/torneo-grupos`, filtrar las ediciones no publicadas para anónimos.
6. Dejar como está la superficie de partido por ID (decisión C17) y documentarlo.

**Dependencias:** TASK-043.

**Criterios de aceptación:**
- [ ] `GET /jugadores?q=<cédula>` sin sesión no devuelve al titular.
- [ ] Las cuentas `Publico` y `Arbitro` no reciben cédula ni correo.
- [ ] Un anónimo no obtiene plantillas ni inscripciones de un torneo no publicado.
- [ ] El panel de administración sigue mostrando todo.

**Pruebas requeridas:**
- Integración: PR-036, PR-037, PR-038.
- Regresión: `test_jugadores.py`, `test_perfil_jugador.py`, `test_portal_publico_visibilidad.py`.

**Estimación:** 3 h

## TASK-015 — Manejo de errores y registro

**Prioridad:** P1

**Categoría:** Backend / Seguridad

**Problema:** todo error del controlador de base se devuelve como 400 con texto de PostgreSQL y no se registra (`BE-04`, `SEC-06`, `UX-12`).

**Objetivo:** que las reglas de negocio lleguen como 400 legibles y lo inesperado como 500 genérico, siempre registrado.

**Archivos afectados:** `backend/app/exceptions/handlers.py`, `backend/app/core/logging.py` *(nuevo)*, `backend/app/main.py`, `frontend/src/api/client.ts`, `backend/tests/test_errores.py` *(nuevo)*.

**Implementación propuesta:**
1. Leer el SQLSTATE con `getattr(exc.orig, "sqlstate", None)`: `P0001` → 400 con el mensaje del `RAISE`; `23505` → 409 con mensaje fijo; `23503`, `23514`, `23502` → 409 o 400 con mensaje genérico por tipo, sin nombre de restricción; `22001` → 422 "texto demasiado largo"; cualquier otro → 500.
2. Manejador para `Exception`: 500 con `{"detail": "Error interno.", "id": <uuid>}` y `logger.exception` con ese identificador.
3. Middleware que asigne un identificador de petición y lo devuelva en `X-Request-ID`.
4. `core/logging.py` con salida JSON a stdout; sustituir los `print` de `main.py`.
5. Añadir a `CODIGOS_ERROR_TRADUCIDOS` los cuatro códigos sin traducir (`jugador_ya_activo_en_este_torneo`, `equipo_ya_asignado_a_otro_grupo_en_esta_fase`, `hito_ya_registrado`, `partido_corrido_sin_ganador`).

**Dependencias:** TASK-043.

**Criterios de aceptación:**
- [ ] Un mensaje de trigger sigue llegando como 400 con el mismo texto.
- [ ] Un fallo de conexión simulado devuelve 500 sin texto de PostgreSQL y deja una línea en el registro con el identificador.
- [ ] Una violación de unicidad devuelve 409 sin nombres de tablas ni restricciones.
- [ ] Toda respuesta incluye `X-Request-ID`.

**Pruebas requeridas:**
- Integración: PR-039 y un caso por SQLSTATE.
- Regresión: toda la suite, porque muchos casos comprueban el texto de `detail`.

**Estimación:** 6 h

## TASK-016 — Guardas en inscripciones y en la baja de equipos

**Prioridad:** P1

**Categoría:** Backend

**Problema:** cancelar una inscripción no cierra las membresías ni mira los partidos; reactivar salta el cupo; se puede inscribir en un torneo cerrado o un equipo inactivo; dar de baja un equipo no comprueba nada (`FUN-07`, `FUN-21`).

**Objetivo:** transiciones de inscripción con reglas explícitas.

**Archivos afectados:** `backend/app/services/inscripcion_torneo.py`, `backend/app/services/equipo.py`, `backend/app/repositories/partido.py`, `backend/tests/test_inscripciones.py`, `backend/tests/test_equipos.py`.

**Implementación propuesta:**
1. Escribir PR-014, PR-015 y PR-016.
2. Sustituir `update` por una función de transición: a `Cancelado`, rechazar si hay partidos `En curso` y avisar de los `Programado`; cerrar las membresías activas con fecha de hoy, en la misma transacción. A `Inscrito` o `Confirmado` desde `Cancelado`, volver a comprobar el cupo con su bloqueo.
3. En el alta por equipo y en la individual: rechazar si el torneo no está `Activo` o si el equipo no está `Activo`. Avisar, sin bloquear, si la modalidad del equipo difiere de la del torneo, salvo que el propietario pida bloquear.
4. En `EquipoService.soft_delete`: rechazar si tiene inscripciones no canceladas en torneos activos.

**Dependencias:** TASK-043. Conviene después de TASK-008.

**Criterios de aceptación:**
- [ ] Tras cancelar una inscripción, sus jugadores pueden darse de alta en otro equipo del mismo torneo.
- [ ] Reactivar con el cupo lleno devuelve 400.
- [ ] Inscribir en un torneo finalizado devuelve 400.
- [ ] Dar de baja un equipo con inscripción activa devuelve 409 con explicación.

**Pruebas requeridas:**
- Integración: PR-014, PR-015, PR-016 y la baja de equipo.
- Regresión: `test_inscripciones.py`, `test_inscripcion_plantilla_base.py`, `test_equipos.py`.

**Estimación:** 6 h

## TASK-017 — Alta en plantilla unificada

**Prioridad:** P1

**Categoría:** Backend

**Problema:** el tope de plantilla y la comprobación de suspensión solo existen en el registro por lote; la edición de vínculos admite cualquier estado y fechas incoherentes; no hay regla para expulsados o sustituidos (`FUN-08`, `FUN-15`, `FUN-20`).

**Objetivo:** una sola regla de alta para los cuatro caminos.

**Archivos afectados:** `backend/app/services/plantilla_reglas.py` *(nuevo)*, `backend/app/services/registro_lote.py`, `jugador_equipo.py`, `traspaso.py`, `inscripcion_torneo.py`, `evento_partido.py`, `backend/app/schemas/jugador_equipo.py`, pruebas de plantillas, traspasos y eventos.

**Implementación propuesta:**
1. Escribir PR-017 y PR-018.
2. Extraer de `registro_lote.py` a `plantilla_reglas.py`: `tope_de_plantilla(modalidad)` y `validar_alta(perfil, inscripcion, torneo)` (perfil de la disciplina del torneo, no suspendido, jugador activo, tope con su bloqueo).
3. Llamarlo desde el alta individual, el traspaso y la copia de plantilla base (en esta última, el exceso se informa como conflicto en vez de abortar).
4. En `JugadorEquipoUpdate`, dejar solo `dorsal`; las bajas van por `/baja` y los cambios de estado por traspaso. Validar `fecha_fin >= fecha_inicio` en `dar_de_baja`.
5. En eventos en vivo, rechazar un evento de un jugador con roja registrada en ese partido o que ya salió por cambio sin haber vuelto a entrar; permitir la corrección por parte de TorneoAdmin con un parámetro explícito si el propietario lo pide.

**Dependencias:** TASK-043.

**Criterios de aceptación:**
- [ ] El alta individual que supera el tope devuelve el mismo mensaje que el lote.
- [ ] Un perfil suspendido no puede darse de alta por ningún camino.
- [ ] `PATCH /plantillas/{id}` con `estado` devuelve 422.
- [ ] Un gol de un jugador expulsado en ese partido devuelve 400.

**Pruebas requeridas:**
- Integración: PR-017, PR-018 y los casos de expulsado y sustituido.
- Regresión: `test_registro_lote.py`, `test_plantillas.py`, `test_traspasos.py`, `test_inscripcion_plantilla_base.py`, `test_eventos_partido.py`.

**Estimación:** 5 h

## TASK-018 — Rehacer sorteo sin pérdida de datos

**Prioridad:** P1

**Categoría:** Backend

**Problema:** el sorteo se puede rehacer si no hay partidos finalizados, aunque haya alguno en curso con eventos (`FUN-11`).

**Objetivo:** que rehacer un sorteo nunca borre actividad registrada.

**Archivos afectados:** `backend/app/services/motor_formatos.py` (`_preparar_rehacer_si_corresponde`), `backend/tests/test_motor_formatos.py`.

**Implementación propuesta:**
1. Escribir PR-022.
2. Rechazar si algún partido de la fase tiene estado distinto de `Programado`, o tiene hitos, eventos o convocados.
3. Mensaje que indique qué partido lo impide.

**Dependencias:** TASK-043.

**Criterios de aceptación:**
- [ ] Con un partido en curso, rehacer devuelve 400 y no borra nada.
- [ ] Con todos los partidos programados y sin actividad, rehacer sigue funcionando.
- [ ] El mensaje de rechazo identifica el partido que lo impide.

**Pruebas requeridas:**
- Integración: PR-022.
- Regresión: `test_motor_formatos.py`, `test_motor_formatos_llaves.py`.

**Estimación:** 2 h

## TASK-019 — Proteger los tipos de evento de sistema

**Prioridad:** P1

**Categoría:** Base de datos / Backend

**Problema:** marcador, tarjetas y cambios se reconocen por el nombre del tipo de evento, que es editable y no único (`FUN-14`, `DB-03`, `ARQ-03`).

**Objetivo:** que la lógica dependa de un identificador estable.

**Archivos afectados:** `database/01_schema.sql`, `02_constraints.sql`, `04_views.sql`, `05_seed.sql`, `06_triggers.sql`, migración *(nueva)*, `backend/app/models/evento.py`, `backend/app/schemas/evento.py`, `backend/app/services/evento.py`, `evento_partido.py`, `partido.py`, `reglas_cambio.py`, `backend/tests/test_eventos.py`.

**Implementación propuesta:**
1. Escribir PR-023.
2. Añadir `EVENTOS.Codigo VARCHAR(30)` único y anulable, con valores `GOL`, `AUTOGOL`, `TARJETA_AMARILLA`, `TARJETA_ROJA`, `CAMBIO` para los cinco tipos existentes (rellenar por nombre en la migración).
3. Cambiar vistas, triggers y servicios para comparar por `Codigo`.
4. En `EventoService`, rechazar renombrar o dar de baja un tipo con `Codigo`, y añadir `UNIQUE (Nombre)`.
5. Exponer `codigo` en `EventoOut` y usarlo en el frontend (`components/eventos.ts`) en lugar del nombre.

**Dependencias:** TASK-043. Coordinar con TASK-013 (mismas rutas).

**Criterios de aceptación:**
- [ ] Renombrar "Gol" devuelve 400.
- [ ] Crear un segundo tipo llamado "Gol" devuelve 409.
- [ ] Marcador, posiciones y goleadores no cambian para los datos existentes.
- [ ] La migración se ejecuta dos veces sin error.

**Pruebas requeridas:**
- Integración: PR-023.
- Regresión: `test_eventos.py`, `test_estadisticas.py`, `test_eventos_partido.py`, `test_resultado_directo.py`, `test_scripts_sql.py`; `eventos.test.ts` en el frontend.

**Estimación:** 4 h

## TASK-020 — `PATCH` con nulo explícito

**Prioridad:** P1

**Categoría:** Backend

**Problema:** `save_changes` descarta los valores `None`; no se puede vaciar ningún campo (`FUN-10`).

**Objetivo:** que un `null` enviado por el cliente limpie el campo cuando este es anulable.

**Archivos afectados:** `backend/app/repositories/base.py`, todos los servicios que llaman a `update` o `save_changes`, `backend/app/services/torneo.py` (quitar el tratamiento especial), pruebas de partidos, jugadores y equipos.

**Implementación propuesta:**
1. Escribir PR-021.
2. Auditar los llamadores de `save_changes` y `update` (unos 25) y clasificar cada uno: pasa un `model_dump(exclude_unset=True)` o pasa argumentos con valores por defecto `None`.
3. Quitar el `if valor is not None` de `save_changes`. En los llamadores del segundo tipo, construir el diccionario solo con lo que realmente se quiere escribir.
4. Para columnas no anulables, convertir un `null` en 422 desde el esquema (campos `Optional` solo donde la columna lo admite).
5. Eliminar el bloque especial de `torneo.py:342-344`.

**Dependencias:** TASK-043. Hacerla antes que TASK-022, que toca los mismos métodos.

**Criterios de aceptación:**
- [ ] `PATCH /partidos/{id}` con `arbitro_id: null` deja el partido sin árbitro.
- [ ] `PATCH /jugadores/{id}` con `foto_url: null` borra la foto.
- [ ] Un `PATCH` que omite un campo no lo modifica.
- [ ] `null` en un campo obligatorio devuelve 422.

**Pruebas requeridas:**
- Integración: PR-021 y un caso por recurso.
- Regresión: toda la suite (es un cambio transversal).

**Estimación:** 5 h

## TASK-021 — Edición de partido restringida para el árbitro

**Prioridad:** P2

**Categoría:** Seguridad / Backend

**Problema:** el árbitro puede cambiar el árbitro asignado, la fecha y la fase de su partido (`SEC-09`, `FUN-22`).

**Objetivo:** que el árbitro solo pueda tocar lo que su papel necesita.

**Archivos afectados:** `backend/app/services/partido.py`, `backend/app/schemas/partido.py`, `backend/tests/test_partidos.py`.

**Implementación propuesta:**
1. Escribir PR-040.
2. En `PartidoService.update`, si el rol es `Arbitro`, rechazar con 403 cualquier clave fuera de los campos de desempate y `ganador_corrido_id`.
3. Validar que `arbitro_id` corresponde a una cuenta activa con rol `Arbitro`.

**Dependencias:** TASK-020.

**Criterios de aceptación:**
- [ ] Un árbitro que envía `arbitro_id` o `fecha_partido` recibe 403.
- [ ] Un TorneoAdmin puede seguir cambiándolos.
- [ ] Asignar como árbitro a una cuenta que no lo es devuelve 400.

**Pruebas requeridas:**
- Integración: PR-040.
- Regresión: `test_partidos.py`, `test_desempate_manual.py`.

**Estimación:** 2 h

---

# Fase 2 — Calidad técnica

## TASK-022 — Transacciones atómicas por caso de uso

**Prioridad:** P1

**Categoría:** Backend / Arquitectura

**Problema:** `BaseRepository` hace `commit` por operación; crear un torneo, registrar un hito con desempate, inscribir con plantilla base y cambiar un rol quedan a medias si falla un paso (`ARQ-02`, `BE-02`, `FUN-18`).

**Objetivo:** que cada caso de uso sea una sola transacción.

**Archivos afectados:** `backend/app/repositories/base.py`, `backend/app/services/torneo.py`, `hito_partido.py`, `inscripcion_torneo.py`, `usuario.py`, `backend/app/repositories/convocado_a_partido.py`, pruebas correspondientes.

**Implementación propuesta:**
1. Escribir PR-024 inyectando un fallo en el último paso de la creación de torneo.
2. Añadir a `BaseRepository.create` y `save_changes` un parámetro `commit: bool = True`. Con `False`, hacer `flush` y no confirmar.
3. En los cuatro servicios citados, usar `commit=False` y un único `await session.commit()` al final.
4. No cambiar el valor por defecto en esta tarea, para acotar el riesgo; dejar anotado que el objetivo final es invertirlo.

**Dependencias:** TASK-020.

**Criterios de aceptación:**
- [ ] Un fallo al crear la configuración de tiempo no deja torneo, grupo ni fase.
- [ ] Un hito de fin rechazado por un trigger no deja escrito el desempate en el partido.
- [ ] El cambio de rol y la baja de asignaciones ocurren juntos o no ocurren.

**Pruebas requeridas:**
- Integración: PR-024 y un caso por servicio con fallo inyectado.
- Regresión: `test_torneos.py`, `test_control_mesa_tiempos.py`, `test_desempate_penales.py`, `test_usuarios.py`.

**Estimación:** 10 h

## TASK-023 — Eliminar consultas N+1

**Prioridad:** P2

**Categoría:** Backend / Rendimiento

**Problema:** el listado de partidos lanza hasta cuatro consultas por fila y el de traspasos dos (`BE-01`, `DB-08`).

**Objetivo:** número de consultas constante por página.

**Archivos afectados:** `backend/app/services/partido.py`, `traspaso.py`, `backend/app/repositories/usuario.py`, `database/03_indexes.sql`, migración *(nueva)*.

**Implementación propuesta:**
1. Prueba que cuente las sentencias ejecutadas (evento `before_cursor_execute`) al listar 50 partidos de eliminación.
2. En `PartidoService.list`, cargar en lote: fases por ID, configuraciones por torneo, conjunto de IDs que son ida de otro partido, y goles de las idas en una consulta agrupada. Hacer que `_a_salida` reciba esos datos.
3. Lo mismo en `TraspasoService.list` para `puede_anularse`.
4. `UsuarioRepository.count` con `SELECT count(*)`.
5. Índice sobre `PARTIDOS(Partido_Ida_ID)`.

**Dependencias:** TASK-043.

**Criterios de aceptación:**
- [ ] Listar 50 partidos ejecuta el mismo número de consultas que listar 5.
- [ ] La respuesta es idéntica a la actual.
- [ ] Existe el índice sobre `PARTIDOS(Partido_Ida_ID)` en `03_indexes.sql` y en la migración.

**Pruebas requeridas:**
- Integración: conteo de consultas.
- Regresión: `test_partidos.py`, `test_traspasos.py`, `test_desempate_penales.py`.

**Estimación:** 5 h

## TASK-024 — Cerrar carreras: titulares, inicio de partido, sorteo

**Prioridad:** P2

**Categoría:** Backend / Base de datos

**Problema:** conteos sin bloqueo en el tope de titulares y en el hito duplicado; sorteo sin serializar; bloqueos consultivos que colisionan (`BE-03`, `BE-09`, `DB-05`).

**Objetivo:** que las tres operaciones sean correctas con peticiones simultáneas.

**Archivos afectados:** `backend/app/services/convocado_a_partido.py`, `hito_partido.py`, `motor_formatos.py`, `backend/app/repositories/torneo.py`, `torneo_grupo.py`, `inscripcion_torneo.py`, `database/03_indexes.sql`, migración *(nueva)*, `backend/tests/test_concurrencia_convocados.py`.

**Implementación propuesta:**
1. Convocatoria: usar `get_or_404_bloqueado` del partido en `agregar` y `reemplazar`.
2. Hitos: índice único parcial `ON HITOS_PARTIDO (Partido_ID) WHERE Tipo_Hito = 'Inicio_Partido'`; bloquear el partido en `registrar`.
3. Sorteo y fixture: bloqueo consultivo por fase.
4. Pasar los bloqueos consultivos a la forma de dos claves `(espacio, id)` con una constante por uso.

**Dependencias:** TASK-022.

**Criterios de aceptación:**
- [ ] PR-050, PR-051 y PR-053 pasan con conexiones reales.
- [ ] Ningún bloqueo consultivo usa la forma de una sola clave.
- [ ] Un segundo `Inicio_Partido` insertado por SQL directo es rechazado por el índice único.

**Pruebas requeridas:**
- Concurrencia: las tres citadas, con `sesiones_paralelas`.
- Regresión: `pytest -m concurrencia` completo.

**Estimación:** 6 h

## TASK-025 — Tabla de posiciones completa

**Prioridad:** P2

**Categoría:** Base de datos

**Problema:** la tabla omite a los equipos sin partidos finalizados y no usa el ganador declarado en torneos de cronómetro corrido (`FUN-09`).

**Objetivo:** tabla correcta desde el primer día y para ambos tipos de cronómetro.

**Archivos afectados:** `database/04_views.sql` (`vw_tabla_posiciones`, `vw_resultados_partidos`), migración *(nueva)*, `backend/tests/test_estadisticas.py`, `frontend/src/pages/Dashboard.tsx`, `pages/publico/DetalleTorneoPublico.tsx`.

**Implementación propuesta:**
1. Escribir PR-019 y PR-020.
2. Partir de los equipos inscritos y no cancelados (y de su grupo, si lo hay) con unión externa a los resultados.
3. Exponer en `vw_resultados_partidos` el ganador declarado y usarlo cuando la configuración del torneo es `Corrido`: 3 puntos al ganador, sin empates.
4. Revisar los consumidores que suponen `pj > 0` (`_podio_desde_tabla`, `generar_playoffs`), que ya comprueban ese caso.
5. Quitar el mensaje "Todavía no hay partidos finalizados" donde ya no aplique.

**Dependencias:** TASK-043.

**Criterios de aceptación:**
- [ ] Un torneo recién sorteado muestra a todos sus equipos con ceros.
- [ ] En cronómetro corrido, el ganador declarado suma 3 puntos sin goles cargados.
- [ ] Las tablas de torneos por periodos no cambian.

**Pruebas requeridas:**
- Integración: PR-019, PR-020.
- Regresión: `test_estadisticas.py`, `test_cierre_torneo.py`, `test_motor_formatos.py`, `test_desempate_manual.py`.

**Estimación:** 6 h

## TASK-026 — Restricciones de base pendientes

**Prioridad:** P2

**Categoría:** Base de datos

**Problema:** estados que admiten nulo y ausencia de comprobaciones de fechas y rangos (`DB-01`, `DB-02`).

**Objetivo:** que la base rechace los valores incoherentes que hoy acepta.

**Archivos afectados:** `database/01_schema.sql`, `02_constraints.sql`, migración *(nueva)*, `backend/tests/test_scripts_sql.py`.

**Implementación propuesta:**
1. La migración comprueba primero que no haya filas infractoras y se detiene con un mensaje si las hay (patrón ya usado en este repositorio).
2. `SET NOT NULL` en las trece columnas `Estado` citadas en `DB-01`.
3. `CHECK` para: fechas de torneo y de membresía, `Equipos_Por_Grupo > 0`, `Clasificados_Por_Grupo > 0`, `Dorsal > 0`, duraciones positivas, `Minuto_Reloj >= 0`, nombres no vacíos.

**Dependencias:** TASK-010, TASK-017, TASK-019.

**Criterios de aceptación:**
- [ ] Insertar un estado nulo falla en todas las tablas citadas.
- [ ] Un torneo con fecha de fin anterior a la de inicio no se puede guardar por SQL.
- [ ] La migración se ejecuta dos veces sin error y se detiene limpiamente con datos inválidos.

**Pruebas requeridas:**
- Integración: un caso por restricción nueva en un archivo de pruebas de base.
- Regresión: `test_scripts_sql.py` y la suite completa.

**Estimación:** 5 h

## TASK-027 — Bloqueo completo de torneo cerrado

**Prioridad:** P2

**Categoría:** Base de datos

**Problema:** se pueden insertar partidos en un torneo finalizado, y convocatorias, inscripciones y plantillas no están cubiertas (`DB-06`).

**Objetivo:** que un torneo cerrado sea inmutable salvo reapertura.

**Archivos afectados:** `database/06_triggers.sql`, migración *(nueva)*, `backend/tests/test_cierre_torneo.py`.

**Implementación propuesta:**
1. Ampliar `trg_partidos_bloquear_torneo_cerrado` a `INSERT OR UPDATE OR DELETE`.
2. Añadir el trigger a `CONVOCADO_A_PARTIDO` e `INSCRIPCIONES_TORNEO`.
3. Excluir expresamente las escrituras que hace el propio cierre (la baja de membresías) y la reapertura.

**Dependencias:** TASK-007.

**Criterios de aceptación:**
- [ ] Crear un partido en un torneo finalizado devuelve el código `torneo_cerrado_resultados_bloqueados`.
- [ ] Añadir un convocado o una inscripción en un torneo finalizado es rechazado.
- [ ] Cerrar y reabrir siguen funcionando.

**Pruebas requeridas:**
- Integración: inserción de partido, convocado e inscripción en torneo cerrado.
- Regresión: `test_cierre_torneo.py`.

**Estimación:** 3 h

## TASK-028 — Zona horaria coherente

**Prioridad:** P2

**Categoría:** Base de datos / Backend / Frontend

**Problema:** todas las fechas son `TIMESTAMP` sin zona; la aplicación compara su reloj con el de la base y el frontend interpreta las fechas como hora local (`BE-05`, `DB-04`, `FE-06`).

**Objetivo:** que el minuto de juego, "hoy" y las ventanas de tiempo sean correctos con cualquier zona del servidor y del navegador.

**Archivos afectados:** `database/01_schema.sql`, `04_views.sql`, migración *(nueva)*, `backend/app/models/*.py` (columnas de fecha), `backend/app/services/evento_partido.py`, `hito_partido.py`, `usuario.py`, `motor_formatos.py`, `backend/app/repositories/acceso.py`, `feed.py`, `backend/app/core/config.py`, `frontend/src/lib/fechas.ts` *(nuevo)*.

**Implementación propuesta:**
1. Decidir con el propietario la zona del negocio (`ZONA_HORARIA`, por ejemplo `America/Guayaquil`) y añadirla a `Settings`.
2. Paso mínimo y de bajo riesgo: dejar de usar `datetime.now()` en comparaciones con columnas de la base; obtener la hora con `SELECT CURRENT_TIMESTAMP` o hacer la comparación en SQL. Unificar `fecha_cierre` con el resto.
3. Paso completo: migrar a `TIMESTAMPTZ` con `ALTER COLUMN … TYPE timestamptz USING columna AT TIME ZONE '<zona>'`, ensayado sobre una copia de la base real. `DateTime(timezone=True)` en los modelos.
4. Calcular "hoy" del feed y `vw_proximos_partidos` en la zona del negocio.
5. En el frontend, un módulo `fechas.ts` con formato y aritmética de días sin `toISOString()`; sustituir las apariciones de `es-AR`.

**Dependencias:** TASK-031 (recomendado), TASK-043. Es la tarea de mayor riesgo técnico: copia de seguridad y ensayo previos obligatorios.

**Criterios de aceptación:**
- [ ] Con la base en UTC y la aplicación en otra zona, el minuto de un evento es correcto.
- [ ] El feed sin fecha muestra el día de la zona del negocio a cualquier hora.
- [ ] Las fechas de partidos existentes se muestran a la misma hora local que antes de migrar.
- [ ] La ventana para deshacer un cierre forzado funciona con relojes distintos.

**Pruebas requeridas:**
- Unitaria: `calcular_minuto_actual` con fechas con zona.
- Integración: feed y próximos partidos con la sesión de PostgreSQL en UTC.
- Frontend: `fechas.test.ts` con desplazamientos positivos y negativos.
- Regresión: `test_minuto_en_vivo.py`, `test_fin_forzado.py`, `test_feed_partidos.py`, `test_rate_limiting_login.py`.

**Estimación:** 10 h

## TASK-029 — Validación de entrada

**Prioridad:** P2

**Categoría:** Backend / Seguridad

**Problema:** cadenas sin longitud, enteros sin rango, listas sin tope y `foto_url` sin esquema (`BE-07`, `SEC-11`).

**Objetivo:** que toda entrada inválida se rechace con 422 antes de llegar a la base.

**Archivos afectados:** `backend/app/schemas/*.py`, `backend/app/api/routes/*.py` (parámetros `skip` y `limit`), pruebas por recurso.

**Implementación propuesta:**
1. Tipos reutilizables en `schemas/_tipos.py` *(nuevo)*: `Nombre100`, `Cedula`, `UrlHttps`, `Dorsal`, `EnteroPositivo`.
2. Aplicarlos con las longitudes de `01_schema.sql`. `EmailStr` para el correo (añade la dependencia `email-validator`).
3. Topes de lista: 100 filas por lote, 300 eventos por resultado directo, 60 convocados.
4. `skip` con `ge=0` y `limit` con `ge=1` en todas las rutas.
5. Normalizar la cédula (quitar espacios y guiones) en un único punto.

**Dependencias:** TASK-015.

**Criterios de aceptación:**
- [ ] Un nombre vacío o de más de 100 caracteres devuelve 422.
- [ ] `skip=-1` devuelve 422 en todas las rutas de listado.
- [ ] Un lote de 101 filas devuelve 422.
- [ ] `foto_url` que no empieza por `https://` devuelve 422.

**Pruebas requeridas:**
- Unitaria: un caso por tipo.
- Regresión: suite completa, por si algún dato de prueba deja de ser válido.

**Estimación:** 5 h

## TASK-030 — Caché del feed acotada

**Prioridad:** P2

**Categoría:** Backend / Seguridad

**Problema:** diccionario en memoria que crece sin límite con claves controladas por visitantes anónimos (`BE-08`, `SEC-08`).

**Objetivo:** memoria acotada y caché válida con varios procesos.

**Archivos afectados:** `backend/app/services/feed.py`, `backend/app/api/routes/partidos.py`, `backend/tests/test_feed_partidos.py`.

**Implementación propuesta:**
1. Sustituir el diccionario por una estructura con tamaño máximo (256 entradas) y expiración; implementarla con `OrderedDict` para no añadir dependencias.
2. Devolver `Cache-Control: public, max-age=60` en el feed y en `/disciplinas/con-partidos`, para que el proxy de `TASK-049` pueda servirla.
3. Acotar `fecha` a un rango razonable (por ejemplo ±2 años).

**Dependencias:** TASK-043.

**Criterios de aceptación:**
- [ ] Tras 1.000 peticiones con fechas distintas, la caché tiene como máximo 256 entradas.
- [ ] Dos peticiones iguales dentro de 60 s ejecutan una sola consulta.
- [ ] La respuesta incluye `Cache-Control`.

**Pruebas requeridas:**
- Unitaria: PR-041.
- Regresión: `test_feed_partidos.py`.

**Estimación:** 4 h

## TASK-031 — Migraciones con registro de versión

**Prioridad:** P2

**Categoría:** Base de datos / DevOps

**Problema:** nada registra qué migración se aplicó en cada base (`ARQ-01`, `DB-10`, `OPS-10`).

**Objetivo:** saber en todo momento el estado de una base y aplicar lo pendiente con un comando.

**Archivos afectados:** `database/00_schema_migrations.sql` *(nuevo)*, `backend/scripts/migrar.py` *(nuevo)*, `database/README.md`, `backend/app/main.py`, `backend/tests/test_scripts_sql.py`.

**Implementación propuesta:**
1. Tabla `SCHEMA_MIGRATIONS (Nombre PRIMARY KEY, Aplicada_En, Checksum)`.
2. `migrar.py`: lista los archivos de migración, compara con la tabla y aplica los pendientes, cada uno en su transacción, registrándolo. Opción `--marcar-hasta NN` para dar de alta una base existente sin ejecutar nada.
3. En una instalación nueva, `01`–`06` insertan como aplicadas todas las migraciones que ya incorporan.
4. Al arrancar, la API registra un aviso si hay migraciones pendientes (sin aplicarlas sola).
5. Mantener el procedimiento manual de copia previa y ensayo; el ejecutor sustituye solo el paso de `psql -1`.

**Dependencias:** TASK-043 (la comparación de esquemas indica desde dónde marcar).

**Criterios de aceptación:**
- [ ] En una base nueva, `migrar.py` informa "nada pendiente".
- [ ] Una migración nueva se aplica una vez y queda registrada.
- [ ] Una migración que falla no deja cambios ni registro.
- [ ] La API avisa al arrancar si falta alguna.

**Pruebas requeridas:**
- Integración: los tres casos anteriores contra una base descartable.
- Regresión: `test_scripts_sql.py`.

**Estimación:** 10 h

## TASK-032 — Cliente tipado sin `as never`

**Prioridad:** P2

**Categoría:** Frontend

**Problema:** 90 conversiones evitan la comprobación de tipos del contrato (`FE-02`, `QA-05`).

**Objetivo:** que un cambio de contrato rompa la compilación en todos los puntos de llamada.

**Archivos afectados:** `frontend/src/hooks/useResourceCrud.ts`, `components/Cronometro.tsx`, `pages/control-mesa/GestionarPartido.tsx`, `pages/control-mesa/ControlDeMesa.tsx`, `pages/torneo-admin/TorneosAdmin.tsx`, `pages/publico/DetalleTorneoPublico.tsx` y el resto de archivos con `as never`; `frontend/src/api/types.ts`.

**Implementación propuesta:**
1. Medir: `grep -rn "as never" src | grep -v test | wc -l` (hoy 90).
2. En las llamadas directas a `api.GET/POST/PATCH`, quitar la conversión y los tipos de respuesta escritos a mano; usar los de `schema.d.ts` a través de `api/types.ts`.
3. `useResourceCrud` es genérico sobre la ruta: tiparlo con las claves de `paths` que admiten cada verbo, o dejar una única conversión documentada dentro del hook y exigir tipos de `schema.d.ts` en sus parámetros genéricos.
4. Regla de lint que prohíba `as never` fuera de ese archivo.

**Dependencias:** TASK-003 (el paso de contrato en CI).

**Criterios de aceptación:**
- [ ] No queda ningún `as never` fuera de `useResourceCrud.ts`.
- [ ] Renombrar un campo en un esquema del backend y regenerar el cliente produce errores de `tsc` en las pantallas que lo usan.
- [ ] La suite sigue en verde.

**Pruebas requeridas:**
- Typecheck y suite completa.

**Estimación:** 8 h

## TASK-033 — Cambio de contraseña propio e invalidación de sesiones

**Prioridad:** P2

**Categoría:** Backend / Frontend / Seguridad

**Problema:** no hay cambio de contraseña propio; los tokens no se pueden invalidar (`FUN-13`, `SEC-03`, `SEC-14`, `UX-15`).

**Objetivo:** que cada usuario gestione su contraseña y que cambiarla cierre las demás sesiones.

**Archivos afectados:** `backend/app/api/routes/auth.py`, `backend/app/services/usuario.py`, `backend/app/core/security.py`, `backend/app/api/deps.py`, `backend/app/models/usuario.py`, `database/01_schema.sql`, migración *(nueva)*, `frontend/src/pages/MiCuenta.tsx` *(nuevo)*, `frontend/src/components/NavBar.tsx`, `frontend/src/App.tsx`.

**Implementación propuesta:**
1. Columna `USUARIOS.Tokens_Validos_Desde TIMESTAMP` anulable.
2. Incluir `iat` en el token. En `_resolver_usuario_autenticado`, rechazar tokens emitidos antes de esa marca.
3. `POST /auth/cambiar-password` (contraseña actual y nueva): verifica, guarda el hash, actualiza la marca y devuelve un token nuevo.
4. Actualizar la marca también cuando un AdminGeneral cambia la contraseña de otro o lo desactiva.
5. Mínimo de 10 caracteres y rechazo de una lista corta de contraseñas comunes.
6. Pantalla "Mi cuenta" y entrada en el menú de usuario.

**Dependencias:** TASK-015.

**Criterios de aceptación:**
- [ ] Un usuario cambia su contraseña conociendo la actual.
- [ ] Un token emitido antes del cambio devuelve 401.
- [ ] Con la contraseña actual incorrecta devuelve 400 y queda en la bitácora de accesos.
- [ ] El administrador creado al arrancar puede cambiar su contraseña desde la interfaz.

**Pruebas requeridas:**
- Integración: los cuatro casos.
- Frontend: prueba de la pantalla.
- Regresión: `test_auth.py`, `test_usuarios.py`, `App.routing.test.tsx`.

**Estimación:** 8 h

---

# Fase 3 — Experiencia de usuario

## TASK-042 — Revisión visual real en cuatro tamaños de pantalla

**Prioridad:** P1

**Categoría:** UX

**Problema:** esta auditoría no pudo ver ninguna pantalla; los hallazgos `UX-01`, `UX-07` y los de responsive son deducciones del CSS.

**Objetivo:** confirmar o descartar esos hallazgos y encontrar lo que el código no muestra.

**Archivos afectados:** ninguno del código; `docs/audit/12_REVISION_VISUAL.md` *(nuevo)* y capturas en `docs/audit/capturas/` *(nuevo)*.

**Implementación propuesta:**
1. Levantar el entorno con datos de demostración (`10_demo_torneos_admin.sql`, `seed_portal_demo.sql`).
2. Recorrer con cada rol: feed, detalle de torneo, partido en vivo, login, dashboard, Control de Mesa, gestión de partido, panel de torneo (cinco pestañas), equipos, jugadores, registro por lote, usuarios, accesos, auditoría.
3. Capturar cada pantalla a 360, 768, 1280 y 1920 px.
4. Anotar por pantalla: desbordamientos, jerarquía, coherencia de botones y espaciados, estados de carga, vacío y error.
5. Probar con teclado: orden de tabulación, foco visible, apertura y cierre de modales.
6. Actualizar la tabla de `05_AUDITORIA_UX_UI.md` marcando cada hallazgo como confirmado o descartado.

**Dependencias:** TASK-006 o un PostgreSQL local.

**Criterios de aceptación:**
- [ ] Hay capturas de las pantallas listadas en los cuatro tamaños.
- [ ] Cada hallazgo `UX-*` clasificado como riesgo potencial queda confirmado o descartado.
- [ ] Los problemas nuevos tienen identificador y severidad.

**Pruebas requeridas:**
- Ninguna automatizada; es una revisión.

**Estimación:** 8 h

## TASK-038 — Confirmación en acciones destructivas

**Prioridad:** P1

**Categoría:** UX / Frontend

**Problema:** dar de baja, cancelar una inscripción y cancelar un partido se ejecutan con un clic (`UX-06`).

**Objetivo:** que ninguna acción destructiva ocurra por un toque accidental.

**Archivos afectados:** `frontend/src/components/admin/ResourceTable.tsx`, `ResourceTable.test.tsx`, `pages/torneo-admin/SimpleResourceAdminPage.tsx`, `EquiposAdmin.tsx`, `torneo-dashboard/EquiposDelTorneo.tsx`, `torneo-dashboard/PartidosDelTorneo.tsx`, `frontend/src/index.css`.

**Implementación propuesta:**
1. En `ResourceTable`, el botón de baja pasa a un estado de confirmación en la misma fila: "¿Dar de baja a «Halcones FC»?" con "Confirmar" y "Cancelar".
2. Propiedad opcional `confirmacion: (fila) => string` para que cada pantalla explique la consecuencia ("Se cancelará la inscripción; sus jugadores quedarán libres").
3. El foco pasa a "Cancelar" al abrir la confirmación; Escape la cierra.

**Dependencias:** ninguna (si TASK-034 ya existe, usar su botón base).

**Criterios de aceptación:**
- [ ] Un clic en "Dar de baja" no ejecuta la baja.
- [ ] La confirmación nombra el elemento afectado.
- [ ] Funciona solo con teclado.

**Pruebas requeridas:**
- Componente: `ResourceTable.test.tsx` con los tres casos.
- Regresión: pruebas de las páginas que usan la tabla.

**Estimación:** 4 h

## TASK-034 — `DESIGN.md` y componentes base

**Prioridad:** P2

**Categoría:** UX / Frontend

**Problema:** no hay sistema de diseño; una hoja de estilos de 2.452 líneas y estilos por pantalla (`UX-11`, `FE-08`).

**Objetivo:** un vocabulario visual mínimo y cuatro componentes base de los que partan los cambios siguientes.

**Archivos afectados:** `DESIGN.md` *(nuevo)*, `frontend/src/index.css`, `frontend/src/components/ui/Button.tsx`, `Field.tsx`, `Table.tsx`, `Modal.tsx` *(nuevos)*, `TODOS.md`.

**Implementación propuesta:**
1. Escribir `DESIGN.md` a partir de lo que ya existe y de `TASK-042`: paleta, escala tipográfica de 6 tamaños, escala de espaciado, radios, estados (carga, vacío, error, éxito), reglas de botones (primario, secundario, destructivo, enlace).
2. Añadir las variables de espaciado y tipografía a `:root`. Subir el contraste del borde de los campos a 3:1 o más.
3. Crear los cuatro componentes extrayendo estilos existentes; no rediseñar.
4. Migrar dos pantallas como ejemplo (`UsuariosAdmin` y `Login`). El resto se migra al tocarlas.
5. Retirar la entrada pendiente de `TODOS.md`.

**Dependencias:** TASK-042.

**Criterios de aceptación:**
- [ ] `DESIGN.md` existe y describe variables y componentes.
- [ ] Los cuatro componentes tienen prueba y se usan en dos pantallas.
- [ ] El borde de los campos alcanza 3:1 sobre su fondo.
- [ ] Ninguna pantalla no migrada cambia de aspecto.

**Pruebas requeridas:**
- Componente: una por componente base.
- Regresión: suite completa y comparación visual manual de las dos pantallas.

**Estimación:** 16 h

## TASK-035 — Modal accesible único

**Prioridad:** P2

**Categoría:** UX / Accesibilidad

**Problema:** nueve modales, uno solo con gestión de foco (`UX-03`).

**Objetivo:** que todos los modales atrapen el foco, cierren con Escape y devuelvan el foco.

**Archivos afectados:** `frontend/src/components/ui/Modal.tsx`, `hooks/useModalFocusTrap.ts`, `components/ModalSustitucion.tsx`, `components/admin/SelectorJugadorBuscable.tsx`, `pages/admin/AsignarTorneosModal.tsx`, `pages/control-mesa/ModalResultadoDirecto.tsx`, `pages/torneo-admin/DetalleEquipo.tsx`, `torneo-dashboard/ModalAgregarInscripcion.tsx`, `ModalGestionarPlantilla.tsx`, `ModalPerfilJugador.tsx`, `ModalSiguienteFase.tsx`.

**Implementación propuesta:**
1. `Modal` con `role="dialog"`, `aria-modal`, `aria-labelledby`, `useModalFocusTrap`, cierre por Escape y por clic en el fondo (desactivable cuando hay datos sin guardar) y bloqueo del desplazamiento de la página.
2. Migrar los nueve modales uno a uno conservando su contenido.
3. En `ModalResultadoDirecto`, pedir confirmación al cerrar si hay eventos cargados.

**Dependencias:** TASK-034.

**Criterios de aceptación:**
- [ ] Los nueve modales usan el componente.
- [ ] En todos, Tab no sale del modal, Escape cierra y el foco vuelve al botón que lo abrió.
- [ ] Ningún modal pierde datos por un Escape accidental.

**Pruebas requeridas:**
- Componente: `Modal.test.tsx`.
- Regresión: las pruebas existentes de cada modal.

**Estimación:** 6 h

## TASK-036 — Navegación responsive, "sin permiso" y 404

**Prioridad:** P2

**Categoría:** UX / Frontend

**Problema:** barra de hasta ocho enlaces sin colapsar; mensaje de login a quien ya tiene sesión; rutas desconocidas redirigen en silencio; `session.id` puede faltar sin aviso (`UX-01`, `UX-02`, `FE-03`, `FE-05`).

**Objetivo:** navegación usable en móvil y estados de acceso veraces.

**Archivos afectados:** `frontend/src/components/NavBar.tsx`, `components/RequireRole.tsx`, `pages/Login.tsx`, `pages/SinPermiso.tsx` y `pages/NoEncontrada.tsx` *(nuevos)*, `App.tsx`, `auth/AuthContext.tsx`, `pages/arbitro/MisPartidos.tsx`, `index.css`, `App.routing.test.tsx`.

**Implementación propuesta:**
1. Por debajo de 900 px, botón de menú con `aria-expanded` que despliega los enlaces en columna.
2. Agrupar Usuarios, Accesos y Auditoría bajo "Administración".
3. `RequireRole`: sin sesión, redirigir a `/login` con `state.from`; con sesión y sin rol, mostrar `SinPermiso` con enlace a la página de inicio del rol.
4. Ruta `*` a `NoEncontrada`.
5. Si `/auth/me` falla tras el login, reintentar una vez; si `session.id` sigue sin valor, mostrar un aviso en "Mis partidos" con botón de reintento.

**Dependencias:** TASK-034, TASK-033 (menú de usuario).

**Criterios de aceptación:**
- [ ] A 360 px la barra de un AdminGeneral no desborda.
- [ ] Un TorneoAdmin en `/admin/usuarios` ve "sin permiso", no "iniciá sesión".
- [ ] Tras iniciar sesión desde una ruta protegida se vuelve a esa ruta.
- [ ] Una ruta inexistente muestra la página 404.

**Pruebas requeridas:**
- Frontend: `App.routing.test.tsx` ampliado; PR-072 en la revisión visual.

**Estimación:** 8 h

## TASK-037 — Accesibilidad de base

**Prioridad:** P2

**Categoría:** Accesibilidad

**Problema:** idioma mal declarado, sin títulos de página, tablas sin cabeceras asociadas, botones repetidos sin contexto, estados sin anunciar (`UX-04`, `UX-13`).

**Objetivo:** cumplir los criterios de nivel A y AA señalados en `05_AUDITORIA_UX_UI.md`.

**Archivos afectados:** `frontend/index.html`, `frontend/src/hooks/useTituloPagina.ts` *(nuevo)*, `components/admin/ResourceTable.tsx`, `components/ui/Table.tsx`, páginas con tablas propias, `App.tsx`, `index.css`.

**Implementación propuesta:**
1. `lang="es"` en `index.html`.
2. Hook `useTituloPagina("Usuarios")` en cada página: "Usuarios · Score-App".
3. `scope="col"` en las cabeceras y `<caption>` oculto visualmente en cada tabla; cabecera "Acciones" en lugar de vacía.
4. `aria-label` con el nombre de la fila en "Editar" y "Dar de baja".
5. Componente `Estado` para carga y error con `role="status"` o `role="alert"`; usarlo en la tabla genérica y en las páginas.
6. Enlace "Saltar al contenido" al inicio y `id` en `<main>`.
7. Regla global `:focus-visible` coherente con el acento.

**Dependencias:** TASK-034.

**Criterios de aceptación:**
- [ ] El análisis automático no reporta infracciones graves ni críticas en las diez pantallas principales.
- [ ] Cada pantalla tiene un título de pestaña propio.
- [ ] Un lector de pantalla anuncia "Editar Halcones FC" y no solo "Editar".

**Pruebas requeridas:**
- Las de `TASK-044`.
- Regresión: suite completa (cambian nombres accesibles que las pruebas consultan).

**Estimación:** 8 h

## TASK-039 — Paginación y búsqueda en listados

**Prioridad:** P2

**Categoría:** UX / Frontend / Backend

**Problema:** los listados cargan hasta 200 filas y filtran en el navegador; listas auxiliares completas para traducir identificadores (`UX-05`, `FE-09`).

**Objetivo:** listados que funcionen igual con 50 que con 5.000 registros.

**Archivos afectados:** `frontend/src/hooks/useResourceCrud.ts`, `components/admin/ResourceTable.tsx`, `components/admin/FiltrosRecurso.tsx`, `pages/torneo-admin/EquiposAdmin.tsx`, `JugadoresAdmin.tsx`, `pages/admin/AuditoriaAdmin.tsx`, `AccesosAdmin.tsx`; `backend/app/api/routes/equipos.py`, `backend/app/repositories/equipo.py`.

**Implementación propuesta:**
1. `useResourceCrud` con `pagina` y `tamano`, usando `X-Total-Count` de `TASK-011` (extender la cabecera a todos los listados).
2. Pie de tabla con "1–50 de 312" y controles anterior y siguiente.
3. Parámetro `q` en `/equipos` (búsqueda por nombre), como ya existe en `/jugadores`.
4. Endpoint o parámetro para resolver nombres por lista de identificadores (`?ids=1,2,3`) en equipos y jugadores, y usarlo en `useFetchFaltantes` en lugar de una petición por identificador.

**Dependencias:** TASK-011, TASK-012, TASK-034.

**Criterios de aceptación:**
- [ ] Con 500 jugadores, la tabla permite llegar al último.
- [ ] Buscar un equipo por nombre consulta al servidor.
- [ ] Control de Mesa no descarga la lista completa de equipos.

**Pruebas requeridas:**
- Integración: `q` e `ids` en equipos.
- Frontend: `useResourceCrud.test.ts` y `ResourceTable.test.tsx` con paginación.

**Estimación:** 10 h

## TASK-040 — Arreglos puntuales: enlace al portal, fechas, formato regional

**Prioridad:** P2

**Categoría:** Frontend

**Problema:** el enlace "Portal público" redirige al dashboard; la aritmética de fechas del feed depende de la zona; `es-AR` repetido (`FUN-12`, `FUN-17`, `FE-06`, `UX-09`).

**Objetivo:** tres correcciones pequeñas e independientes.

**Archivos afectados:** `frontend/src/App.tsx`, `components/NavBar.tsx`, `pages/publico/FeedPartidos.tsx`, `FeedPartidos.test.tsx`, `App.routing.test.tsx`, `frontend/src/lib/fechas.ts`.

**Implementación propuesta:**
1. Ruta `/portal` que muestra siempre `FeedPartidosPage`; el enlace del `NavBar` apunta ahí. `/` conserva su comportamiento.
2. `sumarDias` con aritmética de calendario local: construir la fecha con `new Date(año, mes, día + n)` y formatear con `getFullYear`, `getMonth` y `getDate`. "Hoy" con la misma función, no con `toISOString()`.
3. Constante única de formato regional en `lib/fechas.ts` (si `TASK-028` ya la creó, reutilizarla).

**Dependencias:** ninguna.

**Criterios de aceptación:**
- [ ] Con sesión, "Portal público" muestra el feed.
- [ ] `sumarDias("2026-05-10", 1)` devuelve `2026-05-11` con cualquier desplazamiento horario.
- [ ] No queda ningún `"es-AR"` fuera de `lib/fechas.ts`.

**Pruebas requeridas:**
- Unitaria: `fechas.test.ts` simulando desplazamientos positivos y negativos.
- Frontend: caso nuevo en `App.routing.test.tsx` que haga clic en el enlace.

**Estimación:** 3 h

## TASK-041 — Límite de errores y división de código

**Prioridad:** P2

**Categoría:** Frontend

**Problema:** un error de render deja la pantalla en blanco; el paquete único pesa 527 kB (`FE-03`).

**Objetivo:** fallos contenidos y carga inicial ligera para el portal público.

**Archivos afectados:** `frontend/src/components/ErrorBoundary.tsx` *(nuevo)*, `frontend/src/App.tsx`, `frontend/src/main.tsx`.

**Implementación propuesta:**
1. `ErrorBoundary` de clase con mensaje, botón "Recargar" y registro del error; uno alrededor de las rutas y otro alrededor de `MesaPanel`, para no perder el marcador.
2. `React.lazy` para los módulos de administración, torneo-admin y mesa, con `Suspense` y el estado de carga común.
3. Comprobar el tamaño de los fragmentos con `vite build`.

**Dependencias:** ninguna.

**Criterios de aceptación:**
- [ ] Un error provocado en una página muestra el mensaje de recuperación y la barra de navegación sigue visible.
- [ ] El fragmento inicial que descarga un visitante anónimo pesa menos de 250 kB sin comprimir.
- [ ] El build no emite el aviso de tamaño.

**Pruebas requeridas:**
- Componente: `ErrorBoundary.test.tsx`.
- Regresión: `App.routing.test.tsx` (las rutas diferidas necesitan esperar).

**Estimación:** 4 h

---

# Fase 4 — Pruebas y confiabilidad

## TASK-048 — Matriz de autorización por rol y ruta

**Prioridad:** P1

**Categoría:** QA / Seguridad

**Problema:** los permisos se prueban caso a caso; no hay una comprobación sistemática (`QA-06`) y `SEC-04` pasó sin detectarse.

**Objetivo:** una prueba que recorra todas las rutas de escritura con todos los roles.

**Archivos afectados:** `backend/tests/test_matriz_permisos.py` *(nuevo)*, `backend/tests/conftest.py`, `docs/permisos.md` *(nuevo)*.

**Implementación propuesta:**
1. Tabla declarativa: para cada ruta con `POST`, `PATCH`, `PUT` o `DELETE`, el resultado esperado por actor (anónimo, Publico, Arbitro no asignado, Arbitro asignado, TorneoAdmin sin el torneo, TorneoAdmin con el torneo, AdminGeneral).
2. Prueba parametrizada que construya la petición mínima y compruebe solo 401 o 403 frente a "pasa la autorización".
3. Prueba de exhaustividad: recorrer `app.routes` y fallar si existe una ruta de escritura que no esté en la tabla.
4. Publicar la tabla como `docs/permisos.md`.

**Dependencias:** TASK-013, TASK-014, TASK-021.

**Criterios de aceptación:**
- [ ] Todas las rutas de escritura están en la matriz.
- [ ] Añadir una ruta nueva sin declararla hace fallar la suite.
- [ ] La matriz coincide con el comportamiento tras las tareas de seguridad.

**Pruebas requeridas:**
- La propia matriz (PR-035).

**Estimación:** 8 h

## TASK-044 — Pruebas automáticas de accesibilidad

**Prioridad:** P2

**Categoría:** QA / Accesibilidad

**Problema:** no hay ninguna comprobación automática de accesibilidad (`QA-12`).

**Objetivo:** que las regresiones de accesibilidad se detecten en la suite.

**Archivos afectados:** `frontend/package.json`, `frontend/src/test/a11y.ts` *(nuevo)*, pruebas de las diez pantallas principales.

**Implementación propuesta:**
1. Añadir `vitest-axe` (o `axe-core` directamente) como dependencia de desarrollo.
2. Auxiliar `esperarSinInfracciones(container)` que falle con infracciones graves o críticas.
3. Un caso por pantalla principal y uno por modal (apertura, Tab, Escape, retorno del foco).

**Dependencias:** TASK-035, TASK-037.

**Criterios de aceptación:**
- [ ] Diez pantallas y nueve modales tienen caso de accesibilidad.
- [ ] Quitar una etiqueta de un campo hace fallar la suite.
- [ ] La suite completa sigue en verde.

**Pruebas requeridas:**
- PR-070, PR-071.

**Estimación:** 4 h

## TASK-045 — Pruebas de concurrencia pendientes

**Prioridad:** P2

**Categoría:** QA / Backend

**Problema:** las pruebas reales del tope de titulares y del doble fin de partido siguen pendientes (T23 y T24 en `TODOS.md`).

**Objetivo:** cubrir con conexiones reales las cuatro carreras identificadas.

**Archivos afectados:** `backend/tests/test_concurrencia_convocados.py`, `backend/tests/test_concurrencia_hitos.py` *(nuevo)*, `TODOS.md`.

**Implementación propuesta:**
1. Con `sesiones_paralelas`: PR-050, PR-051, PR-052, PR-053.
2. Envolver cada mitad contenciosa en `asyncio.timeout`, como indica `backend/README.md`.
3. Retirar T23 y T24 de `TODOS.md`.

**Dependencias:** TASK-024.

**Criterios de aceptación:**
- [ ] Las cuatro pruebas pasan diez veces seguidas.
- [ ] `pytest -m concurrencia` completo en verde.
- [ ] `TODOS.md` ya no lista T23 ni T24 como pendientes.

**Pruebas requeridas:**
- Las cuatro citadas.

**Estimación:** 4 h

## TASK-046 — Extremo a extremo de cinco flujos

**Prioridad:** P2

**Categoría:** QA

**Problema:** frontend y backend nunca se prueban juntos (`QA-05`).

**Objetivo:** cinco recorridos reales en navegador contra el entorno de compose.

**Archivos afectados:** `e2e/` *(nuevo)*: `package.json`, `playwright.config.ts`, cinco archivos de especificación; `.github/workflows/ci.yml`.

**Implementación propuesta:**
1. Proyecto Playwright aparte, para no mezclar dependencias con el frontend.
2. Preparación: levantar el compose con un volumen vacío y crear los datos por la API.
3. Implementar PR-060 a PR-064.
4. Trabajo de CI que los ejecute en la rama principal y guarde trazas y capturas si fallan.

**Dependencias:** TASK-006, TASK-003; después de la Fase 1, para no automatizar defectos conocidos.

**Criterios de aceptación:**
- [ ] Los cinco recorridos pasan tres veces seguidas sin fallos intermitentes.
- [ ] Un fallo deja traza y captura.
- [ ] La ejecución completa dura menos de diez minutos.

**Pruebas requeridas:**
- PR-060 a PR-064.

**Estimación:** 16 h

## TASK-047 — Cobertura medida y umbrales

**Prioridad:** P3

**Categoría:** QA

**Problema:** no se mide la cobertura (`QA-04`, `QA-11`).

**Objetivo:** conocer la cobertura real y evitar que baje en los módulos críticos.

**Archivos afectados:** `backend/requirements-dev.txt`, `backend/pytest.ini`, `frontend/package.json`, `frontend/vite.config.ts`, `.github/workflows/ci.yml`.

**Implementación propuesta:**
1. `pytest-cov` en el backend y `@vitest/coverage-v8` en el frontend.
2. Publicar el informe como artefacto de CI.
3. Tras una primera medición, fijar umbral por carpeta (`services/` del backend; `lib/` y `hooks/` del frontend) en el valor medido menos dos puntos.
4. Añadir pruebas a los componentes sin archivo propio que resulten con menor cobertura.

**Dependencias:** TASK-003.

**Criterios de aceptación:**
- [ ] CI publica cobertura de backend y frontend.
- [ ] Bajar del umbral en una carpeta crítica hace fallar el flujo.
- [ ] Los umbrales están documentados con la medición que los originó.

**Pruebas requeridas:**
- Ninguna nueva obligatoria; las que resulten del paso 4.

**Estimación:** 4 h

---

# Fase 5 — Producción

## TASK-051 — Copias automáticas y restauración ensayada

**Prioridad:** P0 (antes de tener datos reales)

**Categoría:** DevOps

**Problema:** las copias son manuales y la restauración no se ha ensayado (`OPS-05`).

**Objetivo:** poder recuperar la base del día anterior en un tiempo conocido.

**Archivos afectados:** `infrastructure/backup/backup.sh` y `restore.sh` *(nuevos)*, `infrastructure/docker-compose.prod.yml` *(nuevo, compartido con TASK-050)*, `docs/runbook-backups.md` *(nuevo)*.

**Implementación propuesta:**
1. Servicio de copia en el compose de producción: `pg_dump -Fc` diario a un volumen propio, con nombre fechado.
2. Retención: 7 diarias, 4 semanales, 6 mensuales.
3. Copia fuera del servidor (almacenamiento de objetos o `rsync`), con las credenciales como secreto.
4. `restore.sh` que restaure en una base nueva y ejecute comprobaciones básicas (recuentos de tablas principales).
5. Ensayar la restauración completa, cronometrarla y documentarla.
6. Alerta si la última copia tiene más de 26 horas.

**Dependencias:** TASK-006.

**Criterios de aceptación:**
- [ ] Hay una copia diaria durante tres días seguidos sin intervención.
- [ ] Una restauración ensayada recupera los datos y su duración está documentada.
- [ ] Existe una copia fuera del servidor.
- [ ] `docker compose down -v` en producción no elimina las copias.

**Pruebas requeridas:**
- Ensayo de restauración documentado.

**Estimación:** 6 h

## TASK-049 — Imagen del frontend, proxy inverso con TLS y cabeceras

**Prioridad:** P1

**Categoría:** DevOps / Seguridad

**Problema:** no hay artefacto del frontend, ni TLS, ni cabeceras de seguridad, ni limitación de peticiones (`OPS-02`, `OPS-08`, `SEC-03`, `SEC-08`, `SEC-17`, `SEC-18`, `BE-12`).

**Objetivo:** un despliegue con un solo punto de entrada HTTPS.

**Archivos afectados:** `frontend/Dockerfile` *(nuevo)*, `infrastructure/proxy/Caddyfile` *(nuevo)*, `infrastructure/docker-compose.prod.yml`, `backend/Dockerfile`, `backend/requirements.txt`, `backend/requirements-dev.txt`, `frontend/.env.example`.

**Implementación propuesta:**
1. `frontend/Dockerfile` en dos etapas: `npm ci && npm run build` con `VITE_API_BASE_URL` vacío (mismo origen) y una imagen de servidor de estáticos.
2. Proxy inverso (Caddy, por su TLS automático): `/api/*` y `/health*` a la API; el resto a los estáticos con `try_files` hacia `index.html`.
3. Cabeceras: `Strict-Transport-Security`, `Content-Security-Policy` (`default-src 'self'`; `img-src 'self' https: data:`), `X-Content-Type-Options`, `Referrer-Policy`, `frame-ancestors 'none'`.
4. Limitación de peticiones por IP en `/api/v1/auth/login` y en las rutas públicas; el proxy fija `X-Forwarded-For` y la API confía solo en él (`TASK-004`).
5. API: separar dependencias de prueba, fijar la imagen base por resumen, `HEALTHCHECK`, dos procesos.
6. La API y la base no publican puertos al anfitrión.

**Dependencias:** TASK-004, TASK-005, TASK-050.

**Criterios de aceptación:**
- [ ] `docker compose -f docker-compose.prod.yml up` sirve la aplicación por HTTPS en un solo dominio.
- [ ] Recargar el navegador en `/torneos/1` funciona.
- [ ] Las cabeceras citadas están presentes.
- [ ] El puerto 5432 no es accesible desde fuera.
- [ ] La imagen de la API no contiene pytest.

**Pruebas requeridas:**
- Los recorridos de `TASK-046` contra este compose.
- Comprobación de cabeceras con `curl -I`.

**Estimación:** 10 h

## TASK-050 — Configuración por entorno y secretos

**Prioridad:** P1

**Categoría:** DevOps / Seguridad

**Problema:** un solo compose de desarrollo con secretos débiles, CORS abierto y documentación de la API pública (`OPS-04`, `SEC-10`, `SEC-15`, `SEC-16`, `DB-09`, `DB-13`, `BE-14`).

**Objetivo:** que producción tenga su propia configuración, segura por defecto.

**Archivos afectados:** `infrastructure/docker-compose.prod.yml`, `infrastructure/.env.example` *(nuevo)*, `backend/app/main.py`, `backend/app/core/config.py`, `database/roles.sql` *(nuevo)*.

**Implementación propuesta:**
1. Compose de producción sin valores por defecto para secretos, leídos de un `.env` no versionado o de secretos de Docker.
2. Con `ENTORNO=produccion`: `docs_url=None`, `redoc_url=None`, `openapi_url=None`; CORS limitado al dominio.
3. Rol de PostgreSQL para la aplicación sin permiso `DELETE`, salvo en las tablas que lo necesitan (`PARTIDOS`, `GRUPO`, `GRUPO_EQUIPO`, `HITOS_PARTIDO`, `CONVOCADO_A_PARTIDO`, `ACCESOS`, `AUDITORIA`) y sin propiedad del esquema.
4. Decidir con el propietario la retención de bitácoras y fijarla en la configuración de producción.

**Dependencias:** TASK-005.

**Criterios de aceptación:**
- [ ] En producción, `/docs` devuelve 404.
- [ ] Una petición desde otro origen no recibe cabeceras CORS.
- [ ] La aplicación funciona con el rol restringido y la suite pasa con él.
- [ ] No hay ningún secreto en archivos versionados.

**Pruebas requeridas:**
- Integración: suite completa con el rol restringido.
- Manual: `/docs` y CORS en el compose de producción.

**Estimación:** 4 h

## TASK-052 — Observabilidad

**Prioridad:** P1

**Categoría:** DevOps / Backend

**Problema:** sin comprobación real de salud, sin métricas ni alertas (`OPS-06`, `OPS-13`, `BE-10`).

**Objetivo:** enterarse de una caída antes que los usuarios y poder diagnosticarla.

**Archivos afectados:** `backend/app/main.py`, `backend/app/api/routes/salud.py` *(nuevo)*, `infrastructure/docker-compose.prod.yml`, `docs/runbook-operacion.md` *(nuevo)*.

**Implementación propuesta:**
1. `/health/live` (el proceso responde) y `/health/ready` (`SELECT 1` con tiempo máximo de 2 s). Mantener `/health` como alias del primero.
2. `healthcheck` del servicio `api` contra `/health/ready`.
3. Registro de acceso en JSON con identificador de petición, usuario, ruta, estado y duración (apoyado en `TASK-015`).
4. Guardar la referencia de las tareas de arranque y cerrar el motor al apagar.
5. Monitor externo sencillo que consulte `/health/ready` cada minuto y avise.
6. Prueba de carga breve del sondeo del partido en vivo (por ejemplo 200 espectadores) para dimensionar.
7. Manual: qué mirar ante cada alerta.

**Dependencias:** TASK-015.

**Criterios de aceptación:**
- [ ] Con la base detenida, `/health/ready` devuelve 503 y `/health/live` 200.
- [ ] Cada petición deja una línea JSON con su duración.
- [ ] Una caída de la base genera un aviso en menos de cinco minutos.
- [ ] Está documentado cuántos espectadores simultáneos soporta la configuración elegida.

**Pruebas requeridas:**
- Integración: las dos rutas de salud con la base disponible y con fallo simulado.

**Estimación:** 8 h

## TASK-053 — Mantenimiento programado y servidor de producción

**Prioridad:** P2

**Categoría:** DevOps / Backend

**Problema:** las purgas solo corren al arrancar y el servidor es un único proceso (`OPS-07`, `ARQ-06`).

**Objetivo:** mantenimiento periódico y capacidad para más de un proceso.

**Archivos afectados:** `backend/app/main.py`, `backend/scripts/purgar_bitacoras.py` *(nuevo)*, `infrastructure/docker-compose.prod.yml`.

**Implementación propuesta:**
1. Extraer las purgas a un script ejecutable y programarlo a diario (servicio con `cron` en el compose o `pg_cron`).
2. Quitar las purgas del arranque, o protegerlas con un bloqueo consultivo para que solo las ejecute un proceso.
3. Proteger igual la creación del administrador inicial.
4. Arrancar con dos procesos y tiempos de espera definidos.

**Dependencias:** TASK-030, TASK-052.

**Criterios de aceptación:**
- [ ] La purga se ejecuta a diario sin reiniciar la API.
- [ ] Con dos procesos, el administrador inicial se crea una sola vez.
- [ ] El feed responde correctamente con dos procesos.

**Pruebas requeridas:**
- Integración: `test_bootstrap.py` con dos arranques simultáneos; purga con filas antiguas.

**Estimación:** 4 h

## TASK-054 — Manual de despliegue y vuelta atrás

**Prioridad:** P2

**Categoría:** DevOps / Documentación

**Problema:** no hay procedimiento de despliegue, versiones ni vuelta atrás (`OPS-11`).

**Objetivo:** que desplegar y revertir sean pasos escritos y repetibles.

**Archivos afectados:** `docs/runbook-despliegue.md` *(nuevo)*, `backend/app/main.py`, `frontend/package.json`.

**Implementación propuesta:**
1. Versión semántica única, etiqueta de git por despliegue e imágenes etiquetadas con ella.
2. Procedimiento: copia previa, migraciones con el ejecutor, despliegue, comprobaciones posteriores.
3. Vuelta atrás: imagen anterior y, si hubo migración, restauración de la copia previa; indicar qué migraciones son reversibles.
4. Lista de comprobación previa al primer despliegue con los P0 de este backlog.

**Dependencias:** TASK-031, TASK-049, TASK-051.

**Criterios de aceptación:**
- [ ] Una persona que no escribió el manual despliega siguiéndolo.
- [ ] Se ha ensayado una vuelta atrás.
- [ ] La API expone su versión en `/health`.

**Pruebas requeridas:**
- Ensayo documentado de despliegue y de vuelta atrás.

**Estimación:** 4 h

## TASK-056 — Dependencias: actualización y análisis automático

**Prioridad:** P2

**Categoría:** Seguridad / DevOps

**Problema:** ocho vulnerabilidades en herramientas de desarrollo del frontend; dependencias de Python sin analizar (`SEC-12`).

**Objetivo:** dependencias al día y avisos automáticos.

**Archivos afectados:** `frontend/package.json`, `frontend/package-lock.json`, `backend/requirements.txt`, `.github/workflows/ci.yml`, `.github/dependabot.yml` *(nuevo)*.

**Implementación propuesta:**
1. `npm audit fix` y actualizar `vite`, `vitest` y `openapi-typescript` a las versiones corregidas; ejecutar `npm run verify`.
2. `pip-audit -r requirements.txt` y actualizar lo que señale.
3. Paso de CI con `npm audit --audit-level=high` y `pip-audit`, informativo al principio.
4. Actualizaciones automáticas semanales agrupadas.

**Dependencias:** TASK-003.

**Criterios de aceptación:**
- [ ] `npm audit` no reporta vulnerabilidades altas.
- [ ] `pip-audit` se ejecuta en CI y su resultado queda visible.
- [ ] Las dos suites siguen en verde tras actualizar.

**Pruebas requeridas:**
- Regresión: suites completas.

**Estimación:** 3 h

## TASK-055 — Actualizar la documentación desactualizada

**Prioridad:** P3

**Categoría:** Documentación

**Problema:** varios documentos de entrada ya no describen el sistema (`ARQ-05`).

**Objetivo:** que quien llegue al repositorio lea lo que hay.

**Archivos afectados:** `backend/README.md`, `frontend/README.md`, `backend/Dockerfile`, `infrastructure/docker-compose.yml`, `backend/pytest.ini`, `backend/app/main.py`, `Enceder.txt`, `README.md`, `TODOS.md`.

**Implementación propuesta:**
1. `backend/README.md`: tabla con los cuatro roles reales, qué lecturas son públicas y lista de endpoints actual.
2. `frontend/README.md`: páginas actuales, retirar la mención a `Convocatoria.tsx`, versión de Node.
3. Corregir los comentarios que citan asyncpg como controlador de la aplicación.
4. Sustituir `Enceder.txt` por la sección equivalente del README o eliminarlo.
5. En `main.py`, corregir la remisión a una nota de `TODOS.md` que ya no existe.
6. Añadir a `README.md` un enlace a `docs/audit/`.

**Dependencias:** conviene al final, cuando las demás tareas hayan cambiado lo que se documenta.

**Criterios de aceptación:**
- [ ] Ninguno de los desajustes listados en `ARQ-05` sigue presente.
- [ ] Un clon nuevo se levanta siguiendo solo el README.
- [ ] El README raíz enlaza esta auditoría.

**Pruebas requeridas:**
- Revisión por una persona que siga el README desde cero.

**Estimación:** 3 h

---

## Índice de tareas

| Tarea | Fase | Prioridad | Horas | Hallazgos que cierra |
|---|---|---|---:|---|
| TASK-001 | 0 | P0 | 2 | QA-01, QA-08, FE-01, OPS-09 |
| TASK-002 | 0 | P1 | 0,5 | QA-02, QA-07, FE-07 |
| TASK-003 | 0 | P1 | 6 | OPS-03, OPS-12, QA-09, QA-10, BE-11 |
| TASK-004 | 1 | P0 | 4 | SEC-01, SEC-13 |
| TASK-005 | 1 | P0 | 4 | SEC-02, OPS-04 |
| TASK-006 | 1 | P0 | 4 | OPS-01 |
| TASK-007 | 1 | P0 | 6 | FUN-01 |
| TASK-008 | 1 | P1 | 6 | FUN-02 |
| TASK-009 | 1 | P1 | 8 | FUN-03, FUN-19 |
| TASK-010 | 1 | P0 | 4 | FUN-04 |
| TASK-011 | 1 | P0 | 5 | FUN-05, BE-06, UX-05 |
| TASK-012 | 1 | P1 | 4 | FUN-06 |
| TASK-013 | 1 | P1 | 6 | SEC-04 |
| TASK-014 | 1 | P1 | 3 | SEC-05, SEC-07 |
| TASK-015 | 1 | P1 | 6 | BE-04, SEC-06, UX-12 |
| TASK-016 | 1 | P1 | 6 | FUN-07, FUN-21 |
| TASK-017 | 1 | P1 | 5 | FUN-08, FUN-15, FUN-20 |
| TASK-018 | 1 | P1 | 2 | FUN-11 |
| TASK-019 | 1 | P1 | 4 | FUN-14, DB-03, ARQ-03 |
| TASK-020 | 1 | P1 | 5 | FUN-10 |
| TASK-021 | 1 | P2 | 2 | SEC-09, FUN-22 |
| TASK-022 | 2 | P1 | 10 | ARQ-02, BE-02, FUN-18 |
| TASK-023 | 2 | P2 | 5 | BE-01, DB-08 |
| TASK-024 | 2 | P2 | 6 | BE-03, BE-09, DB-05 |
| TASK-025 | 2 | P2 | 6 | FUN-09 |
| TASK-026 | 2 | P2 | 5 | DB-01, DB-02 |
| TASK-027 | 2 | P2 | 3 | DB-06 |
| TASK-028 | 2 | P2 | 10 | BE-05, DB-04, FE-06 |
| TASK-029 | 2 | P2 | 5 | BE-07, SEC-11 |
| TASK-030 | 2 | P2 | 4 | BE-08, SEC-08 |
| TASK-031 | 2 | P2 | 10 | ARQ-01, DB-10, OPS-10 |
| TASK-032 | 2 | P2 | 8 | FE-02 |
| TASK-033 | 2 | P2 | 8 | FUN-13, SEC-03, SEC-14, UX-15 |
| TASK-034 | 3 | P2 | 16 | UX-11, FE-08 |
| TASK-035 | 3 | P2 | 6 | UX-03 |
| TASK-036 | 3 | P2 | 8 | UX-01, UX-02, FE-05 |
| TASK-037 | 3 | P2 | 8 | UX-04, UX-13 |
| TASK-038 | 3 | P1 | 4 | UX-06 |
| TASK-039 | 3 | P2 | 10 | UX-05, FE-09 |
| TASK-040 | 3 | P2 | 3 | FUN-12, FUN-17, UX-09 |
| TASK-041 | 3 | P2 | 4 | FE-03 |
| TASK-042 | 3 | P1 | 8 | Verificación de UX-01, UX-07 y del responsive |
| TASK-043 | 0 | P0 | 4 | QA-03 |
| TASK-044 | 4 | P2 | 4 | QA-12 |
| TASK-045 | 4 | P2 | 4 | QA-06 (concurrencia) |
| TASK-046 | 4 | P2 | 16 | QA-05 |
| TASK-047 | 4 | P3 | 4 | QA-04, QA-11 |
| TASK-048 | 4 | P1 | 8 | QA-06 (permisos) |
| TASK-049 | 5 | P1 | 10 | OPS-02, OPS-08, SEC-17, SEC-18, BE-12 |
| TASK-050 | 5 | P1 | 4 | SEC-10, SEC-15, SEC-16, DB-09, DB-13, BE-14 |
| TASK-051 | 5 | P0 | 6 | OPS-05 |
| TASK-052 | 5 | P1 | 8 | OPS-06, OPS-13, BE-10 |
| TASK-053 | 5 | P2 | 4 | OPS-07, ARQ-06 |
| TASK-054 | 5 | P2 | 4 | OPS-11 |
| TASK-055 | 5 | P3 | 3 | ARQ-05 |
| TASK-056 | 5 | P2 | 3 | SEC-12 |
| **Total** | | | **321,5** | |

### Hallazgos sin tarea en este ciclo

| Hallazgo | Motivo |
|---|---|
| `ARQ-04`, `FE-04`, `BE-13` (archivos y funciones grandes) | Se reducen al tocar cada archivo; una tarea dedicada sería una reescritura sin beneficio funcional |
| `FUN-16` (modalidad individual sin partidos) | Decisión de producto pendiente |
| `DB-07` (columnas heredadas), `DB-11` (vistas anidadas), `DB-12` (índice de trigramas) | Sin impacto al volumen actual; revisar cuando haya datos de uso |
| `UX-07` (tema claro), `UX-08` (edición masiva de fechas), `UX-10` (subida de imágenes), `UX-14` (actualización automática del feed) | Mejoras P3; priorizar tras la revisión visual |
