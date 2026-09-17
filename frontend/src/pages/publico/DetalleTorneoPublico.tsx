import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, apiErrorMessage } from "../../api/client";
import { Escudo } from "../../components/publico/Escudo";
import { useNombrePorIdConFaltantes } from "../../hooks/useFetchFaltantes";
import { BracketView } from "../torneo-admin/torneo-dashboard/BracketView";

interface TorneoDetalle {
  id: number;
  nombre: string;
  torneo_grupo_id: number;
  formato: "Liga" | "Eliminacion" | "Grupos_Playoffs";
  fecha_inicio: string;
  estado: string;
  // Cierre de Fase Regular + Llaves + Playoffs (Fase E4) — NULL mientras
  // el torneo no está cerrado.
  campeon_equipo_id: number | null;
  subcampeon_equipo_id: number | null;
  tercer_puesto_equipo_id: number | null;
  fecha_cierre: string | null;
}
interface TorneoGrupoDetalle {
  id: number;
  nombre: string;
  pais: string | null;
  logo_url: string | null;
}
interface PosicionRow {
  equipo_id: number;
  equipo: string;
  grupo_id: number | null;
  pj: number;
  pg: number;
  pe: number;
  pp: number;
  gf: number;
  gc: number;
  dg: number;
  pts: number;
}
interface ResultadoRow {
  partido_id: number;
  equipo_local: string;
  equipo_visitante: string;
  goles_local: number;
  goles_visitante: number;
  fecha_partido: string;
  estado: string;
}
interface GoleadorRow {
  jugador_id: number;
  jugador: string;
  equipo: string;
  goles: number;
}

type Tab = "posiciones" | "resultados" | "goleadores";

const formatearFecha = (iso: string) => new Date(iso).toLocaleDateString("es-AR", { day: "2-digit", month: "short" });

/** Vista pública de un torneo (portal-publico-feed-partidos-plan.md, T5.2):
 * tabla de posiciones, resultados y goleadores con los endpoints públicos
 * de /estadisticas/* que ya existen — nueva es solo esta página. Gateada
 * por Publicado (C2/T3.4b) del lado del backend: un anónimo sobre un
 * torneo despublicado recibe 404 en el mismo GET /torneos/{id} que arma
 * esta página, así que ese caso se resuelve con el mismo estado de error
 * que "torneo inexistente" (D16: el 404 público necesita diseño, no la
 * pantalla cruda del router). */
