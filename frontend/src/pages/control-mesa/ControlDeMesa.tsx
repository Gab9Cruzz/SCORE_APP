import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api/client";
import { useAuth } from "../../auth/useAuth";
import { useNombrePorIdConFaltantes } from "../../hooks/useFetchFaltantes";

/** Dashboard de Control de Mesa: la lista de partidos operables.
 *
 * Cada fila tiene UN solo botón de acción, "Gestionar Partido", que navega a la
 * vista dedicada. Antes tenía cuatro o cinco controles (editar fecha, empezar,
 * resultado directo, walkover, ir al vivo) que envolvían mal en 375px, y
 * "Empezar Partido" montaba `useTitularesCompletos` POR FILA — 6 queries cada
 * una, ~60 requests para pintar 20 partidos en el 3G de una cancha.
 *
 * Colapsar la fila elimina esas queries del dashboard: el cálculo se hace una
 * sola vez, adentro del partido que el operador abrió.
 */
export function ControlDeMesaPage() {
  const { session } = useAuth();
  const navigate = useNavigate();
  const [torneoIdSeleccionado, setTorneoIdSeleccionado] = useState<number | null>(null);

  const torneosQuery = useQuery({
    queryKey: ["torneos-mesa", session?.id],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/torneos", {
        params: { query: { solo_mios: true, limit: 200 } },
      } as never);
      if (error) throw error;
      return data as { id: number; nombre: string }[];
    },
    enabled: session != null,
  });
  const torneos = torneosQuery.data ?? [];

  const partidosQuery = useQuery({
    queryKey: ["partidos-mesa", torneoIdSeleccionado],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/partidos", {
        params: {
          query: {
            limit: 100,
            solo_mios: true,
            ...(torneoIdSeleccionado != null ? { torneo_id: torneoIdSeleccionado } : {}),
          },
        },
      } as never);
      if (error) throw error;
      return data as {
        id: number;
        torneo_id: number;
        estado: string;
        fecha_partido: string;
        equipos_id_local: number | null;
        equipos_id_visitante: number | null;
      }[];
    },
  });

  // Lista de equipos como mapa BASE, con resolución dirigida por ID encima:
  // un equipo fuera de la ventana del listado se pide individual antes de caer
  // al fallback "#ID".
  const equiposQuery = useQuery({
    queryKey: ["equipos-mesa"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/equipos", { params: { query: { limit: 200 } } } as never);
      if (error) throw error;
      return data as { id: number; nombre: string }[];
    },
    staleTime: 5 * 60 * 1000,
  });
  const nombreEquipoBase = useMemo(
    () => new Map((equiposQuery.data ?? []).map((e) => [e.id, e.nombre])),
    [equiposQuery.data],
  );

  const nombreTorneo = useNombrePorIdConFaltantes(
    "/api/v1/torneos",
    new Map(torneos.map((t) => [t.id, t.nombre])),
    (partidosQuery.data ?? []).map((p) => p.torneo_id),
  );
  const nombreEquipo = useNombrePorIdConFaltantes(
    "/api/v1/equipos",
    nombreEquipoBase,
    (partidosQuery.data ?? []).flatMap((p) => [p.equipos_id_local, p.equipos_id_visitante]),
  );

  const seleccionables = (partidosQuery.data ?? []).filter(
    (p) => p.estado === "Programado" || p.estado === "En curso",
  );

  return (
    <div className="page">
      <h1>Control de Mesa</h1>
      {/* Solo cuando hay algo que elegir: un TorneoAdmin con 1 torneo asignado
          no necesita un selector para verlo. */}
      {torneos.length > 1 && (
        <label className="selector-torneo-control-mesa">
          Torneo
          <select
            value={torneoIdSeleccionado ?? ""}
            onChange={(e) => setTorneoIdSeleccionado(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">Todos mis torneos</option>
            {torneos.map((t) => (
              <option key={t.id} value={t.id}>
                {t.nombre}
              </option>
            ))}
          </select>
        </label>
      )}
      {partidosQuery.isLoading && <p>Cargando partidos...</p>}
      {partidosQuery.isError && <p className="error-text">No se pudieron cargar los partidos.</p>}
      {!partidosQuery.isLoading && seleccionables.length === 0 && (
        <p>No hay partidos programados ni en curso ahora mismo.</p>
      )}
      <ul className="partidos-list">
        {seleccionables.map((p) => (
          <li key={p.id} className="partido-mesa-fila">
            <span className="badge">{p.estado}</span>
            {torneos.length > 1 && (
              <span className="muted">{nombreTorneo.get(p.torneo_id) ?? `Torneo #${p.torneo_id}`}</span>
            )}
            <span className="partido-mesa-fila__equipos">
              {p.equipos_id_local != null ? nombreEquipo.get(p.equipos_id_local) ?? `#${p.equipos_id_local}` : "?"}
              {" vs "}
              {p.equipos_id_visitante != null
                ? nombreEquipo.get(p.equipos_id_visitante) ?? `#${p.equipos_id_visitante}`
                : "?"}
            </span>
            <span className="muted">
              {new Date(p.fecha_partido).toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short" })}
            </span>
            {/* Punto de entrada único. Sirve para 'Programado' y 'En curso' por
                igual: es lo que rompe el deadlock que había antes, cuando a la
                convocatoria solo se llegaba con el partido ya empezado. */}
            <button type="button" onClick={() => navigate(`/control-de-mesa/partido/${p.id}`)}>
              Gestionar Partido
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
