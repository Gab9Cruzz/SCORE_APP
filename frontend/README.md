# Score-App — Frontend

Vite + React + TypeScript + React Router + TanStack Query, con un cliente API
tipado generado desde el OpenAPI del backend (`openapi-typescript` +
`openapi-fetch`). Ver el design doc en `../docs/designs/frontend-inicial-dashboard-mesa-en-vivo.md`
para el porqué de estas decisiones.

## Versión de Node

Node **26** (LTS), fijado en `.nvmrc` (`nvm use`). `package.json` admite
`>=22`. Vitest arranca sus workers con `--no-experimental-webstorage`
(`vite.config.ts`): desde Node 25 el `localStorage` nativo tapa al de jsdom
y rompe toda la suite.

## Correr en desarrollo

1. Backend corriendo en `http://127.0.0.1:8000` (ver `../backend/README` /
   `run.py` — en Windows usar `python run.py`, no `uvicorn app.main:app`
   directo).
2. `npm install --legacy-peer-deps`
3. `copy .env.example .env` (en Linux/Mac, `cp`)
4. `npm run dev` → http://localhost:5173

`.env.example` trae `VITE_API_BASE_URL=http://127.0.0.1:8000` (sin el
prefijo `/api/v1` — los paths del cliente generado ya lo incluyen). Sin
`.env`, el login falla como error de red.

## Regenerar el cliente tipado

Con el backend corriendo:

```
npm run gen:api
```

Lee `http://127.0.0.1:8000/openapi.json` y regenera `src/api/schema.d.ts`.
Corré esto cada vez que el backend agregue/cambie un endpoint — si no, el
cliente queda desincronizado hasta la próxima corrida manual (ver
Dependencies en el design doc).

## Comandos

| Comando | Qué hace |
|---|---|
| `npm run dev` | Servidor de desarrollo en http://localhost:5173 |
| `npm run verify` | oxlint, `tsc`, Vitest y build; lo mismo que corre CI. Vitest no revisa tipos: sin `tsc` un error de tipos pasa. |
| `npm test` | Solo Vitest (pruebas con MSW, sin backend) |
| `npm run coverage` | Vitest con cobertura y los pisos de `vite.config.ts` (ver `../docs/cobertura.md`) |
| `npm run gen:api` | Regenera `src/api/schema.d.ts` desde la API levantada |

Los recorridos de punta a punta en navegador real están en `../e2e/`
(Playwright, con su propio README).

Por qué `--legacy-peer-deps`: `openapi-typescript` declara TypeScript 5
como par y el proyecto usa TypeScript 6.

## Páginas

Las rutas están en `src/App.tsx`. Salvo el feed, el login y las páginas de
error, cada sección se carga aparte (`React.lazy`), y cada ruta tiene su
propio límite de errores: si una página falla, la barra de navegación
sigue en pie.

**Públicas**

| Ruta | Página |
|---|---|
| `/` | Feed de partidos (`publico/FeedPartidos`). Con sesión iniciada redirige a `/dashboard`. |
| `/portal` | El mismo feed, también con sesión (es el destino de "Portal público"). |
| `/torneos/:torneoId` | Detalle público de un torneo publicado: tabla, llave, resultados. |
| `/partido/:partidoId/en-vivo`, `/partidos/:partidoId` | Partido en vivo: marcador y eventos, se actualiza solo. |
| `/dashboard` | Tablero: posiciones, goleadores y próximos partidos por torneo. |
| `/login` | Inicio de sesión. |

**Con sesión** (`components/RequireRole`; sin el rol muestra "Sin permiso")

| Ruta | Roles | Página |
|---|---|---|
| `/mi-cuenta` | todos | Datos propios y cambio de contraseña. |
| `/control-de-mesa` | AdminGeneral, TorneoAdmin, Arbitro | Partidos del día y panel de mesa: cronómetro, goles, tarjetas, cambios. |
| `/control-de-mesa/partido/:partidoId` | AdminGeneral, TorneoAdmin, Arbitro | Gestionar partido: convocados y titulares, fecha, walkover, resultado directo. |
| `/arbitro` | AdminGeneral, Arbitro | Mis partidos asignados. |
| `/torneo-admin/torneos` y `/torneo-admin/torneos/:torneoId/*` | AdminGeneral, TorneoAdmin | Torneos y el tablero de cada uno: equipos, plantillas, traspasos, partidos (fixture, llaves, cierre, reclamos) y estadísticas. |
| `/torneo-admin/equipos`, `/equipos/:equipoId`, `/jugadores`, `/jugadores/:jugadorId/perfil`, `/plantillas/lote`, `/disciplinas` | AdminGeneral, TorneoAdmin | Equipos y su plantilla base, jugadores y perfiles, registro por lote, catálogo de disciplinas. |
| `/admin/usuarios`, `/admin/accesos`, `/admin/auditoria` | AdminGeneral | Usuarios, licencias y torneos asignados; bitácora de accesos; auditoría de cambios. |

Cualquier otra ruta muestra la página 404.

## Convocatoria a un partido

Se arma en Gestionar partido (`control-mesa/GestionarPartido.tsx`, con
`AlineacionEditor.tsx`). Sin convocatoria guardada, los cambios de la mesa
ofrecen toda la plantilla vigente del equipo. Con convocatoria (titular o
suplente por jugador), la mesa ofrece solo a los convocados. La tabla
`CONVOCADO_A_PARTIDO` no reemplaza la plantilla: dice quién de esa
plantilla fue convocado a ese partido.
