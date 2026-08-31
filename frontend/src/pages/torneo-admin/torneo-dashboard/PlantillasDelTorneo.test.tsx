import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { server } from "../../../test/msw-server";
import { createWrapper } from "../../../test/test-utils";
import { PlantillasDelTorneoPage } from "./PlantillasDelTorneo";
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

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => mockNavigate, useOutletContext: () => CONTEXTO };
});

const JUGADORES = "http://127.0.0.1:8000/api/v1/jugadores";
const PERFILES = "http://127.0.0.1:8000/api/v1/perfiles";
const EQUIPOS = "http://127.0.0.1:8000/api/v1/equipos";
const INSCRIPCIONES = "http://127.0.0.1:8000/api/v1/inscripciones";
const PLANTILLAS = "http://127.0.0.1:8000/api/v1/plantillas";
const DISCIPLINAS = "http://127.0.0.1:8000/api/v1/disciplinas";
const MODALIDADES = "http://127.0.0.1:8000/api/v1/modalidades";

function renderPagina() {
  const Wrapper = createWrapper();
  return render(
    <Wrapper>
      <PlantillasDelTorneoPage />
    </Wrapper>,
  );
}

function mockBase() {
  server.use(
    http.get(DISCIPLINAS, () => HttpResponse.json([{ id: 1, nombre: "Fútbol", estado: "Activo", orden_popularidad: 1 }])),
    http.get(MODALIDADES, () => HttpResponse.json([])),
    http.get(JUGADORES, () => HttpResponse.json([{ id: 1, nombre: "Carlos Pérez", foto_url: null }])),
    http.get(PERFILES, () => HttpResponse.json([{ id: 1, jugador_id: 1, disciplina_id: 1 }])),
    http.get(EQUIPOS, () => HttpResponse.json([{ id: 1, nombre: "Halcones FC" }])),
    http.get(INSCRIPCIONES, () => HttpResponse.json([{ id: 5, equipo_id: 1 }])),
    http.get(PLANTILLAS, () =>
      HttpResponse.json([
        {
          id: 1,
          jugador_perfil_id: 1,
          inscripcion_torneo_id: 5,
          dorsal: 10,
          fecha_inicio: "2026-01-01",
          fecha_fin: null,
          estado: "Activo",
        },
      ]),
    ),
  );
}

