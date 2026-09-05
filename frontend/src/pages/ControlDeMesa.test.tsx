import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { TOKEN_STORAGE_KEY } from "../api/client";
import { AuthProvider } from "../auth/AuthContext";
import { server } from "../test/msw-server";
import { createTestQueryClient, createWrapper } from "../test/test-utils";
import { limpiarEventoPendiente } from "../lib/colaOfflineEventos";
import { ControlDeMesaPage, MesaPanel } from "./ControlDeMesa";

const PARTIDO_3 = "http://127.0.0.1:8000/api/v1/partidos/3";
const EQUIPOS = "http://127.0.0.1:8000/api/v1/equipos";
const EVENTOS = "http://127.0.0.1:8000/api/v1/eventos";
const EVENTOS_PARTIDO = "http://127.0.0.1:8000/api/v1/eventos-partido";
const PLANTILLA_1 = "http://127.0.0.1:8000/api/v1/estadisticas/equipos/1/plantilla";
const PLANTILLA_2 = "http://127.0.0.1:8000/api/v1/estadisticas/equipos/2/plantilla";
const CONVOCADOS_3 = "http://127.0.0.1:8000/api/v1/partidos/3/convocados";
const TORNEOS = "http://127.0.0.1:8000/api/v1/torneos";
const PARTIDOS = "http://127.0.0.1:8000/api/v1/partidos";

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

function sembrarSesion(rol: string = "Arbitro", username: string = "arbitro_test", id: number = 42) {
  localStorage.setItem(TOKEN_STORAGE_KEY, "fake-token");
  localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify({ username, rol, id }));
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
    http.get(PLANTILLA_1, () =>
      HttpResponse.json([
        { jugador_id: 5, jugador: "Andrés Vera", equipo_id: 1, equipo: "Tiburones FC", dorsal: 9, jugador_perfil_id: 50 },
      ]),
    ),
    http.get(PLANTILLA_2, () => HttpResponse.json([])),
    // 3B-2 (docs/plans/cierre-backlog-todos-plan.md): sin convocatoria
    // guardada — MesaPanel debe seguir ofreciendo toda la plantilla, ver
    // Convocatoria.tsx.
    http.get(CONVOCADOS_3, () => HttpResponse.json([])),
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

// control-mesa-centralizacion-fixture-plan.md, ítem 1/2: RBAC scoping +
// selector de torneo en la lista de ControlDeMesaPage.
describe("ControlDeMesaPage — RBAC scoping (control-mesa-centralizacion-fixture-plan.md)", () => {
  function renderControlDeMesa() {
    const Wrapper = createWrapper();
    return render(
      <Wrapper>
        <ControlDeMesaPage />
      </Wrapper>,
    );
  }

  const PARTIDO_TORNEO_1 = {
    id: 10,
    estado: "Programado",
    fecha_partido: "2026-03-01T16:00:00",
    torneo_id: 1,
    equipos_id_local: 1,
    equipos_id_visitante: 2,
    jornada: 1,
    arbitro_id: null,
  };

  it("pide GET /partidos con solo_mios=true (scoping RBAC, ítem 1)", async () => {
    sembrarSesion("TorneoAdmin", "torneo_admin_test", 7);
    let queryRecibida: URLSearchParams | undefined;
    server.use(
      http.get(PARTIDOS, ({ request }) => {
        queryRecibida = new URL(request.url).searchParams;
        return HttpResponse.json([PARTIDO_TORNEO_1]);
      }),
      http.get(TORNEOS, () => HttpResponse.json([{ id: 1, nombre: "Copa Ecotec 2026" }])),
      http.get(EQUIPOS, () => HttpResponse.json([{ id: 1, nombre: "Tiburones FC" }, { id: 2, nombre: "Águilas del Sur" }])),
    );
    renderControlDeMesa();

    await waitFor(() => expect(queryRecibida?.get("solo_mios")).toBe("true"));
  });

  it("un TorneoAdmin con 2+ torneos asignados ve el selector, con el nombre de cada torneo", async () => {
    sembrarSesion("TorneoAdmin", "torneo_admin_test", 7);
    server.use(
      http.get(PARTIDOS, () =>
        HttpResponse.json([PARTIDO_TORNEO_1, { ...PARTIDO_TORNEO_1, id: 11, torneo_id: 2 }]),
      ),
      http.get(TORNEOS, () =>
        HttpResponse.json([
          { id: 1, nombre: "Copa Ecotec 2026" },
          { id: 2, nombre: "Liga Relámpago" },
        ]),
      ),
      http.get(EQUIPOS, () => HttpResponse.json([{ id: 1, nombre: "Tiburones FC" }, { id: 2, nombre: "Águilas del Sur" }])),
    );
    renderControlDeMesa();

    const selector = await screen.findByLabelText("Torneo");
    expect(selector).toBeInTheDocument();
    // Aparece dos veces (el <option> del selector + el nombre por fila,
    // Sección 8 "bajo-ingeniería a evitar") — alcanza con confirmar que
    // el nombre real (no el ID) está presente en la página, sin exigir
    // unicidad de match.
    expect((await screen.findAllByText("Copa Ecotec 2026")).length).toBeGreaterThan(0);
    expect((await screen.findAllByText("Liga Relámpago")).length).toBeGreaterThan(0);
  });

  it("con un solo torneo asignado, no muestra el selector (nada que elegir)", async () => {
    sembrarSesion("TorneoAdmin", "torneo_admin_test", 7);
    server.use(
      http.get(PARTIDOS, () => HttpResponse.json([PARTIDO_TORNEO_1])),
      http.get(TORNEOS, () => HttpResponse.json([{ id: 1, nombre: "Copa Ecotec 2026" }])),
      http.get(EQUIPOS, () => HttpResponse.json([{ id: 1, nombre: "Tiburones FC" }, { id: 2, nombre: "Águilas del Sur" }])),
    );
    renderControlDeMesa();

    await screen.findByText("Tiburones FC vs Águilas del Sur");
    expect(screen.queryByLabelText("Torneo")).not.toBeInTheDocument();
  });
});

