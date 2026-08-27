import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "../../test/msw-server";
import { createWrapper } from "../../test/test-utils";
import { TraspasosAdminPage } from "./TraspasosAdmin";

const JUGADORES = "http://127.0.0.1:8000/api/v1/jugadores";
const DISCIPLINAS = "http://127.0.0.1:8000/api/v1/disciplinas";
const PERFILES = "http://127.0.0.1:8000/api/v1/perfiles";
const EQUIPOS = "http://127.0.0.1:8000/api/v1/equipos";
const TORNEOS = "http://127.0.0.1:8000/api/v1/torneos";
const INSCRIPCIONES = "http://127.0.0.1:8000/api/v1/inscripciones";
const TRASPASOS = "http://127.0.0.1:8000/api/v1/traspasos";

function renderPagina() {
  const Wrapper = createWrapper();
  return render(
    <Wrapper>
      <TraspasosAdminPage />
    </Wrapper>,
  );
}

describe("TraspasosAdminPage", () => {
  beforeEach(() => {
    server.use(
      http.get(JUGADORES, () => HttpResponse.json([{ id: 1, nombre: "Carlos Pérez" }])),
      http.get(DISCIPLINAS, () => HttpResponse.json([{ id: 1, nombre: "Fútbol" }])),
      http.get(PERFILES, () => HttpResponse.json([{ id: 1, jugador_id: 1, disciplina_id: 1 }])),
      http.get(EQUIPOS, () =>
        HttpResponse.json([
          { id: 1, nombre: "Tiburones FC" },
          { id: 2, nombre: "Águilas del Sur" },
        ]),
      ),
      http.get(TORNEOS, () => HttpResponse.json([{ id: 1, nombre: "Copa Ecotec 2026" }])),
      http.get(INSCRIPCIONES, () =>
        HttpResponse.json([
          { id: 1, torneo_id: 1, equipo_id: 1 },
          { id: 2, torneo_id: 1, equipo_id: 2 },
        ]),
      ),
      http.get(TRASPASOS, () =>
        HttpResponse.json([
          {
            id: 1,
            jugador_perfil_id: 1,
            inscripcion_origen_id: 1,
            inscripcion_destino_id: 2,
            dorsal_nuevo: 99,
            motivo: "Prueba",
            fecha_traspaso: "2026-02-01T10:00:00",
            estado: "Completado",
          },
        ]),
      ),
    );
  });

  it("lista traspasos con perfil/origen/destino resueltos", async () => {
    renderPagina();
    expect(await screen.findByText("Carlos Pérez — Fútbol")).toBeInTheDocument();
    expect(screen.getByText("Copa Ecotec 2026 — Tiburones FC → Copa Ecotec 2026 — Águilas del Sur")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Anular" })).toBeInTheDocument();
  });

  it("anular un traspaso llama a POST /traspasos/{id}/anular", async () => {
    const user = userEvent.setup();
    let llamado = false;
    server.use(
      http.post(`${TRASPASOS}/1/anular`, () => {
        llamado = true;
        return HttpResponse.json({
          id: 1,
          jugador_perfil_id: 1,
          inscripcion_origen_id: 1,
          inscripcion_destino_id: 2,
          dorsal_nuevo: 99,
          motivo: "Prueba",
          fecha_traspaso: "2026-02-01T10:00:00",
          estado: "Anulado",
        });
      }),
    );
    renderPagina();
    await screen.findByText("Carlos Pérez — Fútbol");

    await user.click(screen.getByRole("button", { name: "Anular" }));

    await waitFor(() => expect(llamado).toBe(true));
  });

  it("crear un traspaso desde libre (sin origen) manda inscripcion_origen_id null", async () => {
    const user = userEvent.setup();
    let bodyEnviado: unknown = null;
    server.use(
      http.post(TRASPASOS, async ({ request }) => {
        bodyEnviado = await request.json();
        return HttpResponse.json(
          {
            id: 2,
            jugador_perfil_id: 1,
            inscripcion_origen_id: null,
            inscripcion_destino_id: 1,
            dorsal_nuevo: null,
            motivo: null,
            fecha_traspaso: "2026-02-01T10:00:00",
            estado: "Completado",
          },
          { status: 201 },
        );
      }),
    );
    renderPagina();
    await screen.findByText("Carlos Pérez — Fútbol");

    await user.click(screen.getByRole("button", { name: "+ Nuevo traspaso" }));
    await user.selectOptions(screen.getByLabelText("Jugador — Disciplina"), "Carlos Pérez — Fútbol");
    await user.selectOptions(screen.getByLabelText("Equipo de destino"), "Copa Ecotec 2026 — Tiburones FC");
    await user.click(screen.getByRole("button", { name: "Traspasar" }));

    // El campo nunca se tocó en el form: ResourceForm no manda la clave en
    // absoluto (queda undefined, no null explícito) — el backend trata
    // ambos igual (Pydantic usa el default None), así que se compara con
    // == para no atarse a cuál de los dos manda el cliente.
    await waitFor(() => expect(bodyEnviado).toMatchObject({ jugador_perfil_id: 1, inscripcion_destino_id: 1 }));
    expect((bodyEnviado as { inscripcion_origen_id?: number | null }).inscripcion_origen_id).toBeFalsy();
  });
});
