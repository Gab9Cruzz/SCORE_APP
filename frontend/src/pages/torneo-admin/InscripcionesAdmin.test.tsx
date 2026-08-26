import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "../../test/msw-server";
import { createWrapper } from "../../test/test-utils";
import { InscripcionesAdminPage } from "./InscripcionesAdmin";

const TORNEOS = "http://127.0.0.1:8000/api/v1/torneos";
const EQUIPOS = "http://127.0.0.1:8000/api/v1/equipos";
const INSCRIPCIONES = "http://127.0.0.1:8000/api/v1/inscripciones";

function renderPagina() {
  const Wrapper = createWrapper();
  return render(
    <Wrapper>
      <InscripcionesAdminPage />
    </Wrapper>,
  );
}

describe("InscripcionesAdminPage", () => {
  beforeEach(() => {
    server.use(
      http.get(TORNEOS, () => HttpResponse.json([{ id: 1, nombre: "Copa Ecotec 2026" }])),
      http.get(EQUIPOS, () =>
        HttpResponse.json([
          { id: 1, nombre: "Tiburones FC" },
          { id: 2, nombre: "Águilas del Sur" },
        ]),
      ),
      http.get(INSCRIPCIONES, () =>
        HttpResponse.json([{ id: 1, torneo_id: 1, equipo_id: 1, estado: "Inscrito", fecha: "2026-01-01T00:00:00" }]),
      ),
    );
  });

  it("resuelve los nombres de torneo/equipo en la lista, no muestra los IDs crudos", async () => {
    renderPagina();
    expect(await screen.findByText("Copa Ecotec 2026")).toBeInTheDocument();
    expect(screen.getByText("Tiburones FC")).toBeInTheDocument();
  });

  it("crear: los pickers de torneo y equipo son selects de referencia", async () => {
    const user = userEvent.setup();
    renderPagina();
    await screen.findByText("Copa Ecotec 2026");

    await user.click(screen.getByRole("button", { name: "+ Nueva" }));

    expect(screen.getByRole("option", { name: "Copa Ecotec 2026" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Águilas del Sur" })).toBeInTheDocument();
  });

  it('"Cancelar" hace PATCH a estado=Cancelado, no DELETE', async () => {
    const user = userEvent.setup();
    let patchBody: unknown = null;
    let deleteCalled = false;
    server.use(
      http.patch(`${INSCRIPCIONES}/1`, async ({ request }) => {
        patchBody = await request.json();
        return HttpResponse.json({ id: 1, torneo_id: 1, equipo_id: 1, estado: "Cancelado", fecha: "2026-01-01T00:00:00" });
      }),
      http.delete(`${INSCRIPCIONES}/1`, () => {
        deleteCalled = true;
        return HttpResponse.json({});
      }),
    );
    renderPagina();
    await screen.findByText("Tiburones FC");

    await user.click(screen.getByRole("button", { name: "Cancelar" }));

    await waitFor(() => expect(patchBody).toEqual({ estado: "Cancelado" }));
    expect(deleteCalled).toBe(false);
  });
});