// Sección 16 (Decision Audit Trail #9): Walkover mudado desde
// PartidosDelTorneo.tsx — ahora vive en Control de Mesa, junto a "Cargar
// resultado directo".
describe("ControlDeMesaPage — Walkover (control-mesa-centralizacion-fixture-plan.md, Sección 16)", () => {
  function renderControlDeMesa() {
    const Wrapper = createWrapper();
    return render(
      <Wrapper>
        <ControlDeMesaPage />
      </Wrapper>,
    );
  }

  const PARTIDO_PROGRAMADO = {
    id: 30,
    estado: "Programado",
    fecha_partido: "2026-03-01T16:00:00",
    torneo_id: 1,
    equipos_id_local: 1,
    equipos_id_visitante: 2,
    jornada: 1,
    arbitro_id: null,
  };

  it("'Walkover' pide quién no se presentó y manda el equipo elegido", async () => {
    sembrarSesion("AdminGeneral", "admin_general_test", 1);
    server.use(
      http.get(PARTIDOS, () => HttpResponse.json([PARTIDO_PROGRAMADO])),
      http.get(TORNEOS, () => HttpResponse.json([])),
      http.get(EQUIPOS, () => HttpResponse.json([{ id: 1, nombre: "Tiburones FC" }, { id: 2, nombre: "Águilas del Sur" }])),
    );
    let cuerpoRecibido: unknown;
    server.use(
      http.post("http://127.0.0.1:8000/api/v1/partidos/30/walkover", async ({ request }) => {
        cuerpoRecibido = await request.json();
        return HttpResponse.json({ ...PARTIDO_PROGRAMADO, estado: "Finalizado", es_walkover: true });
      }),
    );
    const user = userEvent.setup();
    renderControlDeMesa();
    await screen.findByText("Tiburones FC vs Águilas del Sur");

    await user.click(screen.getByRole("button", { name: "Walkover" }));
    expect(screen.getByText("¿Quién no se presentó?")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Tiburones FC" }));

    await waitFor(() => expect(cuerpoRecibido).toEqual({ equipo_ausente_id: 1 }));
  });
});

describe("ControlDeMesaPage — Cargar resultado directo (control-mesa-centralizacion-fixture-plan.md, ítem 3)", () => {
  function renderControlDeMesa() {
    const Wrapper = createWrapper();
    return render(
      <Wrapper>
        <ControlDeMesaPage />
      </Wrapper>,
    );
  }

  const PARTIDO_PROGRAMADO = {
    id: 20,
    estado: "Programado",
    fecha_partido: "2026-03-01T16:00:00",
    torneo_id: 1,
    equipos_id_local: 1,
    equipos_id_visitante: 2,
    jornada: 1,
    arbitro_id: null,
  };

  function mockBase(partido: Record<string, unknown> = PARTIDO_PROGRAMADO) {
    server.use(
      http.get(PARTIDOS, () => HttpResponse.json([partido])),
      http.get(TORNEOS, () => HttpResponse.json([])),
      http.get(EQUIPOS, () => HttpResponse.json([{ id: 1, nombre: "Tiburones FC" }, { id: 2, nombre: "Águilas del Sur" }])),
      http.get("http://127.0.0.1:8000/api/v1/partidos/20/cronometro", () =>
        HttpResponse.json({
          tipo_cronometro: "Periodos",
          cantidad_periodos: 2,
          duracion_periodo_minutos: 45,
          duracion_descanso_minutos: 15,
          partido_iniciado: false,
          partido_finalizado: false,
          periodo_abierto: null,
          ultimo_periodo_cerrado: 0,
          en_pausa: false,
          acciones_permitidas: ["Inicio_Partido"],
          hitos: [],
        }),
      ),
      http.get(PLANTILLA_1, () =>
        HttpResponse.json([{ jugador_id: 5, jugador: "Andrés Vera", equipo_id: 1, equipo: "Tiburones FC", dorsal: 9, jugador_perfil_id: 50 }]),
      ),
      http.get(PLANTILLA_2, () => HttpResponse.json([])),
      http.get(EVENTOS, () => HttpResponse.json([{ id: 1, nombre: "Gol", estado: "Activo" }])),
    );
  }

  it("'Cargar resultado directo' solo aparece en Programado, no en En curso", async () => {
    sembrarSesion("AdminGeneral", "admin_general_test", 1);
    mockBase({ ...PARTIDO_PROGRAMADO, estado: "En curso" });
    renderControlDeMesa();
    await screen.findByText("Tiburones FC vs Águilas del Sur");

    expect(screen.queryByRole("button", { name: "Cargar resultado directo" })).not.toBeInTheDocument();
  });

  it("agrega un evento, guarda, y hace POST a /resultado-directo con el body armado", async () => {
    sembrarSesion("AdminGeneral", "admin_general_test", 1);
    mockBase();
    let bodyRecibido: unknown;
    server.use(
      http.post("http://127.0.0.1:8000/api/v1/partidos/20/resultado-directo", async ({ request }) => {
        bodyRecibido = await request.json();
        return HttpResponse.json({ ...PARTIDO_PROGRAMADO, estado: "Finalizado" });
      }),
    );
    const user = userEvent.setup();
    renderControlDeMesa();
    await screen.findByText("Tiburones FC vs Águilas del Sur");

    await user.click(screen.getByRole("button", { name: "Cargar resultado directo" }));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Jugador"), "5");
    await user.type(screen.getByLabelText("Minuto"), "10");
    await user.click(screen.getByRole("button", { name: "+ Agregar evento" }));
    await user.click(screen.getByRole("button", { name: "Guardar resultado" }));

    await waitFor(() =>
      expect(bodyRecibido).toMatchObject({
        eventos: [{ jugador_id: 5, equipo_id: 1, eventos_id: 1, jugador_id_entra: null, minuto: 10 }],
      }),
    );
  });

  it("guarda un resultado 0-0 sin cargar ningún evento (lista vacía es válida)", async () => {
    sembrarSesion("AdminGeneral", "admin_general_test", 1);
    mockBase();
    let bodyRecibido: unknown;
    server.use(
      http.post("http://127.0.0.1:8000/api/v1/partidos/20/resultado-directo", async ({ request }) => {
        bodyRecibido = await request.json();
        return HttpResponse.json({ ...PARTIDO_PROGRAMADO, estado: "Finalizado" });
      }),
    );
    const user = userEvent.setup();
    renderControlDeMesa();
    await screen.findByText("Tiburones FC vs Águilas del Sur");

    await user.click(screen.getByRole("button", { name: "Cargar resultado directo" }));
    await screen.findByRole("dialog");
    await user.click(screen.getByRole("button", { name: "Guardar resultado" }));

    await waitFor(() => expect(bodyRecibido).toMatchObject({ eventos: [] }));
  });

  it("un rechazo del backend muestra el mensaje de error sin perder el formulario", async () => {
    sembrarSesion("AdminGeneral", "admin_general_test", 1);
    mockBase();
    server.use(
      http.post("http://127.0.0.1:8000/api/v1/partidos/20/resultado-directo", () =>
        HttpResponse.json({ detail: "Este partido está 'Finalizado' — el resultado directo solo se puede cargar para un partido 'Programado' que todavía no arrancó." }, { status: 400 }),
      ),
    );
    const user = userEvent.setup();
    renderControlDeMesa();
    await screen.findByText("Tiburones FC vs Águilas del Sur");

    await user.click(screen.getByRole("button", { name: "Cargar resultado directo" }));
    await screen.findByRole("dialog");
    await user.click(screen.getByRole("button", { name: "Guardar resultado" }));

    expect(await screen.findByText(/el resultado directo solo se puede cargar/)).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});
