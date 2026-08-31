import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "../../../test/msw-server";
import { createWrapper } from "../../../test/test-utils";
import { MotorFormatosPanel } from "./MotorFormatosPanel";

const EQUIPOS = "http://127.0.0.1:8000/api/v1/equipos";
const TORNEO_ID = 20;

function renderPanel(props: Partial<Parameters<typeof MotorFormatosPanel>[0]> = {}) {
  const Wrapper = createWrapper();
  return render(
    <Wrapper>
      <MotorFormatosPanel
        torneoId={TORNEO_ID}
        formato="Liga"
        partidos={[]}
        equiposInscritosCount={4}
        {...props}
      />
    </Wrapper>,
  );
}

describe("MotorFormatosPanel — Liga", () => {
  it("muestra Generar Fixture cuando no hay calendario todavía", async () => {
    renderPanel({ formato: "Liga", partidos: [] });
    expect(await screen.findByText("Aún no se generó el calendario.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generar Fixture" })).toBeInTheDocument();
  });

  it("no muestra nada si el fixture ya se generó (partidos con fase_id)", () => {
    renderPanel({ formato: "Liga", partidos: [{ fase_id: 1, grupo_id: null, estado: "Programado" }] });
    expect(screen.queryByText("Aún no se generó el calendario.")).not.toBeInTheDocument();
  });

  it("Generar Fixture llama a POST /torneos/{id}/fixture", async () => {
    let llamado = false;
    server.use(
      http.post(`http://127.0.0.1:8000/api/v1/torneos/${TORNEO_ID}/fixture`, () => {
        llamado = true;
        return HttpResponse.json({ id: 1, estado: "En_Curso" });
      }),
    );
    const user = userEvent.setup();
    renderPanel({ formato: "Liga", partidos: [] });
    await user.click(await screen.findByRole("button", { name: "Generar Fixture" }));
    await waitFor(() => expect(llamado).toBe(true));
  });
});

describe("MotorFormatosPanel — Eliminación", () => {
  it("muestra Hacer Sorteo cuando no hay bracket todavía", async () => {
    renderPanel({ formato: "Eliminacion", partidos: [] });
    expect(await screen.findByText("Aún no se hizo el sorteo.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Hacer Sorteo" })).toBeInTheDocument();
  });

  // T46 — una casilla sin equipo dice "Ganador Partido N", nunca queda
  // en blanco sin explicación.
  it("el bracket muestra 'Ganador Partido N' en casillas sin equipo aún", async () => {
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
            estado: "Programado",
          },
        ]),
      ),
      http.get(EQUIPOS, () =>
        HttpResponse.json([
          { id: 1, nombre: "Tigres" },
          { id: 2, nombre: "Leones" },
          { id: 3, nombre: "Osos" },
          { id: 4, nombre: "Águilas" },
        ]),
      ),
    );
    renderPanel({ formato: "Eliminacion", partidos: [{ fase_id: 1, grupo_id: null, estado: "Programado" }] });

    expect(await screen.findByText("Tigres")).toBeInTheDocument();
    expect(screen.getByText("Ganador Partido 1")).toBeInTheDocument();
    expect(screen.getByText("Ganador Partido 2")).toBeInTheDocument();
  });
});

describe("MotorFormatosPanel — Grupos + Playoffs", () => {
  it("muestra Sortear Grupos cuando no hay grupos todavía", async () => {
    renderPanel({ formato: "Grupos_Playoffs", partidos: [] });
    expect(await screen.findByText("Fase de Grupos: sorteo pendiente.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sortear Grupos" })).toBeInTheDocument();
  });

  it("muestra Generar Playoffs solo cuando todos los partidos de grupos terminaron", async () => {
    const { rerender } = renderPanel({
      formato: "Grupos_Playoffs",
      partidos: [
        { fase_id: 1, grupo_id: 10, estado: "Programado" },
        { fase_id: 1, grupo_id: 10, estado: "Finalizado" },
      ],
    });
    expect(await screen.findByText(/en curso/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Generar Playoffs" })).not.toBeInTheDocument();

    const Wrapper = createWrapper();
    rerender(
      <Wrapper>
        <MotorFormatosPanel
          torneoId={TORNEO_ID}
          formato="Grupos_Playoffs"
          partidos={[
            { fase_id: 1, grupo_id: 10, estado: "Finalizado" },
            { fase_id: 1, grupo_id: 10, estado: "Finalizado" },
          ]}
          equiposInscritosCount={4}
        />
      </Wrapper>,
    );
    expect(await screen.findByText("Fase de Grupos: terminada.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generar Playoffs" })).toBeInTheDocument();
  });
});
