import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderOptions } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";

/** QueryClient para tests: sin reintentos (si no, un test de "error" tarda
 * varios ciclos en asentarse) y sin cache entre tests. */
export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

/** Wrapper para `renderHook`/`render` — cada llamada arma su propio
 * QueryClient, así un test no contamina el cache de otro. Incluye
 * `MemoryRouter`: varias páginas de torneo-admin usan `Link`/`useNavigate`
 * (PlantillasDelTorneo, RegistroLoteAdmin, JugadoresAdmin...) y sin un Router
 * alrededor esos hooks tiran en el render, no solo al navegar. Ningún test
 * de este wrapper necesita rutas anidadas reales — para eso está
 * `App.routing.test.tsx`, que arma su propio `MemoryRouter` aparte.
 *
 * `AuthProvider` (rbac-licencias-torneos-plan.md, Fase 3): agregado acá
 * en vez de en cada test file — `useAuth()` ya lo necesitan
 * `TorneosAdminPage` (filtro "mis torneos") y probablemente más pantallas
 * en el futuro; sin sesión sembrada, `session` es `null` (mismo
 * comportamiento que "sin loguear" en cualquier test que no le importe la
 * sesión) — no rompe ningún test que no use `useAuth()`. */
export function createWrapper() {
  const queryClient = createTestQueryClient();
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <AuthProvider>{children}</AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>
    );
  };
}

export function renderWithQueryClient(ui: ReactElement, options?: RenderOptions) {
  return render(ui, { wrapper: createWrapper(), ...options });
}
