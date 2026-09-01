/** 3B-1 (docs/plans/cierre-backlog-todos-plan.md, offline-first en
 * Control de Mesa, alcance reducido): cola local de UN evento pendiente
 * por partido — no una cola general de N eventos (completeness 7/10 a
 * propósito, ver el plan: cubre el caso común — wifi de cancha que se
 * corta justo al cargar un evento — no un sync completo tipo CRDT).
 *
 * Funciones puras sobre localStorage, separadas del componente para
 * poder testearlas sin montar React ni mockear fetch. */

export interface EventoPendiente {
  partidos_id: number;
  jugador_id: number;
  equipo_id: number;
  eventos_id: number;
  jugador_id_entra?: number | null;
  minuto: number;
  /** Cuándo se guardó — para que la UI pueda decir "desde hace 3 min" en
   * vez de solo "hay algo pendiente". */
  guardadoEn: string;
}

function clave(partidoId: number): string {
  return `score-app.mesa-offline.${partidoId}`;
}

/** `null` si no hay nada guardado, o si el valor guardado no es JSON
 * válido (localStorage corrupto/editado a mano no debe romper la
 * pantalla, solo se trata como "no hay nada pendiente"). */
export function leerEventoPendiente(partidoId: number): EventoPendiente | null {
  try {
    const crudo = localStorage.getItem(clave(partidoId));
    if (!crudo) return null;
    return JSON.parse(crudo) as EventoPendiente;
  } catch {
    return null;
  }
}

export function guardarEventoPendiente(partidoId: number, evento: Omit<EventoPendiente, "guardadoEn">): void {
  try {
    const conFecha: EventoPendiente = { ...evento, guardadoEn: new Date().toISOString() };
    localStorage.setItem(clave(partidoId), JSON.stringify(conFecha));
  } catch {
    /* localStorage no disponible (modo privado, cuota llena) — el evento
     * se pierde si se corta la conexión, pero no rompe la carga normal. */
  }
}

export function limpiarEventoPendiente(partidoId: number): void {
  try {
    localStorage.removeItem(clave(partidoId));
  } catch {
    /* ver guardarEventoPendiente */
  }
}
