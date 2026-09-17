import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import type { Equipo as EquipoRow } from "../../../api/types";
import { api, apiErrorMessage } from "../../../api/client";
import { useResourceCrud } from "../../../hooks/useResourceCrud";
import { useNombrePorIdConFaltantes } from "../../../hooks/useFetchFaltantes";
import { badgePenales } from "../../../lib/desempate";

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
  fecha_partido: string;
  ganador_corrido_id: number | null;
  es_walkover: boolean;
  // Desempate de eliminatoria: tiempo extra y penales (D-D9) — viven en
  // el partido de VUELTA (o único); una IDA nunca los tiene.
  metodo_desempate?: "Tiempo_Extra" | "Penales" | "Manual" | null;
  hubo_tiempo_extra?: boolean;
  penales_local?: number | null;
  penales_visitante?: number | null;
}

interface ResultadoRow {
  partido_id: number;
  goles_local: number;
  goles_visitante: number;
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
 * Cierre de Fase Regular + Llaves + Playoffs (Fase E3/D11): cuando un
 * partido tiene `partido_ida_id`, se agrupa con su IDA en UN SOLO nodo —
 * dos filas de pierna con fecha y marcador, más el agregado en su propia
 * fila (Design review, Pass 1/7: "one node = one llave", una llave a dos
 * piernas independientes duplicaría la cantidad de cajas). El marcador
 * sale de `GET /estadisticas/torneos/{id}/resultados` (la misma vista que
 * ya usa el portal público) — el bracket en sí (`GET /bracket`) no trae
 * goles a propósito, para poder mostrar shells sin equipos todavía.
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
  // D11: solo hace falta para pintar marcador/agregado — un fallo acá no
  // debe tumbar el bracket entero (sigue mostrando nombres y fechas sin
  // marcador, degradado con gracia). `enabled` atado a que YA haya
  // partidos: sin esto se pedía igual con un bracket vacío/todavía
  // cargando.
  const hayPartidosEnBracket = (query.data?.length ?? 0) > 0;
  const resultadosQuery = useQuery({
    queryKey: ["resultados", torneoId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/estadisticas/torneos/{torneo_id}/resultados", {
        params: { path: { torneo_id: torneoId } },
      } as never);
      if (error) throw error;
      return data as ResultadoRow[];
    },
    enabled: hayPartidosEnBracket,
  });
  const golesPorPartido = useMemo(
    () => new Map((resultadosQuery.data ?? []).map((r) => [r.partido_id, { local: r.goles_local, visitante: r.goles_visitante }])),
    [resultadosQuery.data],
  );

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

  function formatearFecha(iso: string): string {
    return new Date(iso).toLocaleDateString("es-AR", { day: "2-digit", month: "short" });
  }

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

  // D11 + "Corrido (non-goal) disciplines get their own aggregate copy"
  // (Design review): sin marcador de goles en `golesPorPartido`, se cae a
  // `ganador_corrido_id` si está — y si ninguno de los dos hay todavía,
  // no se muestra nada (partido sin jugar).
  function marcadorDePierna(p: PartidoBracket): string | null {
    const goles = golesPorPartido.get(p.id);
    if (goles) return `${goles.local}-${goles.visitante}`;
    if (p.ganador_corrido_id != null) {
      return `Ganador: ${nombreEquipo.get(p.ganador_corrido_id) ?? `#${p.ganador_corrido_id}`}`;
    }
    return null;
  }

  // Agregado de una llave: suma de goles invirtiendo local/visitante de la
  // ida (misma cuenta que fn_resolver_llave, 06_triggers.sql) — solo si
  // AMBAS piernas tienen marcador de goles. Para Corrido no hay "global"
  // numérico (se decide por victorias de pierna, no goles): se arma una
  // leyenda de texto en su lugar.
  function agregadoDeLlave(ida: PartidoBracket, vuelta: PartidoBracket): string | null {
    const golesIda = golesPorPartido.get(ida.id);
    const golesVuelta = golesPorPartido.get(vuelta.id);
    if (golesIda && golesVuelta) {
      const globalLocal = golesVuelta.local + golesIda.visitante;
      const globalVisitante = golesVuelta.visitante + golesIda.local;
      return `Global ${globalLocal}-${globalVisitante}`;
    }
    if (ida.ganador_corrido_id != null && vuelta.ganador_corrido_id != null) {
      const ganadorIda = nombreEquipo.get(ida.ganador_corrido_id) ?? `#${ida.ganador_corrido_id}`;
      const ganadorVuelta = nombreEquipo.get(vuelta.ganador_corrido_id) ?? `#${vuelta.ganador_corrido_id}`;
      return ganadorIda === ganadorVuelta ? `Definido: ${ganadorIda}` : `Ida: ${ganadorIda} · Vuelta: ${ganadorVuelta}`;
    }
    return null;
  }

  // D3 (Design review, Pass 7): variante visual de walkover — mismo badge
  // que ya usa PartidosDelTorneoPage ("W.O."), para que un 3-0 por
  // ausencia no se confunda con un 3-0 jugado.
  function badgeWalkover(p: PartidoBracket) {
    if (!p.es_walkover) return null;
    return (
      <span className="badge badge--archivado" title="Cerrado por walkover (ausencia)">
        {" "}
        W.O.
      </span>
    );
  }

  // Desempate de eliminatoria: tiempo extra y penales (D-D9) — badge
  // compacto y NO envolvente ("pen. 4-2"), separado del marcador/global
  // que ya se muestra aparte. `aria-label` completo (D-D15): el badge
  // visual abrevia, el lector de pantalla no.
  function badgeDesempate(p: PartidoBracket) {
    const texto = badgePenales({
      golesLocal: 0,
      golesVisitante: 0,
      metodoDesempate: p.metodo_desempate,
      huboTiempoExtra: p.hubo_tiempo_extra,
      penalesLocal: p.penales_local,
      penalesVisitante: p.penales_visitante,
    });
    if (!texto) return null;
    return (
      <span
        className="badge badge--desempate"
        aria-label={`Penales ${p.penales_local} a ${p.penales_visitante}`}
      >
        {" "}
        {texto}
      </span>
    );
  }

  function renderPartido(p: PartidoBracket) {
    const marcador = marcadorDePierna(p);
    if (p.partido_ida_id == null) {
      return (
        <div key={p.id} className="bracket__partido">
          <p className="fila-partido__hora">{formatearFecha(p.fecha_partido)}</p>
          <div className="bracket__equipo">{etiqueta(p.equipos_id_local, p, "Local")}</div>
          <div className="bracket__equipo">{etiqueta(p.equipos_id_visitante, p, "Visitante")}</div>
          {marcador && (
            <p className="muted--cuerpo">
              {marcador}
              {p.hubo_tiempo_extra && " a.e.t."}
              {badgeDesempate(p)}
              {badgeWalkover(p)}
            </p>
          )}
        </div>
      );
    }
    // Llave a dos partidos — un nodo, dos filas de pierna (Design review:
    // "one node = one llave", nunca dos cards sueltas).
    const ida = idaPorId.get(p.partido_ida_id);
    const agregado = ida ? agregadoDeLlave(ida, p) : null;
    return (
      <div key={p.id} className="bracket__partido bracket__partido--llave">
        <div className="bracket__pierna">
          <span className="bracket__pierna-fecha">{ida ? formatearFecha(ida.fecha_partido) : ""} · Ida</span>
          <span>
            {ida ? etiqueta(ida.equipos_id_local, p, "Visitante") : "…"} vs{" "}
            {ida ? etiqueta(ida.equipos_id_visitante, p, "Local") : "…"}
            {ida && marcadorDePierna(ida) && <> · {marcadorDePierna(ida)}</>}
            {ida && badgeWalkover(ida)}
            {ida && <span className="muted"> ({ETIQUETA_ESTADO_PIERNA[ida.estado] ?? ida.estado})</span>}
          </span>
        </div>
        <div className="bracket__pierna">
          <span className="bracket__pierna-fecha">{formatearFecha(p.fecha_partido)} · Vuelta</span>
          <span>
            {etiqueta(p.equipos_id_local, p, "Local")} vs {etiqueta(p.equipos_id_visitante, p, "Visitante")}
            {marcador && <> · {marcador}</>}
            {badgeWalkover(p)}
            <span className="muted"> ({ETIQUETA_ESTADO_PIERNA[p.estado] ?? p.estado})</span>
          </span>
        </div>
        {agregado && (
          <p className="bracket__agregado">
            {agregado}
            {p.hubo_tiempo_extra && " a.e.t."}
            {badgeDesempate(p)}
          </p>
        )}
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
