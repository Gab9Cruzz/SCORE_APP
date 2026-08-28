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
        HttpResponse.json([{ id: 1, nombre: "Fútbol", estado: "Activo" }]),
      ),
      http.get("http://127.0.0.1:8000/api/v1/modalidades", () =>
        HttpResponse.json([{ id: 1, disciplina_id: 1, nombre: "Fútbol 11", tamano_equipo: 11, estado: "Activo" }]),
      ),
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
                modalidad_id: 1,
                estado: "Activo",
                fecha_inicio: "2026-04-01",
                fecha_fin: "2026-06-30",
              },
            ],
          },
        ]),
      ),
      http.get("http://127.0.0.1:8000/api/v1/torneo-grupos/7", () =>
        HttpResponse.json({
          id: 7,
          nombre: "Liga Relámpago",
          ediciones: [
            {
              id: 20,
              numero_edicion: 2,
              disciplina_id: 1,
              modalidad_id: 1,
              estado: "Activo",
              fecha_inicio: "2026-04-01",
              fecha_fin: "2026-06-30",
            },
          ],
        }),
      ),
      http.get("http://127.0.0.1:8000/api/v1/torneos/20", () =>
        HttpResponse.json({
          id: 20,
          nombre: "Liga Relámpago - Edición 2",
          torneo_grupo_id: 7,
          numero_edicion: 2,
          disciplina_id: 1,
          modalidad_id: 1,
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
    // Selector de ediciones del grupo (pedido de seguimiento a
    // ediciones-catalogo-disciplinas-plan.md: administrar ediciones desde
    // adentro de "Ver Torneo", no solo desde la Pestaña Torneos).
    expect(screen.getByLabelText("Edición:")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /Edición 2 — Activo/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "+ Nueva edición" })).toBeInTheDocument();
    // Sub-nav propio del dashboard, además del admin-nav global.
    expect(screen.getByRole("link", { name: "Estadísticas" })).toBeInTheDocument();
    // index redirige a "equipos" — el botón de esa sub-pestaña ya visible.
    expect(await screen.findByRole("button", { name: "+ Agregar Equipo" })).toBeInTheDocument();
  });

  it("permite crear una nueva edición sin salir del dashboard y navega a ella", async () => {
    mockComoTorneoAdmin();
    server.use(
      http.get("http://127.0.0.1:8000/api/v1/disciplinas", () =>
        HttpResponse.json([{ id: 1, nombre: "Fútbol", estado: "Activo" }]),
      ),
      http.get("http://127.0.0.1:8000/api/v1/modalidades", () =>
        HttpResponse.json([{ id: 1, disciplina_id: 1, nombre: "Fútbol 11", tamano_equipo: 11, estado: "Activo" }]),
      ),
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
                modalidad_id: 1,
                estado: "Activo",
                fecha_inicio: "2026-04-01",
                fecha_fin: "2026-06-30",
              },
            ],
          },
        ]),
      ),
      http.get("http://127.0.0.1:8000/api/v1/torneo-grupos/7", () =>
        HttpResponse.json({
          id: 7,
          nombre: "Liga Relámpago",
          ediciones: [
            {
              id: 20,
              numero_edicion: 2,
              disciplina_id: 1,
              modalidad_id: 1,
              estado: "Activo",
              fecha_inicio: "2026-04-01",
              fecha_fin: "2026-06-30",
            },
          ],
        }),
      ),
      http.get("http://127.0.0.1:8000/api/v1/torneos/20", () =>
        HttpResponse.json({
          id: 20,
          nombre: "Liga Relámpago - Edición 2",
          torneo_grupo_id: 7,
          numero_edicion: 2,
          disciplina_id: 1,
          modalidad_id: 1,
          estado: "Activo",
          fecha_inicio: "2026-04-01",
          fecha_fin: "2026-06-30",
        }),
      ),
      http.get("http://127.0.0.1:8000/api/v1/torneos/21", () =>
        HttpResponse.json({
          id: 21,
          nombre: "Liga Relámpago - Edición 3",
          torneo_grupo_id: 7,
          numero_edicion: 3,
          disciplina_id: 1,
          modalidad_id: 1,
          estado: "Activo",
          fecha_inicio: "2026-07-01",
          fecha_fin: "2026-09-30",
        }),
      ),
      http.post("http://127.0.0.1:8000/api/v1/torneos", async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        // D-Eng-5: no debe mandar disciplina_id/modalidad_id, se heredan.
        expect(body).toEqual({ torneo_grupo_id: 7, fecha_inicio: "2026-07-01", fecha_fin: "2026-09-30" });
        return HttpResponse.json(
          {
            id: 21,
            nombre: "Liga Relámpago - Edición 3",
            torneo_grupo_id: 7,
            numero_edicion: 3,
            disciplina_id: 1,
            modalidad_id: 1,
            estado: "Activo",
            fecha_inicio: "2026-07-01",
            fecha_fin: "2026-09-30",
          },
          { status: 201 },
        );
      }),
      http.get("http://127.0.0.1:8000/api/v1/inscripciones", () => HttpResponse.json([])),
      http.get("http://127.0.0.1:8000/api/v1/equipos", () => HttpResponse.json([])),
      http.get("http://127.0.0.1:8000/api/v1/plantillas", () => HttpResponse.json([])),
    );

    renderApp("/login");
    await iniciarSesion();
    await screen.findByText("Liga Relámpago");
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Ver Torneo →" }));
    await screen.findByRole("heading", { name: "Liga Relámpago — Edición 2" });

    await user.click(screen.getByRole("button", { name: "+ Nueva edición" }));
    await user.type(screen.getByLabelText("Fecha de inicio"), "2026-07-01");
    await user.type(screen.getByLabelText("Fecha de fin"), "2026-09-30");
    await user.click(screen.getByRole("button", { name: "Crear edición" }));

    expect(await screen.findByRole("heading", { name: "Liga Relámpago — Edición 3" })).toBeInTheDocument();
    // T17 (equipos-disciplina-navegacion-plan.md): este camino ya caía en
    // "Agregar Equipo" antes del plan y tiene que seguir haciéndolo — es
    // el mismo destino que ahora usa "Nueva edición" desde la Pestaña
    // Torneos (T16), que era el que estaba roto.
    expect(await screen.findByRole("heading", { name: "Equipos inscritos" })).toBeInTheDocument();
  });
});
