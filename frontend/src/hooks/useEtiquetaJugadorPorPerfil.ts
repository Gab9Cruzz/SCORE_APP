import { useMemo } from "react";
import { idsFaltantesDe, useFetchFaltantes } from "./useFetchFaltantes";

interface PerfilConJugador {
  id: number;
  jugador_id: number;
}
interface JugadorConNombre {
  id: number;
  nombre: string;
}

/** Bug 2 (fixes-datos-traspasos-control-mesa-plan.md, D2) — versión de DOS
 * saltos de `useFetchFaltantes` para el patrón `"Perfil #ID"`:
 * `jugador_perfil_id` → `JUGADOR_PERFIL_DISCIPLINA.jugador_id` →
 * `JUGADOR.nombre`. Un perfil fuera de la ventana de `LIMITE_LISTA` se
 * resuelve pidiendo `GET /perfiles/{id}` primero (da el `jugador_id`) y, si
 * ESE jugador tampoco estaba en el mapa de jugadores ya cargado,
 * `GET /jugadores/{id}` después — sin backend nuevo, mismo criterio que
 * `useNombrePorIdConFaltantes` pero encadenado.
 *
 * `perfilIdsReferenciados`: TODOS los `jugador_perfil_id` que la pantalla
 * necesita mostrar (no solo los que ya están en `perfilPorId`). */
export function useEtiquetaJugadorPorPerfil(
  perfilIdsReferenciados: (number | null | undefined)[],
  perfilPorId: Map<number, PerfilConJugador>,
  nombreJugador: Map<number, string>,
): (perfilId: number) => string {
  const perfilesFaltantesIds = idsFaltantesDe(perfilPorId, perfilIdsReferenciados);
  const perfilesFaltantes = useFetchFaltantes<PerfilConJugador>("/api/v1/perfiles", perfilesFaltantesIds);

  const perfilPorIdCompleto = useMemo(() => {
    if (perfilesFaltantes.size === 0) return perfilPorId;
    const m = new Map(perfilPorId);
    for (const [id, p] of perfilesFaltantes) m.set(id, p);
    return m;
  }, [perfilPorId, perfilesFaltantes]);

  const jugadorIdsReferenciados = useMemo(
    () => perfilIdsReferenciados.map((pid) => (pid != null ? perfilPorIdCompleto.get(pid)?.jugador_id : null)),
    [perfilIdsReferenciados, perfilPorIdCompleto],
  );
  const jugadorFaltantesIds = idsFaltantesDe(nombreJugador, jugadorIdsReferenciados);
  const jugadoresFaltantes = useFetchFaltantes<JugadorConNombre>("/api/v1/jugadores", jugadorFaltantesIds);

  const nombreJugadorCompleto = useMemo(() => {
    if (jugadoresFaltantes.size === 0) return nombreJugador;
    const m = new Map(nombreJugador);
    for (const [id, j] of jugadoresFaltantes) m.set(id, j.nombre);
    return m;
  }, [nombreJugador, jugadoresFaltantes]);

  return useMemo(() => {
    return (perfilId: number) => {
      const p = perfilPorIdCompleto.get(perfilId);
      if (!p) return `Perfil #${perfilId}`;
      return nombreJugadorCompleto.get(p.jugador_id) ?? `Jugador #${p.jugador_id}`;
    };
  }, [perfilPorIdCompleto, nombreJugadorCompleto]);
}
