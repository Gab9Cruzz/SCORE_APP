import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "../test/msw-server";
import { createTestQueryClient } from "../test/test-utils";
import { Convocatoria } from "./Convocatoria";

const CONVOCADOS_1 = "http://127.0.0.1:8000/api/v1/partidos/1/convocados";

const PLANTILLA_LOCAL = [
  { jugador_id: 5, jugador: "Andrés Vera", equipo_id: 1, equipo: "Tiburones FC", dorsal: 9, jugador_perfil_id: 50 },
  { jugador_id: 6, jugador: "Bruno Díaz", equipo_id: 1, equipo: "Tiburones FC", dorsal: 4, jugador_perfil_id: 51 },
];
const PLANTILLA_VISITANTE = [
  { jugador_id: 7, jugador: "Carla Ruiz", equipo_id: 2, equipo: "Águilas del Sur", dorsal: 1, jugador_perfil_id: 52 },
];

function montar() {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <Convocatoria
        partidoId={1}
        nombreLocal="Tiburones FC"
        nombreVisitante="Águilas del Sur"
        plantillaLocal={PLANTILLA_LOCAL}
        plantillaVisitante={PLANTILLA_VISITANTE}
      />
    </QueryClientProvider>,
  );
}

describe("Convocatoria (3B-2, docs/plans/cierre-backlog-todos-plan.md)", () => {
  it("sin convocatoria guardada, avisa que toda la plantilla es candidata", async () => {
    server.use(http.get(CONVOCADOS_1, () => HttpResponse.json([])));
    montar();

    expect(await screen.findByText(/Sin convocatoria/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Definir convocatoria" })).toBeInTheDocument();
  });

  it("con convocatoria guardada, muestra el resumen de convocados/titulares", async () => {
    server.use(
      http.get(CONVOCADOS_1, () =>
        HttpResponse.json([
          { id: 1, partido_id: 1, jugador_perfil_id: 50, titular: true },
          { id: 2, partido_id: 1, jugador_perfil_id: 52, titular: false },
        ]),
      ),
    );
    montar();

    expect(await screen.findByText(/2 convocados \(1 titulares\)/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Editar convocatoria" })).toBeInTheDocument();
  });

  it("marca jugadores y guarda el PUT con el body correcto", async () => {
    server.use(http.get(CONVOCADOS_1, () => HttpResponse.json([])));
    let cuerpoRecibido: unknown;
    server.use(
      http.put(CONVOCADOS_1, async ({ request }) => {
        cuerpoRecibido = await request.json();
        return HttpResponse.json([{ id: 1, partido_id: 1, jugador_perfil_id: 50, titular: true }]);
      }),
    );
    const user = userEvent.setup();
    montar();

    await user.click(await screen.findByRole("button", { name: "Definir convocatoria" }));
    // Convocar a Andrés Vera (jugador_perfil_id 50) y marcarlo titular.
    await user.click(screen.getByRole("checkbox", { name: /Andrés Vera/ }));
    await user.click(screen.getByRole("checkbox", { name: "Titular" }));
    await user.click(screen.getByRole("button", { name: "Guardar convocatoria" }));

    await waitFor(() => expect(cuerpoRecibido).toEqual({ convocados: [{ jugador_perfil_id: 50, titular: true }] }));
    // Al guardar con éxito, vuelve a la vista resumen (deja de mostrar el
    // form de edición).
    await waitFor(() => expect(screen.queryByRole("button", { name: "Guardar convocatoria" })).not.toBeInTheDocument());
  });

  it("'Sacar convocatoria' manda un PUT vacío", async () => {
    server.use(
      http.get(CONVOCADOS_1, () =>
        HttpResponse.json([{ id: 1, partido_id: 1, jugador_perfil_id: 50, titular: true }]),
      ),
    );
    let cuerpoRecibido: unknown;
    server.use(
      http.put(CONVOCADOS_1, async ({ request }) => {
        cuerpoRecibido = await request.json();
        return HttpResponse.json([]);
      }),
    );
    const user = userEvent.setup();
    montar();

    await user.click(await screen.findByRole("button", { name: "Editar convocatoria" }));
    await user.click(screen.getByRole("button", { name: /Sacar convocatoria/ }));

    await waitFor(() => expect(cuerpoRecibido).toEqual({ convocados: [] }));
  });

  it("un rechazo del backend muestra el mensaje de error", async () => {
    server.use(http.get(CONVOCADOS_1, () => HttpResponse.json([])));
    server.use(
      http.put(CONVOCADOS_1, () =>
        HttpResponse.json({ detail: "Ese jugador no está en la plantilla del equipo." }, { status: 409 }),
      ),
    );
    const user = userEvent.setup();
    montar();

    await user.click(await screen.findByRole("button", { name: "Definir convocatoria" }));
    await user.click(screen.getByRole("checkbox", { name: /Andrés Vera/ }));
    await user.click(screen.getByRole("button", { name: "Guardar convocatoria" }));

    expect(await screen.findByText("Ese jugador no está en la plantilla del equipo.")).toBeInTheDocument();
  });
});
