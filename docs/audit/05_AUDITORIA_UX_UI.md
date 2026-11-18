# 05 — Auditoría del frontend y de UX/UI

Fase V.

> **Declaración obligatoria sobre la evaluación visual.** **Ninguna pantalla fue probada visualmente.** El backend no pudo levantarse (sin PostgreSQL ni Docker en la máquina de auditoría) y no se dispuso de un navegador automatizado. Todo lo que sigue procede de leer el código de `frontend/src` (57 componentes y páginas `.tsx` y 20 módulos `.ts`, sin contar pruebas ni el esquema generado), la hoja de estilos `index.css` (2.452 líneas), un cálculo de contraste sobre la paleta y la ejecución de lint, typecheck, pruebas y build. Por eso los problemas de diseño y de responsive se clasifican como **riesgo potencial por lectura de CSS**, no como defectos observados. La revisión visual real queda como tarea (`TASK-042`) y es la mayor fuente de incertidumbre de esta auditoría.

## 1. Resultados de las herramientas (ejecutadas)

| Comprobación | Resultado |
|---|---|
| `oxlint` | 0 errores, 1 aviso (`set-state-in-effect` en `GestionarPartido.tsx:235`) |
| `tsc -b --noEmit` | Sin errores |
| `vitest run` tal como lo ejecuta `npm run verify` | **344 de 344 pruebas fallan** con Node 26.13.1 (ver `QA-01`) |
| `vitest run` con `NODE_OPTIONS=--no-experimental-webstorage` | 343 pasan, 1 falla (`QA-02`) |
| `vite build` (a una carpeta temporal fuera del repo) | Correcto. Un único JS de 527 kB (143 kB gzip) y CSS de 31 kB; Vite avisa de que supera 500 kB |
| `npm audit` | 8 vulnerabilidades (6 altas, 2 moderadas), todas en herramientas de desarrollo (`SEC-12`) |

## 2. Calidad técnica del frontend

### Fortalezas

- **Cliente de API tipado y generado** (`openapi-typescript` + `openapi-fetch`), con interceptor único para token, 401 y licencia revocada (`src/api/client.ts`).
- **Estado de servidor con TanStack Query** en todas las pantallas; no hay `fetch` en `useEffect`. Solo 16 `useEffect` en todo el código.
- **Lógica pura separada y probada**: `lib/colaOfflineEventos.ts`, `lib/reconciliarSlots.ts`, `lib/desempate.ts`, `components/eventos.ts`, `pages/control-mesa/alineacion.ts`.
- **Abstracciones de administración reutilizadas**: `useResourceCrud`, `ResourceTable`, `ResourceForm`, `FiltrosRecurso`, `SimpleResourceAdminPage`, `SelectorJugadorBuscable`.
- **Higiene**: 0 `any`, 0 `console.*`, 0 `dangerouslySetInnerHTML`, TypeScript estricto con `noUnusedLocals`.
- **El servidor decide**: la interfaz no reimplementa la máquina de estados del cronómetro ni las reglas de inicio; consume `acciones_permitidas`, `puede_iniciar` y `elegible_desempate`.
- **38 archivos de prueba, 344 casos**, con MSW simulando la API.

### Hallazgos técnicos

