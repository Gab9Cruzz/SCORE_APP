import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { server } from "../../test/msw-server";
import { createTestQueryClient } from "../../test/test-utils";
import { BarraDisciplinasPublica } from "./BarraDisciplinasPublica";

const CON_PARTIDOS = "http://127.0.0.1:8000/api/v1/disciplinas/con-partidos";

function renderBarra(deporteSeleccionado: string | null = null, onSeleccionar = vi.fn()) {
  const queryClient = createTestQueryClient();
  return {
    onSeleccionar,
    ...render(
      <QueryClientProvider client={queryClient}>
        <BarraDisciplinasPublica deporteSeleccionado={deporteSeleccionado} onSeleccionar={onSeleccionar} />
      </QueryClientProvider>,
    ),
  };
}

describe("BarraDisciplinasPublica (portal-publico-feed-partidos-plan.md, T2.2/C8/D5)", () => {
  it("C8: con ≤1 disciplina con contenido, no se renderiza nada", async () => {
    let respondido = false;
    server.use(
      http.get(CON_PARTIDOS, () => {
        respondido = true;
        return HttpResponse.json([{ id: 1, slug: "futbol", nombre: "Fútbol" }]);
      }),
    );
    const { container } = renderBarra();
    // Espera a que la query resuelva antes de afirmar la ausencia. Antes era
    // un setTimeout de 50 ms: con la máquina cargada (la suite con
    // cobertura) la query seguía en vuelo, se veía el esqueleto de carga
    // —que usa la misma clase— y la prueba fallaba sin motivo.
    await waitFor(() => expect(respondido).toBe(true));
    await waitFor(() => expect(container.querySelector(".barra-disciplinas-publica")).not.toBeInTheDocument());
  });

  it("con 2+ disciplinas, se renderiza una pill por cada una", async () => {
    server.use(
      http.get(CON_PARTIDOS, () =>
        HttpResponse.json([
          { id: 1, slug: "futbol", nombre: "Fútbol" },
          { id: 3, slug: "tenis", nombre: "Tenis" },
        ]),
      ),
    );
    renderBarra();
    expect(await screen.findByRole("button", { name: /Fútbol/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Tenis/ })).toBeInTheDocument();
  });

  it("clickear una pill activa llama onSeleccionar(null) — toggle apaga el filtro", async () => {
    server.use(
      http.get(CON_PARTIDOS, () =>
        HttpResponse.json([
          { id: 1, slug: "futbol", nombre: "Fútbol" },
          { id: 3, slug: "tenis", nombre: "Tenis" },
        ]),
      ),
    );
    const user = userEvent.setup();
    const { onSeleccionar } = renderBarra("futbol");
    const pill = await screen.findByRole("button", { name: /Fútbol/ });
    expect(pill).toHaveAttribute("aria-pressed", "true");
    await user.click(pill);
    expect(onSeleccionar).toHaveBeenCalledWith(null);
  });

  it("D5c: la disciplina de la URL no está en el sidecar — su pill se muestra igual, activa", async () => {
    server.use(
      http.get(CON_PARTIDOS, () =>
        HttpResponse.json([
          { id: 1, slug: "futbol", nombre: "Fútbol" },
          { id: 3, slug: "tenis", nombre: "Tenis" },
        ]),
      ),
    );
    renderBarra("baloncesto");
    const pill = await screen.findByRole("button", { name: /baloncesto/i });
    expect(pill).toHaveAttribute("aria-pressed", "true");
  });
});
