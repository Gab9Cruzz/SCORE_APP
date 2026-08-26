import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";

/**
 * CRUD genérico sobre TanStack Query, para los recursos del módulo Torneo
 * Admin (roles-3-modulos-plan.md, Fase 2, D1). Torneo/Equipo/Jugador
 * comparten esta forma exacta en el backend (id + estado +
 * fecha_registro + fecha_modificacion, GET con skip/limit/estado, DELETE
 * = soft-delete) — es el mismo patrón que BaseRepository generaliza del
 * lado del backend.
 *
 * InscripcionTorneo y JugadorEquipo se desvían de esta forma (sin DELETE
 * plano, sin skip/limit/estado en el GET) — usan `customAction` para sus
 * casos especiales en vez de `update`/`softDelete`, ver PlantillasAdmin.tsx
 * e InscripcionesAdmin.tsx.
 *
 * Los paths se pasan como string plano, no como el literal tipado que
 * openapi-fetch preferiría (`keyof paths`) — a propósito: una función
 * genérica que sirve para cualquier recurso no puede a la vez fijar un
 * path literal. Lo que SÍ queda tipado, vía los genéricos <TOut, TCreate,
 * TUpdate> que cada página pasa explícitamente, es la FORMA de los datos
 * — que es lo que realmente atrapa bugs (nombre de campo mal escrito,
 * tipo equivocado), no la URL en sí.
 */

interface UseResourceCrudOptions {
  /** Cache key de TanStack Query para este recurso (ej: "torneos"). */
  resourceKey: string;
  /** Path base del recurso (ej: "/api/v1/torneos"). */
  basePath: string;
  /** Query params extra para el GET de lista (ej: { torneo_id }). */
  listParams?: Record<string, unknown>;
  /** Si es false, no dispara el GET de lista (para pickers condicionales). */
  enabled?: boolean;
}

export function useResourceCrud<
  TOut extends { id: number },
  TCreate = Partial<TOut>,
  TUpdate = Partial<TOut>,
>(options: UseResourceCrudOptions) {
  const { resourceKey, basePath, listParams, enabled = true } = options;
  const queryClient = useQueryClient();
  const queryKey = [resourceKey, listParams ?? null] as const;

  const listQuery = useQuery({
    queryKey,
    enabled,
    queryFn: async () => {
      const { data, error } = await api.GET(basePath as never, {
        params: { query: { limit: 200, ...listParams } },
      } as never);
      if (error) throw error;
      return data as TOut[];
    },
  });

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: [resourceKey] });
  }

  const create = useMutation({
    mutationFn: async (body: TCreate) => {
      const { data, error } = await api.POST(basePath as never, { body } as never);
      if (error) throw error;
      return data as TOut;
    },
    onSuccess: invalidate,
  });

  const update = useMutation({
    mutationFn: async ({ id, body }: { id: number; body: TUpdate }) => {
      const { data, error } = await api.PATCH(`${basePath}/${id}` as never, { body } as never);
      if (error) throw error;
      return data as TOut;
    },
    onSuccess: invalidate,
  });

  const softDelete = useMutation({
    mutationFn: async (id: number) => {
      const { data, error } = await api.DELETE(`${basePath}/${id}` as never, {} as never);
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
      const fn = method === "POST" ? api.POST : api.PATCH;
      const { data, error } = await fn(path as never, {
        body,
        params: query ? { query } : undefined,
      } as never);
      if (error) throw error;
      return data;
    },
    onSuccess: invalidate,
  });

  return { listQuery, create, update, softDelete, customAction };
}
