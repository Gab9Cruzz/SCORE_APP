import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";
import type { Equipo as EquipoRow } from "../../../api/types";
import { api, apiErrorMessage } from "../../../api/client";
import { useResourceCrud } from "../../../hooks/useResourceCrud";
import { useNombrePorIdConFaltantes } from "../../../hooks/useFetchFaltantes";

interface PartidoBracket {
  id: number;
  equipos_id_local: number | null;
  equipos_id_visitante: number | null;
  ronda_nombre: string | null;
  partido_siguiente_id: number | null;
  slot_siguiente: "Local" | "Visitante" | null;
  partido_perdedor_siguiente_id: number | null;
  slot_perdedor_siguiente: "Local" | "Visitante" | null;
  estado: string;
}
interface PartidoRow {
  fase_id: number | null;
  grupo_id: number | null;
  estado: string;
}
interface MotorFormatosPanelProps {
  torneoId: number;
  formato: "Liga" | "Eliminacion" | "Grupos_Playoffs";
  partidos: PartidoRow[];
  equiposInscritosCount: number;
}

/** Design sección E del plan (motor-formatos-plantillas-navegacion-plan.md):
 * pantalla "Generar Fixture / Sorteo" — aparece en la pestaña Partidos una
 * vez que el torneo tiene equipos matriculados, antes de que existan
 * partidos generados por el motor. No reemplaza el alta manual existente
 * (sigue debajo, en la tabla de siempre) — es un atajo nuevo, no un
 * reemplazo de lo que ya funcionaba. */
export function MotorFormatosPanel(props: MotorFormatosPanelProps) {
  const { torneoId, formato, partidos, equiposInscritosCount } = props;
  const queryClient = useQueryClient();

  function invalidar() {
    queryClient.invalidateQueries({ queryKey: ["partidos"] });
    queryClient.invalidateQueries({ queryKey: ["bracket", torneoId] });
  }

  const fixture = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/torneos/{torneo_id}/fixture", {
        params: { path: { torneo_id: torneoId } },
      } as never);
      if (error) throw error;
      return data;
    },
    onSuccess: invalidar,
  });
  const sorteo = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/torneos/{torneo_id}/sorteo", {
        params: { path: { torneo_id: torneoId } },
        body: {},
      } as never);
      if (error) throw error;
      return data;
    },
    onSuccess: invalidar,
  });
  const playoffs = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/torneos/{torneo_id}/playoffs", {
        params: { path: { torneo_id: torneoId } },
      } as never);
      if (error) throw error;
      return data;
    },
    onSuccess: invalidar,
  });

  if (formato === "Liga") {
    const yaGenerado = partidos.some((p) => p.fase_id != null);
    if (yaGenerado) return null; // el calendario ya está — la tabla de abajo lo muestra
    return (
      <div className="card motor-formatos-panel">
        <p>Aún no se generó el calendario.</p>
        <p className="muted">{equiposInscritosCount} equipo(s) matriculado(s).</p>
        {fixture.isError && <p className="error-text">{apiErrorMessage(fixture.error)}</p>}
        <button type="button" disabled={fixture.isPending || equiposInscritosCount < 2} onClick={() => fixture.mutate()}>
          {fixture.isPending ? "Generando..." : "Generar Fixture"}
        </button>
      </div>
    );
  }

  if (formato === "Eliminacion") {
    const yaSorteado = partidos.some((p) => p.fase_id != null);
    if (!yaSorteado) {
      return (
        <div className="card motor-formatos-panel">
          <p>Aún no se hizo el sorteo.</p>
          <p className="muted">{equiposInscritosCount} equipo(s) matriculado(s).</p>
          {sorteo.isError && <p className="error-text">{apiErrorMessage(sorteo.error)}</p>}
          <button type="button" disabled={sorteo.isPending || equiposInscritosCount < 2} onClick={() => sorteo.mutate()}>
            {sorteo.isPending ? "Sorteando..." : "Hacer Sorteo"}
          </button>
        </div>
      );
    }
    return <BracketView torneoId={torneoId} />;
  }

  // Grupos_Playoffs
  const partidosGrupos = partidos.filter((p) => p.grupo_id != null);
  const partidosPlayoffs = partidos.filter((p) => p.fase_id != null && p.grupo_id == null);

  if (partidosGrupos.length === 0) {
    return (
      <div className="card motor-formatos-panel">
        <p>Fase de Grupos: sorteo pendiente.</p>
        <p className="muted">{equiposInscritosCount} equipo(s) matriculado(s).</p>
        {sorteo.isError && <p className="error-text">{apiErrorMessage(sorteo.error)}</p>}
        <button type="button" disabled={sorteo.isPending || equiposInscritosCount < 2} onClick={() => sorteo.mutate()}>
          {sorteo.isPending ? "Sorteando..." : "Sortear Grupos"}
        </button>
      </div>
    );
  }

  if (partidosPlayoffs.length === 0) {
    const grupoTerminado = partidosGrupos.every((p) => p.estado === "Finalizado" || p.estado === "Cancelado");
    return (
      <div className="card motor-formatos-panel">
        <p>Fase de Grupos: {grupoTerminado ? "terminada." : "en curso — la tabla de partidos está más abajo."}</p>
        {grupoTerminado && (
          <>
            <p className="muted">Fase Eliminatoria: pendiente de generar.</p>
            {playoffs.isError && <p className="error-text">{apiErrorMessage(playoffs.error)}</p>}
            <button type="button" disabled={playoffs.isPending} onClick={() => playoffs.mutate()}>
              {playoffs.isPending ? "Generando..." : "Generar Playoffs"}
            </button>
          </>
        )}
      </div>
    );
  }

  return <BracketView torneoId={torneoId} />;
}

