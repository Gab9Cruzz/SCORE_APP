import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { TOKEN_STORAGE_KEY } from "../../api/client";
import { AuthProvider } from "../../auth/AuthContext";
import { server } from "../../test/msw-server";
import { createTestQueryClient } from "../../test/test-utils";
import { GestionarPartidoPage } from "./GestionarPartido";

const BASE = "http://127.0.0.1:8000/api/v1";
const SESSION_STORAGE_KEY = "score-app.session";

const PARTIDO = {
  id: 30,
  estado: "Programado",
  fecha_partido: "2026-03-01T16:00:00",
  torneo_id: 1,
  equipos_id_local: 1,
  equipos_id_visitante: 2,
  jornada: 1,
  arbitro_id: null,
};

function sembrarSesion(rol = "TorneoAdmin", id = 7) {
  localStorage.setItem(TOKEN_STORAGE_KEY, "fake-token");
  localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify({ username: "admin_test", rol, id }));
}

/** Handlers mínimos para que la vista monte. `onUnhandledRequest: "error"`
 * (test/setup.ts) convierte cualquier request sin mock en fallo duro, así que
 * la lista tiene que estar completa. */
function sembrarBackend(overrides: Parameters<typeof server.use> = [] as never) {
  server.use(
    // Los overrides van PRIMERO: MSW resuelve con el primer handler que
    // matchea, así que puestos al final quedarían tapados por los defaults.
    ...overrides,
    http.get(`${BASE}/partidos/30`, () => HttpResponse.json(PARTIDO)),
    http.get(`${BASE}/partidos/30/convocados`, () => HttpResponse.json([])),
    http.get(`${BASE}/partidos/30/cronometro`, () =>
      HttpResponse.json({ tipo_cronometro: "Periodos", partido_iniciado: false }),
    ),
    http.get(`${BASE}/partidos/30/preflight-inicio`, () =>
      HttpResponse.json({
        minimo_para_iniciar: 5,
        titulares_por_equipo: [
          { equipo_id: 1, nombre: "Tiburones FC", titulares: 0 },
          { equipo_id: 2, nombre: "Águilas del Sur", titulares: 0 },
        ],
        puede_iniciar: false,
        motivo_bloqueo: "Tiburones FC tiene 0 titulares marcados, esta modalidad exige 5.",
        partido_iniciado: false,
      }),
    ),
    http.get(`${BASE}/inscripciones`, () =>
      HttpResponse.json([
        { id: 100, equipo_id: 1, torneo_id: 1 },
        { id: 200, equipo_id: 2, torneo_id: 1 },
      ]),
    ),
    http.get(`${BASE}/plantillas`, () => HttpResponse.json([])),
    http.get(`${BASE}/equipos`, () =>
      HttpResponse.json([
        { id: 1, nombre: "Tiburones FC" },
        { id: 2, nombre: "Águilas del Sur" },
      ]),
    ),
    http.get(`${BASE}/torneos`, () => HttpResponse.json([{ id: 1, nombre: "Copa Ecotec 2026" }])),
    // Resolución dirigida por ID: la vista arranca sin mapa base de torneos, así
    // que pide el suyo individual (useNombrePorIdConFaltantes).
    http.get(`${BASE}/torneos/1`, () => HttpResponse.json({ id: 1, nombre: "Copa Ecotec 2026" })),
    // Las pide MesaPanel cuando el partido está en curso, y el modal de
    // resultado directo para elegir jugadores.
    http.get(`${BASE}/estadisticas/equipos/1/plantilla`, () => HttpResponse.json([])),
    http.get(`${BASE}/estadisticas/equipos/2/plantilla`, () => HttpResponse.json([])),
    http.get(`${BASE}/eventos`, () => HttpResponse.json([{ id: 1, nombre: "Gol", estado: "Activo" }])),
    http.get(`${BASE}/eventos-partido`, () => HttpResponse.json([])),
  );
}

