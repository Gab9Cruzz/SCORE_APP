import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { server } from "../../test/msw-server";
import { createTestQueryClient } from "../../test/test-utils";
import { DetalleEquipoPage } from "./DetalleEquipo";

/** C1 (docs/plans/cierre-pendientes-todos-plan.md): `DetalleEquipo` no
 * tenía archivo de test propio — este se escribe para cubrir búsqueda,
 * conflicto de inscripción y alta inline ANTES de migrar el modal de
 * búsqueda al `SelectorJugadorBuscable` compartido, para que el refactor
 * tenga red. Usa MemoryRouter + Routes (no `createWrapper()`) porque la
 * página usa `useParams` — mismo criterio que PerfilJugadorAdmin.test.tsx. */

const EQUIPO_5 = "http://127.0.0.1:8000/api/v1/equipos/5";
const PLANTILLA_BASE = "http://127.0.0.1:8000/api/v1/equipos/5/plantilla-base";
const VERIFICAR = "http://127.0.0.1:8000/api/v1/equipos/5/plantilla-base/verificar";
const INSCRIPCIONES = "http://127.0.0.1:8000/api/v1/inscripciones";
const JUGADORES = "http://127.0.0.1:8000/api/v1/jugadores";

function renderConRuta() {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/torneo-admin/equipos/5"]}>
        <Routes>
          <Route path="/torneo-admin/equipos/:equipoId" element={<DetalleEquipoPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function mockBase() {
  server.use(
    http.get(EQUIPO_5, () =>
      HttpResponse.json({ id: 5, nombre: "Halcones FC", disciplina_id: 1, modalidad_id: 1, estado: "Activo" }),
    ),
    http.get(PLANTILLA_BASE, () => HttpResponse.json([])),
    http.get(INSCRIPCIONES, () => HttpResponse.json([{ id: 1, torneo_id: 9 }])),
    http.get(JUGADORES, ({ request }) => {
      const q = new URL(request.url).searchParams.get("q") ?? "";
      return HttpResponse.json(
        q.trim() === "" ? [] : [{ id: 1, nombre: "Carlos Pérez", cedula: "0900000001" }],
      );
    }),
  );
}

describe("DetalleEquipoPage", () => {
  it("busca un jugador y lo agrega directo cuando no hay conflicto", async () => {
    mockBase();
    server.use(http.get(VERIFICAR, () => HttpResponse.json({ conflicto: false, equipos: [] })));
    let bodyRecibido: unknown;
    server.use(
      http.post(PLANTILLA_BASE, async ({ request }) => {
        bodyRecibido = await request.json();
        return HttpResponse.json({ id: 1 }, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderConRuta();

    await user.click(await screen.findByRole("button", { name: "+ Buscar/Agregar jugador" }));
    await user.type(await screen.findByLabelText("Buscar jugador"), "Carlos");
    await user.click(await screen.findByRole("button", { name: "Elegir" }));

    await waitFor(() => expect(bodyRecibido).toMatchObject({ jugador_id: 1, dorsal_sugerido: null }));
    // Sin conflicto: se agrega directo, el modal se cierra.
    expect(screen.queryByRole("dialog", { name: "Buscar o agregar jugador" })).not.toBeInTheDocument();
  });

  it("con conflicto de multimilitancia, muestra la advertencia y agrega solo tras confirmar", async () => {
    mockBase();
    server.use(
      http.get(VERIFICAR, () =>
        HttpResponse.json({ conflicto: true, equipos: ["Tiburones FC"], mensaje: "Ya juega en otro equipo activo." }),
      ),
    );
    let llamadas = 0;
    server.use(
      http.post(PLANTILLA_BASE, async () => {
        llamadas += 1;
        return HttpResponse.json({ id: 1 }, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderConRuta();

    await user.click(await screen.findByRole("button", { name: "+ Buscar/Agregar jugador" }));
    await user.type(await screen.findByLabelText("Buscar jugador"), "Carlos");
    await user.click(await screen.findByRole("button", { name: "Elegir" }));

    expect(await screen.findByText(/ya está inscrito en Tiburones FC/)).toBeInTheDocument();
    expect(screen.getByText("Ya juega en otro equipo activo.")).toBeInTheDocument();
    // Todavía no se agregó — la confirmación es explícita.
    expect(llamadas).toBe(0);

    await user.click(screen.getByRole("button", { name: "Agregar igual" }));
    await waitFor(() => expect(llamadas).toBe(1));
  });

  it("Volver a buscar descarta la elección conflictiva sin agregar nada", async () => {
    mockBase();
    server.use(
      http.get(VERIFICAR, () =>
        HttpResponse.json({ conflicto: true, equipos: ["Tiburones FC"], mensaje: "Ya juega en otro equipo activo." }),
      ),
    );
    let llamadas = 0;
    server.use(http.post(PLANTILLA_BASE, async () => {
      llamadas += 1;
      return HttpResponse.json({ id: 1 }, { status: 201 });
    }));
    const user = userEvent.setup();
    renderConRuta();

    await user.click(await screen.findByRole("button", { name: "+ Buscar/Agregar jugador" }));
    await user.type(await screen.findByLabelText("Buscar jugador"), "Carlos");
    await user.click(await screen.findByRole("button", { name: "Elegir" }));

    await screen.findByText(/ya está inscrito en Tiburones FC/);
    await user.click(screen.getByRole("button", { name: "Volver a buscar" }));

    expect(screen.queryByText(/ya está inscrito en Tiburones FC/)).not.toBeInTheDocument();
    expect(screen.getByLabelText("Buscar jugador")).toBeInTheDocument();
    expect(llamadas).toBe(0);
  });

  it("crea un jugador nuevo inline y lo agrega a la plantilla base", async () => {
    mockBase();
    server.use(http.get(VERIFICAR, () => HttpResponse.json({ conflicto: false, equipos: [] })));
    server.use(
      http.post(JUGADORES, async ({ request }) => {
        const body = (await request.json()) as { nombre: string; cedula: string };
        return HttpResponse.json(
          { id: 42, nombre: body.nombre, cedula: body.cedula, estado: "Activo" },
          { status: 201 },
        );
      }),
    );
    let bodyRecibido: unknown;
    server.use(
      http.post(PLANTILLA_BASE, async ({ request }) => {
        bodyRecibido = await request.json();
        return HttpResponse.json({ id: 2 }, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderConRuta();

    await user.click(await screen.findByRole("button", { name: "+ Buscar/Agregar jugador" }));
    await user.click(await screen.findByRole("button", { name: "+ Crear jugador nuevo" }));

    const [cedula, nombre, correo] = screen.getAllByRole("textbox").slice(-3);
    await user.type(cedula, "0900000099");
    await user.type(nombre, "Jugador Nuevo");
    await user.type(correo, "nuevo@example.com");
    await user.click(screen.getByRole("button", { name: "Crear y agregar" }));

    await waitFor(() => expect(bodyRecibido).toMatchObject({ jugador_id: 42, dorsal_sugerido: null }));
  });
});
