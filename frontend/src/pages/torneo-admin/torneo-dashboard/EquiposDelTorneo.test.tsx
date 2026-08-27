import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { server } from "../../../test/msw-server";
import { createWrapper } from "../../../test/test-utils";
import { EquiposDelTorneoPage } from "./EquiposDelTorneo";
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

const INSCRIPCIONES = "http://127.0.0.1:8000/api/v1/inscripciones";
const EQUIPOS = "http://127.0.0.1:8000/api/v1/equipos";
const PLANTILLAS = "http://127.0.0.1:8000/api/v1/plantillas";

function renderPagina() {
  const Wrapper = createWrapper();
  return render(
    <Wrapper>
      <EquiposDelTorneoPage />
    </Wrapper>,
  );
}

describe("EquiposDelTorneoPage", () => {
  it("lista equipos inscritos con la cantidad de jugadores activos", async () => {
    server.use(
      http.get(INSCRIPCIONES, () => HttpResponse.json([{ id: 1, torneo_id: 20, equipo_id: 1, estado: "Inscrito" }])),
      http.get(EQUIPOS, () => HttpResponse.json([{ id: 1, nombre: "Halcones FC" }])),
      http.get(PLANTILLAS, () =>
        HttpResponse.json([
          { id: 1, inscripcion_torneo_id: 1, estado: "Activo" },
          { id: 2, inscripcion_torneo_id: 1, estado: "Activo" },
          { id: 3, inscripcion_torneo_id: 1, estado: "Traspasado" },
        ]),
      ),
    );
    renderPagina();

    expect(await screen.findByText("Halcones FC")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument(); // solo cuenta Activo
  });

  // Fase 3 del plan: reemplaza a la extinta pestaña global Inscripciones —
  // "Cancelar inscripción" es el mismo PATCH {estado: "Cancelado"} directo.
  it("Cancelar inscripción manda PATCH {estado: Cancelado}", async () => {
    server.use(
      http.get(INSCRIPCIONES, () => HttpResponse.json([{ id: 1, torneo_id: 20, equipo_id: 1, estado: "Inscrito" }])),
      http.get(EQUIPOS, () => HttpResponse.json([{ id: 1, nombre: "Halcones FC" }])),
      http.get(PLANTILLAS, () => HttpResponse.json([])),
    );
    let bodyRecibido: unknown;
    server.use(
      http.patch(`${INSCRIPCIONES}/1`, async ({ request }) => {
        bodyRecibido = await request.json();
        return HttpResponse.json({ id: 1, torneo_id: 20, equipo_id: 1, estado: "Cancelado" });
      }),
    );
    const user = userEvent.setup();
    renderPagina();

    await user.click(await screen.findByRole("button", { name: "Cancelar inscripción" }));

    await waitFor(() => expect(bodyRecibido).toEqual({ estado: "Cancelado" }));
  });

  it("+ Agregar jugadores navega al registro por lote con el equipo ya resuelto", async () => {
    server.use(
      http.get(INSCRIPCIONES, () => HttpResponse.json([{ id: 1, torneo_id: 20, equipo_id: 1, estado: "Inscrito" }])),
      http.get(EQUIPOS, () => HttpResponse.json([{ id: 1, nombre: "Halcones FC" }])),
      http.get(PLANTILLAS, () => HttpResponse.json([])),
    );
    const user = userEvent.setup();
    renderPagina();

    await user.click(await screen.findByRole("button", { name: "+ Agregar jugadores" }));

    expect(mockNavigate).toHaveBeenCalledWith("/torneo-admin/plantillas/lote", {
      state: {
        inscripcionTorneoId: 1,
        contexto: "Halcones FC — Liga Relámpago — Edición 2",
        volverA: "/torneo-admin/torneos/20/equipos",
      },
    });
  });
});
