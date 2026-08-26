import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { App } from "./App";
import { AuthProvider } from "./auth/AuthContext";
import { server } from "./test/msw-server";
import { createTestQueryClient } from "./test/test-utils";

const LOGIN = "http://127.0.0.1:8000/api/v1/auth/login";
const ME = "http://127.0.0.1:8000/api/v1/auth/me";
const TORNEOS = "http://127.0.0.1:8000/api/v1/torneos";
const PARTIDOS = "http://127.0.0.1:8000/api/v1/partidos";

function renderApp(initialPath: string) {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function mockLogin(rol: string) {
  server.use(
    http.post(LOGIN, () => HttpResponse.json({ access_token: "fake-token", token_type: "bearer", rol })),
  );
}

async function iniciarSesion() {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Usuario"), "usuario_test");
  await user.type(screen.getByLabelText("Contraseña"), "clave12345");
  await user.click(screen.getByRole("button", { name: "Ingresar" }));
}

describe("Ruteo y redirect por rol (roles-3-modulos-plan.md, Fase 2, D2)", () => {
  beforeEach(() => {
    server.use(
      http.get(TORNEOS, () => HttpResponse.json([])),
      http.get(PARTIDOS, () => HttpResponse.json([])),
      // AuthContext.login() llama /auth/me tras cada login exitoso (Fase 3,
      // D2) — default handler acá para que los tests que no lo pisan no
      // revienten con un request sin mockear (onUnhandledRequest: "error").
      http.get(ME, () => HttpResponse.json({ id: 42, username: "usuario_test", rol: "Arbitro" })),
    );
  });

  it("navegar directo a /torneo-admin sin sesión muestra el prompt de login, no crashea", () => {
    renderApp("/torneo-admin/torneos");
    expect(screen.getByText("Necesitás iniciar sesión")).toBeInTheDocument();
    expect(screen.getByText(/TorneoAdmin o AdminGeneral/)).toBeInTheDocument();
  });

  it("navegar directo a /arbitro sin sesión muestra el prompt de login, no crashea (Fase 3, D3)", () => {
    renderApp("/arbitro");
    expect(screen.getByText("Necesitás iniciar sesión")).toBeInTheDocument();
    expect(screen.getByText("Arbitro", { selector: "strong" })).toBeInTheDocument();
  });

  it("TorneoAdmin logueado no puede entrar a /arbitro (D3: sin AdminGeneral/TorneoAdmin en la lista)", async () => {
    mockLogin("TorneoAdmin");
    renderApp("/login");
    await iniciarSesion();
    await waitFor(() => expect(screen.getByRole("heading", { name: "Torneo Admin" })).toBeInTheDocument());

    renderApp("/arbitro");
    expect(screen.getByText("Necesitás iniciar sesión")).toBeInTheDocument();
  });

  it("TorneoAdmin: login redirige a /torneo-admin (antes NO pasaba — login() no exponía el rol)", async () => {
    mockLogin("TorneoAdmin");
    renderApp("/login");

    await iniciarSesion();

    await waitFor(() => expect(screen.getByRole("heading", { name: "Torneo Admin" })).toBeInTheDocument());
  });

  it("AdminGeneral: login también redirige a /torneo-admin", async () => {
    mockLogin("AdminGeneral");
    renderApp("/login");

    await iniciarSesion();

    await waitFor(() => expect(screen.getByRole("heading", { name: "Torneo Admin" })).toBeInTheDocument());
  });

  it("Arbitro: login redirige a /arbitro, no a /dashboard ni /torneo-admin (Fase 3, D3)", async () => {
    mockLogin("Arbitro");
    renderApp("/login");

    await iniciarSesion();

    await waitFor(() => expect(screen.getByRole("heading", { name: "Mis partidos" })).toBeInTheDocument());
  });

  it("el fallo de GET /auth/me tras el login no rompe el login ni el redirect por rol", async () => {
    // Fase 3, D2: /auth/me se pide aparte del login para tener el id. Si
    // esa llamada falla, el login ya fue exitoso (login() usa el rol que
    // SÍ vino de /auth/login) — el redirect no depende de session.id.
    server.use(http.get(ME, () => HttpResponse.error()));
    mockLogin("Arbitro");
    renderApp("/login");

    await iniciarSesion();

    await waitFor(() => expect(screen.getByRole("heading", { name: "Mis partidos" })).toBeInTheDocument());
    // Sin id, "Mis partidos" no puede armar el filtro — se lo dice al
    // usuario en vez de pedir partidos sin filtrar o crashear.
    expect(
      screen.getByText(/No pudimos confirmar tu usuario/),
    ).toBeInTheDocument();
  });
});
