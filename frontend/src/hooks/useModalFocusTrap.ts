import { useEffect, useRef, useState } from "react";

const SELECTOR_FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Modales abiertos, del más viejo al más nuevo. Solo el de adelante
 * atiende Tab y Escape: con un modal dentro de otro (la reconciliación de
 * goles de Resultado directo, el resumen de conflictos de Agregar equipo),
 * Escape cierra ese y no los dos. */
interface ModalAbierto {
  id: symbol;
  panel: HTMLElement | null;
}
const pila: ModalAbierto[] = [];
let overflowOriginal = "";

/** El de adelante: el último abierto entre los que no contienen a otro.
 * No alcanza con "el último": si los dos se montan juntos, React corre el
 * efecto del hijo antes que el del padre y el de afuera quedaría último. */
function modalDeAdelante(): symbol | undefined {
  const hojas = pila.filter((m) => !pila.some((otro) => otro !== m && m.panel?.contains(otro.panel ?? null)));
  return hojas[hojas.length - 1]?.id;
}

/** Gestión de foco de un modal (Design review, Pass 6; TASK-035):
 *
 * - al montar, el foco va al primer control del panel (o al panel),
 * - Tab y Shift+Tab no salen del panel,
 * - Escape llama a `alEscape`,
 * - la página de atrás no se desplaza mientras haya un modal abierto,
 * - al desmontar, el foco vuelve al elemento que lo abrió.
 *
 * `containerRef` apunta al panel, no al fondo. `alEscape` puede cambiar en
 * cada render: se lee de un ref, así el efecto se arma una sola vez y un
 * redibujo del padre no le mueve el foco al usuario. */
export function useModalFocusTrap(containerRef: React.RefObject<HTMLElement | null>, alEscape: () => void) {
  const alEscapeRef = useRef(alEscape);
  // Quién abrió el modal se lee en el primer render, no en el efecto: un
  // control con autoFocus dentro del modal (Resultado directo) toma el foco
  // al montarse, antes que corra el efecto, y "quien abrió" quedaría siendo
  // ese control, que desaparece al cerrar.
  const [disparador] = useState(() => (typeof document === "undefined" ? null : document.activeElement));
  useEffect(() => {
    alEscapeRef.current = alEscape;
  }, [alEscape]);

  useEffect(() => {
    const yo = Symbol("modal");
    pila.push({ id: yo, panel: containerRef.current });
    if (pila.length === 1) {
      overflowOriginal = document.body.style.overflow;
      document.body.style.overflow = "hidden";
    }

    const contenedor = containerRef.current;
    // Un control con autoFocus dentro del modal ya tiene el foco: respetarlo.
    if (contenedor && !contenedor.contains(document.activeElement)) {
      (contenedor.querySelector<HTMLElement>(SELECTOR_FOCUSABLE) ?? contenedor).focus();
    }

    function alPresionarTecla(e: KeyboardEvent) {
      if (modalDeAdelante() !== yo) return;
      if (e.key === "Escape") {
        e.preventDefault();
        alEscapeRef.current();
        return;
      }
      if (e.key !== "Tab" || !contenedor) return;
      const focuseables = Array.from(contenedor.querySelectorAll<HTMLElement>(SELECTOR_FOCUSABLE)).filter(
        (el) => !el.closest("[inert]"),
      );
      if (focuseables.length === 0) {
        e.preventDefault();
        contenedor.focus();
        return;
      }
      const primero = focuseables[0];
      const ultimo = focuseables[focuseables.length - 1];
      const activo = document.activeElement;
      const afuera = !contenedor.contains(activo);
      if (e.shiftKey && (activo === primero || activo === contenedor || afuera)) {
        e.preventDefault();
        ultimo.focus();
      } else if (!e.shiftKey && (activo === ultimo || afuera)) {
        e.preventDefault();
        primero.focus();
      }
    }

    document.addEventListener("keydown", alPresionarTecla);
    return () => {
      document.removeEventListener("keydown", alPresionarTecla);
      const i = pila.findIndex((m) => m.id === yo);
      if (i >= 0) pila.splice(i, 1);
      if (pila.length === 0) document.body.style.overflow = overflowOriginal;
      if (disparador instanceof HTMLElement && disparador.isConnected) disparador.focus();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- se arma una sola vez al montar el modal.
  }, []);
}
