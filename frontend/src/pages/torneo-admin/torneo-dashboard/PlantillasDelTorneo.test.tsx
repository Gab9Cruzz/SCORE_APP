import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { server } from "../../../test/msw-server";
import { createWrapper } from "../../../test/test-utils";
import { PlantillasDelTorneoPage } from "./PlantillasDelTorneo";
import type { TorneoDashboardContext } from "./TorneoDashboard";

const CONTEXTO: TorneoDashboardContext = {
  torneoId: 20,
  torneoGrupoId: 7,
  disciplinaId: 1,
  modalidadId: null,
  torneoContexto: "Liga Relámpago — Edición 2",
};

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => mockNavigate, useOutletContext: () => CONTEXTO };
});

const JUGADORES = "http://127.0.0.1:8000/api/v1/jugadores";
const PERFILES = "http://127.0.0.1:8000/api/v1/perfiles";
const EQUIPOS = "http://127.0.0.1:8000/api/v1/equipos";
const INSCRIPCIONES = "http://127.0.0.1:8000/api/v1/inscripciones";
const PLANTILLAS = "http://127.0.0.1:8000/api/v1/plantillas";

function renderPagina() {
  const Wrapper = createWrapper();
  return render(
    <Wrapper>
      <PlantillasDelTorneoPage />
    </Wrapper>,
  );
}

function mockBase() {
  server.use(
    http.get(JUGADORES, () => HttpResponse.json([{ id: 1, nombre: "Carlos Pérez" }])),
    http.get(PERFILES, () => HttpResponse.json([{ id: 1, jugador_id: 1, disciplina_id: 1 }])),
    http.get(EQUIPOS, () => HttpResponse.json([{ id: 1, nombre: "Halcones FC" }])),
    http.get(INSCRIPCIONES, () => HttpResponse.json([{ id: 5, equipo_id: 1 }])),
    http.get(PLANTILLAS, () =>
      HttpResponse.json([
        {
          id: 1,
          jugador_perfil_id: 1,
          inscripcion_torneo_id: 5,
          dorsal: 10,
          fecha_inicio: "2026-01-01",
          fecha_fin: null,
          estado: "Activo",
        },
      ]),
    ),
  );
}

describe("PlantillasDelTorneoPage", () => {
  it("resuelve jugador/equipo a nombres, sin volver a mostrar el torneo (ya se sabe)", async () => {
    mockBase();
    renderPagina();
    expect(await screen.findByText("Carlos Pérez")).toBeInTheDocument();
    expect(screen.getByText("Halcones FC")).toBeInTheDocument();
    expect(screen.getByText("#10")).toBeInTheDocument();
  });

  it("nuevo vínculo para un jugador SIN perfil todavía crea el perfil con la disciplina del torneo, sin preguntarla", async () => {
    mockBase();
    let perfilCreado: unknown = null;
    let vinculoCreado: unknown = null;
    server.use(
      http.get(JUGADORES, () => HttpResponse.json([{ id: 2, nombre: "Jugador Nuevo" }])),
      http.get(PERFILES, () => HttpResponse.json([])), // sin perfil todavía
      http.post(PERFILES, async ({ request }) => {
        perfilCreado = await request.json();
        return HttpResponse.json({ id: 9, jugador_id: 2, disciplina_id: 1 }, { status: 201 });
      }),
      http.post(PLANTILLAS, async ({ request }) => {
        vinculoCreado = await request.json();
        return HttpResponse.json({ id: 2 }, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderPagina();

    await user.click(await screen.findByRole("button", { name: "+ Nuevo vínculo" }));
    // No hay campo de Disciplina en este formulario — la fija el torneo.
    expect(screen.queryByLabelText("Disciplina")).not.toBeInTheDocument();
    await user.selectOptions(await screen.findByLabelText("Jugador"), "2");
    await user.selectOptions(screen.getByLabelText("Equipo"), "5");
    await user.type(screen.getByLabelText("Fecha de inicio"), "2026-02-01");
    await user.click(screen.getByRole("button", { name: "Vincular" }));

    await waitFor(() => expect(perfilCreado).toEqual({ jugador_id: 2, disciplina_id: 1 }));
    expect(vinculoCreado).toMatchObject({ jugador_perfil_id: 9, inscripcion_torneo_id: 5 });
  });

  it("+ Registro por lote navega con alcance de torneo (sin equipo pre-resuelto)", async () => {
    mockBase();
    const user = userEvent.setup();
    renderPagina();

    await user.click(await screen.findByRole("button", { name: "+ Registro por lote" }));

    expect(mockNavigate).toHaveBeenCalledWith("/torneo-admin/plantillas/lote", {
      state: { torneoId: 20, volverA: "/torneo-admin/torneos/20/plantillas" },
    });
  });

  it("dar de baja llama a POST /plantillas/{id}/baja con fecha_fin en la query", async () => {
    mockBase();
    let queryFechaFin: string | null = null;
    server.use(
      http.post(`${PLANTILLAS}/1/baja`, ({ request }) => {
        queryFechaFin = new URL(request.url).searchParams.get("fecha_fin");
        return HttpResponse.json({
          id: 1,
          jugador_perfil_id: 1,
          inscripcion_torneo_id: 5,
          dorsal: 10,
          fecha_inicio: "2026-01-01",
          fecha_fin: "2026-06-01",
          estado: "Inactivo",
        });
      }),
    );
    const user = userEvent.setup();
    renderPagina();
    await screen.findByText("Carlos Pérez");

    await user.click(screen.getByRole("button", { name: "Dar de baja" }));
    await user.type(screen.getByLabelText("Fecha de baja"), "2026-06-01");
    await user.click(screen.getByRole("button", { name: "Confirmar baja" }));

    await waitFor(() => expect(queryFechaFin).toBe("2026-06-01"));
  });
});
