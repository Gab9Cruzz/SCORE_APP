# 10 — Roadmap de mejoras

Fase X: plan estratégico construido sobre los hallazgos de los documentos 01 a 08. Cada tarea está detallada en [11_BACKLOG_IMPLEMENTACION.md](11_BACKLOG_IMPLEMENTACION.md).

## 1. Resumen ejecutivo

SCORE_APP tiene un núcleo sólido (modelo de datos, reglas de negocio defendidas en la base, flujo de mesa, contrato de API generado, más de 800 pruebas) y tres frentes abiertos:

1. **Corrección funcional.** Seis defectos altos alrededor del ciclo de vida del torneo y de los listados. Se manifiestan al corregir resultados o al superar unos cien registros por torneo.
2. **Seguridad de configuración y de acceso.** El límite de login se elude, hay credenciales por defecto y los catálogos globales no están acotados.
3. **Operación.** No existe todavía un camino de despliegue: ni empaquetado del frontend, ni TLS, ni copias automáticas, ni integración continua. Y la verificación local está en rojo por la versión de Node.

El plan propone **56 tareas en seis fases, unas 320 horas**. El camino mínimo a una producción responsable (Fases 0, 1 y la parte P0/P1 de la 5) son unas **150 horas**. No hace falta reescribir nada: todas las tareas son cambios localizados sobre la arquitectura actual.

## 2. Estado actual

| Dimensión | Puntos | Lectura |
|---|---:|---|
| Funcionalidad | 68 | Amplia y bien resuelta en el camino principal; falla al corregir y al crecer |
| Arquitectura | 72 | Limpia y documentada |
| Backend | 70 | Coherente; faltan atomicidad, paginación y registro de errores |
| Base de datos | 72 | Muy defendida; tres reglas con efecto combinado incorrecto |
| Frontend | 66 | Bien tipado; suite en rojo en esta máquina |
| UX/UI | 60 | Sin verificar visualmente; accesibilidad de base pendiente |
| Seguridad | 55 | Buenos cimientos, configuración débil |
| QA | 62 | Mucha prueba, señal rota |
| DevOps | 35 | Sin empezar |
| **Global** | **65** | **Necesita mejoras** |

## 3. Principales problemas

| # | Problema | Hallazgos | Por qué importa |
|---|---|---|---|
| 1 | Reabrir un torneo lo deja sin plantillas | `FUN-01` | La función existe para corregir, y es lo que no permite |
| 2 | Listados cortados en 100 sin aviso | `FUN-05`, `FUN-06`, `UX-05` | El usuario percibe pérdida de datos a partir de torneos medianos |
| 3 | Límite de login eludible y credenciales por defecto | `SEC-01`, `SEC-02` | Acceso de administrador por fuerza bruta |
| 4 | Verificación en rojo y sin CI | `QA-01`, `QA-03`, `OPS-03` | Sin señal fiable no se puede corregir con seguridad |
| 5 | La base no se inicializa bien con Docker | `OPS-01` | Bloquea cualquier entorno nuevo |
| 6 | Editar un torneo permite estados imposibles | `FUN-04` | Un `PATCH` cierra un torneo sin podio |
| 7 | Validación de jugador por estado actual | `FUN-02` | Impide completar actas tras un traspaso |
| 8 | Anular eventos tras el cierre no recalcula | `FUN-03` | Llaves incoherentes con el marcador |
| 9 | Catálogos globales sin control de acceso | `SEC-04`, `FUN-14` | Un administrador afecta torneos ajenos; renombrar "Gol" borra marcadores |
| 10 | Sin despliegue, TLS ni copias automáticas | `OPS-02`, `OPS-05`, `SEC-18` | No hay forma segura de ponerlo en producción |

## 4. Mejoras prioritarias

