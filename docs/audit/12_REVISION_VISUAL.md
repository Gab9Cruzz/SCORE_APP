# 12 — Revisión visual real (TASK-042)

La auditoría de `05_AUDITORIA_UX_UI.md` se hizo sin poder ver ninguna pantalla. Esta revisión las recorre en un navegador real para confirmar o descartar lo que ahí se dedujo del código y del CSS, y para encontrar lo que el código no muestra.

Fecha: 2026-11-19. Rama `main`, después de TASK-033.

## Método

- **Entorno.** Base `torneos_demo` creada aparte desde `01`–`06`, `11`, `10_demo_torneos_admin.sql` y `seed_portal_demo.sql` (la base de desarrollo `torneos_mvp` no se tocó). API (`python run.py`) y frontend (`vite`) locales.
- **Cuentas.** Una por rol: `admin` (AdminGeneral), `organizador` (TorneoAdmin, con los torneos 1, 3 y 5), `arbitro1` (Árbitro de los partidos 3 y 5) y el visitante anónimo.
- **Navegador.** Chrome 140 sin interfaz, manejado con `playwright-core`. Script: [`capturas/capturar.mjs`](capturas/capturar.mjs).
- **Tamaños.** 360 × 740, 768 × 1024, 1280 × 800 y 1920 × 1080.
- **Qué se midió en cada pantalla y tamaño, además de la captura:**
  - el scroll horizontal de la página;
  - los elementos que salen del ancho de la ventana;
  - los controles de menos de 32 px;
  - los controles sin nombre accesible;
  - los errores de consola;
  - a 1280 px, los primeros 12 pasos de tabulación y si el foco se ve.
- **Modales.** Se abrieron con Enter y se comprobó si el foco entra, si Tab queda dentro y si Escape cierra. Script: [`capturas/modales.mjs`](capturas/modales.mjs).

Las capturas están en [`capturas/`](capturas/), con el nombre `<pantalla>__<ancho>.jpg`: 22 pantallas × 4 tamaños, más `sin-permiso__1280.jpg`.

> **Artefacto de captura.** En las capturas de página completa, la barra de acciones fija de "Gestionar partido" aparece en medio del contenido a 360 px (`gestionar-partido__360.jpg`), porque se dibuja donde estaba la ventana. En el navegador queda abajo, sin tapar nada. No es un defecto.

## Resultado por hallazgo de `05_AUDITORIA_UX_UI.md`

| Hallazgo | Veredicto | Evidencia |
|---|---|---|
| **UX-01** Barra de navegación | **Confirmado, peor de lo estimado** | Con AdminGeneral a 360 px la página tiene 364 px de scroll horizontal: los 8 enlaces no envuelven y ensanchan todo el documento (`usuarios__360.jpg`). Con TorneoAdmin entra, pero partiendo "Control de Mesa" en tres renglones. El árbitro desborda 9 px. A 768 px y más, bien |
| **UX-02** Rutas protegidas | **Confirmado** | Un árbitro con sesión que entra a `/admin/usuarios` lee "Necesitás iniciar sesión" y un `<a href="/login">` (`sin-permiso__1280.jpg`) |
| **UX-03** Modales | **Confirmado** | "Agregar equipo": el foco se queda en el botón que lo abrió, Tab sale del modal y Escape no lo cierra. "Resultado directo": el foco entra, pero Tab sale, y Escape ya no cierra cuando el foco quedó afuera; el foco termina en `<body>` |
| **UX-04** Accesibilidad de base | **Parcial** | Se descarta una parte: el foco se ve en todas las pantallas (0 de 260 pasos sin indicador). Se confirma otra: no hay enlace para saltar al contenido, y el feed y el partido en vivo no tienen `<h1>` (ver UX-22) |
| **UX-05** Listados | Sin verificar | Los datos de demostración no llegan a 100 filas |
| **UX-06** Acciones destructivas | Sin cambios | Verificado en el código; no se ejecutaron bajas sobre la demo. Lo resuelve TASK-038 |
| **UX-07** Tema | **Confirmado** (solo oscuro) | La interfaz no tiene tema claro. La legibilidad a pleno sol no se puede medir con capturas |
| **UX-08** Fixture | Sin verificar | No se generó un fixture |
| **UX-09** Navegación con sesión | **Confirmado** | Con sesión, el clic en "Portal público" deja al usuario en `/dashboard` |
| **UX-10** Imágenes | Sin cambios | Verificado en el código |
| **UX-11** Coherencia global | **Confirmado** | En una misma pantalla conviven tres estilos de botón: acento relleno ("+ Agregar Equipo"), oscuro con borde ("Editar") y gris nativo ("Gestionar Partido", "Empezar Partido", "Recargar", "Compartir", "Salir", "+ Nueva edición"). En la lista de torneos, "Archivar" es el único botón con acento: la acción menos frecuente y más delicada luce como la principal |
| **UX-12** Mensajes de error | Sin verificar | No se provocaron rechazos |
| **UX-13** Título de la pestaña | **Confirmado** | Las cinco rutas probadas dicen "Score-App" |
| **UX-14** Portal público | **Confirmado** | El feed tiene "Recargar" manual; no se observó actualización sola |
| **UX-15** Cuenta propia | **Resuelto** | TASK-033 agregó "Mi cuenta" (`mi-cuenta__*.jpg`) |

