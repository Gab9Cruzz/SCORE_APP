import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { server } from "../../../test/msw-server";
import { createWrapper } from "../../../test/test-utils";
import { EstadisticasDelTorneoPage } from "./EstadisticasDelTorneo";
import type { TorneoDashboardContext } from "./TorneoDashboard";

const CONTEXTO: TorneoDashboardContext = {
  torneoId: 20,
  torneoGrupoId: 7,
  disciplinaId: 1,
  modalidadId: null,
  torneoContexto: "Liga Relámpago — Edición 2",
};

const mockSetSearchParams = vi.fn();
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return {
    ...actual,
    useOutletContext: () => CONTEXTO,
    useSearchParams: () => [new URLSearchParams(), mockSetSearchParams],
  };
});

const TORNEOS = "http://127.0.0.1:8000/api/v1/torneos";

function renderPagina() {
  const Wrapper = createWrapper();
  return render(
    <Wrapper>
      <EstadisticasDelTorneoPage />
    </Wrapper>,
  );
}

describe("EstadisticasDelTorneoPage", () => {
  it("carga posiciones y goleadores de la edición actual (torneoId del contexto)", async () => {
    server.use(
      http.get(TORNEOS, () =>
        HttpResponse.json([
          { id: 10, numero_edicion: 1, estado: "Finalizado" },
          { id: 20, numero_edicion: 2, estado: "Activo" },
        ]),
      ),
      http.get("http://127.0.0.1:8000/api/v1/estadisticas/torneos/20/posiciones", () =>
        HttpResponse.json([{ equipo_id: 1, equipo: "Halcones FC", pj: 1, pg: 1, pe: 0, pp: 0, gf: 3, gc: 1, dg: 2, pts: 3 }]),
      ),
      http.get("http://127.0.0.1:8000/api/v1/estadisticas/torneos/20/goleadores", () =>
        HttpResponse.json([{ jugador_id: 1, jugador: "Micky", equipo: "Halcones FC", goles: 2 }]),
      ),
    );
    renderPagina();

    expect(await screen.findAllByText("Halcones FC")).toHaveLength(2); // tabla de posiciones + goleadores
    expect(screen.getByText("Micky")).toBeInTheDocument();
    // El selector abre en la edición del dashboard, no en cualquiera.
    expect(screen.getByRole("combobox", { name: "Edición:" })).toHaveValue("20");
  });

  it("cambiar de edición en el selector refetcha con el torneo_id elegido", async () => {
    server.use(
      http.get(TORNEOS, () =>
        HttpResponse.json([
          { id: 10, numero_edicion: 1, estado: "Finalizado" },
          { id: 20, numero_edicion: 2, estado: "Activo" },
        ]),
      ),
      http.get("http://127.0.0.1:8000/api/v1/estadisticas/torneos/20/posiciones", () => HttpResponse.json([])),
      http.get("http://127.0.0.1:8000/api/v1/estadisticas/torneos/20/goleadores", () => HttpResponse.json([])),
      http.get("http://127.0.0.1:8000/api/v1/estadisticas/torneos/10/posiciones", () =>
        HttpResponse.json([{ equipo_id: 1, equipo: "Halcones FC (Ed. 1)", pj: 5, pg: 3, pe: 1, pp: 1, gf: 10, gc: 5, dg: 5, pts: 10 }]),
      ),
      http.get("http://127.0.0.1:8000/api/v1/estadisticas/torneos/10/goleadores", () => HttpResponse.json([])),
    );
    const user = userEvent.setup();
    renderPagina();

    await screen.findByRole("option", { name: "Edición 1 (finalizado)" });
    await user.selectOptions(screen.getByRole("combobox", { name: "Edición:" }), "10");

    expect(await screen.findByText("Halcones FC (Ed. 1)")).toBeInTheDocument();
  });
});