| Prioridad | Significado | Tareas | Horas |
|---|---|---:|---:|
| **P0** | Antes de producción o para evitar un riesgo grave | 9 | 39 |
| **P1** | Corto plazo | 20 | 113,5 |
| **P2** | Calidad y experiencia | 25 | 162 |
| **P3** | Optimización futura | 2 | 7 |
| **Total** | | **56** | **321,5** |

**P0 (9 tareas):** `TASK-001` fijar Node y reparar la suite · `TASK-004` límite de login · `TASK-005` secretos al arrancar · `TASK-006` inicialización del compose · `TASK-007` reabrir torneo · `TASK-010` `PATCH` de torneo · `TASK-011` paginación de listados · `TASK-043` línea base del backend · `TASK-051` copias de seguridad.

## 5. Roadmap por fases

### Fase 0 — Recuperar la señal (12,5 h)

Objetivo: que "verde" vuelva a significar algo. Sin esto, cada corrección posterior se hace a ciegas.

| Tarea | Nombre | Prioridad | Horas |
|---|---|---|---:|
| TASK-001 | Fijar la versión de Node y reparar la suite de Vitest | P0 | 2 |
| TASK-002 | Corregir la prueba desactualizada y silenciar el ruido de MSW | P1 | 0,5 |
| TASK-043 | Ejecutar la suite de backend y registrar la línea base | P0 | 4 |
| TASK-003 | Integración continua mínima | P1 | 6 |

**Resultado:** las dos suites en verde en un entorno fijo, ejecutadas en cada cambio.

### Fase 1 — Estabilización (84 h)

Objetivo: corregir los defectos funcionales altos y medios y cerrar los accesos indebidos.

| Tarea | Nombre | Prioridad | Horas |
|---|---|---|---:|
| TASK-004 | Límite de login no eludible | P0 | 4 |
| TASK-005 | Rechazar secretos de ejemplo al arrancar | P0 | 4 |
| TASK-006 | Inicialización correcta de la base en Docker | P0 | 4 |
| TASK-007 | Reabrir un torneo restaura sus plantillas | P0 | 6 |
| TASK-010 | Cerrar el `PATCH` de torneo | P0 | 4 |
| TASK-011 | Paginación explícita en los listados que cortan en 100 | P0 | 5 |
| TASK-008 | Validar la pertenencia del jugador por fecha | P1 | 6 |
| TASK-009 | Proteger las consecuencias de anular eventos en un partido finalizado | P1 | 8 |
| TASK-012 | Control de Mesa y "Mis partidos" filtran por estado en el servidor | P1 | 4 |
| TASK-013 | Autorización de catálogos globales | P1 | 6 |
| TASK-014 | Datos personales y sub-recursos de torneos no publicados | P1 | 3 |
| TASK-015 | Manejo de errores y registro | P1 | 6 |
| TASK-016 | Guardas en inscripciones y en la baja de equipos | P1 | 6 |
| TASK-017 | Alta en plantilla unificada | P1 | 5 |
| TASK-018 | Rehacer sorteo sin pérdida de datos | P1 | 2 |
| TASK-019 | Proteger los tipos de evento de sistema | P1 | 4 |
| TASK-020 | `PATCH` con nulo explícito | P1 | 5 |
| TASK-021 | Edición de partido restringida para el árbitro | P2 | 2 |

**Resultado:** los seis defectos altos cerrados, cada uno con su prueba de regresión.

### Fase 2 — Calidad técnica (80 h)

Objetivo: atomicidad, rendimiento, integridad y mantenibilidad.

| Tarea | Nombre | Prioridad | Horas |
|---|---|---|---:|
| TASK-022 | Transacciones atómicas por caso de uso | P1 | 10 |
| TASK-023 | Eliminar consultas N+1 | P2 | 5 |
| TASK-024 | Cerrar carreras: titulares, inicio de partido, sorteo | P2 | 6 |
| TASK-025 | Tabla de posiciones completa | P2 | 6 |
| TASK-026 | Restricciones de base pendientes | P2 | 5 |
| TASK-027 | Bloqueo completo de torneo cerrado | P2 | 3 |
| TASK-028 | Zona horaria coherente | P2 | 10 |
| TASK-029 | Validación de entrada | P2 | 5 |
| TASK-030 | Caché del feed acotada | P2 | 4 |
| TASK-031 | Migraciones con registro de versión | P2 | 10 |
| TASK-032 | Cliente tipado sin `as never` | P2 | 8 |
| TASK-033 | Cambio de contraseña propio e invalidación de sesiones | P2 | 8 |

