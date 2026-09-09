import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";

/** Arranca un partido correctamente, sea cual sea el tipo de cronómetro
 * (gestionar-partido-alineaciones-plan.md, H-10).
 *
 * Existe porque había DOS formas distintas de "empezar el partido" en el
 * código, con efectos distintos:
 *
 * - El botón del dashboard disparaba solo `Inicio_Partido`. En un torneo por
 *   períodos eso deja el partido "En curso" con el reloj parado en 00:00, y el
 *   operador se encontraba con OTRO botón ▶ que decía "Iniciar 1er Tiempo".
 * - `Cronometro.iniciarPrimerTiempo()` disparaba `Inicio_Partido` +
 *   `Inicio_Periodo(1)`, que es lo que el árbitro percibe como una sola acción.
 *
 * El segundo es el correcto. Este hook lo centraliza para que "Empezar
 * Partido" signifique una sola cosa en toda la app.
 *
 * `Corrido` (Tenis/Pádel) no tiene períodos: ahí `Inicio_Partido` solo es lo
 * correcto, no una simplificación.
 */
export function useEmpezarPartido(partidoId: number | null) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (tipoCronometro: "Periodos" | "Corrido") => {
      if (partidoId == null) throw new Error("Sin partido");
      const registrar = async (body: Record<string, unknown>) => {
        const { data, error } = await api.POST("/api/v1/partidos/{partido_id}/hitos", {
          params: { path: { partido_id: partidoId } },
          body,
        } as never);
        if (error) throw error;
        return data;
      };

      await registrar({ tipo_hito: "Inicio_Partido" });
      if (tipoCronometro === "Periodos") {
        // Secuencial a propósito: el backend valida la secuencia de hitos, así
        // que el segundo solo es válido después de que el primero se persistió.
        await registrar({ tipo_hito: "Inicio_Periodo", numero_periodo: 1 });
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cronometro", partidoId] });
      queryClient.invalidateQueries({ queryKey: ["partido", partidoId] });
      queryClient.invalidateQueries({ queryKey: ["partidos-mesa"] });
      queryClient.invalidateQueries({ queryKey: ["preflight-inicio", partidoId] });
    },
  });
}
