import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { TOKEN_STORAGE_KEY } from "./api/client";
import { AuthProvider } from "./auth/AuthContext";
import { server } from "./test/msw-server";
import { createTestQueryClient } from "./test/test-utils";

// TASK-041: una página que revienta al dibujarse. Va en su propio archivo
// porque vi.mock reemplaza el módulo para todo el archivo de pruebas.
vi.mock("./pages/MiCuenta", () => ({
  MiCuentaPage: () => {
    throw new Error("fallo provocado en Mi cuenta");
  },
}));

describe("Límite de errores alrededor de las rutas (TASK-041)", () => {
  let consola: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    consola = vi.spyOn(console, "error").mockImplementation(() => {});
    localStorage.setItem(TOKEN_STORAGE_KEY, "fake-token");
    localStorage.setItem("score-app.session", JSON.stringify({ username: "usuario_test", rol: "Arbitro", id: 7 }));
    server.use(http.get("http://127.0.0.1:8000/api/v1/disciplinas/con-partidos", () => HttpResponse.json([])));
  });
  afterEach(() => consola.mockRestore());

  it("un error en una página muestra la recuperación y la barra de navegación sigue visible", async () => {
    render(
      <QueryClientProvider client={createTestQueryClient()}>
        <MemoryRouter initialEntries={["/mi-cuenta"]}>
          <AuthProvider>
            <App />
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(await screen.findByRole("heading", { name: /Algo falló al mostrar esta página/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Recargar" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Portal público" })).toBeInTheDocument();
  });
});
