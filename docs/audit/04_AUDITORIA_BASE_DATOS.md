# 04 — Auditoría de base de datos

Fase IV: PostgreSQL, por sí sola y en relación con el backend.

> **Nivel de evidencia.** No había un servidor PostgreSQL disponible, así que no se ejecutó ninguna consulta: ni `EXPLAIN`, ni pruebas de concurrencia, ni comparación entre el esquema de `database/` y una base real. Todo sale de leer `database/01_schema.sql` a `06_triggers.sql`, las migraciones y los modelos del ORM. **No se pudo verificar que la base `torneos_mvp` en uso coincida con `01`–`06`** (ver `DB-10`).

## 1. Modelo de datos

25 tablas, 10 vistas, 20 funciones (17 de ellas de trigger), 32 triggers y 53 índices explícitos (conteos sobre `01`–`06`).

```
DISCIPLINA 1─N MODALIDAD
DISCIPLINA 1─N TORNEO N─1 MODALIDAD
TORNEO_GRUPO 1─N TORNEO 1─1 CONFIGURACION_TIEMPO_TORNEO
TORNEO 1─N FASE 1─N GRUPO 1─N GRUPO_EQUIPO N─1 INSCRIPCIONES_TORNEO
TORNEO 1─N INSCRIPCIONES_TORNEO N─1 EQUIPOS            (o N─1 JUGADOR_PERFIL_DISCIPLINA, individual)
JUGADORES 1─N JUGADOR_PERFIL_DISCIPLINA N─1 DISCIPLINA
JUGADOR_PERFIL_DISCIPLINA 1─N JUGADOR_EQUIPO N─1 INSCRIPCIONES_TORNEO
JUGADOR_PERFIL_DISCIPLINA 1─N TRASPASOS (origen/destino → INSCRIPCIONES_TORNEO)
EQUIPOS 1─N EQUIPO_JUGADOR_BASE N─1 JUGADOR_PERFIL_DISCIPLINA
TORNEO 1─N PARTIDOS (local/visitante → EQUIPOS; fase, grupo; siguiente, perdedor_siguiente, ida → PARTIDOS)
PARTIDOS 1─N HITOS_PARTIDO · 1─N EVENTOS_PARTIDO (→ JUGADORES, EQUIPOS, EVENTOS) · 1─N CONVOCADO_A_PARTIDO
FASE 1─N SORTEOS
USUARIOS 1─N ASIGNACION_TORNEO_ADMIN N─1 TORNEO · 1─N ACCESOS · 1─N AUDITORIA
```

### Decisiones de modelado acertadas

- **Perfil por disciplina** (`JUGADOR_PERFIL_DISCIPLINA`): una persona, un perfil por deporte. La suspensión y las estadísticas quedan aisladas por disciplina.
- **Plantilla con vigencia**: `JUGADOR_EQUIPO` cuelga de la inscripción (equipo en un torneo), con fechas de inicio y fin. Permite historia y traspasos sin perder trazabilidad.
- **Torneo como edición de un grupo**: `TORNEO_GRUPO` + `Numero_Edicion`, con unicidad por grupo.
- **Marcador derivado, no almacenado**: se calcula desde `EVENTOS_PARTIDO`. Elimina la clase de errores "el marcador no coincide con los goles".
- **Llave como grafo en la propia tabla**: `Partido_Siguiente_ID`, `Slot_Siguiente`, `Partido_Perdedor_Siguiente_ID`, `Partido_Ida_ID`.
- **Hitos como fuente de verdad del tiempo y del estado** del partido.
- **Inscripción con dos formas** y `CHECK` de "exactamente uno" entre equipo y jugador.

### Normalización

Tercera forma normal en general. Redundancias detectadas:

- `PARTIDOS.Fase` y `PARTIDOS.Grupo` (texto, del modelo original) conviven con `Fase_ID` y `Grupo_ID`. Las vistas exponen ambos (`DB-07`).
- `TORNEO.Disciplina_ID` es derivable de `Modalidad_ID`; un trigger mantiene la coherencia. Lo mismo en `EQUIPOS`. Aceptable.
- `TRASPASOS.Dorsal_Nuevo` duplica el dorsal de la membresía creada. Aceptable como registro del acto.

## 2. Integridad

