import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "../../../test/msw-server";
import { createWrapper } from "../../../test/test-utils";
import { MotorFormatosPanel } from "./MotorFormatosPanel";

const EQUIPOS = "http://127.0.0.1:8000/api/v1/equipos";
const TORNEO_ID = 20;
const ESTADO_FASE_URL = `http://127.0.0.1:8000/api/v1/torneos/${TORNEO_ID}/estado-fase`;
const TORNEO_URL = `http://127.0.0.1:8000/api/v1/torneos/${TORNEO_ID}`;

function mockEstadoFase(overrides: Record<string, unknown> = {}) {
  server.use(
    http.get(ESTADO_FASE_URL, () =>
      HttpResponse.json({
        fase_actual: { id: 1, nombre: "Fase", tipo: "Liga", estado: "En_Curso" },
        partidos_total: 0,
        partidos_finalizados: 0,
        partidos_cancelados: 0,
        partidos_pendientes: 0,
        fase_completa: false,
        acciones_disponibles: [],
        torneo_cerrado: false,
        podio: null,
        ...overrides,
      }),
    ),
  );
}

function renderPanel(props: Partial<Parameters<typeof MotorFormatosPanel>[0]> = {}) {
  const Wrapper = createWrapper();
  return render(
    <Wrapper>
      <MotorFormatosPanel torneoId={TORNEO_ID} formato="Liga" equiposInscritosCount={4} {...props} />
    </Wrapper>,
  );
}

describe("MotorFormatosPanel — Liga", () => {
  it("muestra Generar Fixture cuando no hay calendario todavía", async () => {
    mockEstadoFase({ fase_actual: null });
    renderPanel({ formato: "Liga" });
    expect(await screen.findByText("Aún no se generó el calendario.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generar Fixture" })).toBeInTheDocument();
  });

  it("Generar Fixture llama a POST /torneos/{id}/fixture", async () => {
    mockEstadoFase({ fase_actual: null });
    let llamado = false;
    server.use(
      http.post(`http://127.0.0.1:8000/api/v1/torneos/${TORNEO_ID}/fixture`, () => {
        llamado = true;
        return HttpResponse.json({ id: 1, estado: "En_Curso" });
      }),
    );
    const user = userEvent.setup();
    renderPanel({ formato: "Liga" });
    await user.click(await screen.findByRole("button", { name: "Generar Fixture" }));
    await waitFor(() => expect(llamado).toBe(true));
  });

  it("fase en curso (no completa): muestra el conteo de 3 partes, sin botón de acción", async () => {
    mockEstadoFase({
      partidos_total: 6,
      partidos_finalizados: 2,
      partidos_cancelados: 0,
      partidos_pendientes: 4,
      fase_completa: false,
      acciones_disponibles: [],
    });
    renderPanel({ formato: "Liga" });
    expect(await screen.findByText("2 jugado(s) · 0 cancelado(s) · 4 pendiente(s)")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Configurar Siguiente Fase" })).not.toBeInTheDocument();
  });

  it("fase completa con los 2 caminos: el botón dice 'Configurar Siguiente Fase'", async () => {
    mockEstadoFase({
      partidos_total: 6,
      partidos_finalizados: 6,
      fase_completa: true,
      acciones_disponibles: ["cerrar_directo", "generar_playoffs"],
    });
    renderPanel({ formato: "Liga" });
    expect(await screen.findByRole("button", { name: "Configurar Siguiente Fase" })).toBeInTheDocument();
  });

  it("torneo cerrado: el panel no renderiza nada (el podio vive en TorneoDashboard)", async () => {
    mockEstadoFase({ torneo_cerrado: true });
    const { container } = renderPanel({ formato: "Liga" });
    await waitFor(() => expect(container.querySelector(".motor-formatos-panel")).not.toBeInTheDocument());
  });
});

describe("MotorFormatosPanel — Eliminación", () => {
  it("muestra Hacer Sorteo cuando no hay bracket todavía", async () => {
    mockEstadoFase({ fase_actual: null });
    renderPanel({ formato: "Eliminacion" });
    expect(await screen.findByText("Aún no se hizo el sorteo.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Hacer Sorteo" })).toBeInTheDocument();
  });

  // T46 — una casilla sin equipo dice "Ganador Partido N", nunca queda
  // en blanco sin explicación.
  it("el bracket muestra 'Ganador Partido N' en casillas sin equipo aún", async () => {
    mockEstadoFase({
      fase_actual: { id: 1, nombre: "Eliminatoria", tipo: "Eliminacion", estado: "En_Curso" },
      partidos_total: 3,
      partidos_pendientes: 3,
    });
    server.use(
      http.get(`http://127.0.0.1:8000/api/v1/torneos/${TORNEO_ID}/bracket`, () =>
        HttpResponse.json([
          {
            id: 1,
            equipos_id_local: 1,
            equipos_id_visitante: 2,
            ronda_nombre: "Semifinal",
            partido_siguiente_id: 3,
            slot_siguiente: "Local",
            partido_perdedor_siguiente_id: null,
            slot_perdedor_siguiente: null,
            partido_ida_id: null,
            estado: "Programado",
          },
          {
            id: 2,
            equipos_id_local: 3,
            equipos_id_visitante: 4,
            ronda_nombre: "Semifinal",
            partido_siguiente_id: 3,
            slot_siguiente: "Visitante",
            partido_perdedor_siguiente_id: null,
            slot_perdedor_siguiente: null,
            partido_ida_id: null,
            estado: "Programado",
          },
          {
            id: 3,
            equipos_id_local: null,
            equipos_id_visitante: null,
            ronda_nombre: "Final",
            partido_siguiente_id: null,
            slot_siguiente: null,
            partido_perdedor_siguiente_id: null,
            slot_perdedor_siguiente: null,
            partido_ida_id: null,
            estado: "Programado",
          },
        ].map((p) => ({ ...p, fecha_partido: "2026-04-01T00:00:00", ganador_corrido_id: null, es_walkover: false }))),
      ),
      http.get(`http://127.0.0.1:8000/api/v1/estadisticas/torneos/${TORNEO_ID}/resultados`, () => HttpResponse.json([])),
      http.get(EQUIPOS, () =>
        HttpResponse.json([
          { id: 1, nombre: "Tigres" },
          { id: 2, nombre: "Leones" },
          { id: 3, nombre: "Osos" },
          { id: 4, nombre: "Águilas" },
        ]),
      ),
    );
    renderPanel({ formato: "Eliminacion" });

    expect(await screen.findByText("Tigres")).toBeInTheDocument();
    expect(screen.getByText("Ganador Partido 1")).toBeInTheDocument();
    expect(screen.getByText("Ganador Partido 2")).toBeInTheDocument();
  });

  it("bracket completo: el botón dice 'Cerrar Torneo'", async () => {
    mockEstadoFase({
      fase_actual: { id: 1, nombre: "Eliminatoria", tipo: "Eliminacion", estado: "En_Curso" },
      partidos_total: 1,
      partidos_finalizados: 1,
      fase_completa: true,
      acciones_disponibles: ["cerrar_directo"],
    });
    server.use(http.get(`http://127.0.0.1:8000/api/v1/torneos/${TORNEO_ID}/bracket`, () => HttpResponse.json([])));
    renderPanel({ formato: "Eliminacion" });
    expect(await screen.findByRole("button", { name: "Cerrar Torneo" })).toBeInTheDocument();
  });
});

