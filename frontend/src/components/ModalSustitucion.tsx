import type { PlantillaJugador } from "./eventos";

/** Modal contextual de sustitución (modo-vivo-sustituciones-cierre-plan.md,
 * Área 3, T4) — se abre al tocar un titular en la alineación en vivo de
 * `MesaPanel`, en vez de que el operador arme el Cambio a mano en el
 * formulario genérico de `CargaEvento` (que sigue existiendo como camino
 * alternativo, sin duplicarse: acá solo se ELIGE quién entra, el POST del
 * evento y sus reglas de negocio — tope de cambios, no-retorno — son
 * 100% autoritativas del backend, `EventoPartidoService._validar_reglas_cambio`;
 * este modal no reimplementa esa validación, solo ofrece una lista
 * razonable de candidatos).
 *
 * Cerrar sin elegir reemplazo no persiste nada (Sección 4 del plan,
 * "Cerrar el modal sin elegir reemplazo" — CRITICAL si no: evento fantasma
 * sin 'entra') — el caller solo llama a `onConfirmar` cuando el operador
 * ya eligió, nunca al cerrar. */
export function ModalSustitucion(props: {
  jugadorSale: PlantillaJugador;
  elegibles: PlantillaJugador[];
  onConfirmar: (entraId: number) => void;
  onCancelar: () => void;
  confirmando: boolean;
  error: string | null;
}) {
  const { jugadorSale, elegibles, onConfirmar, onCancelar, confirmando, error } = props;

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="modal-sustitucion-titulo">
      <div className="modal-panel">
        <h2 id="modal-sustitucion-titulo">
          Sale {jugadorSale.dorsal != null ? `#${jugadorSale.dorsal} ` : ""}
          {jugadorSale.jugador} — ¿Por quién ingresa?
        </h2>

        {error && <p className="error-text">{error}</p>}

        {elegibles.length === 0 ? (
          // Pass 2 (Design Fase 2): estado vacío que NO es un callejón sin
          // salida — el operador solo puede cancelar acá (la alta tardía de
          // un suplente vive en "Gestionar Partido › Convocatoria", fuera
          // del alcance directo de este panel de eventos).
          <p className="muted">
            No hay suplentes disponibles para entrar (todos ya entraron o fueron expulsados). Sumá un
            suplente desde la convocatoria del partido si llegó alguien tarde.
          </p>
        ) : (
          <div className="tap-grid">
            {elegibles.map((j) => (
              <button
                key={j.jugador_id}
                type="button"
                className="tap-button"
                disabled={confirmando}
                onClick={() => onConfirmar(j.jugador_id)}
              >
                {j.dorsal != null ? `#${j.dorsal} ` : ""}
                {j.jugador}
              </button>
            ))}
          </div>
        )}

        <div className="confirmar-evento__acciones">
          <button type="button" className="link-button" onClick={onCancelar} disabled={confirmando}>
            Cancelar
          </button>
        </div>
      </div>
    </div>
  );
}
