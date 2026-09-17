import { useEffect, useRef } from "react";

const SELECTOR_FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Cierre de Fase Regular + Llaves + Playoffs (Design review, Pass 6):
 * gestión de foco para un modal — trap de Tab dentro del panel, Escape
 * cierra, y el foco vuelve al elemento que lo abrió. Gap verificado:
 * `ModalClasificadosPorGrupo` seteaba `aria-modal="true"` sin ninguna de
 * las tres — se agrega ACÁ, en un hook propio, para que cualquier otro
 * `.modal-panel` de la app lo pueda adoptar sin reescribir la lógica.
 *
 * `containerRef` apunta al panel (no al overlay completo) — ahí es donde
 * se busca el primer elemento focuseable y se traba el Tab. */
export function useModalFocusTrap(containerRef: React.RefObject<HTMLElement | null>, onClose: () => void) {
  const disparadorRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    disparadorRef.current = document.activeElement as HTMLElement | null;
    const contenedor = containerRef.current;
    const primero = contenedor?.querySelector<HTMLElement>(SELECTOR_FOCUSABLE);
    primero?.focus();

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key !== "Tab" || !contenedor) return;
      const focuseables = Array.from(contenedor.querySelectorAll<HTMLElement>(SELECTOR_FOCUSABLE));
      if (focuseables.length === 0) return;
      const primeroF = focuseables[0];
      const ultimoF = focuseables[focuseables.length - 1];
      if (e.shiftKey && document.activeElement === primeroF) {
        e.preventDefault();
        ultimoF.focus();
      } else if (!e.shiftKey && document.activeElement === ultimoF) {
        e.preventDefault();
        primeroF.focus();
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      disparadorRef.current?.focus();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- se arma una sola vez al montar el modal.
  }, []);
}