### Fase 3 — Experiencia de usuario (67 h)

Objetivo: coherencia visual, accesibilidad de base y navegación.

| Tarea | Nombre | Prioridad | Horas |
|---|---|---|---:|
| TASK-042 | Revisión visual real en cuatro tamaños de pantalla | P1 | 8 |
| TASK-038 | Confirmación en acciones destructivas | P1 | 4 |
| TASK-034 | `DESIGN.md` y componentes base | P2 | 16 |
| TASK-035 | Modal accesible único | P2 | 6 |
| TASK-036 | Navegación responsive, "sin permiso" y 404 | P2 | 8 |
| TASK-037 | Accesibilidad de base | P2 | 8 |
| TASK-039 | Paginación y búsqueda en listados | P2 | 10 |
| TASK-040 | Arreglos puntuales: enlace al portal, fechas, formato regional | P2 | 3 |
| TASK-041 | Límite de errores y división de código | P2 | 4 |

`TASK-042` va primero dentro de la fase: sus resultados pueden añadir o reordenar tareas.

### Fase 4 — Pruebas y confiabilidad (36 h)

| Tarea | Nombre | Prioridad | Horas |
|---|---|---|---:|
| TASK-048 | Matriz de autorización por rol y ruta | P1 | 8 |
| TASK-044 | Pruebas automáticas de accesibilidad | P2 | 4 |
| TASK-045 | Pruebas de concurrencia pendientes | P2 | 4 |
| TASK-046 | Extremo a extremo de cinco flujos | P2 | 16 |
| TASK-047 | Cobertura medida y umbrales | P3 | 4 |

Las pruebas de regresión de cada defecto no están aquí: forman parte de la tarea que lo corrige (regla de la sección 10).

### Fase 5 — Producción (42 h)

| Tarea | Nombre | Prioridad | Horas |
|---|---|---|---:|
| TASK-051 | Copias automáticas y restauración ensayada | P0 | 6 |
| TASK-049 | Imagen del frontend, proxy inverso con TLS y cabeceras | P1 | 10 |
| TASK-050 | Configuración por entorno y secretos | P1 | 4 |
| TASK-052 | Observabilidad | P1 | 8 |
| TASK-053 | Mantenimiento programado y servidor de producción | P2 | 4 |
| TASK-054 | Manual de despliegue y vuelta atrás | P2 | 4 |
| TASK-056 | Dependencias: actualización y análisis automático | P2 | 3 |
| TASK-055 | Actualizar la documentación desactualizada | P3 | 3 |

## 6. Dependencias

```
TASK-001 ─┬─► TASK-002 ─┐
          │             ├─► TASK-003 (CI) ──► TASK-046, TASK-047, TASK-056
TASK-043 ─┴─────────────┘
    │
    └─► toda la Fase 1 (cada corrección empieza con su prueba)

TASK-006 ──► TASK-046 (necesita un entorno que arranque) ──► TASK-049

TASK-011 ──► TASK-012 ──► TASK-039
TASK-015 ──► TASK-052
TASK-008 ──► TASK-007   (si se valida por fecha, reabrir es más simple; ver nota)
TASK-022 ──► TASK-024
TASK-013 ──► TASK-048
TASK-019 ──► TASK-026
TASK-005 ──► TASK-050 ──► TASK-049 ──► TASK-054
TASK-030, TASK-053 ──► varios procesos de API (dentro de TASK-053)
TASK-031 ──► TASK-026, TASK-027, TASK-028 (las migraciones nuevas ya usan el ejecutor)
TASK-042 ──► TASK-034 ──► TASK-035, TASK-036, TASK-037, TASK-038, TASK-039
TASK-035, TASK-037 ──► TASK-044
TASK-033 ──► TASK-036 (menú de usuario)
```

