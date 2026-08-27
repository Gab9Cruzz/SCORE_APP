import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useOutletContext, useSearchParams } from "react-router-dom";
import { api, apiErrorMessage } from "../../../api/client";
import { useResourceCrud } from "../../../hooks/useResourceCrud";
import type { TorneoDashboardContext } from "./TorneoDashboard";

interface EdicionRow {
  id: number;
  numero_edicion: number;
  estado: string;
}
interface PosicionRow {
  equipo_id: number;
  equipo: string;
  pj: number;
  pg: number;
  pe: number;
  pp: number;
  gf: number;
  gc: number;
  dg: number;
  pts: number;
}
interface GoleadorRow {
  jugador_id: number;
  jugador: string;
  equipo: string;
  goles: number;
}

/** Selector de Edición (torneos-admin-plan.md, Fase 2, parte B): SOLO
 * cambia qué edición alimenta esta tabla — no navega a otra URL visible
 * como página distinta, no toca las demás sub-pestañas (Equipos/Plantillas/...
 * siguen mostrando la edición del dashboard). El querystring se actualiza
 * para que el link sea compartible y el botón "atrás" funcione, sin
 * recargar la página (Decision Audit Trail #6: evita el bug de "edité el
 * equipo de la edición equivocada porque el desplegable decía otra cosa"). */
export function EstadisticasDelTorneoPage() {
  const { torneoId, torneoGrupoId } = useOutletContext<TorneoDashboardContext>();
  const [searchParams, setSearchParams] = useSearchParams();

  const [edicionId, setEdicionId] = useState<number>(() => {
    const desdeUrl = Number(searchParams.get("edicion"));
    return Number.isFinite(desdeUrl) && desdeUrl > 0 ? desdeUrl : torneoId;
  });

  const ediciones = useResourceCrud<EdicionRow>({
    resourceKey: "torneos",
    basePath: "/api/v1/torneos",
    listParams: { torneo_grupo_id: torneoGrupoId },
  });

  function elegirEdicion(id: number) {
    setEdicionId(id);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("edicion", String(id));
      return next;
    });
  }

  // Si el dashboard cambia de torneoId (navegación a otra edición desde
  // la Pestaña Torneos) sin que este componente se desmonte del todo,
  // vuelve a alinear el selector — evita mostrar estadísticas de una
  // edición que ya no es la que el resto del dashboard tiene abierta.
  useEffect(() => {
    if (!searchParams.get("edicion")) setEdicionId(torneoId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [torneoId]);

  const posicionesQuery = useQuery({
    queryKey: ["estadisticas", "posiciones", edicionId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/estadisticas/torneos/{torneo_id}/posiciones", {
        params: { path: { torneo_id: edicionId } },
      } as never);
      if (error) throw error;
      return data as PosicionRow[];
    },
  });
  const goleadoresQuery = useQuery({
    queryKey: ["estadisticas", "goleadores", edicionId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/estadisticas/torneos/{torneo_id}/goleadores", {
        params: { path: { torneo_id: edicionId } },
      } as never);
      if (error) throw error;
      return data as GoleadorRow[];
    },
  });

  return (
    <div>
      <h2>Estadísticas</h2>
      <div className="torneo-dashboard__edicion-selector">
        <label htmlFor="selector-edicion">Edición:</label>
        <select
          id="selector-edicion"
          value={edicionId}
          onChange={(e) => elegirEdicion(Number(e.target.value))}
          disabled={ediciones.listQuery.isLoading}
        >
          {(ediciones.listQuery.data ?? [])
            .slice()
            .sort((a, b) => b.numero_edicion - a.numero_edicion)
            .map((e) => (
              <option key={e.id} value={e.id}>
                Edición {e.numero_edicion} ({e.estado.toLowerCase()})
              </option>
            ))}
        </select>
      </div>

      <h3>Tabla de posiciones</h3>
      {posicionesQuery.isLoading && <p>Cargando...</p>}
      {posicionesQuery.isError && <p className="error-text">{apiErrorMessage(posicionesQuery.error)}</p>}
      {posicionesQuery.data?.length === 0 && <p className="muted">Sin partidos jugados todavía en esta edición.</p>}
      {!!posicionesQuery.data?.length && (
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
              {posicionesQuery.data.map((p) => (
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
      )}

      <h3>Goleadores</h3>
      {goleadoresQuery.data?.length === 0 && <p className="muted">Sin goles registrados todavía en esta edición.</p>}
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
    </div>
  );
}
