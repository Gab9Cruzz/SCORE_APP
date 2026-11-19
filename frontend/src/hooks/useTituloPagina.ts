import { useEffect } from "react";

const SITIO = "Score-App";

/** Título de la pestaña del navegador (TASK-037, WCAG 2.4.2): "Usuarios ·
 * Score-App". Antes todas las pantallas decían "Score-App", y con varias
 * pestañas abiertas, o con un lector de pantalla, no se sabía cuál era
 * cuál. `null`/`undefined` (dato todavía cargando) deja solo el sitio. */
export function useTituloPagina(titulo: string | null | undefined) {
  useEffect(() => {
    document.title = titulo ? `${titulo} · ${SITIO}` : SITIO;
  }, [titulo]);
}
