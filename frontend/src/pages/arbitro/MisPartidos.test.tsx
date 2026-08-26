import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { TOKEN_STORAGE_KEY } from "../../api/client";
import { AuthProvider } from "../../auth/AuthContext";
import { server } from "../../test/msw-server";
import { createTestQueryClient } from "../../test/test-utils";
import { MisPartidosPage } from "./MisPartidos";

const PARTIDOS = "http://127.0.0.1:8000/api/v1/partidos";
const PARTIDO_5 = "http://127.0.0.1:8000/api/v1/partidos/5";
const EQUIPOS = "http://127.0.0.1:8000/api/v1/equipos";
const EVENTOS = "http://127.0.0.1:8000/api/v1/eventos";
const EVENTOS_PARTIDO = "http://127.0.0.1:8000/api/v1/eventos-partido";
const PLANTILLA_1 = "http://127.0.0.1:8000/api/v1/estadisticas/equipos/1/plantilla";
const PLANTILLA_2 = "http://127.0.0.1:8000/api/v1/estadisticas/equipos/2/plantilla";

// Mismo nombre de key que el privado `SESSION_STORAGE_KEY` en
// AuthContext.tsx — sembrar localStorage directo (en vez de pasar por el
// form de Login) alcanza porque `loadStoredSession()` lee de acá de forma
// síncrona al montar `AuthProvider`.
const SESSION_STORAGE_KEY = "score-app.session";

/** Deja una sesión de Arbitro con id ya sembrada en localStorage —
 * equivalente a lo que `AuthContext.login()` deja después de un login
 * exitoso + `GET /auth/me` resuelto (Fase 3, D2), sin tener que pasar por
 * el form real de Login en cada test de esta página. */
function sembrarSesionArbitro(id = 42) {
  localStorage.setItem(TOKEN_STORAGE_KEY, "fake-token");
  localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify({ username: "arbitro_test", rol: "Arbitro", id }));
}

function renderPagina() {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MisPartidosPage />
      </AuthProvider>
    </QueryClientProvider>,
  );
}

describe("MisPartidosPage (roles-3-modulos-plan.md, Fase 3)", () => {
  beforeEach(() => {
    server.use(http.get(PARTIDOS, () => HttpResponse.json([])));
  });

  it("pide GET /partidos con arbitro_id = session.id (D1, D2)", async () => {
    let query: string | null = null;
    server.use(
      http.get(PARTIDOS, ({ request }) => {
        query = new URL(request.url).search;
        return HttpResponse.json([]);
      }),
    );
    sembrarSesionArbitro(42);
    renderPagina();

    await waitFor(() => expect(query).toContain("arbitro_id=42"));
  });

  it("sin session.id (falló /auth/me) no dispara la query y avisa en vez de romper", () => {
    localStorage.setItem(TOKEN_STORAGE_KEY, "fake-token");
    localStorage.setItem(
      SESSION_STORAGE_KEY,
      JSON.stringify({ username: "arbitro_test", rol: "Arbitro" }), // sin id
    );
    renderPagina();

    expect(screen.getByText(/No pudimos confirmar tu usuario/)).toBeInTheDocument();
  });

  it("filtra a Programado/En curso — no muestra Finalizado ni Cancelado (D6)", async () => {
    server.use(
      http.get(PARTIDOS, () =>
        HttpResponse.json([
          { id: 1, estado: "Finalizado", fecha_partido: "2026-01-15T16:00:00", torneo_id: 1, equipos_id_local: 1, equipos_id_visitante: 2, jornada: 1, arbitro_id: 42 },
          { id: 2, estado: "Cancelado", fecha_partido: "2026-01-16T16:00:00", torneo_id: 1, equipos_id_local: 1, equipos_id_visitante: 2, jornada: 2, arbitro_id: 42 },
          { id: 5, estado: "Programado", fecha_partido: "2026-02-05T16:00:00", torneo_id: 1, equipos_id_local: 1, equipos_id_visitante: 2, jornada: 3, arbitro_id: 42 },
        ]),
      ),
    );
    sembrarSesionArbitro();
    renderPagina();

    expect(await screen.findByText(/Partido #5/)).toBeInTheDocument();
    expect(screen.queryByText(/Partido #1\b/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Partido #2\b/)).not.toBeInTheDocument();
  });

  it("empty-state árbitro-específico cuando no hay partidos asignados activos", async () => {
    sembrarSesionArbitro();
    renderPagina();

    expect(await screen.findByText("No tenés partidos asignados por ahora.")).toBeInTheDocument();
  });

  it("al elegir un partido, reusa MesaPanel (D4) — se ve 'Volver a la lista'", async () => {
    const user = userEvent.setup();
    server.use(
      http.get(PARTIDOS, () =>
        HttpResponse.json([
          { id: 5, estado: "Programado", fecha_partido: "2026-02-05T16:00:00", torneo_id: 1, equipos_id_local: 1, equipos_id_visitante: 2, jornada: 3, arbitro_id: 42 },
        ]),
      ),
      http.get(PARTIDO_5, () =>
        HttpResponse.json({ id: 5, estado: "Programado", fecha_partido: "2026-02-05T16:00:00", torneo_id: 1, equipos_id_local: 1, equipos_id_visitante: 2, jornada: 3, arbitro_id: 42 }),
      ),
      http.get(EQUIPOS, () =>
        HttpResponse.json([
          { id: 1, nombre: "Tiburones FC" },
          { id: 2, nombre: "Águilas del Sur" },
        ]),
      ),
      http.get(EVENTOS, () => HttpResponse.json([])),
      http.get(EVENTOS_PARTIDO, () => HttpResponse.json([])),
      http.get(PLANTILLA_1, () => HttpResponse.json([])),
      http.get(PLANTILLA_2, () => HttpResponse.json([])),
    );
    sembrarSesionArbitro();
    renderPagina();

    await user.click(await screen.findByText(/Partido #5/));

    expect(await screen.findByText("← Volver a la lista")).toBeInTheDocument();
    expect(screen.getByText("Tiburones FC")).toBeInTheDocument();
  });
});
