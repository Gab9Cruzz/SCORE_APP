import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";

export function DashboardPage() {
  const torneosQuery = useQuery({
    queryKey: ["torneos"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/torneos", { params: { query: { estado: "Activo" } } });
      if (error) throw error;
      return data;
    },
  });

  const [torneoId, setTorneoId] = useState<number | null>(null);
  const torneos = torneosQuery.data ?? [];
  const selectedId = torneoId ?? torneos[0]?.id ?? null;

  return (
    <div className="page">
      <h1>Dashboard de Torneo</h1>

      {torneosQuery.isLoading && <p>Cargando torneos...</p>}
      {torneosQuery.isError && <p className="error-text">No se pudieron cargar los torneos.</p>}

      {torneos.length > 0 && (
        <label className="torneo-picker">
          Torneo:
          <select
            value={selectedId ?? ""}
            onChange={(e) => setTorneoId(Number(e.target.value))}
          >
            {torneos.map((t) => (
              <option key={t.id} value={t.id}>
                {t.nombre}
              </option>
            ))}
          </select>
        </label>
      )}

      {!torneosQuery.isLoading && torneos.length === 0 && <p>No hay torneos activos todavía.</p>}

      {selectedId !== null && (
        <div className="dashboard-grid">
          <TablaPosiciones torneoId={selectedId} />
          <Goleadores torneoId={selectedId} />
          <ProximosPartidos torneoId={selectedId} />
        </div>
      )}
    </div>
  );
}

function TablaPosiciones({ torneoId }: { torneoId: number }) {
  const query = useQuery({
    queryKey: ["posiciones", torneoId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/estadisticas/torneos/{torneo_id}/posiciones", {
        params: { path: { torneo_id: torneoId } },
      });
      if (error) throw error;
      return data;
    },
  });

  return (
    <section className="card">
      <h2>Tabla de posiciones</h2>
      {query.isLoading && <p>Cargando...</p>}
      {query.isError && <p className="error-text">No se pudo cargar la tabla.</p>}
      {query.data && query.data.length === 0 && <p>Todavía no hay partidos finalizados.</p>}
      {query.data && query.data.length > 0 && (
        <div className="table-scroll">
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
              {query.data.map((row) => (
                <tr key={row.equipo_id}>
                  <td>{row.equipo}</td>
                  <td>{row.pj}</td>
                  <td>{row.pg}</td>
                  <td>{row.pe}</td>
                  <td>{row.pp}</td>
                  <td>{row.gf}</td>
                  <td>{row.gc}</td>
                  <td>{row.dg}</td>
                  <td>
                    <strong>{row.pts}</strong>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function Goleadores({ torneoId }: { torneoId: number }) {
  const query = useQuery({
    queryKey: ["goleadores", torneoId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/estadisticas/torneos/{torneo_id}/goleadores", {
        params: { path: { torneo_id: torneoId }, query: { limit: 10 } },
      });
      if (error) throw error;
      return data;
    },
  });

  return (
    <section className="card">
      <h2>Goleadores</h2>
      {query.isLoading && <p>Cargando...</p>}
      {query.isError && <p className="error-text">No se pudieron cargar los goleadores.</p>}
      {query.data && query.data.length === 0 && <p>Todavía no hay goles cargados.</p>}
      {query.data && query.data.length > 0 && (
        <ol className="goleadores-list">
          {query.data.map((g) => (
            <li key={`${g.jugador_id}-${g.equipo_id}`}>
              <span>{g.jugador}</span>
              <span className="muted">{g.equipo}</span>
              <strong>{g.goles}</strong>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function ProximosPartidos({ torneoId }: { torneoId: number }) {
  const query = useQuery({
    queryKey: ["proximos-partidos", torneoId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/estadisticas/proximos-partidos", {
        params: { query: { torneo_id: torneoId } },
      });
      if (error) throw error;
      return data;
    },
  });

  return (
    <section className="card">
      <h2>Próximos partidos</h2>
      {query.isLoading && <p>Cargando...</p>}
      {query.isError && <p className="error-text">No se pudieron cargar los próximos partidos.</p>}
      {query.data && query.data.length === 0 && <p>No hay partidos programados.</p>}
      {query.data && query.data.length > 0 && (
        <ul className="partidos-list">
          {query.data.map((p) => (
            <li key={p.partido_id}>
              <div>
                <strong>{p.equipo_local}</strong> vs <strong>{p.equipo_visitante}</strong>
              </div>
              <div className="muted">
                {new Date(p.fecha_partido).toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short" })}
                {p.jornada ? ` · Jornada ${p.jornada}` : ""}
              </div>
              <Link to={`/partido/${p.partido_id}/en-vivo`}>Ver en vivo →</Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
