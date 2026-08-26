import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "../../test/msw-server";
import { createWrapper } from "../../test/test-utils";
import { SimpleResourceAdminPage } from "./SimpleResourceAdminPage";

const BASE = "http://127.0.0.1:8000/api/v1/test-resource";

interface Fila {
  id: number;
  nombre: string;
  estado: string;
}

const campos = [{ name: "nombre", label: "Nombre", type: "text" as const, required: true }];
const columnas = [
  { key: "nombre", label: "Nombre" },
  { key: "estado", label: "Estado" },
];

function renderPagina() {
  const Wrapper = createWrapper();
  return render(
    <Wrapper>
      <SimpleResourceAdminPage<Fila>
        resourceKey="test-resource"
        basePath="/api/v1/test-resource"
        title="Recursos de prueba"
        createFields={campos}
        editFields={campos}
        columns={columnas}
      />
    </Wrapper>,
  );
}

describe("SimpleResourceAdminPage", () => {
  beforeEach(() => {
    server.use(http.get(BASE, () => HttpResponse.json([{ id: 1, nombre: "Uno", estado: "Activo" }])));
  });

  it("lista los recursos existentes", async () => {
    renderPagina();
    expect(await screen.findByText("Uno")).toBeInTheDocument();
  });

  it("crear: abre el form, envía, y vuelve a la lista", async () => {
    const user = userEvent.setup();
    server.use(
      http.post(BASE, async ({ request }) => {
        const body = (await request.json()) as { nombre: string };
        return HttpResponse.json({ id: 2, nombre: body.nombre, estado: "Activo" }, { status: 201 });
      }),
    );
    renderPagina();
    await screen.findByText("Uno");

    await user.click(screen.getByRole("button", { name: "+ Nuevo" }));
    await user.type(screen.getByLabelText("Nombre"), "Dos");
    await user.click(screen.getByRole("button", { name: "Crear" }));

    // Vuelve a la lista al confirmar (onSuccess: volver).
    await waitFor(() => expect(screen.getByRole("button", { name: "+ Nuevo" })).toBeInTheDocument());
  });

  it("editar: precarga los valores de la fila elegida", async () => {
    const user = userEvent.setup();
    renderPagina();
    await screen.findByText("Uno");

    await user.click(screen.getByRole("button", { name: "Editar" }));

    expect(screen.getByLabelText("Nombre")).toHaveValue("Uno");
  });

  it("dar de baja: dispara DELETE al id de la fila", async () => {
    const user = userEvent.setup();
    let deleteHit = false;
    server.use(
      http.delete(`${BASE}/1`, () => {
        deleteHit = true;
        return HttpResponse.json({ id: 1, nombre: "Uno", estado: "Inactivo" });
      }),
    );
    renderPagina();
    await screen.findByText("Uno");

    await user.click(screen.getByRole("button", { name: "Dar de baja" }));

    await waitFor(() => expect(deleteHit).toBe(true));
  });

  it("muestra el error del backend inline al fallar la creación", async () => {
    const user = userEvent.setup();
    server.use(http.post(BASE, () => HttpResponse.json({ detail: "nombre duplicado" }, { status: 409 })));
    renderPagina();
    await screen.findByText("Uno");

    await user.click(screen.getByRole("button", { name: "+ Nuevo" }));
    await user.type(screen.getByLabelText("Nombre"), "Repetido");
    await user.click(screen.getByRole("button", { name: "Crear" }));

    expect(await screen.findByText("nombre duplicado")).toBeInTheDocument();
  });
});