**Nota sobre `TASK-007` y `TASK-008`.** Las dos tocan la misma regla. Hacer primero `TASK-008` (validar por fecha y no por estado) reduce `TASK-007` a decidir qué pasa con las membresías al reabrir. Por prioridad `TASK-007` es P0 y `TASK-008` P1, pero conviene planificarlas juntas, en ese orden.

**Nota sobre `TASK-031`.** Está en la Fase 2, pero las tareas de la Fase 1 que cambian el esquema (`TASK-007`, `TASK-008`, `TASK-019`) siguen el procedimiento manual actual de `database/README.md`, que es válido. No hay que esperar al ejecutor de migraciones para corregir defectos.

### Orden recomendado

1. Fase 0 completa.
2. Fase 1, P0 primero: `004`, `005`, `006`, `010`, `011`, `008`+`007`.
3. Fase 1, P1: `012`, `009`, `013`, `014`, `015`, `016`, `017`, `018`, `019`, `020`.
4. Fase 5 mínima: `051`, `050`, `049`, `052`. **Aquí el sistema es desplegable.**
5. Fase 4: `048`.
6. Fase 2.
7. Fase 3, empezando por `042`.
8. Resto de Fases 4 y 5.

## 7. Estimación de esfuerzo

| Fase | Tareas | Horas | Semanas (una persona, 30 h efectivas) |
|---|---:|---:|---:|
| 0 — Recuperar la señal | 4 | 12,5 | 0,5 |
| 1 — Estabilización | 18 | 84 | 3 |
| 2 — Calidad técnica | 12 | 80 | 2,5 |
| 3 — Experiencia de usuario | 9 | 67 | 2,5 |
| 4 — Pruebas y confiabilidad | 5 | 36 | 1 |
| 5 — Producción | 8 | 42 | 1,5 |
| **Total** | **56** | **321,5** | **≈ 11** |

**Camino mínimo a producción** (pasos 1 a 4 del orden recomendado): 12,5 + 84 + 28 = **124,5 horas de tarea**; con un margen del 20 % para lo que aparezca al ejecutar por primera vez la suite de backend y el compose, **unas 150 horas, cinco semanas**.

**Supuestos de la estimación:**

- Una persona que conoce el código, con ayuda de un agente de programación.
- Las horas incluyen la prueba de regresión y la actualización de `01`–`06` cuando hay cambio de esquema.
- No incluyen el tiempo de revisión del propietario ni el de decisión en los puntos de la sección 9.
- La suite de backend está verde hoy. Si no lo está, `TASK-043` crece.
- Son estimaciones sin haber ejecutado el backend; la incertidumbre es de ±30 %.

## 8. Criterios de aceptación por fase

| Fase | Se considera cerrada cuando |
|---|---|
| 0 | `npm run verify` y `pytest` (con y sin `-m concurrencia`) terminan en verde en CI sobre la rama principal; la versión de Node está fijada |
| 1 | Las pruebas PR-001 a PR-041 marcadas P0 y P1 en `07_AUDITORIA_QA.md` existen y pasan; ningún hallazgo `FUN` alto sigue abierto; `docker compose up` desde un volumen vacío deja la API con el catálogo de 28 disciplinas |
| 2 | Crear un torneo, registrar un hito y cambiar un rol son atómicos (prueba con fallo inyectado); `GET /partidos?limit=200` ejecuta un número fijo de consultas; las migraciones dejan registro; no quedan `as never` fuera de un módulo de adaptación |
| 3 | Sin infracciones graves en el análisis automático de accesibilidad de las diez pantallas principales; todos los modales usan el componente único; la navegación no desborda a 360 px; existe `DESIGN.md` |
| 4 | Matriz de permisos automatizada para todas las rutas de escritura; cinco recorridos de extremo a extremo en CI; cobertura medida y publicada |
| 5 | Despliegue reproducible con un comando; HTTPS con cabeceras de seguridad; copia diaria y una restauración ensayada y cronometrada; alertas ante caída de la API o de la base; manual de despliegue y vuelta atrás |

