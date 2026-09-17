import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, apiErrorMessage } from "../../../api/client";
import { BracketView } from "./BracketView";
import { ModalSiguienteFase } from "./ModalSiguienteFase";

interface MotorFormatosPanelProps {
  torneoId: number;
  formato: "Liga" | "Eliminacion" | "Grupos_Playoffs";
  equiposInscritosCount: number;
}

type AccionDisponible = "cerrar_directo" | "generar_playoffs";
interface EstadoFase {
  fase_actual: { id: number; nombre: string; tipo: "Liga" | "Grupos" | "Eliminacion"; estado: string } | null;
  partidos_total: number;
  partidos_finalizados: number;
  partidos_cancelados: number;
  partidos_pendientes: number;
  fase_completa: boolean;
  acciones_disponibles: AccionDisponible[];
  torneo_cerrado: boolean;
}

const NOMBRE_FASE: Record<string, string> = {
  Liga: "Fase Regular",
  Grupos: "Fase de Grupos",
  Eliminacion: "Fase Eliminatoria",
};

/** C4/E1 (docs/plans/cierre-fase-regular-llaves-playoffs-plan.md):
 * reemplaza el escaneo client-side de `partidos` que tenía este panel por
 * `GET /estado-fase` — una sola fuente de la regla "¿la fase terminó y
 * qué se puede hacer ahora?" (antes duplicada acá y en
 * `generar_playoffs`). Devuelve `null` cuando el torneo está cerrado: el
 * podio vive UNA sola vez, en el header de `TorneoDashboard` (Design
 * review, Pass 1 — hard rejection: antes esto lo iba a duplicar). */
