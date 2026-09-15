import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, apiErrorMessage } from "../../../api/client";
import { BracketView } from "./BracketView";

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
    // T10 (control-mesa-reactividad-playoffs-plan.md, Fase 3 §6): el
    // override persiste en Torneo.clasificados_por_grupo — invalidar la
    // query del torneo para que la próxima apertura del modal muestre el
    // valor recién guardado, no el viejo en cache.
    queryClient.invalidateQueries({ queryKey: ["torneo", torneoId] });
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
    mutationFn: async (clasificadosPorGrupo: number | null) => {
      const { data, error } = await api.POST("/api/v1/torneos/{torneo_id}/playoffs", {
        params: { path: { torneo_id: torneoId } },
        body: clasificadosPorGrupo != null ? { clasificados_por_grupo: clasificadosPorGrupo } : {},
      } as never);
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      invalidar();
      setModalPlayoffsAbierto(false);
    },
  });

  // T10: modal propio (no window.prompt(), Fase 2 — AI Slop Risk) para
  // preguntar cuántos equipos clasifican por grupo al momento de generar
  // playoffs. Solo se consulta el torneo (para pre-cargar el valor
  // actual) cuando el modal está por mostrarse — Grupos_Playoffs con
  // grupos terminados es la única rama que lo necesita.
  const [modalPlayoffsAbierto, setModalPlayoffsAbierto] = useState(false);
  const torneoQuery = useQuery({
    queryKey: ["torneo", torneoId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/torneos/{torneo_id}", {
        params: { path: { torneo_id: torneoId } },
      } as never);
      if (error) throw error;
      return data as { clasificados_por_grupo: number | null };
    },
    enabled: modalPlayoffsAbierto,
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
            <button type="button" disabled={playoffs.isPending} onClick={() => setModalPlayoffsAbierto(true)}>
              {playoffs.isPending ? "Generando..." : "Generar Playoffs"}
            </button>
          </>
        )}
        {modalPlayoffsAbierto && (
          <ModalClasificadosPorGrupo
            valorActual={torneoQuery.data?.clasificados_por_grupo ?? null}
            cargando={torneoQuery.isLoading}
            guardando={playoffs.isPending}
            onCancelar={() => setModalPlayoffsAbierto(false)}
            onConfirmar={(n) => playoffs.mutate(n)}
          />
        )}
      </div>
    );
  }

  return <BracketView torneoId={torneoId} />;
}

/** T10 (control-mesa-reactividad-playoffs-plan.md, Fase 3 §6) — "¿cuántos
 * equipos clasifican por grupo?" al momento de generar los playoffs.
 * Modal propio, mismo patrón `.modal-panel` que el resto de la app (ej.
 * el modal de reconciliación de ModalResultadoDirecto.tsx) — nunca un
 * `window.prompt()` nativo (Fase 2 del plan, AI Slop Risk): no puede
 * mostrar el valor actual como referencia, no valida antes de mandar, y
 * es fácil de cerrar por accidente en mobile. Pre-cargado con
 * `Torneo.clasificados_por_grupo` — confirmar sin tocarlo repite el
 * comportamiento de siempre; el valor elegido queda PERSISTIDO ahí
 * mismo (Gate Final T2 del plan). */
function ModalClasificadosPorGrupo(props: {
  valorActual: number | null;
  cargando: boolean;
  guardando: boolean;
  onCancelar: () => void;
  onConfirmar: (clasificadosPorGrupo: number) => void;
}) {
  const { valorActual, cargando, guardando, onCancelar, onConfirmar } = props;
  const [valor, setValor] = useState(() => String(valorActual ?? 2));

  // El valor real llega recién cuando `torneoQuery` resuelve (el modal se
  // abre antes de que la respuesta vuelva) — sin este efecto, el input se
  // quedaba en el default "2" aunque el torneo tuviera otro valor guardado.
  useEffect(() => {
    if (valorActual != null) setValor(String(valorActual));
  }, [valorActual]);

  const n = Number(valor);
  const esValido = valor !== "" && Number.isInteger(n) && n >= 1;

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="modal-clasificados-titulo">
      <div className="modal-panel">
        <h2 id="modal-clasificados-titulo">¿Cuántos equipos clasifican por grupo?</h2>
        <p className="muted">
          Se usan para armar los cruces de la Fase Eliminatoria (1° vs 2° del grupo siguiente, etc.). El valor queda
          guardado para la próxima vez.
        </p>
        <label>
          Clasificados por grupo
          <input
            type="number"
            min={1}
            value={valor}
            onChange={(e) => setValor(e.target.value)}
            disabled={cargando}
            autoFocus
          />
        </label>
        {!esValido && valor !== "" && <p className="error-text">Tiene que ser al menos 1.</p>}
        <div className="resource-form__actions">
          <button type="button" className="link-button" onClick={onCancelar} disabled={guardando}>
            Cancelar
          </button>
          <button type="button" disabled={!esValido || guardando || cargando} onClick={() => onConfirmar(n)}>
            {guardando ? "Generando..." : "Generar Playoffs"}
          </button>
        </div>
      </div>
    </div>
  );
}

