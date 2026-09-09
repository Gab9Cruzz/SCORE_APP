import { useState } from "react";

/** Campo de fecha/hora inline (Flujo 4 del plan: "desde esta misma
 * vista", sin navegar a otra pantalla). Clic en la fecha abre un
 * `datetime-local`, PATCH al confirmar, refetch inmediato — si falla, el
 * campo vuelve al valor anterior + mensaje inline (no pierde el resto de
 * la fila). */
export function EditorFechaPartido(props: {
  partidoId: number;
  fechaActual: string;
  onGuardar: (fechaIso: string) => void;
  guardando: boolean;
}) {
  const [editando, setEditando] = useState(false);
  const [valor, setValor] = useState(() => props.fechaActual.slice(0, 16));

  if (!editando) {
    return (
      <button type="button" className="link-button" onClick={() => setEditando(true)}>
        📅 {new Date(props.fechaActual).toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short" })} ▾
      </button>
    );
  }

  return (
    <span className="editor-fecha-partido">
      <input
        type="datetime-local"
        aria-label="Fecha y hora del partido"
        value={valor}
        onChange={(e) => setValor(e.target.value)}
        autoFocus
      />
      <button
        type="button"
        disabled={props.guardando}
        onClick={() => {
          props.onGuardar(valor);
          setEditando(false);
        }}
      >
        ✓
      </button>
      <button type="button" className="link-button" onClick={() => setEditando(false)}>
        ✕
      </button>
    </span>
  );
}