/** Vista de bracket, solo lectura — Design sección E. Agrupa por columnas
 * (una por ronda, orden inferido por cantidad de partidos: la ronda con
 * más partidos es la más temprana) en vez de dibujar las líneas de
 * conexión del árbol — "Ganador Partido N" nunca queda como un espacio
 * en blanco sin explicación, que es el requisito real del mockup. */
function BracketView({ torneoId }: { torneoId: number }) {
  const query = useQuery({
    queryKey: ["bracket", torneoId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/torneos/{torneo_id}/bracket", {
        params: { path: { torneo_id: torneoId } },
      } as never);
      if (error) throw error;
      return data as PartidoBracket[];
    },
  });
  const equipos = useResourceCrud<EquipoRow>({ resourceKey: "equipos", basePath: "/api/v1/equipos" });
  const nombreEquipoBase = useMemo(
    () => new Map((equipos.listQuery.data ?? []).map((e) => [e.id, e.nombre])),
    [equipos.listQuery.data],
  );
  // Bug 2 (D2, parte B): resolución dirigida — un equipo fuera de la
  // ventana de LIMITE_LISTA se pedía individual antes de caer al fallback
  // "Equipo #ID" en el bracket (P3 del plan).
  const idsEquiposBracket = useMemo(
    () => (query.data ?? []).flatMap((p) => [p.equipos_id_local, p.equipos_id_visitante]),
    [query.data],
  );
  const nombreEquipo = useNombrePorIdConFaltantes("/api/v1/equipos", nombreEquipoBase, idsEquiposBracket);

  if (query.isLoading) return <p>Cargando bracket...</p>;
  if (query.isError) return <p className="error-text">{apiErrorMessage(query.error)}</p>;
  const partidos = query.data ?? [];
  if (partidos.length === 0) return null;

  const tercerLugar = partidos.find((p) => p.ronda_nombre === "Tercer Lugar");
  const rondas = partidos.filter((p) => p.ronda_nombre !== "Tercer Lugar");

  const porRonda = new Map<string, PartidoBracket[]>();
  for (const p of rondas) {
    const nombre = p.ronda_nombre ?? "?";
    const arr = porRonda.get(nombre);
    if (arr) arr.push(p);
    else porRonda.set(nombre, [p]);
  }
  // Más partidos = ronda más temprana (Octavos > Cuartos > Semifinal > Final).
  const ordenRondas = [...porRonda.entries()].sort((a, b) => b[1].length - a[1].length).map(([nombre]) => nombre);

  function etiqueta(equipoId: number | null, partido: PartidoBracket, slot: "Local" | "Visitante"): string {
    if (equipoId != null) return nombreEquipo.get(equipoId) ?? `Equipo #${equipoId}`;
    // Busca el feeder que apunta ESPECÍFICAMENTE a este slot (Local o
    // Visitante) — un partido puede tener 2 feeders distintos, uno por
    // lado, y mostrar el mismo para los dos sería un dato incorrecto, no
    // solo impreciso. El Tercer Lugar se alimenta del PERDEDOR de cada
    // semifinal (Partido_Perdedor_Siguiente_ID), no del ganador.
    const ganadorDe = partidos.find((p) => p.partido_siguiente_id === partido.id && p.slot_siguiente === slot);
    if (ganadorDe) return `Ganador Partido ${ganadorDe.id}`;
    const perdedorDe = partidos.find(
      (p) => p.partido_perdedor_siguiente_id === partido.id && p.slot_perdedor_siguiente === slot,
    );
    if (perdedorDe) return `Perdedor Semifinal ${perdedorDe.id}`;
    return "Por definir";
  }

  return (
    <div className="card motor-formatos-panel">
      <div className="bracket">
        {ordenRondas.map((nombreRonda) => (
          <div key={nombreRonda} className="bracket__columna">
            <h4>{nombreRonda}</h4>
            {porRonda.get(nombreRonda)!.map((p) => (
              <div key={p.id} className="bracket__partido">
                <div className="bracket__equipo">{etiqueta(p.equipos_id_local, p, "Local")}</div>
                <div className="bracket__equipo">{etiqueta(p.equipos_id_visitante, p, "Visitante")}</div>
              </div>
            ))}
          </div>
        ))}
        {tercerLugar && (
          <div className="bracket__columna bracket__columna--tercer-lugar">
            <h4>Tercer Lugar</h4>
            <div className="bracket__partido">
              <div className="bracket__equipo">{etiqueta(tercerLugar.equipos_id_local, tercerLugar, "Local")}</div>
              <div className="bracket__equipo">{etiqueta(tercerLugar.equipos_id_visitante, tercerLugar, "Visitante")}</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
