# Auditoría integral de SCORE_APP

**Fecha:** 2026-11-16
**Base auditada:** rama `main`, commit `7d5a365` más el árbol de trabajo sin commitear (22 archivos con cambios menores: `from __future__ import annotations` en servicios/repositorios y dos ajustes de tipos en el frontend).
**Alcance:** backend (FastAPI), frontend (React + Vite + TypeScript), base de datos (PostgreSQL, SQL puro), infraestructura (Docker Compose), pruebas, documentación y scripts.
**Regla respetada:** no se modificó ningún archivo del proyecto. Lo único que esta auditoría agrega al repositorio es esta carpeta `docs/audit/`, que no existía (se verificó antes de crearla, así que no se sobrescribió nada).

## Cómo leer estos documentos

| # | Documento | Qué contiene |
|---|---|---|
| 01 | [Análisis de arquitectura](01_ANALISIS_ARQUITECTURA.md) | Mapa del sistema, módulos, flujos, fortalezas y riesgos iniciales |
| 02 | [Auditoría funcional](02_AUDITORIA_FUNCIONAL.md) | Matriz por módulo, escenarios y hallazgos `FUN-*` |
| 03 | [Auditoría de backend](03_AUDITORIA_BACKEND.md) | Arquitectura, API, rendimiento y calidad — hallazgos `BE-*` |
| 04 | [Auditoría de base de datos](04_AUDITORIA_BASE_DATOS.md) | Modelo, constraints, triggers, vistas, concurrencia — hallazgos `DB-*` |
| 05 | [Auditoría de UX/UI y frontend](05_AUDITORIA_UX_UI.md) | Diseño, usabilidad, responsive, accesibilidad, calidad técnica — `UX-*` y `FE-*` |
| 06 | [Auditoría de seguridad](06_AUDITORIA_SEGURIDAD.md) | OWASP Top 10 / API Top 10 — hallazgos `SEC-*` |
| 07 | [Auditoría de QA](07_AUDITORIA_QA.md) | Estado real de las suites, huecos y matriz de pruebas — `QA-*` |
| 08 | [Auditoría de DevOps](08_AUDITORIA_DEVOPS.md) | Contenedores, despliegue, backups, observabilidad — `OPS-*` |
| 09 | [Evaluación global](09_EVALUACION_GLOBAL.md) | Puntuación ponderada y nivel de confianza |
| 10 | [Roadmap de mejoras](10_ROADMAP_MEJORAS.md) | Plan por fases, dependencias, esfuerzo, DoD |
| 11 | [Backlog de implementación](11_BACKLOG_IMPLEMENTACION.md) | 56 tareas ejecutables `TASK-001…056` |
| 12 | [Revisión visual](12_REVISION_VISUAL.md) | TASK-042: capturas en 4 tamaños, veredicto de cada `UX-*` y hallazgos nuevos `UX-16…26` |

## Convenciones

**Identificadores.** Cada hallazgo tiene un ID estable con prefijo de área (`ARQ`, `FUN`, `BE`, `DB`, `FE`, `UX`, `SEC`, `QA`, `OPS`). El roadmap y el backlog referencian esos IDs; ninguna tarea existe sin un hallazgo detrás.

**Tipo de hallazgo.** Cada uno declara cómo se llegó a él:

| Tipo | Significado |
|---|---|
| **Confirmado (ejecutado)** | Se reprodujo corriendo algo en esta máquina (pruebas, build, script aislado). |
| **Confirmado (estático)** | El defecto se deduce de forma directa del código leído, con archivo y línea, pero no se ejecutó. |
| **Riesgo potencial** | El código lo permite, pero depende de condiciones (carga, concurrencia, configuración de despliegue) que no se probaron. |
| **Mejora** | No es un defecto: es una recomendación de calidad. |
| **No verificable** | No se pudo comprobar en este entorno; se explica qué haría falta. |

**Severidad:** Crítico, Alto, Medio, Bajo, Informativo. **Prioridad** (en roadmap y backlog): P0 antes de producción, P1 corto plazo, P2 calidad, P3 futuro.

## Limitaciones de esta auditoría (importante)

Estas tres limitaciones bajan la confianza de varias conclusiones y están repetidas donde aplican:

