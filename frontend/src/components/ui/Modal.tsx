import { useEffect, useId, useRef, type ReactNode } from "react";

const FOCABLES =
  "button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], [tabindex]:not([tabindex='-1'])";

interface ModalProps {
  titulo: ReactNode;
  onCerrar: () => void;
  children: ReactNode;
  /** Panel de 560px en vez de 480px, para contenido con tablas o dos
   * columnas (`.modal-panel--ancho`). */
  ancho?: boolean;
}

/** Diálogo modal base (TASK-034), extraído del único modal que ya
 * gestionaba el foco (AsignarTorneosModal, T12):
 *
 * - el foco entra al abrir (primer control del panel),
 * - Tab y Shift+Tab no salen del panel,
 * - Escape llama a `onCerrar`,
 * - al cerrar, el foco vuelve al elemento que lo abrió.
 *
 * Hacer clic fuera NO cierra: un clic de más no puede tirar lo que se
 * llevaba cargado. Ver DESIGN.md, "Modales". */
export function Modal({ titulo, onCerrar, children, ancho = false }: ModalProps) {
  const idTitulo = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  // `onCerrar` suele ser una flecha nueva en cada render; guardarlo en un
  // ref evita que el efecto se vuelva a montar y robe el foco al usuario
  // cada vez que el componente padre se redibuja.
  const onCerrarRef = useRef(onCerrar);
  useEffect(() => {
    onCerrarRef.current = onCerrar;
  }, [onCerrar]);

  useEffect(() => {
    const elementoQueAbrio = document.activeElement;
    const panel = panelRef.current;
    const primero = panel?.querySelector<HTMLElement>(FOCABLES);
    (primero ?? panel)?.focus();

    function alPresionarTecla(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        onCerrarRef.current();
        return;
      }
      if (e.key !== "Tab" || !panelRef.current) return;
      const focables = panelRef.current.querySelectorAll<HTMLElement>(FOCABLES);
      if (focables.length === 0) {
        e.preventDefault();
        return;
      }
      const inicio = focables[0];
      const fin = focables[focables.length - 1];
      const activo = document.activeElement;
      const fuera = !panelRef.current.contains(activo);
      if (e.shiftKey && (activo === inicio || fuera)) {
        e.preventDefault();
        fin.focus();
      } else if (!e.shiftKey && (activo === fin || fuera)) {
        e.preventDefault();
        inicio.focus();
      }
    }

    document.addEventListener("keydown", alPresionarTecla);
    return () => {
      document.removeEventListener("keydown", alPresionarTecla);
      if (elementoQueAbrio instanceof HTMLElement) elementoQueAbrio.focus();
    };
  }, []);

  return (
    <div className="modal-overlay">
      <div
        ref={panelRef}
        className={ancho ? "modal-panel modal-panel--ancho" : "modal-panel"}
        role="dialog"
        aria-modal="true"
        aria-labelledby={idTitulo}
        tabIndex={-1}
      >
        <h2 id={idTitulo}>{titulo}</h2>
        {children}
      </div>
    </div>
  );
}
