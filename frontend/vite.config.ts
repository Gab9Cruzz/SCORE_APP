/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    // Desde Node 25, `localStorage`/`sessionStorage` nativos están activos
    // por defecto y, sin `--localstorage-file`, valen `undefined`. Como
    // quedan en `globalThis`, tapan los de jsdom y toda la suite falla en
    // `localStorage.clear()` (docs/audit QA-01). Apagarlos en los workers
    // deja visibles los de jsdom. Node 22 y 24 aceptan el flag sin efecto.
    execArgv: ['--no-experimental-webstorage'],
    // TASK-047: `npm run coverage`. Los pisos por carpeta salen de la
    // medición registrada en docs/cobertura.md (medido menos dos puntos).
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/**/*.test.{ts,tsx}', 'src/test/**', 'src/api/schema.d.ts', 'src/main.tsx', 'src/vite-env.d.ts'],
      reporter: ['text-summary', 'html', 'json-summary'],
      reportsDirectory: './coverage',
      // Piso por carpeta crítica = medición del 2026-11-19 menos dos puntos
      // (docs/cobertura.md). Bajar de cualquiera hace fallar el comando.
      thresholds: {
        'src/lib/**': { lines: 95, statements: 95, branches: 95, functions: 90 },
        'src/hooks/**': { lines: 93, statements: 91, branches: 87, functions: 96 },
      },
    },
  },
})
