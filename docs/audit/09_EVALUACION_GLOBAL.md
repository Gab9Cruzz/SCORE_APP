# 09 — Evaluación global

Fase IX: puntuación ponderada del proyecto a partir de los documentos 01 a 08.

## 1. Resultado

**65 / 100 — "Necesita mejoras"** (rango 60–69). Confianza de la evaluación: **media**.

| Dimensión | Peso | Puntos | Aporte | Confianza |
|---|---:|---:|---:|---|
| Funcionalidad | 20 % | 68 | 13,60 | Media |
| Arquitectura y mantenibilidad | 15 % | 72 | 10,80 | Alta |
| Backend y APIs | 10 % | 70 | 7,00 | Media |
| Base de datos | 10 % | 72 | 7,20 | Media |
| Frontend y calidad técnica | 10 % | 66 | 6,60 | Alta |
| UX/UI y accesibilidad | 15 % | 60 | 9,00 | **Baja** |
| Seguridad | 10 % | 55 | 5,50 | Media |
| QA y testing | 5 % | 62 | 3,10 | Media |
| Infraestructura y DevOps | 5 % | 35 | 1,75 | Media |
| **Total** | **100 %** | | **64,55 ≈ 65** | **Media** |

## 2. Cómo leer la cifra

- **No es un proyecto en mal estado.** La nota la bajan sobre todo dos cosas que no tienen que ver con la calidad del código de negocio: la operación (todavía no se ha preparado un despliegue) y la seguridad de configuración. El núcleo —modelo de datos, reglas, flujo de mesa— está por encima de 70.
- **La cifra tiene un margen de unos ±5 puntos.** Tres dimensiones se puntuaron sin poder ejecutar lo necesario (ver sección 4). Si la suite de backend resulta verde y la revisión visual no encuentra problemas graves, el total real estaría más cerca de 68. Si alguna de las dos trae sorpresas, más cerca de 60.
- **Distancia a "Bueno" (70):** se alcanza cerrando la Fase 1 del roadmap. **A "Muy bueno" (80):** con las Fases 1, 2 y 5.

## 3. Justificación por dimensión

### Funcionalidad — 68

**A favor.** Alcance amplio y coherente: tres formatos de competición con llaves a ida y vuelta, desempates, convocatorias, cronómetro por periodos o corrido, traspasos reversibles, registro por lote, portal público, RBAC por torneo con licencias. Los caminos principales están bien resueltos y tienen pruebas.

**En contra.** Seis defectos de severidad alta, todos confirmados por lectura de código: reabrir un torneo lo deja inoperable para cargar eventos (`FUN-01`), la validación de jugadores depende de su estado actual (`FUN-02`), anular eventos tras el cierre no recalcula la llave (`FUN-03`), editar un torneo permite estados imposibles (`FUN-04`), listados que se cortan en 100 sin avisar (`FUN-05`) y la pantalla de mesa que deja de mostrar partidos pendientes en torneos medianos (`FUN-06`). Ocho más de severidad media. Sin cambio de contraseña propio. Modalidad individual incompleta.

**Por qué no más bajo.** Ninguno afecta al camino feliz de un torneo pequeño; aparecen al crecer o al corregir.

### Arquitectura y mantenibilidad — 72

**A favor.** Capas limpias y respetadas, decisiones documentadas en 21 planes, contrato generado, reglas extraídas a módulos puros, auditoría transversal bien diseñada.

**En contra.** Esquema mantenido a mano en dos representaciones sin registro de versiones (`ARQ-01`), `commit` por operación en el repositorio base (`ARQ-02`), reglas enlazadas por cadenas de texto entre capas (`ARQ-03`), siete archivos de más de 600 líneas (`ARQ-04`), documentación de entrada desactualizada (`ARQ-05`).

### Backend y APIs — 70

**A favor.** API coherente, códigos de estado bien diferenciados, dependencias de permiso componibles, concurrencia cuidada en el camino en vivo, tipado completo.

**En contra.** Consultas N+1 (`BE-01`), transacciones partidas (`BE-02`), carreras conocidas (`BE-03`), errores de infraestructura devueltos como 400 y sin registro (`BE-04`), paginación inconsistente (`BE-06`), caché sin techo (`BE-08`), sin linter ni comprobación de tipos para Python.

### Base de datos — 72

**A favor.** 55 claves foráneas, 57 `CHECK`, 18 restricciones de unicidad más índices únicos parciales, 20 funciones que defienden las reglas donde no se pueden esquivar, verificación del propio esquema al instalar, pruebas dedicadas a triggers.

**En contra.** Tres reglas con efecto combinado incorrecto (`FUN-01`, `FUN-02`, `FUN-03`), estados que admiten nulo (`DB-01`), faltan comprobaciones de fechas (`DB-02`), tipos de evento identificados por un nombre no único (`DB-03`), fechas sin zona (`DB-04`), validaciones por conteo no seguras ante concurrencia (`DB-05`), migraciones sin registro (`DB-10`). Nada se ejecutó.

### Frontend y calidad técnica — 66

**A favor.** Cliente tipado generado, estado de servidor bien gestionado, lógica pura separada, cero `any`, 344 pruebas, lint y tipos limpios (ejecutado).

**En contra.** La suite falla entera con el Node instalado (`QA-01`), 90 conversiones que evitan el contrato tipado (`FE-02`), sin límite de errores, sin 404, sin división de código (`FE-03`), componentes de hasta 1.088 líneas (`FE-04`), una hoja de estilos global sin sistema (`FE-08`).

