# DESIGN.md — vocabulario visual de Score-App

Este documento describe el sistema visual que **ya existe** en
`frontend/src/index.css`, ordenado y con nombre. Se escribió en TASK-034, a
partir de la revisión visual de TASK-042 (`docs/audit/12_REVISION_VISUAL.md`).
No es un rediseño.

Reglas generales:

- Todo color, tamaño y espacio sale de una variable de `:root`. No hay
  valores sueltos en código nuevo.
- Código nuevo usa los componentes de `frontend/src/components/ui/`. Una
  pantalla vieja se migra cuando se la toca por otro motivo, no antes.
- Tema único, oscuro (`color-scheme: dark`).

## 1. Paleta

| Variable | Valor | Uso | Contraste sobre `--bg` / `--surface` / `--surface-alt` |
|---|---|---|---|
| `--bg` | `#0f1420` | Fondo de la página | — |
| `--surface` | `#171f30` | Tarjetas, barra de navegación, modales | — |
| `--surface-alt` | `#1f2a40` | Campos, botones secundarios, filas resaltadas | — |
| `--border` | `#2b3654` | Bordes de tarjetas, tablas y separadores (decorativos) | 1,5 / 1,4 / 1,2 |
| `--border-campo` | `#6b7ba3` | Contorno de campos de formulario | 4,4 / 3,9 / 3,4 |
| `--text` | `#e6ebf5` | Texto principal | 15,4 / 13,8 / 12,0 |
| `--text-muted` | `#93a0bd` | Texto secundario | 7,0 / 6,3 / 5,5 |
| `--accent` | `#4fd1c5` | Acción principal, enlaces, estado activo | 9,9 / 8,8 / 7,7 |
| `--accent-strong` | `#38b2ac` | Acento presionado | — |
| `--texto-sobre-acento` | `#05201d` | Texto del botón primario | 9,1 sobre `--accent` |
| `--danger` | `#ef6a6a` | Errores y acciones destructivas | 6,1 / 5,4 / 4,7 |
| `--warning` | `#e0b23a` | Advertencias | 9,3 / 8,3 / 7,2 |
| `--podio-oro` / `--podio-plata` / `--podio-bronce` | | Solo podio | — |

**`--border` no sirve para el contorno de un control.** Con 1,2:1 sobre
`--surface-alt`, un campo vacío no se distingue de su fondo; WCAG 1.4.11 pide
3:1. Por eso los campos usan `--border-campo`. Tarjetas y tablas siguen con
`--border` porque su borde es decorativo.

El color nunca es la única señal: un error lleva texto, un estado lleva
etiqueta.

## 2. Tipografía

Fuente del sistema (`system-ui, -apple-system, "Segoe UI", Roboto`). Seis
tamaños:

| Variable | Valor | Uso |
|---|---|---|
| `--texto-xs` | 0,75rem (12px) | Insignias, metadatos muy secundarios |
| `--texto-sm` | 0,85rem (13,6px) | Etiquetas de campo, ayuda, texto `.muted` |
| `--texto-md` | 1rem (16px) | Cuerpo |
| `--texto-lg` | 1,25rem (20px) | Títulos de sección (`h2`) |
| `--texto-xl` | 1,5rem (24px) | Títulos de página en móvil |
| `--texto-2xl` | 2rem (32px) | `h1`, marcador |

Pesos: 400 para el texto y 600 para énfasis y botones primarios. El 700 queda
para la marca y el marcador.

Hoy la hoja tiene unos 18 tamaños distintos (0,7rem, 0,82rem, 0,9rem, 1,05rem…).
Al migrar una regla, se lleva al tamaño más cercano de la escala. La excepción
documentada es el texto de los campos dentro de `.login-form` y
`.resource-form`, que conserva sus 0,9rem para no cambiar esas pantallas.

## 3. Espaciado

| Variable | Valor |
|---|---|
| `--espacio-1` | 0,25rem (4px) |
| `--espacio-2` | 0,5rem (8px) |
| `--espacio-3` | 0,75rem (12px) |
| `--espacio-4` | 1rem (16px) |
| `--espacio-5` | 1,5rem (24px) |
| `--espacio-6` | 2rem (32px) |
| `--espacio-7` | 3rem (48px) |

Convención: `--espacio-2` entre controles de una misma fila, `--espacio-3`
entre campos de un formulario, `--espacio-4` como relleno de tarjeta y margen
lateral de la página en móvil.

## 4. Radios y elevación

- `--radius` (10px) para todo: tarjetas, campos, botones, modales.
- Las píldoras (insignias, chips de disciplina) usan `999px`.
- No hay sombras. La jerarquía se marca con el fondo: `--bg`, luego
  `--surface`, luego `--surface-alt`. El modal oscurece la página con
  `rgba(0, 0, 0, 0.55)`.

## 5. Estados

Cada lista o bloque que carga datos muestra uno de estos cuatro estados, con
el mismo texto en toda la aplicación. `<Table>` ya los resuelve.

| Estado | Cómo se ve | Texto por defecto |
|---|---|---|
| Carga | Párrafo simple, o esqueleto con brillo donde el salto de alto molesta (`.estado-fase__skeleton`) | "Cargando..." |
| Vacío | Párrafo que dice qué falta y, si se puede, qué hacer | "No hay elementos." (cada pantalla da el suyo) |
| Error | `.error-text` (`--danger`) con el mensaje de la API | "No se pudo cargar la lista." |
| Éxito | `.success-text` (`--accent`) cerca de la acción, sin modal | — |

Un error de un formulario va debajo del campo (`<Field error>`) o, si es
general, encima de los botones.

## 6. Botones

