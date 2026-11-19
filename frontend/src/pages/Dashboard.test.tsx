import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "../test/msw-server";
import { createWrapper } from "../test/test-utils";
import { DashboardPage } from "./Dashboard";

// TASK-047: Dashboard no tenía prueba propia (31 % de líneas): solo se
// montaba de pasada en App.routing.test.

const API = "http://127.0.0.1:8000/api/v1";

function posicion(torneo_id: number, equipo_id: number, equipo: string, pts: number) {
  return { torneo_id, equipo_id, equipo, pj: 2, pg: pts / 3, pe: 0, pp: 2 - pts / 3, gf: 3, gc: 1, dg: 2, pts };
}

function sembrar() {
  server.use(
    http.get(`${API}/torneos`, () =>
      HttpResponse.json([
        { id: 1, nombre: "Liga Norte", estado: "Activo" },
        { id: 2, nombre: "Copa Sur", estado: "Activo" },
      ]),
    ),
    http.get(`${API}/estadisticas/torneos/:id/posiciones`, ({ params }) =>
      HttpResponse.json(
        params.id === "1"
          ? [posicion(1, 10, "Halcones", 6), posicion(1, 11, "Pumas", 0)]
          : [posicion(2, 20, "Cóndores", 3)],
      ),
    ),
    http.get(`${API}/estadisticas/torneos/:id/goleadores`, ({ params }) =>
      HttpResponse.json(
        params.id === "1" ? [{ torneo_id: 1, jugador_id: 5, jugador: "Ana Ruiz", equipo_id: 10, equipo: "Halcones", goles: 4 }] : [],
      ),
    ),
    http.get(`${API}/estadisticas/proximos-partidos`, ({ request }) =>
      HttpResponse.json(
        new URL(request.url).searchParams.get("torneo_id") === "1"
          ? [
              {
                partido_id: 7,
                torneo_id: 1,
                torneo: "Liga Norte",
                equipo_local_id: 10,
                equipo_local: "Halcones",
                equipo_visitante_id: 11,
                equipo_visitante: "Pumas",
                fecha_partido: "2026-12-05T16:00:00",
                jornada: 3,
                fase: "Liga",
                grupo: null,
                estado: "Programado",
              },
            ]
          : [],
      ),
    ),
  );
}

function renderDashboard() {
  const Wrapper = createWrapper();
  return render(
    <Wrapper>
      <DashboardPage />
    </Wrapper>,
  );
}

describe("DashboardPage", () => {
  it("muestra tabla, goleadores y próximos partidos del primer torneo activo", async () => {
    sembrar();
    renderDashboard();

    const tabla = await screen.findByRole("region", { name: "Tabla de posiciones" });
    expect(await within(tabla).findByRole("row", { name: /Halcones .* 6$/ })).toBeInTheDocument();
    expect(await screen.findByText("Ana Ruiz")).toBeInTheDocument();
    expect(await screen.findByText(/Jornada 3/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ver en vivo →" })).toHaveAttribute("href", "/partido/7/en-vivo");
  });

  it("al elegir otro torneo cambia todo el tablero, con los vacíos explicados", async () => {
    sembrar();
    const user = userEvent.setup();
    renderDashboard();
    await screen.findByText("Ana Ruiz");

    await user.selectOptions(screen.getByLabelText("Torneo:"), "2");

    expect(await screen.findByRole("row", { name: /Cóndores/ })).toBeInTheDocument();
    expect(await screen.findByText("Todavía no hay goles cargados.")).toBeInTheDocument();
    expect(await screen.findByText("No hay partidos programados.")).toBeInTheDocument();
    expect(screen.queryByText("Halcones")).not.toBeInTheDocument();
  });

  it("sin torneos activos lo dice y no arma el tablero", async () => {
    server.use(http.get(`${API}/torneos`, () => HttpResponse.json([])));
    renderDashboard();
    expect(await screen.findByText("No hay torneos activos todavía.")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Goleadores" })).not.toBeInTheDocument();
  });

  it("un error del servidor se informa en cada sección, sin romper la página", async () => {
    sembrar();
    server.use(
      http.get(`${API}/estadisticas/torneos/:id/posiciones`, () => HttpResponse.json({ detail: "x" }, { status: 500 })),
      http.get(`${API}/estadisticas/torneos/:id/goleadores`, () => HttpResponse.json({ detail: "x" }, { status: 500 })),
    );
    renderDashboard();
    expect(await screen.findByText("No se pudieron cargar los goleadores.")).toBeInTheDocument();
    expect(await screen.findByText("No se pudo cargar la tabla.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Próximos partidos" })).toBeInTheDocument();
  });

  it("si fallan los torneos, lo informa", async () => {
    server.use(http.get(`${API}/torneos`, () => HttpResponse.json({ detail: "x" }, { status: 500 })));
    renderDashboard();
    expect(await screen.findByText("No se pudieron cargar los torneos.")).toBeInTheDocument();
  });
});
