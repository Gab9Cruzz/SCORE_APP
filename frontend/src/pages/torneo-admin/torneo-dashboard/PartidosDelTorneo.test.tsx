import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { server } from "../../../test/msw-server";
import { createWrapper } from "../../../test/test-utils";
import { PartidosDelTorneoPage } from "./PartidosDelTorneo";
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

const EQUIPOS = "http://127.0.0.1:8000/api/v1/equipos";
const INSCRIPCIONES = "http://127.0.0.1:8000/api/v1/inscripciones";
const PARTIDOS = "http://127.0.0.1:8000/api/v1/partidos";
const USUARIOS = "http://127.0.0.1:8000/api/v1/usuarios";

function renderPagina() {
  const Wrapper = createWrapper();
  return render(
    <Wrapper>
      <PartidosDelTorneoPage />
    </Wrapper>,
  );
}

function mockBase() {
  server.use(
    http.get(EQUIPOS, () =>
      HttpResponse.json([
        { id: 1, nombre: "Halcones FC" },
        { id: 2, nombre: "Tiburones FC" },
      ]),
    ),
    http.get(INSCRIPCIONES, () =>
      HttpResponse.json([
        { id: 5, equipo_id: 1, estado: "Inscrito" },
        { id: 6, equipo_id: 2, estado: "Inscrito" },
      ]),
    ),
    http.get(PARTIDOS, () => HttpResponse.json([])),
    http.get(USUARIOS, () => HttpResponse.json([])),
  );
}

describe("PartidosDelTorneoPage", () => {
  it("crea un partido con torneo_id fijo (no se pregunta), sin selector de Torneo", async () => {
    mockBase();
    let bodyRecibido: unknown;
    server.use(
      http.post(PARTIDOS, async ({ request }) => {
        bodyRecibido = await request.json();
        return HttpResponse.json({ id: 1 }, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderPagina();

    await user.click(await screen.findByRole("button", { name: "+ Nuevo" }));
    expect(screen.queryByLabelText("Torneo")).not.toBeInTheDocument();
    await user.selectOptions(await screen.findByLabelText("Equipo local"), "1");
    await user.selectOptions(screen.getByLabelText("Equipo visitante"), "2");
    await user.type(screen.getByLabelText("Fecha y hora"), "2026-05-01T16:00");
    await user.click(screen.getByRole("button", { name: "Crear partido" }));

    await waitFor(() =>
      expect(bodyRecibido).toMatchObject({ torneo_id: 20, equipos_id_local: 1, equipos_id_visitante: 2 }),
    );
  });

  it("lista partidos sin columna de Torneo (ya se sabe cuál es)", async () => {
    mockBase();
    server.use(
      http.get(PARTIDOS, () =>
        HttpResponse.json([
          {
            id: 1,
            equipos_id_local: 1,
            equipos_id_visitante: 2,
            fecha_partido: "2026-05-01T16:00:00",
            jornada: 1,
            fase: "Regular",
            grupo: null,
            estado: "Programado",
            arbitro_id: null,
          },
        ]),
      ),
    );
    renderPagina();
    expect(await screen.findByText("Halcones FC vs Tiburones FC")).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Torneo" })).not.toBeInTheDocument();
  });
});
