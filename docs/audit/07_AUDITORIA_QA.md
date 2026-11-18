# 07 — Auditoría de QA y pruebas

Fase VII: qué pruebas existen, cuáles se pudieron ejecutar y con qué resultado, y qué falta.

## 1. Resultados reales de ejecución

Todo lo de esta sección se ejecutó en la máquina de auditoría (Windows 10, Node 26.13.1, npm 11.20.0, Python 3.12.5) el 2026-11-16.

| Suite | Comando | Resultado |
|---|---|---|
| Lint del frontend | `npx oxlint` | **Correcto.** 0 errores, 1 aviso (`GestionarPartido.tsx:235`, `set-state-in-effect`) |
| Tipos del frontend | `npx tsc -b --noEmit` | **Correcto.** Sin errores |
| Pruebas del frontend, tal cual | `npx vitest run` | **Falla. 38 de 38 archivos, 344 de 344 pruebas** |
| Pruebas del frontend, con el almacenamiento web de Node desactivado | `NODE_OPTIONS=--no-experimental-webstorage npx vitest run` | **343 pasan, 1 falla** (37 de 38 archivos) en 104 s |
| Build de producción | `npx vite build --outDir <carpeta temporal>` | **Correcto**, con aviso de tamaño (527 kB) |
| Pruebas del backend | `python -m pytest` | **No ejecutadas** (`QA-03`) |
| Pruebas de concurrencia | `pytest -m concurrencia` | **No ejecutadas** (`QA-03`) |
| `verificar.ps1` completo | — | **No ejecutado**: su primer paso es pytest |

El archivo `frontend/verify-output.txt` que ya estaba en el árbol de trabajo (sin versionar, de una ejecución anterior del propietario) muestra el mismo fallo masivo, así que no es un efecto de esta auditoría.

## 2. Hallazgos

### QA-01 — La suite del frontend falla entera con la versión de Node instalada

- **Tipo:** Confirmado (ejecutado). **Severidad:** Alto.
- **Ubicación:** `frontend/src/test/setup.ts:36` (`afterEach(() => localStorage.clear())`); `frontend/package.json` (sin campo `engines`); no existe `.nvmrc` ni `.node-version`.
- **Evidencia:**
  ```
  (node:10576) ExperimentalWarning: localStorage is not available because --localstorage-file was not provided.
  TypeError: Cannot read properties of undefined (reading 'clear')
   ❯ src/test/setup.ts:36:30
   Test Files  38 failed (38)
        Tests  344 failed (344)
  ```
- **Causa:** Node 26 trae un `localStorage` global propio que, sin la opción `--localstorage-file`, vale `undefined` y tapa al que aporta jsdom. El `afterEach` global revienta en cada prueba. No es un defecto de la aplicación.
- **Comprobación:** desactivando esa característica de Node con una variable de entorno, sin tocar el proyecto, pasan 343 de 344.
- **Impacto:** `npm run verify` y `verificar.ps1` no pueden dar verde en esta máquina. El criterio de "terminado" del proyecto ("ver todo en verde", `README.md`) queda sin efecto, y un fallo real pasa inadvertido entre 344 falsos: es exactamente lo que ocurrió con `QA-02`.
- **Recomendación:** fijar la versión de Node (`engines` y `.nvmrc`) y hacer la configuración de pruebas inmune a esta característica. `TASK-001`.

### QA-02 — Una prueba quedó desactualizada

- **Tipo:** Confirmado (ejecutado). **Severidad:** Medio.
- **Ubicación:** `frontend/src/pages/torneo-admin/torneo-dashboard/ModalSiguienteFase.test.tsx`, caso "envía formato_eliminatoria y clasificados_por_grupo elegidos".
- **Evidencia:** `AssertionError: expected { clasificados_por_grupo: 2, …(2) } to deeply equal { clasificados_por_grupo: 2, …(1) }`. El componente envía un campo más de los que la prueba espera (el método de desempate, añadido con el plan de tiempo extra y penales). El archivo tiene cambios sin confirmar en el árbol de trabajo, así que puede ser trabajo en curso.
- **Recomendación:** actualizar la aserción. `TASK-002`.

### QA-03 — La suite del backend no pudo ejecutarse