describe("MotorFormatosPanel — Grupos + Playoffs", () => {
  it("muestra Sortear Grupos cuando no hay grupos todavía", async () => {
    mockEstadoFase({ fase_actual: null });
    renderPanel({ formato: "Grupos_Playoffs" });
    expect(await screen.findByText("Sorteo pendiente.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sortear Grupos" })).toBeInTheDocument();
  });

  it("grupos en curso: sin botón de Generar Playoffs todavía", async () => {
    mockEstadoFase({
      fase_actual: { id: 1, nombre: "Fase de Grupos", tipo: "Grupos", estado: "En_Curso" },
      partidos_total: 2,
      partidos_finalizados: 1,
      partidos_pendientes: 1,
      fase_completa: false,
      acciones_disponibles: [],
    });
    renderPanel({ formato: "Grupos_Playoffs" });
    expect(await screen.findByText("1 jugado(s) · 0 cancelado(s) · 1 pendiente(s)")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Generar Playoffs" })).not.toBeInTheDocument();
  });

  it("Generar Playoffs abre el modal (no window.prompt) pre-cargado con clasificados_por_grupo, y persiste el override elegido", async () => {
    mockEstadoFase({
      fase_actual: { id: 1, nombre: "Fase de Grupos", tipo: "Grupos", estado: "En_Curso" },
      partidos_total: 2,
      partidos_finalizados: 2,
      fase_completa: true,
      acciones_disponibles: ["generar_playoffs"],
    });
    let cuerpoEnviado: { clasificados_por_grupo?: number } | undefined;
    server.use(
      http.get(TORNEO_URL, () =>
        HttpResponse.json({ id: TORNEO_ID, clasificados_por_grupo: 2, formato_eliminatoria: "Unico" }),
      ),
      http.post(`http://127.0.0.1:8000/api/v1/torneos/${TORNEO_ID}/playoffs`, async ({ request }) => {
        cuerpoEnviado = (await request.json()) as never;
        return HttpResponse.json({ id: 99, estado: "Pendiente" });
      }),
    );
    const user = userEvent.setup();
    renderPanel({ formato: "Grupos_Playoffs" });

    await user.click(await screen.findByRole("button", { name: "Generar Playoffs" }));

    const input = await screen.findByLabelText("Clasificados por grupo");
    await waitFor(() => expect(input).toHaveValue(2)); // pre-cargado desde el torneo

    await user.clear(input);
    await user.type(input, "1");
    const modal = input.closest(".modal-panel") as HTMLElement;
    await user.click(within(modal).getByRole("button", { name: "Generar Playoffs" }));

    await waitFor(() =>
      expect(cuerpoEnviado).toEqual({ clasificados_por_grupo: 1, formato_eliminatoria: "Unico" }),
    );
    // El modal se cierra al confirmar con éxito.
    expect(screen.queryByLabelText("Clasificados por grupo")).not.toBeInTheDocument();
  });

  it("el modal de Generar Playoffs rechaza un valor menor a 1", async () => {
    mockEstadoFase({
      fase_actual: { id: 1, nombre: "Fase de Grupos", tipo: "Grupos", estado: "En_Curso" },
      partidos_total: 2,
      partidos_finalizados: 2,
      fase_completa: true,
      acciones_disponibles: ["generar_playoffs"],
    });
    server.use(
      http.get(TORNEO_URL, () =>
        HttpResponse.json({ id: TORNEO_ID, clasificados_por_grupo: null, formato_eliminatoria: "Unico" }),
      ),
    );
    const user = userEvent.setup();
    renderPanel({ formato: "Grupos_Playoffs" });

    await user.click(await screen.findByRole("button", { name: "Generar Playoffs" }));
    const input = await screen.findByLabelText("Clasificados por grupo");
    await user.clear(input);
    await user.type(input, "0");

    const modal = input.closest(".modal-panel") as HTMLElement;
    expect(within(modal).getByRole("button", { name: "Generar Playoffs" })).toBeDisabled();
    expect(screen.getByText("Tiene que ser al menos 1.")).toBeInTheDocument();
  });
});
