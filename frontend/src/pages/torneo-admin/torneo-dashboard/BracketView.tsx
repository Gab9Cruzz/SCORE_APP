import { useQuery } from "@tanstack/react-query";
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

/** Vista de bracket, solo lectura — Design sección E (motor-formatos-
 * plantillas-navegacion-plan.md). Agrupa por columnas (una por ronda,
 * orden inferido por cantidad de partidos: la ronda con más partidos es
 * la más temprana) en vez de dibujar las líneas de conexión del árbol —
 * "Ganador Partido N" nunca queda como un espacio en blanco sin
 * explicación, que es el requisito real del mockup.
 *
 * Extraído de MotorFormatosPanel.tsx (control-mesa-reactividad-playoffs-
 * plan.md, Fase 3 §6): antes solo vivía en la pestaña Partidos del
 * torneo; ahora se reusa acá Y en EstadisticasDelTorneo.tsx (debajo de
 * la tabla de posiciones, donde el usuario lo espera) — un componente,
 * dos puntos de montaje, para no forkear la lógica de resolución de
 * "Ganador Partido N"/"Perdedor Semifinal N" (byes, TBD, Tercer Lugar). */
export function BracketView({ torneoId }: { torneoId: number }) {
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
