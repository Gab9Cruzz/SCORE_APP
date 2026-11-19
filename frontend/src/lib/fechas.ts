/** Fechas del negocio (TASK-028, FE-06).
 *
 * El backend devuelve las fechas con hora SIN zona ("2026-03-01T16:00:00"),
 * en la hora local del negocio (America/Guayaquil, ZONA_HORARIA del backend).
 * Interpretarlas como hora local del navegador y mostrarlas igual da la misma
 * hora de pared, así que se respetan. Lo que había que evitar:
 *
 * - `new Date("2026-03-01")` (fecha SOLA): JavaScript la toma como medianoche
 *   UTC, y en UTC−5 se muestra como el 28 de febrero.
 * - `new Date().toISOString().slice(0, 10)` como "hoy": es el día en UTC, que
 *   en Ecuador ya es mañana desde las 19:00.
 */

export const ZONA_NEGOCIO = "America/Guayaquil";
export const LOCALE = "es-EC";

const SOLO_FECHA = /^(\d{4})-(\d{2})-(\d{2})$/;

/** Una fecha sola es ese día a medianoche local; con hora y sin zona, esa
 * hora local. Una con zona explícita se respeta. */
export function parsearFecha(iso: string): Date {
  const m = SOLO_FECHA.exec(iso);
  if (m) return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  return new Date(iso);
}

export function formatearFecha(iso: string, opciones?: Intl.DateTimeFormatOptions): string {
  return parsearFecha(iso).toLocaleDateString(LOCALE, opciones);
}

export function formatearFechaHora(iso: string, opciones?: Intl.DateTimeFormatOptions): string {
  return parsearFecha(iso).toLocaleString(LOCALE, opciones);
}

export function formatearHora(iso: string, opciones?: Intl.DateTimeFormatOptions): string {
  return parsearFecha(iso).toLocaleTimeString(LOCALE, opciones);
}

/** "YYYY-MM-DD" de hoy en la zona del negocio. */
export function hoyISO(): string {
  // en-CA formatea como YYYY-MM-DD.
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: ZONA_NEGOCIO,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

/** Aritmética de días sobre "YYYY-MM-DD", sin pasar por la zona del
 * navegador ni por toISOString(). */
export function sumarDias(fechaISO: string, dias: number): string {
  const m = SOLO_FECHA.exec(fechaISO);
  if (!m) throw new Error(`Fecha inválida: ${fechaISO}`);
  const d = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]) + dias));
  const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(d.getUTCDate()).padStart(2, "0");
  return `${d.getUTCFullYear()}-${mm}-${dd}`;
}
