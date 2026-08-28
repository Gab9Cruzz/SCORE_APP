/**
 * Icono por disciplina (equipos-disciplina-navegacion-plan.md, Decisión
 * de diseño #8).
 *
 * Emoji, no SVG: el catálogo tiene 28 disciplinas, y 28 iconos propios son
 * 28 assets de diseño que este plan no incluye. Vive en su PROPIO módulo
 * justamente para que cambiarlos después sea reemplazar este archivo, no
 * tocar la barra de navegación ni la grilla de equipos.
 *
 * Las claves son los nombres exactos de 11_catalogo_disciplinas.sql. La
 * búsqueda es tolerante a mayúsculas/acentos porque el nombre viene de la
 * base y un cambio de tipeo no debería dejar la barra sin iconos.
 */
const ICONOS: Record<string, string> = {
  futbol: "⚽",
  "futbol americano / flag football": "🏈",
  baloncesto: "🏀",
  voleibol: "🏐",
  handbol: "🤾",
  rugby: "🏉",
  tenis: "🎾",
  "ping pong": "🏓",
  badminton: "🏸",
  "squash / racquetball": "🎾",
  pickleball: "🥒",
  "fronton / pelota vasca": "🪀",
  atletismo: "🏃",
  natacion: "🏊",
  ciclismo: "🚴",
  gimnasia: "🤸",
  crossfit: "🏋️",
  mma: "🥋",
  boxeo: "🥊",
  judo: "🥋",
  taekwondo: "🥋",
  karate: "🥋",
  "league of legends": "🎮",
  "cs:go": "🎮",
  valorant: "🎮",
  "rocket league": "🚗",
  "fifa / ea fc": "🎮",
  ajedrez: "♟️",
};

/** Normaliza para que "Fútbol", "FUTBOL" y "futbol" caigan en la misma
 * clave — el catálogo trae acentos y la clave del mapa no. */
function normalizar(nombre: string): string {
  return nombre
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "");
}

/** El emoji de la disciplina, o `null` si no hay uno mapeado — el llamador
 * decide el fallback (la barra usa la inicial en un círculo). Devolver
 * `null` en vez de un emoji genérico es a propósito: un icono equivocado
 * confunde más que ninguno. */
export function iconoDisciplina(nombre: string | undefined | null): string | null {
  if (!nombre) return null;
  return ICONOS[normalizar(nombre)] ?? null;
}

/** Fallback visual: la inicial. Se usa cuando `iconoDisciplina` no
 * encuentra nada — una disciplina nueva en el catálogo aparece igual en la
 * barra, con su letra, en vez de quedar sin marca. */
export function inicialDisciplina(nombre: string | undefined | null): string {
  if (!nombre) return "?";
  return nombre.trim().charAt(0).toUpperCase();
}
