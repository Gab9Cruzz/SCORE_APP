import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { TOKEN_STORAGE_KEY } from "../api/client";
import { AuthProvider } from "../auth/AuthContext";
import { server } from "../test/msw-server";
import { createTestQueryClient } from "../test/test-utils";
import { limpiarEventoPendiente } from "../lib/colaOfflineEventos";
import { MesaPanel } from "./ControlDeMesa";

const PARTIDO_3 = "http://127.0.0.1:8000/api/v1/partidos/3";
const EQUIPOS = "http://127.0.0.1:8000/api/v1/equipos";
const EVENTOS = "http://127.0.0.1:8000/api/v1/eventos";
const EVENTOS_PARTIDO = "http://127.0.0.1:8000/api/v1/eventos-partido";
const PLANTILLA_1 = "http://127.0.0.1:8000/api/v1/estadisticas/equipos/1/plantilla";
const PLANTILLA_2 = "http://127.0.0.1:8000/api/v1/estadisticas/equipos/2/plantilla";

const SESSION_STORAGE_KEY = "score-app.session";

const PARTIDO_EN_CURSO = {
  id: 3,
  estado: "En curso",
  fecha_partido: "2026-02-05T16:00:00",
  torneo_id: 1,
  equipos_id_local: 1,
  equipos_id_visitante: 2,
  jornada: 1,
  arbitro_id: 42,
};

function sembrarSesion() {
  localStorage.setItem(TOKEN_STORAGE_KEY, "fake-token");
  localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify({ username: "arbitro_test", rol: "Arbitro", id: 42 }));
}

function montarMesaPanel() {
  server.use(
    http.get(PARTIDO_3, () => HttpResponse.json(PARTIDO_EN_CURSO)),
    http.get(EQUIPOS, () =>
      HttpResponse.json([
        { id: 1, nombre: "Tiburones FC" },
        { id: 2, nombre: "Águilas del Sur" },
      ]),
    ),
    http.get(EVENTOS, () =>
      HttpResponse.json([
        { id: 1, nombre: "Gol", estado: "Activo" },
        { id: 3, nombre: "Tarjeta Roja", estado: "Activo" },
      ]),
    ),
    http.get(EVENTOS_PARTIDO, () => HttpResponse.json([])),
    http.get(PLANTILLA_1, () => HttpResponse.json([{ jugador_id: 5, jugador: "Andrés Vera", equipo_id: 1, equipo: "Tiburones FC", dorsal: 9 }])),
    http.get(PLANTILLA_2, () => HttpResponse.json([])),
  );
  sembrarSesion();
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MesaPanel partidoId={3} onVolver={() => {}} />
      </AuthProvider>
    </QueryClientProvider>,
  );
}

/** Carga un Gol de Tiburones FC (Andrés Vera) en el minuto 30 — mismo
 * flujo tap-a-tap que un árbitro real, hasta el botón "Confirmar". */
async function cargarUnGol(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: /Gol/ }));
  await user.click(screen.getByRole("button", { name: "Tiburones FC" }));
  await user.click(screen.getByRole("button", { name: /Andrés Vera/ }));
  await user.type(screen.getByLabelText("Minuto"), "30");
  await user.click(screen.getByRole("button", { name: "Confirmar" }));
}

describe("MesaPanel — offline-first (3B-1, docs/plans/cierre-backlog-todos-plan.md)", () => {
  beforeEach(() => {
    // Cola limpia entre tests — localStorage es compartido por todo el
    // entorno de tests, no se resetea solo entre `it()`.
    limpiarEventoPendiente(3);
  });

  it("un fallo de RED (no un rechazo del backend) encola el evento en vez de perderlo", async () => {
    server.use(http.post(EVENTOS_PARTIDO, () => HttpResponse.error()));
    const user = userEvent.setup();
    montarMesaPanel();
    await screen.findByText("Cargar evento");

    await cargarUnGol(user);

    expect(await screen.findByText(/todavía no se pudo enviar/)).toBeInTheDocument();
    // El form de carga se oculta mientras haya algo pendiente — un solo
    // slot de cola, no se pisa con un segundo evento.
    expect(screen.queryByText("Cargar evento")).not.toBeInTheDocument();
  });

  it("al reconectar, el evento encolado se envía solo y el form vuelve", async () => {
    server.use(http.post(EVENTOS_PARTIDO, () => HttpResponse.error()));
    const user = userEvent.setup();
    montarMesaPanel();
    await screen.findByText("Cargar evento");
    await cargarUnGol(user);
    await screen.findByText(/todavía no se pudo enviar/);

    let cuerpoRecibido: unknown;
    server.use(
      http.post(EVENTOS_PARTIDO, async ({ request }) => {
        cuerpoRecibido = await request.json();
        return HttpResponse.json({ id: 1, estado: "Registrado" }, { status: 201 });
      }),
    );

    window.dispatchEvent(new Event("online"));

    await waitFor(() => expect(cuerpoRecibido).toMatchObject({ jugador_id: 5, equipo_id: 1, eventos_id: 1, minuto: 30 }));
    expect(await screen.findByText("Cargar evento")).toBeInTheDocument();
    expect(screen.queryByText(/todavía no se pudo enviar/)).not.toBeInTheDocument();
  });

  it("un rechazo REAL del backend (no de red) no se encola — el form muestra el error de siempre", async () => {
    server.use(
      http.post(EVENTOS_PARTIDO, () => HttpResponse.json({ detail: "El jugador no pertenece a ese equipo." }, { status: 400 })),
    );
    const user = userEvent.setup();
    montarMesaPanel();
    await screen.findByText("Cargar evento");

    await cargarUnGol(user);

    expect(await screen.findByText("El jugador no pertenece a ese equipo.")).toBeInTheDocument();
    // Sigue siendo el form normal, no el card de "pendiente" — un 400 no
    // es un problema de conexión.
    expect(screen.getByText("Cargar evento")).toBeInTheDocument();
  });

  it("'Descartar' saca el evento pendiente sin enviarlo", async () => {
    server.use(http.post(EVENTOS_PARTIDO, () => HttpResponse.error()));
    const user = userEvent.setup();
    montarMesaPanel();
    await screen.findByText("Cargar evento");
    await cargarUnGol(user);
    await screen.findByText(/todavía no se pudo enviar/);

    await user.click(screen.getByRole("button", { name: "Descartar" }));

    expect(await screen.findByText("Cargar evento")).toBeInTheDocument();
  });
});
