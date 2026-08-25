# Score-App — Frontend

Vite + React + TypeScript + React Router + TanStack Query, con un cliente API
tipado generado desde el OpenAPI del backend (`openapi-typescript` +
`openapi-fetch`). Ver el design doc en `../docs/designs/frontend-inicial-dashboard-mesa-en-vivo.md`
para el porqué de estas decisiones.

## Correr en desarrollo

1. Backend corriendo en `http://127.0.0.1:8000` (ver `../backend/README` /
   `run.py` — en Windows usar `python run.py`, no `uvicorn app.main:app`
   directo).
2. `npm install`
3. `npm run dev` → http://localhost:5173

`.env` trae `VITE_API_BASE_URL=http://127.0.0.1:8000` por defecto (sin el
prefijo `/api/v1` — los paths del cliente generado ya lo incluyen).

## Regenerar el cliente tipado

Con el backend corriendo:

```
npm run gen:api
```

Lee `http://127.0.0.1:8000/openapi.json` y regenera `src/api/schema.d.ts`.
Corré esto cada vez que el backend agregue/cambie un endpoint — si no, el
cliente queda desincronizado hasta la próxima corrida manual (ver
Dependencies en el design doc).

## Páginas

- `/dashboard` — Dashboard de Torneo (público). Tabla de posiciones,
  goleadores, próximos partidos.
- `/control-de-mesa` — Control de Mesa (requiere rol Admin o Árbitro).
  Carga de goles/tarjetas/cambios, pensado para uso desde el celular.
- `/partido/:partidoId/en-vivo` — Partido en Vivo (público). Marcador y
  timeline de eventos, se actualiza solo cada 5s.

## Limitación conocida

El modelo de datos no distingue titular/suplente — el flujo de Cambio en
Control de Mesa ofrece toda la plantilla vigente del equipo (menos quien ya
salió o fue expulsado) como candidatos para "quién entra", no solo el banco
real. Ver el pre-chequeo de Cambio en el design doc.