## 9. Riesgos

| Riesgo | Probabilidad | Efecto | Mitigación |
|---|---|---|---|
| La suite de backend no está verde | Media | Retrasa la Fase 1 | `TASK-043` va primero y acota el alcance |
| Algún defecto alto no se reproduce | Baja | Tarea innecesaria | Cada tarea empieza con la prueba; si pasa sin cambios, se cierra y se corrige este informe |
| La base real difiere de `01`–`06` | Media | Migraciones que fallan en producción | Comparar esquemas antes de la primera migración; copia previa obligatoria |
| Corregir `FUN-02` cambia qué eventos se aceptan | Media | Eventos antes rechazados pasan a ser válidos | Pruebas en ambos sentidos (PR-003 a PR-005) |
| Restringir catálogos rompe el trabajo de algún TorneoAdmin | Media | Usuarios bloqueados | Decidir el modelo con el propietario antes de `TASK-013` |
| Cambiar a fechas con zona afecta a datos existentes | Alta | Horas desplazadas | Migración con zona explícita, ensayo sobre una copia; es la tarea de mayor riesgo técnico |
| La revisión visual descubre más trabajo del estimado | Alta | La Fase 3 crece | Está prevista como primera tarea de la fase |
| Se introducen regresiones al tocar triggers | Media | Reglas debilitadas | Las pruebas de triggers existentes y la regla de "prueba primero" |

### Decisiones que corresponden al propietario

Estas tareas necesitan una decisión de producto antes de empezar:

1. **`TASK-013`:** ¿los catálogos de equipos y jugadores son compartidos entre organizadores o cada uno ve los suyos? Determina el alcance de la restricción.
2. **`TASK-007`:** al reabrir, ¿se restauran todas las membresías que cerró el cierre, o se deja de cerrarlas al finalizar el torneo?
3. **`TASK-009`:** ¿se prohíbe anular un evento que cambia el resultado de un partido cuya llave ya avanzó, o se permite con recálculo?
4. **`TASK-003`:** reabrir la decisión de no tener CI, con la evidencia de `QA-01` y `QA-02`.
5. **Modalidad individual (`FUN-16`):** completarla o retirarla de la interfaz.
6. **Retención de bitácoras (`DB-13`):** plazo y tratamiento de datos personales.

## 10. Definición de terminado

Una tarea está terminada cuando se cumple **todo** lo siguiente:

1. **Prueba primero.** Existe una prueba automatizada que fallaba antes del cambio y pasa después. En defectos, la prueba reproduce el hallazgo citado.
2. **Criterios de aceptación** de la tarea, marcados uno por uno.
3. **Verificación completa en verde:** pruebas de backend (incluidas las de concurrencia si la tarea toca bloqueos), lint, tipos, pruebas del frontend y build.
4. **Esquema en sus tres lugares** si hay cambio de base: `01`–`06`, migración idempotente numerada y lista `SCRIPTS_VIGENTES`, como exige `database/README.md`.
5. **Contrato regenerado** (`npm run gen:api`) si cambió un esquema de la API, sin introducir `as never`.
6. **Sin degradar lo existente:** ninguna prueba se elimina ni se marca como omitida para pasar.
7. **Documentación al día:** el README afectado y, si la tarea revierte una decisión de un plan, una nota en ese plan.
8. **Auditoría:** si la tarea escribe en la base por un camino nuevo, el cambio queda en `AUDITORIA`.
9. **Revisión:** el propietario ha visto el cambio y, si tiene interfaz, lo ha probado en el navegador.
10. **Hallazgo cerrado:** el ID del hallazgo se cita en el mensaje del commit.
