/** Slots de gol generados por el input de marcador en "Cargar resultado
 * directo" (goles-por-marcador-slots-plan.md, Fase 1 0C-bis Alternativa A —
 * reversión de D1). El marcador NO es una estructura de datos aparte: cada
 * slot vive acá, el marcador que el operador ve es la CUENTA de slots por
 * lado — nunca puede desincronizarse porque es el mismo array, no dos
 * fuentes de verdad a mantener sincronizadas a mano.
 *
 * Reconciliación (Design Fase 2, Pass 3 — el problema que D1 dejó sin
 * diseñar el 2026-09-08): subir el marcador agrega slots vacíos al final;
 * bajarlo primero intenta quitar slots VACÍOS (nada que perder, sin pedir
 * nada); si no alcanzan, no descarta nada solo — devuelve
 * `pendienteConfirmar` con los candidatos llenos para que la UI muestre el
 * modal de confirmación (sugerencia: el más reciente, con escape hatch
 * "cancelar, mantener el marcador anterior" — eso vive en el componente,
 * no acá, esta función es pura). */

export interface SlotGol {
  id: string;
  lado: "local" | "visitante";
  jugadorId: number | null;
  minuto: string;
}

export function contarSlots(slots: SlotGol[], lado: "local" | "visitante"): number {
  return slots.filter((s) => s.lado === lado).length;
}

export interface ResultadoReconciliacion {
  slots: SlotGol[];
  /** No-null = la baja de marcador afecta al menos 1 slot LLENO — la UI
   * debe mostrar el modal de confirmación con estos candidatos antes de
   * aplicar nada. `slots` en este caso es IGUAL al array de entrada (sin
   * tocar) — el descarte real lo hace `descartarSlotYReconciliar` una vez
   * que el operador elige. */
  pendienteConfirmar: { lado: "local" | "visitante"; candidatos: SlotGol[] } | null;
}

export function reconciliarSlots(
  slotsActuales: SlotGol[],
  lado: "local" | "visitante",
  marcadorNuevo: number,
  crearId: () => string,
): ResultadoReconciliacion {
  const deEsteLado = slotsActuales.filter((s) => s.lado === lado);
  const actual = deEsteLado.length;

  if (marcadorNuevo === actual) {
    return { slots: slotsActuales, pendienteConfirmar: null };
  }

  if (marcadorNuevo > actual) {
    const nuevos = [...slotsActuales];
    for (let i = actual; i < marcadorNuevo; i++) {
      nuevos.push({ id: crearId(), lado, jugadorId: null, minuto: "" });
    }
    return { slots: nuevos, pendienteConfirmar: null };
  }

  // marcadorNuevo < actual: hay que quitar (actual - marcadorNuevo) slots
  // de este lado. Primero los vacíos (jugador y/o minuto sin completar) —
  // esos se pueden quitar sin preguntar nada, no hay dato que perder.
  const exceso = actual - marcadorNuevo;
  const vacios = deEsteLado.filter((s) => s.jugadorId === null || s.minuto === "");
  if (vacios.length >= exceso) {
    const idsAQuitar = new Set(vacios.slice(0, exceso).map((s) => s.id));
    return { slots: slotsActuales.filter((s) => !idsAQuitar.has(s.id)), pendienteConfirmar: null };
  }

  // No alcanza con los vacíos — al menos 1 slot LLENO quedaría afectado.
  // Nunca se descarta sin confirmación explícita (Sección 1 del plan:
  // "nunca un borrado silencioso").
  const llenos = deEsteLado.filter((s) => s.jugadorId !== null && s.minuto !== "");
  return { slots: slotsActuales, pendienteConfirmar: { lado, candidatos: llenos } };
}

/** El operador confirmó CUÁL slot lleno descartar (Design Fase 2, Pass 3) —
 * lo quita y, si todavía sobran slots de ese lado tras el descarte, vuelve
 * a intentar la reconciliación completa (puede hacer falta descartar más
 * de 1, ej. bajar el marcador en 2 de una vez). */
export function descartarSlotYReconciliar(
  slotsActuales: SlotGol[],
  slotId: string,
  lado: "local" | "visitante",
  marcadorNuevo: number,
  crearId: () => string,
): ResultadoReconciliacion {
  const sinEseSlot = slotsActuales.filter((s) => s.id !== slotId);
  return reconciliarSlots(sinEseSlot, lado, marcadorNuevo, crearId);
}

/** Autogol inferido del equipo del jugador elegido (Design Fase 2, Pass 7):
 * si el jugador pertenece al plantel RIVAL del lado del slot, el evento se
 * guarda como Autogol acreditado a ese lado — mismo criterio que
 * `acreditadoLocal` en `MesaPanel.tsx` (`tipo === "Autogol" ? equipo_id !==
 * equipoLocalId : equipo_id === equipoLocalId`), para que el invariante
 * "marcador = f(eventos)" no se rompa en partidos con autogol (Eng
 * corrección 5 — la razón por la que este helper es una función aparte,
 * testeada, en vez de un cálculo inline en el componente). */
export function resolverTipoYEquipoDeSlot(
  slot: SlotGol,
  equipoLocalId: number,
  equipoVisitanteId: number,
  equipoIdDelJugador: (jugadorId: number) => number | undefined,
): { tipo: "Gol" | "Autogol"; equipoId: number } | null {
  if (slot.jugadorId === null) return null;
  const ladoEquipoId = slot.lado === "local" ? equipoLocalId : equipoVisitanteId;
  const jugadorEquipoId = equipoIdDelJugador(slot.jugadorId);
  if (jugadorEquipoId != null && jugadorEquipoId !== ladoEquipoId) {
    return { tipo: "Autogol", equipoId: jugadorEquipoId };
  }
  return { tipo: "Gol", equipoId: ladoEquipoId };
}
