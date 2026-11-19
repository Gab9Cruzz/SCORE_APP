import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { pedirRutaDinamica } from "../api/rutaDinamica";

/**
 * CRUD genérico sobre TanStack Query, para los recursos del módulo Torneo
 * Admin (roles-3-modulos-plan.md, Fase 2, D1). Torneo/Equipo/Jugador
 * comparten esta forma exacta en el backend (id + estado +
 * fecha_registro + fecha_modificacion, GET con skip/limit/estado, DELETE
 * = soft-delete) — es el mismo patrón que BaseRepository generaliza del
 * lado del backend.
 *
 * InscripcionTorneo y JugadorEquipo se desvían de esta forma (sin DELETE
 * plano, sin filtro de estado en el GET) — usan `customAction` para sus
 * casos especiales en vez de `update`/`softDelete`, ver
 * torneo-dashboard/PlantillasDelTorneo.tsx y torneo-dashboard/EquiposDelTorneo.tsx
 * (cancelar una inscripción).
 *
 * Los paths se pasan como string plano, no como el literal tipado que
 * openapi-fetch preferiría (`keyof paths`) — a propósito: una función
 * genérica que sirve para cualquier recurso no puede a la vez fijar un
 * path literal (ver api/rutaDinamica.ts). Lo que SÍ queda tipado, vía los genéricos <TOut, TCreate,
 * TUpdate> que cada página pasa explícitamente, es la FORMA de los datos
 * — que es lo que realmente atrapa bugs (nombre de campo mal escrito,
 * tipo equivocado), no la URL en sí.
 */

/** Techo de filas que pide TODO listado de este hook.
 *
 * Es el mismo valor que el `le=200` de los endpoints (`Query(default=100,
 * le=200)`), y está exportado a propósito: antes vivía hardcodeado acá
 * adentro y una página que quisiera avisar "hay más de los que ves" tenía
 * que repetir el número, con el riesgo obvio de que los dos se
 * desincronicen. Ahora el hook devuelve `truncado` ya calculado y nadie
 * necesita saber el número — se exporta solo para quien quiera mostrarlo
 * en el mensaje.
 *
 * Es el tope de los listados SIN paginar (selectores, mapas de nombres).
 * Las grillas de administración paginan con `tamanoPagina` (TASK-039). */
export const LIMITE_LISTA = 200;

/** Tope de eventos de UN partido (`le=500` en GET /eventos-partido,
 * TASK-011): un partido se trae entero, no se pagina. */
export const LIMITE_EVENTOS_PARTIDO = 500;

interface UseResourceCrudOptions {
  /** Cache key de TanStack Query para este recurso (ej: "torneos"). */
  resourceKey: string;
  /** Path base del recurso (ej: "/api/v1/torneos"). */
  basePath: string;
  /** Query params extra para el GET de lista (ej: { torneo_id }). */
  listParams?: Record<string, unknown>;
  /** Si es false, no dispara el GET de lista (para pickers condicionales). */
  enabled?: boolean;
  /** TASK-039: con esto el GET pide una página (`skip`/`limit`) en lugar de
   * las primeras `LIMITE_LISTA` filas. `pagina` empieza en 0. */
  tamanoPagina?: number;
  pagina?: number;
}

/** Filas por página de las grillas de administración (TASK-039). */
export const TAMANO_PAGINA = 50;

export function useResourceCrud<
  TOut extends { id: number },
  TCreate = Partial<TOut>,
  TUpdate = Partial<TOut>,
>(options: UseResourceCrudOptions) {
  const { resourceKey, basePath, listParams, enabled = true, tamanoPagina, pagina = 0 } = options;
  const queryClient = useQueryClient();
  const ventana = tamanoPagina ? { skip: pagina * tamanoPagina, limit: tamanoPagina } : { limit: LIMITE_LISTA };
  // La ventana va en la clave solo si pagina: los listados de siempre
  // conservan su clave (y lo que ya la invalida o la siembra en tests).
  const queryKey = tamanoPagina
    ? ([resourceKey, listParams ?? null, ventana] as const)
    : ([resourceKey, listParams ?? null] as const);

  // TASK-011: la respuesta guarda también el total de X-Total-Count. Dos
  // observadores sobre la misma entrada de caché (una sola petición): uno
  // expone las filas, como siempre, y el otro el total.
  const listaConTotal = {
    queryKey,
    enabled,
    queryFn: async (): Promise<{ filas: TOut[]; total: number | null }> => {
      const { data, error, response } = await pedirRutaDinamica("GET", basePath, {
        query: { ...ventana, ...listParams },
      });
      if (error) throw error;
      const cabecera = response?.headers.get("X-Total-Count");
      const total = cabecera != null && cabecera !== "" ? Number(cabecera) : null;
      return { filas: data as TOut[], total: Number.isFinite(total) ? total : null };
    },
    // Al cambiar de página se sigue viendo la anterior hasta que llega la
    // nueva, en vez de vaciar la tabla y mostrar "Cargando…" cada vez.
    placeholderData: tamanoPagina ? keepPreviousData : undefined,
  };
  const listQuery = useQuery({ ...listaConTotal, select: (d) => d.filas });
  const totalQuery = useQuery({ ...listaConTotal, select: (d) => d.total });
  const total = totalQuery.data ?? null;

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: [resourceKey] });
  }

  const create = useMutation({
    mutationFn: async (body: TCreate) => {
      const { data, error } = await pedirRutaDinamica("POST", basePath, { body });
      if (error) throw error;
      return data as TOut;
    },
    onSuccess: invalidate,
  });

  const update = useMutation({
    mutationFn: async ({ id, body }: { id: number; body: TUpdate }) => {
      const { data, error } = await pedirRutaDinamica("PATCH", `${basePath}/${id}`, { body });
      if (error) throw error;
      return data as TOut;
    },
    onSuccess: invalidate,
  });

  const softDelete = useMutation({
    mutationFn: async (id: number) => {
      const { data, error } = await pedirRutaDinamica("DELETE", `${basePath}/${id}`);
      if (error) throw error;
      return data as TOut;
    },
    onSuccess: invalidate,
  });

  /** Escape hatch para acciones que no son un PATCH/DELETE plano — ej.
   * JugadorEquipo: `POST /plantillas/{id}/baja?fecha_fin=X`. */
  const customAction = useMutation({
    mutationFn: async (args: {
      path: string;
      method?: "POST" | "PATCH";
      body?: unknown;
      query?: Record<string, unknown>;
    }) => {
      const { path, method = "POST", body, query } = args;
      const { data, error } = await pedirRutaDinamica(method, path, { body, query });
      if (error) throw error;
      return data;
    },
    onSuccess: invalidate,
  });

  /** La lista volvió justo llena, así que es muy probable que el servidor
   * haya cortado y existan filas que el usuario no está viendo. Un falso
   * positivo (exactamente 200 filas en total) es aceptable: el costo es un
   * aviso de más; el del falso negativo era que la fila 201 no existiera
   * para nadie, sin ningún indicio en pantalla. */
  const filasRecibidas = listQuery.data?.length ?? 0;
  // TASK-011: con X-Total-Count el aviso es exacto. Sin la cabecera (los
  // endpoints que todavía no la mandan) se mantiene la inferencia de arriba.
  const truncado = tamanoPagina
    ? false
    : total !== null
      ? total > filasRecibidas
      : filasRecibidas === LIMITE_LISTA;

  return { listQuery, total, truncado, create, update, softDelete, customAction };
}
