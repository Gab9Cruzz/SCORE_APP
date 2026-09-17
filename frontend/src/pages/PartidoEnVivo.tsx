import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { formatearResultadoDesempate, fraseResultadoDesempate } from "../lib/desempate";

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
    // D7 (portal-publico-feed-partidos-plan.md): C17 se resolvió por la
    // opción (b) — esta página sigue pública pase lo que pase, pero
    // /estadisticas/torneos/{id}/resultados sí gatea por Publicado
    // (T3.4b). Sin retry: un 404 por torneo despublicado no es transitorio.
    retry: false,
  });

  // D7: cabecera con nombre/país del torneo, enlazada a /torneos/:id — el
  // eslabón partido→torneo que C6 quiere medir. `retry: false` y sin
  // lanzar en el catch: si el torneo está despublicado, esta consulta
  // 404ea igual que resultadosQuery (mismo gate) y la cabecera
  // simplemente no se renderiza, en vez de romper la página.
  const torneoQuery = useQuery({
    queryKey: ["torneo-header", torneoId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/torneos/{torneo_id}", {
        params: { path: { torneo_id: torneoId as number } },
      } as never);
      if (error) throw error;
      return data as { id: number; torneo_grupo_id: number };
    },
    enabled: torneoId !== undefined,
    retry: false,
  });
  const grupoIdParaHeader = torneoQuery.data?.torneo_grupo_id;
  const grupoHeaderQuery = useQuery({
    queryKey: ["torneo-grupo-header", grupoIdParaHeader],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/torneo-grupos/{torneo_grupo_id}", {
        params: { path: { torneo_grupo_id: grupoIdParaHeader as number } },
      } as never);
      if (error) throw error;
      return data as { nombre: string; pais: string | null };
    },
    enabled: grupoIdParaHeader !== undefined,
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
  // Fase 1/2 (Timeline visual): nombre de equipo por hito — antes esta
  // timeline pública mostraba jugador pero nunca el equipo. Un partido de
  // bracket sin equipos definidos todavía (shell "Ganador Partido N") no
  // tiene eventos que mostrar, así que null acá nunca se busca de verdad —
  // se filtra igual para que el tipo del Map sea `number`, no `number | null`.
  const equipoNombrePorId = new Map<number, string>(
    [
      [partidoQuery.data.equipos_id_local, resultado?.equipo_local ?? "Local"],
      [partidoQuery.data.equipos_id_visitante, resultado?.equipo_visitante ?? "Visitante"],
    ].filter((par): par is [number, string] => par[0] != null),
  );

  const eventos = [...(eventosQuery.data ?? [])]
    .filter((e) => e.estado === "Registrado")
    .sort((a, b) => b.minuto - a.minuto);

  return (
    <div className="page en-vivo publico">
      {/* D7: identidad y salida — el visitante que llega desde WhatsApp
          veía dos nombres flotando, sin torneo, sin fecha y sin vuelta.
          No se renderiza nada si torneoQuery/grupoHeaderQuery no
          resolvieron todavía o el torneo está despublicado (404 propio,
          `retry:false` arriba) — nunca un link roto. */}
      {torneoQuery.data && grupoHeaderQuery.data && (
        <p className="en-vivo__torneo-header">
          <Link to={`/torneos/${torneoQuery.data.id}`}>{grupoHeaderQuery.data.nombre}</Link>
          {grupoHeaderQuery.data.pais && <span className="muted"> · {grupoHeaderQuery.data.pais}</span>}
        </p>
      )}
      <div className="marcador">
        <div className="marcador__equipo">
          <span>{resultado?.equipo_local ?? "Local"}</span>
        </div>
        <div className="marcador__score">
          {resultado
            ? formatearResultadoDesempate({
                golesLocal: resultado.goles_local,
                golesVisitante: resultado.goles_visitante,
                metodoDesempate: partidoQuery.data.metodo_desempate,
                huboTiempoExtra: partidoQuery.data.hubo_tiempo_extra,
                penalesLocal: partidoQuery.data.penales_local,
                penalesVisitante: partidoQuery.data.penales_visitante,
              })
            : "- : -"}
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
      {/* Desempate de eliminatoria: tiempo extra y penales (D-D9) — línea
          en prosa, "Definido en penales 4-2 tras 2-2 en el tiempo extra". */}
      {resultado &&
        (() => {
          const frase = fraseResultadoDesempate({
            golesLocal: resultado.goles_local,
            golesVisitante: resultado.goles_visitante,
            metodoDesempate: partidoQuery.data.metodo_desempate,
            huboTiempoExtra: partidoQuery.data.hubo_tiempo_extra,
            penalesLocal: partidoQuery.data.penales_local,
            penalesVisitante: partidoQuery.data.penales_visitante,
          });
          return frase && <p className="muted en-vivo__desempate">{frase}</p>;
        })()}
      {/* D7/C17(b): el torneo sigue existiendo y estando despublicado NO
          rompe la página (la superficie de partido queda pública pase lo
          que pase) — pero el marcador de arriba (placeholders "Local"/
          "- : -") se leería como datos reales sin este aviso explícito. */}
      {resultadosQuery.isError && (
        <p className="muted en-vivo__resultados-no-disponibles">Resultados no disponibles para este torneo.</p>
      )}

      <section className="card">
        <h2>Eventos</h2>
        {eventos.length === 0 && <p>Todavía no hay eventos cargados.</p>}
        {eventos.length > 0 && (
          <ul className="eventos-timeline">
            {eventos.map((e) => {
              const tipo = eventoNombre.get(e.eventos_id) ?? "";
              const nombreEq = equipoNombrePorId.get(e.equipo_id) ?? `Equipo #${e.equipo_id}`;
              const nombreJ = jugadorNombre.get(e.jugador_id) ?? `Jugador #${e.jugador_id}`;
              const esCambio = tipo === "Cambio";
              const nombreEntra =
                e.jugador_id_entra !== null && e.jugador_id_entra !== undefined
                  ? (jugadorNombre.get(e.jugador_id_entra) ?? `#${e.jugador_id_entra}`)
                  : null;
              const ariaLabel = esCambio
                ? `Minuto ${e.minuto}, cambio, ${nombreEq}, sale ${nombreJ}, entra ${nombreEntra ?? ""}`
                : `Minuto ${e.minuto}, ${tipo}, ${nombreEq}, ${nombreJ}`;
              return (
                <li key={e.id} aria-label={ariaLabel}>
                  <span className="eventos-timeline__minuto" aria-hidden="true">
                    {e.minuto}'
                  </span>
                  <span aria-hidden="true">{EVENTO_LABEL[tipo] ?? tipo}</span>
                  <div className="eventos-timeline__detalle" aria-hidden="true">
                    <span>{nombreEq}</span>
                    {esCambio ? (
                      <span className="muted">
                        Sale: {nombreJ} <span aria-hidden="true">➔</span> Entra: {nombreEntra}
                      </span>
                    ) : (
                      <span className="muted">{nombreJ}</span>
                    )}
                  </div>
                </li>
              );
            })}
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
