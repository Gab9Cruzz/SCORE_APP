import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { server } from "../../../test/msw-server";
import { createWrapper } from "../../../test/test-utils";
import { ModalAgregarEquipo } from "./ModalAgregarEquipo";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => mockNavigate };
});

const EQUIPOS = "http://127.0.0.1:8000/api/v1/equipos";
const INSCRIPCIONES = "http://127.0.0.1:8000/api/v1/inscripciones";
const MODALIDADES = "http://127.0.0.1:8000/api/v1/modalidades";

function renderModal(overrides: Partial<React.ComponentProps<typeof ModalAgregarEquipo>> = {}) {
  const Wrapper = createWrapper();
  return render(
    <Wrapper>
      <ModalAgregarEquipo
        torneoId={20}
        torneoContexto="Liga Relámpago — Edición 2"
        torneoModalidadId={null}
        equiposYaInscritosIds={new Set([1])}
        onClose={() => {}}
        {...overrides}
      />
    </Wrapper>,
  );
}

describe("ModalAgregarEquipo", () => {
  it("lista equipos no inscritos y excluye a los ya inscritos", async () => {
    server.use(
      http.get(EQUIPOS, () =>
        HttpResponse.json([
          { id: 1, nombre: "Halcones FC", estado: "Activo" },
          { id: 2, nombre: "Tiburones FC", estado: "Activo" },
        ]),
      ),
      http.get(MODALIDADES, () => HttpResponse.json([])),
    );
    renderModal();

    expect(await screen.findByText("Tiburones FC")).toBeInTheDocument();
    expect(screen.queryByText("Halcones FC")).not.toBeInTheDocument();
  });

  it("inscribe un equipo existente con POST /inscripciones", async () => {
    server.use(
      http.get(EQUIPOS, () => HttpResponse.json([{ id: 2, nombre: "Tiburones FC", estado: "Activo" }])),
      http.get(MODALIDADES, () => HttpResponse.json([])),
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

  it("crear equipo nuevo encadena equipo → inscripción → navega al registro por lote", async () => {
    server.use(
      http.get(EQUIPOS, () => HttpResponse.json([])),
      http.get(MODALIDADES, () => HttpResponse.json([])),
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

  it("disciplina individual (tamano_equipo=1): autocompleta el nombre del equipo con el de la primera fila", async () => {
    server.use(
      http.get(EQUIPOS, () => HttpResponse.json([])),
      http.get(MODALIDADES, () =>
        HttpResponse.json([{ id: 9, nombre: "Individual", disciplina_id: 2, tamano_equipo: 1, estado: "Activo" }]),
      ),
    );
    const user = userEvent.setup();
    renderModal({ torneoModalidadId: 9 });

    await user.click(await screen.findByRole("button", { name: "+ Crear equipo nuevo" }));
    await user.type(screen.getByLabelText("Nombre fila 1"), "Micky Fernández");

    expect(screen.getByLabelText("Nombre del equipo")).toHaveValue("Micky Fernández");
    // Disciplina de tamaño 1: no tiene sentido ofrecer una segunda fila.
    expect(screen.queryByRole("button", { name: "+ agregar fila" })).not.toBeInTheDocument();
  });
});
