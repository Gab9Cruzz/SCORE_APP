import type { Rol } from "./authContextValue";

/** Página de inicio de cada rol (roles-3-modulos-plan.md, Fase 2, D2). La
 * usan el login (adónde ir después de entrar), "sin permiso" y la 404
 * ("Ir a mi inicio"). */
export function landingPorRol(rol: Rol | undefined): string {
  if (rol === "TorneoAdmin" || rol === "AdminGeneral") return "/torneo-admin";
  // Fase 3, D3: Árbitro tiene su propia landing ("Mis partidos") — el
  // resto (Publico, sin sesión) sigue cayendo en /dashboard sin cambios.
  if (rol === "Arbitro") return "/arbitro";
  return "/dashboard";
}
