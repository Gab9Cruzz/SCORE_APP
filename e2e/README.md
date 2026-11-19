# Recorridos de extremo a extremo

Cinco recorridos en un navegador real, con el frontend y la API juntos
(TASK-046, PR-060 a PR-064 de `docs/audit/07_AUDITORIA_QA.md`).

| Archivo | Recorrido |
|---|---|
| `pr060-alta-completa.spec.ts` | Torneo, tres equipos, plantilla por lote en pantalla, fixture; el portal lo muestra solo después de publicar. |
| `pr061-partido-en-vivo.spec.ts` | Alineación, inicio, gol, doble amarilla (roja automática), cambio y fin; marcador y tabla en el portal. |
| `pr062-penales.spec.ts` | Resultado directo 1-1 con penales 4-3 en una semifinal; el ganador pasa a la final. |
| `pr063-roles.spec.ts` | Árbitro, TorneoAdmin sin torneos y cuenta con la licencia revocada. |
| `pr064-cierre-reapertura.spec.ts` | Reclamo en semifinal, cierre con el podio de la llave, reapertura y nuevo cierre. |

## Cómo correrlos

Requisitos: PostgreSQL local, el entorno de `backend/.venv` instalado y
`npm ci` hecho en `frontend/`.

```bash
cd e2e
npm ci
npx playwright test             # una vez
npm run test:repetir            # tres veces seguidas
```

Playwright levanta sus propios servidores y no toca los de desarrollo:

- la API en el puerto 8100, sobre la base `torneos_e2e`, que se **borra y
  recrea vacía** en cada corrida (`scripts/preparar_base.py`; solo acepta
  nombres que terminen en `_e2e`);
- Vite en el 5190, apuntando a esa API.

Cada recorrido crea sus datos por la API (`tests/api.ts`), así que no
dependen entre sí. Localmente usa el Chrome instalado; en CI, el Chromium de
Playwright.

Variables opcionales: `E2E_DATABASE_URL` (por defecto
`postgresql+psycopg://postgres:1234@localhost:5432/torneos_e2e`),
`E2E_PYTHON`, `E2E_API_PORT`, `E2E_WEB_PORT`, `E2E_ADMIN_PASSWORD`.

## Cuando algo falla

Cada fallo deja captura y traza en `test-results/`. La traza se abre con:

```bash
npx playwright show-trace test-results/<carpeta>/trace.zip
```

En CI (trabajo `e2e`, solo en `main`) quedan como artefacto `e2e-trazas`.
