import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { api, apiErrorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";

const LIVE_POLL_MS = 5000;

type TipoEvento = "Gol" | "Autogol" | "Tarjeta Amarilla" | "Tarjeta Roja" | "Cambio";
const TIPOS: TipoEvento[] = ["Gol", "Autogol", "Tarjeta Amarilla", "Tarjeta Roja", "Cambio"];
const TIPO_ICONO: Record<TipoEvento, string> = {
  Gol: "⚽",
  Autogol: "⚽ (en contra)",
  "Tarjeta Amarilla": "🟨",
  "Tarjeta Roja": "🟥",
  Cambio: "🔄",
};

export function ControlDeMesaPage() {
  const [partidoId, setPartidoId] = useState<number | null>(null);

  const partidosQuery = useQuery({
    queryKey: ["partidos-mesa"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/partidos", { params: { query: { limit: 100 } } });
      if (error) throw error;
      return data;
    },
  });

  const seleccionables = (partidosQuery.data ?? []).filter(
    (p) => p.estado === "Programado" || p.estado === "En curso",
  );

  if (partidoId !== null) {
    return <MesaPanel partidoId={partidoId} onVolver={() => setPartidoId(null)} />;
  }

  return (
    <div className="page">
      <h1>Control de Mesa</h1>
      {partidosQuery.isLoading && <p>Cargando partidos...</p>}
      {partidosQuery.isError && <p className="error-text">No se pudieron cargar los partidos.</p>}
      {!partidosQuery.isLoading && seleccionables.length === 0 && (
        <p>No hay partidos programados ni en curso ahora mismo.</p>
      )}
      <ul className="partidos-list partidos-list--tappable">
        {seleccionables.map((p) => (
          <li key={p.id}>
            <button type="button" onClick={() => setPartidoId(p.id)}>
              <span className="badge">{p.estado}</span>
              Partido #{p.id} · {new Date(p.fecha_partido).toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short" })}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function MesaPanel({ partidoId, onVolver }: { partidoId: number; onVolver: () => void }) {
  const queryClient = useQueryClient();
  const { session } = useAuth();

  const partidoQuery = useQuery({
    queryKey: ["partido", partidoId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/partidos/{partido_id}", { params: { path: { partido_id: partidoId } } });
      if (error) throw error;
      return data;
    },
  });

  const equiposQuery = useQuery({
    queryKey: ["equipos-catalogo"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/equipos", { params: { query: { limit: 200 } } });
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

  const eventosPartidoQuery = useQuery({
    queryKey: ["eventos-partido", partidoId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/eventos-partido", { params: { query: { partidos_id: partidoId } } });
      if (error) throw error;
      return data;
    },
    refetchInterval: LIVE_POLL_MS,
  });

  const equipoLocalId = partidoQuery.data?.equipos_id_local;
  const equipoVisitanteId = partidoQuery.data?.equipos_id_visitante;

  const plantillaLocalQuery = useQuery({
    queryKey: ["plantilla", equipoLocalId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/estadisticas/equipos/{equipo_id}/plantilla", {
        params: { path: { equipo_id: equipoLocalId as number } },
      });
      if (error) throw error;
      return data;
    },
    enabled: equipoLocalId !== undefined,
  });

  const plantillaVisitanteQuery = useQuery({
    queryKey: ["plantilla", equipoVisitanteId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/estadisticas/equipos/{equipo_id}/plantilla", {
        params: { path: { equipo_id: equipoVisitanteId as number } },
      });
      if (error) throw error;
      return data;
    },
    enabled: equipoVisitanteId !== undefined,
  });

  const equipoNombre = useMemo(
    () => new Map((equiposQuery.data ?? []).map((e) => [e.id, e.nombre])),
    [equiposQuery.data],
  );
  const eventoIdPorNombre = useMemo(
    () => new Map((eventosCatalogoQuery.data ?? []).map((e) => [e.nombre, e.id])),
    [eventosCatalogoQuery.data],
  );
  const eventoNombrePorId = useMemo(
    () => new Map((eventosCatalogoQuery.data ?? []).map((e) => [e.id, e.nombre])),
    [eventosCatalogoQuery.data],
  );

  const eventosRegistrados = (eventosPartidoQuery.data ?? []).filter((e) => e.estado === "Registrado");

  // Marcador calculado como vw_goles_acreditados: Gol suma al equipo del
  // jugador, Autogol suma al rival. Se recalcula en cada refetch — no hay
  // estado de marcador guardado aparte.
  const marcador = useMemo(() => {
    let local = 0;
    let visitante = 0;
    for (const e of eventosRegistrados) {
      const tipo = eventoNombrePorId.get(e.eventos_id);
      if (tipo !== "Gol" && tipo !== "Autogol") continue;
      const acreditadoLocal = tipo === "Autogol" ? e.equipo_id !== equipoLocalId : e.equipo_id === equipoLocalId;
      if (acreditadoLocal) local += 1;
      else visitante += 1;
    }
    return { local, visitante };
  }, [eventosRegistrados, eventoNombrePorId, equipoLocalId]);

  const mutation = useMutation({
    mutationFn: async (body: {
      partidos_id: number;
      jugador_id: number;
      equipo_id: number;
      eventos_id: number;
      jugador_id_entra?: number | null;
      minuto: number;
    }) => {
      const { data, error } = await api.POST("/api/v1/eventos-partido", { body });
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["eventos-partido", partidoId] });
    },
  });

  if (partidoQuery.isLoading) return <div className="page"><p>Cargando partido...</p></div>;
  if (partidoQuery.isError || !partidoQuery.data) {
    return (
      <div className="page">
        <button type="button" onClick={onVolver}>← Volver</button>
        <p className="error-text">No se pudo cargar el partido.</p>
      </div>
    );
  }

  const partido = partidoQuery.data;
  const nombreLocal = equipoNombre.get(partido.equipos_id_local) ?? `Equipo #${partido.equipos_id_local}`;
  const nombreVisitante = equipoNombre.get(partido.equipos_id_visitante) ?? `Equipo #${partido.equipos_id_visitante}`;

  return (
    <div className="page mesa">
      <button type="button" className="link-button" onClick={onVolver}>← Volver a la lista</button>

      <div className="marcador">
        <div className="marcador__equipo"><span>{nombreLocal}</span></div>
        <div className="marcador__score">{marcador.local} - {marcador.visitante}</div>
        <div className="marcador__equipo"><span>{nombreVisitante}</span></div>
      </div>
      <div className="marcador__estado">
        <span className={`badge badge--${partido.estado.replace(" ", "-").toLowerCase()}`}>{partido.estado}</span>
        <span className="muted">operando como {session?.username} ({session?.rol})</span>
      </div>

      <CargaEvento
        partidoId={partidoId}
        equipoLocalId={partido.equipos_id_local}
        equipoVisitanteId={partido.equipos_id_visitante}
        nombreLocal={nombreLocal}
        nombreVisitante={nombreVisitante}
        plantillaLocal={plantillaLocalQuery.data ?? []}
        plantillaVisitante={plantillaVisitanteQuery.data ?? []}
        eventosRegistrados={eventosRegistrados}
        eventoIdPorNombre={eventoIdPorNombre}
        eventoNombrePorId={eventoNombrePorId}
        onSubmit={(body) => mutation.mutate(body)}
        submitting={mutation.isPending}
        submitError={mutation.isError ? apiErrorMessage(mutation.error) : null}
      />

      <section className="card">
        <h2>Eventos cargados</h2>
        {eventosRegistrados.length === 0 && <p>Todavía no hay eventos.</p>}
        {eventosRegistrados.length > 0 && (
          <ul className="eventos-timeline">
            {[...eventosRegistrados].sort((a, b) => b.minuto - a.minuto).map((e) => (
              <li key={e.id}>
                <span className="eventos-timeline__minuto">{e.minuto}'</span>
                <span>{TIPO_ICONO[eventoNombrePorId.get(e.eventos_id) as TipoEvento] ?? eventoNombrePorId.get(e.eventos_id)}</span>
                <span>{[...plantillaLocalQuery.data ?? [], ...plantillaVisitanteQuery.data ?? []].find((j) => j.jugador_id === e.jugador_id)?.jugador ?? `#${e.jugador_id}`}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

interface PlantillaJugador {
  jugador_id: number;
  jugador: string;
  equipo_id: number;
  equipo: string;
  dorsal: number | null;
}

interface EventoPartidoRow {
  id: number;
  jugador_id: number;
  jugador_id_entra: number | null;
  equipo_id: number;
  eventos_id: number;
  estado: string;
}

function CargaEvento(props: {
  partidoId: number;
  equipoLocalId: number;
  equipoVisitanteId: number;
  nombreLocal: string;
  nombreVisitante: string;
  plantillaLocal: PlantillaJugador[];
  plantillaVisitante: PlantillaJugador[];
  eventosRegistrados: EventoPartidoRow[];
  eventoIdPorNombre: Map<string, number>;
  eventoNombrePorId: Map<number, string>;
  onSubmit: (body: {
    partidos_id: number;
    jugador_id: number;
    equipo_id: number;
    eventos_id: number;
    jugador_id_entra?: number | null;
    minuto: number;
  }) => void;
  submitting: boolean;
  submitError: string | null;
}) {
  const [tipo, setTipo] = useState<TipoEvento | null>(null);
  const [equipoId, setEquipoId] = useState<number | null>(null);
  const [sale, setSale] = useState<number | null>(null);
  const [entra, setEntra] = useState<number | null>(null);
  const [minuto, setMinuto] = useState("");

  function reset() {
    setTipo(null);
    setEquipoId(null);
    setSale(null);
    setEntra(null);
    setMinuto("");
  }

  const plantillaEquipo = equipoId === props.equipoLocalId ? props.plantillaLocal : props.plantillaVisitante;

  // Derivación de "quién sigue disponible" a partir del historial del
  // partido — el modelo de datos no distingue titular/suplente, así que
  // esto es plantilla vigente menos quien ya salió o fue expulsado. Ver
  // pre-chequeo de Cambio en el design doc: es una simplificación consciente,
  // no un cálculo exacto de "quién está en cancha ahora mismo".
  const salidosOExpulsados = new Set<number>();
  for (const e of props.eventosRegistrados) {
    const nombreTipo = props.eventoNombrePorId.get(e.eventos_id);
    if (nombreTipo === "Tarjeta Roja" || nombreTipo === "Cambio") salidosOExpulsados.add(e.jugador_id);
  }
  const yaEntraron = new Set(
    props.eventosRegistrados
      .filter((e) => props.eventoNombrePorId.get(e.eventos_id) === "Cambio" && e.jugador_id_entra !== null)
      .map((e) => e.jugador_id_entra as number),
  );

  const disponiblesParaSalir = plantillaEquipo.filter((j) => !salidosOExpulsados.has(j.jugador_id));
  const disponiblesParaEntrar = plantillaEquipo.filter(
    (j) => !salidosOExpulsados.has(j.jugador_id) && !yaEntraron.has(j.jugador_id) && j.jugador_id !== sale,
  );

  const jugadorSimple = tipo !== "Cambio" ? sale : null;

  function handleConfirmar() {
    if (!tipo || !equipoId || sale === null || !minuto) return;
    props.onSubmit({
      partidos_id: props.partidoId,
      jugador_id: sale,
      equipo_id: equipoId,
      eventos_id: props.eventoIdPorNombre.get(tipo) as number,
      jugador_id_entra: tipo === "Cambio" ? entra : null,
      minuto: Number(minuto),
    });
    reset();
  }

  const puedeConfirmar =
    tipo !== null &&
    equipoId !== null &&
    sale !== null &&
    minuto !== "" &&
    (tipo !== "Cambio" || entra !== null);

  return (
    <section className="card carga-evento">
      <h2>Cargar evento</h2>

      {!tipo && (
        <div className="tap-grid">
          {TIPOS.map((t) => (
            <button key={t} type="button" className="tap-button" onClick={() => setTipo(t)}>
              <span className="tap-button__icon">{TIPO_ICONO[t]}</span>
              {t}
            </button>
          ))}
        </div>
      )}

      {tipo && !equipoId && (
        <div className="tap-grid">
          <button type="button" className="tap-button" onClick={() => setEquipoId(props.equipoLocalId)}>
            {props.nombreLocal}
          </button>
          <button type="button" className="tap-button" onClick={() => setEquipoId(props.equipoVisitanteId)}>
            {props.nombreVisitante}
          </button>
          <button type="button" className="link-button" onClick={reset}>← {tipo}</button>
        </div>
      )}

      {tipo && equipoId && tipo !== "Cambio" && sale === null && (
        <div className="tap-grid">
          {disponiblesParaSalir.map((j) => (
            <button key={j.jugador_id} type="button" className="tap-button" onClick={() => setSale(j.jugador_id)}>
              {j.dorsal ? `#${j.dorsal} ` : ""}{j.jugador}
            </button>
          ))}
          {disponiblesParaSalir.length === 0 && <p>No hay jugadores disponibles en la plantilla.</p>}
          <button type="button" className="link-button" onClick={() => setEquipoId(null)}>← Cambiar equipo</button>
        </div>
      )}

      {tipo === "Cambio" && equipoId && sale === null && (
        <div className="tap-grid">
          <p className="muted">¿Quién sale? (plantilla vigente — no distingue titular/suplente)</p>
          {disponiblesParaSalir.map((j) => (
            <button key={j.jugador_id} type="button" className="tap-button" onClick={() => setSale(j.jugador_id)}>
              {j.dorsal ? `#${j.dorsal} ` : ""}{j.jugador}
            </button>
          ))}
          <button type="button" className="link-button" onClick={() => setEquipoId(null)}>← Cambiar equipo</button>
        </div>
      )}

      {tipo === "Cambio" && equipoId && sale !== null && entra === null && (
        <div className="tap-grid">
          <p className="muted">¿Quién entra?</p>
          {disponiblesParaEntrar.map((j) => (
            <button key={j.jugador_id} type="button" className="tap-button" onClick={() => setEntra(j.jugador_id)}>
              {j.dorsal ? `#${j.dorsal} ` : ""}{j.jugador}
            </button>
          ))}
          {disponiblesParaEntrar.length === 0 && <p>No hay suplentes disponibles en la plantilla.</p>}
          <button type="button" className="link-button" onClick={() => setSale(null)}>← Elegir otro</button>
        </div>
      )}

      {tipo && equipoId && (jugadorSimple !== null || (tipo === "Cambio" && entra !== null)) && (
        <div className="confirmar-evento">
          <label>
            Minuto
            <input
              type="number"
              inputMode="numeric"
              min={0}
              max={130}
              value={minuto}
              onChange={(e) => setMinuto(e.target.value)}
              autoFocus
            />
          </label>
          {props.submitError && <p className="error-text">{props.submitError}</p>}
          <div className="confirmar-evento__acciones">
            <button type="button" onClick={reset} className="link-button">Cancelar</button>
            <button type="button" onClick={handleConfirmar} disabled={!puedeConfirmar || props.submitting}>
              {props.submitting ? "Guardando..." : "Confirmar"}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