## Hallazgos nuevos

| Id | Pantalla | Problema | Severidad | Evidencia |
|---|---|---|---|---|
| **UX-16** | Torneo Admin › Torneos | La fila de acciones de cada tarjeta (hasta 7 botones) no envuelve: se sale de la tarjeta y de la página. Scroll horizontal de 218 px a 360, de 186 px a 768 y de 108 px **a 1280**. "Ver página pública" queda cortado y "Archivar" fuera de la tarjeta | Alto | `torneos__1280.jpg`, `torneos__360.jpg` |
| **UX-17** | Panel del torneo (las 5 pestañas) | A 360 px, el selector de edición y el botón "+ Nueva edición" van en una sola línea: 126 px de scroll horizontal | Medio | `torneo-equipos__360.jpg` |
| **UX-18** | Dashboard | A 360 px el selector de torneo se sale 75 px del borde | Medio | `dashboard__360.jpg` |
| **UX-19** | Control de Mesa (lista) | A 360 px cada tarjeta acomoda estado, torneo, equipos, fecha y botón en un orden distinto según el largo de los nombres. Los equipos quedan en una columna angosta, a una o dos palabras por renglón ("Demo / FC / Norte vs / Demo / FC / Centro") | Medio | `control-mesa__360.jpg` |
| **UX-20** | Gestionar partido, Usuarios | A 360 px hay 8 y 10 controles de menos de 32 px. La mesa se usa en el celular, en cancha | Medio | `metricas` del script, `gestionar-partido__360.jpg` |
| **UX-21** | Gestionar partido | `GET /partidos/{id}/cronometro` responde **400** cuando el torneo no tiene configuración de tiempos. Es un estado normal, no un error, pero deja dos errores en la consola por cada visita y ensucia cualquier monitoreo de 4xx | Bajo | Consola en las 4 capturas de `gestionar-partido` |
| **UX-22** | Feed, Partido en vivo | No hay `<h1>`: la página arranca con texto de tarjetas | Bajo | Métrica `h1` vacía |
| **UX-23** | Toda la app con sesión | Sin enlace "saltar al contenido": el AdminGeneral tabula 10 elementos del menú antes de llegar a la página | Bajo | Recorrido de teclado a 1280 px |
| **UX-24** | Partido en vivo | El enlace al torneo usa el morado por defecto de enlace visitado, fuera de la paleta | Bajo | `partido-en-vivo__360.jpg` |
| **UX-25** | Detalle de torneo (público) | A 360 px hay un hueco de unos 70 px entre el nombre del torneo y "Compartir" | Bajo | `detalle-torneo__360.jpg` |
| **UX-26** | Registro por lote | Ninguna pestaña de Torneo Admin aparece activa en esta ruta | Bajo | `registro-lote__1280.jpg` |

**Lo que está bien y conviene conservar:**

- Las tablas anchas (equipos, jugadores, auditoría, registro por lote) se desplazan dentro de su contenedor sin romper la página.
- El feed público y el login se ven bien en los cuatro tamaños.
- El foco con teclado se ve siempre.

## Qué tarea toma cada hallazgo

| Hallazgo | Tarea |
|---|---|
| UX-01, UX-02, UX-09, UX-23 | TASK-036 (navegación). UX-23 también encaja en TASK-037 |
| UX-03 | TASK-035 (modal único) |
| UX-11, UX-16, UX-17, UX-18, UX-19, UX-20, UX-24 | TASK-034 (componentes base y responsive). **UX-16 conviene hacerlo primero**: se ve en escritorio |
| UX-13, UX-22, UX-25 | TASK-037 (accesibilidad) |
| UX-21 | Backend, fuera de las tareas de UX: devolver 200 con `null` o 404 explícito. Queda anotado en `TODOS.md` |
| UX-26 | TASK-034 |

## Límites de esta revisión

- Navegador de escritorio con tamaño de móvil, sin dispositivo real ni pantalla táctil.
- Solo Chrome. Safari de iOS, que es lo que usan muchos organizadores, no se probó.
- No se probó con lector de pantalla.
- Con los datos de demostración no se ven listados largos (UX-05) ni torneos con muchas fases.
