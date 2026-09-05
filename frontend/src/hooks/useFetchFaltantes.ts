import { useQueries } from "@tanstack/react-query";
import { useMemo } from "react";
import { api } from "../api/client";

/**
 * Bug 2 (fixes-datos-traspasos-control-mesa-plan.md, D2): resolución
 * dirigida por ID. Un listado capado a `LIMITE_LISTA` filas
 * (`useResourceCrud`) arma su `Map<id, nombre>` solo con lo que trajo esa
 * página — un ID fuera de esa ventana (equipo/jugador/perfil recién creado
 * en un entorno con miles de filas previas) nunca entra al mapa, y la
 * pantalla cae al fallback `"Equipo #ID"`/`"Perfil #ID"` aunque el dato
 * real esté perfecto en la base (causa raíz confirmada en P3 del plan).
 *
 * Este hook pide, UNO POR UNO, solo los IDs que el llamador diga que le
 * faltan — `GET {basePath}/{id}` (ya existe para equipos/jugadores/
 * perfiles, sin backend nuevo) — y los cachea aparte
 * (`queryKey: [basePath, "individual", id]`, no compite con el `queryKey`
 * de la lista capada). No es paginación real (eso sigue siendo
 * `TODOS.md` §3B-9): resuelve el ID puntual que la pantalla necesita
 * mostrar, no "cuántos hay en total".
 *
 * Devuelve un `Map<id, fila completa>` — el llamador extrae el campo que
 * necesite (`nombre`, `jugador_id`, etc.), porque distintos recursos
 * exponen distintos campos.
 */
export function useFetchFaltantes<T extends { id: number }>(basePath: string, idsFaltantes: number[]): Map<number, T> {
  const resultados = useQueries({
    queries: idsFaltantes.map((id) => ({
      queryKey: [basePath, "individual", id] as const,
      queryFn: async () => {
        const { data, error } = await api.GET(`${basePath}/{id}` as never, {
          params: { path: { id } },
        } as never);
        if (error) throw error;
        return data as T;
      },
      staleTime: 5 * 60 * 1000,
    })),
  });

  // eslint-disable-next-line react-hooks/exhaustive-deps -- `resultados` es
  // un array nuevo cada render (useQueries), pero su CONTENIDO solo cambia
  // cuando algún query realmente resuelve — comparar por longitud+datos
  // sería más ruidoso que útil acá, total el Map es barato de rearmar.
  return useMemo(() => {
    const m = new Map<number, T>();
    for (const r of resultados) {
      if (r.data) m.set((r.data as T).id, r.data as T);
    }
    return m;
  }, [resultados]);
}

/** Calcula qué IDs de `referenciados` NO están ya en `mapaBase` — la lista
 * a pasarle a `useFetchFaltantes`. Ignora `null`/`undefined` (referencias
 * ausentes, ej. `equipo_id` de un partido de bracket sin definir) y
 * deduplica. */
export function idsFaltantesDe(mapaBase: Map<number, unknown>, referenciados: (number | null | undefined)[]): number[] {
  const vistos = new Set<number>();
  const out: number[] = [];
  for (const id of referenciados) {
    if (id == null) continue;
    if (mapaBase.has(id)) continue;
    if (vistos.has(id)) continue;
    vistos.add(id);
    out.push(id);
  }
  return out;
}

/** Envoltorio de conveniencia para el caso más común: un `Map<id, nombre>`
 * armado desde una lista capada (`nombreEquipo`, `nombreJugador`...) al que
 * le faltan algunos IDs. Devuelve el mismo Map si no falta nada — evita
 * pasar una identidad nueva en cada render cuando no hay nada que resolver
 * (el caso normal, sin equipos/jugadores fuera de la ventana de 200). */
export function useNombrePorIdConFaltantes(
  basePath: string,
  mapaBase: Map<number, string>,
  idsReferenciados: (number | null | undefined)[],
): Map<number, string> {
  const faltantesIds = idsFaltantesDe(mapaBase, idsReferenciados);
  const faltantes = useFetchFaltantes<{ id: number; nombre: string }>(basePath, faltantesIds);
  return useMemo(() => {
    if (faltantes.size === 0) return mapaBase;
    const m = new Map(mapaBase);
    for (const [id, row] of faltantes) m.set(id, row.nombre);
    return m;
  }, [mapaBase, faltantes]);
}