| ID | Tipo | Severidad | Hallazgo | Evidencia | Tarea |
|---|---|---|---|---|---|
| FE-01 | Confirmado (ejecutado) | Alto | La suite completa falla con la versión de Node instalada; no hay `engines` ni `.nvmrc` que fije la versión | `QA-01` | `TASK-001` |
| FE-02 | Confirmado (estático) | Medio | 90 conversiones `as never` evitan el cliente tipado y obligan a declarar a mano los tipos de respuesta. Concentradas en `Cronometro.tsx` (13), `GestionarPartido.tsx` (9), `TorneosAdmin.tsx` (7) y `useResourceCrud.ts` (7). Un cambio de contrato en esas llamadas no rompe la compilación, que es justo la garantía que el proyecto dice tener | recuento con `grep`; ejemplo en `pages/control-mesa/ControlDeMesa.tsx:26-55` | `TASK-032` |
| FE-03 | Confirmado (estático / ejecutado) | Medio | Sin `ErrorBoundary` (un error de render deja la pantalla en blanco), sin página 404 (cualquier ruta desconocida redirige a `/`) y sin división de código (0 `lazy()`; un visitante del portal descarga también el back-office) | `src/App.tsx:1-30,202`, salida del build | `TASK-041` |
| FE-04 | Mejora | Medio | Componentes monolíticos: `MesaPanel.tsx` 1.088 líneas, `TorneosAdmin.tsx` 987, `ModalResultadoDirecto.tsx` 912, `Cronometro.tsx` 880, `GestionarPartido.tsx` 664, `ModalAgregarInscripcion.tsx` 583, `ModalSiguienteFase.tsx` 535 | recuento de líneas | Extraer al tocarlos |
| FE-05 | Confirmado (estático) | Bajo | Si `GET /auth/me` falla tras un login correcto, `session.id` queda indefinido y "Mis partidos" no consulta nunca, sin mensaje | `src/auth/AuthContext.tsx:97-104`, `pages/arbitro/MisPartidos.tsx:32` | `TASK-036` |
| FE-06 | Confirmado (estático) | Bajo | Formato regional `es-AR` escrito en 12 archivos; fechas del servidor sin zona interpretadas como hora local del navegador; aritmética con `toISOString()` en el feed (`FUN-17`) | `grep` de `es-AR`; `pages/publico/FeedPartidos.tsx:17-21` | `TASK-040` |
| FE-07 | Confirmado (ejecutado) | Bajo | 90 avisos de MSW por peticiones sin manejador durante las pruebas; ruido que tapa fallos reales | salida de Vitest | `TASK-002` |
| FE-08 | Mejora | Medio | Una sola hoja de estilos global de 2.452 líneas, sin componentes de interfaz base ni escala de espaciado o tipografía; no existe una regla global para `button` (cada botón depende de una clase propia) | `src/index.css` | `TASK-034` |
| FE-09 | Confirmado (estático) | Bajo | Listas auxiliares cargadas enteras para traducir IDs a nombres (`/equipos?limit=200`, `/jugadores?limit=200`); `useFetchFaltantes` lo compensa con peticiones individuales por cada ID que falte | `pages/control-mesa/ControlDeMesa.tsx:57-66`, `hooks/useFetchFaltantes.ts` | `TASK-039` |

## 3. Diseño visual

Evaluado solo sobre el CSS.

| Aspecto | Observación |
|---|---|
| Identidad | Tema oscuro único (`color-scheme: dark`), acento turquesa `#4fd1c5`, tipografía del sistema. Sin logotipo: la marca es el texto "Score-App"; el favicon se usa también como imagen para redes |
| Variables | 14 variables en `:root` (fondo, superficies, borde, texto, acento, peligro, aviso, radio, podio). No hay escala de espaciado, de tamaños de letra ni de sombras |
| Tipografía | 15 tamaños distintos, de 0,7 rem a 2,5 rem; predominan 0,85 y 0,9 rem. El texto secundario (`.muted`) mide 13,6 px, por debajo de lo cómodo en móvil |
| Jerarquía | Un `h1` por página (30 en total) y tarjetas con `h2` |
| Iconografía | Emoji por disciplina (`components/iconosDisciplina.ts`); decisión documentada. Su aspecto varía entre sistemas operativos |
| Componentes | Tabla, formulario y filtros genéricos reutilizados en administración. Modales, botones y tarjetas se estilizan caso a caso |
| Estados | Carga como texto ("Cargando…", 37 apariciones), error en rojo, vacío con mensaje propio en casi todos los listados |
| Movimiento | Se respeta `prefers-reduced-motion` en dos bloques |

**No existe `DESIGN.md` ni sistema de diseño.** `TODOS.md` lo registra como "recomendado por cinco planes consecutivos, nunca ejecutado". Es la causa de fondo de las inconsistencias de la sección 5.

## 4. Experiencia de usuario

### Arquitectura de información

```
Sin sesión     /  (feed por día y deporte)  →  /torneos/:id  →  /partidos/:id
Con sesión     /dashboard · "Portal público" (enlace roto, FUN-12)
Mesa/Árbitro   /control-de-mesa → /control-de-mesa/partido/:id       /arbitro
TorneoAdmin    /torneo-admin → Torneos · Catálogo · Equipos · Jugadores
                 └ torneos/:id → Equipos · Plantillas · Traspasos · Partidos · Estadísticas
AdminGeneral   /admin/usuarios · /admin/accesos · /admin/auditoria
```

La estructura es razonable y está bien decidida: los recursos propios de un torneo viven dentro de él y los catálogos son globales. El punto débil es que un AdminGeneral ve ocho enlaces en la barra superior, sin agrupar.

### Flujos principales