### Claves y restricciones

| Tipo | Cantidad | Observación |
|---|---:|---|
| Claves primarias | 25 | Todas `SERIAL` |
| Claves foráneas | 55 | 20 con `ON DELETE CASCADE`, 7 con `SET NULL`, el resto restrictivas |
| `UNIQUE` | 18 | Más dos índices únicos parciales (dorsal vigente por plantilla; un único fin por partido) |
| `CHECK` | 57 | Estados, rangos, coherencias (walkover, penales, hitos forzados, motivo de acceso) |

Las restricciones son abundantes y con nombre. Destacan el índice parcial `uq_dorsal_por_roster_vigente`, que libera el dorsal cuando la membresía termina, y el conjunto de `CHECK` sobre hitos forzados.

### Triggers

| Función | Qué garantiza |
|---|---|
| `fn_actualizar_fecha_modificacion` | Fecha de modificación en 14 tablas |
| `fn_validar_jugador_partido` | El equipo disputa el partido; el jugador pertenecía al equipo; `jugador_id_entra` solo en cambios |
| `fn_validar_equipos_inscritos` | Ambos equipos inscritos y no cancelados |
| `fn_validar_torneo_modalidad`, `fn_validar_equipo_modalidad` | La modalidad pertenece a la disciplina; penales no aplican a cronómetro corrido |
| `fn_validar_exclusividad_torneo` | Un perfil, un equipo activo por torneo |
| `fn_validar_tope_titulares` | Máximo de titulares por equipo |
| `fn_validar_equipo_un_grupo_por_fase` | Un equipo en un solo grupo por fase |
| `fn_validar_asignacion_torneo_admin_rol` | Solo se asignan torneos a cuentas TorneoAdmin |
| `fn_validar_hito_partido`, `fn_hito_sincroniza_estado_partido` | Coherencia de hitos y sincronía del estado del partido |
| `fn_validar_ganador_corrido` | Partido de cronómetro corrido no termina sin ganador |
| `fn_validar_partido_eliminacion_desempate`, `fn_validar_forma_desempate` | Eliminación no termina empatada sin desempate; tanda coherente |
| `fn_marcador_partido`, `fn_resolver_llave` | Fuente única del ganador de un partido o de una llave a dos partidos |
| `fn_propagar_ganador_bracket` | Avanza ganador y perdedor en la llave |
| `fn_cerrar_torneo_libera_jugadores` | Libera a los jugadores al cerrar el torneo |
| `fn_bloquear_escritura_torneo_cerrado` | Resultados inmutables en torneo cerrado |
| `fn_generar_disciplina_slug` | Slug estable para el portal |

`06_triggers.sql` termina con un bloque `DO` que valida el estado de la base tras la instalación (partidos con equipos no inscritos, eventos con equipo o jugador ajeno), lo que convierte una carga de datos incoherente en un error inmediato. Buena práctica.

### Coherencia entre backend y base

No se encontraron contradicciones entre lo que valida Python y lo que exige PostgreSQL: los servicios dan el mensaje legible y el trigger es la red de fondo. Las reglas que solo viven en Python (y que un `psql` directo no respeta) son: cupo de inscripciones, tope de plantilla, reglas de cambio, mínimo de titulares para iniciar y la doble amarilla. Están documentadas como decisiones.

Tres reglas de la base producen resultados funcionalmente incorrectos y se describen en el documento 02: `FUN-01` (el cierre da de baja las plantillas y la reapertura no las repone), `FUN-02` (validación por estado actual en lugar de por fechas) y `FUN-03` (el avance en la llave no se recalcula).

## 3. Hallazgos

### DB-01 — Columnas de estado que admiten `NULL`

