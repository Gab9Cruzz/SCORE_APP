# Score-App

Sistema de gestión de torneos deportivos: catálogo de disciplinas, equipos
y jugadores, inscripciones, plantillas, traspasos, partidos y estadísticas
en vivo.

FastAPI + PostgreSQL + React (Vite + TypeScript).

## Levantar todo

Necesitás PostgreSQL corriendo. Dos terminales:

**Backend** → http://localhost:8000
```powershell
cd backend
.venv\Scripts\activate
python run.py
```
En Windows es `python run.py`, **no** `uvicorn app.main:app` — el porqué
está explicado arriba de `backend/run.py`. Confirmá en
http://localhost:8000/health → `{"status":"ok"}`.

**Frontend** → http://localhost:5173
```powershell
cd frontend
npm run dev
```

Primera vez: `pip install -r backend/requirements.txt`, `npm install` en
`frontend/`, y crear la base con los scripts de [`database/`](database/README.md).

## Verificar antes de dar algo por terminado

```powershell
.\verificar.ps1
```

Corre tests de backend, lint, typecheck, tests de frontend y build de
producción, y frena en el primer fallo. No necesita el servidor levantado
(sí PostgreSQL: crea y destruye sus propias bases, nunca toca
`torneos_mvp`).

Los pedazos por separado: `python -m pytest` en `backend/`,
`npm run verify` en `frontend/`.

## Dónde está cada cosa

| | |
|---|---|
| [`backend/`](backend/README.md) | API. `routes` → `services` → `repositories` → `models`. Las reglas de negocio duras viven en triggers de la base, no en Python. |
| [`frontend/`](frontend/README.md) | SPA. Cliente API **tipado y generado** desde el OpenAPI del backend. |
| [`database/`](database/README.md) | El esquema, en SQL puro. Sin Alembic. **Leer ese README antes de tocar el esquema** — la numeración de los archivos no es cronológica y confundirla cuesta caro. |
| `docs/plans/` | Un plan por módulo, con las decisiones y por qué se tomaron. |
| `docs/designs/` | Design docs de UI. |
| `TODOS.md` | Lo deferido de cada plan, con el motivo. |
| `infrastructure/` | `docker-compose.yml`. |

## Cómo se trabaja acá

El proyecto se construyó por módulos, cada uno con un plan en
`docs/plans/` que se escribe y se discute **antes** de tocar código. Los
planes registran las decisiones y las alternativas descartadas, así que
cuando algo parece raro, la respuesta suele estar ahí y no en el commit.

Dos convenciones que valen más de lo que parece:

- **El contrato del frontend se genera, no se escribe a mano.** Si cambiás
  un schema de Pydantic, corré `npm run gen:api` (con el backend arriba) y
  `tsc` te va a decir qué se rompió del otro lado. Un endpoint sin
  `response_model` deja su respuesta como `unknown` y ese aviso se pierde
  — si necesitás `response_model=None` (proyecciones que se eligen en
  runtime), declará la forma con `responses={200: ...}`; hay un ejemplo en
  `backend/app/api/routes/jugadores.py`.
- **La base es la última línea de defensa.** Exclusividad de un jugador
  por torneo, coherencia disciplina↔modalidad, validez de un jugador en un
  partido: son triggers en `database/06_triggers.sql`. El service da el
  mensaje legible; el trigger impide que un `psql` directo se lo saltee.