export function MotorFormatosPanel(props: MotorFormatosPanelProps) {
  const { torneoId, formato, equiposInscritosCount } = props;
  const queryClient = useQueryClient();
  const [modalAbierto, setModalAbierto] = useState(false);

  function invalidar() {
    queryClient.invalidateQueries({ queryKey: ["partidos"] });
    queryClient.invalidateQueries({ queryKey: ["bracket", torneoId] });
    queryClient.invalidateQueries({ queryKey: ["torneo", torneoId] });
    queryClient.invalidateQueries({ queryKey: ["torneos", torneoId] });
    queryClient.invalidateQueries({ queryKey: ["estado-fase", torneoId] });
  }

  const estadoQuery = useQuery({
    queryKey: ["estado-fase", torneoId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/torneos/{torneo_id}/estado-fase", {
        params: { path: { torneo_id: torneoId } },
      } as never);
      if (error) throw error;
      return data as EstadoFase;
    },
  });

  // Solo se pide cuando el modal está por abrirse — precarga
  // formato_eliminatoria/clasificados_por_grupo guardados (mismo criterio
  // que el viejo ModalClasificadosPorGrupo: confirmar sin tocar nada
  // repite el comportamiento de siempre).
  const torneoQuery = useQuery({
    queryKey: ["torneo", torneoId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/torneos/{torneo_id}", {
        params: { path: { torneo_id: torneoId } },
      } as never);
      if (error) throw error;
      return data as {
        clasificados_por_grupo: number | null;
        formato_eliminatoria: "Unico" | "Ida_Vuelta" | "Mixto";
        fecha_inicio: string;
      };
    },
    enabled: modalAbierto,
  });

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

  // E1 (Design review, Pass 2): la acción zona reserva su altura mientras
  // GET /estado-fase resuelve — convertir un render client-derivado
  // (instantáneo) en una lectura de red no debe mover el layout.
  if (estadoQuery.isLoading) {
    return (
      <div className="card motor-formatos-panel">
        <div className="estado-fase__skeleton" />
      </div>
    );
  }
  if (estadoQuery.isError || !estadoQuery.data) {
    return (
      <div className="card motor-formatos-panel">
        <p className="error-text">{apiErrorMessage(estadoQuery.error, "No se pudo cargar el estado de la fase.")}</p>
      </div>
    );
  }
  const estado = estadoQuery.data;
  if (estado.torneo_cerrado) return null;

  const conteoTresPartes = `${estado.partidos_finalizados} jugado(s) · ${estado.partidos_cancelados} cancelado(s) · ${estado.partidos_pendientes} pendiente(s)`;

  // D7: el label del botón se DERIVA de acciones_disponibles, nunca
  // hardcodeado — "Configurar Siguiente Fase" solo cuando hay 2 caminos.
  function labelBoton(): string {
    const { acciones_disponibles } = estado;
    if (acciones_disponibles.includes("cerrar_directo") && acciones_disponibles.includes("generar_playoffs")) {
      return "Configurar Siguiente Fase";
    }
    if (acciones_disponibles.includes("cerrar_directo")) return "Cerrar Torneo";
    return "Generar Playoffs";
  }

  // Sin fase (no debería pasar — todo torneo nace con una), o fase recién
  // creada sin nada generado todavía: la acción INICIAL depende del
  // Formato, GET /estado-fase no la modela (es sobre la fase EXISTENTE).
  if (estado.fase_actual == null || estado.partidos_total === 0) {
    if (formato === "Liga") {
      return (
        <div className="card motor-formatos-panel">
          <h3>Fase Regular</h3>
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
      return (
        <div className="card motor-formatos-panel">
          <h3>Fase Eliminatoria</h3>
          <p>Aún no se hizo el sorteo.</p>
          <p className="muted">{equiposInscritosCount} equipo(s) matriculado(s).</p>
          {sorteo.isError && <p className="error-text">{apiErrorMessage(sorteo.error)}</p>}
          <button type="button" disabled={sorteo.isPending || equiposInscritosCount < 2} onClick={() => sorteo.mutate()}>
            {sorteo.isPending ? "Sorteando..." : "Hacer Sorteo"}
          </button>
        </div>
      );
    }
    // Grupos_Playoffs
    return (
      <div className="card motor-formatos-panel">
        <h3>Fase de Grupos</h3>
        <p>Sorteo pendiente.</p>
        <p className="muted">{equiposInscritosCount} equipo(s) matriculado(s).</p>
        {sorteo.isError && <p className="error-text">{apiErrorMessage(sorteo.error)}</p>}
        <button type="button" disabled={sorteo.isPending || equiposInscritosCount < 2} onClick={() => sorteo.mutate()}>
          {sorteo.isPending ? "Sorteando..." : "Sortear Grupos"}
        </button>
      </div>
    );
  }

  const fase = estado.fase_actual;
  const hayAccion = estado.fase_completa && estado.acciones_disponibles.length > 0;

  return (
    <>
      <div className="card motor-formatos-panel">
        <h3>{NOMBRE_FASE[fase.tipo]}</h3>
        {/* Design review, Pass 2: reemplaza el viejo "N de M resueltos" —
            la regla real es Finalizado O Cancelado, y "30 de 30" a
            alguien con 2 cancelados lee como un bug del sistema. */}
        <p className="muted--cuerpo">{conteoTresPartes}</p>
        {hayAccion && (
          <button type="button" onClick={() => setModalAbierto(true)}>
            {labelBoton()}
          </button>
        )}
        {!hayAccion && fase.tipo !== "Eliminacion" && <p className="muted">La tabla de partidos está más abajo.</p>}
      </div>
      {fase.tipo === "Eliminacion" && <BracketView torneoId={torneoId} />}
      {modalAbierto && !torneoQuery.isLoading && (
        <ModalSiguienteFase
          torneoId={torneoId}
          formatoTorneo={formato}
          accionesDisponibles={estado.acciones_disponibles}
          formatoEliminatoriaActual={torneoQuery.data?.formato_eliminatoria ?? "Unico"}
          clasificadosPorGrupoActual={torneoQuery.data?.clasificados_por_grupo ?? null}
          fechaInicioTorneo={torneoQuery.data?.fecha_inicio ?? null}
          onClose={() => setModalAbierto(false)}
          onCerrado={() => setModalAbierto(false)}
          onPlayoffsGenerados={() => setModalAbierto(false)}
        />
      )}
    </>
  );
}
