import { useCallback, useEffect, useRef, useState } from "react";

/** Ancho a partir del cual se habilita el arrastre
 * (gestionar-partido-alineaciones-plan.md, decisión del gate final).
 *
 * Por debajo de esto la única vía de mover jugadores es el botón de tap, que es
 * de primera clase, no un repliegue. Tres razones, todas verificadas:
 *
 * 1. En 375px la zona destino casi nunca está en pantalla (~7 filas visibles
 *    contra ~900px de contenido con un plantel de 14), así que cada arrastre
 *    sería "llevar el dedo al borde y esperar el auto-scroll" contra un solo
 *    toque.
 * 2. El gesto no se puede cubrir con tests: jsdom no implementa `PointerEvent`
 *    ni `setPointerCapture`, y `getBoundingClientRect()` devuelve ceros, así
 *    que no hay forma de decidir sobre qué zona se soltó.
 * 3. El design doc del módulo fija "celular en cancha, 2-3 toques, sin tipear"
 *    como criterio de éxito.
 *
 * En ≥1000px el layout es de dos columnas, las dos zonas entran juntas en
 * pantalla y el mouse hace el gesto barato: ahí el arrastre suma.
 */
export const ANCHO_MINIMO_ARRASTRE = 1000;

export function useArrastreHabilitado(): boolean {
  const [habilitado, setHabilitado] = useState(
    () => typeof window !== "undefined" && window.innerWidth >= ANCHO_MINIMO_ARRASTRE,
  );

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia(`(min-width: ${ANCHO_MINIMO_ARRASTRE}px)`);
    const onChange = () => setHabilitado(mq.matches);
    onChange();
    // `addEventListener` sobre MediaQueryList no existe en Safari viejo; el
    // fallback a addListener mantiene la pantalla usable ahí.
    if (typeof mq.addEventListener === "function") {
      mq.addEventListener("change", onChange);
      return () => mq.removeEventListener("change", onChange);
    }
    mq.addListener(onChange);
    return () => mq.removeListener(onChange);
  }, []);

  return habilitado;
}

export interface EstadoArrastre<T extends string> {
  /** Qué se está arrastrando, o null si no hay gesto en curso. */
  itemId: number | null;
  /** Sobre qué zona está el puntero ahora mismo. */
  zonaActiva: T | null;
  /** Desplazamiento acumulado, para pintar el elemento levantado. */
  dx: number;
  dy: number;
}

/** Arrastre por Pointer Events, sin dependencias externas.
 *
 * Pointer Events cubren mouse y touch con una sola implementación (a diferencia
 * del drag & drop nativo de HTML5, que directamente no dispara en touch), pero
 * este hook solo se monta cuando `useArrastreHabilitado()` da true — ver
 * ANCHO_MINIMO_ARRASTRE.
 *
 * El componente decide a qué zona pertenece cada punto: este hook no sabe nada
 * de jugadores ni de equipos, solo reporta "qué se arrastra" y "sobre qué zona
 * está". Mantenerlo tonto es lo que permite testear la lógica de reubicación
 * como función pura, aparte del gesto.
 */
export function usePointerDrag<T extends string>(opciones: {
  /** Devuelve la zona bajo un punto de la pantalla, o null si no hay ninguna. */
  zonaEnPunto: (x: number, y: number) => T | null;
  /** Se llama al soltar sobre una zona válida distinta de la de origen. */
  onSoltar: (itemId: number, zona: T) => void;
}) {
  const { zonaEnPunto, onSoltar } = opciones;
  const [estado, setEstado] = useState<EstadoArrastre<T>>({
    itemId: null,
    zonaActiva: null,
    dx: 0,
    dy: 0,
  });
  // El origen vive en un ref y no en el estado: se lee en cada pointermove y no
  // debe disparar re-render por sí mismo.
  const origen = useRef<{ x: number; y: number } | null>(null);

  const cancelar = useCallback(() => {
    origen.current = null;
    setEstado({ itemId: null, zonaActiva: null, dx: 0, dy: 0 });
  }, []);

  const alPresionar = useCallback((itemId: number, e: React.PointerEvent) => {
    // Solo botón principal: un click derecho no arrastra.
    if (e.button !== 0) return;
    origen.current = { x: e.clientX, y: e.clientY };
    setEstado({ itemId, zonaActiva: null, dx: 0, dy: 0 });
    // setPointerCapture: el gesto sigue perteneciendo a este elemento aunque el
    // puntero salga de sus límites, que es lo normal al arrastrar entre zonas.
    (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
  }, []);

  const alMover = useCallback(
    (e: React.PointerEvent) => {
      if (estado.itemId == null || origen.current == null) return;
      const dx = e.clientX - origen.current.x;
      const dy = e.clientY - origen.current.y;
      const zona = zonaEnPunto(e.clientX, e.clientY);
      setEstado((prev) =>
        prev.zonaActiva === zona && prev.dx === dx && prev.dy === dy
          ? prev
          : { ...prev, zonaActiva: zona, dx, dy },
      );
    },
    [estado.itemId, zonaEnPunto],
  );

  const alSoltar = useCallback(
    (e: React.PointerEvent) => {
      const { itemId } = estado;
      const zona = itemId != null ? zonaEnPunto(e.clientX, e.clientY) : null;
      // Soltar fuera de toda zona cancela y la fila vuelve a su lugar: no se
      // adivina un destino.
      if (itemId != null && zona != null) onSoltar(itemId, zona);
      cancelar();
    },
    [estado, zonaEnPunto, onSoltar, cancelar],
  );

  return {
    estado,
    /** Props para la manija de arrastre de cada fila. */
    propsManija: (itemId: number) => ({
      onPointerDown: (e: React.PointerEvent) => alPresionar(itemId, e),
      onPointerMove: alMover,
      onPointerUp: alSoltar,
      // Una llamada entrante o una notificación cancelan el gesto: la fila
      // vuelve a su lugar en vez de quedar levantada para siempre.
      onPointerCancel: cancelar,
    }),
  };
}
