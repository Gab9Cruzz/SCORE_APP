import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { server } from "../../../test/msw-server";
import { createWrapper } from "../../../test/test-utils";
import { TraspasosDelTorneoPage } from "./TraspasosDelTorneo";
import type { TorneoDashboardContext } from "./TorneoDashboard";

const CONTEXTO: TorneoDashboardContext = {
  torneoId: 20,
  torneoGrupoId: 7,
  disciplinaId: 1,
  modalidadId: null,
  torneoContexto: "Liga Relámpago — Edición 2",
};

vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useOutletContext: () => CONTEXTO };
});

const JUGADORES = "http://127.0.0.1:8000/api/v1/jugadores";
const PERFILES = "http://127.0.0.1:8000/api/v1/perfiles";
const EQUIPOS = "http://127.0.0.1:8000/api/v1/equipos";
const INSCRIPCIONES = "http://127.0.0.1:8000/api/v1/inscripciones";
const TRASPASOS = "http://127.0.0.1:8000/api/v1/traspasos";

function renderPagina() {
  const Wrapper = createWrapper();
  return render(
    <Wrapper>
      <TraspasosDelTorneoPage />
    </Wrapper>,
  );
}

function mockBase() {
  server.use(
    http.get(JUGADORES, () => HttpResponse.json([{ id: 1, nombre: "Carlos Pérez" }])),
    http.get(PERFILES, () => HttpResponse.json([{ id: 1, jugador_id: 1 }])),
    http.get(EQUIPOS, () =>
      HttpResponse.json([
        { id: 1, nombre: "Halcones FC" },
        { id: 2, nombre: "Tiburones FC" },
      ]),
    ),
    http.get(INSCRIPCIONES, () =>
      HttpResponse.json([
        { id: 5, equipo_id: 1 },
        { id: 6, equipo_id: 2 },
      ]),
    ),
    http.get(TRASPASOS, () => HttpResponse.json([])),
  );
}

describe("TraspasosDelTorneoPage", () => {
  it("resuelve jugador y equipos de origen/destino a nombres", async () => {
    mockBase();
    server.use(
      http.get(TRASPASOS, () =>
        HttpResponse.json([
          {
            id: 1,
            jugador_perfil_id: 1,
            inscripcion_origen_id: 5,
            inscripcion_destino_id: 6,
            motivo: "Prueba",
            fecha_traspaso: "2026-02-01T10:00:00",
            estado: "Completado",
          },
        ]),
      ),
    );
    renderPagina();

    expect(await screen.findByText("Carlos Pérez")).toBeInTheDocument();
    expect(screen.getByText("Halcones FC → Tiburones FC")).toBeInTheDocument();
  });

  it("crea un traspaso con los pickers ya acotados a este torneo", async () => {
    mockBase();
    let bodyRecibido: unknown;
    server.use(
      http.post(TRASPASOS, async ({ request }) => {
        bodyRecibido = await request.json();
        return HttpResponse.json({ id: 2, estado: "Completado" }, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderPagina();

    await user.click(await screen.findByRole("button", { name: "+ Nuevo traspaso" }));
    await user.selectOptions(await screen.findByLabelText("Jugador"), "1");
    await user.selectOptions(screen.getByLabelText("Equipo de destino"), "6");
    await user.click(screen.getByRole("button", { name: "Traspasar" }));

    await waitFor(() => expect(bodyRecibido).toMatchObject({ jugador_perfil_id: 1, inscripcion_destino_id: 6 }));
  });

  it("anular llama a POST /traspasos/{id}/anular", async () => {
    mockBase();
    server.use(
      http.get(TRASPASOS, () =>
        HttpResponse.json([
          {
            id: 1,
            jugador_perfil_id: 1,
            inscripcion_origen_id: 5,
            inscripcion_destino_id: 6,
            motivo: null,
            fecha_traspaso: "2026-02-01T10:00:00",
            estado: "Completado",
          },
        ]),
      ),
    );
    let llamado = false;
    server.use(
      http.post(`${TRASPASOS}/1/anular`, () => {
        llamado = true;
        return HttpResponse.json({ id: 1, estado: "Anulado" });
      }),
    );
    const user = userEvent.setup();
    renderPagina();

    await user.click(await screen.findByRole("button", { name: "Anular" }));

    await waitFor(() => expect(llamado).toBe(true));
  });
});
