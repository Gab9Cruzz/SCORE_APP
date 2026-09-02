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
  modalidadId: 1,
  torneoContexto: "Liga Relámpago — Edición 2",
  formato: "Liga",
  incluyeTercerLugar: true,
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

  describe("walkover (3B-13)", () => {
    const PARTIDO_PROGRAMADO = {
      id: 1,
      equipos_id_local: 1,
      equipos_id_visitante: 2,
      fecha_partido: "2026-05-01T16:00:00",
      jornada: 1,
      fase: "Regular",
      grupo: null,
      estado: "Programado",
      arbitro_id: null,
    };

    it("'Walkover' pide quién no se presentó y manda el equipo elegido", async () => {
      mockBase();
      server.use(http.get(PARTIDOS, () => HttpResponse.json([PARTIDO_PROGRAMADO])));
      let cuerpoRecibido: unknown;
      server.use(
        http.post("http://127.0.0.1:8000/api/v1/partidos/1/walkover", async ({ request }) => {
          cuerpoRecibido = await request.json();
          return HttpResponse.json({ ...PARTIDO_PROGRAMADO, estado: "Finalizado", es_walkover: true, walkover_equipo_ausente_id: 1 });
        }),
      );
      const user = userEvent.setup();
      renderPagina();
      await screen.findByText("Halcones FC vs Tiburones FC");

      await user.click(screen.getByRole("button", { name: "Walkover" }));
      expect(screen.getByText("¿Quién no se presentó?")).toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: "Halcones FC" }));

      await waitFor(() => expect(cuerpoRecibido).toEqual({ equipo_ausente_id: 1 }));
    });

    it("no ofrece 'Walkover' en un partido ya Finalizado", async () => {
      mockBase();
      server.use(
        http.get(PARTIDOS, () => HttpResponse.json([{ ...PARTIDO_PROGRAMADO, estado: "Finalizado" }])),
      );
      renderPagina();
      await screen.findByText("Halcones FC vs Tiburones FC");

      expect(screen.queryByRole("button", { name: "Walkover" })).not.toBeInTheDocument();
    });

    it("muestra el badge W.O. en un partido cerrado por walkover", async () => {
      mockBase();
      server.use(
        http.get(PARTIDOS, () =>
          HttpResponse.json([{ ...PARTIDO_PROGRAMADO, estado: "Finalizado", es_walkover: true, walkover_equipo_ausente_id: 1 }]),
        ),
      );
      renderPagina();
      await screen.findByText("Halcones FC vs Tiburones FC");

      expect(await screen.findByText("W.O.")).toBeInTheDocument();
    });
  });
});
