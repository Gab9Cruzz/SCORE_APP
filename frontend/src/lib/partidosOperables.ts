/** Estados de un partido que la mesa y el árbitro pueden operar. Se piden al
 * servidor (`GET /partidos?estado=…&estado=…`, TASK-012) en vez de filtrar
 * en el navegador: con más de 100 partidos jugados, el filtro local sobre
 * los primeros 100 por ID dejaba la lista vacía. */
export const ESTADOS_OPERABLES = ["Programado", "En curso"] as const;

/** El total de un listado paginado (cabecera `X-Total-Count`, TASK-011), o
 * `null` si la respuesta no la trae. */
export function totalDeRespuesta(response: Response | undefined): number | null {
  const cabecera = response?.headers.get("X-Total-Count");
  if (cabecera == null || cabecera === "") return null;
  const total = Number(cabecera);
  return Number.isFinite(total) ? total : null;
}