function montar() {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={["/control-de-mesa/partido/30"]}>
          <Routes>
            <Route path="/control-de-mesa/partido/:partidoId" element={<GestionarPartidoPage />} />
            <Route path="/control-de-mesa" element={<div>LISTA</div>} />
            <Route path="/partidos/:partidoId" element={<div>VISTA PÚBLICA DEL PARTIDO</div>} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

describe("GestionarPartido — deep-link y punto de entrada", () => {
  it("carga montando directo en la ruta (equivale a un refresh en pleno partido)", async () => {
    sembrarSesion();
    sembrarBackend();
    montar();

    // Antes esto era un panel por useState sin URL: un refresh devolvía al
    // operador a la lista y le hacía perder el lugar.
    expect(await screen.findByRole("heading", { name: /Tiburones FC vs Águilas del Sur/ })).toBeInTheDocument();
  });

  it("muestra el torneo en el header (la vista es deep-linkeable)", async () => {
    sembrarSesion();
    sembrarBackend();
    montar();

    expect(await screen.findByText(/Copa Ecotec 2026/)).toBeInTheDocument();
  });
});

describe("GestionarPartido — arranque", () => {
  it("bloquea 'Empezar Partido' con el motivo del backend, sin reimplementar la regla", async () => {
    sembrarSesion();
    sembrarBackend();
    montar();

    const boton = await screen.findByRole("button", { name: /Empezar Partido/ });
    expect(boton).toHaveAttribute("aria-disabled", "true");
    // El motivo es texto real en el DOM y el botón lo referencia: un
    // `disabled` + `title` no sería focusable ni anunciable, y `title` no
    // existe en touch.
    expect(boton).toHaveAttribute("aria-describedby", "motivo-inicio");
    expect(screen.getByText(/esta modalidad exige 5/)).toBeInTheDocument();
  });

  it("con el mínimo alcanzado, arranca disparando Inicio_Partido Y el primer período", async () => {
    // H-10: el botón del dashboard viejo solo mandaba Inicio_Partido, lo que en
    // un torneo por períodos dejaba el partido "En curso" con el reloj parado.
    sembrarSesion();
    const hitos: unknown[] = [];
    sembrarBackend([
      http.get(`${BASE}/partidos/30/preflight-inicio`, () =>
        HttpResponse.json({
          minimo_para_iniciar: 5,
          titulares_por_equipo: [],
          puede_iniciar: true,
          motivo_bloqueo: null,
          partido_iniciado: false,
        }),
      ),
      http.post(`${BASE}/partidos/30/hitos`, async ({ request }) => {
        hitos.push(await request.json());
        return HttpResponse.json({ id: hitos.length, tipo_hito: "x" });
      }),
    ] as never);
    const user = userEvent.setup();
    montar();

    await user.click(await screen.findByRole("button", { name: /Empezar Partido/ }));

    await waitFor(() => expect(hitos).toHaveLength(2));
    expect(hitos[0]).toMatchObject({ tipo_hito: "Inicio_Partido" });
    expect(hitos[1]).toMatchObject({ tipo_hito: "Inicio_Periodo", numero_periodo: 1 });
  });

  it("en un torneo 'Corrido' arranca con un solo hito (no hay períodos)", async () => {
    sembrarSesion();
    const hitos: unknown[] = [];
    sembrarBackend([
      http.get(`${BASE}/partidos/30/cronometro`, () =>
        HttpResponse.json({ tipo_cronometro: "Corrido", partido_iniciado: false }),
      ),
      http.get(`${BASE}/partidos/30/preflight-inicio`, () =>
        HttpResponse.json({
          minimo_para_iniciar: 1,
          titulares_por_equipo: [],
          puede_iniciar: true,
          motivo_bloqueo: null,
          partido_iniciado: false,
        }),
      ),
      http.post(`${BASE}/partidos/30/hitos`, async ({ request }) => {
        hitos.push(await request.json());
        return HttpResponse.json({ id: 1, tipo_hito: "x" });
      }),
    ] as never);
    const user = userEvent.setup();
    montar();

    await user.click(await screen.findByRole("button", { name: /Empezar Partido/ }));

    await waitFor(() => expect(hitos).toHaveLength(1));
    expect(hitos[0]).toMatchObject({ tipo_hito: "Inicio_Partido" });
  });
});

describe("GestionarPartido — partido en curso (llegadas tardías)", () => {
  function sembrarEnCurso(extra: Parameters<typeof server.use> = [] as never) {
    sembrarBackend([
      http.get(`${BASE}/partidos/30`, () => HttpResponse.json({ ...PARTIDO, estado: "En curso" })),
      http.get(`${BASE}/partidos/30/cronometro`, () =>
        HttpResponse.json({ tipo_cronometro: "Periodos", partido_iniciado: true }),
      ),
      http.get(`${BASE}/partidos/30/preflight-inicio`, () =>
        HttpResponse.json({
          minimo_para_iniciar: 5,
          titulares_por_equipo: [],
          puede_iniciar: false,
          motivo_bloqueo: "El partido ya arrancó.",
          partido_iniciado: true,
        }),
      ),
      ...extra,
    ] as never);
  }

  it("avisa que el cronómetro sigue corriendo y que solo se pueden sumar suplentes", async () => {
    sembrarSesion();
    sembrarEnCurso();
    montar();

    expect(await screen.findByText(/Solo podés sumar suplentes/)).toBeInTheDocument();
  });

  it("no ofrece 'Empezar Partido' ni 'Cargar resultado directo' con el partido en curso", async () => {
    sembrarSesion();
    sembrarEnCurso();
    montar();

    await screen.findByText(/Solo podés sumar suplentes/);
    expect(screen.queryByRole("button", { name: /Empezar Partido/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Cargar resultado directo/ })).not.toBeInTheDocument();
  });

  it("no deja reprogramar la fecha con el partido en curso", async () => {
    // Mover la fecha hacia atrás con eventos ya cargados los dejaría
    // inconsistentes: el trigger que valida pertenencia mira la fecha del
    // partido, pero corre sobre EVENTOS_PARTIDO, no sobre PARTIDOS.
    sembrarSesion();
    sembrarEnCurso();
    montar();

    await screen.findByText(/Solo podés sumar suplentes/);
    expect(screen.getByText(/La fecha no se puede cambiar con el partido en curso/)).toBeInTheDocument();
  });
});

describe("GestionarPartido — acciones secundarias", () => {
  it("'Walkover' pide quién no se presentó y manda el equipo elegido", async () => {
    sembrarSesion("AdminGeneral", 1);
    let cuerpoRecibido: unknown;
    sembrarBackend([
      http.post(`${BASE}/partidos/30/walkover`, async ({ request }) => {
        cuerpoRecibido = await request.json();
        return HttpResponse.json({ ...PARTIDO, estado: "Finalizado", es_walkover: true });
      }),
    ] as never);
    const user = userEvent.setup();
    montar();

    await screen.findByRole("heading", { name: /Tiburones FC vs Águilas del Sur/ });
    await user.click(screen.getByRole("button", { name: "Walkover" }));
    expect(screen.getByText("¿Quién no se presentó?")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Tiburones FC" }));

    await waitFor(() => expect(cuerpoRecibido).toEqual({ equipo_ausente_id: 1 }));
  });

  it("'Cargar resultado directo' abre el modal sin pasar por el cronómetro", async () => {
    sembrarSesion();
    sembrarBackend();
    const user = userEvent.setup();
    montar();

    await user.click(await screen.findByRole("button", { name: /Cargar resultado directo/ }));

    // Por rol, no por texto: el botón que abre el modal dice lo mismo que su
    // encabezado, así que un matcher por texto encuentra los dos.
    expect(await screen.findByRole("heading", { name: "Cargar resultado directo" })).toBeInTheDocument();
  });
});

describe("GestionarPartido — estados no editables", () => {
  it("un partido Finalizado queda en solo lectura", async () => {
    sembrarSesion();
    sembrarBackend([
      http.get(`${BASE}/partidos/30`, () => HttpResponse.json({ ...PARTIDO, estado: "Finalizado" })),
    ] as never);
    montar();

    expect(await screen.findByText(/la alineación quedó cerrada/)).toBeInTheDocument();
  });

  it("un partido de bracket sin rival explica que falta el equipo, sin editor", async () => {
    sembrarSesion();
    sembrarBackend([
      http.get(`${BASE}/partidos/30`, () =>
        HttpResponse.json({ ...PARTIDO, equipos_id_visitante: null }),
      ),
    ] as never);
    montar();

    expect(await screen.findByText(/todavía no tiene los dos equipos definidos/)).toBeInTheDocument();
  });
});

describe("GestionarPartido — la plantilla tiene que llegar a la pantalla", () => {
  const ROSTER_LOCAL = [
    { equipo_id: 1, equipo: "Tiburones FC", torneo_id: 1, jugador_id: 11, jugador: "Samuel Luna", jugador_perfil_id: 1785, dorsal: 1, fecha_inicio: "2026-01-01" },
    { equipo_id: 1, equipo: "Tiburones FC", torneo_id: 1, jugador_id: 12, jugador: "David Peña", jugador_perfil_id: 1784, dorsal: 10, fecha_inicio: "2026-01-01" },
  ];

  it("lista los jugadores del roster del torneo en el Paso 1", async () => {
    // Regresión: la vista leía `GET /plantillas`, que devuelve JugadorEquipoOut
    // — sin el nombre del jugador y sin equipo_id — e incluye las filas
    // Traspasado/Inactivo. Con ese endpoint la pantalla no mostraba ningún
    // jugador para convocar. La fuente correcta es
    // /estadisticas/equipos/{id}/plantilla?torneo_id= (H2-eng del plan).
    sembrarSesion();
    sembrarBackend([
      http.get(`${BASE}/estadisticas/equipos/1/plantilla`, () => HttpResponse.json(ROSTER_LOCAL)),
      // Si la vista volviera a /plantillas, este handler vacío la deja sin nadie.
      http.get(`${BASE}/plantillas`, () => HttpResponse.json([])),
    ] as never);
    const user = userEvent.setup();
    montar();

    await user.click(await screen.findByRole("button", { name: /Paso 1 · Convocados/ }));

    // Por rol checkbox: el nombre del jugador aparece también en el aria-label
    // del botón de mover, así que un matcher por texto encuentra los dos.
    expect(await screen.findByRole("checkbox", { name: /Samuel Luna/ })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /David Peña/ })).toBeInTheDocument();
  });

  it("acota la plantilla al torneo del partido (un equipo en dos torneos no duplica perfiles)", async () => {
    sembrarSesion();
    let urlPedida = "";
    sembrarBackend([
      http.get(`${BASE}/estadisticas/equipos/1/plantilla`, ({ request }) => {
        urlPedida = request.url;
        return HttpResponse.json(ROSTER_LOCAL);
      }),
    ] as never);
    montar();

    await waitFor(() => expect(urlPedida).toContain("torneo_id=1"));
  });

  it("un GET /convocados que falla se ve como error, no como pantalla vacía", async () => {
    // Regresión del bug reportado en /control-de-mesa/partido/13: con la
    // migración 25 sin aplicar el endpoint devolvía 500, `seleccion` quedaba
    // en null y la pantalla mostraba el header y nada más — sin editor y sin
    // ningún indicio de que algo hubiera fallado.
    sembrarSesion();
    sembrarBackend([
      http.get(`${BASE}/partidos/30/convocados`, () =>
        HttpResponse.json({ detail: "no existe la relación «convocado_a_partido»" }, { status: 500 }),
      ),
      http.get(`${BASE}/estadisticas/equipos/1/plantilla`, () => HttpResponse.json(ROSTER_LOCAL)),
    ] as never);
    montar();

    expect(await screen.findByText(/No se pudo cargar la convocatoria/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });

  it("una plantilla que falla muestra el error de ESE equipo, con reintento", async () => {
    sembrarSesion();
    sembrarBackend([
      http.get(`${BASE}/estadisticas/equipos/1/plantilla`, () =>
        HttpResponse.json({ detail: "boom" }, { status: 500 }),
      ),
    ] as never);
    montar();

    expect(await screen.findByText(/No se pudo cargar la plantilla de Tiburones FC/)).toBeInTheDocument();
  });

  it("un roster vacío lo dice, en vez de no renderizar nada", async () => {
    // Antes la inicialización exigía `plantillaCompleta.length > 0`, así que un
    // roster vacío dejaba `seleccion` en null para siempre y el editor no
    // llegaba a montarse ni para avisar.
    sembrarSesion();
    sembrarBackend();
    const user = userEvent.setup();
    montar();

    await user.click(await screen.findByRole("button", { name: /Paso 1 · Convocados/ }));

    expect(await screen.findByText(/no tiene jugadores en el roster del torneo/)).toBeInTheDocument();
  });
});

describe("GestionarPartido — redirección post-guardado de resultado directo", () => {
  it("al guardar resultado directo, redirige a la vista pública del partido (control-mesa-reactividad-playoffs-plan.md, Fase 1/2/3 §8)", async () => {
    sembrarSesion();
    sembrarBackend([
      http.post(`${BASE}/partidos/30/resultado-directo`, () => HttpResponse.json({ id: 30, estado: "Finalizado" })),
    ] as never);
    const user = userEvent.setup();
    montar();

    await user.click(await screen.findByRole("button", { name: /Cargar resultado directo/ }));
    // 0-0 es un resultado válido — sin slots que completar, el botón
    // "Guardar resultado" ya queda habilitado.
    await user.click(await screen.findByRole("button", { name: "Guardar resultado" }));

    expect(await screen.findByText("VISTA PÚBLICA DEL PARTIDO")).toBeInTheDocument();
  });
});
