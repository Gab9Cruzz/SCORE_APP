import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { App } from "../../../App";
import { AuthProvider } from "../../../auth/AuthContext";
import { server } from "../../../test/msw-server";
import { createTestQueryClient } from "../../../test/test-utils";

const LOGIN = "http://127.0.0.1:8000/api/v1/auth/login";
const ME = "http://127.0.0.1:8000/api/v1/auth/me";

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

function mockComoTorneoAdmin() {
  server.use(
    http.post(LOGIN, () => HttpResponse.json({ access_token: "fake-token", token_type: "bearer", rol: "TorneoAdmin" })),
    http.get(ME, () => HttpResponse.json({ id: 1, username: "torneo_admin_test", rol: "TorneoAdmin" })),
  );
}

async function iniciarSesion() {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Usuario"), "torneo_admin_test");
  await user.type(screen.getByLabelText("Contraseña"), "clave12345");
  await user.click(screen.getByRole("button", { name: "Ingresar" }));
}

// torneos-admin-plan.md, Fase 2: integración real (sin mockear useNavigate,
// a diferencia de TorneosAdmin.test.tsx) — "Ver Torneo" desde la tarjeta
// tiene que aterrizar de verdad en el dashboard scoped correcto.
describe("Torneo Admin — dashboard scoped por torneo", () => {
  it("Ver Torneo navega al dashboard con el header compuesto grupo + edición", async () => {
    mockComoTorneoAdmin();
    server.use(
      http.get("http://127.0.0.1:8000/api/v1/disciplinas", () =>
        HttpResponse.json([{ id: 1, nombre: "Fútbol", tipo: "Equipo", estado: "Activo" }]),
      ),
      http.get("http://127.0.0.1:8000/api/v1/modalidades", () => HttpResponse.json([])),
      http.get("http://127.0.0.1:8000/api/v1/torneo-grupos", () =>
        HttpResponse.json([
          {
            id: 7,
            nombre: "Liga Relámpago",
            ediciones: [
              {
                id: 20,
                numero_edicion: 2,
                disciplina_id: 1,
                modalidad_id: null,
                estado: "Activo",
                fecha_inicio: "2026-04-01",
                fecha_fin: "2026-06-30",
              },
            ],
          },
        ]),
      ),
      http.get("http://127.0.0.1:8000/api/v1/torneo-grupos/7", () =>
        HttpResponse.json({ id: 7, nombre: "Liga Relámpago" }),
      ),
      http.get("http://127.0.0.1:8000/api/v1/torneos/20", () =>
        HttpResponse.json({
          id: 20,
          nombre: "Liga Relámpago - Edición 2",
          torneo_grupo_id: 7,
          numero_edicion: 2,
          disciplina_id: 1,
          modalidad_id: null,
          estado: "Activo",
          fecha_inicio: "2026-04-01",
          fecha_fin: "2026-06-30",
        }),
      ),
      http.get("http://127.0.0.1:8000/api/v1/inscripciones", () => HttpResponse.json([])),
      http.get("http://127.0.0.1:8000/api/v1/equipos", () => HttpResponse.json([])),
      http.get("http://127.0.0.1:8000/api/v1/plantillas", () => HttpResponse.json([])),
    );

    renderApp("/login");
    await iniciarSesion();
    await waitFor(() => expect(screen.getByRole("heading", { name: "Torneo Admin" })).toBeInTheDocument());

    await screen.findByText("Liga Relámpago");
    await userEvent.setup().click(screen.getByRole("button", { name: "Ver Torneo →" }));

    expect(await screen.findByRole("heading", { name: "Liga Relámpago — Edición 2" })).toBeInTheDocument();
    expect(screen.getByText("Estado: Activo")).toBeInTheDocument();
    // Sub-nav propio del dashboard, además del admin-nav global.
    expect(screen.getByRole("link", { name: "Estadísticas" })).toBeInTheDocument();
    // index redirige a "equipos" — el botón de esa sub-pestaña ya visible.
    expect(await screen.findByRole("button", { name: "+ Agregar Equipo" })).toBeInTheDocument();
  });
});
