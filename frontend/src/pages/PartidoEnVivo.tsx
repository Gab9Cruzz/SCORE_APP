import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { api } from "../api/client";

// Intervalo de refresco para lo "en vivo" — arranca en 5s, ver Recommended
// Approach del design doc. Fácil de ajustar acá si en la práctica se siente
// lento o pesado para el servidor.
const LIVE_POLL_MS = 5000;

const EVENTO_LABEL: Record<string, string> = {
  Gol: "⚽ Gol",
  Autogol: "⚽ Autogol",
  "Tarjeta Amarilla": "🟨 Amarilla",
  "Tarjeta Roja": "🟥 Roja",
  Cambio: "🔄 Cambio",
};

export function PartidoEnVivoPage() {
  const { partidoId } = useParams<{ partidoId: string }>();
  const id = Number(partidoId);

  const partidoQuery = useQuery({
    queryKey: ["partido", id],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/partidos/{partido_id}", { params: { path: { partido_id: id } } });
      if (error) throw error;
      return data;
    },
    enabled: Number.isFinite(id),
  });

  const torneoId = partidoQuery.data?.torneo_id;

  const resultadosQuery = useQuery({
    queryKey: ["resultados", torneoId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/estadisticas/torneos/{torneo_id}/resultados", {
        params: { path: { torneo_id: torneoId as number } },
      });
      if (error) throw error;
      return data;
    },
    enabled: torneoId !== undefined,
    refetchInterval: LIVE_POLL_MS,
  });

  const eventosQuery = useQuery({
    queryKey: ["eventos-partido", id],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/eventos-partido", { params: { query: { partidos_id: id } } });
      if (error) throw error;
      return data;
    },
    enabled: Number.isFinite(id),
    refetchInterval: LIVE_POLL_MS,
  });

  // Catálogos — no cambian en vivo, se piden una vez y quedan en cache.
  const jugadoresQuery = useQuery({
    queryKey: ["jugadores-catalogo"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/jugadores", { params: { query: { limit: 200 } } });
      if (error) throw error;
      return data;
    },
    staleTime: 5 * 60 * 1000,
  });

  const eventosCatalogoQuery = useQuery({
    queryKey: ["eventos-catalogo"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/eventos", {});
      if (error) throw error;
      return data;
    },
    staleTime: 5 * 60 * 1000,
  });

  if (!Number.isFinite(id)) {
    return (
      <div className="page">
        <p className="error-text">Partido inválido.</p>
      </div>
    );
  }

  if (partidoQuery.isLoading) {
    return (
      <div className="page">
        <p>Cargando partido...</p>
      </div>
    );
  }

  if (partidoQuery.isError || !partidoQuery.data) {
    return (
      <div className="page">
        <p className="error-text">No se pudo cargar el partido.</p>
      </div>
    );
  }

  const resultado = resultadosQuery.data?.find((r) => r.partido_id === id);
  const jugadorNombre = new Map((jugadoresQuery.data ?? []).map((j) => [j.id, j.nombre]));
  const eventoNombre = new Map((eventosCatalogoQuery.data ?? []).map((e) => [e.id, e.nombre]));

  const eventos = [...(eventosQuery.data ?? [])]
    .filter((e) => e.estado === "Registrado")
    .sort((a, b) => b.minuto - a.minuto);

  return (
    <div className="page en-vivo">
      <div className="marcador">
        <div className="marcador__equipo">
          <span>{resultado?.equipo_local ?? "Local"}</span>
        </div>
        <div className="marcador__score">
          {resultado ? `${resultado.goles_local} - ${resultado.goles_visitante}` : "- : -"}
        </div>
        <div className="marcador__equipo">
          <span>{resultado?.equipo_visitante ?? "Visitante"}</span>
        </div>
      </div>
      <div className="marcador__estado">
        <span className={`badge badge--${partidoQuery.data.estado.replace(" ", "-").toLowerCase()}`}>
          {partidoQuery.data.estado}
        </span>
        {resultadosQuery.data && <span className="muted">actualizado en vivo</span>}
      </div>

      <section className="card">
        <h2>Eventos</h2>
        {eventos.length === 0 && <p>Todavía no hay eventos cargados.</p>}
        {eventos.length > 0 && (
          <ul className="eventos-timeline">
            {eventos.map((e) => (
              <li key={e.id}>
                <span className="eventos-timeline__minuto">{e.minuto}'</span>
                <span>{EVENTO_LABEL[eventoNombre.get(e.eventos_id) ?? ""] ?? eventoNombre.get(e.eventos_id)}</span>
                <span>{jugadorNombre.get(e.jugador_id) ?? `Jugador #${e.jugador_id}`}</span>
                {e.jugador_id_entra !== null && e.jugador_id_entra !== undefined && (
                  <span className="muted">→ entra {jugadorNombre.get(e.jugador_id_entra) ?? `#${e.jugador_id_entra}`}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