- **Tipo:** No verificable. **Severidad:** Alto, por la incertidumbre que deja.
- **Motivo:** las pruebas reconstruyen una base PostgreSQL real desde `database/01`–`06` (`backend/tests/conftest.py`). En la máquina de auditoría no hay PostgreSQL (sin servicio, sin puerto 5432, sin binarios), ni Docker, ni los trae la distribución de WSL. No se instaló nada para no alterar el equipo.
- **Consecuencia:** no se puede afirmar que las 505 pruebas pasen hoy. `TODOS.md` las da por verdes al 2026-09-18 (526 recolectadas, contando las parametrizadas). Desde entonces hay 22 archivos con cambios sin confirmar; son triviales (`from __future__ import annotations`), pero no están verificados.
- **Recomendación:** ejecutar la suite completa, incluida la de concurrencia, en un entorno con PostgreSQL y guardar el resultado como línea base antes de empezar las correcciones. `TASK-043`.

### QA-04 — No se mide la cobertura

- **Tipo:** Confirmado (estático). **Severidad:** Medio.
- **Evidencia:** ni `pytest-cov` en `backend/requirements.txt`, ni `@vitest/coverage-*` en `frontend/package.json`, ni configuración de cobertura en `pytest.ini` o `vite.config.ts`.
- **Impacto:** el número de pruebas es alto, pero no se sabe qué ramas quedan sin ejercitar. Varios defectos de este informe están en caminos sin prueba (`FUN-01`, `FUN-03`, `FUN-04`, `FUN-05`).
- **Recomendación:** medir primero; fijar umbral después, sobre los módulos críticos. `TASK-047`.

### QA-05 — No hay pruebas de extremo a extremo

- **Tipo:** Confirmado (estático). **Severidad:** Medio.
- **Descripción:** el frontend se prueba contra una API simulada (MSW) y el backend contra un cliente HTTP interno. Nunca se ejercitan juntos. La protección del contrato recae en los tipos generados, que 90 conversiones `as never` evitan (`FE-02`). `FUN-05` es un ejemplo de fallo que solo aparece al juntarlos: el frontend envía `limit: 200`, el backend lo ignora, y cada lado pasa sus pruebas.
- **Recomendación:** cinco recorridos con Playwright sobre el entorno de compose. `TASK-046`.

### QA-06 — Escenarios críticos sin prueba

- **Tipo:** Confirmado (estático), buscando por nombre en `backend/tests/`. **Severidad:** Medio.

| Escenario | Estado | Hallazgo relacionado |
|---|---|---|
| Reabrir un torneo y cargar un evento | Sin prueba (`test_cierre_torneo.py:322` solo verifica el podio) | `FUN-01` |
| Evento de un partido anterior a un traspaso o una baja | Sin prueba | `FUN-02` |
| Anular un gol decisivo en un partido de llave ya finalizado | Sin prueba | `FUN-03` |
| `PATCH` de torneo con `estado`, `disciplina_id` o fechas invertidas | Sin prueba | `FUN-04` |
| Listados con más de 100 filas | Sin prueba | `FUN-05` |
| Límite de login variando mayúsculas o la cabecera de IP | Sin prueba; las pruebas existentes usan la cabecera para elegir IP | `SEC-01` |
| Un TorneoAdmin modifica catálogos o grupos ajenos | Sin prueba | `SEC-04` |
| Búsqueda anónima por cédula | Sin prueba | `SEC-05` |
| Tabla de posiciones con cronómetro corrido o con equipos sin jugar | Sin prueba | `FUN-09` |
| Rehacer sorteo con un partido en curso | Sin prueba | `FUN-11` |
| Reactivar una inscripción con el cupo lleno | Sin prueba | `FUN-07` |
| Carrera en el tope de titulares y doble fin de partido con conexiones reales | Pendiente, reconocido como T23 y T24 en `TODOS.md` | `BE-03` |

### Hallazgos menores