describe("PlantillasDelTorneoPage — grid de tarjetas (Design sección D)", () => {
  // T32 — el grid agrupa por equipo, foto+dorsal por tarjeta.
  it("agrupa las tarjetas por equipo, con dorsal en cada una", async () => {
    mockBase();
    renderPagina();

    expect(await screen.findByText(/Halcones FC/)).toBeInTheDocument();
    expect(screen.getByText("1 jugador)", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("Carlos Pérez")).toBeInTheDocument();
    expect(screen.getByText("#10")).toBeInTheDocument();
  });

  // T32 — jugador sin Foto_URL muestra iniciales, no un ícono roto.
  it("un jugador sin foto muestra sus iniciales en el avatar", async () => {
    mockBase();
    renderPagina();

    await screen.findByText("Carlos Pérez");
    expect(screen.getByText("CP")).toBeInTheDocument();
  });

  it("un equipo sin jugadores muestra el mensaje con link a Equipos, no una tarjeta vacía", async () => {
    server.use(
      http.get(DISCIPLINAS, () => HttpResponse.json([{ id: 1, nombre: "Fútbol", estado: "Activo", orden_popularidad: 1 }])),
      http.get(MODALIDADES, () => HttpResponse.json([])),
      http.get(JUGADORES, () => HttpResponse.json([])),
      http.get(PERFILES, () => HttpResponse.json([])),
      http.get(EQUIPOS, () => HttpResponse.json([{ id: 1, nombre: "Halcones FC" }])),
      http.get(INSCRIPCIONES, () => HttpResponse.json([{ id: 5, equipo_id: 1 }])),
      http.get(PLANTILLAS, () => HttpResponse.json([])),
    );
    renderPagina();

    expect(await screen.findByText(/Halcones FC/)).toBeInTheDocument();
    expect(screen.getByText("Sin jugadores todavía —", { exact: false })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ir a Equipos para agregar" })).toHaveAttribute(
      "href",
      "/torneo-admin/torneos/20/equipos",
    );
  });

  it("torneo sin equipos matriculados muestra el mensaje de listado vacío", async () => {
    server.use(
      http.get(DISCIPLINAS, () => HttpResponse.json([{ id: 1, nombre: "Fútbol", estado: "Activo", orden_popularidad: 1 }])),
      http.get(MODALIDADES, () => HttpResponse.json([])),
      http.get(JUGADORES, () => HttpResponse.json([])),
      http.get(PERFILES, () => HttpResponse.json([])),
      http.get(EQUIPOS, () => HttpResponse.json([])),
      http.get(INSCRIPCIONES, () => HttpResponse.json([])),
      http.get(PLANTILLAS, () => HttpResponse.json([])),
    );
    renderPagina();

    expect(await screen.findByText(/Todavía no hay equipos matriculados/)).toBeInTheDocument();
  });

  it("nuevo vínculo para un jugador SIN perfil todavía crea el perfil con la disciplina del torneo, sin preguntarla", async () => {
    mockBase();
    let perfilCreado: unknown = null;
    let vinculoCreado: unknown = null;
    server.use(
      http.get(JUGADORES, () => HttpResponse.json([{ id: 2, nombre: "Jugador Nuevo", foto_url: null }])),
      http.get(PERFILES, () => HttpResponse.json([])), // sin perfil todavía
      http.post(PERFILES, async ({ request }) => {
        perfilCreado = await request.json();
        return HttpResponse.json({ id: 9, jugador_id: 2, disciplina_id: 1 }, { status: 201 });
      }),
      http.post(PLANTILLAS, async ({ request }) => {
        vinculoCreado = await request.json();
        return HttpResponse.json({ id: 2 }, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderPagina();

    await user.click(await screen.findByRole("button", { name: "+ Nuevo vínculo" }));
    // No hay campo de Disciplina en este formulario — la fija el torneo.
    expect(screen.queryByLabelText("Disciplina")).not.toBeInTheDocument();
    await user.selectOptions(await screen.findByLabelText("Jugador"), "2");
    await user.selectOptions(screen.getByLabelText("Equipo"), "5");
    await user.type(screen.getByLabelText("Fecha de inicio"), "2026-02-01");
    await user.click(screen.getByRole("button", { name: "Vincular" }));

    await waitFor(() => expect(perfilCreado).toEqual({ jugador_id: 2, disciplina_id: 1 }));
    expect(vinculoCreado).toMatchObject({ jugador_perfil_id: 9, inscripcion_torneo_id: 5 });
  });

  it("+ Registro por lote navega con alcance de torneo (sin equipo pre-resuelto)", async () => {
    mockBase();
    const user = userEvent.setup();
    renderPagina();

    await user.click(await screen.findByRole("button", { name: "+ Registro por lote" }));

    expect(mockNavigate).toHaveBeenCalledWith("/torneo-admin/plantillas/lote", {
      state: { torneoId: 20, volverA: "/torneo-admin/torneos/20/plantillas" },
    });
  });

  it("Dar de baja (desde la tarjeta) llama a POST /plantillas/{id}/baja con fecha_fin en la query", async () => {
    mockBase();
    let queryFechaFin: string | null = null;
    server.use(
      http.post(`${PLANTILLAS}/1/baja`, ({ request }) => {
        queryFechaFin = new URL(request.url).searchParams.get("fecha_fin");
        return HttpResponse.json({
          id: 1,
          jugador_perfil_id: 1,
          inscripcion_torneo_id: 5,
          dorsal: 10,
          fecha_inicio: "2026-01-01",
          fecha_fin: "2026-06-01",
          estado: "Inactivo",
        });
      }),
    );
    const user = userEvent.setup();
    renderPagina();
    await screen.findByText("Carlos Pérez");

    await user.click(screen.getByRole("button", { name: "Dar de baja" }));
    await user.type(screen.getByLabelText("Fecha de baja"), "2026-06-01");
    await user.click(screen.getByRole("button", { name: "Confirmar baja" }));

    await waitFor(() => expect(queryFechaFin).toBe("2026-06-01"));
  });

  // T30 — click en la tarjeta abre el Perfil de Jugador en un modal, sin
  // navegar afuera del grid.
  it("click en una tarjeta abre el Perfil de Jugador editable en un modal", async () => {
    mockBase();
    server.use(
      http.get("http://127.0.0.1:8000/api/v1/jugadores/1/perfil", () =>
        HttpResponse.json({
          jugador_id: 1,
          nombre: "Carlos Pérez",
          foto_url: null,
          cedula: "0900000001",
          correo_electronico: "carlos.perez@example.com",
          disciplinas: [],
        }),
      ),
    );
    const user = userEvent.setup();
    renderPagina();

    await user.click(await screen.findByRole("button", { name: /Carlos Pérez/ }));

    expect(await screen.findByText("Cédula: 0900000001 — Correo: carlos.perez@example.com")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Editar" })).toBeInTheDocument();
  });

  // T30 — Editar conecta PATCH /jugadores/{id}, hasta ahora sin consumidor.
  it("Perfil de Jugador: Editar guarda vía PATCH /jugadores/{id}", async () => {
    mockBase();
    server.use(
      http.get("http://127.0.0.1:8000/api/v1/jugadores/1/perfil", () =>
        HttpResponse.json({
          jugador_id: 1,
          nombre: "Carlos Pérez",
          foto_url: null,
          cedula: "0900000001",
          correo_electronico: "carlos.perez@example.com",
          disciplinas: [],
        }),
      ),
    );
    let bodyRecibido: unknown;
    server.use(
      http.patch(`${JUGADORES}/1`, async ({ request }) => {
        bodyRecibido = await request.json();
        return HttpResponse.json({ id: 1, nombre: "Carlos Pérez Editado", estado: "Activo" });
      }),
    );
    const user = userEvent.setup();
    renderPagina();

    await user.click(await screen.findByRole("button", { name: /Carlos Pérez/ }));
    await user.click(await screen.findByRole("button", { name: "Editar" }));
    const nombreInput = screen.getByDisplayValue("Carlos Pérez");
    await user.clear(nombreInput);
    await user.type(nombreInput, "Carlos Pérez Editado");
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => expect(bodyRecibido).toMatchObject({ nombre: "Carlos Pérez Editado" }));
  });

  // T31 — cédula duplicada llega como mensaje inline, no un toast genérico.
  it("Perfil de Jugador: cédula duplicada al editar se muestra inline", async () => {
    mockBase();
    server.use(
      http.get("http://127.0.0.1:8000/api/v1/jugadores/1/perfil", () =>
        HttpResponse.json({
          jugador_id: 1,
          nombre: "Carlos Pérez",
          foto_url: null,
          cedula: "0900000001",
          correo_electronico: "carlos.perez@example.com",
          disciplinas: [],
        }),
      ),
      http.patch(`${JUGADORES}/1`, () =>
        HttpResponse.json({ detail: "Ya existe un registro con esos datos (restricción de unicidad)." }, { status: 409 }),
      ),
    );
    const user = userEvent.setup();
    renderPagina();

    await user.click(await screen.findByRole("button", { name: /Carlos Pérez/ }));
    await user.click(await screen.findByRole("button", { name: "Editar" }));
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    expect(await screen.findByText(/restricción de unicidad/)).toBeInTheDocument();
  });
});
