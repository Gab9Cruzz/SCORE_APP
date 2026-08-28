import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { server } from "../../../test/msw-server";
import { createWrapper } from "../../../test/test-utils";
import { ModalAgregarInscripcion } from "./ModalAgregarInscripcion";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => mockNavigate };
});

const EQUIPOS = "http://127.0.0.1:8000/api/v1/equipos";
const INSCRIPCIONES = "http://127.0.0.1:8000/api/v1/inscripciones";
const MODALIDADES = "http://127.0.0.1:8000/api/v1/modalidades";
const JUGADORES = "http://127.0.0.1:8000/api/v1/jugadores";

const MODALIDAD_CONJUNTO = { id: 1, nombre: "Fútbol 11", disciplina_id: 1, tamano_equipo: 11, estado: "Activo" };
const MODALIDAD_PAREJA = { id: 2, nombre: "Dobles", disciplina_id: 2, tamano_equipo: 2, estado: "Activo" };
const MODALIDAD_INDIVIDUAL = { id: 3, nombre: "Singles", disciplina_id: 2, tamano_equipo: 1, estado: "Activo" };

function renderModal(overrides: Partial<React.ComponentProps<typeof ModalAgregarInscripcion>> = {}) {
  const Wrapper = createWrapper();
  return render(
    <Wrapper>
      <ModalAgregarInscripcion
        torneoId={20}
        torneoContexto="Liga Relámpago — Edición 2"
        torneoModalidadId={MODALIDAD_CONJUNTO.id}
        equiposYaInscritosIds={new Set([1])}
        onClose={() => {}}
        {...overrides}
      />
    </Wrapper>,
  );
}

