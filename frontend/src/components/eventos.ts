/** Catálogo de tipos de evento, compartido entre el panel en vivo
 * (`MesaPanel`) y la carga de resultado directo (`ModalResultadoDirecto`).
 *
 * Vivía duplicado dentro de `ControlDeMesa.tsx` cuando los dos componentes
 * estaban en el mismo archivo; al partirlo se extrajo acá en vez de copiarlo,
 * para que agregar un tipo de evento siga siendo un cambio en un solo lugar.
 *
 * Los emoji no son decoración: son el vocabulario visual del dominio que la
 * mesa ya usa para cargar sucesos de un toque.
 */
export type TipoEvento = "Gol" | "Autogol" | "Tarjeta Amarilla" | "Tarjeta Roja" | "Cambio";

export const TIPOS: TipoEvento[] = ["Gol", "Autogol", "Tarjeta Amarilla", "Tarjeta Roja", "Cambio"];

export const TIPO_ICONO: Record<TipoEvento, string> = {
  Gol: "⚽",
  Autogol: "⚽ (en contra)",
  "Tarjeta Amarilla": "🟨",
  "Tarjeta Roja": "🟥",
  Cambio: "🔄",
};

/** Una fila de la plantilla vigente tal como la devuelve `GET /plantillas`. */
export interface PlantillaJugador {
  jugador_id: number;
  jugador: string;
  equipo_id: number;
  equipo: string;
  dorsal: number | null;
  jugador_perfil_id: number;
}

interface EventoRegistradoMinimo {
  jugador_id: number;
  jugador_id_entra: number | null;
  eventos_id: number;
}

/** Derivación de "quién sigue disponible" a partir del historial del
 * partido (modo-vivo-sustituciones-cierre-plan.md, Sección 5 — extraído
 * acá para que `CargaEvento` (MesaPanel.tsx) y `ModalSustitucion` compartan
 * el mismo cálculo en vez de que cada uno reimplemente su propia
 * heurística: exactamente el riesgo DRY que el plan señala). El modelo de
 * datos no distingue titular/suplente en el historial, así que esto es
 * "plantilla vigente menos quien ya salió o fue expulsado" — una
 * simplificación consciente, no un cálculo exacto de "quién está en
 * cancha ahora mismo". La validación AUTORITATIVA (tope de cambios,
 * no-retorno) es 100% del backend (`EventoPartidoService._validar_reglas_cambio`)
 * — esto es solo la lista de candidatos que se le ofrece al operador. */
export function calcularElegibilidadCambios(eventosRegistrados: EventoRegistradoMinimo[], eventoNombrePorId: Map<number, string>) {
  const salidosOExpulsados = new Set<number>();
  for (const e of eventosRegistrados) {
    const nombreTipo = eventoNombrePorId.get(e.eventos_id);
    if (nombreTipo === "Tarjeta Roja" || nombreTipo === "Cambio") salidosOExpulsados.add(e.jugador_id);
  }
  const yaEntraron = new Set(
    eventosRegistrados
      .filter((e) => eventoNombrePorId.get(e.eventos_id) === "Cambio" && e.jugador_id_entra !== null)
      .map((e) => e.jugador_id_entra as number),
  );
  return { salidosOExpulsados, yaEntraron };
}