- **Tipo:** Riesgo potencial. **Severidad:** Medio.
- **Ubicación:** `database/01_schema.sql`: `Estado VARCHAR(20) DEFAULT '…'` sin `NOT NULL` en `DISCIPLINA`, `MODALIDAD`, `TORNEO`, `EQUIPOS`, `JUGADORES`, `INSCRIPCIONES_TORNEO`, `JUGADOR_EQUIPO`, `TRASPASOS`, `EQUIPO_JUGADOR_BASE`, `PARTIDOS`, `EVENTOS`, `USUARIOS` y `EVENTOS_PARTIDO`. Las creadas después (`TORNEO_GRUPO`, `FASE`, `SORTEOS`, `ASIGNACION_TORNEO_ADMIN`) sí lo tienen.
- **Descripción:** un `CHECK (Estado IN (…))` da por válido un `NULL`. Una fila con estado nulo queda fuera de todo filtro `Estado = 'Activo'` y también de todo `Estado <> 'Cancelado'`. La vista del feed ya se protege con `IS DISTINCT FROM`, lo que indica que el caso se tuvo presente.
- **Impacto:** hoy la API siempre deja el valor por defecto; el riesgo aparece con cargas por SQL o con un `INSERT … (Estado) VALUES (NULL)`. En `USUARIOS`, un estado nulo impediría el acceso (`deps.py:42`), que falla del lado seguro.
- **Recomendación:** `SET NOT NULL` tras comprobar que no hay nulos. `TASK-026`.

### DB-02 — Faltan restricciones de coherencia simples

- **Tipo:** Confirmado (estático). **Severidad:** Medio.
- **Detalle (ausentes en `database/02_constraints.sql`):**
  - `TORNEO`: `Fecha_Fin >= Fecha_Inicio`; `Equipos_Por_Grupo > 0`; `Clasificados_Por_Grupo > 0`.
  - `JUGADOR_EQUIPO`: `Fecha_Fin IS NULL OR Fecha_Fin >= Fecha_Inicio`; `Dorsal > 0`.
  - `CONFIGURACION_TIEMPO_TORNEO`: cantidades y duraciones positivas.
  - `HITOS_PARTIDO`: `Minuto_Reloj >= 0`.
  - Nombres no vacíos en `EQUIPOS`, `JUGADORES`, `TORNEO`, `EVENTOS`.
- **Impacto:** valores que la API tampoco valida (`BE-07`, `FUN-04`, `FUN-20`) quedan guardados.
- **Recomendación:** `TASK-026`.

### DB-03 — `EVENTOS.Nombre` sin unicidad y usado como identificador

- **Tipo:** Confirmado (estático). **Severidad:** Medio.
- **Ubicación:** `database/02_constraints.sql` (bloque `ALTER TABLE EVENTOS`: solo el `CHECK` de estado); `database/04_views.sql:18-44`; `database/06_triggers.sql:243`.
- **Descripción e impacto:** ver `FUN-14`.
- **Recomendación:** columna `Codigo` estable y única para los tipos de sistema, o al menos `UNIQUE (Nombre)` más protección contra renombrado. `TASK-019`.

### DB-04 — Fechas sin zona horaria

- **Tipo:** Riesgo potencial. **Severidad:** Medio.
- **Ubicación:** todas las columnas de fecha y hora de `database/01_schema.sql` son `TIMESTAMP`; `vw_proximos_partidos` compara con `CURRENT_TIMESTAMP` (`04_views.sql:46-92`); el feed usa `CURRENT_DATE` del servidor (`backend/app/repositories/feed.py:23`).
- **Impacto:** "hoy" y "próximos" dependen de la zona de la sesión de PostgreSQL. Con el servidor en UTC y usuarios en UTC−5, entre las 19:00 y las 24:00 el feed por defecto salta al día siguiente.
- **Recomendación:** `TASK-028`.

### DB-05 — Validaciones por conteo que no resisten concurrencia

- **Tipo:** Riesgo potencial. **Severidad:** Medio.
- **Ubicación:** `06_triggers.sql:141-153` (titulares), `:1068-1078` (hito duplicado), `:489-500` (exclusividad), `:555-564` (un grupo por fase).
- **Descripción:** en `READ COMMITTED`, dos transacciones simultáneas cuentan sin verse. La exclusividad está mitigada en la aplicación con un bloqueo consultivo (`repositories/jugador_equipo.py:30-33`), pero no ante SQL directo. El fin de partido sí está protegido con un índice único parcial.
- **Recomendación:** donde la regla sea "a lo sumo uno", expresarla como índice único parcial (inicio de partido; membresía activa por perfil y torneo requiere desnormalizar el torneo o una restricción de exclusión); para el tope de titulares, bloquear la fila del partido. `TASK-024`.

### DB-06 — El bloqueo de torneo cerrado tiene huecos

