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
          { id: 1, username: "admin_test", nombre: "Admin", rol: "AdminGeneral", estado: "Activo", licencia_activa: true, fecha_registro: "2026-01-01T00:00:00" },
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
          { id: 2, username: "arbitro1", nombre: "Árbitro Uno", rol: "Arbitro", estado: "Activo", licencia_activa: true, fecha_registro: "2026-01-01T00:00:00" },
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
          { id: 1, username: "admin_test", nombre: "Admin", rol: "AdminGeneral", estado: "Activo", licencia_activa: true, fecha_registro: "2026-01-01T00:00:00" },
          { id: 2, username: "arbitro1", nombre: "Árbitro Uno", rol: "Arbitro", estado: "Activo", licencia_activa: true, fecha_registro: "2026-01-01T00:00:00" },
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

// --- Licencia + asignación de torneos (rbac-licencias-torneos-plan.md, §5.3) ---

describe("UsuariosAdminPage — licencia y torneos (rbac-licencias-torneos-plan.md)", () => {
  it("muestra el toggle de licencia y dispara PATCH al tocarlo", async () => {
    const user = userEvent.setup();
    let cuerpoRecibido: unknown;
    server.use(
      http.get(USUARIOS, () =>
        HttpResponse.json([
          { id: 2, username: "arbitro1", nombre: "Árbitro Uno", rol: "Arbitro", estado: "Activo", licencia_activa: true, fecha_registro: "2026-01-01T00:00:00" },
        ]),
      ),
      http.patch(`${USUARIOS}/2/licencia`, async ({ request }) => {
        cuerpoRecibido = await request.json();
        return HttpResponse.json({ id: 2, licencia_activa: false });
      }),
    );
    renderPagina();
    await screen.findByText("arbitro1");

    const toggle = screen.getByRole("checkbox", { name: "Licencia activa — arbitro1" });
    expect(toggle).toBeChecked();

    await user.click(toggle);
    expect(cuerpoRecibido).toEqual({ activa: false });
  });

  it("isSelf: no muestra el toggle en la propia fila (mismo criterio que 'Dar de baja')", async () => {
    server.use(
      http.get(USUARIOS, () =>
        HttpResponse.json([
          { id: 1, username: "admin_test", nombre: "Admin", rol: "AdminGeneral", estado: "Activo", licencia_activa: true, fecha_registro: "2026-01-01T00:00:00" },
        ]),
      ),
    );
    sembrarSesion(1);
    renderPagina();
    await screen.findByText("admin_test");

    expect(screen.queryByRole("checkbox", { name: "Licencia activa — admin_test" })).not.toBeInTheDocument();
    expect(screen.getByText("Activa")).toBeInTheDocument();
  });

  it("'Gestionar torneos' solo aparece para filas TorneoAdmin", async () => {
    server.use(
      http.get(USUARIOS, () =>
        HttpResponse.json([
          { id: 2, username: "torneo_admin1", nombre: "TA Uno", rol: "TorneoAdmin", estado: "Activo", licencia_activa: true, fecha_registro: "2026-01-01T00:00:00" },
          { id: 3, username: "arbitro1", nombre: "Árbitro Uno", rol: "Arbitro", estado: "Activo", licencia_activa: true, fecha_registro: "2026-01-01T00:00:00" },
        ]),
      ),
    );
    renderPagina();
    await screen.findByText("torneo_admin1");

    expect(screen.getAllByRole("button", { name: "Gestionar torneos" })).toHaveLength(1);
  });

  it("abre el modal, precarga el set actual, y guarda el nuevo set", async () => {
    const user = userEvent.setup();
    let cuerpoRecibido: unknown;
    server.use(
      http.get(USUARIOS, () =>
        HttpResponse.json([
          { id: 2, username: "torneo_admin1", nombre: "TA Uno", rol: "TorneoAdmin", estado: "Activo", licencia_activa: true, fecha_registro: "2026-01-01T00:00:00" },
        ]),
      ),
      http.get(`${USUARIOS}/2/torneos`, () => HttpResponse.json([1])),
      http.get("http://127.0.0.1:8000/api/v1/torneos", () =>
        HttpResponse.json([
          { id: 1, nombre: "Copa Uno", estado: "Activo" },
          { id: 2, nombre: "Copa Dos", estado: "Activo" },
        ]),
      ),
      http.patch(`${USUARIOS}/2/torneos`, async ({ request }) => {
        cuerpoRecibido = await request.json();
        return HttpResponse.json([2]);
      }),
    );
    renderPagina();
    await screen.findByText("torneo_admin1");

    await user.click(screen.getByRole("button", { name: "Gestionar torneos" }));

    expect(await screen.findByText("Copa Uno")).toBeInTheDocument();
    // Precarga: Torneo 1 ya asignado (GET .../torneos devolvió [1]).
    expect(screen.getByLabelText("Copa Uno")).toBeChecked();
    expect(screen.getByLabelText("Copa Dos")).not.toBeChecked();

    await user.click(screen.getByLabelText("Copa Uno"));
    await user.click(screen.getByLabelText("Copa Dos"));
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    expect(cuerpoRecibido).toEqual({ torneo_ids: [2] });
  });

  it("modal: 'No hay torneos activos para asignar' cuando la lista viene vacía (T13)", async () => {
    const user = userEvent.setup();
    server.use(
      http.get(USUARIOS, () =>
        HttpResponse.json([
          { id: 2, username: "torneo_admin1", nombre: "TA Uno", rol: "TorneoAdmin", estado: "Activo", licencia_activa: true, fecha_registro: "2026-01-01T00:00:00" },
        ]),
      ),
      http.get(`${USUARIOS}/2/torneos`, () => HttpResponse.json([])),
      http.get("http://127.0.0.1:8000/api/v1/torneos", () => HttpResponse.json([])),
    );
    renderPagina();
    await screen.findByText("torneo_admin1");
    await user.click(screen.getByRole("button", { name: "Gestionar torneos" }));

    expect(await screen.findByText("No hay torneos activos para asignar.")).toBeInTheDocument();
  });

  it("modal: Escape cierra sin guardar", async () => {
    const user = userEvent.setup();
    server.use(
      http.get(USUARIOS, () =>
        HttpResponse.json([
          { id: 2, username: "torneo_admin1", nombre: "TA Uno", rol: "TorneoAdmin", estado: "Activo", licencia_activa: true, fecha_registro: "2026-01-01T00:00:00" },
        ]),
      ),
      http.get(`${USUARIOS}/2/torneos`, () => HttpResponse.json([])),
      http.get("http://127.0.0.1:8000/api/v1/torneos", () => HttpResponse.json([{ id: 1, nombre: "Copa Uno", estado: "Activo" }])),
    );
    renderPagina();
    await screen.findByText("torneo_admin1");
    await user.click(screen.getByRole("button", { name: "Gestionar torneos" }));
    await screen.findByText("Copa Uno");

    await user.keyboard("{Escape}");

    expect(screen.queryByText("Copa Uno")).not.toBeInTheDocument();
  });
});
