import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { server } from "../../test/msw-server";
import { createWrapper } from "../../test/test-utils";
import { TorneosAdminPage } from "./TorneosAdmin";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => mockNavigate };
});

const DISCIPLINAS = [
  { id: 1, nombre: "Fútbol", tipo: "Equipo", estado: "Activo" },
  { id: 2, nombre: "Tenis", tipo: "Individual", estado: "Activo" },
];
const MODALIDADES = [{ id: 1, nombre: "Individual", disciplina_id: 2, tamano_equipo: 1, estado: "Activo" }];

function mockCatalogos() {
  server.use(
    http.get("http://127.0.0.1:8000/api/v1/disciplinas", () => HttpResponse.json(DISCIPLINAS)),
    http.get("http://127.0.0.1:8000/api/v1/modalidades", () => HttpResponse.json(MODALIDADES)),
  );
}

describe("TorneosAdminPage", () => {
  it("lista tarjetas por grupo con la disciplina resuelta y el badge de ediciones", async () => {
    mockCatalogos();
    server.use(
      http.get("http://127.0.0.1:8000/api/v1/torneo-grupos", () =>
        HttpResponse.json([
          {
            id: 1,
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
              {
                id: 10,
                numero_edicion: 1,
                disciplina_id: 1,
                modalidad_id: null,
                estado: "Finalizado",
                fecha_inicio: "2026-03-01",
                fecha_fin: "2026-05-15",
              },
            ],
          },
        ]),
      ),
    );
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <TorneosAdminPage />
      </Wrapper>,
    );

    expect(await screen.findByText("Liga Relámpago")).toBeInTheDocument();
    expect(screen.getByText(/Fútbol/)).toBeInTheDocument();
    expect(screen.getByText(/2 ediciones/)).toBeInTheDocument();
    // Abre la Activa (Edición 2), no la de numero_edicion más alto a ciegas.
    expect(screen.getByText(/Edición 2 — Activo/)).toBeInTheDocument();
  });

  it("Ver Torneo navega a la edición activa del grupo", async () => {
    mockCatalogos();
    server.use(
      http.get("http://127.0.0.1:8000/api/v1/torneo-grupos", () =>
        HttpResponse.json([
          {
            id: 1,
            nombre: "Copa Raíces",
            ediciones: [
              {
                id: 30,
                numero_edicion: 1,
                disciplina_id: 2,
                modalidad_id: 1,
                estado: "Activo",
                fecha_inicio: "2026-04-10",
                fecha_fin: "2026-06-20",
              },
            ],
          },
        ]),
      ),
    );
    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <TorneosAdminPage />
      </Wrapper>,
    );

    await screen.findByText("Copa Raíces");
    await user.click(screen.getByRole("button", { name: "Ver Torneo →" }));
    expect(mockNavigate).toHaveBeenCalledWith("/torneo-admin/torneos/30");
  });

  it("Modalidad se oculta por defecto y aparece solo para disciplina Individual", async () => {
    mockCatalogos();
    server.use(http.get("http://127.0.0.1:8000/api/v1/torneo-grupos", () => HttpResponse.json([])));
    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <TorneosAdminPage />
      </Wrapper>,
    );

    await user.click(await screen.findByRole("button", { name: "+ Torneo nuevo" }));
    expect(screen.queryByLabelText("Modalidad")).not.toBeInTheDocument();

    await user.selectOptions(await screen.findByLabelText("Disciplina"), "Tenis");
    expect(await screen.findByLabelText("Modalidad")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Disciplina"), "Fútbol");
    expect(screen.queryByLabelText("Modalidad")).not.toBeInTheDocument();
  });

  it("Torneo nuevo: crea un grupo con torneo_grupo_nombre", async () => {
    mockCatalogos();
    server.use(http.get("http://127.0.0.1:8000/api/v1/torneo-grupos", () => HttpResponse.json([])));
    let bodyRecibido: unknown;
    server.use(
      http.post("http://127.0.0.1:8000/api/v1/torneos", async ({ request }) => {
        bodyRecibido = await request.json();
        return HttpResponse.json({ id: 1, torneo_grupo_id: 1, numero_edicion: 1 }, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <TorneosAdminPage />
      </Wrapper>,
    );

    await user.click(await screen.findByRole("button", { name: "+ Torneo nuevo" }));
    await user.type(await screen.findByLabelText("Nombre del torneo"), "Liga Relámpago");
    await user.selectOptions(screen.getByLabelText("Disciplina"), "Fútbol");
    await user.type(screen.getByLabelText("Fecha de inicio"), "2026-03-01");
    await user.type(screen.getByLabelText("Fecha de fin"), "2026-05-15");
    await user.click(screen.getByRole("button", { name: "Crear" }));

    await waitFor(() =>
      expect(bodyRecibido).toMatchObject({ torneo_grupo_nombre: "Liga Relámpago", disciplina_id: 1 }),
    );
  });

  it("Nueva edición: manda torneo_grupo_id, sin pedir nombre de grupo", async () => {
    mockCatalogos();
    server.use(
      http.get("http://127.0.0.1:8000/api/v1/torneo-grupos", () =>
        HttpResponse.json([
          {
            id: 7,
            nombre: "Liga Relámpago",
            ediciones: [
              {
                id: 10,
                numero_edicion: 1,
                disciplina_id: 1,
                modalidad_id: null,
                estado: "Activo",
                fecha_inicio: "2026-03-01",
                fecha_fin: "2026-05-15",
              },
            ],
          },
        ]),
      ),
    );
    let bodyRecibido: unknown;
    server.use(
      http.post("http://127.0.0.1:8000/api/v1/torneos", async ({ request }) => {
        bodyRecibido = await request.json();
        return HttpResponse.json({ id: 2, torneo_grupo_id: 7, numero_edicion: 2 }, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <TorneosAdminPage />
      </Wrapper>,
    );

    await screen.findByText("Liga Relámpago");
    await user.click(screen.getByRole("button", { name: "+ Nueva edición" }));
    expect(screen.queryByLabelText("Nombre del torneo")).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Disciplina"), "Fútbol");
    await user.type(screen.getByLabelText("Fecha de inicio"), "2026-06-01");
    await user.type(screen.getByLabelText("Fecha de fin"), "2026-08-30");
    await user.click(screen.getByRole("button", { name: "Crear edición" }));

    await waitFor(() => expect(bodyRecibido).toMatchObject({ torneo_grupo_id: 7, disciplina_id: 1 }));
  });
});
