/** Desempate de eliminatoria: tiempo extra y penales
 * (docs/plans/desempate-tiempo-extra-penales-plan.md, §11 "Matriz de
 * render"). `Metodo_Desempate` x `Hubo_Tiempo_Extra` tiene ocho celdas —
 * compartida por BracketView, PartidosDelTorneo y DetalleTorneoPublico
 * para que las tres superficies rendericen el mismo string ante los
 * mismos datos (una sola fuente de verdad, no tres implementaciones que
 * puedan divergir). Dos celdas son "imposibles" (los triggers las
 * rechazan, `06_triggers.sql` fn_validar_forma_desempate) — no se
 * distinguen acá, caen al mismo string que su celda vecina válida en vez
 * de mostrar un estado que nunca debería poder pasar. */

export type MetodoDesempate = "Tiempo_Extra" | "Penales" | "Manual" | null | undefined;

export interface ResultadoDesempate {
  golesLocal: number;
  golesVisitante: number;
  metodoDesempate: MetodoDesempate;
  huboTiempoExtra: boolean | null | undefined;
  penalesLocal: number | null | undefined;
  penalesVisitante: number | null | undefined;
}

/** `title`/`aria-label` de la anotación "(def.)" — D-D15: nunca un valor
 * sin explicar. */
export const DEF_ARIA_LABEL = "Definido por decisión — sin marcador de tanda";

/** String completo — "2-2 a.e.t. (4-2 pen.)" — para PartidosDelTorneo y
 * DetalleTorneoPublico (D-D9: string completo inline). */
export function formatearResultadoDesempate(r: ResultadoDesempate): string {
  const marcador = `${r.golesLocal} - ${r.golesVisitante}`;
  const aet = r.huboTiempoExtra ? " a.e.t." : "";
  if (r.metodoDesempate === "Penales" && r.penalesLocal != null && r.penalesVisitante != null) {
    return `${marcador}${aet} (${r.penalesLocal}-${r.penalesVisitante} pen.)`;
  }
  if (r.metodoDesempate === "Manual") {
    return `${marcador}${aet} (def.)`;
  }
  // 'Tiempo_Extra' (siempre trae Hubo_Tiempo_Extra=TRUE, S3) y NULL (sin
  // empate que resolver) comparten el mismo formato: el sufijo a.e.t. ya
  // lo agrega `aet` arriba cuando corresponde.
  return `${marcador}${aet}`;
}

/** Línea en prosa para DetalleTorneoPublico ("Definido en penales 4-2
 * tras 2-2 en el tiempo extra") — `null` cuando no hay nada que contar
 * (el caso normal, sin empate). */
export function fraseResultadoDesempate(r: ResultadoDesempate): string | null {
  if (r.metodoDesempate === "Penales" && r.penalesLocal != null && r.penalesVisitante != null) {
    const marcador = `${r.golesLocal}-${r.golesVisitante}`;
    return r.huboTiempoExtra
      ? `Definido en penales ${r.penalesLocal}-${r.penalesVisitante} tras ${marcador} en el tiempo extra.`
      : `Definido en penales ${r.penalesLocal}-${r.penalesVisitante} tras ${marcador} en el tiempo regular.`;
  }
  if (r.metodoDesempate === "Tiempo_Extra") {
    return `Definido en el tiempo extra ${r.golesLocal}-${r.golesVisitante}.`;
  }
  if (r.metodoDesempate === "Manual") {
    return r.huboTiempoExtra
      ? "Empate tras el tiempo extra, resuelto por decisión."
      : "Empate en tiempo regular, resuelto por decisión.";
  }
  return null;
}

/** Badge compacto para BracketView (D-D9) — SOLO la tanda ("pen. 4-2"),
 * pensado para no envolver junto al marcador/global ya mostrado aparte.
 * `null` si no hubo tanda. */
export function badgePenales(r: ResultadoDesempate): string | null {
  if (r.metodoDesempate !== "Penales" || r.penalesLocal == null || r.penalesVisitante == null) return null;
  return `pen. ${r.penalesLocal}-${r.penalesVisitante}`;
}

/** D-D8: el chip de regla vigente — "Empate → tiempo extra" / "Empate →
 * penales" / "Empate → lo decidís vos", en la cabecera de mesa/cronómetro
 * de todo partido de Eliminación. `null` si no hay nada confiable que
 * mostrar (nunca se inventa un valor — §11-bis: "oculto si no se pudo
 * leer"). `'Penales_Salvo_Final'` es una regla de CUADRO (no puede
 * aparecer en `Metodo_Desempate_Aplicable`, que ya viene resuelto a un
 * método concreto) pero SÍ puede ser la regla del TORNEO todavía sin
 * snapshotear — se contempla acá para ese caso, antes de que el partido
 * arranque. */
export type MetodoDesempateEliminatoriaOTorneo =
  | "Manual"
  | "Penales_Directo"
  | "Tiempo_Extra_Penales"
  | "Penales_Salvo_Final"
  | null
  | undefined;

export function etiquetaReglaDesempate(metodo: MetodoDesempateEliminatoriaOTorneo): string | null {
  switch (metodo) {
    case "Manual":
      return "Empate → lo decidís vos";
    case "Penales_Directo":
      return "Empate → penales";
    case "Tiempo_Extra_Penales":
      return "Empate → tiempo extra";
    case "Penales_Salvo_Final":
      return "Empate → penales (tiempo extra en la Final)";
    default:
      return null;
  }
}

/** Versión corta para la coletilla del global en una vuelta —
 * "Global 3-3 — si termina así, penales". */
export function consecuenciaCortaDesempate(metodo: MetodoDesempateEliminatoriaOTorneo): string | null {
  switch (metodo) {
    case "Manual":
      return "lo decidís vos";
    case "Penales_Directo":
      return "penales";
    case "Tiempo_Extra_Penales":
      return "tiempo extra";
    case "Penales_Salvo_Final":
      return "penales (tiempo extra en la Final)";
    default:
      return null;
  }
}
