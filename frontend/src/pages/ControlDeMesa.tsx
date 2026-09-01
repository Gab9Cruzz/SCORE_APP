import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { api, apiErrorMessage } from "../api/client";
import { useAuth } from "../auth/useAuth";
import { Cronometro } from "./Cronometro";

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
  const queryClient = useQueryClient();

  const partidosQuery = useQuery({
    queryKey: ["partidos-mesa"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/partidos", { params: { query: { limit: 100 } } });
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
  const nombreEquipo = useMemo(
    () => new Map((equiposQuery.data ?? []).map((e) => [e.id, e.nombre])),
    [equiposQuery.data],
  );

  const editarFecha = useMutation({
    mutationFn: async ({ id, fecha }: { id: number; fecha: string }) => {
      const { data, error } = await api.PATCH("/api/v1/partidos/{partido_id}", {
        params: { path: { partido_id: id } },
        body: { fecha_partido: fecha },
      } as never);
      if (error) throw error;
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["partidos-mesa"] }),
  });

  // "Empezar Partido" dispara el Hito Inicio_Partido (no el PATCH directo
  // de estado) — así el partido siempre queda con un Inicio_Partido
  // auditable con hora real, necesario para vw_duracion_partido (Flujo 4
  // del plan). El botón del dashboard y el Cronómetro convergen al mismo
  // endpoint.
  const empezarPartido = useMutation({
    mutationFn: async (id: number) => {
      const { data, error } = await api.POST("/api/v1/partidos/{partido_id}/hitos", {
        params: { path: { partido_id: id } },
        body: { tipo_hito: "Inicio_Partido" },
      } as never);
      if (error) throw error;
      return data;
    },
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: ["partidos-mesa"] });
      setPartidoId(id);
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
      {empezarPartido.isError && <p className="error-text">{apiErrorMessage(empezarPartido.error)}</p>}
      <ul className="partidos-list">
        {seleccionables.map((p) => (
          <li key={p.id} className="partido-mesa-fila">
            <span className="badge">{p.estado}</span>
            <span className="partido-mesa-fila__equipos">
              {p.equipos_id_local != null ? nombreEquipo.get(p.equipos_id_local) ?? `#${p.equipos_id_local}` : "?"}
              {" vs "}
              {p.equipos_id_visitante != null ? nombreEquipo.get(p.equipos_id_visitante) ?? `#${p.equipos_id_visitante}` : "?"}
            </span>
            <EditorFechaPartido
              partidoId={p.id}
              fechaActual={p.fecha_partido}
              onGuardar={(fecha) => editarFecha.mutate({ id: p.id, fecha })}
              guardando={editarFecha.isPending}
            />
            {/* "Empezar Partido" solo si Programado; una vez en curso el
                botón cambia a "Ir al partido en vivo" — mismo lugar,
                mismo peso visual, para no reflowar la fila (Flujo 4). */}
            {p.estado === "Programado" ? (
              <button type="button" disabled={empezarPartido.isPending} onClick={() => empezarPartido.mutate(p.id)}>
                {empezarPartido.isPending ? "Iniciando..." : "▶ Empezar Partido"}
              </button>
            ) : (
              <button type="button" onClick={() => setPartidoId(p.id)}>
                Ir al partido en vivo
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Campo de fecha/hora inline (Flujo 4 del plan: "desde esta misma
 * vista", sin navegar a otra pantalla). Clic en la fecha abre un
 * `datetime-local`, PATCH al confirmar, refetch inmediato — si falla, el
 * campo vuelve al valor anterior + mensaje inline (no pierde el resto de
 * la fila). */
function EditorFechaPartido(props: {
  partidoId: number;
  fechaActual: string;
  onGuardar: (fechaIso: string) => void;
  guardando: boolean;
}) {
  const [editando, setEditando] = useState(false);
  const [valor, setValor] = useState(() => props.fechaActual.slice(0, 16));

  if (!editando) {
    return (
      <button type="button" className="link-button" onClick={() => setEditando(true)}>
        📅 {new Date(props.fechaActual).toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short" })} ▾
      </button>
    );
  }

  return (
    <span className="editor-fecha-partido">
      <input
        type="datetime-local"
        aria-label="Fecha y hora del partido"
        value={valor}
        onChange={(e) => setValor(e.target.value)}
        autoFocus
      />
      <button
        type="button"
        disabled={props.guardando}
        onClick={() => {
          props.onGuardar(valor);
          setEditando(false);
        }}
      >
        ✓
      </button>
      <button type="button" className="link-button" onClick={() => setEditando(false)}>
        ✕
      </button>
    </span>
  );
}

/** Exportado para reusarlo tal cual en el módulo Árbitro (Fase 3, D4) —
 * "Mis partidos" embebe este mismo componente al elegir un partido, sin
 * duplicar la lógica de carga de eventos/mutaciones. No tiene ninguna
 * afordancia exclusiva de TorneoAdmin/AdminGeneral (confirmado en la
 * revisión de Fase 3): solo scoreboard, form de carga de evento y
 * timeline de eventos, seguro de embeber para un Árbitro. */
export function MesaPanel({ partidoId, onVolver }: { partidoId: number; onVolver: () => void }) {
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
    enabled: equipoLocalId != null,
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
    enabled: equipoVisitanteId != null,
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

  // Corrección de minuto de un evento ya cargado (gestion-avanzada-
  // equipos-control-mesa-plan.md, Entregable 3 — "cargué un gol en el
  // minuto 23 pero fue en el 32"). Caso DISTINTO de corregir un Hito de
  // tiempo (eso vive en Cronometro.tsx): esto es la timeline de eventos
  // que ya existía en este panel.
  const corregirMinutoEvento = useMutation({
    mutationFn: async ({ id, minuto }: { id: number; minuto: number }) => {
      const { data, error } = await api.PATCH("/api/v1/eventos-partido/{evento_partido_id}", {
        params: { path: { evento_partido_id: id } },
        body: { minuto },
      } as never);
      if (error) throw error;
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["eventos-partido", partidoId] }),
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
  // Motor de Formatos: un partido de bracket puede nacer con uno o los
  // dos equipos sin definir todavía ("Ganador Partido N", TBD hasta que
  // el partido anterior termine) — no hay nada que cargar acá hasta
  // entonces.
  if (partido.equipos_id_local == null || partido.equipos_id_visitante == null) {
    return (
      <div className="page">
        <button type="button" className="link-button" onClick={onVolver}>← Volver a la lista</button>
        <p className="muted">Este partido todavía no tiene los dos equipos definidos — esperá a que termine el partido anterior del bracket.</p>
      </div>
    );
  }
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

      <Cronometro
        partidoId={partidoId}
        equipoLocalId={partido.equipos_id_local}
        equipoVisitanteId={partido.equipos_id_visitante}
        nombreLocal={nombreLocal}
        nombreVisitante={nombreVisitante}
      />

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
        {corregirMinutoEvento.isError && <p className="error-text">{apiErrorMessage(corregirMinutoEvento.error)}</p>}
        {eventosRegistrados.length > 0 && (
          <ul className="eventos-timeline">
            {[...eventosRegistrados].sort((a, b) => b.minuto - a.minuto).map((e) => (
              <EventoTimelineFila
                key={e.id}
                evento={e}
                tipoIcono={TIPO_ICONO[eventoNombrePorId.get(e.eventos_id) as TipoEvento] ?? eventoNombrePorId.get(e.eventos_id) ?? ""}
                jugadorNombre={[...plantillaLocalQuery.data ?? [], ...plantillaVisitanteQuery.data ?? []].find((j) => j.jugador_id === e.jugador_id)?.jugador ?? `#${e.jugador_id}`}
                onCorregir={(minuto) => corregirMinutoEvento.mutate({ id: e.id, minuto })}
                corrigiendo={corregirMinutoEvento.isPending}
              />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

/** Fila de la timeline de eventos con corrección de minuto inline —
 * mismo patrón de ícono de lápiz que Cronometro.tsx usa para sus Hitos,
 * pero es un control DISTINTO (PATCH /eventos-partido/{id}, no
 * /partidos/{id}/hitos/{id}): son dos problemas distintos según el plan
 * ("cargué un gol en el minuto 23 pero fue en el 32" vs. "presioné Fin
 * del 1er Tiempo tarde"). */
function EventoTimelineFila(props: {
  evento: EventoPartidoRow;
  tipoIcono: string;
  jugadorNombre: string;
  onCorregir: (minuto: number) => void;
  corrigiendo: boolean;
}) {
  const { evento, tipoIcono, jugadorNombre, onCorregir, corrigiendo } = props;
  const [editando, setEditando] = useState(false);
  const [minuto, setMinuto] = useState(String(evento.minuto));

  return (
    <li>
      {editando ? (
        <>
          <input
            type="number"
            aria-label="Corregir minuto del evento"
            value={minuto}
            onChange={(e) => setMinuto(e.target.value)}
            style={{ width: "3.5rem" }}
            autoFocus
          />
          <button
            type="button"
            disabled={corrigiendo}
            onClick={() => {
              if (minuto !== "") onCorregir(Number(minuto));
              setEditando(false);
            }}
          >
            Guardar
          </button>
          <button type="button" className="link-button" onClick={() => setEditando(false)}>
            Cancelar
          </button>
        </>
      ) : (
        <>
          <span className="eventos-timeline__minuto">{evento.minuto}'</span>
          <span>{tipoIcono}</span>
          <span>{jugadorNombre}</span>
          <button type="button" className="link-button" aria-label="Corregir minuto" onClick={() => setEditando(true)}>
            ✏️
          </button>
        </>
      )}
    </li>
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
  minuto: number;
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
