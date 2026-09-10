import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { server } from "../../test/msw-server";
import { createTestQueryClient } from "../../test/test-utils";
import { ModalResultadoDirecto } from "./ModalResultadoDirecto";

/** goles-por-marcador-slots-plan.md — reversión de D1: la UI de slots por
 * marcador, el Quick Action Bar, el filtrado titular/suplente con
 * degradación con gracia (D4), y el timeline ascendente reactivo. */

const BASE = "http://127.0.0.1:8000/api/v1";
const PARTIDO = { id: 3, equipos_id_local: 1, equipos_id_visitante: 2 };
const NOMBRE_EQUIPO = new Map([[1, "Tiburones FC"], [2, "Águilas del Sur"]]);

const JUGADOR_LOCAL = { jugador_id: 5, jugador: "Andrés Vera", equipo_id: 1, equipo: "Tiburones FC", dorsal: 9, jugador_perfil_id: 50 };
const JUGADOR_LOCAL_TITULAR2 = { jugador_id: 7, jugador: "Diego Paz", equipo_id: 1, equipo: "Tiburones FC", dorsal: 3, jugador_perfil_id: 52 };
const JUGADOR_LOCAL_SUPLENTE = { jugador_id: 6, jugador: "Bruno Salas", equipo_id: 1, equipo: "Tiburones FC", dorsal: 12, jugador_perfil_id: 51 };
const JUGADOR_VISITANTE = { jugador_id: 1, jugador: "Carlos Ruiz", equipo_id: 2, equipo: "Águilas del Sur", dorsal: 4, jugador_perfil_id: 10 };

function sembrarBackend(opts: { conConvocatoria?: boolean } = {}) {
  server.use(
    http.get(`${BASE}/partidos/3/cronometro`, () => HttpResponse.json({ tipo_cronometro: "Periodos", partido_iniciado: false })),
    http.get(`${BASE}/estadisticas/equipos/1/plantilla`, () =>
      HttpResponse.json([JUGADOR_LOCAL, JUGADOR_LOCAL_TITULAR2, JUGADOR_LOCAL_SUPLENTE]),
    ),
    http.get(`${BASE}/estadisticas/equipos/2/plantilla`, () => HttpResponse.json([JUGADOR_VISITANTE])),
    http.get(`${BASE}/eventos`, () =>
      HttpResponse.json([
        { id: 1, nombre: "Gol", estado: "Activo" },
        { id: 2, nombre: "Autogol", estado: "Activo" },
        { id: 3, nombre: "Tarjeta Amarilla", estado: "Activo" },
        { id: 4, nombre: "Tarjeta Roja", estado: "Activo" },
        { id: 5, nombre: "Cambio", estado: "Activo" },
      ]),
    ),
    http.get(`${BASE}/partidos/3/convocados`, () =>
      HttpResponse.json(
        opts.conConvocatoria
          ? [
              { jugador_perfil_id: JUGADOR_LOCAL.jugador_perfil_id, titular: true },
              { jugador_perfil_id: JUGADOR_LOCAL_TITULAR2.jugador_perfil_id, titular: true },
              { jugador_perfil_id: JUGADOR_LOCAL_SUPLENTE.jugador_perfil_id, titular: false },
            ]
          : [],
      ),
    ),
  );
}

function montar(onGuardado = vi.fn()) {
  const queryClient = createTestQueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <ModalResultadoDirecto partido={PARTIDO} nombreEquipo={NOMBRE_EQUIPO} onClose={vi.fn()} onGuardado={onGuardado} />
    </QueryClientProvider>,
  );
  return { onGuardado };
}

/** `fireEvent.change` en vez de `userEvent.type` a propósito:
 * `<input type="number">` no soporta seleccionar texto (`setSelectionRange`
 * tira en un input numérico, en el navegador real y en jsdom) — un
 * `{selectall}` de user-event no limpia nada, así que escribir un dígito
 * cuando ya hay otro APPENDEA en vez de reemplazar ("3" + "1" → "31", no
 * "1"). Un cambio de valor único, como dispara un input real al perder el
 * foco con el valor final, evita ese problema por completo. */
async function escribirMarcador(lado: "Local" | "Visitante", valor: string) {
  const input = await screen.findByLabelText(new RegExp(`Goles ${lado === "Local" ? "Tiburones FC" : "Águilas del Sur"}`));
  fireEvent.change(input, { target: { value: valor } });
}

