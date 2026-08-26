import { setupServer } from "msw/node";

/** Servidor MSW compartido — intercepta a nivel de red, no el cliente
 * openapi-fetch (más robusto ante cambios internos del cliente). Ciclo de
 * vida (listen/resetHandlers/close) registrado globalmente en setup.ts;
 * cada test agrega sus propios handlers con `server.use(...)`. */
export const server = setupServer();
