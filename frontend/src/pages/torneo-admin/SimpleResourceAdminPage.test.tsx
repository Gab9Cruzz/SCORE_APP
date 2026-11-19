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

function renderPagina(isSelf?: (row: Fila) => boolean, conBusqueda = false) {
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
        isSelf={isSelf}
        busqueda={conBusqueda ? { etiqueta: "Buscar recurso" } : undefined}
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

    await user.click(screen.getByRole("button", { name: /^Editar/ }));

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

    await user.click(screen.getByRole("button", { name: /^Dar de baja/ }));
    // TASK-038: la baja pide confirmación.
    await user.click(screen.getByRole("button", { name: "Confirmar" }));

    await waitFor(() => expect(deleteHit).toBe(true));
  });

  it("dar de baja: muestra un mensaje si falla (roles-3-modulos-plan.md, Fase 4, D2b — antes era silencioso)", async () => {
    const user = userEvent.setup();
    server.use(
      http.delete(`${BASE}/1`, () =>
        HttpResponse.json({ detail: "no podés desactivar tu propia cuenta" }, { status: 403 }),
      ),
    );
    renderPagina();
    await screen.findByText("Uno");

    await user.click(screen.getByRole("button", { name: /^Dar de baja/ }));
    // TASK-038: la baja pide confirmación.
    await user.click(screen.getByRole("button", { name: "Confirmar" }));

    expect(await screen.findByText("no podés desactivar tu propia cuenta")).toBeInTheDocument();
  });

  it("isSelf oculta el botón de 'Dar de baja' para la propia fila (Fase 4, D2a)", async () => {
    renderPagina((row) => row.id === 1);
    await screen.findByText("Uno");

    expect(screen.queryByRole("button", { name: /^Dar de baja/ })).not.toBeInTheDocument();
    // Editar sigue disponible — isSelf solo afecta la baja.
    expect(screen.getByRole("button", { name: /^Editar/ })).toBeInTheDocument();
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

  // TASK-039 (UX-05): antes se cortaba en 200 con un aviso; ahora pagina
  // y se llega a la última fila.
  it("pagina de a 50 y llega a la última fila con 500 registros", async () => {
    const user = userEvent.setup();
    const pedidos: string[] = [];
    server.use(
      http.get(BASE, ({ request }) => {
        const url = new URL(request.url);
        pedidos.push(url.search);
        const skip = Number(url.searchParams.get("skip"));
        const limit = Number(url.searchParams.get("limit"));
        const filas = Array.from({ length: Math.max(0, Math.min(limit, 500 - skip)) }, (_, i) => ({
          id: skip + i + 1,
          nombre: `Fila ${skip + i + 1}`,
          estado: "Activo",
        }));
        return HttpResponse.json(filas, { headers: { "X-Total-Count": "500" } });
      }),
    );
    renderPagina();

    expect(await screen.findByText("Fila 1")).toBeInTheDocument();
    expect(screen.getByText(/1–50 de 500/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Anterior/ })).toBeDisabled();

    for (let i = 0; i < 9; i++) {
      await waitFor(() => expect(screen.getByRole("button", { name: /Siguiente/ })).toBeEnabled());
      await user.click(screen.getByRole("button", { name: /Siguiente/ }));
    }
    expect(await screen.findByText("Fila 500")).toBeInTheDocument();
    expect(screen.getByText(/451–500 de 500/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Siguiente/ })).toBeDisabled();
    expect(pedidos.at(-1)).toContain("skip=450");
    expect(pedidos.at(-1)).toContain("limit=50");
    // Diez páginas de clics: con toda la suite en paralelo pasa de los 5 s por defecto.
  }, 20_000);

  it("con una sola página no muestra el pie de paginación", async () => {
    renderPagina();
    await screen.findByText("Uno");
    expect(screen.queryByRole("navigation", { name: "Paginación" })).not.toBeInTheDocument();
  });

  it("la búsqueda va al servidor y vuelve a la primera página", async () => {
    const user = userEvent.setup();
    const pedidos: URLSearchParams[] = [];
    server.use(
      http.get(BASE, ({ request }) => {
        const params = new URL(request.url).searchParams;
        pedidos.push(params);
        const q = params.get("q");
        const skip = Number(params.get("skip"));
        if (q)
          return HttpResponse.json([{ id: 9, nombre: "Buscado", estado: "Activo" }], {
            headers: { "X-Total-Count": "1" },
          });
        const filas = Array.from({ length: 50 }, (_, i) => ({
          id: skip + i + 1,
          nombre: `Fila ${skip + i + 1}`,
          estado: "Activo",
        }));
        return HttpResponse.json(filas, { headers: { "X-Total-Count": "120" } });
      }),
    );
    renderPagina(undefined, true);
    await screen.findByText("Fila 1");
    await user.click(screen.getByRole("button", { name: /Siguiente/ }));
    await screen.findByText("Fila 51");

    await user.type(screen.getByRole("searchbox", { name: "Buscar recurso" }), "busc");
    expect(await screen.findByText("Buscado")).toBeInTheDocument();
    const ultimo = pedidos.at(-1)!;
    expect(ultimo.get("q")).toBe("busc");
    expect(ultimo.get("skip")).toBe("0");
  });
});
