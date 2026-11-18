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
  },
})
