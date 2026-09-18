import type { EstadoTarjeta } from "./eventos";

const ETIQUETA: Record<EstadoTarjeta, string> = {
  "1A": "1 amarilla",
  "2A": "2 amarillas",
  R: "Expulsado",
};

/** exp.1 (docs/plans/cierre-pendientes-todos-plan.md) — badge de estado de
 * tarjetas por jugador, en la fila de alineación en vivo y en los
 * candidatos `.tap-button` de ModalSustitucion. TEXTO ("1A"/"2A"/"R") Y
 * FORMA (rectángulo para amarilla — como una tarjeta real — vs. círculo
 * para roja) además de color: el color solo es la codificación que falla
 * para daltonismo bajo sol directo, el entorno real de uso en cancha. Se
 * distingue en escala de grises por el texto solo (la forma es refuerzo). */
export function BadgeTarjeta({ estado }: { estado: EstadoTarjeta }) {
  return (
    <span
      className={`badge-tarjeta badge-tarjeta--${estado === "R" ? "roja" : "amarilla"}`}
      aria-label={ETIQUETA[estado]}
      title={ETIQUETA[estado]}
    >
      {estado}
    </span>
  );
}
