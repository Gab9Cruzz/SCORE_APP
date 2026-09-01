import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter, useSearchParams } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { server } from "../../test/msw-server";
import { createTestQueryClient, createWrapper } from "../../test/test-utils";
import { TorneosAdminPage } from "./TorneosAdmin";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => mockNavigate };
});

// Catálogo unificado (ediciones-catalogo-disciplinas-plan.md, Decisión A1):
// ya no hay `tipo` en DISCIPLINA, y toda disciplina tiene 1+ modalidades.
const DISCIPLINAS = [
  { id: 1, nombre: "Fútbol", estado: "Activo" },
  { id: 2, nombre: "Tenis", estado: "Activo" },
];
const MODALIDADES = [
  { id: 1, nombre: "Fútbol 11", disciplina_id: 1, tamano_equipo: 11, estado: "Activo" },
  { id: 2, nombre: "Singles", disciplina_id: 2, tamano_equipo: 1, estado: "Activo" },
  { id: 3, nombre: "Fútbol 5", disciplina_id: 1, tamano_equipo: 5, estado: "Activo" },
];

function mockCatalogos() {
  server.use(
    http.get("http://127.0.0.1:8000/api/v1/disciplinas", () => HttpResponse.json(DISCIPLINAS)),
    http.get("http://127.0.0.1:8000/api/v1/modalidades", () => HttpResponse.json(MODALIDADES)),
  );
}

