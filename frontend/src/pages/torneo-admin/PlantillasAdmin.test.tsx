import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "../../test/msw-server";
import { createWrapper } from "../../test/test-utils";
import { PlantillasAdminPage } from "./PlantillasAdmin";

const JUGADORES = "http://127.0.0.1:8000/api/v1/jugadores";
const DISCIPLINAS = "http://127.0.0.1:8000/api/v1/disciplinas";
const PERFILES = "http://127.0.0.1:8000/api/v1/perfiles";
const EQUIPOS = "http://127.0.0.1:8000/api/v1/equipos";
const TORNEOS = "http://127.0.0.1:8000/api/v1/torneos";
const INSCRIPCIONES = "http://127.0.0.1:8000/api/v1/inscripciones";
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
      http.get(DISCIPLINAS, () => HttpResponse.json([{ id: 1, nombre: "Fútbol" }])),
      http.get(PERFILES, () => HttpResponse.json([{ id: 1, jugador_id: 1, disciplina_id: 1 }])),
      http.get(EQUIPOS, () => HttpResponse.json([{ id: 1, nombre: "Tiburones FC" }])),
      http.get(TORNEOS, () => HttpResponse.json([{ id: 1, nombre: "Copa Ecotec 2026" }])),
      http.get(INSCRIPCIONES, () => HttpResponse.json([{ id: 1, torneo_id: 1, equipo_id: 1 }])),
      http.get(PLANTILLAS, () =>
        HttpResponse.json([
          {
            id: 1,
            jugador_perfil_id: 1,
            inscripcion_torneo_id: 1,
            dorsal: 10,
            fecha_inicio: "2026-01-01",
            fecha_fin: null,
            estado: "Activo",
          },
        ]),
      ),
    );
  });

  it("resuelve perfil/inscripción a nombres y muestra el dorsal", async () => {
    renderPagina();
    expect(await screen.findByText("Carlos Pérez — Fútbol")).toBeInTheDocument();
    expect(screen.getByText("Copa Ecotec 2026 — Tiburones FC")).toBeInTheDocument();
    expect(screen.getByText("#10")).toBeInTheDocument();
  });

  it("'Dar de baja' abre el form de fecha_fin, no muta directo", async () => {
    const user = userEvent.setup();
    renderPagina();
    await screen.findByText("Carlos Pérez — Fútbol");

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
          jugador_perfil_id: 1,
          inscripcion_torneo_id: 1,
          dorsal: 10,
          fecha_inicio: "2026-01-01",
          fecha_fin: "2026-06-01",
          estado: "Inactivo",
        });
      }),
    );
    renderPagina();
    await screen.findByText("Carlos Pérez — Fútbol");

    await user.click(screen.getByRole("button", { name: "Dar de baja" }));
    await user.type(screen.getByLabelText("Fecha de baja"), "2026-06-01");
    await user.click(screen.getByRole("button", { name: "Confirmar baja" }));

    await waitFor(() => expect(queryFechaFin).toBe("2026-06-01"));
  });

  it("crear un vínculo para un jugador SIN perfil todavía crea el perfil primero", async () => {
    const user = userEvent.setup();
    let perfilCreado: unknown = null;
    let vinculoCreado: unknown = null;
    server.use(
      // Segundo jugador, sin perfil de ninguna disciplina todavía.
      http.get(JUGADORES, () =>
        HttpResponse.json([
          { id: 1, nombre: "Carlos Pérez" },
          { id: 2, nombre: "Fichaje Nuevo" },
        ]),
      ),
      http.post(PERFILES, async ({ request }) => {
        perfilCreado = await request.json();
        return HttpResponse.json({ id: 2, jugador_id: 2, disciplina_id: 1 }, { status: 201 });
      }),
      http.post(PLANTILLAS, async ({ request }) => {
        vinculoCreado = await request.json();
        return HttpResponse.json(
          {
            id: 2,
            jugador_perfil_id: 2,
            inscripcion_torneo_id: 1,
            dorsal: 7,
            fecha_inicio: "2026-02-01",
            fecha_fin: null,
            estado: "Activo",
          },
          { status: 201 },
        );
      }),
    );
    renderPagina();
    await screen.findByText("Carlos Pérez — Fútbol");

    await user.click(screen.getByRole("button", { name: "+ Nuevo vínculo" }));
    await user.selectOptions(screen.getByLabelText("Jugador"), "2");
    await user.selectOptions(screen.getByLabelText("Disciplina"), "1");
    await user.selectOptions(screen.getByLabelText("Torneo — Equipo"), "1");
    await user.type(screen.getByLabelText("Dorsal"), "7");
    await user.type(screen.getByLabelText("Fecha de inicio"), "2026-02-01");
    await user.click(screen.getByRole("button", { name: "Vincular" }));

    await waitFor(() => expect(perfilCreado).toEqual({ jugador_id: 2, disciplina_id: 1 }));
    await waitFor(() =>
      expect(vinculoCreado).toEqual({
        jugador_perfil_id: 2,
        inscripcion_torneo_id: 1,
        dorsal: 7,
        fecha_inicio: "2026-02-01",
      }),
    );
  });
});
