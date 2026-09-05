import { useEffect, useState } from "react";

/** Debounce mínimo sin librería extra — extraído de
 * `useDebouncedEffect` (`DetalleEquipo.tsx`, Flujo 2 de
 * `gestion-avanzada-equipos-control-mesa-plan.md`) a un hook compartido
 * (D3 de `fixes-datos-traspasos-control-mesa-plan.md`) para que Traspasos
 * pueda reusar el mismo criterio de "esperar 300ms después de que el
 * usuario deja de tipear" sin duplicar la función local. Devuelve el
 * valor debounced directo en vez de pedir un setter externo — más simple
 * de usar en un componente nuevo. */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  return debounced;
}
