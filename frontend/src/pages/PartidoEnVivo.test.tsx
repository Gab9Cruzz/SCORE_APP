import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { server } from "../test/msw-server";
import { createTestQueryClient } from "../test/test-utils";
import { PartidoEnVivoPage } from "./PartidoEnVivo";

const PARTIDO_1 = "http://127.0.0.1:8000/api/v1/partidos/1";
const RESULTADOS_1 = "http://127.0.0.1:8000/api/v1/estadisticas/torneos/1/resultados";
const EVENTOS_PARTIDO = "http://127.0.0.1:8000/api/v1/eventos-partido";
const JUGADORES = "http://127.0.0.1:8000/api/v1/jugadores";
const EVENTOS = "http://127.0.0.1:8000/api/v1/eventos";
const CONVOCADOS_1 = "http://127.0.0.1:8000/api/v1/partidos/1/convocados";
const PLANTILLA_1 = "http://127.0.0.1:8000/api/v1/estadisticas/equipos/1/plantilla";
const PLANTILLA_2 = "http://127.0.0.1:8000/api/v1/estadisticas/equipos/2/plantilla";
const TORNEO_1 = "http://127.0.0.1:8000/api/v1/torneos/1";
const GRUPO_9 = "http://127.0.0.1:8000/api/v1/torneo-grupos/9";

const PARTIDO = {
  id: 1,
  torneo_id: 1,
  estado: "Finalizado",
  equipos_id_local: 1,
  equipos_id_visitante: 2,
  fecha_partido: "2026-01-15T16:00:00",
};

function mockBase() {
  server.use(
    http.get(PARTIDO_1, () => HttpResponse.json(PARTIDO)),
    http.get(RESULTADOS_1, () =>
      HttpResponse.json([
        { partido_id: 1, equipo_local: "Tiburones FC", equipo_visitante: "Águilas del Sur", goles_local: 2, goles_visitante: 1 },
      ]),
    ),
    http.get(EVENTOS_PARTIDO, () => HttpResponse.json([])),
    http.get(JUGADORES, () => HttpResponse.json([])),
    http.get(EVENTOS, () => HttpResponse.json([])),
    http.get(CONVOCADOS_1, () => HttpResponse.json([])),
    http.get(PLANTILLA_1, () =>
      HttpResponse.json([
        { jugador_id: 5, jugador: "Andrés Vera", equipo_id: 1, equipo: "Tiburones FC", dorsal: 9, jugador_perfil_id: 50 },
        { jugador_id: 6, jugador: "Bruno Ibarra", equipo_id: 1, equipo: "Tiburones FC", dorsal: 4, jugador_perfil_id: 51 },
      ]),
    ),
    http.get(PLANTILLA_2, () =>
      HttpResponse.json([{ jugador_id: 3, jugador: "Mateo Salcedo", equipo_id: 2, equipo: "Águilas del Sur", dorsal: 9, jugador_perfil_id: 30 }]),
    ),
    http.get(TORNEO_1, () => HttpResponse.json({ id: 1, torneo_grupo_id: 9 })),
    http.get(GRUPO_9, () => HttpResponse.json({ nombre: "Liga Demo", pais: "Ecuador" })),
  );
}

/** Ambas rutas montan el MISMO componente (control-mesa-centralizacion-
 * fixture-plan.md, ítem 5) — este helper monta con la ruta que cada test
 * necesite probar, sin duplicar la config de rutas de App.tsx. */
