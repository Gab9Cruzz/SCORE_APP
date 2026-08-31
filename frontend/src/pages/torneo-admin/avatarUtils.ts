/**
 * Fallback visual para la tarjeta de jugador cuando no hay Foto_URL (grid
 * de Plantillas — motor-formatos-plantillas-navegacion-plan.md, Design
 * sección D). Mismo criterio que iconosDisciplina.ts: un módulo propio y
 * chico, sin acoplar el cálculo a ningún componente puntual.
 *
 * "Jugador sin foto | Círculo con iniciales, color determinístico por
 * Jugador_ID (mismo jugador = mismo color siempre)" — estados de
 * interacción del grid, Fase 2 del plan.
 */
const PALETA_AVATAR = [
  "#2f6f4f",
  "#3a5a8c",
  "#8c4a3a",
  "#6b4a8c",
  "#4a8c7c",
  "#8c7a3a",
  "#3a748c",
  "#8c3a6b",
];

/** Inicial + inicial del último nombre — "Juan Pérez" → "JP". Un solo
 * nombre ("Nadal") → solo esa inicial, sin duplicarla. */
export function inicialesJugador(nombre: string | undefined | null): string {
  const partes = (nombre ?? "").trim().split(/\s+/).filter(Boolean);
  if (partes.length === 0) return "?";
  const primera = partes[0].charAt(0);
  const ultima = partes.length > 1 ? partes[partes.length - 1].charAt(0) : "";
  return (primera + ultima).toUpperCase();
}

/** Determinístico por ID (no por nombre): dos jugadores homónimos no
 * comparten color, y el mismo jugador nunca cambia de color entre
 * renders. */
export function colorAvatar(jugadorId: number): string {
  return PALETA_AVATAR[Math.abs(jugadorId) % PALETA_AVATAR.length];
}
