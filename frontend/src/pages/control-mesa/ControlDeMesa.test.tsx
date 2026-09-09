import { render, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { TOKEN_STORAGE_KEY } from "../../api/client";
import { server } from "../../test/msw-server";
import { createWrapper } from "../../test/test-utils";
import { ControlDeMesaPage } from "./ControlDeMesa";

const EQUIPOS = "http://127.0.0.1:8000/api/v1/equipos";
const TORNEOS = "http://127.0.0.1:8000/api/v1/torneos";
const PARTIDOS = "http://127.0.0.1:8000/api/v1/partidos";

const SESSION_STORAGE_KEY = "score-app.session";

function sembrarSesion(rol: string = "Arbitro", username: string = "arbitro_test", id: number = 42) {
  localStorage.setItem(TOKEN_STORAGE_KEY, "fake-token");
  localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify({ username, rol, id }));
}

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


// gestionar-partido-alineaciones-plan.md, Requerimiento 1: la fila se colapsa
// a un punto de entrada unico.
describe("ControlDeMesaPage — punto de entrada unico", () => {
  const PARTIDO_PROGRAMADO = {
    id: 10,
    estado: "Programado",
    fecha_partido: "2026-03-01T16:00:00",
    torneo_id: 1,
    equipos_id_local: 1,
    equipos_id_visitante: 2,
    jornada: 1,
    arbitro_id: null,
  };

  function montar() {
    const Wrapper = createWrapper();
    return render(
      <Wrapper>
        <ControlDeMesaPage />
      </Wrapper>,
    );
  }

  function sembrarPartidos(estado: string) {
    sembrarSesion("TorneoAdmin", "torneo_admin_test", 7);
    server.use(
      http.get(PARTIDOS, () => HttpResponse.json([{ ...PARTIDO_PROGRAMADO, estado }])),
      http.get(TORNEOS, () => HttpResponse.json([{ id: 1, nombre: "Copa Ecotec 2026" }])),
      http.get(EQUIPOS, () =>
        HttpResponse.json([
          { id: 1, nombre: "Tiburones FC" },
          { id: 2, nombre: "Aguilas del Sur" },
        ]),
      ),
    );
  }

  it("cada fila tiene UN solo boton de accion, 'Gestionar Partido'", async () => {
    sembrarPartidos("Programado");
    montar();

    await screen.findByText(/Tiburones FC/);
    const fila = screen.getByRole("listitem");
    const botones = within(fila).getAllByRole("button");
    expect(botones).toHaveLength(1);
    expect(botones[0]).toHaveTextContent("Gestionar Partido");
  });

  it("ofrece 'Gestionar Partido' tambien para un partido Programado (regresion del deadlock)", async () => {
    // T1 del plan. Antes, la unica puerta al panel (y por lo tanto a la
    // convocatoria) se renderizaba SOLO si el partido NO estaba 'Programado'
    // — pero para dejar de estarlo hacia falta una convocatoria que no se
    // podia cargar. Un TorneoAdmin quedaba trabado sin salida.
    sembrarPartidos("Programado");
    montar();

    expect(await screen.findByRole("button", { name: "Gestionar Partido" })).toBeInTheDocument();
  });

  it("el mismo boton sirve con el partido En curso", async () => {
    sembrarPartidos("En curso");
    montar();

    expect(await screen.findByRole("button", { name: "Gestionar Partido" })).toBeInTheDocument();
  });
});
