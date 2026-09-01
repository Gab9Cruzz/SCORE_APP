import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
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
  // EC-54 (motor-formatos-plantillas-navegacion-plan.md): un torneo
  // Grupos_Playoffs devuelve varias tablas bajo el mismo Torneo_ID — se
  // separan acá por Grupo_ID en vez de mezclarlas en una sola.
  fase_id: number | null;
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
interface GrupoRow {
  id: number;
  nombre: string;
}
interface GoleadorRow {
  jugador_id: number;
  jugador: string;
  equipo: string;
  goles: number;
}

// 3A-5 (docs/plans/cierre-backlog-todos-plan.md): GET
// /estadisticas/torneos/{id}/goleadores tiene su propio tope, `limit=50`
// por default (backend/app/api/routes/estadisticas.py) — distinto de
// LIMITE_LISTA (200, useResourceCrud) porque esta pantalla no pasa por ese
// hook (es un GET directo, no un CRUD paginado). Mismo criterio de "sin
// endpoint que devuelva el total real, se infiere truncado === tope".
const LIMITE_GOLEADORES = 50;

/** Selector de Edición (torneos-admin-plan.md, Fase 2, parte B): SOLO
 * cambia qué edición alimenta esta tabla — no navega a otra URL visible
 * como página distinta, no toca las demás sub-pestañas (Equipos/Plantillas/...
 * siguen mostrando la edición del dashboard). El querystring se actualiza
 * para que el link sea compartible y el botón "atrás" funcione, sin
 * recargar la página (Decision Audit Trail #6: evita el bug de "edité el
 * equipo de la edición equivocada porque el desplegable decía otra cosa"). */
export function EstadisticasDelTorneoPage() {
  const { torneoId, torneoGrupoId, formato } = useOutletContext<TorneoDashboardContext>();
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

  // EC-54: un torneo Grupos_Playoffs trae varios grupos mezclados en la
  // misma respuesta — se separan por Grupo_ID. Todas las filas de la
  // fase de grupos comparten el mismo Fase_ID, así que alcanza con
  // pedir los nombres UNA vez (no una llamada por grupo).
  const faseGruposId = posicionesQuery.data?.find((p) => p.grupo_id != null)?.fase_id ?? null;
  const gruposQuery = useResourceCrud<GrupoRow>({
    resourceKey: "grupos",
    basePath: "/api/v1/grupos",
    listParams: { fase_id: faseGruposId },
    enabled: formato === "Grupos_Playoffs" && faseGruposId != null,
  });
  const nombreGrupo = useMemo(
    () => new Map((gruposQuery.listQuery.data ?? []).map((g) => [g.id, g.nombre])),
    [gruposQuery.listQuery.data],
  );
  const posicionesPorGrupo = useMemo(() => {
    const mapa = new Map<number, PosicionRow[]>();
    for (const fila of posicionesQuery.data ?? []) {
      if (fila.grupo_id == null) continue;
      const arr = mapa.get(fila.grupo_id);
      if (arr) arr.push(fila);
      else mapa.set(fila.grupo_id, [fila]);
    }
    return [...mapa.entries()].sort(([a], [b]) => a - b);
  }, [posicionesQuery.data]);
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
      {formato === "Grupos_Playoffs" && !!posicionesQuery.data?.length
        ? // EC-54: un torneo Grupos_Playoffs separa por grupo — mezclarlos
          // en una sola tabla no dice nada (los puntos de un grupo no se
          // comparan con los de otro).
          posicionesPorGrupo.map(([grupoId, filas]) => (
            <div key={grupoId}>
              <h4>Grupo {nombreGrupo.get(grupoId) ?? grupoId}</h4>
              <TablaPosiciones filas={filas} />
            </div>
          ))
        : !!posicionesQuery.data?.length && <TablaPosiciones filas={posicionesQuery.data} />}

      <h3>Goleadores</h3>
      {goleadoresQuery.data?.length === 0 && <p className="muted">Sin goles registrados todavía en esta edición.</p>}
      {goleadoresQuery.data?.length === LIMITE_GOLEADORES && (
        <p className="muted">Mostrando los primeros {LIMITE_GOLEADORES} goleadores.</p>
      )}
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

function TablaPosiciones({ filas }: { filas: PosicionRow[] }) {
  return (
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
          {filas.map((p) => (
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
  );
}