export function DetalleTorneoPublicoPage() {
  const { torneoId } = useParams<{ torneoId: string }>();
  const id = Number(torneoId);

  const torneoQuery = useQuery({
    queryKey: ["torneo-publico", id],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/torneos/{torneo_id}", {
        params: { path: { torneo_id: id } },
      } as never);
      if (error) throw error;
      return data as TorneoDetalle;
    },
    enabled: Number.isFinite(id),
    retry: false,
  });

  const grupoId = torneoQuery.data?.torneo_grupo_id;
  const grupoQuery = useQuery({
    queryKey: ["torneo-grupo-publico", grupoId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/torneo-grupos/{torneo_grupo_id}", {
        params: { path: { torneo_grupo_id: grupoId as number } },
      } as never);
      if (error) throw error;
      return data as TorneoGrupoDetalle;
    },
    enabled: grupoId !== undefined,
  });

  const formato = torneoQuery.data?.formato;
  // D8a: Resultados por defecto si el torneo ya empezó — proxy barato
  // (Fecha_Inicio <= hoy) que no exige una consulta aparte solo para
  // decidir la pestaña inicial. El torneo Eliminación no tiene pestaña
  // de Posiciones (D8b): arranca directo en Resultados.
  const yaEmpezo = torneoQuery.data ? new Date(torneoQuery.data.fecha_inicio) <= new Date() : false;
  const [tab, setTab] = useState<Tab | null>(null);
  const tabEfectiva: Tab = tab ?? (formato === "Eliminacion" || yaEmpezo ? "resultados" : "posiciones");

  const posicionesQuery = useQuery({
    queryKey: ["estadisticas-publico", "posiciones", id],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/estadisticas/torneos/{torneo_id}/posiciones", {
        params: { path: { torneo_id: id } },
      } as never);
      if (error) throw error;
      return data as PosicionRow[];
    },
    enabled: torneoQuery.isSuccess && formato !== "Eliminacion",
  });

  const resultadosQuery = useQuery({
    queryKey: ["estadisticas-publico", "resultados", id],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/estadisticas/torneos/{torneo_id}/resultados", {
        params: { path: { torneo_id: id } },
      } as never);
      if (error) throw error;
      return data as ResultadoRow[];
    },
    enabled: torneoQuery.isSuccess,
  });

  const goleadoresQuery = useQuery({
    queryKey: ["estadisticas-publico", "goleadores", id],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/estadisticas/torneos/{torneo_id}/goleadores", {
        params: { path: { torneo_id: id } },
      } as never);
      if (error) throw error;
      return data as GoleadorRow[];
    },
    enabled: torneoQuery.isSuccess,
  });

  if (!Number.isFinite(id)) {
    return (
      <div className="page publico">
        <p className="error-text">Torneo inválido.</p>
      </div>
    );
  }

  if (torneoQuery.isLoading) {
    return (
      <div className="page publico">
        <p>Cargando torneo...</p>
      </div>
    );
  }

  // D16: 404 público con diseño propio — no revela si el torneo existe y
  // no está publicado, o si directamente no existe (mismo mensaje genérico
  // del backend, ver deps.verificar_torneo_visible).
  if (torneoQuery.isError || !torneoQuery.data) {
    return (
      <div className="page publico">
        <div className="card publico__no-encontrado">
          <h1>No encontramos este torneo</h1>
          <p className="muted">Puede que el link esté mal escrito o que el torneo ya no esté disponible.</p>
          <Link to="/">Volver al inicio</Link>
        </div>
      </div>
    );
  }

  const torneo = torneoQuery.data;
  const grupo = grupoQuery.data;

  return (
    <div className="page publico publico-torneo">
      <header className="publico-torneo__header">
        <Escudo id={torneo.torneo_grupo_id} nombre={grupo?.nombre ?? torneo.nombre} logoUrl={grupo?.logo_url} tamano="grande" />
        <div>
          <h1>{grupo?.nombre ?? torneo.nombre}</h1>
          <p className="muted">{grupo?.pais ?? " "}</p>
        </div>
        <BotonCompartir titulo={grupo?.nombre ?? torneo.nombre} />
      </header>

      {torneo.estado === "Finalizado" && <PodioPublico torneo={torneo} />}

      <nav className="publico-torneo__tabs" role="tablist">
        {formato !== "Eliminacion" && (
          <button
            type="button"
            role="tab"
            aria-selected={tabEfectiva === "posiciones"}
            className={tabEfectiva === "posiciones" ? "active" : undefined}
            onClick={() => setTab("posiciones")}
          >
            Posiciones
          </button>
        )}
        <button
          type="button"
          role="tab"
          aria-selected={tabEfectiva === "resultados"}
          className={tabEfectiva === "resultados" ? "active" : undefined}
          onClick={() => setTab("resultados")}
        >
          Resultados
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tabEfectiva === "goleadores"}
          className={tabEfectiva === "goleadores" ? "active" : undefined}
          onClick={() => setTab("goleadores")}
        >
          Goleadores
        </button>
      </nav>

      {tabEfectiva === "posiciones" && formato !== "Eliminacion" && (
        <section className="card">
          {posicionesQuery.isLoading && <p>Cargando...</p>}
          {posicionesQuery.isError && <p className="error-text">{apiErrorMessage(posicionesQuery.error)}</p>}
          {/* D8c: un torneo recién creado no muestra tres tablas de ceros
              — la primera impresión honesta es que todavía no hay nada
              que mostrar, con una acción hacia lo que sí hay. */}
          {posicionesQuery.data?.length === 0 && (
            <p className="muted">Todavía no hay partidos jugados en este torneo.</p>
          )}
          {!!posicionesQuery.data?.length && <TablaPosicionesPublica filas={posicionesQuery.data} />}
          {formato === "Grupos_Playoffs" && <BracketView torneoId={id} />}
        </section>
      )}

      {tabEfectiva === "resultados" && (
        <section className="card">
          {resultadosQuery.isLoading && <p>Cargando...</p>}
          {resultadosQuery.isError && <p className="error-text">{apiErrorMessage(resultadosQuery.error)}</p>}
          {resultadosQuery.data?.length === 0 && (
            <p className="muted">Todavía no hay partidos programados en este torneo.</p>
          )}
          {!!resultadosQuery.data?.length && (
            <ul className="publico-torneo__resultados">
              {resultadosQuery.data.map((r) => (
                <li key={r.partido_id}>
                  <Link to={`/partidos/${r.partido_id}`} className="publico-torneo__resultado-fila">
                    <span className="muted">{formatearFecha(r.fecha_partido)}</span>
                    <span>{r.equipo_local}</span>
                    <span className="publico-torneo__marcador">
                      {r.estado === "Programado" ? "vs" : `${r.goles_local} - ${r.goles_visitante}`}
                    </span>
                    <span>{r.equipo_visitante}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
          {formato === "Eliminacion" && <BracketView torneoId={id} />}
        </section>
      )}

      {tabEfectiva === "goleadores" && (
        <section className="card">
          {goleadoresQuery.isLoading && <p>Cargando...</p>}
          {goleadoresQuery.isError && <p className="error-text">{apiErrorMessage(goleadoresQuery.error)}</p>}
          {goleadoresQuery.data?.length === 0 && <p className="muted">Todavía no hay goles registrados.</p>}
          {!!goleadoresQuery.data?.length && (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Jugador</th>
                    <th>Equipo</th>
                    <th>Goles</th>
                  </tr>
                </thead>
                <tbody>
                  {goleadoresQuery.data.map((g) => (
                    <tr key={g.jugador_id}>
                      <td>{g.jugador}</td>
                      <td>{g.equipo}</td>
                      <td>{g.goles}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

function TablaPosicionesPublica({ filas }: { filas: PosicionRow[] }) {
  const porGrupo = new Map<string, PosicionRow[]>();
  for (const fila of filas) {
    const clave = fila.grupo_id != null ? String(fila.grupo_id) : "unica";
    const arr = porGrupo.get(clave);
    if (arr) arr.push(fila);
    else porGrupo.set(clave, [fila]);
  }

  return (
    <>
      {[...porGrupo.values()].map((grupoFilas) => (
        <div className="table-scroll" key={grupoFilas[0]?.equipo_id}>
          <table>
            <thead>
              <tr>
                <th>Equipo</th>
                <th>PJ</th>
                <th>PG</th>
                <th>PE</th>
                <th>PP</th>
                <th>GF</th>
                <th>GC</th>
                <th>DG</th>
                <th>Pts</th>
              </tr>
            </thead>
            <tbody>
              {grupoFilas.map((p) => (
                <tr key={p.equipo_id}>
                  <td>{p.equipo}</td>
                  <td>{p.pj}</td>
                  <td>{p.pg}</td>
                  <td>{p.pe}</td>
                  <td>{p.pp}</td>
                  <td>{p.gf}</td>
                  <td>{p.gc}</td>
                  <td>{p.dg}</td>
                  <td>{p.pts}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </>
  );
}

/** T5.2b/D15: copia el deep link, sin sistema de toasts nuevo — el botón
 * intercambia su propio label por "¡Copiado!" 2s. `navigator.share` en
 * móvil cuando está disponible. `navigator.clipboard` no existe en
 * contexto inseguro (http:// sin TLS): en ese caso el link se muestra
 * seleccionable en vez de que el botón no haga nada. */
/** Cierre de Fase Regular + Llaves + Playoffs (Fase E4): el podio también
 * en el portal público si el torneo está `publicado` — mismo bloque
 * visual que TorneoDashboard.tsx, sin la franja de divergencia (Design
 * review: esa es ADMIN-ONLY, un visitante anónimo avisado de "este podio
 * podría estar mal" queda peor que uno viendo un podio simplemente
 * desactualizado) y sin el control de Reabrir. */
function PodioPublico({ torneo }: { torneo: TorneoDetalle }) {
  const ids = [torneo.campeon_equipo_id, torneo.subcampeon_equipo_id, torneo.tercer_puesto_equipo_id].filter(
    (id): id is number => id != null,
  );
  const nombreEquipo = useNombrePorIdConFaltantes("/api/v1/equipos", new Map(), ids);
  if (torneo.campeon_equipo_id == null) return null;

  return (
    <div className="podio">
      <div className="podio__fila podio__fila--1">
        <span className="podio__puesto">1°</span>
        <span>{nombreEquipo.get(torneo.campeon_equipo_id) ?? `Equipo #${torneo.campeon_equipo_id}`}</span>
      </div>
      {torneo.subcampeon_equipo_id != null && (
        <div className="podio__fila podio__fila--2">
          <span className="podio__puesto">2°</span>
          <span>{nombreEquipo.get(torneo.subcampeon_equipo_id) ?? `Equipo #${torneo.subcampeon_equipo_id}`}</span>
        </div>
      )}
      {torneo.tercer_puesto_equipo_id != null && (
        <div className="podio__fila podio__fila--3">
          <span className="podio__puesto">3°</span>
          <span>{nombreEquipo.get(torneo.tercer_puesto_equipo_id) ?? `Equipo #${torneo.tercer_puesto_equipo_id}`}</span>
        </div>
      )}
      {torneo.fecha_cierre && (
        <p className="podio__provenance muted--cuerpo">
          Torneo finalizado el {new Date(torneo.fecha_cierre).toLocaleDateString("es-AR")}.
        </p>
      )}
    </div>
  );
}

function BotonCompartir({ titulo }: { titulo: string }) {
  const [estado, setEstado] = useState<"idle" | "copiado" | "sin-clipboard">("idle");
  const url = typeof window !== "undefined" ? window.location.href : "";

  async function compartir() {
    if (typeof navigator !== "undefined" && "share" in navigator) {
      try {
        await navigator.share({ title: titulo, url });
        return;
      } catch {
        // Cancelado por el usuario u otro fallo — cae al camino de copiar.
      }
    }
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      await navigator.clipboard.writeText(url);
      setEstado("copiado");
      setTimeout(() => setEstado("idle"), 2000);
      return;
    }
    setEstado("sin-clipboard");
  }

  return (
    <div className="publico-torneo__compartir">
      <button type="button" onClick={compartir}>
        {estado === "copiado" ? "¡Copiado!" : "Compartir"}
      </button>
      {estado === "sin-clipboard" && (
        <input type="text" readOnly value={url} onFocus={(e) => e.currentTarget.select()} aria-label="Link para compartir" />
      )}
    </div>
  );
}
