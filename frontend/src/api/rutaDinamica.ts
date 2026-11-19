import { api } from "./client";

/** Llamada a una ruta que se arma en tiempo de ejecución (TASK-032).
 *
 * openapi-fetch tipa cada llamada por el path LITERAL (`keyof paths`). Los
 * hooks genéricos (`useResourceCrud`, `useFetchFaltantes`) reciben el path
 * como string, así que no pueden fijarlo: el tipado de esos hooks está en
 * sus genéricos (TOut, TCreate, TUpdate), que cada página llena con los
 * esquemas de `schema.d.ts`.
 *
 * Este es el ÚNICO lugar donde se le quita el tipo al cliente. Antes había
 * `as never` repartidos por ~40 llamadas de páginas; el test
 * `sinAsNever.test.ts` impide que vuelvan. Las páginas que conocen su ruta
 * usan `api.GET("/api/v1/...")` directo, con el contrato completo.
 */
type Metodo = "GET" | "POST" | "PATCH" | "DELETE";

export interface OpcionesRutaDinamica {
  body?: unknown;
  query?: Record<string, unknown>;
  path?: Record<string, unknown>;
}

export interface RespuestaRutaDinamica {
  data?: unknown;
  error?: unknown;
  response: Response;
}

type LlamadaSinTipo = (
  ruta: string,
  init: { body?: unknown; params?: { query?: Record<string, unknown>; path?: Record<string, unknown> } },
) => Promise<RespuestaRutaDinamica>;

export function pedirRutaDinamica(
  metodo: Metodo,
  ruta: string,
  { body, query, path }: OpcionesRutaDinamica = {},
): Promise<RespuestaRutaDinamica> {
  const llamar = api[metodo] as unknown as LlamadaSinTipo;
  const params = query || path ? { ...(query ? { query } : {}), ...(path ? { path } : {}) } : undefined;
  return llamar(ruta, { ...(body !== undefined ? { body } : {}), ...(params ? { params } : {}) });
}