| ID | Tipo | Severidad | Hallazgo | Evidencia | Tarea |
|---|---|---|---|---|---|
| QA-07 | Confirmado (ejecutado) | Bajo | 90 avisos "intercepted a request without a matching request handler" durante las pruebas del frontend; la salida es tan ruidosa que un fallo real cuesta de ver | salida de Vitest | `TASK-002` |
| QA-08 | Confirmado (estático) | Bajo | `passWithNoTests: true` sigue activo; se puso para una fase en la que aún no había pruebas | `frontend/vite.config.ts:15` | `TASK-001` |
| QA-09 | Confirmado (estático) | Medio | Sin integración continua: la verificación depende de que alguien ejecute `verificar.ps1` (solo Windows). `TODOS.md` lo lista como descartado a propósito | `verificar.ps1`; ausencia de `.github/` | `TASK-003` |
| QA-10 | Mejora | Bajo | Las pruebas de concurrencia son opcionales (`-Concurrencia`), así que pueden pasar semanas sin ejecutarse | `verificar.ps1:61` | `TASK-003` |
| QA-11 | Mejora | Bajo | Componentes relevantes sin archivo de prueba propio: `BracketView.tsx` (310 líneas), `ModalGestionarPlantilla.tsx` (299), `AlineacionEditor.tsx` (286), `ModalPerfilJugador.tsx` (234), `AsignarTorneosModal.tsx` (180), `AuthContext.tsx` (141), `Login.tsx`, `NavBar.tsx`. Algunos se ejercitan indirectamente desde la prueba de la página que los contiene | comparación de archivos `.tsx` y `.test.tsx` | `TASK-047` |
| QA-12 | Mejora | Bajo | Sin pruebas de accesibilidad automatizadas ni de regresión visual | — | `TASK-044` |

## 3. Valoración de la estrategia existente

### Backend (análisis estático de `backend/tests/`)

| Aspecto | Valoración |
|---|---|
| Volumen | 51 archivos, 505 funciones de prueba, 8 de ellas de concurrencia real |
| Tipo | Predominan las pruebas de API de punta a punta contra una base real: prueban a la vez ruta, servicio, repositorio y trigger. Es la decisión correcta para un sistema cuyas reglas viven en la base |
| Aislamiento | Cada prueba dentro de una transacción con punto de guardado que se revierte; base reconstruida por sesión desde los mismos `.sql` que una instalación nueva |
| Seguridad del arnés | `_verificar_nombre_de_base_de_test` impide ejecutar contra una base que no sea de pruebas (`conftest.py:90`) |
| Datos | Fixtures por rol (`admin_general_headers`, `torneo_admin_headers`, `arbitro_headers`, `arbitro_no_asignado_headers`, `torneo_admin_con_torneo_headers`) y datos del `05_seed.sql` |
| Triggers | Pruebas dedicadas (`test_db_triggers_equipos_jugadores.py`, `test_db_triggers_motor_formatos.py`) |
| Scripts SQL | `test_scripts_sql.py` ejecuta dos veces los scripts de datos y las migraciones vigentes, y exige que todo archivo de `database/` esté clasificado |
| Concurrencia | Fixture `sesiones_paralelas` con dos conexiones reales y base propia; marcador registrado con `--strict-markers` |
| Autorización | 25 archivos comprueban 401 o 403 |
| Unidades puras | `test_motor_formatos_algoritmos.py`, `test_reglamento_torneo.py` |
| Lo que falta | Cobertura medida, matriz sistemática de permisos por rol y ruta, los escenarios de `QA-06` |

### Frontend

| Aspecto | Valoración |
|---|---|
| Volumen | 38 archivos, 344 casos |
| Tipo | Pruebas de componente y de página con Testing Library sobre MSW; pruebas unitarias de la lógica pura |
| Enrutado por rol | `App.routing.test.tsx` cubre redirecciones y accesos |
| Buenas prácticas | Consultas por rol y por texto visible; limpieza de sesión entre pruebas (lo mismo que hoy rompe la suite) |
| Lo que falta | Extremo a extremo, accesibilidad, manejadores para todas las peticiones, flujo de autenticación |

## 4. Matriz de pruebas recomendadas

Prioridad: P0 antes de corregir o de producción · P1 con la corrección correspondiente · P2 ciclo de calidad.

### Regresión de los defectos funcionales