1. **La suite de backend no se ejecutó.** La máquina de auditoría no tiene PostgreSQL ni Docker (se comprobó: sin servicio, sin puerto 5432, sin binarios, y la distro de WSL tampoco los trae). Los 505 tests de `backend/tests/` necesitan una base real, así que todo lo relativo a backend y base de datos es **análisis estático**. No se instaló nada para no alterar el equipo.
2. **No hubo evaluación visual.** Sin backend no se pueden recorrer las pantallas con datos, y no se contó con un navegador automatizado. Todo lo de UX/UI sale de leer componentes y CSS, más un cálculo de contraste sobre la paleta. Ninguna pantalla se declara "probada visualmente".
3. **`docker compose` no se ejecutó.** El hallazgo sobre la inicialización de la base (`OPS-01`) se apoya en el código, en la documentación del propio repositorio y en el comportamiento documentado de la imagen oficial de PostgreSQL.

Lo que sí se ejecutó: lint (`oxlint`), typecheck (`tsc -b --noEmit`), la suite de Vitest completa (dos veces, ver `QA-01`), un build de producción hacia una carpeta temporal fuera del repo, `npm audit`, y dos scripts aislados para reproducir aritmética de fechas.

## Revisión final de los entregables

Antes de cerrar se hizo una revisión cruzada de los doce documentos. Resultado:

| Comprobación | Resultado |
|---|---|
| ¿Se revisaron todos los módulos? | Sí: los 21 routers, 30 servicios, el esquema `01`–`06` completo, las vistas, las 20 funciones de trigger, la infraestructura y el frontend. Con lectura completa: rutas, servicios de partido, eventos, hitos, torneo, inscripción, traspaso, motor de formatos y registro por lote. Por muestreo: modelos ORM, migraciones `09`–`33`, y los componentes grandes del frontend (`MesaPanel`, `Cronometro`, `TorneosAdmin`, `ModalResultadoDirecto`), de los que se leyeron estructura y llamadas a la API pero no cada rama |
| ¿Directorios omitidos? | `backend/scripts/` y `docs/plans/` se consultaron por referencia, no se auditaron línea a línea. Los 21 planes no se contrastaron uno por uno contra el código |
| ¿Cada hallazgo tiene evidencia? | Sí: archivo y línea, o salida de una herramienta. 122 hallazgos, todos con tipo declarado |
| ¿Se confundieron riesgos con defectos? | Se separan con la columna "Tipo". Solo 9 hallazgos se apoyan en algo ejecutado o simulado en esta máquina; el resto de los confirmados lo son por lectura de código y así se indica |
| ¿Recomendaciones contradictorias? | Se detectó y resolvió una: `TASK-007` y `TASK-008` tocan la misma regla y se ordenaron explícitamente. `TASK-003` contradice una decisión registrada en `TODOS.md`; se señala y se deja a criterio del propietario |
| ¿Referencias cruzadas coherentes? | Verificado con un script: ningún ID de hallazgo, tarea o prueba referenciado queda sin definir; los 122 hallazgos aparecen en el backlog, con tarea o con motivo para no tenerla |
| ¿Estimaciones coherentes? | La suma de las 56 fichas (321,5 h) coincide con el índice y con el roadmap |
| ¿Criterios de aceptación verificables? | Cada tarea tiene al menos tres, formulados como comportamiento observable |
| ¿El roadmap respeta dependencias? | Sí; ver la sección 6 del roadmap |
| ¿Compatibles con la arquitectura? | Sí: ninguna tarea cambia de framework, de ORM ni de estrategia de esquema |
| ¿Se respetó la prohibición de modificar código? | Sí. `git status` muestra los mismos 22 archivos modificados que al empezar (60 inserciones, 1 eliminación, sin cambios) y como único añadido esta carpeta. Las pruebas y el build escribieron solo en `node_modules/.tmp` y en una carpeta temporal fuera del repositorio |

## Resumen en una pantalla

- **Estado global: 65/100 — "Necesita mejoras"**, con confianza media.
- **Lo mejor del proyecto:** disciplina de diseño poco habitual (un plan por módulo con decisiones y alternativas), reglas de negocio defendidas en la base con triggers y constraints, cliente de API generado desde OpenAPI, 505 + 344 pruebas, RBAC por torneo con licencias, auditoría de cambios y bitácora de accesos.
- **Lo más urgente:** seis defectos funcionales de severidad alta alrededor del ciclo de vida del torneo y los listados (`FUN-01` a `FUN-06`), el límite de intentos de login que se puede eludir (`SEC-01`), credenciales por defecto (`SEC-02`), la inicialización del `docker-compose` (`OPS-01`) y una suite de frontend que hoy falla entera en esta máquina por la versión de Node (`QA-01`).
- **Para producción hace falta además:** despliegue del frontend con TLS, backups automáticos con restauración probada, CI, observabilidad y separación de entornos.
- **Esfuerzo estimado:** unas 320 horas en total; unas 150 para el camino mínimo a producción.
