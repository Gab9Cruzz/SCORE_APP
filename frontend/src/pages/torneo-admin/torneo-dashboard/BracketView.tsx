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
  // Cierre de Fase Regular + Llaves + Playoffs (Fase D): en el partido de
  // VUELTA, apunta a su IDA — permite agrupar las dos piernas de una
  // misma llave en un solo nodo (Design review, Pass 1/7).
  partido_ida_id: number | null;
  estado: string;
}

const ETIQUETA_ESTADO_PIERNA: Record<string, string> = {
  Programado: "pendiente",
  "En curso": "en curso",
  Finalizado: "jugada",
  Cancelado: "cancelada",
};

/** Vista de bracket, solo lectura — Design sección E (motor-formatos-
 * plantillas-navegacion-plan.md). Agrupa por columnas (una por ronda,
 * orden inferido por cantidad de partidos: la ronda con más partidos es
 * la más temprana) en vez de dibujar las líneas de conexión del árbol —
 * "Ganador Partido N" nunca queda como un espacio en blanco sin
 * explicación, que es el requisito real del mockup.
 *
 * Cierre de Fase Regular + Llaves + Playoffs (Fase E3): cuando un partido
 * tiene `partido_ida_id`, se agrupa con su IDA en UN SOLO nodo — dos
 * filas de pierna, no dos cards sueltas (Design review, Pass 1/7: "one
 * node = one llave", una llave a dos piernas independientes duplicaría
 * la cantidad de cajas y el bracket dejaría de leerse como un bracket).
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

  const idaPorId = new Map(partidos.map((p) => [p.id, p]));
  // Un partido es IDA si otro (su vuelta) lo referencia — "se deriva", no
  // hay columna Es_Vuelta redundante (mismo criterio que el backend).
  const idsReferenciadosComoIda = new Set(partidos.filter((p) => p.partido_ida_id != null).map((p) => p.partido_ida_id as number));

  const tercerLugar = partidos.find((p) => p.ronda_nombre === "Tercer Lugar");
  // Nodos CANÓNICOS: cualquier partido que no sea la ida de otro — un
  // partido único, o la vuelta de una llave (que ya carga toda la
  // información de encadenamiento hacia la ronda siguiente).
  const canonicos = partidos.filter((p) => p.ronda_nombre !== "Tercer Lugar" && !idsReferenciadosComoIda.has(p.id));

  const porRonda = new Map<string, PartidoBracket[]>();
  for (const p of canonicos) {
    const nombre = p.ronda_nombre ?? "?";
    const arr = porRonda.get(nombre);
    if (arr) arr.push(p);
    else porRonda.set(nombre, [p]);
  }
  // Más partidos = ronda más temprana (Octavos > Cuartos > Semifinal > Final).
  const ordenRondas = [...porRonda.entries()].sort((a, b) => b[1].length - a[1].length).map(([nombre]) => nombre);
  const hayLlaves = canonicos.some((p) => p.partido_ida_id != null);

  // `partidoCanonico` es SIEMPRE la vuelta (o el partido único) — el que
  // carga Partido_Siguiente_ID/Slot_Siguiente reales. Para resolver el
  // placeholder de una pierna sin equipo, el slot a buscar es el de la
  // VUELTA (invertido cuando se pregunta por la IDA — ver `slotEnVuelta`).
  function etiqueta(equipoId: number | null, partidoCanonico: PartidoBracket, slotEnVuelta: "Local" | "Visitante"): string {
    if (equipoId != null) return nombreEquipo.get(equipoId) ?? `Equipo #${equipoId}`;
    const ganadorDe = partidos.find((p) => p.partido_siguiente_id === partidoCanonico.id && p.slot_siguiente === slotEnVuelta);
    if (ganadorDe) return `Ganador Partido ${ganadorDe.id}`;
    const perdedorDe = partidos.find(
      (p) => p.partido_perdedor_siguiente_id === partidoCanonico.id && p.slot_perdedor_siguiente === slotEnVuelta,
    );
    if (perdedorDe) return `Perdedor Semifinal ${perdedorDe.id}`;
    return "Por definir";
  }

  function renderPartido(p: PartidoBracket) {
    if (p.partido_ida_id == null) {
      return (
        <div key={p.id} className="bracket__partido">
          <div className="bracket__equipo">{etiqueta(p.equipos_id_local, p, "Local")}</div>
          <div className="bracket__equipo">{etiqueta(p.equipos_id_visitante, p, "Visitante")}</div>
        </div>
      );
    }
    // Llave a dos partidos — un nodo, dos filas de pierna (Design review:
    // "one node = one llave", nunca dos cards sueltas).
    const ida = idaPorId.get(p.partido_ida_id);
    return (
      <div key={p.id} className="bracket__partido bracket__partido--llave">
        <div className="bracket__pierna">
          <span className="bracket__pierna-fecha">Ida</span>
          <span>
            {ida ? etiqueta(ida.equipos_id_local, p, "Visitante") : "…"} vs{" "}
            {ida ? etiqueta(ida.equipos_id_visitante, p, "Local") : "…"}
            {ida && <span className="muted"> ({ETIQUETA_ESTADO_PIERNA[ida.estado] ?? ida.estado})</span>}
          </span>
        </div>
        <div className="bracket__pierna">
          <span className="bracket__pierna-fecha">Vuelta</span>
          <span>
            {etiqueta(p.equipos_id_local, p, "Local")} vs {etiqueta(p.equipos_id_visitante, p, "Visitante")}
            <span className="muted"> ({ETIQUETA_ESTADO_PIERNA[p.estado] ?? p.estado})</span>
          </span>
        </div>
        {ida && ida.estado !== "Programado" && ida.estado !== "En curso" && p.estado === "Programado" && (
          <p className="bracket__agregado">Ida jugada · Vuelta pendiente</p>
        )}
      </div>
    );
  }

  return (
    <div className="card motor-formatos-panel">
      <div className="bracket">
        {ordenRondas.map((nombreRonda) => (
          <div key={nombreRonda} className={`bracket__columna${hayLlaves ? " bracket__columna--llave" : ""}`}>
            <h4>{nombreRonda}</h4>
            {porRonda.get(nombreRonda)!.map(renderPartido)}
          </div>
        ))}
        {tercerLugar && (
          <div className={`bracket__columna bracket__columna--tercer-lugar${hayLlaves ? " bracket__columna--llave" : ""}`}>
            <h4>Tercer Lugar</h4>
            {renderPartido(tercerLugar)}
          </div>
        )}
      </div>
    </div>
  );
}
