import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
  // 3A-12 (docs/plans/cierre-backlog-todos-plan.md, EC-51): NULL en Liga
  // (sin Fase de Grupos) — grupo_equipo_id es a lo que apunta el PATCH de
  // desempate manual, orden_manual es el valor ya guardado (si hay).
  grupo_equipo_id: number | null;
  orden_manual: number | null;
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
  const queryClient = useQueryClient();

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

  // 3A-12 (EC-51): PATCH /grupos/equipos/{id} — orden_manual: null saca
  // el override. Invalida "posiciones" (no "grupos": el nombre del grupo
  // no cambia) para que la tabla se reordene con el valor recién guardado.
  const definirOrdenManual = useMutation({
    mutationFn: async ({ grupoEquipoId, ordenManual }: { grupoEquipoId: number; ordenManual: number | null }) => {
      const { data, error } = await api.PATCH("/api/v1/grupos/equipos/{grupo_equipo_id}", {
        params: { path: { grupo_equipo_id: grupoEquipoId } },
        body: { orden_manual: ordenManual },
      } as never);
      if (error) throw error;
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["estadisticas", "posiciones", edicionId] }),
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
      {definirOrdenManual.isError && <p className="error-text">{apiErrorMessage(definirOrdenManual.error)}</p>}
      {posicionesQuery.data?.length === 0 && <p className="muted">Sin partidos jugados todavía en esta edición.</p>}
      {formato === "Grupos_Playoffs" && !!posicionesQuery.data?.length
        ? // EC-54: un torneo Grupos_Playoffs separa por grupo — mezclarlos
          // en una sola tabla no dice nada (los puntos de un grupo no se
          // comparan con los de otro).
          posicionesPorGrupo.map(([grupoId, filas]) => (
            <div key={grupoId}>
              <h4>Grupo {nombreGrupo.get(grupoId) ?? grupoId}</h4>
              <TablaPosiciones
                filas={filas}
                onDefinirOrdenManual={(grupoEquipoId, ordenManual) =>
                  definirOrdenManual.mutate({ grupoEquipoId, ordenManual })
                }
                guardando={definirOrdenManual.isPending}
              />
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

/** 3A-12 (EC-51): equipos cuyos PTS/DG/GF coinciden con al menos un
 * vecino en la tabla YA ordenada — el enfrentamiento directo no está
 * calculado acá (el admin lo resuelve a ojo, este componente solo
 * persiste la decisión), así que "empatado" se define por esos tres
 * campos nada más, no por posición. */
function idsEmpatados(filas: PosicionRow[]): Set<number> {
  const empatados = new Set<number>();
  const mismosPuntos = (a: PosicionRow, b: PosicionRow) => a.pts === b.pts && a.dg === b.dg && a.gf === b.gf;
  for (let i = 0; i < filas.length; i++) {
    const anterior = filas[i - 1];
    const siguiente = filas[i + 1];
    if ((anterior && mismosPuntos(filas[i], anterior)) || (siguiente && mismosPuntos(filas[i], siguiente))) {
      empatados.add(filas[i].equipo_id);
    }
  }
  return empatados;
}

function TablaPosiciones({
  filas,
  onDefinirOrdenManual,
  guardando,
}: {
  filas: PosicionRow[];
  /** Solo se pasa desde la rama Grupos_Playoffs (Liga no tiene
   * grupo_equipo_id) — su sola presencia habilita la columna de
   * desempate, no hace falta un booleano aparte. */
  onDefinirOrdenManual?: (grupoEquipoId: number, ordenManual: number | null) => void;
  guardando?: boolean;
}) {
  const empatados = useMemo(() => idsEmpatados(filas), [filas]);
  const hayColumnaDesempate = Boolean(onDefinirOrdenManual);

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
            {hayColumnaDesempate && <th>Desempate</th>}
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
              {hayColumnaDesempate && (
                <td>
                  {/* Solo se ofrece si de verdad hay algo que desempatar
                      (EC-51: "cuando PTS/DG/GF no alcanzan") — mostrarlo
                      en cada fila invitaría a "ordenar" una tabla que ya
                      está resuelta por puntos. */}
                  {p.grupo_equipo_id != null && empatados.has(p.equipo_id) && (
                    <CeldaOrdenManual
                      grupoEquipoId={p.grupo_equipo_id}
                      ordenManual={p.orden_manual}
                      onGuardar={(valor) => onDefinirOrdenManual?.(p.grupo_equipo_id as number, valor)}
                      guardando={guardando ?? false}
                    />
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Mismo patrón de ícono de lápiz que EventoTimelineFila (ControlDeMesa.tsx)
 * y Cronometro.tsx: click para editar inline, sin navegar a otra pantalla.
 * `null` es un valor de guardado válido (sacar el override), distinto de
 * "no tocar nada" — por eso el botón "Quitar" existe aparte de Cancelar. */
function CeldaOrdenManual(props: {
  grupoEquipoId: number;
  ordenManual: number | null;
  onGuardar: (valor: number | null) => void;
  guardando: boolean;
}) {
  const { ordenManual, onGuardar, guardando } = props;
  const [editando, setEditando] = useState(false);
  const [valor, setValor] = useState(ordenManual != null ? String(ordenManual) : "");

  if (!editando) {
    return (
      <button
        type="button"
        className="link-button"
        onClick={() => {
          setValor(ordenManual != null ? String(ordenManual) : "");
          setEditando(true);
        }}
      >
        {ordenManual != null ? `#${ordenManual} ✏️` : "Definir manualmente"}
      </button>
    );
  }

  return (
    <span className="orden-manual-editor">
      <input
        type="number"
        aria-label="Orden manual"
        min={1}
        value={valor}
        onChange={(e) => setValor(e.target.value)}
        style={{ width: "3.5rem" }}
        autoFocus
      />
      <button
        type="button"
        disabled={guardando || valor === ""}
        onClick={() => {
          onGuardar(Number(valor));
          setEditando(false);
        }}
      >
        Guardar
      </button>
      {ordenManual != null && (
        <button
          type="button"
          className="link-button"
          disabled={guardando}
          onClick={() => {
            onGuardar(null);
            setEditando(false);
          }}
        >
          Quitar
        </button>
      )}
      <button type="button" className="link-button" onClick={() => setEditando(false)}>
        Cancelar
      </button>
    </span>
  );
}
