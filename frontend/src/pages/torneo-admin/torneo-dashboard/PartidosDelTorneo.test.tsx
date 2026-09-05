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

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useOutletContext: () => CONTEXTO, useNavigate: () => mockNavigate };
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
  es_walkover: false,
  walkover_equipo_ausente_id: null,
};

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
    server.use(http.get(PARTIDOS, () => HttpResponse.json([PARTIDO_PROGRAMADO])));
    renderPagina();
    expect(await screen.findByText("Halcones FC vs Tiburones FC")).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Torneo" })).not.toBeInTheDocument();
  });

  // control-mesa-centralizacion-fixture-plan.md, Sección 16: de solo
  // lectura para la operación del partido — sin editar libre ni Walkover
  // (ambos se mudaron a Control de Mesa).
  it("no ofrece 'Editar' ni 'Walkover' — solo Detalle/Asignar árbitro/Cancelar", async () => {
    mockBase();
    server.use(http.get(PARTIDOS, () => HttpResponse.json([PARTIDO_PROGRAMADO])));
    renderPagina();
    await screen.findByText("Halcones FC vs Tiburones FC");

    expect(screen.queryByRole("button", { name: "Editar" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Walkover" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Detalle del Partido" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Asignar árbitro" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancelar" })).toBeInTheDocument();
  });

  it("'Detalle del Partido' navega a /partidos/:id", async () => {
    mockBase();
    server.use(http.get(PARTIDOS, () => HttpResponse.json([PARTIDO_PROGRAMADO])));
    const user = userEvent.setup();
    renderPagina();
    await screen.findByText("Halcones FC vs Tiburones FC");

    await user.click(screen.getByRole("button", { name: "Detalle del Partido" }));
    expect(mockNavigate).toHaveBeenCalledWith("/partidos/1");
  });

  it("'Asignar árbitro' elige uno de la lista y hace PATCH con arbitro_id", async () => {
    mockBase();
    server.use(
      http.get(PARTIDOS, () => HttpResponse.json([PARTIDO_PROGRAMADO])),
      http.get(USUARIOS, () => HttpResponse.json([{ id: 9, username: "arbitro1", nombre: "Ana Árbitro" }])),
    );
    let bodyRecibido: unknown;
    server.use(
      http.patch("http://127.0.0.1:8000/api/v1/partidos/1", async ({ request }) => {
        bodyRecibido = await request.json();
        return HttpResponse.json({ ...PARTIDO_PROGRAMADO, arbitro_id: 9 });
      }),
    );
    const user = userEvent.setup();
    renderPagina();
    await screen.findByText("Halcones FC vs Tiburones FC");

    await user.click(screen.getByRole("button", { name: "Asignar árbitro" }));
    await user.selectOptions(await screen.findByLabelText("Árbitro asignado"), "9");
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => expect(bodyRecibido).toEqual({ arbitro_id: 9 }));
  });

  it("muestra el badge W.O. en un partido cerrado por walkover (dato de solo lectura)", async () => {
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

  // Bug del fixture (control-mesa-centralizacion-fixture-plan.md, Sección
  // 1/9): regresión — reproduce el bug reportado (un equipo con ID fuera
  // de la ventana simulada de la lista base de /equipos) y confirma que el
  // fix (useNombrePorIdConFaltantes) lo resuelve, no cae a "?".
  it("resuelve el nombre de un equipo recién creado, fuera de la ventana de /equipos (bug reportado, ya no cae a '?')", async () => {
    server.use(
      // La lista BASE de /equipos (sin filtro, tope de 200 por ID
      // ascendente) no trae al equipo 999 — simula esa ventana ya llena.
      http.get(EQUIPOS, () => HttpResponse.json([{ id: 1, nombre: "Halcones FC" }])),
      // Resolución dirigida (useFetchFaltantes): GET /equipos/999 SÍ
      // existe y devuelve el nombre real — es lo que pide para el ID que
      // falta en la lista base.
      http.get(`${EQUIPOS}/999`, () => HttpResponse.json({ id: 999, nombre: "Equipo Recién Creado" })),
      http.get(INSCRIPCIONES, () => HttpResponse.json([{ id: 7, equipo_id: 999, estado: "Inscrito" }])),
      http.get(
        PARTIDOS,
        () =>
          HttpResponse.json([
            { ...PARTIDO_PROGRAMADO, id: 2, equipos_id_local: 999, equipos_id_visitante: 1 },
          ]),
      ),
      http.get(USUARIOS, () => HttpResponse.json([])),
    );
    renderPagina();

    // Antes del fix (P3 confirmado en el plan): esto caía a "? vs Halcones FC".
    expect(await screen.findByText("Equipo Recién Creado vs Halcones FC")).toBeInTheDocument();
    expect(screen.queryByText("? vs Halcones FC")).not.toBeInTheDocument();
  });
});