`<Button variante=…>`, en `components/ui/Button.tsx`.

| Variante | Aspecto | Cuándo |
|---|---|---|
| `primario` | Relleno `--accent`, texto `--texto-sobre-acento`, peso 600 | La acción principal de la pantalla o del formulario. **Una sola por zona.** |
| `secundario` (por defecto) | Fondo `--surface-alt`, borde `--border` | Acciones frecuentes que no son la principal: Editar, Recargar |
| `peligro` | Fondo `--surface-alt`, borde y texto `--danger` | Ejecutar algo destructivo (Confirmar una baja). Nunca va relleno |
| `enlace` | Sin fondo, texto `--accent` | Salir sin hacer nada (Cancelar, Volver) o navegar |

Reglas:

- En la fila de botones de un formulario o modal, el enlace de salida va
  primero y la acción principal al final, como en `ResourceForm`.
- Una acción destructiva **pide confirmación** (TASK-038). El botón que abre la
  confirmación es `secundario`; el que la ejecuta, `peligro`; el que la
  descarta, `secundario` y con el foco puesto.
- El texto de un botón es un verbo con su objeto: "Guardar cambios", "Dar de
  baja". Nunca "OK" ni "Sí".
- Deshabilitado: opacidad 0,5. Si no es obvio por qué está deshabilitado, se
  explica al lado con texto.
- `type="button"` por defecto. Un botón que envía un formulario lo dice:
  `type="submit"`.
- El foco se ve: contorno de 2px en `--accent`.
- Área táctil mínima de 44px en las pantallas de mesa (`.mesa`) y en las que
  se usan en la cancha. Está pendiente en las demás (UX-20).

## 7. Campos

`<Field etiqueta error ayuda>{(p) => <input {...p} />}</Field>`, en
`components/ui/Field.tsx`.

- La etiqueta está siempre visible, arriba del control. El placeholder no la
  reemplaza.
- El borde es `--border-campo`. Con error, `--danger` y `aria-invalid`.
- La ayuda y el error quedan enlazados al control con `aria-describedby`, así
  que el lector de pantalla los lee al entrar al campo.
- Los checkbox van con la caja antes del texto (`.resource-form__checkbox`).

## 8. Tablas

`<Table encabezados cargando error vacio mensajeVacio etiqueta>`, en
`components/ui/Table.tsx`.

- La tabla va dentro de `.table-scroll`: una tabla ancha hace scroll ella
  misma, no la página.
- La primera columna va alineada a la izquierda y las demás, centradas (regla
  global de `th`/`td`).
- La columna de acciones no tiene título visible; para lectores de pantalla
  se llama "Acciones".
- Si una página tiene más de una tabla, cada una lleva `etiqueta`.

`ResourceTable` (en `components/admin/`) es la tabla de CRUD construida sobre
`<Table>`: suma Editar, la baja con confirmación y las acciones extra.

## 9. Modales

`<Modal titulo|etiqueta|idTitulo onCerrar sinGuardar cierreBloqueado ancho>`,
en `components/ui/Modal.tsx`. Todos los modales de la aplicación lo usan
(TASK-035).

- Usa `role="dialog"` y `aria-modal`. Toma su nombre del título (`titulo`).
  Si el título cambia según el paso, lo da `etiqueta` o `idTitulo`.
- Al abrirse, el foco va al primer control, salvo que uno tenga `autoFocus`.
  Tab y Shift+Tab no salen del modal. Al cerrar, el foco vuelve a quien lo
  abrió. Todo eso lo hace `hooks/useModalFocusTrap.ts`.
- Escape y un clic en el fondo cierran. Con `sinGuardar` (hay datos que se
  perderían), en vez de cerrar muestran "Hay datos sin guardar" con dos
  botones: "Seguir editando", que recibe el foco, y "Descartar y cerrar". El
  "Cancelar" del modal pasa por la misma pregunta si usa `pedirCierre`, que
  el modal le da cuando su contenido es una función.
- Con `cierreBloqueado` (guardando), no se cierra.
- Un modal dentro de otro funciona: Escape y Tab los atiende solo el de
  adelante.
- Mientras haya un modal abierto, la página de atrás no se desplaza.
- El ancho es 480px; con `ancho`, 560px (contenido con tablas o pasos).
- Los botones van al pie, dentro de `.resource-form__actions`.

## 10. Estado de la migración

| Pieza | Migrada en | Notas |
|---|---|---|
| `Login` | TASK-034 | `Field` y `Button` |
| `UsuariosAdmin` y su modal | TASK-034 | Mediante los componentes compartidos de abajo |
| `SimpleResourceAdminPage`, `ResourceForm`, `ResourceTable` | TASK-034 | También las usan Torneos, Jugadores y Equipos, que reciben el mismo cambio |
| Los nueve modales | TASK-035 | Solo cambia la envoltura; su contenido sigue igual |
| Todo lo demás | — | Se migra al tocarlo |

Los componentes base tienen especificidad baja (una clase), así que las reglas
por contexto que ya existen (`.page__header button`, `.table-actions button`,
`.resource-form__actions button[type="submit"]`) siguen ganando. Por eso
migrar una pantalla no cambia su aspecto. Los únicos cambios visibles de
TASK-034, comprobados con capturas antes y después, son:

- El contorno de todos los campos pasa de `--border` a `--border-campo`
  (contraste de 1,2:1 a 3,4:1).
- En los formularios de las piezas migradas, "Cancelar" deja de ser un botón
  gris nativo y pasa a la variante `enlace`. El "Guardar" del modal de torneos
  deja de ser gris y pasa a `primario`. Era el problema UX-11: tres estilos de
  botón en una misma pantalla.
