import { render, screen, waitFor, within } from "@testing-library/react";
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

  it("avisa cuando goleadores llega al techo del backend (3A-5, límite=50 distinto de LIMITE_LISTA)", async () => {
    server.use(
      http.get(TORNEOS, () => HttpResponse.json([{ id: 20, numero_edicion: 2, estado: "Activo" }])),
      http.get("http://127.0.0.1:8000/api/v1/estadisticas/torneos/20/posiciones", () => HttpResponse.json([])),
      http.get("http://127.0.0.1:8000/api/v1/estadisticas/torneos/20/goleadores", () =>
        HttpResponse.json(
          Array.from({ length: 50 }, (_, i) => ({
            jugador_id: i + 1,
            jugador: `Goleador ${i + 1}`,
            equipo: "Halcones FC",
            goles: 1,
          })),
        ),
      ),
    );
    renderPagina();

    expect(await screen.findByText(/Mostrando los primeros 50 goleadores/)).toBeInTheDocument();
  });

  describe("desempate manual (3A-12, EC-51)", () => {
    const POSICIONES = "http://127.0.0.1:8000/api/v1/estadisticas/torneos/20/posiciones";

    // Tigres/Leones empatados (3pts/0dg/1gf cada uno); Osos claramente
    // primero (6pts) — ni Tigres ni Leones tienen orden_manual todavía.
    const FILAS_EMPATADAS = [
      { equipo_id: 3, equipo: "Osos", fase_id: 5, grupo_id: 100, pj: 2, pg: 2, pe: 0, pp: 0, gf: 3, gc: 0, dg: 3, pts: 6, grupo_equipo_id: 300, orden_manual: null },
      { equipo_id: 1, equipo: "Tigres", fase_id: 5, grupo_id: 100, pj: 1, pg: 1, pe: 0, pp: 0, gf: 1, gc: 0, dg: 1, pts: 3, grupo_equipo_id: 100, orden_manual: null },
      { equipo_id: 2, equipo: "Leones", fase_id: 5, grupo_id: 100, pj: 1, pg: 1, pe: 0, pp: 0, gf: 1, gc: 0, dg: 1, pts: 3, grupo_equipo_id: 200, orden_manual: null },
    ];

    function montarConEmpate() {
      CONTEXTO.formato = "Grupos_Playoffs";
      server.use(
        http.get(TORNEOS, () => HttpResponse.json([{ id: 20, numero_edicion: 1, estado: "Activo" }])),
        http.get(POSICIONES, () => HttpResponse.json(FILAS_EMPATADAS)),
        http.get("http://127.0.0.1:8000/api/v1/estadisticas/torneos/20/goleadores", () => HttpResponse.json([])),
        http.get("http://127.0.0.1:8000/api/v1/grupos", () =>
          HttpResponse.json([{ id: 100, fase_id: 5, nombre: "A" }]),
        ),
      );
      return renderPagina();
    }

    it("ofrece 'Definir manualmente' solo a los equipos empatados, no al líder claro", async () => {
      try {
        montarConEmpate();
        await screen.findByText("Tigres");

        const filaOsos = screen.getByText("Osos").closest("tr") as HTMLElement;
        const filaTigres = screen.getByText("Tigres").closest("tr") as HTMLElement;
        const filaLeones = screen.getByText("Leones").closest("tr") as HTMLElement;

        expect(within(filaOsos).queryByRole("button", { name: /Definir manualmente/ })).not.toBeInTheDocument();
        expect(within(filaTigres).getByRole("button", { name: "Definir manualmente" })).toBeInTheDocument();
        expect(within(filaLeones).getByRole("button", { name: "Definir manualmente" })).toBeInTheDocument();
      } finally {
        CONTEXTO.formato = "Liga";
      }
    });

    it("guardar un orden manual manda el PATCH correcto y refresca la tabla", async () => {
      try {
        montarConEmpate();
        const user = userEvent.setup();
        await screen.findByText("Tigres");

        let cuerpoRecibido: unknown;
        server.use(
          http.patch("http://127.0.0.1:8000/api/v1/grupos/equipos/200", async ({ request }) => {
            cuerpoRecibido = await request.json();
            return HttpResponse.json({ id: 200, grupo_id: 100, inscripcion_torneo_id: 9, orden_manual: 1, fecha_registro: "2026-01-01T00:00:00" });
          }),
        );

        const filaLeones = screen.getByText("Leones").closest("tr") as HTMLElement;
        await user.click(within(filaLeones).getByRole("button", { name: "Definir manualmente" }));
        await user.type(within(filaLeones).getByLabelText("Orden manual"), "1");
        await user.click(within(filaLeones).getByRole("button", { name: "Guardar" }));

        await waitFor(() => expect(cuerpoRecibido).toEqual({ orden_manual: 1 }));
      } finally {
        CONTEXTO.formato = "Liga";
      }
    });

    it("'Quitar' manda orden_manual null, no omite el campo", async () => {
      try {
        CONTEXTO.formato = "Grupos_Playoffs";
        server.use(
          http.get(TORNEOS, () => HttpResponse.json([{ id: 20, numero_edicion: 1, estado: "Activo" }])),
          http.get(POSICIONES, () =>
            HttpResponse.json([
              { ...FILAS_EMPATADAS[1], orden_manual: 2 },
              { ...FILAS_EMPATADAS[2], orden_manual: 1 },
            ]),
          ),
          http.get("http://127.0.0.1:8000/api/v1/estadisticas/torneos/20/goleadores", () => HttpResponse.json([])),
          http.get("http://127.0.0.1:8000/api/v1/grupos", () =>
            HttpResponse.json([{ id: 100, fase_id: 5, nombre: "A" }]),
          ),
        );
        const user = userEvent.setup();
        renderPagina();
        await screen.findByText("Tigres");

        let cuerpoRecibido: unknown;
        server.use(
          http.patch("http://127.0.0.1:8000/api/v1/grupos/equipos/200", async ({ request }) => {
            cuerpoRecibido = await request.json();
            return HttpResponse.json({ id: 200, grupo_id: 100, inscripcion_torneo_id: 9, orden_manual: null, fecha_registro: "2026-01-01T00:00:00" });
          }),
        );

        const filaLeones = screen.getByText("Leones").closest("tr") as HTMLElement;
        // Ya tiene orden_manual=1 → el botón muestra el valor, no el texto genérico.
        await user.click(within(filaLeones).getByRole("button", { name: "#1 ✏️" }));
        await user.click(within(filaLeones).getByRole("button", { name: "Quitar" }));

        await waitFor(() => expect(cuerpoRecibido).toEqual({ orden_manual: null }));
      } finally {
        CONTEXTO.formato = "Liga";
      }
    });
  });
});