| Flujo | Pasos | Valoración |
|---|---|---|
| Crear torneo y dejarlo listo | Crear → inscribir equipos (copia la plantilla base) → generar fixture o sorteo → reprogramar fechas una a una | Bueno hasta el fixture; reprogramar es tedioso (`UX-08`) |
| Cargar plantilla | Registro por lote: pegar filas → validar → confirmar | Bueno, con rechazo parcial explicado |
| Operar un partido | Lista → Gestionar → alineación → comprobación previa → empezar → eventos → finalizar | El mejor flujo de la aplicación; pensado para el pulgar |
| Cargar un acta atrasada | Modal de resultado directo | Bueno; afectado por `FUN-02` |
| Cerrar torneo | Asistente de siguiente fase con podio y empates | Bueno |
| Gestionar usuarios | Tabla + formulario + modal de torneos asignados | Correcto |

### Retroalimentación

- **Errores**: `apiErrorMessage` muestra el mensaje del servidor, casi siempre con texto que explica cómo seguir ("Bajá alguno a suplente antes de guardar"). Doce códigos de la base se traducen en el cliente. Otros llegan sin traducir: `jugador_ya_activo_en_este_torneo`, `equipo_ya_asignado_a_otro_grupo_en_esta_fase`, `hito_ya_registrado`, `partido_corrido_sin_ganador`, además de los mensajes crudos de PostgreSQL (`SEC-06`).
- **Éxito**: confirmación con `aria-live` tras cada evento en la mesa. En administración el éxito es implícito: la tabla se recarga.
- **Confirmaciones**: ver `UX-06`.
- **Sin conexión**: aviso de estado y cola de un evento pendiente en la mesa.

## 5. Tabla de problemas

| Pantalla o módulo | Problema | Severidad | Impacto UX | Mejora propuesta |
|---|---|---|---|---|
| **UX-01** Barra de navegación | Hasta 8 enlaces en una fila flexible sin salto de línea, desplazamiento ni menú; a 480 px o menos solo se le da ancho completo (`index.css`, `.nav-bar__links` y media query de la línea 979). *Riesgo potencial por lectura de CSS* | Medio | En móvil y tableta los enlaces de un administrador pueden desbordar la pantalla | Menú desplegable por debajo de unos 900 px y agrupar "Administración" (`TASK-036`) |
| **UX-02** Rutas protegidas (`RequireRole`) | A un usuario con sesión pero sin el rol se le dice "Necesitás iniciar sesión"; el enlace es un `<a href="/login">` que recarga la aplicación y pierde la ruta de origen (`components/RequireRole.tsx`, `pages/Login.tsx:80-94`) | Medio | Mensaje falso y callejón sin salida | Pantalla de "sin permiso" distinta de la de "sin sesión"; `<Link>` con `state.from` (`TASK-036`) |
| **UX-03** Modales (9 implementaciones) | Solo 4 declaran `aria-modal` y solo 1 atrapa el foco, cierra con Escape y devuelve el foco (`useModalFocusTrap`, usado únicamente en `ModalSiguienteFase.tsx`) | Medio | Con teclado o lector de pantalla el foco se escapa detrás del modal | Un componente `Modal` único (`TASK-035`) |
| **UX-04** Accesibilidad de base | Ver sección 7 | Medio | Barreras para teclado y lector de pantalla | `TASK-037` |
| **UX-05** Listados de administración | Sin paginación; búsqueda en servidor solo para jugadores; aviso de truncado solo a 200 filas, y cuatro listados se cortan en 100 sin aviso (`FUN-05`) | Alto | Datos que "desaparecen" al crecer | Paginación y búsqueda en servidor (`TASK-011`, `TASK-039`) |
| **UX-06** Acciones destructivas en tablas | "Dar de baja" (equipos, jugadores, usuarios), "Cancelar inscripción" y cancelar partido se ejecutan con un clic, sin confirmación ni deshacer (`pages/torneo-admin/SimpleResourceAdminPage.tsx:115`, `EquiposAdmin.tsx:278`, `torneo-dashboard/EquiposDelTorneo.tsx:149,268`, `PartidosDelTorneo.tsx:186`). En todo el frontend hay un solo `window.confirm` | Medio | Un toque accidental cancela una inscripción, con los efectos de `FUN-07` | Confirmación en línea o "deshacer" durante unos segundos (`TASK-038`) |
| **UX-07** Tema | Solo oscuro. El Control de Mesa se usa en cancha, a menudo a pleno sol. *No verificado* | Bajo | Legibilidad en exteriores | Tema claro de alto contraste para la mesa |
| **UX-08** Fixture | Las fechas se generan a las 00:00 y con una jornada por semana (`services/motor_formatos.py:197-204`); se corrigen partido a partido | Bajo | Trabajo repetitivo en torneos grandes | Edición por jornada o plantilla de horarios |
| **UX-09** Navegación con sesión | "Portal público" redirige al dashboard (`FUN-12`); `/dashboard` y el portal muestran información parecida con distinto aspecto | Medio | Enlace muerto; dos vistas de lo mismo | Ruta propia para el feed (`TASK-040`) |
| **UX-10** Imágenes | Escudos y fotos se cargan pegando una URL `https://` | Bajo | Fricción para usuarios no técnicos | Subida de archivos (pendiente en `TODOS.md`) |
| **UX-11** Coherencia global | Sin sistema de diseño; botones, modales y tarjetas con clases propias por pantalla; 15 tamaños de letra | Medio | Inconsistencia que crece con cada módulo | `DESIGN.md` y componentes base (`TASK-034`) |
| **UX-12** Mensajes de error | Códigos internos y mensajes de PostgreSQL visibles al usuario en algunos rechazos | Bajo | Texto incomprensible | Traducir todos los códigos y normalizar errores (`TASK-015`) |
| **UX-13** Título de la pestaña | Siempre "Score-App"; nunca se actualiza `document.title` | Bajo | Pestañas e historial indistinguibles | Título por pantalla (`TASK-037`) |
| **UX-14** Portal público | El feed no se actualiza solo (botón "Recargar"); vista previa de enlaces genérica (documentado) | Bajo | Resultados desactualizados | Sondeo suave cuando hay partidos en curso |
| **UX-15** Cuenta propia | No hay pantalla de perfil ni cambio de contraseña (`FUN-13`) | Medio | Dependencia del administrador | `TASK-033` |

