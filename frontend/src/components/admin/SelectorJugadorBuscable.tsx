import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../api/client";
import { useDebouncedValue } from "../../hooks/useDebouncedValue";

export interface JugadorBuscadoRow {
  id: number;
  nombre: string;
  cedula: string;
}

interface SelectorJugadorBuscableProps {
  /** Jugador ya elegido (controla si se muestra el input de búsqueda o el
   * resultado fijado) — `null` = sin elegir todavía. */
  elegido: JugadorBuscadoRow | null;
  onElegir: (jugador: JugadorBuscadoRow) => void;
  /** Vuelve al input de búsqueda — resetea lo que dependa del jugador
   * elegido (Traspasos: origen/dorsal sugerido, ver EC del plan). */
  onCambiar: () => void;
  label?: string;
}

/** Selector de jugador con búsqueda server-side + debounce — extraído de
 * `ModalBuscarAgregarJugador` (`DetalleEquipo.tsx`, Flujo 2 de
 * `gestion-avanzada-equipos-control-mesa-plan.md`) a un componente
 * compartido (D3 de `fixes-datos-traspasos-control-mesa-plan.md`),
 * generalizado para "elegir un jugador" en vez de "agregarlo a un equipo":
 * sin la parte de alerta de multimilitancia (no aplica a Traspasos, que
 * opera sobre un jugador que YA existe en algún lado del sistema) y sin
 * alta de jugador nuevo (mismo motivo — Flujo 2 del plan, Estados de
 * interacción). */
export function SelectorJugadorBuscable(props: SelectorJugadorBuscableProps) {
  const { elegido, onElegir, onCambiar, label } = props;
  const [texto, setTexto] = useState("");
  const textoDebounced = useDebouncedValue(texto, 300);

  const resultadosQuery = useQuery({
    queryKey: ["jugadores-buscar", textoDebounced],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/jugadores", {
        params: { query: { q: textoDebounced, limit: 20 } },
      });
      if (error) throw error;
      return data as JugadorBuscadoRow[];
    },
    enabled: textoDebounced.trim() !== "",
  });

  if (elegido) {
    return (
      <div className="selector-jugador-buscable">
        {label && <span className="selector-jugador-buscable__label">{label}</span>}
        <span className="selector-jugador-buscable__elegido">
          {elegido.nombre} — {elegido.cedula}
        </span>{" "}
        <button type="button" className="link-button" onClick={onCambiar}>
          Cambiar
        </button>
      </div>
    );
  }

  return (
    <div className="selector-jugador-buscable">
      <label>
        {label ?? "Buscar jugador"}
        <input
          placeholder="Buscar por nombre o cédula..."
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
        />
      </label>
      {textoDebounced.trim() !== "" && !resultadosQuery.isLoading && (resultadosQuery.data ?? []).length === 0 && (
        <p className="muted">Ningún jugador coincide con "{textoDebounced}".</p>
      )}
      {(resultadosQuery.data ?? []).map((j) => (
        <div key={j.id} className="modal-panel__equipo-fila">
          <span>
            {j.nombre} — {j.cedula}
          </span>
          <button type="button" onClick={() => onElegir(j)}>
            Elegir
          </button>
        </div>
      ))}
    </div>
  );
}