function renderEn(path: string, ruta: string) {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={ruta} element={<PartidoEnVivoPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("PartidoEnVivoPage — generalizada a Detalle del Partido (control-mesa-centralizacion-fixture-plan.md, ítem 5)", () => {
  it("la ruta vieja /partido/:id/en-vivo sigue funcionando (Dashboard.tsx la linkea así)", async () => {
    mockBase();
    renderEn("/partido/1/en-vivo", "/partido/:partidoId/en-vivo");
    expect(await screen.findByText("2 - 1")).toBeInTheDocument();
  });

  it("la ruta nueva /partidos/:id monta la misma página", async () => {
    mockBase();
    renderEn("/partidos/1", "/partidos/:partidoId");
    expect(await screen.findByText("2 - 1")).toBeInTheDocument();
  });

  it("sin convocatoria guardada, muestra toda la plantilla sin separar titulares/suplentes (mismo fallback que MesaPanel)", async () => {
    mockBase();
    renderEn("/partidos/1", "/partidos/:partidoId");

    expect(await screen.findByText("Alineaciones")).toBeInTheDocument();
    expect(screen.getByText(/Sin convocatoria guardada/)).toBeInTheDocument();
    expect(await screen.findByText(/Andrés Vera/)).toBeInTheDocument();
    expect(await screen.findByText(/Mateo Salcedo/)).toBeInTheDocument();
    expect(screen.queryByText("Titulares")).not.toBeInTheDocument();
  });

  it("con convocatoria guardada, separa titulares y suplentes por equipo", async () => {
    mockBase();
    server.use(
      http.get(CONVOCADOS_1, () =>
        HttpResponse.json([
          { jugador_perfil_id: 50, titular: true },
          { jugador_perfil_id: 51, titular: false },
          { jugador_perfil_id: 30, titular: true },
        ]),
      ),
    );
    renderEn("/partidos/1", "/partidos/:partidoId");

    await screen.findByText("Alineaciones");
    await screen.findByText(/Andrés Vera/);
    expect(screen.queryByText(/Sin convocatoria guardada/)).not.toBeInTheDocument();
    const titulares = screen.getAllByText("Titulares");
    expect(titulares.length).toBe(2); // una lista por equipo
    expect(screen.getByText("Suplentes")).toBeInTheDocument();
    expect(screen.getByText(/Bruno Ibarra/)).toBeInTheDocument();
  });

  it("el timeline muestra nombre de equipo en todo hito y formato Sale/Entra en Cambio (control-mesa-reactividad-playoffs-plan.md, Fase 1/2)", async () => {
    mockBase();
    server.use(
      http.get(JUGADORES, () =>
        HttpResponse.json([
          { id: 5, nombre: "Andrés Vera" },
          { id: 6, nombre: "Bruno Ibarra" },
        ]),
      ),
      http.get(EVENTOS, () =>
        HttpResponse.json([
          { id: 1, nombre: "Gol", estado: "Activo" },
          { id: 5, nombre: "Cambio", estado: "Activo" },
        ]),
      ),
      http.get(EVENTOS_PARTIDO, () =>
        HttpResponse.json([
          { id: 1, partidos_id: 1, jugador_id: 5, equipo_id: 1, eventos_id: 1, jugador_id_entra: null, minuto: 10, estado: "Registrado" },
          { id: 2, partidos_id: 1, jugador_id: 5, equipo_id: 1, eventos_id: 5, jugador_id_entra: 6, minuto: 62, estado: "Registrado" },
        ]),
      ),
    );
    renderEn("/partidos/1", "/partidos/:partidoId");
    await screen.findByText("2 - 1"); // espera a que resultadosQuery resuelva (nombres de equipo)

    const filaGol = (await screen.findByText("10'")).closest("li")!;
    expect(within(filaGol).getByText("Tiburones FC")).toBeInTheDocument();
    expect(within(filaGol).getByText(/Andrés Vera/)).toBeInTheDocument();

    const filaCambio = (await screen.findByText("62'")).closest("li")!;
    expect(within(filaCambio).getByText("Tiburones FC")).toBeInTheDocument();
    expect(within(filaCambio).getByText(/Sale:.*Andrés Vera/)).toBeInTheDocument();
    expect(within(filaCambio).getByText(/Entra:.*Bruno Ibarra/)).toBeInTheDocument();
  });

  // --- D7 (portal-publico-feed-partidos-plan.md): identidad y salida ---

  it("D7: la cabecera enlaza al torneo con nombre y país", async () => {
    mockBase();
    renderEn("/partidos/1", "/partidos/:partidoId");

    const link = await screen.findByRole("link", { name: /Liga Demo/ });
    expect(link).toHaveAttribute("href", "/torneos/1");
    expect(screen.getByText(/Ecuador/)).toBeInTheDocument();
  });

  it("D7/C17(b): torneo despublicado (404 en resultados) muestra el aviso explícito, no el marcador '- : -' como si fuera real", async () => {
    mockBase();
    server.use(
      http.get(RESULTADOS_1, () => HttpResponse.json({ detail: "Torneo con id=1 no encontrado." }, { status: 404 })),
      http.get(TORNEO_1, () => HttpResponse.json({ detail: "Torneo con id=1 no encontrado." }, { status: 404 })),
    );
    renderEn("/partidos/1", "/partidos/:partidoId");

    expect(await screen.findByText("Resultados no disponibles para este torneo.")).toBeInTheDocument();
    // Sin cabecera de torneo (el mismo 404 la tapa) y sin el "- : -" que
    // D7 identificó como el problema: el marcador queda como Local/Visitante
    // por el otro fallback existente, pero el aviso explícito es lo que
    // distingue "no hay resultado todavía" de "no podés ver este torneo".
    expect(screen.queryByRole("link", { name: /Liga Demo/ })).not.toBeInTheDocument();
  });
});