## 6. Responsive

Sin verificación visual. Lo que dice el CSS:

| Punto de corte | Uso |
|---|---|
| hasta 480 px | Barra de navegación a ancho completo; marcador y cronómetro más pequeños |
| hasta 640 px | Ajustes de la mesa y del portal (dos bloques) |
| desde 800 px | Rejilla del dashboard |
| desde 1000 px | Panel de mesa en tres zonas; arrastrar y soltar en alineaciones (cuatro bloques) |

- **Mesa**: diseñada primero para móvil; 14 reglas fijan objetivos táctiles de 44 px o más, y el marcador queda fijo arriba. Es la parte más cuidada.
- **Tablas**: `table { width: 100% }` con contenedor desplazable (`.table-scroll`) en la tabla genérica y otros tres sitios. Las tablas de más de seis columnas (posiciones, auditoría, accesos) dependen de ese desplazamiento horizontal en el teléfono.
- **Contenido principal**: ancho máximo de 1100 px; en pantallas grandes sobra margen pero no se rompe.
- **Riesgos**: la barra superior (`UX-01`) y los modales grandes (resultado directo, agregar inscripción) en pantallas bajas.

Comprobar en 360, 768, 1280 y 1920 px es parte de `TASK-042`.

## 7. Accesibilidad (referencia WCAG 2.2)

### Contraste (calculado)

| Par | Sobre fondo | Sobre superficie | Sobre superficie alterna | Resultado |
|---|---:|---:|---:|---|
| Texto `#e6ebf5` | 15,4 | 13,8 | 12,0 | Supera AAA |
| Texto secundario `#93a0bd` | 7,0 | 6,3 | 5,5 | Supera AA |
| Acento `#4fd1c5` | 9,9 | 8,8 | 7,7 | Supera AA |
| Peligro `#ef6a6a` | 6,1 | 5,4 | 4,7 | Supera AA (justo) |
| Aviso `#e0b23a` | 9,3 | 8,3 | 7,2 | Supera AA |
| **Borde `#2b3654`** | 1,5 | 1,4 | 1,2 | **No alcanza 3:1** (1.4.11) |

La paleta de texto es buena. El problema está en los límites de los controles: los campos tienen fondo `--surface-alt` y borde `--border` sobre `--surface`, con una diferencia de 1,2 a 1,4 a 1.

### Lista de comprobación

