import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { api, apiErrorMessage } from "../../api/client";
import { TIPOS, TIPO_ICONO, type PlantillaJugador, type TipoEvento } from "../../components/eventos";

/** "Cargar resultado directo" (control-mesa-centralizacion-fixture-plan.md,
 * Sección 5, Alternativa A) — cierra un partido 'Programado' de una sola
 * vez (goles/tarjetas/cambios + inicio y fin), sin pasar por el cronómetro
 * en vivo ni exponer `MesaPanel`. Carga TODOS los eventos en memoria y
 * los manda juntos a `POST /resultado-directo` — el backend orquesta
 * Inicio_Partido + N eventos + Fin_Partido en una sola transacción
 * atómica (PartidoService.registrar_resultado_directo). */
export function ModalResultadoDirecto(props: {
  partido: { id: number; equipos_id_local: number; equipos_id_visitante: number };
  nombreEquipo: Map<number, string>;
  onClose: () => void;
  onGuardado: () => void;
}) {
  const { partido, nombreEquipo, onClose, onGuardado } = props;
  const nombreLocal = nombreEquipo.get(partido.equipos_id_local) ?? `Equipo #${partido.equipos_id_local}`;
  const nombreVisitante = nombreEquipo.get(partido.equipos_id_visitante) ?? `Equipo #${partido.equipos_id_visitante}`;

  // tipo_cronometro decide si hace falta pedir un ganador manual (torneos
  // 'Corrido', sin marcador de goles) — mismo endpoint que ya usa el
  // cronómetro en vivo, no hace falta uno nuevo.
  const cronometroQuery = useQuery({
    queryKey: ["cronometro", partido.id],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/partidos/{partido_id}/cronometro", {
        params: { path: { partido_id: partido.id } },
      });
      if (error) throw error;
      return data;
    },
  });
  const esCorrido = cronometroQuery.data?.tipo_cronometro === "Corrido";

  const plantillaLocalQuery = useQuery({
    queryKey: ["plantilla", partido.equipos_id_local],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/estadisticas/equipos/{equipo_id}/plantilla", {
        params: { path: { equipo_id: partido.equipos_id_local } },
      });
      if (error) throw error;
      return data;
    },
  });
  const plantillaVisitanteQuery = useQuery({
    queryKey: ["plantilla", partido.equipos_id_visitante],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/estadisticas/equipos/{equipo_id}/plantilla", {
        params: { path: { equipo_id: partido.equipos_id_visitante } },
      });
      if (error) throw error;
      return data;
    },
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
  const eventoIdPorNombre = useMemo(
    () => new Map((eventosCatalogoQuery.data ?? []).map((e) => [e.nombre, e.id])),
    [eventosCatalogoQuery.data],
  );

  const [eventos, setEventos] = useState<
    { tipo: TipoEvento; equipoId: number; jugadorId: number; jugadorIdEntra: number | null; minuto: number }[]
  >([]);
  const [tipo, setTipo] = useState<TipoEvento>("Gol");
  const [equipoId, setEquipoId] = useState<number>(partido.equipos_id_local);
  const [jugadorId, setJugadorId] = useState<number | null>(null);
  const [jugadorIdEntra, setJugadorIdEntra] = useState<number | null>(null);
  const [minuto, setMinuto] = useState("");
  const [ganadorCorridoId, setGanadorCorridoId] = useState<number | null>(null);

  const plantillaEquipo: PlantillaJugador[] =
    equipoId === partido.equipos_id_local ? (plantillaLocalQuery.data ?? []) : (plantillaVisitanteQuery.data ?? []);

  function agregarEvento() {
    if (jugadorId === null || minuto === "") return;
    if (tipo === "Cambio" && jugadorIdEntra === null) return;
    setEventos((prev) => [
      ...prev,
      { tipo, equipoId, jugadorId, jugadorIdEntra: tipo === "Cambio" ? jugadorIdEntra : null, minuto: Number(minuto) },
    ]);
    setJugadorId(null);
    setJugadorIdEntra(null);
    setMinuto("");
  }

  const mutation = useMutation({
    mutationFn: async () => {
      const body = {
        eventos: eventos.map((e) => ({
          jugador_id: e.jugadorId,
          equipo_id: e.equipoId,
          eventos_id: eventoIdPorNombre.get(e.tipo) as number,
          jugador_id_entra: e.jugadorIdEntra,
          minuto: e.minuto,
        })),
        ganador_corrido_id: esCorrido ? ganadorCorridoId : undefined,
      };
      const { data, error } = await api.POST("/api/v1/partidos/{partido_id}/resultado-directo", {
        params: { path: { partido_id: partido.id } },
        body,
      } as never);
      if (error) throw error;
      return data;
    },
    onSuccess: onGuardado,
  });

  const puedeGuardar = !esCorrido || ganadorCorridoId !== null;

  return (
    <div
      className="modal-overlay"
      role="dialog"
      aria-label={`Cargar resultado directo — ${nombreLocal} vs ${nombreVisitante}`}
    >
      <div className="modal-panel">
        <h2>Cargar resultado directo</h2>
        <p className="muted">
          {nombreLocal} vs {nombreVisitante} — cierra el partido sin usar el cronómetro en vivo.
        </p>

        <div className="resource-form">
          <label>
            Tipo
            <select
              value={tipo}
              onChange={(e) => {
                setTipo(e.target.value as TipoEvento);
                setJugadorId(null);
                setJugadorIdEntra(null);
              }}
            >
              {TIPOS.map((t) => (
                <option key={t} value={t}>
                  {TIPO_ICONO[t]} {t}
                </option>
              ))}
            </select>
          </label>
          <label>
            Equipo
            <select
              value={equipoId}
              onChange={(e) => {
                setEquipoId(Number(e.target.value));
                setJugadorId(null);
                setJugadorIdEntra(null);
              }}
            >
              <option value={partido.equipos_id_local}>{nombreLocal}</option>
              <option value={partido.equipos_id_visitante}>{nombreVisitante}</option>
            </select>
          </label>
          <label>
            {tipo === "Cambio" ? "Sale" : "Jugador"}
            <select value={jugadorId ?? ""} onChange={(e) => setJugadorId(e.target.value ? Number(e.target.value) : null)}>
              <option value="">Elegir...</option>
              {plantillaEquipo.map((j) => (
                <option key={j.jugador_id} value={j.jugador_id}>
                  {j.dorsal ? `#${j.dorsal} ` : ""}
                  {j.jugador}
                </option>
              ))}
            </select>
          </label>
          {tipo === "Cambio" && (
            <label>
              Entra
              <select
                value={jugadorIdEntra ?? ""}
                onChange={(e) => setJugadorIdEntra(e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">Elegir...</option>
                {plantillaEquipo
                  .filter((j) => j.jugador_id !== jugadorId)
                  .map((j) => (
                    <option key={j.jugador_id} value={j.jugador_id}>
                      {j.dorsal ? `#${j.dorsal} ` : ""}
                      {j.jugador}
                    </option>
                  ))}
              </select>
            </label>
          )}
          <label>
            Minuto
            <input type="number" min={0} max={130} value={minuto} onChange={(e) => setMinuto(e.target.value)} />
          </label>
          <div className="resource-form__actions">
            <button
              type="button"
              onClick={agregarEvento}
              disabled={jugadorId === null || minuto === "" || (tipo === "Cambio" && jugadorIdEntra === null)}
            >
              + Agregar evento
            </button>
          </div>
        </div>

        {eventos.length === 0 && <p className="muted">Sin eventos cargados todavía — 0-0 también es un resultado válido.</p>}
        {eventos.length > 0 && (
          <ul className="eventos-timeline">
            {eventos.map((e, i) => (
              <li key={i}>
                <span className="eventos-timeline__minuto">{e.minuto}'</span>
                <span>{TIPO_ICONO[e.tipo]}</span>
                <span>{nombreEquipo.get(e.equipoId) ?? `#${e.equipoId}`}</span>
                <button type="button" className="link-button" onClick={() => setEventos((prev) => prev.filter((_, idx) => idx !== i))}>
                  Quitar
                </button>
              </li>
            ))}
          </ul>
        )}

        {esCorrido && (
          <label>
            Ganador
            <select
              value={ganadorCorridoId ?? ""}
              onChange={(e) => setGanadorCorridoId(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">Elegir...</option>
              <option value={partido.equipos_id_local}>{nombreLocal}</option>
              <option value={partido.equipos_id_visitante}>{nombreVisitante}</option>
            </select>
          </label>
        )}

        {mutation.isError && <p className="error-text">{apiErrorMessage(mutation.error)}</p>}
        <div className="resource-form__actions">
          <button type="button" className="link-button" onClick={onClose}>
            Cancelar
          </button>
          <button type="button" disabled={!puedeGuardar || mutation.isPending} onClick={() => mutation.mutate()}>
            {mutation.isPending ? "Guardando..." : "Guardar resultado"}
          </button>
        </div>
      </div>
    </div>
  );
}
