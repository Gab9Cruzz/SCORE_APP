import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { server } from "../../../test/msw-server";
import { createWrapper } from "../../../test/test-utils";
import { EquiposDelTorneoPage } from "./EquiposDelTorneo";
import type { TorneoDashboardContext } from "./TorneoDashboard";

const CONTEXTO: TorneoDashboardContext = {
  torneoId: 20,
  torneoGrupoId: 7,
  disciplinaId: 1,
  modalidadId: 1,
  torneoContexto: "Liga Relámpago — Edición 2",
};

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => mockNavigate, useOutletContext: () => CONTEXTO };
});

const INSCRIPCIONES = "http://127.0.0.1:8000/api/v1/inscripciones";
const EQUIPOS = "http://127.0.0.1:8000/api/v1/equipos";
const PLANTILLAS = "http://127.0.0.1:8000/api/v1/plantillas";
const MODALIDADES = "http://127.0.0.1:8000/api/v1/modalidades";

// Conjunto (tamano_equipo > 2, ej. Fútbol 11) — id coincide con
// CONTEXTO.modalidadId. Los tests de Individual/Pareja viven en
// EquiposDelTorneo.test.tsx aparte no hace falta: la ramificación por
// tamano_equipo ya está cubierta a nivel de unidad en
// ModalAgregarInscripcion.test.tsx; acá solo se cubre que este archivo
// resuelve la Modalidad del torneo antes de decidir qué vista mostrar.
const MODALIDAD_CONJUNTO = [{ id: 1, tamano_equipo: 11 }];

function renderPagina() {
  const Wrapper = createWrapper();
  return render(
    <Wrapper>
      <EquiposDelTorneoPage />
    </Wrapper>,
  );
}

describe("EquiposDelTorneoPage — Pareja/Conjunto (tamano_equipo >= 2)", () => {
  it("lista equipos inscritos con la cantidad de jugadores activos", async () => {
    server.use(
      http.get(INSCRIPCIONES, () => HttpResponse.json([{ id: 1, torneo_id: 20, equipo_id: 1, jugador_perfil_id: null, estado: "Inscrito" }])),
      http.get(EQUIPOS, () => HttpResponse.json([{ id: 1, nombre: "Halcones FC" }])),
      http.get(MODALIDADES, () => HttpResponse.json(MODALIDAD_CONJUNTO)),
      http.get(PLANTILLAS, () =>
        HttpResponse.json([
          { id: 1, inscripcion_torneo_id: 1, estado: "Activo" },
          { id: 2, inscripcion_torneo_id: 1, estado: "Activo" },
          { id: 3, inscripcion_torneo_id: 1, estado: "Traspasado" },
        ]),
      ),
    );
    renderPagina();

    expect(await screen.findByText("Equipos inscritos")).toBeInTheDocument();
    expect(await screen.findByText("Halcones FC")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument(); // solo cuenta Activo
  });

  // Fase 3 del plan: reemplaza a la extinta pestaña global Inscripciones —
  // "Cancelar inscripción" es el mismo PATCH {estado: "Cancelado"} directo.
  it("Cancelar inscripción manda PATCH {estado: Cancelado}", async () => {
    server.use(
      http.get(INSCRIPCIONES, () => HttpResponse.json([{ id: 1, torneo_id: 20, equipo_id: 1, jugador_perfil_id: null, estado: "Inscrito" }])),
      http.get(EQUIPOS, () => HttpResponse.json([{ id: 1, nombre: "Halcones FC" }])),
      http.get(MODALIDADES, () => HttpResponse.json(MODALIDAD_CONJUNTO)),
      http.get(PLANTILLAS, () => HttpResponse.json([])),
    );
    let bodyRecibido: unknown;
    server.use(
      http.patch(`${INSCRIPCIONES}/1`, async ({ request }) => {
        bodyRecibido = await request.json();
        return HttpResponse.json({ id: 1, torneo_id: 20, equipo_id: 1, estado: "Cancelado" });
      }),
    );
    const user = userEvent.setup();
    renderPagina();

    await user.click(await screen.findByRole("button", { name: "Cancelar inscripción" }));

    await waitFor(() => expect(bodyRecibido).toEqual({ estado: "Cancelado" }));
  });

  it("+ Agregar jugadores navega al registro por lote con el equipo ya resuelto", async () => {
    server.use(
      http.get(INSCRIPCIONES, () => HttpResponse.json([{ id: 1, torneo_id: 20, equipo_id: 1, jugador_perfil_id: null, estado: "Inscrito" }])),
      http.get(EQUIPOS, () => HttpResponse.json([{ id: 1, nombre: "Halcones FC" }])),
      http.get(MODALIDADES, () => HttpResponse.json(MODALIDAD_CONJUNTO)),
      http.get(PLANTILLAS, () => HttpResponse.json([])),
    );
    const user = userEvent.setup();
    renderPagina();

    await user.click(await screen.findByRole("button", { name: "+ Agregar jugadores" }));

    expect(mockNavigate).toHaveBeenCalledWith("/torneo-admin/plantillas/lote", {
      state: {
        inscripcionTorneoId: 1,
        contexto: "Halcones FC — Liga Relámpago — Edición 2",
        volverA: "/torneo-admin/torneos/20/equipos",
      },
    });
  });
});

describe("EquiposDelTorneoPage — Individual (tamano_equipo == 1)", () => {
  const MODALIDAD_INDIVIDUAL = [{ id: 1, tamano_equipo: 1 }];
  const PERFILES = "http://127.0.0.1:8000/api/v1/perfiles";
  const JUGADORES = "http://127.0.0.1:8000/api/v1/jugadores";

  it("lista jugadores inscritos por nombre, sin ningún Equipo de por medio", async () => {
    server.use(
      http.get(INSCRIPCIONES, () =>
        HttpResponse.json([{ id: 1, torneo_id: 20, equipo_id: null, jugador_perfil_id: 5, estado: "Inscrito" }]),
      ),
      http.get(MODALIDADES, () => HttpResponse.json(MODALIDAD_INDIVIDUAL)),
      http.get(PERFILES, () => HttpResponse.json([{ id: 5, jugador_id: 9 }])),
      http.get(JUGADORES, () => HttpResponse.json([{ id: 9, nombre: "Micky Fernández" }])),
    );
    renderPagina();

    expect(await screen.findByText("Jugadores inscritos")).toBeInTheDocument();
    expect(await screen.findByText("Micky Fernández")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "+ Agregar Jugador" })).toBeInTheDocument();
  });
});