- **Tipo:** Confirmado (estático). **Severidad:** Medio.
- **Ubicación:** `database/06_triggers.sql:1180-1190`.
- **Descripción:** en `PARTIDOS` el trigger es solo `BEFORE UPDATE`: se pueden insertar partidos en un torneo finalizado. `CONVOCADO_A_PARTIDO`, `INSCRIPCIONES_TORNEO` y `JUGADOR_EQUIPO` no están cubiertas. Tampoco hay protección para torneos `Inactivo` (baja lógica).
- **Recomendación:** ampliar a `INSERT` y `DELETE` en partidos y decidir explícitamente qué queda editable en torneo cerrado. `TASK-027`.

### DB-10 — Migraciones sin registro de aplicación

- **Tipo:** Mejora (con riesgo operativo). **Severidad:** Medio.
- **Ubicación:** `database/README.md`.
- **Descripción:** el procedimiento manual es bueno (copia de seguridad previa, ensayo en una base descartable, transacción única con `psql -1`, actualizar `01`–`06` en el mismo cambio) y `backend/tests/test_scripts_sql.py` ejecuta dos veces los scripts vigentes. Pero nada registra qué se aplicó en cada base. El propio README cuenta que el índice de migraciones estuvo desactualizado entre la 21 y la 30 y que una quedó "pendiente de aplicar".
- **Impacto:** la base real puede diferir del esquema con el que corren las pruebas sin que nadie lo note. Esta auditoría no pudo comprobarlo.
- **Recomendación:** tabla `schema_migrations`, un ejecutor que aplique lo pendiente en orden, y una comprobación de arranque que avise si falta alguna. `TASK-031`.

### Hallazgos menores

| ID | Tipo | Severidad | Hallazgo | Evidencia | Tarea |
|---|---|---|---|---|---|
| DB-07 | Mejora | Bajo | Columnas de texto heredadas `PARTIDOS.Fase` y `PARTIDOS.Grupo` junto a las claves `Fase_ID` y `Grupo_ID`; los partidos del motor de formatos dejan `Fase = 'Regular'` por defecto aunque sean de eliminación | `01_schema.sql` (tabla `PARTIDOS`), `services/motor_formatos.py:317-325` | Retirar tras migrar consumidores |
| DB-08 | Mejora | Bajo | Índices redundantes (`idx_config_tiempo_torneo` duplica el de la restricción única; `idx_jugador_equipo_inscripcion` es prefijo de `idx_jugador_equipo_vigencia`) y uno ausente: `PARTIDOS(Partido_Ida_ID)`, consultado por partido en el listado y dentro de un trigger | `03_indexes.sql`; `services/partido.py:399`; `06_triggers.sql:909` | `TASK-023` |
| DB-09 | Riesgo potencial | Bajo | 20 claves con `ON DELETE CASCADE`: un `DELETE` manual de un torneo o un equipo arrastra inscripciones, partidos, eventos e hitos. La API no borra, pero la auditoría de cambios no ve el SQL directo | `02_constraints.sql`; decisión documentada en `backend/README.md` | Usuario de aplicación sin permiso `DELETE` salvo en las dos tablas que lo necesitan (`TASK-050`) |
| DB-11 | Riesgo potencial | Bajo | Vistas anidadas que agregan sobre todos los partidos (`vw_feed_partidos` → `vw_resultados_partidos` → `vw_goles_acreditados`); la tabla de posiciones recalcula todo en cada lectura. Sin medir | `04_views.sql:176-350` | Medir con `EXPLAIN ANALYZE` cuando haya volumen; vista materializada si hace falta |
| DB-12 | Informativo | — | La búsqueda de jugadores usa `ILIKE '%…%'` sobre nombre y cédula sin índice de trigramas; recorre la tabla | `repositories/jugador.py:28-29` | Índice `pg_trgm` al superar unos miles de jugadores |
| DB-13 | Informativo | — | `AUDITORIA` y `ACCESOS` se purgan a los 30 días por defecto y guardan datos personales en JSON sin redactar (cédula, correo) | `core/config.py:28,34`, `core/auditoria.py:58` | Decidir la retención con criterio legal (`TASK-050`) |

## 4. Transacciones y concurrencia