| ID | Módulo | Escenario | Resultado esperado | Prioridad |
|---|---|---|---|---|
| PR-001 | Torneos | Cerrar un torneo, reabrirlo y registrar un gol de un jugador de la plantilla | 201; el evento se guarda | P0 |
| PR-002 | Torneos | Cerrar, reabrir y consultar la plantilla de un equipo | Mismos jugadores activos que antes del cierre | P0 |
| PR-003 | Partidos | Traspasar a un jugador y después cargar por resultado directo un partido anterior con su equipo de origen | 200; evento acreditado al equipo de origen | P1 |
| PR-004 | Partidos | Lo mismo tras una baja con `fecha_fin` posterior al partido | 200 | P1 |
| PR-005 | Partidos | Evento de un jugador cuya membresía empezó después del partido | 400 con mensaje de fecha | P1 |
| PR-006 | Llaves | Anular el gol decisivo de una semifinal finalizada cuya final ya empezó | 400 que explica el bloqueo | P1 |
| PR-007 | Llaves | Anular el gol decisivo cuando el partido siguiente no tiene actividad | El equipo del partido siguiente se actualiza o se exige desempate | P1 |
| PR-008 | Torneos | `PATCH /torneos/{id}` con `estado: "Finalizado"` | 422: campo no admitido | P0 |
| PR-009 | Torneos | `PATCH` cambiando `disciplina_id` con inscripciones | 400 | P0 |
| PR-010 | Torneos | `PATCH` con `fecha_fin` anterior a `fecha_inicio` | 422 | P1 |
| PR-011 | Plantillas | Torneo con 150 vínculos: `GET /plantillas?torneo_id=X&limit=200` | 150 filas y total 150 | P0 |
| PR-012 | Plantillas | Misma consulta sin `limit` | 100 filas, total 150, indicación de que hay más | P0 |
| PR-013 | Mesa | Torneo con 130 partidos, 110 finalizados: `GET /partidos?estado=Programado&estado=En curso` | Los 20 pendientes, por fecha | P0 |
| PR-014 | Inscripciones | Cancelar una inscripción con jugadores activos | Membresías cerradas; los jugadores pueden ir a otro equipo | P1 |
| PR-015 | Inscripciones | Reactivar una inscripción con el cupo lleno | 400 de cupo | P1 |
| PR-016 | Inscripciones | Inscribir en un torneo finalizado o un equipo inactivo | 400 | P1 |
| PR-017 | Plantillas | Alta individual que supera el tope de la modalidad | 400, mismo mensaje que el lote | P1 |
| PR-018 | Plantillas | Alta individual de un perfil suspendido | 400 | P1 |
| PR-019 | Estadísticas | Torneo recién sorteado, sin partidos jugados | Todos los equipos con ceros | P2 |
| PR-020 | Estadísticas | Liga con cronómetro corrido: partido finalizado con ganador declarado y sin goles | 3 puntos al ganador | P2 |
| PR-021 | Partidos | `PATCH /partidos/{id}` con `arbitro_id: null` | El árbitro queda sin asignar | P1 |
| PR-022 | Sorteo | Rehacer el sorteo con un partido en curso con eventos | 400; nada se borra | P1 |
| PR-023 | Catálogo | Renombrar el tipo de evento "Gol" | 400: tipo de sistema | P1 |
| PR-024 | Torneos | Fallo simulado al crear la configuración de tiempo durante el alta | No queda torneo ni fase | P2 |

### Seguridad

