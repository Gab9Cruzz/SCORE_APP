import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderOptions } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";

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
 * (PlantillasAdmin, RegistroLoteAdmin, JugadoresAdmin...) y sin un Router
 * alrededor esos hooks tiran en el render, no solo al navegar. Ningún test
 * de este wrapper necesita rutas anidadas reales — para eso está
 * `App.routing.test.tsx`, que arma su propio `MemoryRouter` aparte. */
export function createWrapper() {
  const queryClient = createTestQueryClient();
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  };
}

export function renderWithQueryClient(ui: ReactElement, options?: RenderOptions) {
  return render(ui, { wrapper: createWrapper(), ...options });
}