| Criterio | Estado | Evidencia |
|---|---|---|
| 3.1.1 Idioma de la página | **Falla** | `frontend/index.html:2` declara `lang="en"` con toda la interfaz en español; un lector de pantalla la pronunciará en inglés |
| 2.4.2 Título de página | **Falla** | `document.title` no se usa en ningún archivo |
| 1.4.11 Contraste de elementos no textuales | **Falla** | Bordes de campos (tabla anterior) |
| 2.4.7 Foco visible | Parcial | No se elimina el contorno por defecto (ningún `outline: none`), lo cual es correcto; solo dos reglas definen un foco propio |
| 2.1.1 Teclado | Parcial | Botones y enlaces nativos. El arrastrar y soltar de alineaciones usa eventos de puntero (`usePointerDrag.ts`); no se verificó que la alternativa por botones cubra todo |
| 2.4.3 / 2.1.2 Foco en modales | **Falla en 8 de 9** | `UX-03` |
| 1.3.1 Información y relaciones | Parcial | 68 `<label>` que envuelven su campo (correcto); 16 tablas sin `scope` ni `caption`; columna de acciones con cabecera vacía |
| 4.1.2 Nombre, función, valor | Parcial | Botones "Editar" y "Dar de baja" idénticos en cada fila, sin nombre que indique sobre qué actúan (`components/admin/ResourceTable.tsx`) |
| 4.1.3 Mensajes de estado | Parcial | `aria-live` o `role` de estado solo en 6 archivos (mesa y alineaciones); "Cargando…" y los errores del resto no se anuncian |
| 1.4.1 Uso del color | Correcto donde se revisó | Tarjetas con texto y forma ("1A", "2A", "R"); estados con etiqueta de texto |
| 2.5.8 Tamaño del objetivo | Correcto en la mesa | 44 px mínimo en las acciones principales |
| 2.3.3 Animación | Correcto | `prefers-reduced-motion` |
| 1.1.1 Texto alternativo | Correcto | Dos `<img>` en todo el código, ambos con `alt`; iniciales decorativas con `aria-hidden` |
| 2.4.1 Saltar bloques | Falla | No hay enlace "saltar al contenido" |

## 8. Fortalezas visuales y de experiencia

- **Control de Mesa**: tres zonas fijas, marcador siempre visible, objetivos táctiles amplios, confirmación audible para lectores de pantalla y recuperación ante cortes de red.
- **Prevención de errores desde el servidor**: los botones del cronómetro reflejan `acciones_permitidas`; el botón de empezar muestra el motivo exacto del bloqueo.
- **Mensajes con salida**: la mayoría de los rechazos dicen qué hacer a continuación.
- **Estados vacíos con texto propio** en lugar de tablas en blanco.
- **Color nunca como único canal** en lo revisado.
- **Portal público** con enlaces compartibles (`/?deporte=…&fecha=…`) y barra de deportes que solo aparece si hay más de uno con contenido.
- **Paleta con buen contraste de texto**.

## 9. Propuestas de rediseño

Ordenadas por relación entre beneficio y esfuerzo. Ninguna requiere reescribir pantallas.

1. **Sistema de diseño mínimo** (`TASK-034`): `DESIGN.md` con escala de espaciado y tipografía, y cuatro componentes base (`Button`, `Modal`, `Field`, `Table`) extraídos de lo que ya existe. Todo lo demás se apoya en esto.
2. **Modal único accesible** (`TASK-035`): sustituir las nueve implementaciones por una con foco atrapado, Escape, `aria-modal` y cierre coherente.
3. **Navegación** (`TASK-036`): menú colapsable, grupo "Administración", pantalla de "sin permiso" y página 404.
4. **Listados** (`TASK-039`): paginación, búsqueda en servidor, total visible y orden por columnas en la tabla genérica.
5. **Acciones destructivas** (`TASK-038`): confirmación en línea con el nombre del elemento y sus consecuencias ("se cancelará la inscripción de Halcones FC; sus 14 jugadores quedarán libres").
6. **Accesibilidad de base** (`TASK-037`): idioma, títulos, cabeceras de tabla, anuncios de estado, borde de campos con contraste suficiente.
7. **Cuenta propia** (`TASK-033`): menú de usuario con cambio de contraseña.
8. **Después de la revisión visual** (`TASK-042`): ajustes de espaciado, jerarquía y responsive que solo se pueden decidir viendo las pantallas.

## 10. Mejoras de navegación

| Hoy | Propuesta |
|---|---|
| `/` muestra el feed sin sesión y redirige con sesión | `/` sigue igual; el feed pasa a `/portal`, accesible siempre |
| Ocho enlaces planos para AdminGeneral | "Operación" (Mesa, Mis partidos), "Torneos", "Administración" (Usuarios, Accesos, Auditoría) |
| Sin migas de pan dentro de un torneo | `Torneos › Liga Relámpago › Edición 2 › Plantillas` |
| Ruta desconocida redirige en silencio | Página 404 con enlaces útiles |
| Sin rol: "Necesitás iniciar sesión" | "Tu cuenta no tiene acceso a esta sección" con vuelta a su inicio |
| Selector de torneo solo en algunas pantallas | Recordar el último torneo usado por el operador |
