import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "../../test/msw-server";
import { createWrapper } from "../../test/test-utils";
import { PlantillasAdminPage } from "./PlantillasAdmin";

const JUGADORES = "http://127.0.0.1:8000/api/v1/jugadores";
const EQUIPOS = "http://127.0.0.1:8000/api/v1/equipos";
const PLANTILLAS = "http://127.0.0.1:8000/api/v1/plantillas";

function renderPagina() {
  const Wrapper = createWrapper();
  return render(
    <Wrapper>
      <PlantillasAdminPage />
    </Wrapper>,
  );
}

describe("PlantillasAdminPage", () => {
  beforeEach(() => {
    server.use(
      http.get(JUGADORES, () => HttpResponse.json([{ id: 1, nombre: "Carlos Pérez" }])),
      http.get(EQUIPOS, () => HttpResponse.json([{ id: 1, nombre: "Tiburones FC" }])),
      http.get(PLANTILLAS, () =>
        HttpResponse.json([
          {
            id: 1,
            jugador_id: 1,
            equipo_id: 1,
            dorsal: 10,
            fecha_inicio: "2026-01-01",
            fecha_fin: null,
            estado: "Activo",
          },
        ]),
      ),
    );
  });

  it("resuelve nombres de jugador/equipo y muestra el dorsal", async () => {
    renderPagina();
    expect(await screen.findByText("Carlos Pérez")).toBeInTheDocument();
    expect(screen.getByText("Tiburones FC")).toBeInTheDocument();
    expect(screen.getByText("#10")).toBeInTheDocument();
  });

  it("'Dar de baja' abre el form de fecha_fin, no muta directo", async () => {
    const user = userEvent.setup();
    renderPagina();
    await screen.findByText("Carlos Pérez");

    await user.click(screen.getByRole("button", { name: "Dar de baja" }));

    // Todavía no mandó nada — solo se abrió el form pidiendo la fecha.
    expect(screen.getByLabelText("Fecha de baja")).toBeInTheDocument();
  });

  it("confirmar la baja llama a POST /plantillas/{id}/baja con fecha_fin en la query", async () => {
    const user = userEvent.setup();
    let queryFechaFin: string | null = null;
    server.use(
      http.post(`${PLANTILLAS}/1/baja`, ({ request }) => {
        queryFechaFin = new URL(request.url).searchParams.get("fecha_fin");
        return HttpResponse.json({
          id: 1,
          jugador_id: 1,
          equipo_id: 1,
          dorsal: 10,
          fecha_inicio: "2026-01-01",
          fecha_fin: "2026-06-01",
          estado: "Inactivo",
        });
      }),
    );
    renderPagina();
    await screen.findByText("Carlos Pérez");

    await user.click(screen.getByRole("button", { name: "Dar de baja" }));
    await user.type(screen.getByLabelText("Fecha de baja"), "2026-06-01");
    await user.click(screen.getByRole("button", { name: "Confirmar baja" }));

    await waitFor(() => expect(queryFechaFin).toBe("2026-06-01"));
  });
});