describe("TorneosAdminPage", () => {
  it("lista tarjetas por grupo con la disciplina resuelta y el badge de ediciones", async () => {
    mockCatalogos();
    server.use(
      http.get("http://127.0.0.1:8000/api/v1/torneo-grupos", () =>
        HttpResponse.json([
          {
            id: 1,
            nombre: "Liga Relámpago",
            ediciones: [
              {
                id: 20,
                numero_edicion: 2,
                disciplina_id: 1,
                modalidad_id: 1,
                estado: "Activo",
                fecha_inicio: "2026-04-01",
                fecha_fin: "2026-06-30",
              },
              {
                id: 10,
                numero_edicion: 1,
                disciplina_id: 1,
                modalidad_id: 1,
                estado: "Finalizado",
                fecha_inicio: "2026-03-01",
                fecha_fin: "2026-05-15",
              },
            ],
          },
        ]),
      ),
    );
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <TorneosAdminPage />
      </Wrapper>,
    );

    expect(await screen.findByText("Liga Relámpago")).toBeInTheDocument();
    // El nombre de la disciplina aparece dos veces desde este plan: en el
    // chip de la barra de navegación y en la tarjeta. Se busca el de la
    // tarjeta, que es el que este test verifica.
    expect(screen.getByText(/Fútbol · 2 ediciones/)).toBeInTheDocument();
    // Abre la Activa (Edición 2), no la de numero_edicion más alto a ciegas.
    expect(screen.getByText(/Edición 2 — Activo/)).toBeInTheDocument();
  });

  it("Ver Torneo navega a la edición activa del grupo", async () => {
    mockCatalogos();
    server.use(
      http.get("http://127.0.0.1:8000/api/v1/torneo-grupos", () =>
        HttpResponse.json([
          {
            id: 1,
            nombre: "Copa Raíces",
            ediciones: [
              {
                id: 30,
                numero_edicion: 1,
                disciplina_id: 2,
                modalidad_id: 2,
                estado: "Activo",
                fecha_inicio: "2026-04-10",
                fecha_fin: "2026-06-20",
              },
            ],
          },
        ]),
      ),
    );
    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <TorneosAdminPage />
      </Wrapper>,
    );

    await screen.findByText("Copa Raíces");
    await user.click(screen.getByRole("button", { name: "Ver Torneo →" }));
    expect(mockNavigate).toHaveBeenCalledWith("/torneo-admin/torneos/30");
  });

  it("Torneo nuevo: Modalidad es siempre obligatoria, sus opciones se filtran por la Disciplina elegida", async () => {
    mockCatalogos();
    server.use(http.get("http://127.0.0.1:8000/api/v1/torneo-grupos", () => HttpResponse.json([])));
    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <TorneosAdminPage />
      </Wrapper>,
    );

    await user.click(await screen.findByRole("button", { name: "+ Torneo nuevo" }));
    // Está siempre presente (catálogo unificado — Decisión A1), a
    // diferencia del Tipo binario de antes, pero sin opciones hasta elegir
    // una Disciplina.
    expect(await screen.findByLabelText("Modalidad")).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Fútbol 11" })).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Disciplina"), "Fútbol");
    expect(await screen.findByRole("option", { name: "Fútbol 11" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Singles" })).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Disciplina"), "Tenis");
    expect(await screen.findByRole("option", { name: "Singles" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Fútbol 11" })).not.toBeInTheDocument();
  });

  it("Torneo nuevo: crea un grupo con torneo_grupo_nombre, disciplina y modalidad", async () => {
    mockCatalogos();
    server.use(http.get("http://127.0.0.1:8000/api/v1/torneo-grupos", () => HttpResponse.json([])));
    let bodyRecibido: unknown;
    server.use(
      http.post("http://127.0.0.1:8000/api/v1/torneos", async ({ request }) => {
        bodyRecibido = await request.json();
        return HttpResponse.json({ id: 1, torneo_grupo_id: 1, numero_edicion: 1 }, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <TorneosAdminPage />
      </Wrapper>,
    );

    await user.click(await screen.findByRole("button", { name: "+ Torneo nuevo" }));
    await user.type(await screen.findByLabelText("Nombre del torneo"), "Liga Relámpago");
    await user.selectOptions(screen.getByLabelText("Disciplina"), "Fútbol");
    await user.selectOptions(await screen.findByLabelText("Modalidad"), "Fútbol 11");
    await user.type(screen.getByLabelText("Fecha de inicio"), "2026-03-01");
    await user.type(screen.getByLabelText("Fecha de fin"), "2026-05-15");
    await user.click(screen.getByRole("button", { name: "Crear" }));

    await waitFor(() =>
      expect(bodyRecibido).toMatchObject({ torneo_grupo_nombre: "Liga Relámpago", disciplina_id: 1, modalidad_id: 1 }),
    );
  });

  // Motor de Formatos (Design sección E, motor-formatos-plantillas-
  // navegacion-plan.md): el selector solo muestra los campos que aplican
  // al Formato elegido, y los manda todos en el submit.
  it("Torneo nuevo: Formato Grupos + Playoffs muestra sus parámetros y los manda en el submit", async () => {
    mockCatalogos();
    server.use(http.get("http://127.0.0.1:8000/api/v1/torneo-grupos", () => HttpResponse.json([])));
    let bodyRecibido: unknown;
    server.use(
      http.post("http://127.0.0.1:8000/api/v1/torneos", async ({ request }) => {
        bodyRecibido = await request.json();
        return HttpResponse.json({ id: 1, torneo_grupo_id: 1, numero_edicion: 1 }, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <TorneosAdminPage />
      </Wrapper>,
    );

    await user.click(await screen.findByRole("button", { name: "+ Torneo nuevo" }));
    // Por defecto (Liga): "Ida y vuelta" está, los de Grupos no.
    expect(await screen.findByLabelText("Ida y vuelta")).toBeInTheDocument();
    expect(screen.queryByLabelText("Equipos por grupo")).not.toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Formato"), "Grupos_Playoffs");
    expect(screen.queryByLabelText("Ida y vuelta")).not.toBeInTheDocument();
    expect(await screen.findByLabelText("Jugar partido por el 3er lugar")).toBeInTheDocument();
    expect(screen.getByLabelText("Equipos por grupo")).toBeInTheDocument();

    await user.type(await screen.findByLabelText("Nombre del torneo"), "Mundialito");
    await user.selectOptions(screen.getByLabelText("Disciplina"), "Fútbol");
    await user.selectOptions(await screen.findByLabelText("Modalidad"), "Fútbol 11");
    await user.type(screen.getByLabelText("Equipos por grupo"), "4");
    await user.type(screen.getByLabelText("Clasifican por grupo"), "2");
    await user.type(screen.getByLabelText("Fecha de inicio"), "2026-03-01");
    await user.type(screen.getByLabelText("Fecha de fin"), "2026-05-15");
    await user.click(screen.getByRole("button", { name: "Crear" }));

    await waitFor(() =>
      expect(bodyRecibido).toMatchObject({
        formato: "Grupos_Playoffs",
        equipos_por_grupo: 4,
        clasificados_por_grupo: 2,
        incluye_tercer_lugar: true,
      }),
    );
    expect((bodyRecibido as Record<string, unknown>).ida_vuelta).toBeUndefined();
  });

  it("Nueva edición: muestra Disciplina/Modalidad heredadas como texto, sin pedirlas ni mandarlas (D-Eng-5)", async () => {
    mockCatalogos();
    server.use(
      http.get("http://127.0.0.1:8000/api/v1/torneo-grupos", () =>
        HttpResponse.json([
          {
            id: 7,
            nombre: "Liga Relámpago",
            ediciones: [
              {
                id: 10,
                numero_edicion: 1,
                disciplina_id: 1,
                modalidad_id: 1,
                estado: "Activo",
                fecha_inicio: "2026-03-01",
                fecha_fin: "2026-05-15",
              },
            ],
          },
        ]),
      ),
    );
    let bodyRecibido: unknown;
    server.use(
      http.post("http://127.0.0.1:8000/api/v1/torneos", async ({ request }) => {
        bodyRecibido = await request.json();
        return HttpResponse.json({ id: 2, torneo_grupo_id: 7, numero_edicion: 2 }, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <TorneosAdminPage />
      </Wrapper>,
    );

    await screen.findByText("Liga Relámpago");
    await user.click(screen.getByRole("button", { name: "+ Nueva edición" }));

    // Texto plano heredado — ni un <select> ni un campo del form (Fase 2
    // parte A del plan).
    expect(screen.queryByLabelText("Nombre del torneo")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Disciplina")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Modalidad")).not.toBeInTheDocument();
    // Sin ambigüedad con los chips de la barra: en la pantalla de
    // "Nueva edición" la barra ni siquiera se monta.
    expect(await screen.findByText("Fútbol")).toBeInTheDocument();
    expect(screen.getByText("Fútbol 11")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Fecha de inicio"), "2026-06-01");
    await user.type(screen.getByLabelText("Fecha de fin"), "2026-08-30");
    await user.click(screen.getByRole("button", { name: "Crear edición" }));

    await waitFor(() => expect(bodyRecibido).toEqual({
      torneo_grupo_id: 7,
      fecha_inicio: "2026-06-01",
      fecha_fin: "2026-08-30",
    }));
  });
});

/** Barra de navegación tipo SofaScore (Fase 2 parte D). Dos grupos de
 * Fútbol (uno de Fútbol 11, otro de Fútbol 5) y uno de Tenis: alcanza para
 * probar los dos niveles, el filtrado y el contador. */
const GRUPOS_MIXTOS = [
  {
    id: 1,
    nombre: "Liga Relámpago",
    ediciones: [
      { id: 10, numero_edicion: 1, disciplina_id: 1, modalidad_id: 1, estado: "Activo", fecha_inicio: "2026-03-01", fecha_fin: "2026-05-15" },
    ],
  },
  {
    id: 2,
    nombre: "Copa Fútbol 5",
    ediciones: [
      { id: 11, numero_edicion: 1, disciplina_id: 1, modalidad_id: 3, estado: "Activo", fecha_inicio: "2026-03-01", fecha_fin: "2026-05-15" },
    ],
  },
  {
    id: 3,
    nombre: "Abierto de Tenis",
    ediciones: [
      { id: 12, numero_edicion: 1, disciplina_id: 2, modalidad_id: 2, estado: "Activo", fecha_inicio: "2026-03-01", fecha_fin: "2026-05-15" },
    ],
  },
];

function montarConGrupos(grupos: unknown[]) {
  mockCatalogos();
  server.use(http.get("http://127.0.0.1:8000/api/v1/torneo-grupos", () => HttpResponse.json(grupos)));
  const Wrapper = createWrapper();
  return render(
    <Wrapper>
      <TorneosAdminPage />
    </Wrapper>,
  );
}

describe("TorneosAdminPage — barra de disciplinas (Fase 2 parte D)", () => {
  // T18 — el filtro efectivamente filtra las tarjetas.
  it("un click en el chip filtra el listado y actualiza el contador", async () => {
    montarConGrupos(GRUPOS_MIXTOS);
    const user = userEvent.setup();

    await screen.findByText("Liga Relámpago");
    expect(screen.getByText("Abierto de Tenis")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: /Tenis/ }));

    expect(screen.getByText("Abierto de Tenis")).toBeInTheDocument();
    expect(screen.queryByText("Liga Relámpago")).not.toBeInTheDocument();
    // El admin siempre sabe que está viendo un subconjunto.
    expect(screen.getByText("(1 de 3)")).toBeInTheDocument();
  });

  // T19 / D-Eng-16 — los chips salen de los torneos cargados, no del
  // catálogo: 28 disciplinas no entran en una barra, y un chip que filtra
  // a vacío no debería poder existir.
  it("solo muestra chips de disciplinas que tienen torneos", async () => {
    montarConGrupos([GRUPOS_MIXTOS[2]]); // solo el de Tenis

    expect(await screen.findByRole("tab", { name: /Tenis/ })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: /Fútbol/ })).not.toBeInTheDocument();
  });

  // T20 — segunda fila condicional: con una sola modalidad presente,
  // elegirla no filtra nada y ocuparía una fila entera.
  it("la fila de modalidades aparece solo con 2+ modalidades presentes", async () => {
    montarConGrupos(GRUPOS_MIXTOS);
    const user = userEvent.setup();

    await screen.findByText("Liga Relámpago");
    expect(screen.queryByRole("tablist", { name: "Filtrar por modalidad" })).not.toBeInTheDocument();

    // Tenis tiene una sola modalidad con torneos → sin segunda fila.
    await user.click(screen.getByRole("tab", { name: /Tenis/ }));
    expect(screen.queryByRole("tablist", { name: "Filtrar por modalidad" })).not.toBeInTheDocument();

    // Fútbol tiene dos → aparece, y filtra.
    await user.click(screen.getByRole("tab", { name: /Fútbol/ }));
    expect(screen.getByRole("tablist", { name: "Filtrar por modalidad" })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Fútbol 5" }));
    expect(screen.getByText("Copa Fútbol 5")).toBeInTheDocument();
    expect(screen.queryByText("Liga Relámpago")).not.toBeInTheDocument();
  });

  // T21 — accesibilidad: botones reales, estado en aria-pressed (no solo
  // color) y flechas que mueven el foco dentro del tablist.
  it("es navegable por teclado y expone el estado activo en aria-pressed", async () => {
    montarConGrupos(GRUPOS_MIXTOS);
    const user = userEvent.setup();

    const todos = await screen.findByRole("tab", { name: /Todos/ });
    expect(todos).toHaveAttribute("aria-pressed", "true");

    todos.focus();
    await user.keyboard("{ArrowRight}");
    expect(document.activeElement).toHaveAccessibleName(expect.stringContaining("Fútbol"));

    await user.keyboard("{Enter}");
    // Nombre exacto: al activar Fútbol aparece la segunda fila, y /Fútbol/
    // pasaría a matchear también el chip de modalidad "Fútbol 5". El emoji
    // no entra en el nombre accesible — va con aria-hidden, como debe ser.
    expect(screen.getByRole("tab", { name: "Fútbol" })).toHaveAttribute("aria-pressed", "true");
    expect(todos).toHaveAttribute("aria-pressed", "false");
  });

  // T22 — sin torneos, una barra de filtros es ruido.
  it("no se renderiza si no hay torneos", async () => {
    montarConGrupos([]);

    expect(await screen.findByText("No hay torneos creados todavía.")).toBeInTheDocument();
    expect(screen.queryByRole("tablist", { name: "Filtrar por disciplina" })).not.toBeInTheDocument();
  });
});

describe("TorneosAdminPage — redirección tras Nueva edición (pedido C)", () => {
  // T16 — el camino roto: desde la Pestaña Torneos, "Nueva edición"
  // volvía al listado y dejaba al admin frente a una tarjeta más.
  it("navega a la pestaña Agregar Equipo de la edición recién creada", async () => {
    mockCatalogos();
    server.use(
      http.get("http://127.0.0.1:8000/api/v1/torneo-grupos", () => HttpResponse.json([GRUPOS_MIXTOS[0]])),
      http.post("http://127.0.0.1:8000/api/v1/torneos", () =>
        HttpResponse.json({ id: 42, torneo_grupo_id: 1, numero_edicion: 2, disciplina_id: 1 }, { status: 201 }),
      ),
    );
    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <TorneosAdminPage />
      </Wrapper>,
    );

    await screen.findByText("Liga Relámpago");
    await user.click(screen.getByRole("button", { name: "+ Nueva edición" }));
    await user.type(screen.getByLabelText("Fecha de inicio"), "2026-06-01");
    await user.type(screen.getByLabelText("Fecha de fin"), "2026-08-30");
    await user.click(screen.getByRole("button", { name: "Crear edición" }));

    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith("/torneo-admin/torneos/42/equipos"));
  });

  // T25 (EC-46, motor-formatos-plantillas-navegacion-plan.md): el mismo
  // camino roto, en la OTRA rama del formulario — crear un torneo la
  // PRIMERA vez (grupo nuevo) se quedaba en el listado en vez de
  // redirigir igual que "Nueva edición".
  it("Torneo nuevo (grupo nuevo): también navega a Agregar Equipo tras crear", async () => {
    mockCatalogos();
    server.use(
      http.get("http://127.0.0.1:8000/api/v1/torneo-grupos", () => HttpResponse.json([])),
      http.post("http://127.0.0.1:8000/api/v1/torneos", () =>
        HttpResponse.json({ id: 99, torneo_grupo_id: 5, numero_edicion: 1 }, { status: 201 }),
      ),
    );
    const user = userEvent.setup();
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <TorneosAdminPage />
      </Wrapper>,
    );

    await user.click(await screen.findByRole("button", { name: "+ Torneo nuevo" }));
    await user.type(await screen.findByLabelText("Nombre del torneo"), "Liga Relámpago");
    await user.selectOptions(screen.getByLabelText("Disciplina"), "Fútbol");
    await user.selectOptions(await screen.findByLabelText("Modalidad"), "Fútbol 11");
    await user.type(screen.getByLabelText("Fecha de inicio"), "2026-03-01");
    await user.type(screen.getByLabelText("Fecha de fin"), "2026-05-15");
    await user.click(screen.getByRole("button", { name: "Crear" }));

    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith("/torneo-admin/torneos/99/equipos"));
  });
});

describe("TorneosAdminPage — filtro de Estado + persistencia en URL (3A-9/3A-10)", () => {
  const GRUPOS_CON_ESTADOS = [
    {
      id: 1,
      nombre: "Liga Relámpago",
      ediciones: [
        { id: 10, numero_edicion: 1, disciplina_id: 1, modalidad_id: 1, estado: "Activo", fecha_inicio: "2026-03-01", fecha_fin: "2026-05-15" },
      ],
    },
    {
      id: 2,
      nombre: "Copa Fútbol 5",
      ediciones: [
        { id: 11, numero_edicion: 1, disciplina_id: 1, modalidad_id: 3, estado: "Finalizado", fecha_inicio: "2025-03-01", fecha_fin: "2025-05-15" },
      ],
    },
  ];

  /** Sibling en el mismo Router que la página — lee el querystring real,
   * distinto del `createWrapper()` compartido (su `MemoryRouter` no
   * expone la ubicación afuera). */
  function UbicacionDebug() {
    const [params] = useSearchParams();
    return <div data-testid="querystring">{params.toString()}</div>;
  }

  function montarConRouter(grupos: unknown[], initialEntry = "/") {
    mockCatalogos();
    server.use(http.get("http://127.0.0.1:8000/api/v1/torneo-grupos", () => HttpResponse.json(grupos)));
    const queryClient = createTestQueryClient();
    return render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[initialEntry]}>
          <TorneosAdminPage />
          <UbicacionDebug />
        </MemoryRouter>
      </QueryClientProvider>,
    );
  }

  it("elegir un chip de estado filtra el listado y escribe ?estado= en la URL", async () => {
    montarConRouter(GRUPOS_CON_ESTADOS);
    const user = userEvent.setup();

    await screen.findByText("Liga Relámpago");
    expect(screen.getByText("Copa Fútbol 5")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Finalizado" }));

    expect(screen.getByText("Copa Fútbol 5")).toBeInTheDocument();
    expect(screen.queryByText("Liga Relámpago")).not.toBeInTheDocument();
    expect(screen.getByTestId("querystring")).toHaveTextContent("estado=Finalizado");
  });

  it("elegir un chip de disciplina escribe ?disciplina_id= en la URL (3A-10)", async () => {
    montarConRouter(GRUPOS_CON_ESTADOS);
    const user = userEvent.setup();

    await screen.findByText("Liga Relámpago");
    await user.click(screen.getByRole("tab", { name: /Fútbol/ }));

    expect(screen.getByTestId("querystring")).toHaveTextContent("disciplina_id=1");
  });

  it("abrir con ?estado=Finalizado en la URL arranca ya filtrado", async () => {
    montarConRouter(GRUPOS_CON_ESTADOS, "/?estado=Finalizado");

    await screen.findByText("Copa Fútbol 5");
    expect(screen.queryByText("Liga Relámpago")).not.toBeInTheDocument();
  });

  it("'Ver todos' desde el vacío filtrado limpia disciplina, modalidad Y estado a la vez", async () => {
    montarConRouter(GRUPOS_CON_ESTADOS, "/?disciplina_id=1&estado=Finalizado");
    const user = userEvent.setup();

    // disciplina=Fútbol (ambos grupos) + estado=Finalizado (solo Copa
    // Fútbol 5) — combinado no vacía la lista todavía, se agrega
    // modalidad=3 (la de Copa Fútbol 5) para forzar el vacío real y
    // ejercitar los tres resets a la vez.
    await screen.findByText("Copa Fútbol 5");
    await user.click(screen.getByRole("tab", { name: "Fútbol 5" }));
    // Fútbol 5 (modalidad_id=3, estado Finalizado) sigue matcheando Copa
    // Fútbol 5 — el vacío real se fuerza sumando un estado que ningún
    // grupo de Fútbol 5 tiene.
    await user.click(screen.getByRole("tab", { name: "Activo" }));

    expect(await screen.findByText(/Ningún torneo de/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Ver todos" }));

    expect(await screen.findByText("Liga Relámpago")).toBeInTheDocument();
    expect(screen.getByText("Copa Fútbol 5")).toBeInTheDocument();
    expect(screen.getByTestId("querystring")).toHaveTextContent("");
  });
});

describe("TorneosAdminPage — archivar/reactivar TORNEO_GRUPO (3B-7)", () => {
  const GRUPO_ACTIVO = {
    id: 1,
    nombre: "Liga Activa",
    estado: "Activo",
    ediciones: [
      { id: 10, numero_edicion: 1, disciplina_id: 1, modalidad_id: 1, estado: "Activo", fecha_inicio: "2026-03-01", fecha_fin: "2026-05-15" },
    ],
  };
  const GRUPO_ARCHIVADO = {
    id: 2,
    nombre: "Liga Vieja",
    estado: "Archivado",
    ediciones: [
      { id: 11, numero_edicion: 1, disciplina_id: 1, modalidad_id: 1, estado: "Finalizado", fecha_inicio: "2025-03-01", fecha_fin: "2025-05-15" },
    ],
  };

  function montarConToggleDeArchivados() {
    mockCatalogos();
    server.use(
      http.get("http://127.0.0.1:8000/api/v1/torneo-grupos", ({ request }) => {
        const incluirArchivados = new URL(request.url).searchParams.get("incluir_archivados") === "true";
        return HttpResponse.json(incluirArchivados ? [GRUPO_ACTIVO, GRUPO_ARCHIVADO] : [GRUPO_ACTIVO]);
      }),
    );
    const Wrapper = createWrapper();
    return render(
      <Wrapper>
        <TorneosAdminPage />
      </Wrapper>,
    );
  }

  it("un grupo Archivado no aparece por default, ni con 'Ver archivados' apagado", async () => {
    montarConToggleDeArchivados();

    await screen.findByText("Liga Activa");
    expect(screen.queryByText("Liga Vieja")).not.toBeInTheDocument();
  });

  it("tildar 'Ver archivados' trae también los archivados, con su badge", async () => {
    montarConToggleDeArchivados();
    const user = userEvent.setup();
    await screen.findByText("Liga Activa");

    await user.click(screen.getByRole("checkbox", { name: "Ver archivados" }));

    expect(await screen.findByText("Liga Vieja")).toBeInTheDocument();
    const filaVieja = screen.getByText("Liga Vieja").closest("h2") as HTMLElement;
    expect(within(filaVieja).getByText("Archivado")).toBeInTheDocument();
  });

  it("'Archivar' manda el PATCH correcto y saca la tarjeta de la vista", async () => {
    montarConToggleDeArchivados();
    const user = userEvent.setup();
    await screen.findByText("Liga Activa");

    let cuerpoRecibido: unknown;
    server.use(
      http.patch("http://127.0.0.1:8000/api/v1/torneo-grupos/1", async ({ request }) => {
        cuerpoRecibido = await request.json();
        return HttpResponse.json({ id: 1, nombre: "Liga Activa", estado: "Archivado", fecha_registro: "2026-01-01T00:00:00", fecha_modificacion: "2026-01-01T00:00:00" });
      }),
    );

    const tarjeta = screen.getByText("Liga Activa").closest(".tarjeta-torneo") as HTMLElement;
    await user.click(within(tarjeta).getByRole("button", { name: "Archivar" }));

    await waitFor(() => expect(cuerpoRecibido).toEqual({ estado: "Archivado" }));
  });

  it("'Reactivar' aparece en un grupo Archivado y manda estado: Activo", async () => {
    montarConToggleDeArchivados();
    const user = userEvent.setup();
    await screen.findByText("Liga Activa");
    await user.click(screen.getByRole("checkbox", { name: "Ver archivados" }));
    await screen.findByText("Liga Vieja");

    let cuerpoRecibido: unknown;
    server.use(
      http.patch("http://127.0.0.1:8000/api/v1/torneo-grupos/2", async ({ request }) => {
        cuerpoRecibido = await request.json();
        return HttpResponse.json({ id: 2, nombre: "Liga Vieja", estado: "Activo", fecha_registro: "2026-01-01T00:00:00", fecha_modificacion: "2026-01-01T00:00:00" });
      }),
    );

    const tarjeta = screen.getByText("Liga Vieja").closest(".tarjeta-torneo") as HTMLElement;
    expect(within(tarjeta).queryByRole("button", { name: "Archivar" })).not.toBeInTheDocument();
    await user.click(within(tarjeta).getByRole("button", { name: "Reactivar" }));

    await waitFor(() => expect(cuerpoRecibido).toEqual({ estado: "Activo" }));
  });
});