| ID | Módulo | Escenario | Resultado esperado | Prioridad |
|---|---|---|---|---|
| PR-030 | Auth | 5 fallos con `admin` y el sexto con `ADMIN` desde la misma IP | 429 | P0 |
| PR-031 | Auth | 6 fallos, cada uno con un `X-Forwarded-For` distinto, sin proxy de confianza | 429 al sexto | P0 |
| PR-032 | Config | Arranque en modo producción con `ADMIN_PASSWORD=admin1234` o con el secreto de ejemplo | El proceso termina con un error claro | P0 |
| PR-033 | Permisos | TorneoAdmin sin el grupo asignado hace `PATCH /torneo-grupos/{id}` con `estado: "Archivado"` | 403 | P1 |
| PR-034 | Permisos | TorneoAdmin hace `POST`, `PATCH` o `DELETE` sobre `/eventos` | 403 | P1 |
| PR-035 | Permisos | Matriz completa: cada ruta de escritura con cada rol y sin sesión | Coincide con la tabla de permisos declarada | P1 |
| PR-036 | Privacidad | `GET /jugadores?q=<cédula>` sin sesión | Lista vacía | P1 |
| PR-037 | Privacidad | `GET /jugadores/{id}` con rol `Publico` o `Arbitro` | Sin cédula ni correo | P1 |
| PR-038 | Privacidad | `GET /plantillas?torneo_id=<no publicado>` sin sesión | 404 o lista vacía | P2 |
| PR-039 | Errores | Fallo de conexión a la base simulado | 500 genérico con identificador, sin texto de PostgreSQL, registrado en el log | P1 |
| PR-040 | Árbitro | `PATCH /partidos/{id}` con `arbitro_id` o `fecha_partido` | 403 o 422 | P2 |
| PR-041 | Feed | 1.000 peticiones con fechas distintas | El tamaño de la caché no supera el máximo configurado | P2 |

### Concurrencia

| ID | Módulo | Escenario | Resultado esperado | Prioridad |
|---|---|---|---|---|
| PR-050 | Convocatoria | Dos altas simultáneas de titulares distintos con un cupo libre | Entra uno; el otro recibe 400 | P2 |
| PR-051 | Cronómetro | Dos `Inicio_Partido` simultáneos | Un solo hito; el segundo, 409 o 400 | P2 |
| PR-052 | Cronómetro | Dos `Fin_Partido` simultáneos | Un solo hito (índice único) | P2 |
| PR-053 | Sorteo | Dos sorteos simultáneos de la misma fase | Una sola llave | P2 |

### Extremo a extremo

| ID | Flujo | Resultado esperado | Prioridad |
|---|---|---|---|
| PR-060 | Alta completa: torneo, tres equipos, plantillas por lote, fixture | El fixture aparece en el panel y en el portal una vez publicado | P2 |
| PR-061 | Partido en vivo: alineación, inicio, gol, doble amarilla, cambio, fin | Marcador y tabla de posiciones correctos en el portal | P2 |
| PR-062 | Resultado directo en una eliminatoria con penales | El ganador avanza en la llave | P2 |
| PR-063 | Acceso por rol: árbitro, TorneoAdmin sin torneo, cuenta con licencia revocada | Cada uno ve lo que le corresponde | P2 |
| PR-064 | Cerrar el torneo, reabrirlo y corregir un resultado | Podio recalculado | P2 |

### Accesibilidad y responsive

| ID | Escenario | Resultado esperado | Prioridad |
|---|---|---|---|
| PR-070 | Análisis automático con axe de las diez pantallas principales | Sin infracciones graves ni críticas | P2 |
| PR-071 | Abrir y cerrar cada modal solo con teclado | Foco atrapado, Escape cierra, foco de vuelta al origen | P2 |
| PR-072 | Barra de navegación de AdminGeneral a 360, 768 y 1280 px | Sin desbordamiento horizontal | P2 |

## 5. Resumen

| ID | Severidad | Tipo | Resumen |
|---|---|---|---|
| QA-01 | Alto | Confirmado (ejecutado) | 344 de 344 pruebas del frontend fallan con Node 26 |
| QA-02 | Medio | Confirmado (ejecutado) | Una aserción desactualizada |
| QA-03 | Alto | No verificable | Backend sin ejecutar por falta de PostgreSQL |
| QA-04 | Medio | Confirmado (estático) | Sin cobertura |
| QA-05 | Medio | Confirmado (estático) | Sin extremo a extremo |
| QA-06 | Medio | Confirmado (estático) | Doce escenarios críticos sin prueba |
| QA-07 a QA-12 | Bajo/Medio | Varios | Ruido, configuración residual, sin CI, concurrencia opcional, componentes sin prueba, sin accesibilidad |

La base de pruebas es amplia y bien planteada; es de lo mejor del proyecto. El problema hoy no es la falta de pruebas sino que la señal está rota: en esta máquina la mitad de la verificación da rojo por un motivo ajeno al código, y por eso un fallo real pasó sin verse.
