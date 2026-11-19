import { useEffect, useId, useRef, useState, type MouseEvent, type ReactNode } from "react";
import { useModalFocusTrap } from "../../hooks/useModalFocusTrap";
import { Button } from "./Button";

interface ModalProps {
  /** Título visible (`h2`); también da el nombre accesible. */
  titulo?: ReactNode;
  /** Nombre accesible cuando el título cambia según el paso y lo pinta el
   * contenido (Perfil de jugador, Siguiente fase). */
  etiqueta?: string;
  /** Alternativa a `etiqueta`: id del `h2` que pinta el contenido. */
  idTitulo?: string;
  onCerrar: () => void;
  /** Hay datos cargados que se perderían. Escape, el clic en el fondo y
   * `pedirCierre` piden confirmación en vez de cerrar. */
  sinGuardar?: boolean;
  /** Hay una operación en curso (guardando): no se puede cerrar. */
  cierreBloqueado?: boolean;
  /** Panel de 560px en vez de 480px (`.modal-panel--ancho`). */
  ancho?: boolean;
  /** Clase extra del panel. */
  className?: string;
  /** El contenido. Como función recibe `pedirCierre`, para que el botón
   * "Cancelar" del modal pase por la misma confirmación que Escape. */
  children: ReactNode | ((pedirCierre: () => void) => ReactNode);
}

/** Diálogo modal único (TASK-034, TASK-035). Ver DESIGN.md, "Modales".
 *
 * El foco lo maneja `useModalFocusTrap`: entra al abrir, no sale con Tab,
 * Escape cierra y al cerrar vuelve a quien lo abrió. Si hay datos sin
 * guardar, cerrar por Escape, por el fondo o por `pedirCierre` muestra
 * "Seguir editando / Descartar" dentro del mismo modal. */
export function Modal({
  titulo,
  etiqueta,
  idTitulo,
  onCerrar,
  sinGuardar = false,
  cierreBloqueado = false,
  ancho = false,
  className,
  children,
}: ModalProps) {
  const idPropio = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const seguirRef = useRef<HTMLButtonElement>(null);
  const [confirmandoDescarte, setConfirmandoDescarte] = useState(false);
  const mouseDownEnFondo = useRef(false);

  function pedirCierre() {
    if (cierreBloqueado) return;
    if (sinGuardar) setConfirmandoDescarte(true);
    else onCerrar();
  }

  useModalFocusTrap(panelRef, () => {
    if (confirmandoDescarte) setConfirmandoDescarte(false);
    else pedirCierre();
  });

  useEffect(() => {
    if (confirmandoDescarte) seguirRef.current?.focus();
  }, [confirmandoDescarte]);

  // Cerrar por el fondo solo si el clic empezó Y terminó en el fondo: una
  // selección de texto que arranca en un campo y se suelta afuera no cierra.
  function alBajarMouse(e: MouseEvent) {
    mouseDownEnFondo.current = e.target === e.currentTarget;
  }
  function alHacerClic(e: MouseEvent) {
    if (mouseDownEnFondo.current && e.target === e.currentTarget) pedirCierre();
    mouseDownEnFondo.current = false;
  }

  const clases = ["modal-panel"];
  if (ancho) clases.push("modal-panel--ancho");
  if (className) clases.push(className);

  const idDelTitulo = titulo != null ? idPropio : idTitulo;

  return (
    <div className="modal-overlay" onMouseDown={alBajarMouse} onClick={alHacerClic}>
      <div
        ref={panelRef}
        className={clases.join(" ")}
        role="dialog"
        aria-modal="true"
        aria-labelledby={idDelTitulo}
        aria-label={idDelTitulo ? undefined : etiqueta}
        tabIndex={-1}
      >
        {titulo != null && <h2 id={idPropio}>{titulo}</h2>}
        {confirmandoDescarte && (
          <div className="modal-panel__descartar" role="alert">
            <p>Hay datos sin guardar. Si cerrás, se pierden.</p>
            <div className="resource-form__actions">
              <Button ref={seguirRef} onClick={() => setConfirmandoDescarte(false)}>
                Seguir editando
              </Button>
              <Button variante="peligro" onClick={onCerrar}>
                Descartar y cerrar
              </Button>
            </div>
          </div>
        )}
        {typeof children === "function" ? children(pedirCierre) : children}
      </div>
    </div>
  );
}