### UX/UI y accesibilidad — 60 (confianza baja)

**A favor (por lectura de código).** Flujo de mesa pensado para móvil, el servidor decide qué acciones están disponibles, mensajes de error que indican cómo seguir, estados vacíos con texto, color nunca como único canal, buen contraste de texto (calculado).

**En contra.** Idioma del documento mal declarado, sin títulos de página, ocho de nueve modales sin gestión de foco, bordes de campos sin contraste suficiente, acciones destructivas sin confirmación, listados sin paginación, navegación que puede desbordar en móvil, un enlace principal que no funciona, sin sistema de diseño.

**Por qué la confianza es baja.** No se vio ninguna pantalla. La nota puede moverse 10 puntos en cualquier sentido tras la revisión visual.

### Seguridad — 55

**A favor.** bcrypt, estado del usuario releído en cada petición, autorización centralizada, sin inyección ni XSS detectables, datos personales ocultos a anónimos, auditoría y bitácora de accesos, contenedor sin privilegios, ningún secreto en el repositorio.

**En contra.** Límite de login eludible (`SEC-01`), credenciales por defecto (`SEC-02`), catálogos globales sin acotar (`SEC-04`), búsqueda pública por cédula (`SEC-05`), errores que exponen detalles y ocultan incidentes (`SEC-06`), sin TLS ni cabeceras (`SEC-18`), token en `localStorage` sin revocación (`SEC-03`).

**Por qué no más bajo.** Los cimientos son correctos; lo pendiente es endurecimiento y configuración, no rediseño.

### QA y testing — 62

**A favor.** 505 pruebas de backend contra una base real con aislamiento por transacción, pruebas de triggers y de scripts SQL, infraestructura de concurrencia con conexiones reales, 344 pruebas de frontend.

**En contra.** La señal está rota: el frontend da rojo completo en esta máquina y el backend no se pudo ejecutar. Sin cobertura, sin extremo a extremo, sin integración continua, doce escenarios críticos sin prueba.

### Infraestructura y DevOps — 35

**A favor.** Dockerfile con usuario sin privilegios, compose con comprobación de salud de la base, procedimiento de migración prudente.

**En contra.** La inicialización del compose previsiblemente falla (`OPS-01`), no hay despliegue del frontend ni TLS (`OPS-02`), no hay integración continua (`OPS-03`), no hay entornos (`OPS-04`), las copias son manuales (`OPS-05`), la observabilidad es mínima (`OPS-06`).

## 4. Qué no se pudo verificar y cómo afecta

| Aspecto | Efecto en la puntuación | Qué lo resolvería |
|---|---|---|
| Suite de backend sin ejecutar | Funcionalidad, Backend, Base de datos y QA se puntuaron suponiendo que pasa, como afirma `TODOS.md` | `TASK-043` |
| Ninguna pantalla vista | UX/UI con confianza baja | `TASK-042` |
| `docker compose` sin ejecutar | `OPS-01` es una deducción, sólida pero no observada | `TASK-006` |
| Base real no inspeccionada | No se sabe si `torneos_mvp` coincide con `01`–`06` | `TASK-031` |
| Los seis defectos altos no reproducidos | Podría existir una protección no vista que invalide alguno | Cada tarea empieza escribiendo la prueba que lo reproduce |
| Dependencias de Python sin analizar | Seguridad con un punto ciego | `TASK-056` |
| Sin pruebas de carga | Las afirmaciones de rendimiento son cualitativas | `TASK-052` |

## 5. Recuento de hallazgos

| Área | Alto | Medio | Bajo | Informativo | Total |
|---|---:|---:|---:|---:|---:|
| Arquitectura (`ARQ`) | 0 | 3 | 3 | 0 | 6 |
| Funcional (`FUN`) | 6 | 8 | 8 | 0 | 22 |
| Backend (`BE`) | 0 | 6 | 7 | 1 | 14 |
| Base de datos (`DB`) | 0 | 7 | 4 | 2 | 13 |
| Frontend (`FE`) | 1 | 4 | 4 | 0 | 9 |
| Experiencia de usuario (`UX`) | 1 | 8 | 6 | 0 | 15 |
| Seguridad (`SEC`) | 2 | 7 | 8 | 1 | 18 |
| QA (`QA`) | 2 | 5 | 5 | 0 | 12 |
| Operación (`OPS`) | 4 | 5 | 4 | 0 | 13 |
| **Total** | **16** | **53** | **49** | **4** | **122** |

Ningún hallazgo se clasificó como Crítico. `SEC-02` pasaría a serlo si el sistema se expusiera a Internet con la configuración actual.

Varios hallazgos describen la misma causa desde dos áreas (por ejemplo `FE-01` y `QA-01`, o `BE-08` y `SEC-08`); el backlog los resuelve una sola vez. Causas distintas hay alrededor de un centenar.

## 6. Fortalezas que hay que conservar

1. La costumbre de escribir un plan con decisiones antes de programar.
2. Las reglas duras en la base de datos.
3. El contrato de API generado.
4. Las pruebas contra una base real.
5. El flujo de Control de Mesa.
6. La auditoría de cambios y la bitácora de accesos.
7. La separación en capas y los módulos de reglas puras.

Ninguna de las recomendaciones de esta auditoría pide reescribir estas piezas.