| Mecanismo | Dónde | Valoración |
|---|---|---|
| Bloqueo de fila con tiempo máximo | Eventos en vivo, anulación de tarjetas, resultado directo | Correcto y probado con conexiones reales |
| Bloqueo dentro de función SQL | `fn_resolver_llave` bloquea la ida antes de leerla | Correcto |
| Bloqueos consultivos | Cupo de inscripciones, numeración de ediciones, exclusividad, cupo de plantilla | Correctos; claves de un solo entero colisionan entre sí (`BE-09`) |
| Control optimista | Convocatoria: versión = máxima fecha de modificación, 412 con el estado actual | Correcto |
| Índices únicos parciales | Dorsal vigente; un fin por partido | Correcto |
| Puntos de guardado | Copia de plantilla base | Correcto |
| Sin protección | Tope de titulares, inicio de partido duplicado, sorteo concurrente, `commit` por paso | `BE-02`, `BE-03`, `DB-05` |

## 5. Consistencia entre ORM y esquema

Se cotejaron los modelos de `backend/app/models/` con `01_schema.sql` por muestreo de las tablas principales (`TORNEO`, `PARTIDOS`, `JUGADOR_EQUIPO`, `HITOS_PARTIDO`, `USUARIOS`, `CONVOCADO_A_PARTIDO`): nombres y tipos coinciden. Como el arnés de pruebas reconstruye la base desde `01`–`06` y ejercita casi todos los modelos, una discrepancia se manifestaría como fallo de la suite; esa comprobación queda pendiente de ejecutar (`QA-03`). **No verificable** en esta auditoría: que la base en uso coincida con esos archivos.

## 6. Posibles datos huérfanos, duplicados e inconsistencias

| Riesgo | ¿Puede ocurrir? | Por qué |
|---|---|---|
| Filas huérfanas | No | Todas las relaciones tienen clave foránea |
| Jugador duplicado | No por cédula (`UNIQUE`). Sí por variaciones de formato de la cédula (espacios, guiones): no hay normalización | `schemas/jugador.py`, `repositories/jugador.py:15` |
| Equipo duplicado | Sí: no hay unicidad por nombre y disciplina (descartado a propósito en `TODOS.md`) | Decisión documentada |
| Tipo de evento duplicado | Sí | `DB-03` |
| Torneo sin fase o sin configuración de tiempo | Sí, si falla un paso de la creación | `FUN-18` |
| Plantilla incoherente tras cancelar una inscripción | Sí | `FUN-07` |
| Llave incoherente con el marcador | Sí | `FUN-03` |
| Membresías inactivas en un torneo activo tras reabrir | Sí | `FUN-01` |
| Partido en torneo cerrado | Sí, por inserción | `DB-06` |

## 7. Resumen

| ID | Severidad | Tipo | Resumen |
|---|---|---|---|
| DB-01 | Medio | Riesgo potencial | Estados que admiten `NULL` |
| DB-02 | Medio | Confirmado (estático) | Faltan `CHECK` de fechas y rangos |
| DB-03 | Medio | Confirmado (estático) | Tipos de evento identificados por nombre no único |
| DB-04 | Medio | Riesgo potencial | Fechas sin zona horaria |
| DB-05 | Medio | Riesgo potencial | Validaciones por conteo sin bloqueo |
| DB-06 | Medio | Confirmado (estático) | Bloqueo de torneo cerrado incompleto |
| DB-07 | Bajo | Mejora | Columnas heredadas redundantes |
| DB-08 | Bajo | Mejora | Índices redundantes y uno ausente |
| DB-09 | Bajo | Riesgo potencial | Cascadas ante borrado manual |
| DB-10 | Medio | Mejora | Migraciones sin registro |
| DB-11 | Bajo | Riesgo potencial | Vistas anidadas sin medir |
| DB-12 | Informativo | — | Búsqueda sin índice de trigramas |
| DB-13 | Informativo | — | Retención y datos personales en bitácoras |

La base es la parte más sólida del proyecto en cuanto a intención: las reglas están donde no se pueden esquivar. Los defectos encontrados no son de falta de restricciones, sino de tres reglas cuyo efecto combinado no se previó (`FUN-01`, `FUN-02`, `FUN-03`) y de endurecimiento pendiente.
