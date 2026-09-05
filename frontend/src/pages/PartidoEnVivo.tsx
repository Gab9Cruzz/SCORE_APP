import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
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

interface PlantillaJugador {
  jugador_id: number;
  jugador: string;
  equipo_id: number;
  equipo: string;
  dorsal: number | null;
  jugador_perfil_id: number;
}
interface ConvocadoRow {
  jugador_perfil_id: number;
  titular: boolean;
}

/** "Detalle del Partido" (control-mesa-centralizacion-fixture-plan.md,
 * ítem 5) — generaliza lo que antes era exclusivamente
 * `/partido/:partidoId/en-vivo`: mismo componente, dos rutas (esa se
 * mantiene — Dashboard.tsx la linkea como "Ver en vivo →" — y la nueva
 * `/partidos/:partidoId`, que es a donde navega el botón "Detalle del
 * Partido" de `PartidosDelTorneo.tsx` ahora que esa pantalla es de solo
 * lectura). Sirve para CUALQUIER estado del partido, no solo "En curso" —
 * el marcador y la timeline de eventos ya funcionaban así (T46/estadísticas
 * públicas); lo único nuevo acá es la sección de Alineaciones. Público,
 * sin auth — mismo criterio que el resto de /partidos y /estadisticas. */
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

  // Alineaciones (ítem 5 del plan — lo único genuinamente nuevo de esta
  // página): reusa GET /partidos/{id}/convocados + GET
  // /estadisticas/equipos/{id}/plantilla, ambos ya públicos, sin backend
  // nuevo. Mismo fallback que MesaPanel (Convocatoria.tsx): sin
  // convocatoria guardada, se muestra toda la plantilla vigente sin
  // distinguir titular/suplente (es estrictamente opt-in).
  const equipoLocalId = partidoQuery.data?.equipos_id_local;
  const equipoVisitanteId = partidoQuery.data?.equipos_id_visitante;

  const convocadosQuery = useQuery({
    queryKey: ["convocados", id],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/partidos/{partido_id}/convocados", {
        params: { path: { partido_id: id } },
      });
      if (error) throw error;
      return data as ConvocadoRow[];
    },
    enabled: Number.isFinite(id),
  });

  const plantillaLocalQuery = useQuery({
    queryKey: ["plantilla", equipoLocalId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/estadisticas/equipos/{equipo_id}/plantilla", {
        params: { path: { equipo_id: equipoLocalId as number } },
      });
      if (error) throw error;
      return data as PlantillaJugador[];
    },
    enabled: equipoLocalId != null,
  });
  const plantillaVisitanteQuery = useQuery({
    queryKey: ["plantilla", equipoVisitanteId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/estadisticas/equipos/{equipo_id}/plantilla", {
        params: { path: { equipo_id: equipoVisitanteId as number } },
      });
      if (error) throw error;
      return data as PlantillaJugador[];
    },
    enabled: equipoVisitanteId != null,
  });

  const titularPorPerfil = useMemo(
    () => new Map((convocadosQuery.data ?? []).map((c) => [c.jugador_perfil_id, c.titular])),
    [convocadosQuery.data],
  );
  const hayConvocatoria = (convocadosQuery.data ?? []).length > 0;

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

      {equipoLocalId != null && equipoVisitanteId != null && (
        <section className="card">
          <h2>Alineaciones</h2>
          {!hayConvocatoria && <p className="muted">Sin convocatoria guardada — se muestra toda la plantilla vigente.</p>}
          <div className="convocatoria-equipos">
            <AlineacionEquipo
              nombre={resultado?.equipo_local ?? "Local"}
              plantilla={plantillaLocalQuery.data ?? []}
              titularPorPerfil={titularPorPerfil}
              hayConvocatoria={hayConvocatoria}
            />
            <AlineacionEquipo
              nombre={resultado?.equipo_visitante ?? "Visitante"}
              plantilla={plantillaVisitanteQuery.data ?? []}
              titularPorPerfil={titularPorPerfil}
              hayConvocatoria={hayConvocatoria}
            />
          </div>
        </section>
      )}
    </div>
  );
}

/** Titulares/suplentes de un equipo — solo lectura (a diferencia de
 * `Convocatoria.tsx`, que además la edita). Sin convocatoria guardada
 * (`hayConvocatoria=false`) se muestra toda la plantilla en una sola
 * lista, sin separar (mismo fallback que `MesaPanel`/`CargaEvento`: la
 * plantilla entera sigue siendo candidata). */
function AlineacionEquipo(props: {
  nombre: string;
  plantilla: PlantillaJugador[];
  titularPorPerfil: Map<number, boolean>;
  hayConvocatoria: boolean;
}) {
  const { nombre, plantilla, titularPorPerfil, hayConvocatoria } = props;

  if (plantilla.length === 0) {
    return (
      <div className="convocatoria-equipo">
        <h3>{nombre}</h3>
        <p className="muted">Sin plantilla cargada.</p>
      </div>
    );
  }

  if (!hayConvocatoria) {
    return (
      <div className="convocatoria-equipo">
        <h3>{nombre}</h3>
        <ul className="convocatoria-lista">
          {plantilla.map((j) => (
            <li key={j.jugador_perfil_id}>
              {j.dorsal ? `#${j.dorsal} ` : ""}
              {j.jugador}
            </li>
          ))}
        </ul>
      </div>
    );
  }

  const titulares = plantilla.filter((j) => titularPorPerfil.get(j.jugador_perfil_id) === true);
  const suplentes = plantilla.filter((j) => titularPorPerfil.has(j.jugador_perfil_id) && titularPorPerfil.get(j.jugador_perfil_id) === false);

  return (
    <div className="convocatoria-equipo">
      <h3>{nombre}</h3>
      <p className="muted">Titulares</p>
      <ul className="convocatoria-lista">
        {titulares.map((j) => (
          <li key={j.jugador_perfil_id}>
            {j.dorsal ? `#${j.dorsal} ` : ""}
            {j.jugador}
          </li>
        ))}
        {titulares.length === 0 && <li className="muted">Sin titulares convocados.</li>}
      </ul>
      {suplentes.length > 0 && (
        <>
          <p className="muted">Suplentes</p>
          <ul className="convocatoria-lista">
            {suplentes.map((j) => (
              <li key={j.jugador_perfil_id}>
                {j.dorsal ? `#${j.dorsal} ` : ""}
                {j.jugador}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
