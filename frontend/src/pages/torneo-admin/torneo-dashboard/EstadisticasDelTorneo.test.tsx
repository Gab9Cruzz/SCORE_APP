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
  modalidadId: 1,
  torneoContexto: "Liga Relámpago — Edición 2",
  formato: "Liga",
  incluyeTercerLugar: true,
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

  // T41 (EC-54, motor-formatos-plantillas-navegacion-plan.md): un torneo
  // Grupos_Playoffs separa la tabla de posiciones por grupo, con el
  // nombre del grupo (no el Grupo_ID crudo) como encabezado.
  it("Grupos_Playoffs: separa la tabla de posiciones por grupo", async () => {
    CONTEXTO.formato = "Grupos_Playoffs";
    try {
      server.use(
        http.get(TORNEOS, () => HttpResponse.json([{ id: 20, numero_edicion: 1, estado: "Activo" }])),
        http.get("http://127.0.0.1:8000/api/v1/estadisticas/torneos/20/posiciones", () =>
          HttpResponse.json([
            { equipo_id: 1, equipo: "Tigres", fase_id: 5, grupo_id: 100, pj: 1, pg: 1, pe: 0, pp: 0, gf: 2, gc: 0, dg: 2, pts: 3 },
            { equipo_id: 2, equipo: "Leones", fase_id: 5, grupo_id: 100, pj: 1, pg: 0, pe: 0, pp: 1, gf: 0, gc: 2, dg: -2, pts: 0 },
            { equipo_id: 3, equipo: "Osos", fase_id: 5, grupo_id: 200, pj: 1, pg: 1, pe: 0, pp: 0, gf: 1, gc: 0, dg: 1, pts: 3 },
            { equipo_id: 4, equipo: "Águilas", fase_id: 5, grupo_id: 200, pj: 1, pg: 0, pe: 0, pp: 1, gf: 0, gc: 1, dg: -1, pts: 0 },
          ]),
        ),
        http.get("http://127.0.0.1:8000/api/v1/estadisticas/torneos/20/goleadores", () => HttpResponse.json([])),
        http.get("http://127.0.0.1:8000/api/v1/grupos", () =>
          HttpResponse.json([
            { id: 100, fase_id: 5, nombre: "A" },
            { id: 200, fase_id: 5, nombre: "B" },
          ]),
        ),
      );
      renderPagina();

      expect(await screen.findByText("Grupo A")).toBeInTheDocument();
      expect(screen.getByText("Grupo B")).toBeInTheDocument();
      expect(screen.getByText("Tigres")).toBeInTheDocument();
      expect(screen.getByText("Osos")).toBeInTheDocument();
    } finally {
      CONTEXTO.formato = "Liga";
    }
  });
});