describe("ModalAgregarInscripcion — Conjunto (tamano_equipo > 2)", () => {
  it("lista equipos no inscritos y excluye a los ya inscritos", async () => {
    server.use(
      http.get(EQUIPOS, () =>
        HttpResponse.json([
          { id: 1, nombre: "Halcones FC", estado: "Activo" },
          { id: 2, nombre: "Tiburones FC", estado: "Activo" },
        ]),
      ),
      http.get(MODALIDADES, () => HttpResponse.json([MODALIDAD_CONJUNTO])),
    );
    renderModal();

    expect(await screen.findByText("Tiburones FC")).toBeInTheDocument();
    expect(screen.queryByText("Halcones FC")).not.toBeInTheDocument();
  });

  it("inscribe un equipo existente con POST /inscripciones", async () => {
    server.use(
      http.get(EQUIPOS, () => HttpResponse.json([{ id: 2, nombre: "Tiburones FC", estado: "Activo" }])),
      http.get(MODALIDADES, () => HttpResponse.json([MODALIDAD_CONJUNTO])),
    );
    let bodyRecibido: unknown;
    server.use(
      http.post(INSCRIPCIONES, async ({ request }) => {
        bodyRecibido = await request.json();
        return HttpResponse.json({ id: 99, torneo_id: 20, equipo_id: 2, estado: "Inscrito" }, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderModal();

    await user.click(await screen.findByRole("button", { name: "Inscribir" }));

    await waitFor(() => expect(bodyRecibido).toEqual({ torneo_id: 20, equipo_id: 2 }));
  });

  it("crear equipo nuevo encadena equipo → inscripción → navega al registro por lote, permite + agregar fila", async () => {
    server.use(
      http.get(EQUIPOS, () => HttpResponse.json([])),
      http.get(MODALIDADES, () => HttpResponse.json([MODALIDAD_CONJUNTO])),
      http.post(EQUIPOS, async ({ request }) => {
        const body = (await request.json()) as { nombre: string };
        return HttpResponse.json({ id: 55, nombre: body.nombre, estado: "Activo" }, { status: 201 });
      }),
      http.post(INSCRIPCIONES, () =>
        HttpResponse.json({ id: 77, torneo_id: 20, equipo_id: 55, estado: "Inscrito" }, { status: 201 }),
      ),
    );
    const user = userEvent.setup();
    renderModal();

    await user.click(await screen.findByRole("button", { name: "+ Crear equipo nuevo" }));
    expect(screen.getByRole("button", { name: "+ agregar fila" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("Nombre del equipo"), "Halcones FC");
    await user.type(screen.getByLabelText("Cédula fila 1"), "0102030405");
    await user.type(screen.getByLabelText("Nombre fila 1"), "Micky Fernández");
    await user.type(screen.getByLabelText("Correo fila 1"), "micky@example.com");
    await user.click(screen.getByRole("button", { name: "Validar y crear" }));

    await waitFor(() =>
      expect(mockNavigate).toHaveBeenCalledWith("/torneo-admin/plantillas/lote", {
        state: {
          inscripcionTorneoId: 77,
          contexto: "Halcones FC — Liga Relámpago — Edición 2",
          volverA: "/torneo-admin/torneos/20/equipos",
        },
      }),
    );
  });
});

describe("ModalAgregarInscripcion — Pareja (tamano_equipo == 2)", () => {
  it("fija exactamente 2 filas y autonombra con el nombre completo de ambos (Decisión D)", async () => {
    server.use(http.get(EQUIPOS, () => HttpResponse.json([])), http.get(MODALIDADES, () => HttpResponse.json([MODALIDAD_PAREJA])));
    const user = userEvent.setup();
    renderModal({ torneoModalidadId: MODALIDAD_PAREJA.id });

    await user.click(await screen.findByRole("button", { name: "+ Crear pareja nueva" }));
    expect(screen.getByLabelText("Cédula fila 1")).toBeInTheDocument();
    expect(screen.getByLabelText("Cédula fila 2")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "+ agregar fila" })).not.toBeInTheDocument();

    await user.type(screen.getByLabelText("Nombre fila 1"), "Carlos Pérez");
    await user.type(screen.getByLabelText("Nombre fila 2"), "Ana Gómez");

    expect(screen.getByLabelText("Nombre de la pareja")).toHaveValue("Carlos Pérez / Ana Gómez");
  });

  it("EC-28: no pisa el nombre editado a mano", async () => {
    server.use(http.get(EQUIPOS, () => HttpResponse.json([])), http.get(MODALIDADES, () => HttpResponse.json([MODALIDAD_PAREJA])));
    const user = userEvent.setup();
    renderModal({ torneoModalidadId: MODALIDAD_PAREJA.id });

    await user.click(await screen.findByRole("button", { name: "+ Crear pareja nueva" }));
    await user.type(screen.getByLabelText("Nombre fila 1"), "Carlos Pérez");
    await user.clear(screen.getByLabelText("Nombre de la pareja"));
    await user.type(screen.getByLabelText("Nombre de la pareja"), "Los Cracks");
    await user.type(screen.getByLabelText("Nombre fila 2"), "Ana Gómez");

    expect(screen.getByLabelText("Nombre de la pareja")).toHaveValue("Los Cracks");
  });
});

describe("ModalAgregarInscripcion — Individual (tamano_equipo == 1)", () => {
  it("no menciona 'equipo' en ningún lado", async () => {
    server.use(http.get(MODALIDADES, () => HttpResponse.json([MODALIDAD_INDIVIDUAL])), http.get(JUGADORES, () => HttpResponse.json([])));
    renderModal({ torneoModalidadId: MODALIDAD_INDIVIDUAL.id });

    expect(await screen.findByText("Agregar jugador — Liga Relámpago — Edición 2")).toBeInTheDocument();
    expect(screen.queryByText(/equipo/i)).not.toBeInTheDocument();
  });

  it("inscribe un jugador existente encontrado por búsqueda, sin crear ningún Equipo", async () => {
    server.use(
      http.get(MODALIDADES, () => HttpResponse.json([MODALIDAD_INDIVIDUAL])),
      http.get(JUGADORES, () =>
        HttpResponse.json([{ id: 1, nombre: "Micky Fernández", cedula: "0102030405", correo_electronico: "micky@example.com", estado: "Activo" }]),
      ),
    );
    let bodyRecibido: unknown;
    let equipoLlamado = false;
    server.use(
      http.post(EQUIPOS, () => {
        equipoLlamado = true;
        return HttpResponse.json({}, { status: 201 });
      }),
      http.post(INSCRIPCIONES, async ({ request }) => {
        bodyRecibido = await request.json();
        return HttpResponse.json(
          { id: 101, torneo_id: 20, equipo_id: null, jugador_perfil_id: 5, estado: "Inscrito" },
          { status: 201 },
        );
      }),
    );
    const user = userEvent.setup();
    renderModal({ torneoModalidadId: MODALIDAD_INDIVIDUAL.id });

    await user.type(await screen.findByLabelText("Buscar jugador existente"), "0102030405");
    await user.click(await screen.findByRole("button", { name: "Inscribir" }));

    await waitFor(() =>
      expect(bodyRecibido).toEqual({
        torneo_id: 20,
        jugador_cedula: "0102030405",
        jugador_nombre: "Micky Fernández",
        jugador_correo_electronico: "micky@example.com",
      }),
    );
    expect(await screen.findByText("Micky Fernández inscrito")).toBeInTheDocument();
    expect(equipoLlamado).toBe(false);
  });

  it("crea un jugador nuevo cuando la búsqueda no encuentra nada", async () => {
    server.use(http.get(MODALIDADES, () => HttpResponse.json([MODALIDAD_INDIVIDUAL])), http.get(JUGADORES, () => HttpResponse.json([])));
    let bodyRecibido: unknown;
    server.use(
      http.post(INSCRIPCIONES, async ({ request }) => {
        bodyRecibido = await request.json();
        return HttpResponse.json(
          { id: 102, torneo_id: 20, equipo_id: null, jugador_perfil_id: 6, estado: "Inscrito" },
          { status: 201 },
        );
      }),
    );
    const user = userEvent.setup();
    renderModal({ torneoModalidadId: MODALIDAD_INDIVIDUAL.id });

    await user.click(await screen.findByRole("button", { name: "+ Crear jugador" }));
    await user.type(screen.getByLabelText("Cédula"), "0900000099");
    await user.type(screen.getByLabelText("Nombre"), "Jugador Nuevo");
    await user.type(screen.getByLabelText("Correo"), "nuevo@example.com");
    await user.click(screen.getByRole("button", { name: "Validar e inscribir" }));

    await waitFor(() =>
      expect(bodyRecibido).toEqual({
        torneo_id: 20,
        jugador_cedula: "0900000099",
        jugador_nombre: "Jugador Nuevo",
        jugador_correo_electronico: "nuevo@example.com",
      }),
    );
  });
});
