import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, apiErrorMessage } from "../api/client";

interface PlantillaJugador {
  jugador_id: number;
  jugador: string;
  equipo_id: number;
  equipo: string;
  dorsal: number | null;
  jugador_perfil_id: number;
}
interface ConvocadoRow {
  id: number;
  partido_id: number;
  jugador_perfil_id: number;
  titular: boolean;
}

/** Titular/suplente/convocados a UN partido puntual (3B-2,
 * docs/plans/cierre-backlog-todos-plan.md) — tabla delgada, NO reemplaza
 * la plantilla vigente del roster: solo dice quién de esa plantilla fue
 * convocado a ESTE partido. Sin convocatoria guardada, `MesaPanel` sigue
 * ofreciendo toda la plantilla como candidata (comportamiento de
 * siempre) — esto es estrictamente opt-in, un torneo que nunca la usa no
 * nota el cambio. */
export function Convocatoria(props: {
  partidoId: number;
  nombreLocal: string;
  nombreVisitante: string;
  plantillaLocal: PlantillaJugador[];
  plantillaVisitante: PlantillaJugador[];
}) {
  const { partidoId, nombreLocal, nombreVisitante, plantillaLocal, plantillaVisitante } = props;
  const queryClient = useQueryClient();
  const [abierto, setAbierto] = useState(false);
  // jugador_perfil_id -> titular. Ausente de este Map = no convocado.
  const [seleccion, setSeleccion] = useState<Map<number, boolean> | null>(null);

  const convocadosQuery = useQuery({
    queryKey: ["convocados", partidoId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/partidos/{partido_id}/convocados", {
        params: { path: { partido_id: partidoId } },
      });
      if (error) throw error;
      return data as ConvocadoRow[];
    },
  });

  const guardar = useMutation({
    mutationFn: async (convocados: { jugador_perfil_id: number; titular: boolean }[]) => {
      const { data, error } = await api.PUT("/api/v1/partidos/{partido_id}/convocados", {
        params: { path: { partido_id: partidoId } },
        body: { convocados },
      });
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["convocados", partidoId] });
      setSeleccion(null);
      setAbierto(false);
    },
  });

  const guardados = convocadosQuery.data ?? [];

  /** La selección en edición si el admin ya tocó algo, si no la que ya
   * está guardada — evita que abrir el panel arranque siempre "vacío". */
  const actual =
    seleccion ?? new Map(guardados.map((c) => [c.jugador_perfil_id, c.titular]));

  function alternar(jugadorPerfilId: number) {
    const copia = new Map(actual);
    if (copia.has(jugadorPerfilId)) copia.delete(jugadorPerfilId);
    else copia.set(jugadorPerfilId, false);
    setSeleccion(copia);
  }
  function marcarTitular(jugadorPerfilId: number, titular: boolean) {
    const copia = new Map(actual);
    copia.set(jugadorPerfilId, titular);
    setSeleccion(copia);
  }

  if (!abierto) {
    return (
      <section className="card">
        <div className="page__header">
          <h2>Convocados</h2>
          <button type="button" className="link-button" onClick={() => setAbierto(true)}>
            {guardados.length > 0 ? "Editar convocatoria" : "Definir convocatoria"}
          </button>
        </div>
        <p className="muted">
          {guardados.length > 0
            ? `${guardados.length} convocados (${guardados.filter((c) => c.titular).length} titulares) — el resto de la plantilla no aparece como candidato en Cargar evento.`
            : "Sin convocatoria — toda la plantilla vigente es candidata en Cargar evento."}
        </p>
      </section>
    );
  }

  return (
    <section className="card">
      <h2>Convocados</h2>
      {guardar.isError && <p className="error-text">{apiErrorMessage(guardar.error)}</p>}
      <div className="convocatoria-equipos">
        <EquipoConvocatoria nombre={nombreLocal} plantilla={plantillaLocal} seleccion={actual} onAlternar={alternar} onTitular={marcarTitular} />
        <EquipoConvocatoria nombre={nombreVisitante} plantilla={plantillaVisitante} seleccion={actual} onAlternar={alternar} onTitular={marcarTitular} />
      </div>
      <div className="confirmar-evento__acciones">
        <button
          type="button"
          className="link-button"
          onClick={() => {
            setSeleccion(null);
            setAbierto(false);
          }}
        >
          Cancelar
        </button>
        <button
          type="button"
          disabled={guardar.isPending}
          onClick={() =>
            guardar.mutate(
              [...actual.entries()].map(([jugador_perfil_id, titular]) => ({ jugador_perfil_id, titular })),
            )
          }
        >
          {guardar.isPending ? "Guardando..." : "Guardar convocatoria"}
        </button>
        {guardados.length > 0 && (
          <button type="button" className="link-button" disabled={guardar.isPending} onClick={() => guardar.mutate([])}>
            Sacar convocatoria (volver a toda la plantilla)
          </button>
        )}
      </div>
    </section>
  );
}

function EquipoConvocatoria(props: {
  nombre: string;
  plantilla: PlantillaJugador[];
  seleccion: Map<number, boolean>;
  onAlternar: (jugadorPerfilId: number) => void;
  onTitular: (jugadorPerfilId: number, titular: boolean) => void;
}) {
  const { nombre, plantilla, seleccion, onAlternar, onTitular } = props;
  return (
    <div className="convocatoria-equipo">
      <h3>{nombre}</h3>
      {plantilla.length === 0 && <p className="muted">Sin plantilla cargada.</p>}
      <ul className="convocatoria-lista">
        {plantilla.map((j) => {
          const convocado = seleccion.has(j.jugador_perfil_id);
          const titular = seleccion.get(j.jugador_perfil_id) ?? false;
          return (
            <li key={j.jugador_perfil_id}>
              <label>
                <input type="checkbox" checked={convocado} onChange={() => onAlternar(j.jugador_perfil_id)} />
                {j.dorsal ? `#${j.dorsal} ` : ""}
                {j.jugador}
              </label>
              {convocado && (
                <label className="convocatoria-titular">
                  <input
                    type="checkbox"
                    checked={titular}
                    onChange={(e) => onTitular(j.jugador_perfil_id, e.target.checked)}
                  />
                  Titular
                </label>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
