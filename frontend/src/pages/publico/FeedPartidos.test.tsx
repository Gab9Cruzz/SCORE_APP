import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { server } from "../../test/msw-server";
import { createTestQueryClient } from "../../test/test-utils";
import { FeedPartidosPage } from "./FeedPartidos";

const FEED = "http://127.0.0.1:8000/api/v1/partidos/feed";

function partido(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    partido_id: 1,
    torneo: { id: 10, nombre: "Liga Demo", grupo: "Liga Demo", pais: "Ecuador", logo_url: null },
    disciplina_id: 1,
    disciplina: "Fútbol",
    local: { id: 1, nombre: "Norte", logo_url: null, goles: 0 },
    visitante: { id: 2, nombre: "Sur", logo_url: null, goles: 0 },
    fecha_partido: "2026-09-15T20:00:00",
    estado: "Programado",
    ...overrides,
  };
}

function renderFeed(initialPath = "/") {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/" element={<FeedPartidosPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("FeedPartidosPage (portal-publico-feed-partidos-plan.md, T4.1-T4.7)", () => {
  it("T4.4: agrupa las filas planas por torneo preservando el orden del backend", async () => {
    server.use(
      http.get(FEED, () =>
        HttpResponse.json({
          fecha_pedida: "2026-09-15",
          fecha_efectiva: "2026-09-15",
          total_disponible: 3,
          partidos: [
            partido({ partido_id: 1, torneo: { id: 10, nombre: "Liga A", grupo: "Liga A", pais: null, logo_url: null } }),
            partido({ partido_id: 2, torneo: { id: 10, nombre: "Liga A", grupo: "Liga A", pais: null, logo_url: null } }),
            partido({ partido_id: 3, torneo: { id: 20, nombre: "Liga B", grupo: "Liga B", pais: null, logo_url: null } }),
          ],
        }),
      ),
    );
    renderFeed();

    const bloques = await screen.findAllByRole("link", { name: /Liga (A|B)/ });
    // El nombre accesible ignora el `aria-hidden` del escudo de iniciales
    // (Escudo cae a iniciales sin logo_url) — solo importa el orden.
    expect(bloques.map((b) => b.textContent?.replace(/^L[AB]/, ""))).toEqual(["Liga A", "Liga B"]);
    // 2 partidos dentro del bloque de Liga A.
    const linksPartido = screen.getAllByRole("link").filter((l) => l.getAttribute("href")?.startsWith("/partidos/"));
    expect(linksPartido).toHaveLength(3);
  });

  it("D2: Programado muestra la hora sin marcador", async () => {
    server.use(
      http.get(FEED, () =>
        HttpResponse.json({
          fecha_pedida: "2026-09-15", fecha_efectiva: "2026-09-15", total_disponible: 1,
          partidos: [partido({ estado: "Programado", fecha_partido: "2026-09-15T20:30:00" })],
        }),
      ),
    );
    renderFeed();
    const fila = (await screen.findByText("Norte")).closest("a")!;
    expect(within(fila).getByText("20:30")).toBeInTheDocument();
    expect(within(fila).getByText("—")).toBeInTheDocument();
  });

  it("D2: En curso muestra el indicador EN VIVO y el marcador", async () => {
    server.use(
      http.get(FEED, () =>
        HttpResponse.json({
          fecha_pedida: "2026-09-15", fecha_efectiva: "2026-09-15", total_disponible: 1,
          partidos: [partido({ estado: "En curso", local: { id: 1, nombre: "Norte", logo_url: null, goles: 2 }, visitante: { id: 2, nombre: "Sur", logo_url: null, goles: 1 } })],
        }),
      ),
    );
    renderFeed();
    const fila = (await screen.findByText("Norte")).closest("a")!;
    expect(within(fila).getByText("EN VIVO")).toBeInTheDocument();
    expect(within(fila).getByText("2")).toBeInTheDocument();
    expect(within(fila).getByText("1")).toBeInTheDocument();
  });

  it("D2: Finalizado muestra FIN y el marcador atenuado", async () => {
    server.use(
      http.get(FEED, () =>
        HttpResponse.json({
          fecha_pedida: "2026-09-15", fecha_efectiva: "2026-09-15", total_disponible: 1,
          partidos: [partido({ estado: "Finalizado", local: { id: 1, nombre: "Norte", logo_url: null, goles: 3 }, visitante: { id: 2, nombre: "Sur", logo_url: null, goles: 0 } })],
        }),
      ),
    );
    renderFeed();
    const fila = (await screen.findByText("Norte")).closest("a")!;
    expect(within(fila).getByText("FIN")).toBeInTheDocument();
    expect(fila.className).toContain("fila-partido--finalizado");
  });

  it("Escudo cae a iniciales cuando no hay logo_url", async () => {
    server.use(
      http.get(FEED, () =>
        HttpResponse.json({
          fecha_pedida: "2026-09-15", fecha_efectiva: "2026-09-15", total_disponible: 1,
          partidos: [partido()],
        }),
      ),
    );
    renderFeed();
    await screen.findByText("Norte");
    // Sin logo_url, Escudo renderiza un <div> con iniciales, no un <img>.
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("D8c/D10: empty state por disciplina cuando no hay partidos", async () => {
    server.use(
      http.get(FEED, () =>
        HttpResponse.json({ fecha_pedida: "2026-09-15", fecha_efectiva: "2026-09-15", total_disponible: 0, partidos: [] }),
      ),
    );
    renderFeed("/?deporte=tenis");
    expect(await screen.findByText(/No hay partidos de Tenis esta semana/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ver todos los deportes" })).toBeInTheDocument();
  });

  it("empty state genérico sin filtro de disciplina", async () => {
    server.use(
      http.get(FEED, () =>
        HttpResponse.json({ fecha_pedida: "2026-09-15", fecha_efectiva: "2026-09-15", total_disponible: 0, partidos: [] }),
      ),
    );
    renderFeed();
    expect(await screen.findByText("No hay partidos programados esta semana.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ver todos los deportes" })).not.toBeInTheDocument();
  });

  it("D4/F7: pie de truncado cuando total_disponible supera lo devuelto", async () => {
    server.use(
      http.get(FEED, () =>
        HttpResponse.json({
          fecha_pedida: "2026-09-15", fecha_efectiva: "2026-09-15", total_disponible: 50,
          partidos: [partido()],
        }),
      ),
    );
    renderFeed();
    expect(await screen.findByText("Mostrando los primeros 1 de 50 partidos.")).toBeInTheDocument();
  });

  it("sin truncar, no muestra el pie", async () => {
    server.use(
      http.get(FEED, () =>
        HttpResponse.json({
          fecha_pedida: "2026-09-15", fecha_efectiva: "2026-09-15", total_disponible: 1,
          partidos: [partido()],
        }),
      ),
    );
    renderFeed();
    await screen.findByText("Norte");
    expect(screen.queryByText(/Mostrando los primeros/)).not.toBeInTheDocument();
  });

  it("D3: navegar al día siguiente pide ventana_fallback_dias=0 (sin fallback en navegación explícita)", async () => {
    let ultimaQuery: URLSearchParams | undefined;
    server.use(
      http.get(FEED, ({ request }) => {
        ultimaQuery = new URL(request.url).searchParams;
        return HttpResponse.json({
          fecha_pedida: "2026-09-15", fecha_efectiva: "2026-09-15", total_disponible: 0, partidos: [],
        });
      }),
    );
    const user = userEvent.setup();
    renderFeed();
    await screen.findByText("No hay partidos programados esta semana.");
    expect(ultimaQuery?.get("ventana_fallback_dias")).toBe("7");

    await user.click(screen.getByRole("button", { name: "Día siguiente" }));
    await screen.findByText("No hay partidos programados esta semana.");
    expect(ultimaQuery?.get("ventana_fallback_dias")).toBe("0");
    expect(ultimaQuery?.get("fecha")).toBe("2026-09-16");
  });

  it("E-G3: la cabecera rotula la fecha real (fecha_efectiva), nunca 'Hoy' a secas", async () => {
    server.use(
      http.get(FEED, () =>
        HttpResponse.json({
          fecha_pedida: "2026-09-15", fecha_efectiva: "2026-09-13", total_disponible: 1,
          partidos: [partido()],
        }),
      ),
    );
    renderFeed();
    await screen.findByText("Norte");
    expect(screen.queryByText("Hoy")).not.toBeInTheDocument();
    expect(screen.getByText(/13 de septiembre/)).toBeInTheDocument();
  });
});