describe("ModalResultadoDirecto — slots por marcador", () => {
  it("ingresar el marcador genera exactamente esa cantidad de slots por lado", async () => {
    sembrarBackend();
    montar();

    await escribirMarcador("Local", "2");
    await escribirMarcador("Visitante", "1");

    expect(await screen.findAllByLabelText(/Goleador, Tiburones FC/)).toHaveLength(2);
    expect(screen.getAllByLabelText(/Goleador, Águilas del Sur/)).toHaveLength(1);
  });

  it("bajar el marcador sin slots llenos no pide confirmación", async () => {
    sembrarBackend();
    montar();

    await escribirMarcador("Local", "3");
    await escribirMarcador("Local", "1");

    expect(screen.getAllByLabelText(/Goleador, Tiburones FC/)).toHaveLength(1);
    expect(screen.queryByRole("heading", { name: /Bajaste el marcador/ })).not.toBeInTheDocument();
  });

  it("bajar el marcador con slots llenos pide confirmación explícita, nunca borra solo", async () => {
    sembrarBackend();
    const user = userEvent.setup();
    montar();

    await escribirMarcador("Local", "2");
    const selects = screen.getAllByLabelText(/Goleador, Tiburones FC/);
    await user.selectOptions(selects[0], String(JUGADOR_LOCAL.jugador_id));
    const minutos = screen.getAllByLabelText(/Minuto, Tiburones FC/);
    await user.type(minutos[0], "23");

    await escribirMarcador("Local", "0");

    expect(await screen.findByRole("heading", { name: /Bajaste el marcador/ })).toBeInTheDocument();
    // Escape hatch: cancelar mantiene el marcador anterior, el slot lleno sigue.
    await user.click(screen.getByRole("button", { name: /Cancelar — mantener marcador anterior/ }));
    expect(screen.queryByRole("heading", { name: /Bajaste el marcador/ })).not.toBeInTheDocument();
    expect(screen.getAllByLabelText(/Goleador, Tiburones FC/)).toHaveLength(2);
  });

  it("un jugador del equipo rival en un slot Local se guarda como Autogol acreditado a Local", async () => {
    sembrarBackend();
    let cuerpoEnviado: { eventos: { equipo_id: number; eventos_id: number; jugador_id: number }[] } | undefined;
    server.use(
      http.post(`${BASE}/partidos/3/resultado-directo`, async ({ request }) => {
        cuerpoEnviado = (await request.json()) as never;
        return HttpResponse.json({ id: 3, estado: "Finalizado" });
      }),
    );
    const user = userEvent.setup();
    const { onGuardado } = montar();

    await escribirMarcador("Local", "1");
    const select = screen.getByLabelText(/Goleador, Tiburones FC #1/);
    // Jugador del plantel VISITANTE en un slot de la columna LOCAL → autogol.
    await user.selectOptions(select, String(JUGADOR_VISITANTE.jugador_id));
    await user.type(screen.getByLabelText(/Minuto, Tiburones FC #1/), "15");

    await user.click(screen.getByRole("button", { name: "Guardar resultado" }));

    await waitFor(() => expect(onGuardado).toHaveBeenCalled());
    expect(cuerpoEnviado?.eventos).toEqual([
      { jugador_id: JUGADOR_VISITANTE.jugador_id, equipo_id: 2, eventos_id: 2, jugador_id_entra: null, minuto: 15 },
    ]);
  });
});

describe("ModalResultadoDirecto — Quick Action Bar y filtrado de Cambio", () => {
  it("Amarilla abre un formulario chico pidiendo jugador y minuto", async () => {
    sembrarBackend();
    const user = userEvent.setup();
    montar();

    await user.click(await screen.findByRole("button", { name: /Tarjeta Amarilla/ }));
    await user.selectOptions(screen.getByLabelText("Equipo"), "1");
    await user.selectOptions(screen.getByLabelText("Jugador"), String(JUGADOR_LOCAL.jugador_id));
    await user.type(screen.getByLabelText("Minuto"), "40");
    await user.click(screen.getByRole("button", { name: "+ Agregar" }));

    expect(await screen.findByText("40'")).toBeInTheDocument();
  });

  it("con convocatoria: Cambio filtra Sale a titulares y Entra a suplentes, estrictamente", async () => {
    sembrarBackend({ conConvocatoria: true });
    const user = userEvent.setup();
    montar();

    await user.click(await screen.findByRole("button", { name: /Cambio/ }));
    await user.selectOptions(screen.getByLabelText("Equipo"), "1");

    const sale = screen.getByLabelText(/Sale \(solo titulares\)/);
    expect(within(sale).getByText(/Andrés Vera/)).toBeInTheDocument();
    expect(within(sale).queryByText(/Bruno Salas/)).not.toBeInTheDocument();

    await user.selectOptions(sale, String(JUGADOR_LOCAL.jugador_id));
    const entra = screen.getByLabelText(/Entra \(solo suplentes\)/);
    expect(within(entra).getByText(/Bruno Salas/)).toBeInTheDocument();
    expect(within(entra).queryByText(/Andrés Vera/)).not.toBeInTheDocument();
  });

  it("sin convocatoria: degrada con gracia (plantilla completa) y muestra el banner persistente", async () => {
    sembrarBackend({ conConvocatoria: false });
    const user = userEvent.setup();
    montar();

    expect(await screen.findByText(/Sin convocatoria guardada para este partido/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Cambio/ }));
    await user.selectOptions(screen.getByLabelText("Equipo"), "1");
    const sale = screen.getByLabelText(/Sale \(solo titulares\)/);
    // Sin convocatoria, ambos jugadores del equipo son candidatos (D4).
    expect(within(sale).getByText(/Andrés Vera/)).toBeInTheDocument();
    expect(within(sale).getByText(/Bruno Salas/)).toBeInTheDocument();
  });

  it("un jugador ya marcado como 'Entra' en otro Cambio del mismo batch no puede repetirse", async () => {
    sembrarBackend({ conConvocatoria: true });
    const user = userEvent.setup();
    montar();

    // Primer Cambio: sale Andrés Vera, entra Bruno Salas.
    await user.click(await screen.findByRole("button", { name: /Cambio/ }));
    await user.selectOptions(screen.getByLabelText("Equipo"), "1");
    await user.selectOptions(screen.getByLabelText(/Sale/), String(JUGADOR_LOCAL.jugador_id));
    await user.selectOptions(screen.getByLabelText(/Entra/), String(JUGADOR_LOCAL_SUPLENTE.jugador_id));
    await user.type(screen.getByLabelText("Minuto"), "30");
    await user.click(screen.getByRole("button", { name: "+ Agregar" }));

    // Bruno Salas ya entró — no debería quedar disponible en un 2do Cambio,
    // aunque salga otro titular (Diego Paz, todavía disponible).
    await user.click(screen.getByRole("button", { name: /Cambio/ }));
    await user.selectOptions(screen.getByLabelText("Equipo"), "1");
    await user.selectOptions(screen.getByLabelText(/Sale/), String(JUGADOR_LOCAL_TITULAR2.jugador_id));
    const entra = screen.getByLabelText(/Entra \(solo suplentes\)/);
    expect(within(entra).queryByText(/Bruno Salas/)).not.toBeInTheDocument();
  });
});

describe("ModalResultadoDirecto — timeline ascendente y reactivo", () => {
  it("reordena automáticamente de menor a mayor minuto en tiempo real", async () => {
    sembrarBackend();
    const user = userEvent.setup();
    montar();

    // Amarilla al minuto 40.
    await user.click(await screen.findByRole("button", { name: /Tarjeta Amarilla/ }));
    await user.selectOptions(screen.getByLabelText("Equipo"), "1");
    await user.selectOptions(screen.getByLabelText("Jugador"), String(JUGADOR_LOCAL.jugador_id));
    await user.type(screen.getByLabelText("Minuto"), "40");
    await user.click(screen.getByRole("button", { name: "+ Agregar" }));

    // Gol al minuto 2 (vía slot).
    await escribirMarcador("Local", "1");
    await user.selectOptions(screen.getByLabelText(/Goleador, Tiburones FC/), String(JUGADOR_LOCAL.jugador_id));
    await user.type(screen.getByLabelText(/Minuto, Tiburones FC/), "2");

    const filas = screen.getAllByText(/'$/); // "2'" y "40'"
    expect(filas[0]).toHaveTextContent("2'");
    expect(filas[1]).toHaveTextContent("40'");
  });
});
