import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "../../test/msw-server";
import { createWrapper } from "../../test/test-utils";
import { PartidosAdminPage } from "./PartidosAdmin";

const TORNEOS = "http://127.0.0.1:8000/api/v1/torneos";
const EQUIPOS = "http://127.0.0.1:8000/api/v1/equipos";
const INSCRIPCIONES = "http://127.0.0.1:8000/api/v1/inscripciones";
const PARTIDOS = "http://127.0.0.1:8000/api/v1/partidos";
const USUARIOS = "http://127.0.0.1:8000/api/v1/usuarios";

function renderPagina() {
  const Wrapper = createWrapper();
  return render(
    <Wrapper>
      <PartidosAdminPage />
    </Wrapper>,
  );
}

describe("PartidosAdminPage", () => {
  beforeEach(() => {
    server.use(
      http.get(TORNEOS, () => HttpResponse.json([{ id: 1, nombre: "Copa Ecotec 2026" }])),
      http.get(EQUIPOS, () =>
        HttpResponse.json([
          { id: 1, nombre: "Tiburones FC" },
          { id: 2, nombre: "Águilas del Sur" },
          { id: 3, nombre: "Halcones United" },
        ]),
      ),
      http.get(PARTIDOS, () => HttpResponse.json([])),
      http.get(USUARIOS, () =>
        HttpResponse.json([
          { id: 11, username: "arbitro1", nombre: "Árbitro Uno", rol: "Arbitro" },
        ]),
      ),
    );
  });

  it("crear: el picker de equipos está vacío hasta elegir un torneo", async () => {
    const user = userEvent.setup();
    // Solo el equipo 1 y 2 están inscritos en el torneo 1.
    server.use(
      http.get(INSCRIPCIONES, () =>
        HttpResponse.json([
          { id: 1, torneo_id: 1, equipo_id: 1, estado: "Inscrito" },
          { id: 2, torneo_id: 1, equipo_id: 2, estado: "Confirmado" },
        ]),
      ),
    );
    renderPagina();
    await screen.findByText("No hay partidos programados todavía.");

    await user.click(screen.getByRole("button", { name: "+ Nuevo" }));

    // Antes de elegir torneo, no hay picker de equipos en absoluto.
    expect(screen.queryByLabelText("Equipo local")).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Torneo"), "1");

    await waitFor(() => expect(screen.getByLabelText("Equipo local")).toBeInTheDocument());
    // Solo los 2 equipos inscritos aparecen — Halcones United (id 3, no
    // inscrito) no está en la lista. Acotado a "Equipo local": el mismo
    // texto aparece también en "Equipo visitante".
    const pickerLocal = within(screen.getByLabelText("Equipo local"));
    expect(pickerLocal.getByRole("option", { name: "Tiburones FC" })).toBeInTheDocument();
    expect(pickerLocal.getByRole("option", { name: "Águilas del Sur" })).toBeInTheDocument();
    expect(pickerLocal.queryByRole("option", { name: "Halcones United" })).not.toBeInTheDocument();
  });

  it("crear: no muestra arbitro_id en ningún momento (PartidoCreate no lo acepta, Fase 1 D6)", async () => {
    const user = userEvent.setup();
    server.use(
      http.get(INSCRIPCIONES, () =>
        HttpResponse.json([
          { id: 1, torneo_id: 1, equipo_id: 1, estado: "Inscrito" },
          { id: 2, torneo_id: 1, equipo_id: 2, estado: "Confirmado" },
        ]),
      ),
    );
    renderPagina();
    await screen.findByText("No hay partidos programados todavía.");

    await user.click(screen.getByRole("button", { name: "+ Nuevo" }));
    await user.selectOptions(screen.getByLabelText("Torneo"), "1");
    await waitFor(() => expect(screen.getByLabelText("Equipo local")).toBeInTheDocument());

    expect(screen.queryByLabelText("Árbitro asignado")).not.toBeInTheDocument();
  });

  it("editar: muestra el picker de árbitro, poblado solo con usuarios rol=Arbitro", async () => {
    const user = userEvent.setup();
    server.use(
      http.get(PARTIDOS, () =>
        HttpResponse.json([
          {
            id: 5,
            torneo_id: 1,
            equipos_id_local: 1,
            equipos_id_visitante: 2,
            fecha_partido: "2026-02-05T16:00:00",
            jornada: 4,
            fase: "Regular",
            grupo: null,
            estado: "Programado",
            arbitro_id: null,
          },
        ]),
      ),
    );
    let usuariosQuery: string | null = null;
    server.use(
      http.get(USUARIOS, ({ request }) => {
        usuariosQuery = new URL(request.url).search;
        return HttpResponse.json([{ id: 11, username: "arbitro1", nombre: "Árbitro Uno", rol: "Arbitro" }]);
      }),
    );
    renderPagina();
    await screen.findByText(/Tiburones FC vs Águilas del Sur/);

    await user.click(screen.getByRole("button", { name: "Editar" }));

    expect(await screen.findByLabelText("Árbitro asignado")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Árbitro Uno (arbitro1)" })).toBeInTheDocument();
    // El picker pide explícitamente rol=Arbitro — server-side esto ya se
    // fuerza para TorneoAdmin (D5), pero para AdminGeneral no, así que el
    // cliente lo tiene que pedir igual.
    expect(usuariosQuery).toContain("rol=Arbitro");
  });

  it("baja (cancelar) hace DELETE, no PATCH — a diferencia de Inscripciones/Plantillas", async () => {
    const user = userEvent.setup();
    let deleteHit = false;
    server.use(
      http.get(PARTIDOS, () =>
        HttpResponse.json([
          {
            id: 5,
            torneo_id: 1,
            equipos_id_local: 1,
            equipos_id_visitante: 2,
            fecha_partido: "2026-02-05T16:00:00",
            jornada: 4,
            fase: "Regular",
            grupo: null,
            estado: "Programado",
            arbitro_id: null,
          },
        ]),
      ),
      http.delete(`${PARTIDOS}/5`, () => {
        deleteHit = true;
        return HttpResponse.json({ id: 5, estado: "Cancelado" });
      }),
    );
    renderPagina();
    await screen.findByText(/Tiburones FC vs Águilas del Sur/);

    await user.click(screen.getByRole("button", { name: "Cancelar" }));

    await waitFor(() => expect(deleteHit).toBe(true));
  });
});
