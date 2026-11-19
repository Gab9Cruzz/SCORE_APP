import { defineConfig, devices } from "@playwright/test";
import { ADMIN_PASSWORD, API_PORT, API_URL, WEB_PORT, WEB_URL } from "./tests/entorno";

/** TASK-046 (QA-05): frontend y backend juntos, en un navegador real.
 *
 * Levanta dos servidores propios, en puertos que no chocan con los de
 * desarrollo (8000/5173):
 * - la API sobre una base `*_e2e` recreada vacía en cada corrida
 *   (scripts/preparar_base.py), con el límite de intentos de login apagado:
 *   los recorridos inician sesión muchas veces desde la misma IP;
 * - el frontend de Vite apuntando a esa API.
 *
 * Cada recorrido crea sus datos por la API (tests/api.ts), así que no
 * dependen entre sí ni del orden. */

const python =
  // Relativo a backend/, que es donde corre el comando (así lee su .env).
  process.env.E2E_PYTHON ?? (process.platform === "win32" ? ".venv\\Scripts\\python.exe" : "python");
const databaseUrl = process.env.E2E_DATABASE_URL ?? "postgresql+psycopg://postgres:1234@localhost:5432/torneos_e2e";

export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  // Una sola base compartida: en serie, para que un recorrido no vea a
  // medias los datos de otro.
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: WEB_URL,
    // Un fallo deja traza y captura (criterio de aceptación).
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
    locale: "es-EC",
    timezoneId: "America/Guayaquil",
  },
  projects: [
    {
      name: "chromium",
      // Localmente, el Chrome instalado (sin descargar navegadores); en CI,
      // el Chromium de Playwright.
      use: { ...devices["Desktop Chrome"], ...(process.env.CI ? {} : { channel: "chrome" }) },
    },
  ],
  webServer: [
    {
      command: `"${python}" ../e2e/scripts/preparar_base.py && "${python}" ../e2e/scripts/api.py`,
      cwd: "../backend",
      url: `${API_URL}/health`,
      reuseExistingServer: false,
      timeout: 120_000,
      stdout: "pipe",
      env: {
        DATABASE_URL: databaseUrl,
        E2E_DATABASE_URL: databaseUrl,
        E2E_API_PORT: String(API_PORT),
        ADMIN_USERNAME: "admin",
        ADMIN_PASSWORD,
        CORS_ORIGINS: WEB_URL,
        LOGIN_RATE_LIMIT_INTENTOS: "0",
        LOGIN_RATE_LIMIT_INTENTOS_CUENTA: "0",
        ZONA_HORARIA: "America/Guayaquil",
      },
    },
    {
      command: `npx vite --host 127.0.0.1 --port ${WEB_PORT} --strictPort`,
      cwd: "../frontend",
      url: WEB_URL,
      reuseExistingServer: false,
      timeout: 120_000,
      env: { VITE_API_BASE_URL: API_URL },
    },
  ],
});
