import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "../test/msw-server";
import { createTestQueryClient } from "../test/test-utils";
import { Cronometro } from "./Cronometro";

const CRONOMETRO_3 = "http://127.0.0.1:8000/api/v1/partidos/3/cronometro";
const HITOS_3 = "http://127.0.0.1:8000/api/v1/partidos/3/hitos";

// Torneo a 2 períodos, 2do período (el último) ABIERTO — el backend recién
// habilita "Fin_Partido" en acciones_permitidas DESPUÉS de que ese período
// se cierre (HitoPartidoService._calcular_estado). Mismo fixture que
// reprodujo el 400 real: "hitos válidos ahora: Pausa, Fin_Periodo".
const CRONOMETRO_ULTIMO_PERIODO_ABIERTO = {
  tipo_cronometro: "Periodos",
  cantidad_periodos: 2,
  duracion_periodo_minutos: 45,
  duracion_descanso_minutos: 15,
  partido_iniciado: true,
  partido_finalizado: false,
  periodo_abierto: 2,
  ultimo_periodo_cerrado: 1,
  en_pausa: false,
  acciones_permitidas: ["Pausa", "Fin_Periodo"],
  hitos: [
    {
      id: 1,
      tipo_hito: "Inicio_Partido",
      numero_periodo: null,
      timestamp_real: new Date().toISOString(),
      minuto_reloj: null,
      registrado_por: 42,
      fecha_registro: new Date().toISOString(),
    },
  ],
};

function renderCronometro() {
  const queryClient = createTestQueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <Cronometro
        partidoId={3}
        equipoLocalId={1}
        equipoVisitanteId={2}
        nombreLocal="Local"
        nombreVisitante="Visitante"
        mostrarInicio={false}
      />
    </QueryClientProvider>,
  );
}

describe("Cronometro — Fin del Partido en el último período", () => {
  beforeEach(() => {
    server.use(
      http.get(CRONOMETRO_3, () => HttpResponse.json(CRONOMETRO_ULTIMO_PERIODO_ABIERTO)),
    );
  });

  it('registra Fin_Periodo del período abierto ANTES de Fin_Partido, no Fin_Partido directo (regresión del 400 "hitos válidos ahora")', async () => {
    const tiposRecibidos: string[] = [];
    server.use(
      http.post(HITOS_3, async ({ request }) => {
        const body = (await request.json()) as { tipo_hito: string; numero_periodo?: number };
        tiposRecibidos.push(body.tipo_hito);
        if (body.tipo_hito === "Fin_Partido" && tiposRecibidos[0] !== "Fin_Periodo") {
          // Simula la validación real del backend (HitoPartidoService):
          // Fin_Partido sin haber cerrado antes el último período se
          // rechaza con 400.
          return HttpResponse.json(
            { detail: "No se puede registrar 'Fin_Partido' en el estado actual del partido (hitos válidos ahora: Pausa, Fin_Periodo)." },
            { status: 400 },
          );
        }
        return HttpResponse.json({ id: 99 }, { status: 201 });
      }),
    );

    renderCronometro();

    const boton = await screen.findByRole("button", { name: "Fin del Partido" });
    await userEvent.click(boton);

    await waitFor(() => expect(tiposRecibidos).toEqual(["Fin_Periodo", "Fin_Partido"]));
    // Sin esto, el click mandaba solo ["Fin_Partido"] y el backend
    // devolvía 400 — el árbitro veía el error tal cual lo reportó el
    // usuario real.
    expect(screen.queryByText(/No se puede registrar/i)).not.toBeInTheDocument();
  });
});
