import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { TOKEN_STORAGE_KEY } from "../../api/client";
import { AuthProvider } from "../../auth/AuthContext";
import { server } from "../../test/msw-server";
import { createTestQueryClient } from "../../test/test-utils";
import { UsuariosAdminPage } from "./UsuariosAdmin";

const USUARIOS = "http://127.0.0.1:8000/api/v1/usuarios";
// Mismo key privado que AuthContext.tsx (ver nota en MisPartidos.test.tsx).
const SESSION_STORAGE_KEY = "score-app.session";

function sembrarSesion(id: number) {
  localStorage.setItem(TOKEN_STORAGE_KEY, "fake-token");
  localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify({ username: "admin_test", rol: "AdminGeneral", id }));
}

function renderPagina() {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <UsuariosAdminPage />
      </AuthProvider>
    </QueryClientProvider>,
  );
}

// El motor compartido (list/create/edit/baja) ya está probado en
// SimpleResourceAdminPage.test.tsx — esto confirma la config de Usuario
// (basePath, campos con password, isSelf) y el gap de D3 (password
// opcional al editar).
describe("UsuariosAdminPage (roles-3-modulos-plan.md, Fase 4)", () => {
  it("lista usuarios con rol y estado", async () => {
    server.use(
      http.get(USUARIOS, () =>
        HttpResponse.json([
          { id: 1, username: "admin_test", nombre: "Admin", rol: "AdminGeneral", estado: "Activo", fecha_registro: "2026-01-01T00:00:00" },
        ]),
      ),
    );
    renderPagina();
    expect(await screen.findByText("admin_test")).toBeInTheDocument();
    expect(screen.getByText("AdminGeneral")).toBeInTheDocument();
  });

  it("crear: pide username, nombre, password y rol", async () => {
    const user = userEvent.setup();
    server.use(http.get(USUARIOS, () => HttpResponse.json([])));
    renderPagina();
    await screen.findByText("No hay usuarios creados todavía.");

    await user.click(screen.getByRole("button", { name: "+ Nuevo" }));

    expect(screen.getByLabelText("Usuario")).toBeInTheDocument();
    expect(screen.getByLabelText("Nombre")).toBeInTheDocument();
    const passwordInput = screen.getByLabelText("Contraseña");
    expect(passwordInput).toHaveAttribute("type", "password");
    expect(screen.getByLabelText("Rol")).toBeInTheDocument();
  });

  it("editar: el campo de contraseña arranca vacío — dejarlo en blanco no la cambia (D3)", async () => {
    const user = userEvent.setup();
    server.use(
      http.get(USUARIOS, () =>
        HttpResponse.json([
          { id: 2, username: "arbitro1", nombre: "Árbitro Uno", rol: "Arbitro", estado: "Activo", fecha_registro: "2026-01-01T00:00:00" },
        ]),
      ),
    );
    renderPagina();
    await screen.findByText("arbitro1");

    await user.click(screen.getByRole("button", { name: "Editar" }));

    expect(screen.getByLabelText("Nueva contraseña (dejar en blanco para no cambiar)")).toHaveValue("");
    // El resto de los campos SÍ vienen precargados.
    expect(screen.getByLabelText("Nombre")).toHaveValue("Árbitro Uno");
  });

  it("isSelf: no muestra 'Dar de baja' en la propia fila (D2a)", async () => {
    server.use(
      http.get(USUARIOS, () =>
        HttpResponse.json([
          { id: 1, username: "admin_test", nombre: "Admin", rol: "AdminGeneral", estado: "Activo", fecha_registro: "2026-01-01T00:00:00" },
          { id: 2, username: "arbitro1", nombre: "Árbitro Uno", rol: "Arbitro", estado: "Activo", fecha_registro: "2026-01-01T00:00:00" },
        ]),
      ),
    );
    sembrarSesion(1);
    renderPagina();
    await screen.findByText("admin_test");

    // Solo una fila (la de "arbitro1") tiene botón de baja — la propia no.
    expect(screen.getAllByRole("button", { name: "Dar de baja" })).toHaveLength(1);
  });
});
