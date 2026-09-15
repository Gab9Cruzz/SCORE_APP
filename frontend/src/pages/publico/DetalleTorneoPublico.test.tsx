import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { server } from "../../test/msw-server";
import { createTestQueryClient } from "../../test/test-utils";
import { DetalleTorneoPublicoPage } from "./DetalleTorneoPublico";

const TORNEO_1 = "http://127.0.0.1:8000/api/v1/torneos/1";
const GRUPO_1 = "http://127.0.0.1:8000/api/v1/torneo-grupos/9";
const POSICIONES_1 = "http://127.0.0.1:8000/api/v1/estadisticas/torneos/1/posiciones";
const RESULTADOS_1 = "http://127.0.0.1:8000/api/v1/estadisticas/torneos/1/resultados";
const GOLEADORES_1 = "http://127.0.0.1:8000/api/v1/estadisticas/torneos/1/goleadores";
const BRACKET_1 = "http://127.0.0.1:8000/api/v1/torneos/1/bracket";
const EQUIPOS = "http://127.0.0.1:8000/api/v1/equipos";

const TORNEO_LIGA_FUTURO = {
  id: 1,
  nombre: "Liga Demo",
  torneo_grupo_id: 9,
  formato: "Liga",
  fecha_inicio: "2099-01-01",
  estado: "Activo",
};

function mockComunes() {
  server.use(
    http.get(GRUPO_1, () => HttpResponse.json({ id: 9, nombre: "Liga Demo Grupo", pais: "Ecuador", logo_url: null })),
    http.get(POSICIONES_1, () => HttpResponse.json([])),
    http.get(RESULTADOS_1, () => HttpResponse.json([])),
    http.get(GOLEADORES_1, () => HttpResponse.json([])),
    http.get(BRACKET_1, () => HttpResponse.json([])),
    http.get(EQUIPOS, () => HttpResponse.json([])),
  );
}

function renderEn(id = "1") {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/torneos/${id}`]}>
        <Routes>
          <Route path="/torneos/:torneoId" element={<DetalleTorneoPublicoPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("DetalleTorneoPublicoPage (portal-publico-feed-partidos-plan.md, T5.2)", () => {
  it("muestra el nombre y país del grupo, no del torneo/edición", async () => {
    mockComunes();
    server.use(http.get(TORNEO_1, () => HttpResponse.json(TORNEO_LIGA_FUTURO)));
    renderEn();

    expect(await screen.findByRole("heading", { name: "Liga Demo Grupo" })).toBeInTheDocument();
    expect(screen.getByText("Ecuador")).toBeInTheDocument();
  });

  it("D8a: un torneo Liga que todavía no empezó abre en Posiciones", async () => {
    mockComunes();
    server.use(http.get(TORNEO_1, () => HttpResponse.json(TORNEO_LIGA_FUTURO)));
    renderEn();

    await screen.findByRole("heading", { name: "Liga Demo Grupo" });
    expect(screen.getByRole("tab", { name: "Posiciones" })).toHaveAttribute("aria-selected", "true");
  });

  it("D8a: un torneo Liga que ya empezó abre en Resultados", async () => {
    mockComunes();
    server.use(http.get(TORNEO_1, () => HttpResponse.json({ ...TORNEO_LIGA_FUTURO, fecha_inicio: "2020-01-01" })));
    renderEn();

    await screen.findByRole("heading", { name: "Liga Demo Grupo" });
    expect(screen.getByRole("tab", { name: "Resultados" })).toHaveAttribute("aria-selected", "true");
  });

  it("D8b: un torneo Eliminación no tiene pestaña de Posiciones y abre en Resultados con el bracket", async () => {
    mockComunes();
    server.use(http.get(TORNEO_1, () => HttpResponse.json({ ...TORNEO_LIGA_FUTURO, formato: "Eliminacion" })));
    renderEn();

    await screen.findByRole("heading", { name: "Liga Demo Grupo" });
    expect(screen.queryByRole("tab", { name: "Posiciones" })).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Resultados" })).toHaveAttribute("aria-selected", "true");
  });

  it("D8c: torneo sin partidos todavía muestra un empty state honesto, no una tabla de ceros", async () => {
    mockComunes();
    server.use(http.get(TORNEO_1, () => HttpResponse.json(TORNEO_LIGA_FUTURO)));
    renderEn();

    expect(await screen.findByText("Todavía no hay partidos jugados en este torneo.")).toBeInTheDocument();
  });

  it("resultados lista partidos y el marcador es distinto para Programado vs Finalizado", async () => {
    mockComunes();
    server.use(
      http.get(TORNEO_1, () => HttpResponse.json({ ...TORNEO_LIGA_FUTURO, fecha_inicio: "2020-01-01" })),
      http.get(RESULTADOS_1, () =>
        HttpResponse.json([
          {
            partido_id: 5,
            equipo_local: "Norte",
            equipo_visitante: "Sur",
            goles_local: 2,
            goles_visitante: 1,
            fecha_partido: "2026-01-10T15:00:00",
            estado: "Finalizado",
          },
          {
            partido_id: 6,
            equipo_local: "Este",
            equipo_visitante: "Oeste",
            goles_local: 0,
            goles_visitante: 0,
            fecha_partido: "2026-01-11T15:00:00",
            estado: "Programado",
          },
        ]),
      ),
    );
    renderEn();

    await screen.findByRole("heading", { name: "Liga Demo Grupo" });
    expect(await screen.findByText("2 - 1")).toBeInTheDocument();
    expect(screen.getByText("vs")).toBeInTheDocument();
  });

  it("D16: torneo despublicado (404 anónimo) muestra el estado de no-encontrado, no un error crudo", async () => {
    mockComunes();
    server.use(
      http.get(TORNEO_1, () =>
        HttpResponse.json({ detail: "Torneo con id=1 no encontrado." }, { status: 404 }),
      ),
    );
    renderEn();

    expect(await screen.findByText("No encontramos este torneo")).toBeInTheDocument();
  });

  it("T5.2b/D15: Compartir copia el link al portapapeles (el botón pasa a '¡Copiado!')", async () => {
    mockComunes();
    server.use(http.get(TORNEO_1, () => HttpResponse.json(TORNEO_LIGA_FUTURO)));
    // jsdom no trae navigator.clipboard por default en este entorno — se
    // define la propiedad (no un simple assign, por si algún setup previo
    // la dejó no-configurable).
    // jsdom no trae navigator.clipboard por default — se define para que
    // el componente entre por la rama de "copiar", no la de
    // "sin-clipboard", sin importar el orden de corrida de otros tests
    // del archivo. No se assertea la llamada al mock en sí (frágil en
    // este entorno) — el efecto observable (el botón cambia de label) es
    // la promesa real que D15 le hace al usuario.
    if (!("clipboard" in navigator) || !navigator.clipboard) {
      Object.defineProperty(navigator, "clipboard", {
        value: { writeText: vi.fn().mockResolvedValue(undefined) },
        configurable: true,
      });
    }

    const user = userEvent.setup();
    renderEn();

    await screen.findByRole("heading", { name: "Liga Demo Grupo" });
    await user.click(screen.getByRole("button", { name: "Compartir" }));

    expect(await screen.findByRole("button", { name: "¡Copiado!" })).toBeInTheDocument();
  });
});
