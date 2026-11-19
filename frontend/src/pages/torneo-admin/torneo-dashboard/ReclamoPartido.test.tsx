import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { server } from "../../../test/msw-server";
import { createWrapper } from "../../../test/test-utils";
import { ReclamoPartido } from "./ReclamoPartido";

const URL_RECLAMO = "http://127.0.0.1:8000/api/v1/partidos/7/reclamo";
const EQUIPOS = [
  { id: 1, nombre: "Tiburones" },
  { id: 2, nombre: "Águilas" },
];

function renderReclamo(onResuelto = vi.fn()) {
  const Wrapper = createWrapper();
  render(
    <Wrapper>
      <ReclamoPartido partidoId={7} equipos={EQUIPOS} onResuelto={onResuelto} />
    </Wrapper>,
  );
  return onResuelto;
}

describe("ReclamoPartido (TASK-009)", () => {
  it("está cerrado hasta que se pide resolver un reclamo", () => {
    renderReclamo();
    expect(screen.getByRole("button", { name: "Resolver reclamo" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Motivo")).not.toBeInTheDocument();
  });

  it("envía el equipo favorecido y el motivo", async () => {
    let cuerpo: unknown;
    server.use(
      http.post(URL_RECLAMO, async ({ request }) => {
        cuerpo = await request.json();
        return HttpResponse.json({ id: 7, ganador_reclamo_id: 2 });
      }),
    );
    const user = userEvent.setup();
    const onResuelto = renderReclamo();

    await user.click(screen.getByRole("button", { name: "Resolver reclamo" }));
    await user.selectOptions(screen.getByLabelText("A favor de"), "2");
    await user.type(screen.getByLabelText("Motivo"), "Alineación indebida");
    await user.click(screen.getByRole("button", { name: "Confirmar reclamo" }));

    await waitFor(() => expect(cuerpo).toEqual({ equipo_id: 2, motivo: "Alineación indebida" }));
    await waitFor(() => expect(onResuelto).toHaveBeenCalled());
  });

  it("no deja confirmar sin motivo", async () => {
    const user = userEvent.setup();
    renderReclamo();
    await user.click(screen.getByRole("button", { name: "Resolver reclamo" }));
    await user.selectOptions(screen.getByLabelText("A favor de"), "1");
    expect(screen.getByRole("button", { name: "Confirmar reclamo" })).toBeDisabled();
  });

  it("muestra el motivo del rechazo del servidor", async () => {
    server.use(
      http.post(URL_RECLAMO, () =>
        HttpResponse.json(
          { detail: "El partido siguiente de la llave ya empezó: el reclamo ya no puede cambiar quién avanza." },
          { status: 400 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderReclamo();
    await user.click(screen.getByRole("button", { name: "Resolver reclamo" }));
    await user.selectOptions(screen.getByLabelText("A favor de"), "2");
    await user.type(screen.getByLabelText("Motivo"), "Tarde");
    await user.click(screen.getByRole("button", { name: "Confirmar reclamo" }));

    expect(await screen.findByText(/ya empezó/)).toBeInTheDocument();
  });
});
