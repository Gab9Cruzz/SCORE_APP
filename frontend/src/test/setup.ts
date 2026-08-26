// Corre antes de cada archivo de test (ver vite.config.ts -> test.setupFiles).
// El import de "/vitest" en vez de la raíz del paquete extiende el `expect`
// de vitest en runtime Y tipa los matchers (toBeInTheDocument, etc.) — la
// raíz del paquete solo hace lo primero.
import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach } from "vitest";
import { cleanup } from "@testing-library/react";
import { server } from "./msw-server";

// server.listen() corre acá, a nivel de módulo, NO dentro de un
// beforeAll(): openapi-fetch resuelve `fetch` una sola vez, al crear el
// cliente (api/client.ts: `fetch: baseFetch = globalThis.fetch`, evaluado
// cuando el módulo se importa). Si el patch de MSW llegara recién en un
// beforeAll(), el cliente ya habría capturado el fetch real de Node —
// setupFiles corre ANTES de que se resuelvan los imports del archivo de
// test (que es lo que carga api/client.ts), así que esto tiene que pasar
// acá arriba, sincrónico, para llegar a tiempo.
//
// onUnhandledRequest: "error" — un request que ningún test mockeó falla
// ruidoso en vez de colgarse o pegarle silenciosamente a la red real.
server.listen({ onUnhandledRequest: "error" });
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// @testing-library/react limpia el DOM solo entre tests cuando detecta los
// hooks globales de Jest/Vitest en `globalThis` — acá no están (vitest
// config no tiene `globals: true`, a propósito, para no tocar tsconfig),
// así que hay que llamarlo a mano o el render de un test queda pegado en
// el DOM del siguiente.
afterEach(() => cleanup());

// AuthContext lee la sesión de localStorage al montar (loadStoredSession).
// Sin esto, un test que hace login deja el token pegado y el siguiente
// test arranca "ya logueado" — pasó de verdad, ver roles-3-modulos-plan.md
// Fase 2 T17/T13.
afterEach(() => localStorage.clear());
