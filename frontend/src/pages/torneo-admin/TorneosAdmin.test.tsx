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

// Catálogo unificado (ediciones-catalogo-disciplinas-plan.md, Decisión A1):
// ya no hay `tipo` en DISCIPLINA, y toda disciplina tiene 1+ modalidades.
const DISCIPLINAS = [
  { id: 1, nombre: "Fútbol", estado: "Activo" },
  { id: 2, nombre: "Tenis", estado: "Activo" },
];
const MODALIDADES = [
  { id: 1, nombre: "Fútbol 11", disciplina_id: 1, tamano_equipo: 11, estado: "Activo" },
  { id: 2, nombre: "Singles", disciplina_id: 2, tamano_equipo: 1, estado: "Activo" },
];

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
                modalidad_id: 1,
                estado: "Activo",
                fecha_inicio: "2026-04-01",
                fecha_fin: "2026-06-30",
              },
              {
                id: 10,
                numero_edicion: 1,
                disciplina_id: 1,
                modalidad_id: 1,
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
                modalidad_id: 2,
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

  it("Torneo nuevo: Modalidad es siempre obligatoria, sus opciones se filtran por la Disciplina elegida", async () => {
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
    // Está siempre presente (catálogo unificado — Decisión A1), a
    // diferencia del Tipo binario de antes, pero sin opciones hasta elegir
    // una Disciplina.
    expect(await screen.findByLabelText("Modalidad")).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Fútbol 11" })).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Disciplina"), "Fútbol");
    expect(await screen.findByRole("option", { name: "Fútbol 11" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Singles" })).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Disciplina"), "Tenis");
    expect(await screen.findByRole("option", { name: "Singles" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Fútbol 11" })).not.toBeInTheDocument();
  });

  it("Torneo nuevo: crea un grupo con torneo_grupo_nombre, disciplina y modalidad", async () => {
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
    await user.selectOptions(await screen.findByLabelText("Modalidad"), "Fútbol 11");
    await user.type(screen.getByLabelText("Fecha de inicio"), "2026-03-01");
    await user.type(screen.getByLabelText("Fecha de fin"), "2026-05-15");
    await user.click(screen.getByRole("button", { name: "Crear" }));

    await waitFor(() =>
      expect(bodyRecibido).toMatchObject({ torneo_grupo_nombre: "Liga Relámpago", disciplina_id: 1, modalidad_id: 1 }),
    );
  });

  it("Nueva edición: muestra Disciplina/Modalidad heredadas como texto, sin pedirlas ni mandarlas (D-Eng-5)", async () => {
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
                modalidad_id: 1,
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

    // Texto plano heredado — ni un <select> ni un campo del form (Fase 2
    // parte A del plan).
    expect(screen.queryByLabelText("Nombre del torneo")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Disciplina")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Modalidad")).not.toBeInTheDocument();
    expect(await screen.findByText("Fútbol")).toBeInTheDocument();
    expect(await screen.findByText("Fútbol 11")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Fecha de inicio"), "2026-06-01");
    await user.type(screen.getByLabelText("Fecha de fin"), "2026-08-30");
    await user.click(screen.getByRole("button", { name: "Crear edición" }));

    await waitFor(() => expect(bodyRecibido).toEqual({
      torneo_grupo_id: 7,
      fecha_inicio: "2026-06-01",
      fecha_fin: "2026-08-30",
    }));
  });
});
