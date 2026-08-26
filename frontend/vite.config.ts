/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    // Esta fase (T1) solo monta la infra — los primeros tests reales
    // llegan en T7/T13/T17. Sin esto, "vitest run" sale con código 1
    // cuando no encuentra ningún archivo *.test.*, que es exactamente
    // el estado entre T1 y T7.
    passWithNoTests: true,
  },
})
